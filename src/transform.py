"""
TRANSFORM + INTEGRACION — ECV 2025 (DANE) + temperatura IDEAM.

Parte 1 (ECV): se conserva la logica de la fase 1 (limpieza, kWh por tarifa, emisiones).
Parte 2 (API): temperatura media por departamento = sum(suma) / sum(n) sobre las ventanas.
Parte 3 (integracion): se une por DEPARTAMENTO (codigo DANE) y se agrega dim_clima.

CONTRATO DE INTEGRACION (para el README, seccion 12)
  Llave ECV ........ P1_DEPARTAMENTO (codigo DANE numerico), de "Datos de la vivienda".
  Llave API ........ departamento (texto del IDEAM) normalizado a minusculas, sin tildes ni
                     puntuacion y traducido al codigo DANE con data/reference/dane_departamentos.csv
                     (mas alias de nombres: Bogota, San Andres).
  Cardinalidad ..... muchos hogares : 1 fila de clima por departamento.
  Alineacion ....... ambas fuentes de 2025 (ventana en API_START_DATE .. API_END_DATE).
  No emparejados ... hogares de un departamento sin estaciones -> fk_clima NULL y
                     clima_emparejado = 0 (se conservan para R1-R5; R6/R7 los excluyen).
                     Departamentos del IDEAM sin codigo DANE -> se descartan y se cuentan.
  Duplicados ....... varias estaciones por departamento son esperadas: se agregan ponderando
                     por numero de lecturas. Filas de estacion con minimo/maximo fuera del
                     rango fisico plausible se excluyen del promedio y se cuentan.
  Supuestos ........ el promedio departamental resume el clima de las estaciones, no el de
                     cada hogar; los cortes de piso termico son una convencion (CONFIRMAR).

Entrada: metadatos de extraccion (rutas raw). Salida: rutas de CSV preparados + conteos.
"""

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from src import config
from src.extract import batch_dir, read_raw

log = logging.getLogger(__name__)

# --------------------------------------------------------------------------- constantes fase 1
FACTOR_ELECTRICO_DEFAULT = 0.097      # kg CO2e / kWh (XM)
PRECIO_GAS_NATURAL_M3 = 1_800         # COP / m3
PRECIO_GLP_KG = 3_200                 # COP / kg
NCV_GAS_NATURAL_MJ_M3 = 37.2
NCV_GLP_MJ_KG = 47.3
NCV_LENA_MJ_KG = 15.6
MJ_POR_TJ = 1_000_000
CONSUMO_LENA_KG_MES = 150
# P8536 -> id_combustible (diccionario DANE ECV 2025)
MAPA_P8536_A_COMBUSTIBLE = {2: 3, 4: 2, 6: 1, 7: 1}

# --------------------------------------------------------------------------- constantes fase 2
TEMP_MIN_PLAUSIBLE, TEMP_MAX_PLAUSIBLE = -15.0, 50.0
# Corte de piso termico (CONFIRMAR con el profesor / fuente): >24 calido, 18-24 templado, <18 frio
CORTE_CALIDO, CORTE_FRIO = 24.0, 18.0
ALIAS_DEPARTAMENTO = {                 # nombre normalizado del IDEAM -> nombre normalizado DANE
    "bogota": "bogota dc",
    "bogota d c": "bogota dc",
    "santafe de bogota": "bogota dc",
    "archipielago de san andres providencia y santa catalina": "san andres y providencia",
    "san andres providencia y santa catalina": "san andres y providencia",
    "san andres": "san andres y providencia",
    "guajira": "la guajira",
}


def normalize_name(text):
    """Minusculas, sin tildes ni puntuacion: 'Bogotá, D.C.' -> 'bogota d c' -> comparable."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _canonical(text):
    n = normalize_name(text)
    n = ALIAS_DEPARTAMENTO.get(n, n)
    return n.replace("bogota d c", "bogota dc")


def piso_termico(temp):
    if pd.isna(temp):
        return "Sin dato"
    if temp > CORTE_CALIDO:
        return "Cálido"
    if temp >= CORTE_FRIO:
        return "Templado"
    return "Frío"


# --------------------------------------------------------------------------- limpieza ECV (fase 1)
def _deduplicar(df):
    antes = len(df)
    df = df.drop_duplicates(subset=config.HOUSEHOLD_KEYS, keep="first")
    return df.reset_index(drop=True), antes - len(df)


def _imputar_pago_energia(df):
    nulos = int(df["P5018"].isna().sum())
    if nulos:
        df["P5018"] = df["P5018"].fillna(df.groupby("P5010")["P5018"].transform("median"))
        df["P5018"] = df["P5018"].fillna(df["P5018"].median())
    return df, nulos


def _tratar_outliers(df):
    p99 = df["P5018"].quantile(0.99)
    n = int((df["P5018"] > p99).sum())
    df["P5018"] = df["P5018"].clip(upper=p99)
    return df, n


def _tratar_ceros(df):
    mask = (df["P5018"] == 0) & (df["P5010"] != 1)   # estrato 1 con $0 es valido (subsidio)
    n = int(mask.sum())
    if n:
        med = df.groupby("P5010")["P5018"].transform("median")
        df.loc[mask, "P5018"] = med[mask]
    return df, n


def _reclasificar_estrato(df):
    mask = ~df["P5010"].between(1, 6)
    n = int(mask.sum())
    df.loc[mask, "P5010"] = 0                        # 0 = "No valido / No informa"
    return df, n


def _calcular_emisiones(df, tarifa_lookup, factor_electrico, factor_comb):
    tarifa = df["P5010"].map(tarifa_lookup).fillna(min(tarifa_lookup.values()))
    df["kwh_consumidos_estimados"] = (df["P5018"].astype(float) / tarifa).round(2).clip(lower=0)
    df["emisiones_energia_kg"] = (df["kwh_consumidos_estimados"] * 12 * factor_electrico).round(4)

    df["ID_COMBUSTIBLE"] = df["P8536"].map(MAPA_P8536_A_COMBUSTIBLE)
    gasto_gas = pd.to_numeric(df["P3163"], errors="coerce").fillna(0)
    gasto_otro = pd.to_numeric(df["P8540"], errors="coerce").fillna(0)
    mensual = pd.Series(0.0, index=df.index)

    m = df["ID_COMBUSTIBLE"] == 3                    # gas natural
    mensual[m] = (gasto_gas[m] / PRECIO_GAS_NATURAL_M3) * NCV_GAS_NATURAL_MJ_M3 / MJ_POR_TJ * factor_comb.get(3, 56100)
    m = df["ID_COMBUSTIBLE"] == 2                    # GLP
    mensual[m] = (gasto_otro[m] / PRECIO_GLP_KG) * NCV_GLP_MJ_KG / MJ_POR_TJ * factor_comb.get(2, 63100)
    m = df["ID_COMBUSTIBLE"] == 1                    # lena / carbon de lena
    mensual[m] = CONSUMO_LENA_KG_MES * NCV_LENA_MJ_KG / MJ_POR_TJ * factor_comb.get(1, 112000)

    df["emisiones_coccion_kg"] = (mensual * 12).round(4)
    df["huella_total_anual_kg"] = (df["emisiones_energia_kg"] + df["emisiones_coccion_kg"]).round(4)
    return df


# --------------------------------------------------------------------------- API -> clima
def build_dim_clima(api_df, dane):
    """Temperatura media 2025 por departamento (codigo DANE). Devuelve (dim_clima, informe)."""
    informe = {"filas_api": int(len(api_df))}
    df = api_df.copy()
    for col in ("suma", "n", "minimo", "maximo"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    validas = df["suma"].notna() & df["n"].gt(0)
    informe["filas_sin_suma_o_n"] = int((~validas).sum())
    df = df[validas]

    fuera = (df["minimo"] < TEMP_MIN_PLAUSIBLE) | (df["maximo"] > TEMP_MAX_PLAUSIBLE)
    informe["filas_estacion_fuera_de_rango_excluidas"] = int(fuera.sum())
    df = df[~fuera]

    mapa = {_canonical(n): c for c, n in zip(dane["codigo_dane"], dane["departamento"])}
    df["codigo_departamento"] = df["departamento"].map(lambda x: mapa.get(_canonical(x)) if pd.notna(x) else None)
    sin_codigo = df["codigo_departamento"].isna()
    informe["filas_sin_codigo_dane_descartadas"] = int(sin_codigo.sum())
    informe["nombres_ideam_sin_codigo_dane"] = sorted(df.loc[sin_codigo, "departamento"].dropna().astype(str).unique().tolist())
    df = df[~sin_codigo]

    g = df.groupby("codigo_departamento").agg(
        suma=("suma", "sum"), n_lecturas=("n", "sum"),
        temp_min_c=("minimo", "min"), temp_max_c=("maximo", "max"),
        n_estaciones=("codigoestacion", "nunique"),
    ).reset_index()
    g["temp_media_c"] = (g["suma"] / g["n_lecturas"]).round(2)
    g["codigo_departamento"] = g["codigo_departamento"].astype(int)
    g = g.merge(dane.rename(columns={"codigo_dane": "codigo_departamento", "departamento": "nombre_departamento"}),
                on="codigo_departamento", how="left")
    g["piso_termico"] = g["temp_media_c"].map(piso_termico)
    g["anio"] = int(config.API_START_DATE[:4])
    g = g.sort_values("codigo_departamento").reset_index(drop=True)
    g.insert(0, "sk_clima", range(1, len(g) + 1))
    informe["departamentos_con_clima"] = int(len(g))
    return g[["sk_clima", "codigo_departamento", "nombre_departamento", "anio", "temp_media_c",
              "temp_min_c", "temp_max_c", "n_estaciones", "n_lecturas", "piso_termico"]], informe


# --------------------------------------------------------------------------- principal
def transform_and_integrate(ecv_meta, api_meta):
    run_id = ecv_meta["batch_id"]
    out_dir = batch_dir(run_id).parent / "prepared"
    out_dir.mkdir(parents=True, exist_ok=True)
    log_t = {}                                   # bitacora de transformaciones (antes/despues)

    ecv = {k: read_raw(v["path"]) for k, v in ecv_meta["tables"].items()}
    api = read_raw(api_meta["path"])
    dane = pd.read_csv(config.REFERENCE_DIR / "dane_departamentos.csv", sep=";", encoding="utf-8")
    t_ref = pd.read_csv(config.REFERENCE_DIR / "dim_tarifas.csv", sep=";", encoding="utf-8-sig")
    c_ref = pd.read_csv(config.REFERENCE_DIR / "dim_combustibles.csv", sep=";", encoding="utf-8-sig")
    f_ref = pd.read_csv(config.REFERENCE_DIR / "dim_factor_electrico.csv", sep=";", encoding="utf-8-sig")

    # -------- ECV: limpieza (fase 1)
    s = ecv["servicios"].copy()
    s["P5018"] = pd.to_numeric(s["P5018"], errors="coerce")
    s["P5010"] = pd.to_numeric(s["P5010"], errors="coerce").fillna(1).astype(int)
    filas_in = len(s)
    s, log_t["duplicados_eliminados"] = _deduplicar(s)
    s, log_t["p5018_nulos_imputados"] = _imputar_pago_energia(s)
    s, log_t["p5018_outliers_truncados_p99"] = _tratar_outliers(s)
    s, log_t["p5018_ceros_imputados_estrato_distinto_1"] = _tratar_ceros(s)
    s, log_t["estratos_invalidos_reclasificados_a_0"] = _reclasificar_estrato(s)
    log_t["hogares_entrada"], log_t["hogares_salida"] = filas_in, len(s)

    # -------- dimensiones de referencia
    dim_tarifas = pd.DataFrame({
        "sk_tarifa": range(1, len(t_ref) + 1),
        "estrato_aplica": t_ref.iloc[:, 0].astype(str).str.extract(r"(\d+)")[0].astype(int),
        "costo_promedio_kwh": pd.to_numeric(t_ref.filter(like="Costo").iloc[:, 0], errors="coerce"),
    })
    dim_combustibles = c_ref[["id_combustible", "tipo_combustible", "factor_emision_co2"]].rename(
        columns={"id_combustible": "sk_combustible", "factor_emision_co2": "factor_emision_kg_tj"})
    factor_elec = float(f_ref.filter(like="factor_emision").iloc[0, 0]) if len(f_ref) else FACTOR_ELECTRICO_DEFAULT

    s = _calcular_emisiones(
        s, dict(zip(dim_tarifas["estrato_aplica"], dim_tarifas["costo_promedio_kwh"])),
        factor_elec, dict(zip(dim_combustibles["sk_combustible"], dim_combustibles["factor_emision_kg_tj"])))

    # -------- dim_hogar (integrantes, vehiculo, equipos P1077S11/S12 — significado por confirmar)
    hogar = s[config.HOUSEHOLD_KEYS].copy()
    personas = ecv["caracteristicas"].groupby(config.HOUSEHOLD_KEYS).size().reset_index(name="num_personas")
    cond = ecv["condiciones"].drop_duplicates(subset=config.HOUSEHOLD_KEYS)
    cond = cond.assign(**{
        "tiene_vehiculo": cond["P1077S15"].map({1: "Sí", 2: "No"}),
        "bien_p1077s11": cond["P1077S11"].map({1: "Sí", 2: "No"}),
        "bien_p1077s12": cond["P1077S12"].map({1: "Sí", 2: "No"}),
    })[[*config.HOUSEHOLD_KEYS, "tiene_vehiculo", "bien_p1077s11", "bien_p1077s12"]]
    dim_hogar = hogar.merge(personas, on=config.HOUSEHOLD_KEYS, how="left").merge(cond, on=config.HOUSEHOLD_KEYS, how="left")
    dim_hogar["num_personas"] = dim_hogar["num_personas"].fillna(1).astype(int)
    for c in ("tiene_vehiculo", "bien_p1077s11", "bien_p1077s12"):
        dim_hogar[c] = dim_hogar[c].fillna("No")
    dim_hogar.insert(0, "sk_hogar", range(1, len(dim_hogar) + 1))
    dim_hogar = dim_hogar.rename(columns={"DIRECTORIO": "directorio", "SECUENCIA_P": "secuencia_p"})

    # -------- departamento por hogar (llave de integracion)
    viv = ecv["vivienda"].drop_duplicates(subset=config.HOUSEHOLD_KEYS)[[*config.HOUSEHOLD_KEYS, "P1_DEPARTAMENTO"]]
    s = s.merge(viv, on=config.HOUSEHOLD_KEYS, how="left")
    s["codigo_departamento"] = pd.to_numeric(s["P1_DEPARTAMENTO"], errors="coerce").fillna(0).astype(int)

    # -------- dim_ubicacion (departamento, estrato)
    dim_ubi = s[["codigo_departamento", "P5010"]].drop_duplicates().sort_values(["codigo_departamento", "P5010"]).reset_index(drop=True)
    dim_ubi.insert(0, "sk_ubicacion", range(1, len(dim_ubi) + 1))
    nombres = dict(zip(dane["codigo_dane"], dane["departamento"]))
    dim_ubi["nombre_departamento"] = dim_ubi["codigo_departamento"].map(nombres).fillna("Desconocido")
    dim_ubi = dim_ubi.rename(columns={"P5010": "estrato"})[["sk_ubicacion", "codigo_departamento", "nombre_departamento", "estrato"]]

    # -------- INTEGRACION: dim_clima (API) y llaves de la tabla de hechos
    dim_clima, informe_api = build_dim_clima(api, dane)

    s = s.merge(dim_hogar[["directorio", "secuencia_p", "sk_hogar"]],
                left_on=config.HOUSEHOLD_KEYS, right_on=["directorio", "secuencia_p"], how="left")
    s = s.merge(dim_ubi.rename(columns={"estrato": "P5010"})[["sk_ubicacion", "codigo_departamento", "P5010"]],
                on=["codigo_departamento", "P5010"], how="left")
    s = s.merge(dim_clima[["sk_clima", "codigo_departamento"]], on="codigo_departamento", how="left")
    s["clima_emparejado"] = s["sk_clima"].notna().astype(int)
    s = s.merge(dim_tarifas[["sk_tarifa", "estrato_aplica"]], left_on="P5010", right_on="estrato_aplica", how="left")

    fact = pd.DataFrame({
        "fk_hogar": s["sk_hogar"], "fk_ubicacion": s["sk_ubicacion"], "fk_clima": s["sk_clima"],
        "fk_combustible_cocina": s["ID_COMBUSTIBLE"], "fk_tarifa_energia": s["sk_tarifa"],
        "clima_emparejado": s["clima_emparejado"],
        "kwh_consumidos_estimados": s["kwh_consumidos_estimados"],
        "emisiones_energia_kg": s["emisiones_energia_kg"],
        "emisiones_coccion_kg": s["emisiones_coccion_kg"],
        "huella_total_anual_kg": s["huella_total_anual_kg"],
    })
    for c in ("fk_hogar", "fk_ubicacion", "fk_clima", "fk_combustible_cocina", "fk_tarifa_energia"):
        fact[c] = pd.to_numeric(fact[c], errors="coerce").astype("Int64")
    fact.insert(0, "sk_fact", range(1, len(fact) + 1))

    # -------- no emparejados
    sin_clima = fact["clima_emparejado"].eq(0)
    deps_hogares = set(s["codigo_departamento"].unique())
    contrato = {
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "llave": "codigo_departamento (DANE)",
        "cardinalidad": "muchos hogares : 1 clima por departamento",
        "hogares_total": int(len(fact)),
        "hogares_con_clima": int((~sin_clima).sum()),
        "hogares_sin_clima": int(sin_clima.sum()),
        "pct_hogares_con_clima": round(float((~sin_clima).mean() * 100), 2),
        "departamentos_en_ecv": sorted(int(d) for d in deps_hogares),
        "departamentos_ecv_sin_clima": sorted(int(d) for d in deps_hogares - set(dim_clima["codigo_departamento"])),
        "departamentos_con_clima": int(len(dim_clima)),
        "api": informe_api,
        "transformaciones_ecv": log_t,
    }

    tables = {"dim_hogar": dim_hogar, "dim_ubicacion": dim_ubi, "dim_clima": dim_clima,
              "dim_combustibles": dim_combustibles, "dim_tarifas": dim_tarifas, "fact_huella_carbono": fact}
    paths, counts = {}, {}
    for name, df in tables.items():
        p = out_dir / f"{name}.csv"
        df.to_csv(p, index=False)
        paths[name], counts[name] = str(p), int(len(df))
    (out_dir / "integration_report.json").write_text(json.dumps(contrato, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Preparado: %s | sin clima: %s hogares", counts, contrato["hogares_sin_clima"])
    return {"tables": paths, "counts": counts, "report": str(out_dir / "integration_report.json")}
