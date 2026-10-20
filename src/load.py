"""
LOAD — PENDIENTE (Persona 3, con apoyo de Persona 1 para la Prueba C).

Estrategia de repetibilidad sugerida para MySQL (InnoDB):
  * CREATE TABLE IF NOT EXISTS (sql/dw_schema.sql) fuera de la transaccion: en MySQL el DDL
    confirma la transaccion de forma implicita, por eso TRUNCATE tampoco es atomico.
  * BEGIN; DELETE de hechos y luego dimensiones; INSERT de dimensiones y luego hechos;
    verificar conteos contra los archivos preparados; registrar la carga en una tabla de
    auditoria (run_id, conteos); COMMIT. Si algo falla: ROLLBACK y el DW queda como estaba.
  * Re-ejecutar el mismo lote deja exactamente el mismo contenido (llaves deterministas).

Debe entregar evidencia de conciliacion (conteos aceptados, de dimensiones, de hechos y no emparejados).
"""


import pandas as pd
import mysql.connector
import logging
from src import config # Asume que aquí están las credenciales

log = logging.getLogger(__name__)

def load_dw(prepared_tables, run_id):
    """
    Carga dimensional a MySQL garantizando la Prueba C (re-ejecución segura).
    Usa DELETE transaccional en lugar de TRUNCATE.
    """
    # Cambia config.MYSQL_CONFIG por la variable real donde tengan sus credenciales
    db_config = config.MYSQL_CONFIG 
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 1. Iniciar transacción
        conn.start_transaction()
        
        # 2. Limpieza transaccional: Primero la tabla hija (hechos), luego padres (dimensiones)
        cursor.execute("DELETE FROM fact_huella_carbono;")
        cursor.execute("DELETE FROM dim_hogar;")
        cursor.execute("DELETE FROM dim_ubicacion;")
        cursor.execute("DELETE FROM dim_clima;")
        cursor.execute("DELETE FROM dim_combustibles;")
        cursor.execute("DELETE FROM dim_tarifas_energia;")
        
        # 3. Inserción: Primero las dimensiones (padres), luego la tabla de hechos (hija)
        orden_carga = [
            ("dim_hogar", "dim_hogar"),
            ("dim_ubicacion", "dim_ubicacion"),
            ("dim_clima", "dim_clima"),
            ("dim_combustibles", "dim_combustibles"),
            ("dim_tarifas", "dim_tarifas_energia"), # El CSV sale como dim_tarifas, la tabla es dim_tarifas_energia
            ("fact_huella_carbono", "fact_huella_carbono")
        ]
        
        conteos = {}
        
        for nombre_csv, nombre_tabla in orden_carga:
            if nombre_csv in prepared_tables:
                df = pd.read_csv(prepared_tables[nombre_csv])
                if df.empty:
                    continue
                    
                columnas = ", ".join(df.columns)
                placeholders = ", ".join(["%s"] * len(df.columns))
                query = f"INSERT INTO {nombre_tabla} ({columnas}) VALUES ({placeholders})"
                
                # Convertir nulos de Pandas (NaN) a nulos de Python (None) para que MySQL no falle
                datos = [tuple(None if pd.isna(val) else val for val in fila) for fila in df.itertuples(index=False, name=None)]
                
                cursor.executemany(query, datos)
                conteos[nombre_tabla] = len(df)
                
        # 4. Si todo sale bien, confirmamos la transacción (Commit)
        conn.commit()
        log.info(f"Carga exitosa para lote {run_id}. Conciliación: {conteos}")
        
        return conteos
        
    except Exception as e:
        # 5. Si ALGO falla, deshacemos todo (Rollback) para no dejar la BD a medias (Prueba C)
        if 'conn' in locals() and conn.is_connected():
            conn.rollback()
        log.error(f"Falla en la carga, haciendo rollback. Error: {e}")
        raise
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
    raise NotImplementedError(
        "PENDIENTE (Persona 3): carga dimensional a MySQL. Ver docstring de src/load.py."
    )
