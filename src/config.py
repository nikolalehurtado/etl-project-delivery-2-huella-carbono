"""
Configuracion central del pipeline (rutas, conexiones y contratos de datos).

Todas las rutas apuntan a carpetas montadas en los contenedores de Airflow
(ver docker-compose.yaml). Fuera de Docker se puede cambiar la raiz con la
variable de entorno PROJECT_ROOT (util para pruebas locales).
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", "/opt/airflow"))

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
ECV_DIR = RAW_DIR / "ecv"             # CSV originales de la ECV (DANE), solo lectura
REFERENCE_DIR = DATA_DIR / "reference"  # tablas de referencia versionadas (DIVIPOLA, factores)
TEST_DIR = DATA_DIR / "test"          # lotes de prueba (falla controlada)
WORK_DIR = DATA_DIR / "work"          # archivos intermedios por ejecucion (run_id)
SQL_DIR = PROJECT_ROOT / "sql"
GX_DIR = PROJECT_ROOT / "gx"          # suites exportadas y resultados de Great Expectations

# ---------------------------------------------------------------------------
# Fuente primaria: ECV 2025 (DANE)
# ---------------------------------------------------------------------------
ECV_SEP = ";"
ECV_ENCODING = "latin-1"

# Cada tabla se identifica por palabras clave del nombre del archivo (sin tildes ni
# mayusculas). La tabla "condiciones" excluye el archivo "(programas)", que es otro capitulo.
HOUSEHOLD_KEYS = ["DIRECTORIO", "SECUENCIA_P"]   # grano: un hogar por fila

ECV_TABLES = {
    "servicios": {
        "keywords": ["servicios"],
        "columns": [*HOUSEHOLD_KEYS, "P5018", "P5010", "P8536", "P8540", "P3163"],
    },
    "vivienda": {
        "keywords": ["vivienda"],
        "columns": [*HOUSEHOLD_KEYS, "P1_DEPARTAMENTO", "P1_MUNICIPIO"],
    },
    "caracteristicas": {
        "keywords": ["caracter"],
        "columns": [*HOUSEHOLD_KEYS, "ORDEN"],       # una fila por persona: sirve para contar integrantes
    },
    "condiciones": {
        "keywords": ["condiciones", "tenencia"],
        "exclude": ["programa"],
        "columns": [*HOUSEHOLD_KEYS, "P1077S15", "P1077S11", "P1077S12"],
    },
}

# ---------------------------------------------------------------------------
# Fuente secundaria: API de temperatura del IDEAM en datos.gov.co (Socrata SODA)
# ---------------------------------------------------------------------------
API_URL = os.getenv("IDEAM_API_URL", "https://www.datos.gov.co/resource/sbwg-7ju4.json")
API_SENSOR_CODE = "0068"              # "Temp Aire 2 m", unidad C
API_APP_TOKEN = os.getenv("DATOS_GOV_APP_TOKEN") or None     # opcional
API_START_DATE = os.getenv("API_START_DATE", "2025-01-01")
API_END_DATE = os.getenv("API_END_DATE", "2026-01-01")       # exclusivo
API_WINDOW_DAYS = int(os.getenv("API_WINDOW_DAYS", "7"))
API_PAGE_LIMIT = 50000                # maximo de filas por peticion en SODA 2.1
API_TIMEOUT = (15, 120)               # (conexion, lectura) en segundos
API_ATTEMPTS_PER_WINDOW = 3           # reintentos locales por ventana ante fallas transitorias
API_MIN_DEPARTMENTS = int(os.getenv("API_MIN_DEPARTMENTS", "20"))

# Columnas que devuelve la consulta agregada por estacion y ventana
API_RAW_COLUMNS = [
    "codigoestacion", "nombreestacion", "departamento", "municipio", "latitud", "longitud",
    "suma", "n", "minimo", "maximo", "window_start", "window_end",
]

# ---------------------------------------------------------------------------
# Data Warehouse (MySQL). Valores tomados de .env; nunca se escriben en el codigo.
# Dentro de Docker el host es el servicio "mysql-dw" y el puerto interno 3306.
# ---------------------------------------------------------------------------
DB_HOST = os.getenv("MYSQL_HOST", "mysql-dw")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_USER = os.getenv("MYSQL_USER")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD")
DW_DB = os.getenv("MYSQL_DATABASE", "huella_carbono_dw_v2")
