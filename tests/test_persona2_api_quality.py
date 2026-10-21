"""
Pruebas automatizadas para las responsabilidades de la Persona 2
(API de Temperatura IDEAM y Calidad de Datos con Great Expectations).

Ejecución:
    python -m unittest tests/test_persona2_api_quality.py
"""

import json
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
from great_expectations.expectations.metadata_types import FailureSeverity

from src import config
from src.extract import (
    APIContractError,
    APITransientError,
    _fetch_page,
    _query_params,
    _windows,
)
from src.validation import (
    SUITES,
    enforce_policy,
    failed_rules,
    run_suite,
)


class TestAPIClient(unittest.TestCase):
    """Pruebas del cliente y lógica de extracción de la API IDEAM."""

    def test_windows_generator(self):
        """Generación de ventanas de tiempo continuas sin solapamiento."""
        wins = list(_windows("2025-01-01", "2025-01-15", 7))
        self.assertEqual(len(wins), 2)
        self.assertEqual(wins[0], (date(2025, 1, 1), date(2025, 1, 8)))
        self.assertEqual(wins[1], (date(2025, 1, 8), date(2025, 1, 15)))

    def test_query_params_structure(self):
        """Parámetros de consulta SODA con agregación en el servidor."""
        params = _query_params(date(2025, 6, 1), date(2025, 6, 15))
        self.assertIn("$select", params)
        self.assertIn("$where", params)
        self.assertIn("$group", params)
        self.assertIn("codigosensor='0068'", params["$where"])
        self.assertIn("sum(valorobservado) as suma", params["$select"])
        self.assertIn("min(valorobservado) as minimo", params["$select"])
        self.assertIn("max(valorobservado) as maximo", params["$select"])

    def test_fetch_page_transient_error_on_500_or_429(self):
        """Errores 5xx y 429 se clasifican como transitorios."""
        session = MagicMock()
        resp_500 = MagicMock(status_code=500, text="Internal Server Error")
        session.get.return_value = resp_500
        with self.assertRaises(APITransientError):
            _fetch_page(session, {})

        resp_429 = MagicMock(status_code=429, text="Too Many Requests")
        session.get.return_value = resp_429
        with self.assertRaises(APITransientError):
            _fetch_page(session, {})

    def test_fetch_page_contract_error_on_400(self):
        """Errores 4xx (como 400 Bad Request) se tratan como fallas deterministas."""
        session = MagicMock()
        resp_400 = MagicMock(status_code=400, text="Bad Request: syntax error in $select")
        session.get.return_value = resp_400
        with self.assertRaises(APIContractError):
            _fetch_page(session, {})

    def test_fetch_page_success(self):
        """Respuesta exitosa 200 devuelve la lista de registros."""
        session = MagicMock()
        mock_data = [{"codigoestacion": "EST01", "suma": 150.0, "n": 6}]
        resp_200 = MagicMock(status_code=200)
        resp_200.json.return_value = mock_data
        session.get.return_value = resp_200

        res = _fetch_page(session, {})
        self.assertEqual(res, mock_data)


class TestCompuerta1ECV(unittest.TestCase):
    """Pruebas de calidad de datos para la Compuerta 1 (Raw ECV)."""

    def test_ecv_servicios_success(self):
        df = pd.DataFrame({
            "DIRECTORIO": [1001, 1002],
            "SECUENCIA_P": [1, 1],
            "P5018": [45000, 78000],
            "P5010": [2, 3],
            "P8536": [1, 1],
            "P8540": [1, 1],
            "P3163": [1, 1],
        })
        summary, max_f, _ = run_suite(df, "ecv_servicios_raw_suite", "t1")
        self.assertIsNone(max_f)

    def test_ecv_vivienda_invalid_departamento_triggers_critical_dq08(self):
        """Código de departamento inválido viola DQ08 (Critical)."""
        df = pd.DataFrame({
            "DIRECTORIO": [1001],
            "SECUENCIA_P": [1],
            "P1_DEPARTAMENTO": [999],  # Código DIVIPOLA inexistente
            "P1_MUNICIPIO": [1],
        })
        summary, max_f, _ = run_suite(df, "ecv_vivienda_raw_suite", "t2")
        self.assertEqual(max_f, FailureSeverity.CRITICAL)
        self.assertIn("DQ08", failed_rules(summary, "critical"))

    def test_ecv_servicios_stratum_warning_dq05(self):
        """Estrato no residencial (ej: 7) viola DQ05 como Warning sin bloquear."""
        df = pd.DataFrame({
            "DIRECTORIO": list(range(100)),
            "SECUENCIA_P": [1] * 100,
            "P5018": [50000] * 100,
            "P5010": [1] * 80 + [7] * 20,
            "P8536": [1] * 100,
            "P8540": [1] * 100,
            "P3163": [1] * 100,
        })
        summary, max_f, _ = run_suite(df, "ecv_servicios_raw_suite", "t3")
        self.assertEqual(max_f, FailureSeverity.WARNING)
        self.assertIn("DQ05", failed_rules(summary, "warning"))


class TestCompuerta2API(unittest.TestCase):
    """Pruebas de calidad de datos para la Compuerta 2 (Raw API IDEAM)."""

    def test_api_success(self):
        df = pd.DataFrame([{
            "codigoestacion": f"est_{i}",
            "nombreestacion": f"Estacion {i}",
            "departamento": f"DEP_{i}",
            "municipio": "MUN",
            "latitud": 4.5,
            "longitud": -74.0,
            "suma": 300.0,
            "n": 12,
            "minimo": 14.0,
            "maximo": 26.0,
            "window_start": "2025-06-01T00:00:00",
            "window_end": "2025-06-15T00:00:00",
        } for i in range(32)])   # 32 departamentos = cobertura real medida en 2025 (umbral DQ17 = 30)
        summary, max_f, _ = run_suite(df, "api_ideam_raw_suite", "t_api_ok")
        self.assertIsNone(max_f)

    def test_api_temperature_outlier_triggers_critical_dq15(self):
        """Temperaturas imposibles por falla de sensor violan DQ15 (Critical)."""
        df = pd.DataFrame([{
            "codigoestacion": f"est_{i}",
            "nombreestacion": f"Estacion {i}",
            "departamento": f"DEP_{i}",
            "municipio": "MUN",
            "latitud": 4.5,
            "longitud": -74.0,
            "suma": 300.0,
            "n": 12,
            "minimo": -99.0,  # Sensor defectuoso
            "maximo": 85.0,
            "window_start": "2025-06-01T00:00:00",
            "window_end": "2025-06-15T00:00:00",
        } for i in range(10)])
        summary, max_f, _ = run_suite(df, "api_ideam_raw_suite", "t_api_bad")
        self.assertEqual(max_f, FailureSeverity.CRITICAL)
        self.assertIn("DQ15", failed_rules(summary, "critical"))


class TestCompuerta3Prepared(unittest.TestCase):
    """Pruebas de calidad de datos para la Compuerta 3 (Datos Preparados)."""

    def test_fact_huella_negative_emissions_triggers_critical_dq22(self):
        """Emisiones negativas violan DQ22 (Critical)."""
        df = pd.DataFrame({
            "sk_fact": [1],
            "fk_hogar": [101],
            "fk_ubicacion": [201],
            "fk_clima": [301],
            "fk_combustible_cocina": [1],
            "fk_tarifa_energia": [1],
            "clima_emparejado": [1.0],
            "kwh_consumidos_estimados": [-50.0],  # Imposible
            "emisiones_energia_kg": [-10.0],
            "emisiones_coccion_kg": [0.0],
            "huella_total_anual_kg": [-10.0],
        })
        summary, max_f, _ = run_suite(df, "prepared_fact_huella_suite", "t_fact_bad")
        self.assertEqual(max_f, FailureSeverity.CRITICAL)
        self.assertIn("DQ22", failed_rules(summary, "critical"))

    def test_fact_huella_inconsistent_total_triggers_critical_dq23(self):
        """Huella total menor que una de sus componentes viola DQ23 (Critical)."""
        df = pd.DataFrame({
            "sk_fact": [1],
            "fk_hogar": [101],
            "fk_ubicacion": [201],
            "fk_clima": [301],
            "fk_combustible_cocina": [1],
            "fk_tarifa_energia": [1],
            "clima_emparejado": [1.0],
            "kwh_consumidos_estimados": [100.0],
            "emisiones_energia_kg": [50.0],
            "emisiones_coccion_kg": [30.0],
            "huella_total_anual_kg": [20.0],  # Menor que 50 (inconsistente)
        })
        summary, max_f, _ = run_suite(df, "prepared_fact_huella_suite", "t_fact_inconsistent")
        self.assertEqual(max_f, FailureSeverity.CRITICAL)
        self.assertIn("DQ23", failed_rules(summary, "critical"))


class TestGatePolicy(unittest.TestCase):
    """Pruebas de la política de compuertas (Critical bloquea, Warning continúa)."""

    def test_critical_raises_value_error(self):
        summary = [{"rule_id": "DQ08", "severity": "critical", "success": False}]
        with self.assertRaises(ValueError) as ctx:
            enforce_policy(summary, FailureSeverity.CRITICAL, "test_gate")
        self.assertIn("CRITICAL", str(ctx.exception))
        self.assertIn("DQ08", str(ctx.exception))

    def test_warning_allows_continuation(self):
        summary = [{"rule_id": "DQ05", "severity": "warning", "success": False}]
        decision = enforce_policy(summary, FailureSeverity.WARNING, "test_gate")
        self.assertEqual(decision["warnings"], ["DQ05"])
        self.assertEqual(decision["max_failure_severity"], "warning")


if __name__ == "__main__":
    unittest.main()
