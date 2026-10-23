"""
DASHBOARD — salidas analiticas R1-R7 consultando el Data Warehouse MySQL.

Uso (desde la raiz del repo, con el DW cargado y el .env disponible):
    python scripts/dashboard_bi.py                  # exige MySQL; falla si no hay conexion
    python scripts/dashboard_bi.py --allow-csv      # SOLO para desarrollo: usa los CSV preparados

Genera docs/evidence/dashboard_bi.html (autocontenido, sin internet). El encabezado de la
pagina dice de donde salieron los datos, para que nadie confunda un respaldo con el DW.
"""

import argparse
import html
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))            # permite "python scripts/dashboard_bi.py" desde la raiz

import pandas as pd  # noqa: E402

from src import config  # noqa: E402

log = logging.getLogger("dashboard")
OUT = ROOT / "docs" / "evidence" / "dashboard_bi.html"
TABLES = ["dim_hogar", "dim_ubicacion", "dim_clima", "dim_combustibles", "fact_huella_carbono"]
PISO_ORDER = ["Cálido", "Templado", "Frío"]


# --------------------------------------------------------------------------- datos
def fetch_from_mysql():
    from src.db import sqlalchemy_engine
    engine = sqlalchemy_engine()
    with engine.connect() as conn:
        data = {t: pd.read_sql(f"SELECT * FROM {t}", conn) for t in TABLES}
        audit = pd.read_sql("SELECT run_id, MAX(loaded_at) AS loaded_at FROM etl_audit_log "
                            "WHERE status = 'SUCCESS' GROUP BY run_id ORDER BY loaded_at DESC LIMIT 1", conn)
    run = audit["run_id"].iloc[0] if len(audit) else "sin registro de auditoria"
    return data, f"MySQL DW {config.DB_HOST}:{config.DB_PORT}/{config.DW_DB} (ultimo lote: {run})"


def fetch_from_csv():
    dirs = sorted((config.DATA_DIR / "work").glob("*/prepared"))
    if not dirs:
        raise RuntimeError("No hay archivos preparados en data/work/*/prepared")
    return ({t: pd.read_csv(dirs[-1] / f"{t}.csv") for t in TABLES},
            f"RESPALDO: CSV preparados ({dirs[-1].parent.name}), NO el Data Warehouse")


def build_frame(d):
    df = d["fact_huella_carbono"].merge(d["dim_ubicacion"], left_on="fk_ubicacion", right_on="sk_ubicacion", how="left")
    df = df.merge(d["dim_hogar"], left_on="fk_hogar", right_on="sk_hogar", how="left")
    clima = d["dim_clima"].drop(columns=["codigo_departamento", "nombre_departamento"])
    df = df.merge(clima, left_on="fk_clima", right_on="sk_clima", how="left")
    df = df.merge(d["dim_combustibles"], left_on="fk_combustible_cocina", right_on="sk_combustible", how="left")
    df["tipo_combustible"] = df["tipo_combustible"].fillna("Sin combustible informado")
    return df


# --------------------------------------------------------------------------- HTML
def bars(items, unit="", fmt="{:,.1f}"):
    """Grafico de barras horizontal en SVG. items = [(etiqueta, valor)]."""
    items = [(str(k), float(v)) for k, v in items if pd.notna(v)]
    if not items:
        return "<p class='muted'>Sin datos.</p>"
    top = max(v for _, v in items) or 1
    h, rows = 26, []
    for i, (k, v) in enumerate(items):
        w = max(2, 330 * v / top)
        rows.append(f"<text x='170' y='{i*h+17}' text-anchor='end' class='lbl'>{html.escape(k)}</text>"
                    f"<rect x='178' y='{i*h+5}' width='{w:.0f}' height='16' rx='3' class='bar'/>"
                    f"<text x='{178+w+6:.0f}' y='{i*h+17}' class='val'>{fmt.format(v)}{unit}</text>")
    return f"<svg viewBox='0 0 640 {len(items)*h+6}' role='img'>{''.join(rows)}</svg>"


def table(df, fmt=None):
    fmt = fmt or {}
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = "".join("<tr>" + "".join(
        f"<td>{(fmt.get(c, '{}')).format(v) if pd.notna(v) else '—'}</td>" for c, v in r.items()) + "</tr>"
        for _, r in df.iterrows())
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def section(code, title, question, chart, tbl, note=""):
    n = f"<p class='note'>{note}</p>" if note else ""
    return (f"<section><h2><span>{code}</span> {title}</h2><p class='q'>{question}</p>"
            f"{chart}{tbl}{n}</section>")


def compute(df, d):
    s = []
    estr = df[df.estrato.between(1, 6)].assign(estrato=lambda x: x.estrato.astype(int))

    r1 = estr.groupby("estrato").agg(hogares=("sk_fact", "count"), kwh=("kwh_consumidos_estimados", "mean"),
                                     co2=("emisiones_energia_kg", "mean")).reset_index()
    s.append(section("R1", "Huella eléctrica por estrato",
                     "¿Cuánta energía y CO₂ eléctrico genera un hogar según su estrato?",
                     bars([(f"Estrato {int(r.estrato)}", r.kwh) for r in r1.itertuples()], " kWh/mes"),
                     table(r1.rename(columns={"kwh": "kWh/mes (media)", "co2": "kg CO₂/año (media)"}),
                           {"hogares": "{:,.0f}", "kWh/mes (media)": "{:,.1f}", "kg CO₂/año (media)": "{:,.1f}"}),
                     "Los hogares sin estrato (valor 0 en la base) se excluyen de esta vista."))

    r2 = df.groupby("tipo_combustible").agg(hogares=("sk_fact", "count"),
                                            ton=("emisiones_coccion_kg", lambda x: x.sum() / 1000),
                                            media=("emisiones_coccion_kg", "mean")).reset_index()
    s.append(section("R2", "Emisiones de cocina por combustible",
                     "¿Cuánto aporta cada combustible de cocina?",
                     bars(r2.sort_values("ton", ascending=False).apply(lambda r: (r.tipo_combustible, r.ton), axis=1), " t CO₂/año"),
                     table(r2.rename(columns={"ton": "t CO₂/año (total)", "media": "kg CO₂/año (media)"}),
                           {"hogares": "{:,.0f}", "t CO₂/año (total)": "{:,.0f}", "kg CO₂/año (media)": "{:,.1f}"}),
                     "Depende de supuestos de precio y consumo (ver docs/supuestos_y_trazabilidad.md, S4–S9)."))

    r3 = estr.groupby(["estrato", "tiene_vehiculo"]).agg(hogares=("sk_fact", "count"),
                                                         huella=("huella_total_anual_kg", "mean")).reset_index()
    s.append(section("R3'", "Huella con y sin vehículo, por estrato",
                     "¿Cómo se compara la huella por energía y cocina de hogares con y sin vehículo, a igual estrato?",
                     bars([(f"E{int(r.estrato)} · {'con' if r.tiene_vehiculo == 'Sí' else 'sin'} vehículo", r.huella)
                           for r in r3.itertuples()], " kg/año"),
                     table(r3.rename(columns={"huella": "kg CO₂/año (media)"}),
                           {"hogares": "{:,.0f}", "kg CO₂/año (media)": "{:,.1f}"}),
                     "R3 reformulado: mide ASOCIACIÓN. La huella NO incluye emisiones del vehículo (la ECV solo dice si lo hay)."))

    dep = df.groupby("nombre_departamento").agg(hogares=("sk_fact", "count"), total=("huella_total_anual_kg", "sum"),
                                               personas=("num_personas", "sum")).reset_index()
    dep["per_capita"] = dep.total / dep.personas
    dep = dep.sort_values("per_capita", ascending=False)
    s.append(section("R4", "Huella per cápita por departamento",
                     "¿Qué departamentos tienen mayor huella residencial por persona?",
                     bars(dep.head(15).apply(lambda r: (r.nombre_departamento, r.per_capita), axis=1), " kg/persona"),
                     table(dep.head(15)[["nombre_departamento", "hogares", "per_capita"]].rename(
                         columns={"per_capita": "kg CO₂/persona/año"}),
                         {"hogares": "{:,.0f}", "kg CO₂/persona/año": "{:,.1f}"}),
                     "Se muestran los 15 primeros de 33. Mapa coroplético: pendiente en la herramienta de BI."))

    df5 = df.assign(tam=df.num_personas.clip(upper=6))
    r5 = df5.groupby("tam").agg(hogares=("sk_fact", "count"), total=("huella_total_anual_kg", "sum"),
                                personas=("num_personas", "sum")).reset_index()
    r5["pc"] = r5.total / r5.personas
    s.append(section("R5", "Huella per cápita según tamaño del hogar",
                     "¿Los hogares más grandes emiten menos por persona?",
                     bars([(f"{int(r.tam)}{'+' if r.tam == 6 else ''} personas", r.pc) for r in r5.itertuples()], " kg/persona"),
                     table(r5[["tam", "hogares", "pc"]].rename(columns={"tam": "personas (6 = 6 o más)", "pc": "kg CO₂/persona/año"}),
                           {"hogares": "{:,.0f}", "kg CO₂/persona/año": "{:,.1f}"})))

    cl = df[df.clima_emparejado == 1]
    r6 = cl.groupby("piso_termico").agg(hogares=("sk_fact", "count"), kwh=("kwh_consumidos_estimados", "mean"),
                                        co2=("emisiones_energia_kg", "mean"), temp=("temp_media_c", "mean")).reset_index()
    r6["o"] = r6.piso_termico.map({p: i for i, p in enumerate(PISO_ORDER)})
    r6 = r6.sort_values("o").drop(columns="o")
    s.append(section("R6", "Consumo eléctrico según piso térmico (API IDEAM)",
                     "¿Los hogares de departamentos cálidos consumen más kWh y emiten más CO₂ eléctrico?",
                     bars([(r.piso_termico, r.kwh) for r in r6.itertuples()], " kWh/mes"),
                     table(r6.rename(columns={"kwh": "kWh/mes (media)", "co2": "kg CO₂/año (media)", "temp": "°C (media)"}),
                           {"hogares": "{:,.0f}", "kWh/mes (media)": "{:,.1f}", "kg CO₂/año (media)": "{:,.1f}", "°C (media)": "{:,.1f}"}),
                     "Asociación entre 33 departamentos; no prueba causalidad. Cortes de piso térmico: convención por confirmar (S14)."))

    r7 = cl.groupby("piso_termico").agg(hogares=("sk_fact", "count"),
                                        p11=("bien_p1077s11", lambda x: 100 * (x == "Sí").mean()),
                                        p12=("bien_p1077s12", lambda x: 100 * (x == "Sí").mean())).reset_index()
    r7["o"] = r7.piso_termico.map({p: i for i, p in enumerate(PISO_ORDER)})
    r7 = r7.sort_values("o").drop(columns="o")
    s.append(section("R7", "Hogares con aire acondicionado y con ventilador según piso térmico (API IDEAM)",
                     "¿Sube la tenencia de estos equipos con la temperatura?",
                     bars([(f"{r.piso_termico} · aire acondicionado", r.p11) for r in r7.itertuples()] +
                          [(f"{r.piso_termico} · ventilador", r.p12) for r in r7.itertuples()], " %"),
                     table(r7.rename(columns={"p11": "% con aire acondicionado", "p12": "% con ventilador"}),
                           {"hogares": "{:,.0f}", "% con aire acondicionado": "{:.1f}", "% con ventilador": "{:.1f}"}),
                     "P1077S11 = aire acondicionado y P1077S12 = ventilador o abanico (diccionario DANE ECV 2025). Asociación, no causalidad."))

    api = d["dim_clima"][["nombre_departamento", "temp_media_c", "n_estaciones", "n_lecturas", "piso_termico"]]
    s.append(section("API", "Cobertura de la API del IDEAM",
                     "¿Qué temperatura y cuántas estaciones tiene cada departamento?", "",
                     table(api.sort_values("temp_media_c", ascending=False),
                           {"temp_media_c": "{:.1f}", "n_estaciones": "{:,.0f}", "n_lecturas": "{:,.0f}"})))
    return s


CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--bar:#2f7d5b;--line:#ddd;--card:#f7f7f5}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--mut:#aaa;--bar:#5cc79a;--line:#333;--card:#202020}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:980px;margin:0 auto;padding:16px}
h1{font-size:24px;margin:8px 0}h2{font-size:18px;margin:0 0 4px}h2 span{color:var(--bar);margin-right:6px}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}
.q{margin:0 0 8px;color:var(--mut)}.note{color:var(--mut);font-size:13px}.muted{color:var(--mut)}
.kpis{display:flex;flex-wrap:wrap;gap:12px}.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 16px}
.kpi b{display:block;font-size:22px}.src{font-size:13px;color:var(--mut);margin-bottom:8px}
svg{width:100%;height:auto;margin:8px 0}.lbl,.val{font-size:12px;fill:var(--fg)}.bar{fill:var(--bar)}
table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}th,td{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right}
th:first-child,td:first-child{text-align:left}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-csv", action="store_true", help="solo desarrollo: usar CSV si no hay MySQL")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        data, source = fetch_from_mysql()
    except Exception as exc:
        if not args.allow_csv:
            raise SystemExit(f"No se pudo consultar el Data Warehouse MySQL: {exc}\n"
                             "El dashboard debe consultar MySQL. Use --allow-csv solo para desarrollo.")
        log.warning("MySQL no disponible (%s). Usando CSV preparados.", exc)
        data, source = fetch_from_csv()

    df = build_frame(data)
    kpis = [("Hogares", f"{len(df):,}"), ("kWh/mes (media)", f"{df.kwh_consumidos_estimados.mean():,.1f}"),
            ("kg CO₂/año (media)", f"{df.huella_total_anual_kg.mean():,.0f}"),
            ("Hogares con clima de la API", f"{100 * (df.clima_emparejado == 1).mean():.1f} %")]
    page = (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Huella de carbono residencial</title><style>{CSS}</style></head><body>"
            f"<h1>Huella de carbono residencial · ECV 2025 + temperatura IDEAM</h1>"
            f"<p class='src'>Fuente: {html.escape(source)} · generado {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC</p>"
            f"<div class='kpis'>{''.join(f'<div class=kpi><b>{v}</b>{k}</div>' for k, v in kpis)}</div>"
            f"{''.join(compute(df, data))}</body></html>")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    log.info("Dashboard escrito en %s (fuente: %s)", OUT, source)


if __name__ == "__main__":
    main()
