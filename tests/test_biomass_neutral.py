"""
Pruebas del tratamiento de la lena como carbono neutra (decision D-04).

Ejecucion:
    python -m unittest tests/test_biomass_neutral.py
"""

import unittest
from unittest.mock import patch

import pandas as pd

from src import config
from src.transform import _calcular_emisiones

TARIFAS = {0: 460, 1: 460, 2: 570, 3: 970, 4: 1150, 5: 1380, 6: 1380}
FACTORES = {1: 112000, 2: 63100, 3: 56100}


def _hogares():
    """Tres hogares del mismo estrato y con el mismo pago de energia; solo cambia el combustible."""
    return pd.DataFrame({
        "P5018": [46000, 46000, 46000],
        "P5010": [1, 1, 1],
        "P8536": [6, 4, 2],            # 6 = lena, 4 = GLP, 2 = gas natural
        "P3163": [0, 0, 18000],        # gasto de gas natural
        "P8540": [0, 32000, 0],        # gasto de GLP / otros
    })


class LenaCarbonoNeutroTest(unittest.TestCase):

    def test_por_defecto_la_lena_no_suma_co2(self):
        self.assertTrue(config.BIOMASS_CO2_NEUTRAL)
        out = _calcular_emisiones(_hogares(), TARIFAS, 0.097, FACTORES)
        lena = out.loc[0]
        self.assertEqual(lena["emisiones_coccion_kg"], 0)
        # sin cocina, la huella total es solo la de energia
        self.assertEqual(lena["huella_total_anual_kg"], lena["emisiones_energia_kg"])

    def test_los_combustibles_fosiles_siguen_sumando(self):
        out = _calcular_emisiones(_hogares(), TARIFAS, 0.097, FACTORES)
        self.assertGreater(out.loc[1, "emisiones_coccion_kg"], 0)   # GLP
        self.assertGreater(out.loc[2, "emisiones_coccion_kg"], 0)   # gas natural

    def test_la_energia_electrica_no_cambia(self):
        out = _calcular_emisiones(_hogares(), TARIFAS, 0.097, FACTORES)
        self.assertEqual(out["emisiones_energia_kg"].nunique(), 1)

    def test_con_la_opcion_apagada_se_recupera_el_calculo_de_la_primera_entrega(self):
        with patch.object(config, "BIOMASS_CO2_NEUTRAL", False):
            out = _calcular_emisiones(_hogares(), TARIFAS, 0.097, FACTORES)
        # 150 kg/mes * 15,6 MJ/kg / 1.000.000 * 112.000 kg/TJ * 12 meses = 3.144,96 kg/ano
        self.assertAlmostEqual(out.loc[0, "emisiones_coccion_kg"], 3144.96, places=2)

    def test_no_hay_emisiones_negativas(self):
        out = _calcular_emisiones(_hogares(), TARIFAS, 0.097, FACTORES)
        self.assertTrue((out["emisiones_coccion_kg"] >= 0).all())


if __name__ == "__main__":
    unittest.main()
