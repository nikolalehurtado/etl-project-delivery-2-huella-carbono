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


def load_dw(prepared_tables, run_id):
    raise NotImplementedError(
        "PENDIENTE (Persona 3): carga dimensional a MySQL. Ver docstring de src/load.py."
    )
