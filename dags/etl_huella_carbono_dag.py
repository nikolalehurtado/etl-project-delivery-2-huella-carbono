"""
ETL Huella de Carbono — Segunda Entrega (UAO)

Airflow 3.1.8 (TaskFlow API, airflow.sdk) · Great Expectations Core 1.23.1

Integra la ECV 2025 (DANE, CSV) con la temperatura del IDEAM (API de datos.gov.co) en un
Data Warehouse dimensional MySQL que responde R1-R7.

    extract_primary -> validate_primary_raw ----\
                                                 >-> transform_and_clean_and_integrate -> validate_prepared -> load_dimensional_dw
    extract_api     -> validate_api_raw --------/

Principios aplicados:
- El DAG solo ORQUESTA; la logica vive en src/ (extract, validation, transform, load).
- Las tareas intercambian RUTAS y metadatos compactos, nunca DataFrames completos.
- Critical en una compuerta => la tarea falla y lo posterior no se ejecuta.
- Reintentos SOLO donde la falla puede ser transitoria (API y base de datos).
- Cada ejecucion trabaja en data/work/<run_id>/ y deja su evidencia en gx/.
"""

import logging
from datetime import timedelta

import pendulum
from airflow.sdk import Param, dag, get_current_context, task

log = logging.getLogger(__name__)

# Politica de reintentos (README, seccion de politica de fallas)
NO_RETRY = {"retries": 0}
API_RETRY = {                      # fallas transitorias de la API (timeout, red, 429, 5xx)
    "retries": 3,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=60),
}
DB_RETRY = {                       # fallas transitorias de red / base de datos
    "retries": 3,
    "retry_delay": timedelta(seconds=30),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=3),
}


def _run_id():
    return get_current_context()["run_id"]


def _db_call(func, *args):
    """Ejecuta una operacion de base de datos aplicando la politica de reintentos selectiva.

    Falla transitoria (conexion/red)   -> se relanza: Airflow la reintenta (DB_RETRY).
    Falla determinista (datos/esquema) -> AirflowFailException: falla de inmediato,
                                          sin gastar reintentos que repetirian el error.
    """
    from airflow.exceptions import AirflowFailException
    from src.db import is_transient
    try:
        return func(*args)
    except NotImplementedError:
        raise
    except Exception as exc:
        if is_transient(exc):
            log.warning("Falla TRANSITORIA de base de datos (se reintentara): %s", exc)
            raise
        raise AirflowFailException(f"Falla DETERMINISTA, no se reintenta: {exc}") from exc


@dag(
    dag_id="etl_huella_carbono",
    description="ECV 2025 + temperatura IDEAM -> GX raw -> integracion -> GX preparado -> DW MySQL",
    schedule=None,                         # ejecuciones manuales para inspeccionar cada DAG Run
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,                     # dos cargas simultaneas al DW no son seguras
    default_args={"execution_timeout": timedelta(minutes=20)},
    params={
        "ecv_source": Param(
            "raw",
            type="string",
            enum=["raw", "test"],
            description="raw = datos reales en data/raw/ecv/. "
                        "test = lote de la Prueba B (data/test/, creado con src/make_bad_data.py)",
        ),
    },
    tags=["etl", "segunda-entrega", "gx", "ecv", "ideam"],
)
def etl_huella_carbono():

    # ------------------------------------------------------------------ EXTRACT
    @task(**NO_RETRY)
    def extract_primary():
        """ECV en archivos locales: si falta un archivo o una columna, reintentar no lo arregla."""
        from src.extract import extract_primary as run
        return run(_run_id(), get_current_context()["params"]["ecv_source"])

    @task(**API_RETRY)
    def extract_api():
        """Temperatura IDEAM por la API: una caida temporal si justifica reintento (con reanudacion)."""
        from airflow.exceptions import AirflowFailException
        from src.extract import APIContractError, extract_api as run
        try:
            return run(_run_id())
        except APIContractError as exc:
            raise AirflowFailException(f"Falla DETERMINISTA de la API, no se reintenta: {exc}") from exc

    # --------------------------------------------------------- RAW VALIDATION
    @task(**NO_RETRY)
    def validate_primary_raw(meta):
        """¿Pueden los datos de la ECV entrar a la transformacion?"""
        from src.validation import run_ecv_raw_gate
        return run_ecv_raw_gate(meta, _run_id())

    @task(**NO_RETRY)
    def validate_api_raw(meta):
        """¿Pueden los datos de la API entrar a la transformacion?"""
        from src.validation import run_api_raw_gate
        return run_api_raw_gate(meta, _run_id())

    # --------------------------------------------------------------- TRANSFORM
    @task(**NO_RETRY)
    def transform_and_clean_and_integrate(ecv_meta, api_meta):
        """Limpieza, armonizacion, integracion por departamento y tablas del modelo estrella."""
        from src.transform import transform_and_integrate as run
        return run(ecv_meta, api_meta)

    # ---------------------------------------------------- PREPARED VALIDATION
    @task(**NO_RETRY)
    def validate_prepared(prepared):
        """Compuerta 3: valida las 6 tablas preparadas (DQ19-DQ30) antes de la carga al DW.

        Una suite GX por tabla. Si CUALQUIERA tiene un Critical, la tarea falla y
        load_dimensional_dw no se ejecuta (las dependencias de Airflow lo garantizan).
        """
        from src.validation import run_prepared_gate
        return run_prepared_gate(prepared, _run_id())

    # -------------------------------------------------------------------- LOAD
    @task(**DB_RETRY)
    def load_dimensional_dw(prepared):
        """Carga transaccional al DW MySQL: un reintento o re-ejecucion no duplica."""
        from src.load import load_dw as run
        return _db_call(run, prepared["tables"], _run_id())

    # ----------------------------------------------------------- DEPENDENCIAS
    ecv_raw = extract_primary()
    api_raw = extract_api()

    ecv_gate = validate_primary_raw(ecv_raw)
    api_gate = validate_api_raw(api_raw)

    prepared = transform_and_clean_and_integrate(ecv_raw, api_raw)
    # Compuerta raw: la transformacion espera a que AMBAS ramas superen la politica
    [ecv_gate, api_gate] >> prepared

    prepared_gate = validate_prepared(prepared)
    loaded = load_dimensional_dw(prepared)
    # Compuerta preparada: no se carga si la validacion preparada no tuvo exito
    prepared_gate >> loaded


etl_huella_carbono()
