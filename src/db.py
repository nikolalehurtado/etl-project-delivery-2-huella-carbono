"""Conexion al Data Warehouse MySQL."""

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from src import config

# Codigos de error de MySQL que indican una falla de conexion o servidor (transitoria):
# 2002/2003 no se puede conectar, 2006 el servidor se fue, 2013 se perdio la conexion,
# 1040 demasiadas conexiones, 1205 timeout por bloqueo, 1213 deadlock.
TRANSIENT_MYSQL_CODES = {2002, 2003, 2006, 2013, 1040, 1205, 1213}


def _check_credentials():
    if not config.DB_USER or not config.DB_PASSWORD:
        raise RuntimeError(
            "Faltan MYSQL_USER o MYSQL_PASSWORD en el entorno (.env). "
            "No se puede conectar al Data Warehouse."
        )


def sqlalchemy_engine(database=None):
    """Engine de SQLAlchemy (lecturas con pandas y consultas de los KPI)."""
    _check_credentials()
    url = URL.create(
        "mysql+pymysql",
        username=config.DB_USER,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=config.DB_PORT,
        database=database or config.DW_DB,
    )
    return create_engine(url, pool_pre_ping=True)


def pymysql_connection(database=None, autocommit=False):
    """Conexion directa (necesaria para transacciones explicitas en la carga)."""
    _check_credentials()
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=database or config.DW_DB,
        charset="utf8mb4",
        connect_timeout=10,
        autocommit=autocommit,
    )


def is_transient(exc):
    """¿La falla puede desaparecer en otro intento sin cambiar datos ni codigo?

    Transitorias (se reintentan): MySQL reiniciando o caido, red interrumpida,
    conexion rechazada o cortada, deadlock.
    Deterministas (NO se reintentan): tabla inexistente, tipo invalido, violacion
    de llave o restriccion, conteo no conciliado: el mismo lote fallaria igual.
    """
    original = getattr(exc, "orig", None) or exc          # SQLAlchemy envuelve el error real
    if isinstance(original, pymysql.err.OperationalError):
        code = original.args[0] if original.args else None
        return code in TRANSIENT_MYSQL_CODES
    return isinstance(original, (pymysql.err.InterfaceError, ConnectionError, TimeoutError))
