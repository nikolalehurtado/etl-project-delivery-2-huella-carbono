"""
VALIDATION — compuertas de calidad con Great Expectations (GX Core 1.23.1).

Cada Expectation lleva en `meta` el ID de la regla de calidad que implementa
(DQxx, ver docs/quality_rules.md) y una severidad:
    critical -> bloquea el camino posterior
    warning  -> se registra y el pipeline continua segun la politica documentada
    info     -> contexto de monitoreo; nunca bloquea

IMPORTANTE — BORRADOR: las reglas y umbrales de abajo son un PUNTO DE PARTIDA.
Cada umbral debe justificarse con el perfilamiento (notebooks/) y con una base
analitica, contractual o historica; un umbral elegido solo porque los datos actuales
lo cumplen no es aceptable (enunciado, seccion 8.1). Marcados con `PROVISIONAL`.

Tres compuertas del enunciado (seccion 9):
    1. Primary Source Raw Validation  -> run_ecv_raw_gate()    (4 tablas de la ECV)
    2. API Raw Validation             -> suite api_ideam_raw_suite
    3. Prepared Data Validation       -> suites PREPARED_*  (por definir: Personas 2 y 3)

Las suites se definen en codigo (versionadas en Git) y en cada ejecucion se exportan
a gx/expectations/. Los resultados se conservan en gx/validation_results/<run_id>/<suite>.json.
"""

import json
import logging
import os
import re
from datetime import datetime, timezone

os.environ.setdefault("GX_ANALYTICS_ENABLED", "False")  # sin telemetria

import great_expectations as gx                           # noqa: E402
import pandas as pd                                       # noqa: E402
from great_expectations.data_context.types.base import ProgressBarsConfig  # noqa: E402
from great_expectations.expectations.metadata_types import FailureSeverity  # noqa: E402

from src import config                                    # noqa: E402

log = logging.getLogger(__name__)
E = gx.expectations


def _dane_codes():
    """Codigos DIVIPOLA de los 33 departamentos (data/reference/dane_departamentos.csv)."""
    ref = pd.read_csv(config.REFERENCE_DIR / "dane_departamentos.csv", sep=";")
    return [int(c) for c in ref["codigo_dane"]]


# ---------------------------------------------------------------------------
# Definicion de suites: lista de (rule_id, severidad, Expectation)
# ---------------------------------------------------------------------------
def _ecv_servicios_raw():
    spec = config.ECV_TABLES["servicios"]["columns"]
    return [
        ("DQ01", "critical", E.ExpectTableColumnsToMatchSet(column_set=spec, exact_match=False)),
        # Identidad del hogar: sin ella no hay grano ni cruce posible
        ("DQ02", "critical", E.ExpectColumnValuesToNotBeNull(column="DIRECTORIO")),
        ("DQ02", "critical", E.ExpectColumnValuesToNotBeNull(column="SECUENCIA_P")),
        # PROVISIONAL: la fase 1 elimino 212 duplicados (0,24%); mas de 1% sugiere un problema de carga
        ("DQ03", "warning", E.ExpectCompoundColumnsToBeUnique(
            column_list=config.HOUSEHOLD_KEYS, mostly=0.99)),
        # PROVISIONAL: la fase 1 imputo P5018 (77% observado). Con menos de 70% observado la
        # huella electrica dependeria mas de la imputacion que del dato real
        ("DQ04", "warning", E.ExpectColumnValuesToNotBeNull(column="P5018", mostly=0.70)),
        # Estrato valido 1-6; la fase 1 reclasifico los codigos 7 y 8 a 0 (12 hogares)
        ("DQ05", "warning", E.ExpectColumnValuesToBeBetween(
            column="P5010", min_value=1, max_value=6, mostly=0.999)),
    ]


def _ecv_vivienda_raw():
    spec = config.ECV_TABLES["vivienda"]["columns"]
    return [
        ("DQ06", "critical", E.ExpectTableColumnsToMatchSet(column_set=spec, exact_match=False)),
        ("DQ07", "critical", E.ExpectColumnValuesToNotBeNull(column="P1_DEPARTAMENTO")),
        # P1_DEPARTAMENTO es la LLAVE DE INTEGRACION con la API: debe ser un codigo DIVIPOLA valido
        ("DQ08", "critical", E.ExpectColumnValuesToBeInSet(
            column="P1_DEPARTAMENTO", value_set=_dane_codes())),
    ]


def _ecv_caracteristicas_raw():
    spec = config.ECV_TABLES["caracteristicas"]["columns"]
    return [
        ("DQ09", "critical", E.ExpectTableColumnsToMatchSet(column_set=spec, exact_match=False)),
        ("DQ09", "critical", E.ExpectColumnValuesToNotBeNull(column="DIRECTORIO")),
        ("DQ09", "critical", E.ExpectColumnValuesToNotBeNull(column="SECUENCIA_P")),
    ]


def _ecv_condiciones_raw():
    spec = config.ECV_TABLES["condiciones"]["columns"]
    return [
        ("DQ10", "critical", E.ExpectTableColumnsToMatchSet(column_set=spec, exact_match=False)),
        # P1077S15 (carro particular) alimenta R3: dominio 1 = si, 2 = no
        ("DQ10", "critical", E.ExpectColumnValuesToBeInSet(column="P1077S15", value_set=[1, 2])),
        # P1077S11 y P1077S12 alimentan R7; el significado exacto debe confirmarse en el diccionario DANE
        ("DQ11", "warning", E.ExpectColumnValuesToBeInSet(column="P1077S11", value_set=[1, 2])),
        ("DQ11", "warning", E.ExpectColumnValuesToBeInSet(column="P1077S12", value_set=[1, 2])),
    ]


def _api_ideam_raw():
    return [
        ("DQ12", "critical", E.ExpectTableColumnsToMatchSet(
            column_set=config.API_RAW_COLUMNS, exact_match=False)),
        # Una extraccion sin ninguna fila no puede alimentar R6 ni R7
        ("DQ13", "critical", E.ExpectTableRowCountToBeBetween(min_value=1)),
        # departamento es la LLAVE DE INTEGRACION con la ECV
        ("DQ14", "critical", E.ExpectColumnValuesToNotBeNull(column="departamento", mostly=0.99)),
        # PROVISIONAL: rango fisico plausible del aire a 2 m en Colombia. La ficha del dataset avisa
        # que el IDEAM no valido los valores (fallas de sensor). Se evalua el minimo y el maximo de
        # cada estacion y ventana, asi un solo dato imposible queda registrado.
        ("DQ15", "critical", E.ExpectColumnValuesToBeBetween(
            column="minimo", min_value=-15, max_value=50, mostly=0.995)),
        ("DQ15", "critical", E.ExpectColumnValuesToBeBetween(
            column="maximo", min_value=-15, max_value=50, mostly=0.995)),
        # Compatibilidad temporal con la ECV 2025
        ("DQ16", "critical", E.ExpectColumnValuesToMatchRegex(column="window_start", regex=r"^2025-")),
        # PROVISIONAL: minimo de departamentos con datos; calibrar con el perfilamiento de cobertura
        ("DQ17", "warning", E.ExpectColumnUniqueValueCountToBeBetween(
            column="departamento", min_value=config.API_MIN_DEPARTMENTS)),
        # Coordenadas dentro de Colombia (incluye San Andres y Providencia, hasta -81,7 de longitud)
        ("DQ18", "warning", E.ExpectColumnValuesToBeBetween(
            column="latitud", min_value=-5, max_value=14, mostly=0.99)),
        ("DQ18", "warning", E.ExpectColumnValuesToBeBetween(
            column="longitud", min_value=-82, max_value=-66, mostly=0.99)),
    ]


# TODO (Personas 2 y 3): suites de la compuerta de datos PREPARADOS (seccion 14 del enunciado):
# esquema y campos obligatorios, dominios y rangos, indicadores de emparejamiento (departamentos
# de la ECV sin temperatura), unicidad en el grano (un hogar por fila), llaves listas para la carga.
SUITES = {
    "ecv_servicios_raw_suite": _ecv_servicios_raw,
    "ecv_vivienda_raw_suite": _ecv_vivienda_raw,
    "ecv_caracteristicas_raw_suite": _ecv_caracteristicas_raw,
    "ecv_condiciones_raw_suite": _ecv_condiciones_raw,
    "api_ideam_raw_suite": _api_ideam_raw,
}


# ---------------------------------------------------------------------------
# Ejecucion controlada
# ---------------------------------------------------------------------------
def _safe(run_id):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(run_id))


def _summarize(result):
    """Resumen por regla: lo que se imprime en el log de Airflow."""
    rows = []
    for r in result.results:
        cfg = r.expectation_config
        res = r.result or {}
        rows.append({
            "rule_id": (cfg.meta or {}).get("rule_id"),
            "severity": str(cfg.severity.value if hasattr(cfg.severity, "value") else cfg.severity),
            "expectation": cfg.type,
            "column": cfg.kwargs.get("column") or cfg.kwargs.get("column_list"),
            "success": bool(r.success),
            "unexpected_count": res.get("unexpected_count"),
            "unexpected_percent": (round(res["unexpected_percent"], 4)
                                   if res.get("unexpected_percent") is not None else None),
            "observed_value": (res.get("observed_value")
                               if not isinstance(res.get("observed_value"), list) else None),
            "exception": bool((r.exception_info or {}).get("raised_exception")),
        })
    return sorted(rows, key=lambda x: (x["rule_id"] or "", x["expectation"]))


def _without_ids(obj):
    """Quita los 'id' aleatorios que GX asigna, para que la suite exportada sea estable en Git."""
    if isinstance(obj, dict):
        return {k: _without_ids(v) for k, v in obj.items() if k != "id"}
    if isinstance(obj, list):
        return [_without_ids(v) for v in obj]
    return obj


def run_suite(df, suite_name, run_id):
    """Valida un DataFrame contra una suite y devuelve (resumen, severidad_maxima_fallida, archivo).

    severidad_maxima_fallida: FailureSeverity.CRITICAL, FailureSeverity.WARNING o None.
    """
    context = gx.get_context(mode="ephemeral")
    # Sin barras de progreso: los logs de Airflow quedan legibles
    context.variables.progress_bars = ProgressBarsConfig(globally=False, metric_calculations=False)
    source = context.data_sources.add_pandas(name=f"{suite_name}_source")
    asset = source.add_dataframe_asset(name=f"{suite_name}_asset")
    batch_definition = asset.add_batch_definition_whole_dataframe(f"{suite_name}_batch")

    suite = context.suites.add(gx.ExpectationSuite(name=suite_name))
    for rule_id, severity, expectation in SUITES[suite_name]():
        expectation.severity = severity
        expectation.meta = {"rule_id": rule_id}
        suite.add_expectation(expectation)

    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(name=f"{suite_name}_validation", data=batch_definition, suite=suite)
    )
    result = validation_definition.run(
        batch_parameters={"dataframe": df},
        result_format={"result_format": "SUMMARY"},
    )
    max_failure = result.get_max_severity_failure()

    # Evidencia persistente: suite exportada y resultado completo en JSON
    (config.GX_DIR / "expectations").mkdir(parents=True, exist_ok=True)
    (config.GX_DIR / "expectations" / f"{suite_name}.json").write_text(
        json.dumps(_without_ids(suite.to_json_dict()), indent=2, default=str), encoding="utf-8")

    summary = _summarize(result)
    out_dir = config.GX_DIR / "validation_results" / _safe(run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": str(run_id),
        "suite": suite_name,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "rows_validated": int(len(df)),
        "success": bool(result.success),
        "max_failure_severity": max_failure.value if max_failure else None,
        "statistics": result.statistics,
        "rules": summary,
        "gx_result": result.to_json_dict(),
    }
    out_file = out_dir / f"{suite_name}.json"
    out_file.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    log.info("GX suite=%s filas=%s success=%s severidad_maxima=%s",
             suite_name, len(df), result.success, max_failure)
    for row in summary:
        estado = "OK  " if row["success"] else "FAIL"
        log.info("  [%s] %s %-8s %-45s col=%s unexpected=%s%% observed=%s",
                 estado, row["rule_id"], row["severity"], row["expectation"], row["column"],
                 row["unexpected_percent"], row["observed_value"])
    log.info("Resultado guardado en %s", out_file)
    return summary, max_failure, str(out_file)


def failed_rules(summary, severity):
    return sorted({r["rule_id"] for r in summary if not r["success"] and r["severity"] == severity})


def enforce_policy(summary, max_failure, gate):
    """Politica de compuerta: Critical bloquea; Warning se registra y continua."""
    if max_failure == FailureSeverity.CRITICAL:
        raise ValueError(
            f"[{gate}] Validacion con severidad CRITICAL. Reglas violadas: "
            f"{failed_rules(summary, 'critical')}. El procesamiento posterior queda bloqueado."
        )
    if max_failure == FailureSeverity.WARNING:
        log.warning("[%s] Reglas WARNING violadas: %s. La politica documentada permite continuar.",
                    gate, failed_rules(summary, "warning"))
    if failed_rules(summary, "info"):
        log.info("[%s] Reglas INFO fuera de rango (solo monitoreo): %s",
                 gate, failed_rules(summary, "info"))
    log.info("[%s] Compuerta superada segun la politica.", gate)
    return {
        "gate": gate,
        "max_failure_severity": max_failure.value if max_failure else None,
        "warnings": failed_rules(summary, "warning"),
        "info": failed_rules(summary, "info"),
    }


def run_ecv_raw_gate(meta, run_id):
    """Compuerta 1: valida las 4 tablas de la ECV. Si CUALQUIERA tiene un Critical, bloquea."""
    from src.extract import read_raw

    decisions, critical = {}, {}
    for table, info in meta["tables"].items():
        suite = f"ecv_{table}_raw_suite"
        df = read_raw(info["path"])
        summary, max_failure, result_file = run_suite(df, suite, run_id)
        if max_failure == FailureSeverity.CRITICAL:
            critical[suite] = failed_rules(summary, "critical")
        else:
            decisions[suite] = {**enforce_policy(summary, max_failure, gate=suite),
                                "result_file": result_file, "rows": len(df)}
    if critical:
        raise ValueError(
            f"[validate_primary_raw] Validacion con severidad CRITICAL: {critical}. "
            "La transformacion queda bloqueada."
        )
    return decisions
