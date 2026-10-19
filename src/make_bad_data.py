"""
Prepara el lote de la PRUEBA B (falla Critical controlada).

NO modifica los archivos originales: crea una copia de "Datos de la vivienda" en data/test/
con UNA violacion deterministica de la regla Critical DQ08 (P1_DEPARTAMENTO debe ser un codigo
DIVIPOLA valido: es la llave de integracion con la API). El resto de tablas se lee de data/raw/ecv/.

Ejecucion (dentro del contenedor, donde estan pandas y las rutas del proyecto):
    docker compose exec airflow-scheduler python /opt/airflow/src/make_bad_data.py

Luego se dispara el DAG con el parametro ecv_source = test
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd                                   # noqa: E402

from src import config                                # noqa: E402
from src.extract import _find_ecv_file                # noqa: E402

INVALID_DEPARTMENT_CODE = "999"                       # no existe en DIVIPOLA


def main():
    source = _find_ecv_file("vivienda", config.ECV_TABLES["vivienda"],
                            [config.ECV_DIR, config.RAW_DIR])
    df = pd.read_csv(source, sep=config.ECV_SEP, encoding=config.ECV_ENCODING,
                     dtype=str, keep_default_na=False)
    column = next(c for c in df.columns if str(c).strip().upper() == "P1_DEPARTAMENTO")
    row = df.index[0]
    original = df.loc[row, column]
    df.loc[row, column] = INVALID_DEPARTMENT_CODE

    config.TEST_DIR.mkdir(parents=True, exist_ok=True)
    out = config.TEST_DIR / source.name
    df.to_csv(out, sep=config.ECV_SEP, encoding=config.ECV_ENCODING, index=False)
    print(f"Lote de prueba creado: {out}")
    print(f"Fila {row}: P1_DEPARTAMENTO {original} -> {INVALID_DEPARTMENT_CODE}")
    print("Regla que debe bloquear: DQ08 (Critical) en validate_primary_raw")


if __name__ == "__main__":
    main()
