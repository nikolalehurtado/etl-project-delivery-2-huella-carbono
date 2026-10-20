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


# ---------------------------------------------------------------------------
# Suites de datos PREPARADOS (compuerta 3 — Sección 14 del enunciado)
# Persona 2: reglas DQ19-DQ30; Persona 3: contrato de integración y grano.
# ---------------------------------------------------------------------------

def _prepared_fact_huella():
    """Suite de la tabla de hechos preparada: fact_huella_carbono."""
    return [
        # DQ19 — Grano único: un hogar por fila en la tabla de hechos
        # Justificación: la clave sk_fact es surrogate; la unicidad real es por fk_hogar.
        # Si hay duplicados, los KPIs de suma (emisiones totales) estarán inflados.
        ("DQ19", "critical", E.ExpectColumnValuesToBeUnique(column="sk_fact")),
        ("DQ19", "critical", E.ExpectColumnValuesToBeUnique(column="fk_hogar")),

        # DQ20 — Llaves foráneas no nulas: sin ellas la fila no puede cargarse al DW
        # Umbral 100%: una FK nula rompe la integridad referencial del modelo estrella.
        ("DQ20", "critical", E.ExpectColumnValuesToNotBeNull(column="fk_hogar")),
        ("DQ20", "critical", E.ExpectColumnValuesToNotBeNull(column="fk_ubicacion")),

        # DQ21 — Emparejamiento ECV–API: se acepta que algunos hogares no tengan clima
        # (departamentos sin estaciones IDEAM). Mínimo 50% emparejados para que R6/R7
        # tengan n suficiente. Umbral 50% conservador: Colombia tiene 33 depts pero
        # los más poblados (Antioquia, Bogotá, Valle) muy probablemente tienen estaciones.
        ("DQ21", "warning", E.ExpectColumnMeanToBeBetween(
            column="clima_emparejado", min_value=0.5, max_value=1.0)),

        # DQ22 — Emisiones eléctricas ≥ 0: el modelo de huella no produce negativos
        # Umbral 100%: un valor negativo indica error en el cálculo de kWh (tarifa > pago).
        ("DQ22", "critical", E.ExpectColumnValuesToBeBetween(
            column="kwh_consumidos_estimados", min_value=0)),
        ("DQ22", "critical", E.ExpectColumnValuesToBeBetween(
            column="emisiones_energia_kg", min_value=0)),
        ("DQ22", "critical", E.ExpectColumnValuesToBeBetween(
            column="emisiones_coccion_kg", min_value=0)),
        ("DQ22", "critical", E.ExpectColumnValuesToBeBetween(
            column="huella_total_anual_kg", min_value=0)),

        # DQ23 — La huella total es la suma de las componentes (consistencia interna)
        # Se valida que ninguna fila tenga huella_total < emisiones_energia (imposible).
        # mostly=1.0: tolerancia 0 → cualquier fila violadora es un error de cálculo.
        ("DQ23", "critical", E.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="huella_total_anual_kg", column_B="emisiones_energia_kg", or_equal=True)),
        ("DQ23", "critical", E.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="huella_total_anual_kg", column_B="emisiones_coccion_kg", or_equal=True)),

        # DQ24 — Conteo de filas: debe haber al menos 1 hogar
        ("DQ24", "critical", E.ExpectTableRowCountToBeBetween(min_value=1)),

        # DQ25 — Columnas requeridas para la carga al DW
        ("DQ25", "critical", E.ExpectTableColumnsToMatchSet(
            column_set=["sk_fact", "fk_hogar", "fk_ubicacion", "fk_clima",
                        "fk_combustible_cocina", "fk_tarifa_energia", "clima_emparejado",
                        "kwh_consumidos_estimados", "emisiones_energia_kg",
                        "emisiones_coccion_kg", "huella_total_anual_kg"],
            exact_match=False)),
    ]


def _prepared_dim_hogar():
    """Suite de dim_hogar preparada."""
    return [
        ("DQ26", "critical", E.ExpectTableColumnsToMatchSet(
            column_set=["sk_hogar", "directorio", "secuencia_p",
                        "num_personas", "tiene_vehiculo", "bien_p1077s11", "bien_p1077s12"],
            exact_match=False)),
        ("DQ26", "critical", E.ExpectColumnValuesToBeUnique(column="sk_hogar")),
        ("DQ26", "critical", E.ExpectColumnValuesToNotBeNull(column="sk_hogar")),
        # num_personas ≥ 1: todo hogar tiene al menos 1 persona
        ("DQ26", "critical", E.ExpectColumnValuesToBeBetween(
            column="num_personas", min_value=1)),
        # Dominio de variables binarias de tenencia
        ("DQ26", "warning", E.ExpectColumnValuesToBeInSet(
            column="tiene_vehiculo", value_set=["Sí", "No"])),
        ("DQ26", "warning", E.ExpectColumnValuesToBeInSet(
            column="bien_p1077s11", value_set=["Sí", "No"])),
        ("DQ26", "warning", E.ExpectColumnValuesToBeInSet(
            column="bien_p1077s12", value_set=["Sí", "No"])),
    ]


def _prepared_dim_ubicacion():
    """Suite de dim_ubicacion preparada."""
    return [
        ("DQ27", "critical", E.ExpectTableColumnsToMatchSet(
            column_set=["sk_ubicacion", "codigo_departamento", "nombre_departamento", "estrato"],
            exact_match=False)),
        ("DQ27", "critical", E.ExpectColumnValuesToBeUnique(column="sk_ubicacion")),
        # Estrato preparado: sólo 0 (reclasificado) y 1–6
        ("DQ27", "warning", E.ExpectColumnValuesToBeBetween(
            column="estrato", min_value=0, max_value=6)),
        # Código departamento: 0 si desconocido, o un código DANE válido
        # mostly=0.99: hasta 1% con código 0 (municipio sin departamento) es aceptable
        ("DQ27", "warning", E.ExpectColumnValuesToNotBeNull(
            column="codigo_departamento")),
    ]


def _prepared_dim_clima():
    """Suite de dim_clima preparada (temperatura departamental integrada de la API)."""
    return [
        ("DQ28", "critical", E.ExpectTableColumnsToMatchSet(
            column_set=["sk_clima", "codigo_departamento", "nombre_departamento",
                        "anio", "temp_media_c", "temp_min_c", "temp_max_c",
                        "n_estaciones", "n_lecturas", "piso_termico"],
            exact_match=False)),
        ("DQ28", "critical", E.ExpectColumnValuesToBeUnique(column="sk_clima")),
        ("DQ28", "critical", E.ExpectColumnValuesToBeUnique(column="codigo_departamento")),
        # Al menos 1 departamento con temperatura (si 0, R6/R7 son imposibles)
        ("DQ28", "critical", E.ExpectTableRowCountToBeBetween(min_value=1)),
        # Temperatura dentro del rango físico (post-limpieza: sin outliers de sensor)
        ("DQ28", "critical", E.ExpectColumnValuesToBeBetween(
            column="temp_media_c", min_value=-15, max_value=50)),
        # temp_min ≤ temp_media ≤ temp_max (consistencia interna)
        ("DQ28", "critical", E.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="temp_media_c", column_B="temp_min_c", or_equal=True)),
        ("DQ28", "critical", E.ExpectColumnPairValuesAToBeGreaterThanB(
            column_A="temp_max_c", column_B="temp_media_c", or_equal=True)),
        # Piso térmico: dominio {Cálido, Templado, Frío, Sin dato}
        ("DQ28", "warning", E.ExpectColumnValuesToBeInSet(
            column="piso_termico", value_set=["Cálido", "Templado", "Frío", "Sin dato"])),
        # Al menos 20 departamentos con clima (calibrado con DQ17)
        ("DQ28", "warning", E.ExpectTableRowCountToBeBetween(min_value=20)),
    ]


def _prepared_dim_tarifas():
    """Suite de dim_tarifas preparada."""
    return [
        ("DQ29", "critical", E.ExpectTableColumnsToMatchSet(
            column_set=["sk_tarifa", "estrato_aplica", "costo_promedio_kwh"],
            exact_match=False)),
        ("DQ29", "critical", E.ExpectColumnValuesToBeUnique(column="sk_tarifa")),
        # Estratos presentes: 1 a 6
        ("DQ29", "critical", E.ExpectColumnValuesToBeBetween(
            column="estrato_aplica", min_value=1, max_value=6)),
        # Costo > 0: la tarifa no puede ser gratuita
        ("DQ29", "critical", E.ExpectColumnValuesToBeBetween(
            column="costo_promedio_kwh", min_value=0.001)),
    ]


def _prepared_dim_combustibles():
    """Suite de dim_combustibles preparada."""
    return [
        ("DQ30", "critical", E.ExpectTableColumnsToMatchSet(
            column_set=["sk_combustible", "tipo_combustible", "factor_emision_kg_tj"],
            exact_match=False)),
        ("DQ30", "critical", E.ExpectColumnValuesToBeUnique(column="sk_combustible")),
        # Factor de emisión > 0 (combustibles siempre emiten CO2)
        ("DQ30", "critical", E.ExpectColumnValuesToBeBetween(
            column="factor_emision_kg_tj", min_value=0.001)),
    ]


SUITES = {
    # Compuerta 1 — Raw ECV
    "ecv_servicios_raw_suite": _ecv_servicios_raw,
    "ecv_vivienda_raw_suite": _ecv_vivienda_raw,
    "ecv_caracteristicas_raw_suite": _ecv_caracteristicas_raw,
    "ecv_condiciones_raw_suite": _ecv_condiciones_raw,
    # Compuerta 2 — Raw API
    "api_ideam_raw_suite": _api_ideam_raw,
    # Compuerta 3 — Datos preparados (Personas 2 y 3)
    "prepared_fact_huella_suite": _prepared_fact_huella,
    "prepared_dim_hogar_suite": _prepared_dim_hogar,
    "prepared_dim_ubicacion_suite": _prepared_dim_ubicacion,
    "prepared_dim_clima_suite": _prepared_dim_clima,
    "prepared_dim_tarifas_suite": _prepared_dim_tarifas,
    "prepared_dim_combustibles_suite": _prepared_dim_combustibles,
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


def run_api_raw_gate(meta, run_id):
    """Compuerta 2: valida el lote raw de la API IDEAM.

    Si hay un Critical, bloquea la transformacion (la integracion ECV-API no puede realizarse).
    """
    from src.extract import read_raw

    df = read_raw(meta["path"])
    suite = "api_ideam_raw_suite"
    summary, max_failure, result_file = run_suite(df, suite, run_id)
    if max_failure == FailureSeverity.CRITICAL:
        raise ValueError(
            f"[validate_api_raw] CRITICAL en {suite}: {failed_rules(summary, 'critical')}. "
            "La transformacion queda bloqueada."
        )
    return {**enforce_policy(summary, max_failure, gate=suite),
            "result_file": result_file, "rows": len(df)}


def run_prepared_gate(prepared_meta, run_id):
    """Compuerta 3: valida las 6 tablas preparadas antes de la carga al DW.

    Tablas validadas:
        fact_huella_carbono -> prepared_fact_huella_suite  (DQ19-DQ25)
        dim_hogar           -> prepared_dim_hogar_suite    (DQ26)
        dim_ubicacion       -> prepared_dim_ubicacion_suite(DQ27)
        dim_clima           -> prepared_dim_clima_suite    (DQ28)
        dim_tarifas         -> prepared_dim_tarifas_suite  (DQ29)
        dim_combustibles    -> prepared_dim_combustibles_suite (DQ30)

    Si CUALQUIERA tiene un Critical, bloquea la carga entera para mantener coherencia.
    Los Warnings se registran y se permite continuar segun la politica documentada.
    """
    from src.extract import read_raw

    TABLE_SUITE_MAP = {
        "fact_huella_carbono": "prepared_fact_huella_suite",
        "dim_hogar":           "prepared_dim_hogar_suite",
        "dim_ubicacion":       "prepared_dim_ubicacion_suite",
        "dim_clima":           "prepared_dim_clima_suite",
        "dim_tarifas":         "prepared_dim_tarifas_suite",
        "dim_combustibles":    "prepared_dim_combustibles_suite",
    }

    decisions, critical = {}, {}
    tables_meta = prepared_meta.get("tables", prepared_meta)
    for table_name, suite_name in TABLE_SUITE_MAP.items():
        path = tables_meta.get(table_name)
        if path is None:
            log.warning("[validate_prepared] Tabla '%s' no en prepared_meta; se omite.", table_name)
            continue
        df = read_raw(path)
        summary, max_failure, result_file = run_suite(df, suite_name, run_id)
        if max_failure == FailureSeverity.CRITICAL:
            critical[suite_name] = failed_rules(summary, "critical")
        else:
            decisions[suite_name] = {
                **enforce_policy(summary, max_failure, gate=suite_name),
                "result_file": result_file,
                "rows": len(df),
            }
    if critical:
        raise ValueError(
            f"[validate_prepared] CRITICAL: {critical}. "
            "La carga al Data Warehouse queda bloqueada."
        )
    log.info("[validate_prepared] Compuerta 3 superada. Tablas: %s", list(decisions.keys()))
    return decisions
