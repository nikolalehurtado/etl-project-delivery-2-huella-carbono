"""
Pruebas de las correcciones de la segunda entrega sobre variables de la ECV 2025:
  - D-07: el estrato es P8520S1A1 (0, 8, 9 y vacios pasan a estrato 0).
  - S17: pagos que cubren varios meses (P5018S1, P3163S1) y codigos 98/99.

Ejecucion:
    python -m unittest tests/test_pagos_y_estrato.py
"""

import unittest

import numpy as np
import pandas as pd

from src.transform import _normalizar_pagos, _reclasificar_estrato


class EstratoTest(unittest.TestCase):

    def test_codigos_0_8_9_y_vacios_pasan_a_estrato_cero(self):
        df = pd.DataFrame({"ESTRATO": [1, 2, 3, 4, 5, 6, 0, 8, 9, np.nan]})
        out, n = _reclasificar_estrato(df)
        self.assertEqual(out["ESTRATO"].tolist(), [1, 2, 3, 4, 5, 6, 0, 0, 0, 0])
        self.assertEqual(n, 4)


class PagosTest(unittest.TestCase):

    def _df(self):
        return pd.DataFrame({
            "P5018":   [60000, 120000, 98, 50000, 90000],
            "P5018S1": [1,     2,      np.nan, np.nan, 3],
            "P3163":   [30000, 60000, 99, np.nan, 30000],
            "P3163S1": [1,     2,      np.nan, np.nan, 99],     # 99 no es un numero de meses valido
            "P8540":   [0,     98,     99, 80000, 100000],
        })

    def test_pago_de_varios_meses_se_divide_entre_los_meses(self):
        out, log = _normalizar_pagos(self._df())
        self.assertEqual(out.loc[0, "P5018"], 60000)           # 1 mes: igual
        self.assertEqual(out.loc[1, "P5018"], 60000)           # 120.000 en 2 meses = 60.000/mes
        self.assertEqual(out.loc[4, "P5018"], 30000)           # 90.000 en 3 meses = 30.000/mes
        self.assertEqual(out.loc[1, "P3163"], 30000)
        self.assertEqual(log["p5018_pagos_de_varios_meses_ajustados"], 2)

    def test_meses_ausentes_o_invalidos_se_suponen_un_mes(self):
        out, _ = _normalizar_pagos(self._df())
        self.assertEqual(out.loc[3, "P5018"], 50000)           # sin dato de meses
        self.assertEqual(out.loc[4, "P3163"], 30000)           # meses = 99 -> 1 mes

    def test_codigos_98_y_99_no_se_leen_como_pesos(self):
        out, log = _normalizar_pagos(self._df())
        self.assertTrue(np.isnan(out.loc[2, "P5018"]))
        self.assertTrue(np.isnan(out.loc[2, "P3163"]))
        self.assertTrue(np.isnan(out.loc[1, "P8540"]) and np.isnan(out.loc[2, "P8540"]))
        self.assertEqual(out.loc[3, "P8540"], 80000)
        self.assertEqual((log["p5018_codigos_98_99_a_nulo"], log["p3163_codigos_98_99_a_nulo"],
                          log["p8540_codigos_98_99_a_nulo"]), (1, 1, 2))


if __name__ == "__main__":
    unittest.main()
