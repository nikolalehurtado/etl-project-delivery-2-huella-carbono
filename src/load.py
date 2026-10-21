"""
LOAD — carga dimensional al Data Warehouse MySQL con re-ejecucion segura (Prueba C).

Estrategia (README, secciones 15 y 20):
  1. El esquema (sql/dw_schema.sql) se aplica con CREATE TABLE IF NOT EXISTS, FUERA de la
     transaccion: en MySQL el DDL confirma de forma implicita, por eso TRUNCATE tampoco es atomico.
  2. Dentro de UNA transaccion: DELETE (hechos primero, luego dimensiones) -> INSERT (dimensiones
     primero, luego hechos) -> conciliacion de conteos contra los archivos preparados ->
     registro en etl_audit_log -> COMMIT.
  3. Cualquier falla (incluida una conciliacion que no cuadra) hace ROLLBACK: el DW queda
     exactamente como estaba antes de empezar.
  4. Las llaves surrogate vienen deterministas de los archivos preparados, asi que cargar el
     mismo lote dos veces deja el mismo contenido (no duplica).

Politica de fallas: las excepciones de conexion se relanzan tal cual (src.db.is_transient decide
si Airflow reintenta); los errores de datos o de conciliacion son deterministas (no se reintentan).
"""

import logging
import re
from datetime import datetime

import pandas as pd

from src import config
from src.db import pymysql_connection

log = logging.getLogger(__name__)

# Orden de INSERT: dimensiones (padres) antes que hechos (hija). El DELETE usa el orden inverso.
LOAD_ORDER = ["dim_hogar", "dim_ubicacion", "dim_clima", "dim_combustibles",
              "dim_tarifas", "fact_huella_carbono"]
CHUNK_ROWS = 5000


class LoadReconciliationError(ValueError):
    """Los conteos del DW no coinciden con los archivos preparados (falla determinista)."""


def _split_statements(sql_text):
    """Separa sql/dw_schema.sql en sentencias (quita comentarios '-- ...')."""
    lines = [re.sub(r"--.*$", "", line) for line in sql_text.splitlines()]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def apply_schema():
    """Crea las tablas si no existen (idempotente). Conexion propia, fuera de la carga."""
    sql = (config.SQL_DIR / "dw_schema.sql").read_text(encoding="utf-8")
    conn = pymysql_connection(autocommit=True)
    try:
        with conn.cursor() as cur:
            for stmt in _split_statements(sql):
                cur.execute(stmt)
    finally:
        conn.close()


def _read_tables(prepared_tables):
    missing = [t for t in LOAD_ORDER if t not in prepared_tables]
    if missing:
        raise ValueError(f"Faltan tablas preparadas para cargar: {missing}")
    frames = {}
    for name in LOAD_ORDER:
        df = pd.read_csv(prepared_tables[name])
        if df.empty:
            raise ValueError(f"La tabla preparada {name} esta vacia; no se carga")
        # NaN/NA de pandas -> None, y escalares nativos de Python (pymysql no acepta numpy)
        frames[name] = df.astype(object).where(df.notna(), None)
    return frames


def _insert(cur, table, df):
    cols = ", ".join(f"`{c}`" for c in df.columns)
    marks = ", ".join(["%s"] * len(df.columns))
    sql = f"INSERT INTO `{table}` ({cols}) VALUES ({marks})"
    rows = df.values.tolist()
    for i in range(0, len(rows), CHUNK_ROWS):
        cur.executemany(sql, rows[i:i + CHUNK_ROWS])


def _audit(cur, run_id, counts, status):
    now = datetime.now()
    cur.executemany(
        "INSERT INTO etl_audit_log (run_id, loaded_at, table_name, rows_loaded, status) "
        "VALUES (%s, %s, %s, %s, %s)",
        [(str(run_id), now, table, int(n), status) for table, n in counts.items()],
    )


def _audit_failure(run_id, error):
    """Deja constancia del intento fallido en una conexion aparte (la carga ya hizo ROLLBACK)."""
    try:
        conn = pymysql_connection(autocommit=True)
        try:
            with conn.cursor() as cur:
                _audit(cur, run_id, {f"RUN_FAILED: {type(error).__name__}"[:50]: 0}, "FAILED")
        finally:
            conn.close()
    except Exception as exc:        # la auditoria nunca debe tapar el error original
        log.warning("No se pudo registrar la falla en etl_audit_log: %s", exc)


def load_dw(prepared_tables, run_id):
    """Carga las 6 tablas preparadas al DW. Devuelve la conciliacion de la carga."""
    frames = _read_tables(prepared_tables)
    expected = {name: len(df) for name, df in frames.items()}
    apply_schema()

    conn = pymysql_connection(autocommit=False)
    try:
        with conn.cursor() as cur:
            for name in reversed(LOAD_ORDER):                       # hechos primero
                cur.execute(f"DELETE FROM `{name}`")
            for name in LOAD_ORDER:                                 # dimensiones primero
                _insert(cur, name, frames[name])
                log.info("Insertadas %s filas en %s", f"{expected[name]:,}", name)

            loaded = {}
            for name in LOAD_ORDER:
                cur.execute(f"SELECT COUNT(*) FROM `{name}`")
                loaded[name] = cur.fetchone()[0]
            diffs = {n: (expected[n], loaded[n]) for n in LOAD_ORDER if expected[n] != loaded[n]}
            if diffs:
                raise LoadReconciliationError(
                    f"Conteos no concilian (esperado, cargado): {diffs}")

            cur.execute("SELECT SUM(clima_emparejado = 0) FROM fact_huella_carbono")
            sin_clima = int(cur.fetchone()[0] or 0)
            _audit(cur, run_id, loaded, "SUCCESS")
        conn.commit()
    except Exception as exc:
        conn.rollback()
        log.error("Falla en la carga del lote %s; ROLLBACK, el DW queda como estaba: %s", run_id, exc)
        conn.close()
        _audit_failure(run_id, exc)
        raise
    conn.close()

    result = {"run_id": str(run_id), "counts": loaded, "reconciled": True,
              "hechos_sin_clima": sin_clima}
    log.info("Carga exitosa del lote %s. Conciliacion: %s", run_id, result)
    return result
