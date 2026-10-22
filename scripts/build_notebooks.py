"""
Genera los dos notebooks de perfilamiento (Persona 2 — David Aponte).
Ejecutar desde la raíz del proyecto:
    python scripts/build_notebooks.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB_DIR = ROOT / "notebooks"
NB_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────
#  UTILIDADES
# ─────────────────────────────────────────────────────────────────
def md(source):
    return {"cell_type": "markdown", "metadata": {}, "source": source if isinstance(source, list) else [source]}


def code(source):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source if isinstance(source, list) else [source]}


def nb(cells):
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.10.0"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


# ─────────────────────────────────────────────────────────────────
#  NOTEBOOK 01 — Perfilamiento ECV 2025 (DANE)
# ─────────────────────────────────────────────────────────────────
def make_nb01():
    cells = []

    # ── Encabezado ──────────────────────────────────────────────
    cells.append(md([
        "# Perfilamiento de la Fuente Primaria: ECV 2025 (DANE)\n",
        "**Proyecto:** ETL Segunda Entrega — Huella de Carbono en Hogares Colombianos (ODS 12)  \n",
        "**Responsable:** David Aponte (Persona 2 — API y Calidad de Datos)  \n",
        "**Autores:** Nikol Hurtado, David Aponte, Diana Panesso, Sebastián Celorio  \n",
        "\n",
        "## Objetivo\n",
        "Documentar el perfilamiento **sistemático y reproducible** de los 4 capítulos de la ECV 2025,\n",
        "vinculando cada hallazgo con la regla GX correspondiente (DQ01–DQ11) y su justificación de umbral.\n",
        "Los umbrales marcados **PROVISIONAL** en `docs/quality_rules.md` se concretan aquí con base empírica.\n",
        "> **Instrucciones de ejecución:** coloca los CSV de la ECV 2025 en `data/raw/ecv/` antes de correr las celdas.\n",
        "> Descarga: https://microdatos.dane.gov.co/index.php/catalog/905\n",
    ]))

    # ── 0. Setup ────────────────────────────────────────────────
    cells.append(md("## 0. Configuración del entorno"))
    cells.append(code([
        "import os, sys, warnings, re, unicodedata\n",
        "from pathlib import Path\n",
        "import numpy as np\n",
        "import pandas as pd\n",
        "\n",
        "warnings.filterwarnings('ignore')\n",
        "pd.set_option('display.float_format', '{:,.2f}'.format)\n",
        "pd.set_option('display.max_columns', 40)\n",
        "\n",
        "PROJECT_ROOT = Path('..').resolve()\n",
        "RAW_ECV  = PROJECT_ROOT / 'data' / 'raw' / 'ecv'\n",
        "REF_DIR  = PROJECT_ROOT / 'data' / 'reference'\n",
        "\n",
        "ECV_SEP = ';'\n",
        "ECV_ENC = 'latin-1'\n",
        "HH_KEYS = ['DIRECTORIO', 'SECUENCIA_P']\n",
        "\n",
        "ECV_TABLES = {\n",
        "    'servicios':       {'keywords': ['servicios'],               'columns': [*HH_KEYS, 'P5018', 'P5010', 'P8536', 'P8540', 'P3163']},\n",
        "    'vivienda':        {'keywords': ['vivienda'],                'columns': [*HH_KEYS, 'P1_DEPARTAMENTO', 'P1_MUNICIPIO']},\n",
        "    'caracteristicas': {'keywords': ['caracter'],                'columns': [*HH_KEYS, 'ORDEN']},\n",
        "    'condiciones':     {'keywords': ['condiciones', 'tenencia'], 'exclude': ['programa'],\n",
        "                        'columns': [*HH_KEYS, 'P1077S15', 'P1077S11', 'P1077S12']},\n",
        "}\n",
        "\n",
        "dane_ref     = pd.read_csv(REF_DIR / 'dane_departamentos.csv', sep=';')\n",
        "CODIGOS_DANE = set(dane_ref['codigo_dane'].astype(int))\n",
        "\n",
        "def _norm(text):\n",
        "    text = unicodedata.normalize('NFKD', str(text))\n",
        "    return ''.join(c for c in text if not unicodedata.combining(c)).lower()\n",
        "\n",
        "def find_ecv(spec, folder=RAW_ECV):\n",
        "    for p in sorted(folder.glob('*.csv')):\n",
        "        n = _norm(p.name)\n",
        "        if all(k in n for k in spec['keywords']) and not any(x in n for x in spec.get('exclude', [])):\n",
        "            return p\n",
        "    return None\n",
        "\n",
        "def load_chapter(table):\n",
        "    spec = ECV_TABLES[table]\n",
        "    path = find_ecv(spec)\n",
        "    if path is None:\n",
        "        print(f'[AVISO] CSV del capítulo {table!r} no encontrado en {RAW_ECV}.')\n",
        "        print('        Descarga la ECV 2025 y coloca los CSV en data/raw/ecv/')\n",
        "        return None, None\n",
        "    hdr = pd.read_csv(path, sep=ECV_SEP, encoding=ECV_ENC, nrows=0)\n",
        "    by_name = {str(c).strip().upper(): c for c in hdr.columns}\n",
        "    missing = [c for c in spec['columns'] if c not in by_name]\n",
        "    if missing:\n",
        "        raise ValueError(f'[{table}] Columnas faltantes: {missing}')\n",
        "    df = pd.read_csv(path, sep=ECV_SEP, encoding=ECV_ENC,\n",
        "                     usecols=[by_name[c] for c in spec['columns']],\n",
        "                     keep_default_na=False, na_values=[''])\n",
        "    df.columns = [str(c).strip().upper() for c in df.columns]\n",
        "    return df[spec['columns']], path\n",
        "\n",
        "print(f'Raíz: {PROJECT_ROOT}')\n",
        "print(f'Departamentos DANE ({len(CODIGOS_DANE)}): {sorted(CODIGOS_DANE)}')\n",
    ]))

    # ── 1. Servicios ─────────────────────────────────────────────
    cells.append(md([
        "---\n",
        "## 1. Capítulo «Servicios del Hogar»\n",
        "Variables: `P5018` (gasto electricidad COP/mes), `P5010` (estrato), `P8536/P8540/P3163` (cocción).\n",
    ]))
    cells.append(code([
        "df_serv, path_serv = load_chapter('servicios')\n",
        "if df_serv is not None:\n",
        "    print(f'Archivo: {path_serv.name}')\n",
        "    print(f'Filas: {len(df_serv):,}  Columnas: {df_serv.shape[1]}')\n",
        "    display(df_serv.head())\n",
    ]))

    cells.append(md([
        "### 1.1 Grano y Duplicados — DQ02 (Critical) y DQ03 (Warning ≥ 99 %)\n",
        "\n",
        "- **DQ02 (Critical 100 %):** `DIRECTORIO` o `SECUENCIA_P` nulos → hogar imposible de cruzar con ninguna dimensión → bloqueo inmediato.\n",
        "- **DQ03 (Warning mostly=0.99):** La fase 1 registró 212 duplicados en 88,432 filas (0.24 %). El umbral de 99 % deja margen para variaciones menores mientras alerta ante problemas de carga (>1 %).\n",
    ]))
    cells.append(code([
        "if df_serv is not None:\n",
        "    n_total  = len(df_serv)\n",
        "    n_dir    = df_serv['DIRECTORIO'].isna().sum()\n",
        "    n_seq    = df_serv['SECUENCIA_P'].isna().sum()\n",
        "    n_uniq   = df_serv.drop_duplicates(subset=HH_KEYS).shape[0]\n",
        "    n_dup    = n_total - n_uniq\n",
        "    pct_uniq = n_uniq / n_total * 100\n",
        "\n",
        "    res = pd.DataFrame({\n",
        "        'Regla':      ['DQ02 — DIRECTORIO nulo', 'DQ02 — SECUENCIA_P nulo', 'DQ03 — Duplicados HH_KEY'],\n",
        "        'Valor':      [n_dir, n_seq, n_dup],\n",
        "        'Pct':        [f'{n_dir/n_total*100:.4f}%', f'{n_seq/n_total*100:.4f}%', f'{n_dup/n_total*100:.4f}%'],\n",
        "        'Umbral':     ['0%', '0%', '≤1%'],\n",
        "        'Severidad':  ['Critical', 'Critical', 'Warning'],\n",
        "        'Estado':     [\n",
        "            'PASA' if n_dir == 0 else 'FALLA',\n",
        "            'PASA' if n_seq == 0 else 'FALLA',\n",
        "            'PASA' if pct_uniq >= 99 else 'FALLA',\n",
        "        ],\n",
        "    })\n",
        "    display(res)\n",
        "    print(f'Unicidad observada: {pct_uniq:.4f}%')\n",
        "    print(f'Justificación DQ03: fase 1 eliminó {n_dup} duplicados ({n_dup/n_total*100:.2f}%). Umbral=99% cubre el patrón histórico con margen.')\n",
        "else:\n",
        "    print('Sin datos reales. Fase 1: 212 duplicados en 88,432 filas (0.24%). Umbral DQ03 mostly=0.99 justificado.')\n",
    ]))

    cells.append(md([
        "### 1.2 Gasto de Electricidad `P5018` — DQ04 (Warning ≥ 70 %)\n",
        "\n",
        "- **Causa de nulos (~23 %):** hogares con servicios incluidos en el arriendo no reportan el valor del recibo.\n",
        "- **Umbral 70 %:** con <70 % de datos observados, la huella eléctrica dependería más de la imputación que del dato real, haciendo el KPI poco confiable para R1 y R6.\n",
        "- **Decisión de pipeline:** imputación por mediana de estrato (determinista); ceros de estratos 2–6 se reemplazan por la mediana del estrato.\n",
        "- **Outliers:** valores >P₉₉ corresponden a cobros comerciales o errores de digitación → truncar.\n",
    ]))
    cells.append(code([
        "if df_serv is not None:\n",
        "    df_serv['P5018'] = pd.to_numeric(df_serv['P5018'], errors='coerce')\n",
        "    n_total = len(df_serv)\n",
        "    n_obs   = df_serv['P5018'].notna().sum()\n",
        "    pct_obs = n_obs / n_total * 100\n",
        "    obs = df_serv['P5018'].dropna()\n",
        "    p99 = obs.quantile(0.99)\n",
        "    n_out = int((obs > p99).sum())\n",
        "\n",
        "    print('P5018 — Gasto mensual electricidad (COP/mes)')\n",
        "    print(f'  Observados:  {n_obs:,}  ({pct_obs:.2f}%)')\n",
        "    print(f'  Nulos:       {n_total - n_obs:,}  ({100 - pct_obs:.2f}%)')\n",
        "    print(f'  DQ04 ≥70%: {\"PASA\" if pct_obs >= 70 else \"FALLA\"}')\n",
        "    print()\n",
        "    desc = obs.describe(percentiles=[.01, .05, .25, .5, .75, .95, .99])\n",
        "    print(desc.to_string())\n",
        "    print(f'\\n  P99 = {p99:,.0f} COP/mes  → umbral de truncamiento')\n",
        "    print(f'  Outliers (>P99): {n_out:,}  ({n_out/n_total*100:.3f}%)  → cobros comerciales o error de digitación')\n",
        "else:\n",
        "    print('Sin datos reales. Fase 1: ~77.4% completitud. Umbral DQ04 ≥70% justificado.')\n",
        "    print('P99 ≈ 350,000 COP/mes. Outliers = cobros no residenciales o errores de captura.')\n",
    ]))

    cells.append(md([
        "### 1.3 Estrato `P5010` — DQ05 (Warning ≥ 99.9 %)\n",
        "\n",
        "Colombia define 6 estratos residenciales (1–6). Códigos 7 y 8 corresponden a propiedades no estratificadas (<0.02 % en F1).  \n",
        "**Umbral 99.9 %:** base en la frecuencia histórica observada (12 casos en 88,432 filas).  \n",
        "**Decisión:** reclasificar a 0 (\"No válido/No informa\"). Tarifa fallback = estrato 1.\n",
    ]))
    cells.append(code([
        "if df_serv is not None:\n",
        "    df_serv['P5010'] = pd.to_numeric(df_serv['P5010'], errors='coerce')\n",
        "    dist_e = df_serv['P5010'].value_counts(dropna=False).sort_index()\n",
        "    n_inv   = int((~df_serv['P5010'].between(1, 6)).sum())\n",
        "    pct_val = df_serv['P5010'].between(1, 6).mean() * 100\n",
        "\n",
        "    print('Distribución de P5010 (estrato):')\n",
        "    print(dist_e.to_string())\n",
        "    print(f'\\n  Fuera de [1,6]: {n_inv}  ({100 - pct_val:.4f}%)')\n",
        "    print(f'  DQ05 ≥99.9%:   {\"PASA\" if pct_val >= 99.9 else \"FALLA\"}')\n",
        "    print('  Decisión: reclasificar 7/8 → 0; tarifa fallback = estrato 1 (más bajo).')\n",
        "else:\n",
        "    print('Sin datos reales. Fase 1: 12 de 88,432 con código 7/8 (0.0136%). DQ05 ≥99.9% justificado.')\n",
    ]))

    # ── 2. Vivienda ──────────────────────────────────────────────
    cells.append(md([
        "---\n",
        "## 2. Capítulo «Datos de la Vivienda» — DQ06, DQ07, DQ08 (todos Critical)\n",
        "\n",
        "`P1_DEPARTAMENTO` es la **llave de integración** entre la ECV y la API IDEAM.  \n",
        "- **DQ07 (Critical 100%):** Nulo en la llave → hogar no puede recibir clima → R6/R7 inviables para ese hogar.  \n",
        "- **DQ08 (Critical 100%):** Código fuera del catálogo DIVIPOLA → JOIN incorrecto (clima de otro dpto) → KPIs contaminados. Base contractual: catálogo oficial DANE.\n",
    ]))
    cells.append(code([
        "df_viv, path_viv = load_chapter('vivienda')\n",
        "if df_viv is not None:\n",
        "    print(f'Archivo: {path_viv.name}  Filas: {len(df_viv):,}')\n",
        "    df_viv['P1_DEPARTAMENTO'] = pd.to_numeric(df_viv['P1_DEPARTAMENTO'], errors='coerce')\n",
        "    n_null  = int(df_viv['P1_DEPARTAMENTO'].isna().sum())\n",
        "    en_cat  = df_viv['P1_DEPARTAMENTO'].dropna().astype(int).isin(CODIGOS_DANE)\n",
        "    n_inv   = int((~en_cat).sum())\n",
        "    pct_comp = (1 - n_null / len(df_viv)) * 100\n",
        "    pct_val  = en_cat.mean() * 100\n",
        "\n",
        "    print(f'\\nDQ07 — P1_DEPARTAMENTO nulos: {n_null}  (completitud {pct_comp:.2f}%) → {\"PASA\" if n_null == 0 else \"FALLA\"}')\n",
        "    print(f'DQ08 — Fuera catálogo:       {n_inv}   ({100 - pct_val:.4f}%)       → {\"PASA\" if n_inv == 0 else \"FALLA\"}')\n",
        "\n",
        "    dist = (df_viv['P1_DEPARTAMENTO'].value_counts()\n",
        "            .rename_axis('codigo_dane').reset_index(name='hogares')\n",
        "            .assign(codigo_dane=lambda d: d['codigo_dane'].astype('Int64'))\n",
        "            .merge(dane_ref, on='codigo_dane', how='left')\n",
        "            .sort_values('codigo_dane'))\n",
        "    print(f'\\nDepartamentos distintos en ECV: {df_viv[\"P1_DEPARTAMENTO\"].dropna().nunique()}')\n",
        "    display(dist)\n",
        "else:\n",
        "    print('Sin datos reales. P1_DEPARTAMENTO: 100% completo esperado (campo obligatorio DANE).')\n",
        "    print('DQ08: todos los códigos dentro del catálogo DIVIPOLA (33 departamentos).')\n",
    ]))

    # ── 3. Características ────────────────────────────────────────
    cells.append(md([
        "---\n",
        "## 3. Capítulo «Características y Composición» — DQ09 (Critical 100 %)\n",
        "\n",
        "Este capítulo tiene **una fila por persona**. Se usa para contar integrantes por hogar\n",
        "(group-count por `DIRECTORIO + SECUENCIA_P` → `dim_hogar.num_personas`).  \n",
        "**DQ09:** Sin llaves válidas el group-count es imposible → columna nula en `dim_hogar` → R5 roto.\n",
    ]))
    cells.append(code([
        "df_car, path_car = load_chapter('caracteristicas')\n",
        "if df_car is not None:\n",
        "    print(f'Archivo: {path_car.name}  Filas: {len(df_car):,}  (personas, no hogares)')\n",
        "    n_dir = int(df_car['DIRECTORIO'].isna().sum())\n",
        "    n_seq = int(df_car['SECUENCIA_P'].isna().sum())\n",
        "    print(f'DQ09 — DIRECTORIO nulos:   {n_dir} → {\"PASA\" if n_dir == 0 else \"FALLA\"}')\n",
        "    print(f'DQ09 — SECUENCIA_P nulos:  {n_seq} → {\"PASA\" if n_seq == 0 else \"FALLA\"}')\n",
        "\n",
        "    personas_hh = df_car.groupby(HH_KEYS).size()\n",
        "    print('\\nPersonas por hogar — estadísticas:')\n",
        "    print(personas_hh.describe().to_string())\n",
        "else:\n",
        "    print('Sin datos reales. DQ09: DIRECTORIO y SECUENCIA_P sin nulos esperado.')\n",
        "    print('Promedio personas/hogar Colombia ≈ 3.0 según DANE.')\n",
    ]))

    # ── 4. Condiciones ────────────────────────────────────────────
    cells.append(md([
        "---\n",
        "## 4. Capítulo «Condiciones de Vida» — DQ10 (Critical) y DQ11 (Warning)\n",
        "\n",
        "Variables clave: `P1077S15` (tenencia carro — R3), `P1077S11` y `P1077S12` (equipos de climatización — R7).  \n",
        "El DANE define dominio `{1: Sí, 2: No}` para todas las variables de tenencia de bienes. Un valor fuera de `{1, 2}` es un error de codificación.\n",
    ]))
    cells.append(code([
        "df_cond, path_cond = load_chapter('condiciones')\n",
        "if df_cond is not None:\n",
        "    print(f'Archivo: {path_cond.name}  Filas: {len(df_cond):,}')\n",
        "    for var, desc, regla, sev in [\n",
        "        ('P1077S15', 'Carro particular (R3)', 'DQ10', 'Critical'),\n",
        "        ('P1077S11', 'Aire acondicionado (R7)', 'DQ11', 'Warning'),\n",
        "        ('P1077S12', 'Ventilador o abanico (R7)', 'DQ11', 'Warning'),\n",
        "    ]:\n",
        "        df_cond[var] = pd.to_numeric(df_cond[var], errors='coerce')\n",
        "        dist  = df_cond[var].value_counts(dropna=False).sort_index()\n",
        "        n_inv = int((~df_cond[var].isin([1, 2])).sum())\n",
        "        pct_v = df_cond[var].isin([1, 2]).mean() * 100\n",
        "        estado = 'PASA' if n_inv == 0 else 'FALLA'\n",
        "        print(f'\\n{var} — {desc}  [{regla}, {sev}]')\n",
        "        print(dist.to_string())\n",
        "        print(f'  Fuera de {{1,2}}: {n_inv}  ({100 - pct_v:.4f}%) → {estado}')\n",
        "else:\n",
        "    print('Sin datos reales. Fase 1: P1077S15/S11/S12 en dominio {1,2}. Sin valores fuera de rango.')\n",
    ]))
    cells.append(md([
        "### Reformulación de R3 (evidencia del perfilamiento)\n",
        "\n",
        "> La ECV **no captura variables de movilidad** (km/año, consumo de galones, cilindraje).  \n",
        "> `P1077S15` es puramente binario: posesión de carro (Sí/No).  \n",
        "> **Decisión de ingeniería (documentada aquí):** R3 reformulado como\n",
        "> *«comparar la huella residencial (eléctrica + cocción) entre hogares con y sin automóvil particular,\n",
        "> controlando por estrato socioeconómico»*.\n",
    ]))

    # ── 5. Verificación contrato columnar ────────────────────────
    cells.append(md([
        "---\n",
        "## 5. Verificación de Contrato Columnar (DQ01, DQ06, DQ09_col, DQ10_col)\n",
        "\n",
        "Cada suite GX arranca con `ExpectTableColumnsToMatchSet` (Critical). Si falta una columna requerida,\n",
        "el pipeline no puede continuar (la información no se puede fabricar).\n",
    ]))
    cells.append(code([
        "rows_c = []\n",
        "for tabla, spec in ECV_TABLES.items():\n",
        "    path = find_ecv(spec)\n",
        "    if path is None:\n",
        "        rows_c.append({'Tabla': tabla, 'Encontrado': False,\n",
        "                        'Col_req': len(spec['columns']), 'Col_pres': 'N/A', 'Missing': 'N/A'})\n",
        "        continue\n",
        "    hdr = pd.read_csv(path, sep=ECV_SEP, encoding=ECV_ENC, nrows=0)\n",
        "    cols_up = [str(c).strip().upper() for c in hdr.columns]\n",
        "    miss = [c for c in spec['columns'] if c not in cols_up]\n",
        "    rows_c.append({\n",
        "        'Tabla': tabla, 'Encontrado': True,\n",
        "        'Col_req': len(spec['columns']), 'Col_pres': len(cols_up),\n",
        "        'Missing': miss if miss else 'Ninguna',\n",
        "    })\n",
        "display(pd.DataFrame(rows_c))\n",
    ]))

    # ── 6. Síntesis ──────────────────────────────────────────────
    cells.append(md([
        "---\n",
        "## 6. Matriz de Síntesis — Hallazgos y Decisiones del Pipeline\n",
    ]))
    cells.append(code([
        "sintesis = pd.DataFrame([\n",
        "    {'Capítulo':'Servicios',      'Atributo':'DIRECTORIO+SECUENCIA_P', 'Dim':'Completitud',       'Regla':'DQ02','Sev':'Critical','Umbral':'100%',    'F1_obs':'~100%',    'Base_umbral':'Grano de hechos — sin llaves la fila no existe'},\n",
        "    {'Capítulo':'Servicios',      'Atributo':'DIRECTORIO+SECUENCIA_P', 'Dim':'Unicidad',           'Regla':'DQ03','Sev':'Warning', 'Umbral':'≥99%',     'F1_obs':'99.76%',   'Base_umbral':'F1: 212 dups en 88,432 filas (0.24%); >1% = error de carga'},\n",
        "    {'Capítulo':'Servicios',      'Atributo':'P5018',                  'Dim':'Completitud',       'Regla':'DQ04','Sev':'Warning', 'Umbral':'≥70%',     'F1_obs':'~77%',     'Base_umbral':'<70% → imputación domina el KPI eléctrico (R1,R6)'},\n",
        "    {'Capítulo':'Servicios',      'Atributo':'P5010',                  'Dim':'Validez',           'Regla':'DQ05','Sev':'Warning', 'Umbral':'≥99.9%',   'F1_obs':'~99.99%',  'Base_umbral':'F1: 12 hogares cod 7/8 (0.014%); reclasificar a 0'},\n",
        "    {'Capítulo':'Vivienda',       'Atributo':'columnas req.',           'Dim':'Validez (contrato)','Regla':'DQ06','Sev':'Critical','Umbral':'100%',    'F1_obs':'100%',     'Base_umbral':'Contrato fuente — columna faltante = pipeline roto'},\n",
        "    {'Capítulo':'Vivienda',       'Atributo':'P1_DEPARTAMENTO',        'Dim':'Completitud',       'Regla':'DQ07','Sev':'Critical','Umbral':'100%',    'F1_obs':'~100%',    'Base_umbral':'Llave de integración con API IDEAM (R6,R7)'},\n",
        "    {'Capítulo':'Vivienda',       'Atributo':'P1_DEPARTAMENTO',        'Dim':'Validez',           'Regla':'DQ08','Sev':'Critical','Umbral':'100%',    'F1_obs':'100%',     'Base_umbral':'Catálogo DIVIPOLA 33 depts — código inválido = JOIN incorrecto'},\n",
        "    {'Capítulo':'Características','Atributo':'DIRECTORIO+SECUENCIA_P', 'Dim':'Completitud',       'Regla':'DQ09','Sev':'Critical','Umbral':'100%',    'F1_obs':'~100%',    'Base_umbral':'Sin llaves, group-count integrantes imposible (R5)'},\n",
        "    {'Capítulo':'Condiciones',    'Atributo':'P1077S15',               'Dim':'Validez',           'Regla':'DQ10','Sev':'Critical','Umbral':'100%',    'F1_obs':'100%',     'Base_umbral':'Diccionario DANE: dominio contractual {1:Sí, 2:No}'},\n",
        "    {'Capítulo':'Condiciones',    'Atributo':'P1077S11, P1077S12',     'Dim':'Validez',           'Regla':'DQ11','Sev':'Warning', 'Umbral':'100%',    'F1_obs':'~100%',    'Base_umbral':'Warning: alimenta solo R7 (S11 aire acondicionado, S12 ventilador; dict. DANE ECV 2025)'},\n",
        "])\n",
        "display(sintesis)\n",
    ]))

    return nb(cells)


# ─────────────────────────────────────────────────────────────────
#  NOTEBOOK 02 — Perfilamiento API IDEAM
# ─────────────────────────────────────────────────────────────────
def make_nb02():
    cells = []

    cells.append(md([
        "# Perfilamiento de la Fuente Secundaria: API IDEAM (datos.gov.co)\n",
        "**Proyecto:** ETL Segunda Entrega — Huella de Carbono en Hogares Colombianos (ODS 12)  \n",
        "**Responsable:** David Aponte (Persona 2 — API y Calidad de Datos)  \n",
        "**Autores:** Nikol Hurtado, David Aponte, Diana Panesso, Sebastián Celorio  \n",
        "\n",
        "## Objetivo\n",
        "Documentar el perfilamiento de la **API SODA del IDEAM** (dataset `sbwg-7ju4` en datos.gov.co),\n",
        "evaluando cobertura espacial/temporal, validez física de temperatura y estrategia de integración con la ECV 2025.\n",
        "Cada hallazgo se vincula con las reglas GX DQ12–DQ18 y con los requisitos R6/R7.\n",
        "\n",
        "> **Instrucciones de ejecución:**  \n",
        "> Opción A: correr el pipeline completo (`docker compose up` + DAG) y luego usar el CSV generado.  \n",
        "> Opción B: correr `python scripts/verificar_cobertura_api.py` para explorar la cobertura primero.  \n",
        "> Opción C: ejecutar directamente las celdas (se conecta a la API en tiempo real).\n",
    ]))

    cells.append(md("## 0. Configuración y Parámetros del Endpoint"))
    cells.append(code([
        "import warnings\n",
        "from pathlib import Path\n",
        "import numpy as np\n",
        "import pandas as pd\n",
        "warnings.filterwarnings('ignore')\n",
        "pd.set_option('display.float_format', '{:,.4f}'.format)\n",
        "\n",
        "try:\n",
        "    import requests\n",
        "    HAS_REQUESTS = True\n",
        "except ImportError:\n",
        "    HAS_REQUESTS = False\n",
        "    print('[AVISO] requests no instalado. Las celdas de llamada a la API quedarán desactivadas.')\n",
        "\n",
        "PROJECT_ROOT = Path('..').resolve()\n",
        "REF_DIR  = PROJECT_ROOT / 'data' / 'reference'\n",
        "RAW_API  = PROJECT_ROOT / 'data' / 'raw' / 'api'\n",
        "\n",
        "# ─── Parámetros del endpoint (deben coincidir con src/config.py) ───\n",
        "ENDPOINT    = 'https://www.datos.gov.co/resource/sbwg-7ju4.json'\n",
        "SENSOR_CODE = '0068'   # Temperatura del Aire a 2 metros, °C\n",
        "API_COLUMNS = ['codigoestacion', 'nombreestacion', 'departamento', 'municipio',\n",
        "               'latitud', 'longitud', 'suma', 'n', 'minimo', 'maximo',\n",
        "               'window_start', 'window_end']\n",
        "TEMP_MIN_PLAUSIBLE = -15.0\n",
        "TEMP_MAX_PLAUSIBLE =  50.0\n",
        "\n",
        "dane_ref     = pd.read_csv(REF_DIR / 'dane_departamentos.csv', sep=';')\n",
        "CODIGOS_DANE = set(dane_ref['codigo_dane'].astype(int))\n",
        "\n",
        "print(f'Endpoint IDEAM : {ENDPOINT}')\n",
        "print(f'Sensor code    : {SENSOR_CODE}  (Temperatura Aire 2 m, °C)')\n",
        "print(f'Rango físico   : [{TEMP_MIN_PLAUSIBLE}, {TEMP_MAX_PLAUSIBLE}] °C')\n",
        "print(f'Departamentos DANE válidos: {len(CODIGOS_DANE)}')\n",
    ]))

    cells.append(md([
        "---\n",
        "## 1. Contrato del Endpoint — DQ12 (Critical)\n",
        "\n",
        "La consulta SODA utiliza agregación en el servidor (`$select`, `$group`) para reducir el volumen de datos.\n",
        "Columnas esperadas en la respuesta:\n",
        "\n",
        "| Campo | Tipo | Rol |\n",
        "|---|---|---|\n",
        "| `codigoestacion` | str | ID de la estación IDEAM |\n",
        "| `nombreestacion` | str | Nombre de la estación |\n",
        "| `departamento` | str | Llave de integración con ECV |\n",
        "| `municipio` | str | Contexto geográfico |\n",
        "| `latitud`, `longitud` | float | Coordenadas para DQ18 |\n",
        "| `suma`, `n` | float | Para calcular temperatura media exacta: $\\\\bar{T} = \\\\text{suma}/n$ |\n",
        "| `minimo`, `maximo` | float | Para validar rango físico (DQ15) |\n",
        "| `window_start`, `window_end` | date-str | Compatibilidad temporal con ECV 2025 (DQ16) |\n",
        "\n",
        "**DQ12 (Critical 100%):** Si la API modifica su esquema (columna renombrada o eliminada), el pipeline falla determinísticamente → no se reintenta.\n",
    ]))
    cells.append(code([
        "# Muestra de la API — ventana de 7 días para validar el contrato\n",
        "sample_df = None\n",
        "if HAS_REQUESTS:\n",
        "    try:\n",
        "        params = {\n",
        "            '$select': ('codigoestacion,nombreestacion,departamento,municipio,latitud,longitud,'\n",
        "                        'sum(valorobservado) as suma,count(*) as n,'\n",
        "                        'min(valorobservado) as minimo,max(valorobservado) as maximo'),\n",
        "            '$where': (f\"codigosensor='{SENSOR_CODE}' \"\n",
        "                       \"AND fechaobservacion >= '2025-01-01T00:00:00' \"\n",
        "                       \"AND fechaobservacion < '2025-01-08T00:00:00'\"),\n",
        "            '$group': 'codigoestacion,nombreestacion,departamento,municipio,latitud,longitud',\n",
        "            '$order': 'codigoestacion',\n",
        "            '$limit': '1000',\n",
        "        }\n",
        "        r = requests.get(ENDPOINT, params=params, timeout=(15, 120))\n",
        "        r.raise_for_status()\n",
        "        sample_df = pd.DataFrame(r.json())\n",
        "        sample_df['window_start'] = '2025-01-01'\n",
        "        sample_df['window_end']   = '2025-01-08'\n",
        "        print(f'Muestra obtenida: {len(sample_df)} filas, {sample_df.shape[1]} columnas')\n",
        "        print(f'Columnas: {sample_df.columns.tolist()}')\n",
        "        display(sample_df.head())\n",
        "    except Exception as exc:\n",
        "        print(f'[AVISO] No se pudo conectar a la API: {exc}')\n",
        "        print('Continúa con el CSV pre-generado (si existe).')\n",
        "else:\n",
        "    print('requests no disponible — saltando llamada en vivo.')\n",
        "\n",
        "# Intentar leer CSV ya generado por el pipeline\n",
        "if sample_df is None:\n",
        "    csv_candidate = next(RAW_API.glob('api_ideam_raw.csv'), None) if RAW_API.exists() else None\n",
        "    if csv_candidate is None:\n",
        "        # Buscar en data/work/\n",
        "        work = PROJECT_ROOT / 'data' / 'work'\n",
        "        if work.exists():\n",
        "            for f in sorted(work.rglob('api_ideam_raw.csv')):\n",
        "                csv_candidate = f\n",
        "                break\n",
        "    if csv_candidate:\n",
        "        sample_df = pd.read_csv(csv_candidate)\n",
        "        print(f'CSV cargado desde: {csv_candidate}')\n",
        "        print(f'Filas: {len(sample_df):,}  Columnas: {sample_df.shape[1]}')\n",
        "        display(sample_df.head())\n",
        "    else:\n",
        "        print('[AVISO] No hay CSV de la API disponible. Ejecuta el DAG primero.')\n",
    ]))

    cells.append(md([
        "---\n",
        "## 2. Validez del Rango Físico de Temperatura — DQ15 (Critical ≥ 99.5 %)\n",
        "\n",
        "> **Aviso oficial de la ficha del IDEAM:** *«El IDEAM no validó previamente la totalidad de los valores\n",
        "> horarios publicados y pueden existir lecturas anómalas por fallas técnicas en sensores remotos».*\n",
        "\n",
        "- Rango plausible para Colombia: **[-15 °C, 50 °C]** (cubre desde los páramos andinos a las costas tropicales).\n",
        "- La regla evalúa `minimo` y `maximo` de cada estación × ventana: una sola lectura imposible queda registrada.\n",
        "- **Umbral 99.5 %:** hasta 0.5 % de fallas de sensor son tolerables sin bloquear el pipeline, pero se registran y excluyen del promedio departamental. Base: aviso de la ficha del IDEAM.\n",
        "- **Decisión de pipeline:** filas con `minimo` < -15 °C o `maximo` > 50 °C se excluyen de `build_dim_clima()` y se cuentan en `integration_report.json`.\n",
    ]))
    cells.append(code([
        "if sample_df is not None:\n",
        "    df = sample_df.copy()\n",
        "    for col in ('suma', 'n', 'minimo', 'maximo', 'latitud', 'longitud'):\n",
        "        df[col] = pd.to_numeric(df[col], errors='coerce')\n",
        "\n",
        "    n_total = len(df)\n",
        "    fuera_min = (df['minimo'] < TEMP_MIN_PLAUSIBLE).sum()\n",
        "    fuera_max = (df['maximo'] > TEMP_MAX_PLAUSIBLE).sum()\n",
        "    fuera_any = ((df['minimo'] < TEMP_MIN_PLAUSIBLE) | (df['maximo'] > TEMP_MAX_PLAUSIBLE)).sum()\n",
        "    pct_ok = (n_total - fuera_any) / n_total * 100\n",
        "\n",
        "    print('DQ15 — Rango físico plausible de temperatura')\n",
        "    print(f'  Total filas          : {n_total:,}')\n",
        "    print(f'  minimo < {TEMP_MIN_PLAUSIBLE}°C : {fuera_min:,}  (fallas sensor por frío extremo)')\n",
        "    print(f'  maximo > {TEMP_MAX_PLAUSIBLE}°C  : {fuera_max:,}  (fallas sensor por calor extremo)')\n",
        "    print(f'  Total fuera de rango : {fuera_any:,}  ({100 - pct_ok:.4f}%)')\n",
        "    print(f'  DQ15 umbral ≥99.5%   : {\"PASA\" if pct_ok >= 99.5 else \"FALLA\"}')\n",
        "\n",
        "    print(f'\\n  Estadísticas de temperatura mínima (°C):')\n",
        "    print(df['minimo'].describe().to_string())\n",
        "    print(f'\\n  Estadísticas de temperatura máxima (°C):')\n",
        "    print(df['maximo'].describe().to_string())\n",
        "else:\n",
        "    print('Sin datos: rango físico Colombia [-15°C, 50°C] justificado por geografia del país.')\n",
        "    print('Umbral 99.5%: basado en aviso oficial IDEAM sobre posibles fallas de sensor.')\n",
    ]))

    cells.append(md([
        "---\n",
        "## 3. Cobertura Departamental — DQ13, DQ14 y DQ17\n",
        "\n",
        "- **DQ13 (Critical ≥1 fila):** Si la extracción completa devuelve 0 filas, la integración con la ECV es imposible → bloqueo.\n",
        "- **DQ14 (Critical ≥99%):** `departamento` nulo → estación sin llave de integración → no se puede asignar clima a ningún hogar de ese departamento.\n",
        "- **DQ17 (Warning ≥20 departamentos):** Con menos de 20 departamentos con datos climáticos, la cobertura es insuficiente para análisis de correlación temperatura–consumo (R6/R7). Base: Colombia tiene 33 departamentos; 20 = mínimo estadístico para inferencia.\n",
    ]))
    cells.append(code([
        "if sample_df is not None:\n",
        "    df = sample_df.copy()\n",
        "\n",
        "    # DQ13 — fila mínima\n",
        "    print(f'DQ13 — Filas totales: {len(df):,}  (min=1) → {\"PASA\" if len(df) >= 1 else \"FALLA\"}')\n",
        "\n",
        "    # DQ14 — departamento nulo\n",
        "    n_dep_null = df['departamento'].isna().sum()\n",
        "    pct_dep_ok = (1 - n_dep_null / len(df)) * 100\n",
        "    print(f'DQ14 — departamento nulos: {n_dep_null}  (completitud {pct_dep_ok:.2f}%) → {\"PASA\" if pct_dep_ok >= 99 else \"FALLA\"}')\n",
        "\n",
        "    # DQ17 — departamentos distintos\n",
        "    n_deptos = df['departamento'].dropna().nunique()\n",
        "    print(f'DQ17 — Departamentos distintos: {n_deptos}  (umbral ≥20) → {\"PASA\" if n_deptos >= 20 else \"FALLA\"}')\n",
        "\n",
        "    # Distribución por departamento\n",
        "    dist_dep = df.groupby('departamento').agg(\n",
        "        estaciones=('codigoestacion', 'nunique'),\n",
        "        filas=('codigoestacion', 'count'),\n",
        "    ).sort_values('filas', ascending=False)\n",
        "    print(f'\\nDistribución por departamento (top 15):')\n",
        "    display(dist_dep.head(15))\n",
        "\n",
        "    print(f'\\nJustificación DQ17 umbral=20:')\n",
        "    print('  Colombia tiene 33 departamentos. Con <20 con datos, la correlación temperatura–kWh')\n",
        "    print('  (R6/R7) tendría n insuficiente para inferencia estadística robusta.')\n",
        "else:\n",
        "    print('Sin datos. Cobertura esperada: ≥25 departamentos con datos del IDEAM.')\n",
    ]))

    cells.append(md([
        "---\n",
        "## 4. Consistencia Temporal — DQ16 (Critical 100 %)\n",
        "\n",
        "La ECV 2025 captura el año 2025. La API debe extraer datos del mismo período para que la integración sea válida.  \n",
        "**DQ16 (Critical 100%):** Ventanas fuera del año 2025 en `window_start` introducirían datos climáticos de otro período → incompatibles con la ECV → bloqueo.\n",
    ]))
    cells.append(code([
        "if sample_df is not None:\n",
        "    if 'window_start' in sample_df.columns:\n",
        "        n_bad = (~sample_df['window_start'].astype(str).str.startswith('2025')).sum()\n",
        "        pct_ok = (1 - n_bad / len(sample_df)) * 100\n",
        "        print(f'DQ16 — Ventanas fuera de 2025: {n_bad}  ({100 - pct_ok:.4f}%)')\n",
        "        print(f'DQ16 umbral 100% → {\"PASA\" if n_bad == 0 else \"FALLA\"}')\n",
        "        print(f'\\nVentanas encontradas: {sample_df[\"window_start\"].unique()[:10]}')\n",
        "    else:\n",
        "        print('[AVISO] Columna window_start no presente en la muestra.')\n",
        "else:\n",
        "    print('Sin datos. DQ16: API_START_DATE=2025-01-01, API_END_DATE=2026-01-01 garantizan año 2025.')\n",
    ]))

    cells.append(md([
        "---\n",
        "## 5. Coordenadas Geográficas — DQ18 (Warning ≥ 99 %)\n",
        "\n",
        "Límites geográficos de Colombia:\n",
        "- **Latitud:** [-5°, 14°] (desde el sur de Amazonas hasta La Guajira)\n",
        "- **Longitud:** [-82°, -66°] (desde el Pacífico hasta los Llanos Orientales; incluye San Andrés y Providencia a -81.7°)\n",
        "\n",
        "**DQ18 (Warning ≥99%):** Coordenadas fuera de estos límites indican estaciones con datos corruptos de GPS. Warning porque no impiden el cálculo de temperatura, pero sí el análisis espacial.\n",
    ]))
    cells.append(code([
        "if sample_df is not None:\n",
        "    df = sample_df.copy()\n",
        "    df['latitud']   = pd.to_numeric(df['latitud'],  errors='coerce')\n",
        "    df['longitud']  = pd.to_numeric(df['longitud'], errors='coerce')\n",
        "\n",
        "    n_lat_ok  = df['latitud'].between(-5, 14).sum()\n",
        "    n_lon_ok  = df['longitud'].between(-82, -66).sum()\n",
        "    n_lat_bad = len(df) - n_lat_ok\n",
        "    n_lon_bad = len(df) - n_lon_ok\n",
        "    pct_lat   = n_lat_ok / len(df) * 100\n",
        "    pct_lon   = n_lon_ok / len(df) * 100\n",
        "\n",
        "    print('DQ18 — Coordenadas dentro de Colombia')\n",
        "    print(f'  Latitud  [-5°, 14°]:   {n_lat_ok:,} OK  {n_lat_bad:,} fuera  ({100 - pct_lat:.4f}%) → {\"PASA\" if pct_lat >= 99 else \"FALLA\"}')\n",
        "    print(f'  Longitud [-82°, -66°]: {n_lon_ok:,} OK  {n_lon_bad:,} fuera  ({100 - pct_lon:.4f}%) → {\"PASA\" if pct_lon >= 99 else \"FALLA\"}')\n",
        "\n",
        "    print('\\nEstadísticas de latitud:')\n",
        "    print(df['latitud'].describe().to_string())\n",
        "    print('\\nEstadísticas de longitud:')\n",
        "    print(df['longitud'].describe().to_string())\n",
        "else:\n",
        "    print('Sin datos. Límites Colombia: lat [-5, 14], lon [-82, -66]. Umbral ≥99%.')\n",
    ]))

    cells.append(md([
        "---\n",
        "## 6. Clasificación Bioclimática (Soporte R6 y R7)\n",
        "\n",
        "La temperatura media departamental se clasifica en pisos térmicos para responder R6:  \n",
        "*«¿Los hogares de departamentos cálidos generan más kWh/mes y kg CO₂ que los de templados/fríos?»*\n",
        "\n",
        "| Piso Térmico | Rango | Ejemplos |\n",
        "|---|---|---|\n",
        "| **Cálido** | > 24 °C | Atlántico, Bolívar, César |\n",
        "| **Templado** | 18 °C – 24 °C | Antioquia, Risaralda, Caldas |\n",
        "| **Frío** | < 18 °C | Bogotá D.C., Boyacá, Nariño |\n",
    ]))
    cells.append(code([
        "def piso_termico(temp):\n",
        "    if pd.isna(temp): return 'Sin dato'\n",
        "    if temp > 24.0:   return 'Cálido'\n",
        "    if temp >= 18.0:  return 'Templado'\n",
        "    return 'Frío'\n",
        "\n",
        "# Demostración con datos de la muestra si disponibles\n",
        "if sample_df is not None:\n",
        "    df = sample_df.copy()\n",
        "    for col in ('suma', 'n'):\n",
        "        df[col] = pd.to_numeric(df[col], errors='coerce')\n",
        "    df = df[df['n'].gt(0) & df['suma'].notna()]\n",
        "\n",
        "    clima_dep = df.groupby('departamento').agg(\n",
        "        suma=('suma', 'sum'), n=('n', 'sum')\n",
        "    ).reset_index()\n",
        "    clima_dep['temp_media_c'] = (clima_dep['suma'] / clima_dep['n']).round(2)\n",
        "    clima_dep['piso_termico'] = clima_dep['temp_media_c'].apply(piso_termico)\n",
        "    clima_dep = clima_dep.sort_values('temp_media_c', ascending=False)\n",
        "\n",
        "    print('Temperatura media por departamento y piso térmico:')\n",
        "    display(clima_dep[['departamento', 'temp_media_c', 'piso_termico']].head(20))\n",
        "\n",
        "    print('\\nResumen por piso térmico:')\n",
        "    print(clima_dep['piso_termico'].value_counts().to_string())\n",
        "else:\n",
        "    test_temps = [14.2, 21.5, 28.3, float('nan')]\n",
        "    print('Función de clasificación — prueba:')\n",
        "    for t in test_temps:\n",
        "        print(f'  Temperatura {t}°C → Piso térmico: {piso_termico(t)}')\n",
    ]))

    cells.append(md([
        "---\n",
        "## 7. Estrategia de Normalización del Campo `departamento`\n",
        "\n",
        "El IDEAM publica los nombres de departamentos sin estandarización consistente:\n",
        "- 'Bogotá, D.C.' / 'BOGOTÁ D.C.' / 'Bogotá' → deben mapear a código DANE 11\n",
        "- 'Archipiélago de San Andrés...' → código DANE 88\n",
        "- 'La Guajira' / 'Guajira' → código DANE 44\n",
        "\n",
        "La tabla `ALIAS_DEPARTAMENTO` en `src/transform.py` maneja estas variantes.\n",
    ]))
    cells.append(code([
        "import unicodedata, re\n",
        "\n",
        "ALIAS_DEP = {\n",
        "    'bogota': 'bogota dc',\n",
        "    'bogota d c': 'bogota dc',\n",
        "    'santafe de bogota': 'bogota dc',\n",
        "    'archipielago de san andres providencia y santa catalina': 'san andres y providencia',\n",
        "    'san andres providencia y santa catalina': 'san andres y providencia',\n",
        "    'san andres': 'san andres y providencia',\n",
        "    'guajira': 'la guajira',\n",
        "}\n",
        "\n",
        "def canonical(text):\n",
        "    t = unicodedata.normalize('NFKD', str(text))\n",
        "    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()\n",
        "    t = re.sub(r'[^a-z0-9 ]', ' ', t)\n",
        "    t = re.sub(r'\\s+', ' ', t).strip()\n",
        "    t = ALIAS_DEP.get(t, t)\n",
        "    return t.replace('bogota d c', 'bogota dc')\n",
        "\n",
        "# Test\n",
        "ejemplos = ['Bogotá, D.C.', 'BOGOTÁ D.C.', 'Archipiélago de San Andrés, Providencia y Santa Catalina',\n",
        "            'La Guajira', 'ANTIOQUIA', 'Valle del Cauca', 'Bolívar']\n",
        "test_df = pd.DataFrame({'original': ejemplos, 'canonical': [canonical(e) for e in ejemplos]})\n",
        "# Mapear código DANE\n",
        "mapa_nombre_codigo = {canonical(row['departamento']): row['codigo_dane']\n",
        "                       for _, row in dane_ref.iterrows()}\n",
        "test_df['codigo_dane'] = test_df['canonical'].map(mapa_nombre_codigo)\n",
        "display(test_df)\n",
    ]))

    cells.append(md([
        "---\n",
        "## 8. Matriz de Síntesis — API IDEAM (DQ12–DQ18)\n",
    ]))
    cells.append(code([
        "sintesis_api = pd.DataFrame([\n",
        "    {'Atributo':'columnas req.',     'Dimensión':'Validez (contrato)', 'Regla':'DQ12','Sev':'Critical','Umbral':'100%',   'Base_umbral':'Cambio de esquema en la API = error determinístico'},\n",
        "    {'Atributo':'filas totales',     'Dimensión':'Completitud',        'Regla':'DQ13','Sev':'Critical','Umbral':'≥1',     'Base_umbral':'0 filas = sin datos climáticos = R6/R7 inviables'},\n",
        "    {'Atributo':'departamento',      'Dimensión':'Completitud',        'Regla':'DQ14','Sev':'Critical','Umbral':'≥99%',   'Base_umbral':'PROVISIONAL — estación sin llave: no contribuye a dim_clima'},\n",
        "    {'Atributo':'minimo, maximo',    'Dimensión':'Validez',            'Regla':'DQ15','Sev':'Critical','Umbral':'≥99.5%', 'Base_umbral':'Rango físico Colombia. Aviso oficial IDEAM de fallas sensor'},\n",
        "    {'Atributo':'window_start',      'Dimensión':'Consistencia temp.', 'Regla':'DQ16','Sev':'Critical','Umbral':'100%',   'Base_umbral':'ECV 2025: clima debe ser 2025 para alineación temporal'},\n",
        "    {'Atributo':'departamento',      'Dimensión':'Completitud (cob.)', 'Regla':'DQ17','Sev':'Warning', 'Umbral':'≥20',    'Base_umbral':'PROVISIONAL — mínimo estadístico para correlación R6/R7 (33 deptos total)'},\n",
        "    {'Atributo':'latitud, longitud', 'Dimensión':'Validez',            'Regla':'DQ18','Sev':'Warning', 'Umbral':'≥99%',   'Base_umbral':'Límites geográficos Colombia [lat -5/14, lon -82/-66]'},\n",
        "])\n",
        "display(sintesis_api)\n",
    ]))

    cells.append(md([
        "---\n",
        "## 9. Conclusiones y Decisiones del Pipeline (API IDEAM)\n",
    ]))
    cells.append(code([
        "conclusiones = pd.DataFrame([\n",
        "    {'Hallazgo':'Nombres departamento no estandarizados',\n",
        "     'Ejemplo': 'Bogotá D.C. / BOGOTÁ, D.C.',\n",
        "     'Decisión':'Normalización Unicode + tabla ALIAS_DEPARTAMENTO → canonical name → código DANE'},\n",
        "    {'Hallazgo':'Fallas de sensor (<0.5%)',\n",
        "     'Ejemplo': 'minimo < -15°C o maximo > 50°C',\n",
        "     'Decisión':'Excluir fila de build_dim_clima(); registrar en integration_report.json'},\n",
        "    {'Hallazgo':'Cobertura parcial (no todos los 33 deptos tienen estaciones)',\n",
        "     'Ejemplo': 'Amazonas, Guainía, Vaupés tienen pocas estaciones',\n",
        "     'Decisión':'Hogares sin clima: fk_clima NULL + clima_emparejado=0; R6/R7 los excluyen'},\n",
        "    {'Hallazgo':'Temperatura media = suma(suma)/suma(n) de las ventanas',\n",
        "     'Ejemplo': 'Suma ponderada por número de lecturas',\n",
        "     'Decisión':'Promedio exacto y reproducible; no promedio de promedios (evita sesgo de estación)'},\n",
        "    {'Hallazgo':'DQ17 umbral=20 PROVISIONAL',\n",
        "     'Ejemplo': 'Calibrar con scripts/verificar_cobertura_api.py',\n",
        "     'Decisión':'Ejecutar verificación antes del primer deploy; ajustar umbral con datos reales'},\n",
        "])\n",
        "display(conclusiones)\n",
    ]))

    return nb(cells)


# ─────────────────────────────────────────────────────────────────
#  Escritura de notebooks
# ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    nb01 = make_nb01()
    nb02 = make_nb02()

    path01 = NB_DIR / '01_perfilamiento_ecv_primaria.ipynb'
    path02 = NB_DIR / '02_perfilamiento_api_ideam.ipynb'

    with open(path01, 'w', encoding='utf-8') as f:
        json.dump(nb01, f, ensure_ascii=False, indent=1)
    with open(path02, 'w', encoding='utf-8') as f:
        json.dump(nb02, f, ensure_ascii=False, indent=1)

    print(f'OK: {path01}  ({len(nb01["cells"])} celdas)')
    print(f'OK: {path02}  ({len(nb02["cells"])} celdas)')
