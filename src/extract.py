"""
EXTRACT — adquisicion de las dos fuentes.

Regla de diseno: la extraccion NO limpia nada. Copia los datos tal como llegan a
archivos raw del lote (run_id), para que la validacion raw evalue la fuente real y
para conservar evidencia investigable.

  extract_primary -> ECV 2025 (DANE): 4 capitulos en CSV, solo las columnas requeridas
  extract_api     -> API de temperatura del IDEAM (datos.gov.co, Socrata SODA)

Politica de fallas de la API (ver README, politica de reintentos):
  - APITransientError  (timeout, red, HTTP 429/5xx): puede desaparecer -> se reintenta
  - APIContractError   (HTTP 4xx, forma inesperada): determinista      -> no se reintenta
"""

import json
import logging
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from src import config
from src.files import read_table

log = logging.getLogger(__name__)


class APITransientError(Exception):
    """Falla de la API que puede desaparecer en otro intento."""


class APIContractError(Exception):
    """Falla determinista de la API: repetir la peticion reproduce el error."""


# ---------------------------------------------------------------------------
# Utilidades de lote
# ---------------------------------------------------------------------------
def _safe(run_id):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(run_id))


def batch_dir(run_id, *parts):
    """Carpeta de trabajo propia de cada ejecucion: data/work/<run_id>/raw/..."""
    path = config.WORK_DIR / _safe(run_id) / "raw"
    for part in parts:
        path = path / part
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_raw(path):
    return read_table(Path(path))


def _normalize(text):
    """Minusculas y sin tildes, para comparar nombres de archivo."""
    text = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


# ---------------------------------------------------------------------------
# FUENTE PRIMARIA: ECV 2025 (DANE)
# ---------------------------------------------------------------------------
def _find_ecv_file(table, spec, search_dirs):
    for folder in search_dirs:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.csv")):
            name = _normalize(path.name)
            if all(k in name for k in spec["keywords"]) and not any(
                    x in name for x in spec.get("exclude", [])):
                return path
    raise FileNotFoundError(
        f"No se encontro el archivo ECV '{table}' (palabras clave {spec['keywords']}) "
        f"en: {[str(d) for d in search_dirs]}. Descarga los CSV de DANE y colocalos en data/raw/ecv/."
    )


def extract_primary(run_id, ecv_source="raw"):
    """Lee los 4 capitulos de la ECV, conserva solo las columnas requeridas y guarda el lote raw.

    ecv_source = "raw"  -> data/raw/ecv/ (datos reales)
    ecv_source = "test" -> data/test/ primero (lote de la Prueba B) y data/raw/ecv/ para el resto
    """
    search_dirs = ([config.TEST_DIR, config.ECV_DIR, config.RAW_DIR] if ecv_source == "test"
                   else [config.ECV_DIR, config.RAW_DIR])
    out_dir = batch_dir(run_id)
    tables = {}

    for table, spec in config.ECV_TABLES.items():
        path = _find_ecv_file(table, spec, search_dirs)
        header = pd.read_csv(path, sep=config.ECV_SEP, encoding=config.ECV_ENCODING, nrows=0)
        by_name = {str(c).strip().upper(): c for c in header.columns}

        missing = [c for c in spec["columns"] if c not in by_name]
        if missing:   # contrato de la fuente incumplido: reintentar no lo arregla
            raise ValueError(f"[{table}] Faltan columnas requeridas en {path.name}: {missing}")

        df = pd.read_csv(
            path, sep=config.ECV_SEP, encoding=config.ECV_ENCODING,
            usecols=[by_name[c] for c in spec["columns"]],
            keep_default_na=False, na_values=[""],
        )
        df.columns = [str(c).strip().upper() for c in df.columns]
        df = df[spec["columns"]]

        out = out_dir / f"ecv_{table}_raw.csv"
        df.to_csv(out, index=False)
        tables[table] = {"path": str(out), "rows": int(len(df)), "source_file": str(path)}
        log.info("ECV %-16s %8s filas  <- %s", table, f"{len(df):,}", path.name)

    meta = {
        "batch_id": _safe(run_id),
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "ecv_source": ecv_source,
        "tables": tables,
    }
    (out_dir / "ecv_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


# ---------------------------------------------------------------------------
# FUENTE SECUNDARIA: API de temperatura IDEAM (Socrata SODA en datos.gov.co)
# ---------------------------------------------------------------------------
def _windows(start, end, days):
    """Ventanas [inicio, fin) de `days` dias entre start y end (end exclusivo)."""
    current = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while current < stop:
        nxt = min(current + timedelta(days=days), stop)
        yield current, nxt
        current = nxt


def _query_params(win_start, win_end):
    """Consulta agregada por estacion: el servidor entrega suma, conteo, minimo y maximo.

    Se agrega en el servidor porque el dataset tiene lecturas cada hora de cientos de
    estaciones y descargarlas todas es lento e inestable. suma y n permiten recalcular
    EXACTAMENTE la media de cualquier periodo; minimo y maximo permiten validar el rango.
    """
    return {
        "$select": ("codigoestacion,nombreestacion,departamento,municipio,latitud,longitud,"
                    "sum(valorobservado) as suma,count(*) as n,"
                    "min(valorobservado) as minimo,max(valorobservado) as maximo"),
        "$where": (f"codigosensor='{config.API_SENSOR_CODE}' "
                   f"AND fechaobservacion >= '{win_start.isoformat()}T00:00:00' "
                   f"AND fechaobservacion < '{win_end.isoformat()}T00:00:00'"),
        "$group": "codigoestacion,nombreestacion,departamento,municipio,latitud,longitud",
        "$order": "codigoestacion",
    }


def _fetch_page(session, params):
    try:
        resp = session.get(config.API_URL, params=params, timeout=config.API_TIMEOUT)
    except (requests.Timeout, requests.ConnectionError) as exc:
        raise APITransientError(f"{type(exc).__name__}: {exc}") from exc
    if resp.status_code == 429 or resp.status_code >= 500:
        raise APITransientError(f"HTTP {resp.status_code}")
    if resp.status_code >= 400:
        raise APIContractError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        data = resp.json()
    except ValueError as exc:      # respuesta no JSON (p. ej. pagina de error del gateway)
        raise APITransientError("La respuesta no es JSON valido") from exc
    if not isinstance(data, list):
        raise APIContractError(f"Se esperaba una lista JSON y llego: {str(data)[:300]}")
    return data


def _fetch_window(session, win_start, win_end):
    """Todas las filas de una ventana (con paginacion y reintentos locales ante fallas transitorias)."""
    rows, offset = [], 0
    while True:
        params = {**_query_params(win_start, win_end),
                  "$limit": config.API_PAGE_LIMIT, "$offset": offset}
        for attempt in range(1, config.API_ATTEMPTS_PER_WINDOW + 1):
            try:
                page = _fetch_page(session, params)
                break
            except APITransientError as exc:
                if attempt == config.API_ATTEMPTS_PER_WINDOW:
                    raise
                wait = min(5 * 2 ** (attempt - 1), 60)
                log.warning("Ventana %s: falla transitoria (%s). Intento %s/%s, espera %ss",
                            win_start, exc, attempt, config.API_ATTEMPTS_PER_WINDOW, wait)
                time.sleep(wait)
        rows.extend(page)
        if len(page) < config.API_PAGE_LIMIT:
            return rows
        offset += config.API_PAGE_LIMIT


def extract_api(run_id):
    """Extrae la temperatura del IDEAM por ventanas de tiempo y guarda el lote raw.

    Reanudable: cada ventana descargada se guarda tal como llego (JSON) en
    data/work/<run_id>/raw/api/. Si Airflow reintenta la tarea con el mismo run_id,
    las ventanas ya descargadas no se piden de nuevo.
    """
    started = time.time()
    out_dir = batch_dir(run_id)
    win_dir = batch_dir(run_id, "api")
    session = requests.Session()
    session.headers["Accept"] = "application/json"
    if config.API_APP_TOKEN:
        session.headers["X-App-Token"] = config.API_APP_TOKEN

    records, windows = [], list(_windows(config.API_START_DATE, config.API_END_DATE,
                                         config.API_WINDOW_DAYS))
    reused = 0
    for i, (w_start, w_end) in enumerate(windows, start=1):
        cache = win_dir / f"window_{w_start.isoformat()}.json"
        if cache.exists():
            rows = json.loads(cache.read_text(encoding="utf-8"))
            reused += 1
        else:
            rows = _fetch_window(session, w_start, w_end)
            tmp = cache.with_suffix(".tmp")
            tmp.write_text(json.dumps(rows), encoding="utf-8")
            tmp.replace(cache)
        for row in rows:
            records.append({**row, "window_start": w_start.isoformat(),
                            "window_end": w_end.isoformat()})
        log.info("API ventana %s/%s [%s, %s): %s filas", i, len(windows), w_start, w_end, len(rows))

    df = pd.DataFrame(records) if records else pd.DataFrame(columns=config.API_RAW_COLUMNS)
    out = out_dir / "api_ideam_raw.csv"
    df.to_csv(out, index=False)

    meta = {
        "batch_id": _safe(run_id),
        "source": config.API_URL,
        "path": str(out),
        "rows": int(len(df)),
        "columns": int(df.shape[1]),
        "windows": len(windows),
        "windows_reused_from_cache": reused,
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "date_range": [config.API_START_DATE, config.API_END_DATE],
        "sensor_code": config.API_SENSOR_CODE,
        "window_days": config.API_WINDOW_DAYS,
        "app_token_used": bool(config.API_APP_TOKEN),
        "elapsed_seconds": round(time.time() - started, 1),
        "query_template": _query_params(windows[0][0], windows[0][1]) if windows else None,
    }
    (out_dir / "api_manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("API IDEAM extraida: %s", {k: v for k, v in meta.items() if k != "query_template"})
    return meta
