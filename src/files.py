"""Lectura uniforme de los archivos del pipeline."""

import pandas as pd


def read_table(path):
    """Lee un CSV tratando como nulo SOLO la celda vacia.

    Por defecto pandas convierte textos como "N/A", "NA", "None" o "null" en nulos.
    Aqui decidir si un texto es nulo es una regla de transformacion explicita,
    no un efecto silencioso de la lectura.
    """
    return pd.read_csv(path, keep_default_na=False, na_values=[""])
