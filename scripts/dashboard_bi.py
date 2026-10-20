"""
DASHBOARD BI — Generador de Tablero Analítico y Reporte de Salidas R1-R7.

Responsable: Persona 4 (Analítica, dashboard y documentación).

Consulta directamente el Data Warehouse MySQL (huella_carbono_dw_v2) o los
datos preparados como respaldo, calculando los KPIs y generando el dashboard
interactivo con estética visual premium en docs/evidence/dashboard_bi.html.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src import config
from src.db import sqlalchemy_engine

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def fetch_data():
    """Consulta el Data Warehouse MySQL o carga datos preparados si DW está offline."""
    try:
        engine = sqlalchemy_engine()
        with engine.connect() as conn:
            log.info("Conectado exitosamente al Data Warehouse MySQL (huella_carbono_dw_v2).")
            hogar = pd.read_sql("SELECT * FROM dim_hogar", conn)
            ubi = pd.read_sql("SELECT * FROM dim_ubicacion", conn)
            clima = pd.read_sql("SELECT * FROM dim_clima", conn)
            comb = pd.read_sql("SELECT * FROM dim_combustibles", conn)
            fact = pd.read_sql("SELECT * FROM fact_huella_carbono", conn)
            source = "MySQL DW (localhost:3307)"
    except Exception as exc:
        log.warning("No se pudo conectar a MySQL (%s). Usando archivos preparados más recientes como respaldo.", exc)
        # Buscar en data/work/*/prepared
        prepared_dirs = list((config.DATA_DIR / "work").glob("*/prepared"))
        if not prepared_dirs:
            raise RuntimeError("No se encontró base de datos MySQL ni archivos preparados en data/work/*/prepared")
        latest = sorted(prepared_dirs)[-1]
        log.info("Cargando datos preparados desde %s", latest)
        hogar = pd.read_csv(latest / "dim_hogar.csv")
        ubi = pd.read_csv(latest / "dim_ubicacion.csv")
        clima = pd.read_csv(latest / "dim_clima.csv")
        comb = pd.read_csv(latest / "dim_combustibles.csv")
        fact = pd.read_csv(latest / "fact_huella_carbono.csv")
        source = f"Archivos preparados ({latest.name})"

    return {"fact": fact, "hogar": hogar, "ubi": ubi, "clima": clima, "comb": comb, "source": source}


def generate_dashboard_html(data, output_path):
    fact = data["fact"]
    hogar = data["hogar"]
    ubi = data["ubi"]
    clima = data["clima"]
    comb = data["comb"]

    # Cruces para métricas
    df = fact.merge(ubi, left_on="fk_ubicacion", right_on="sk_ubicacion", how="left")
    df = df.merge(hogar, left_on="fk_hogar", right_on="sk_hogar", how="left")
    df = df.merge(clima, left_on="fk_clima", right_on="sk_clima", how="left", suffixes=("", "_clima"))
    df = df.merge(comb, left_on="fk_combustible_cocina", right_on="sk_combustible", how="left")

    total_hogares = len(df)
    avg_huella_total = round(df["huella_total_anual_kg"].mean(), 2)
    avg_kwh = round(df["kwh_consumidos_estimados"].mean(), 2)
    pct_con_clima = round(100.0 * (df["clima_emparejado"] == 1).mean(), 2)

    # R1: Consumo y huella eléctrica por estrato
    r1 = df.groupby("estrato").agg(
        hogares=("sk_fact", "count"),
        avg_kwh=("kwh_consumidos_estimados", "mean"),
        avg_co2=("emisiones_energia_kg", "mean"),
    ).reset_index()

    # R2: Combustibles de cocción
    r2 = df.groupby("tipo_combustible").agg(
        hogares=("sk_fact", "count"),
        total_co2_ton=("emisiones_coccion_kg", lambda x: round(x.sum() / 1000.0, 2)),
        avg_co2_kg=("emisiones_coccion_kg", "mean"),
    ).reset_index()

    # R3: Brecha vehicular residencial
    r3 = df.groupby(["estrato", "tiene_vehiculo"]).agg(
        hogares=("sk_fact", "count"),
        avg_huella=("huella_total_anual_kg", "mean"),
        avg_kwh=("kwh_consumidos_estimados", "mean"),
    ).reset_index()

    # R6: Piso térmico vs Consumo eléctrico
    r6 = df[df["clima_emparejado"] == 1].groupby(["piso_termico", "estrato"]).agg(
        hogares=("sk_fact", "count"),
        avg_kwh=("kwh_consumidos_estimados", "mean"),
        avg_co2=("emisiones_energia_kg", "mean"),
    ).reset_index()

    # R7: Equipamiento refrigeración vs Piso térmico
    r7 = df[df["clima_emparejado"] == 1].groupby("piso_termico").agg(
        hogares=("sk_fact", "count"),
        pct_aire=("bien_p1077s11", lambda x: round(100.0 * (x == "Sí").mean(), 2)),
        pct_ventilador=("bien_p1077s12", lambda x: round(100.0 * (x == "Sí").mean(), 2)),
        avg_kwh=("kwh_consumidos_estimados", "mean"),
    ).reset_index()

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard BI — Huella de Carbono Residencial (ODS 12)</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --surface-hover: #334155;
            --primary: #10b981;
            --primary-glow: rgba(16, 185, 129, 0.2);
            --accent: #38bdf8;
            --warning: #f59e0b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; }}
        body {{ background: var(--bg); color: var(--text-main); padding: 24px; min-height: 100vh; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; padding-bottom: 24px; border-bottom: 1px solid var(--border); margin-bottom: 24px; }}
        .header h1 {{ font-size: 24px; font-weight: 700; color: #fff; }}
        .header p {{ color: var(--text-muted); font-size: 14px; }}
        .badge {{ background: var(--primary-glow); color: var(--primary); padding: 6px 12px; border-radius: 9999px; font-size: 12px; font-weight: 600; border: 1px solid var(--primary); }}
        
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 28px; }}
        .kpi-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; transition: transform 0.2s; }}
        .kpi-card:hover {{ transform: translateY(-2px); }}
        .kpi-label {{ font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 8px; }}
        .kpi-val {{ font-size: 28px; font-weight: 700; color: var(--text-main); }}
        .kpi-sub {{ font-size: 12px; color: var(--accent); margin-top: 4px; }}
        
        .section-title {{ font-size: 18px; font-weight: 600; margin: 24px 0 16px; color: var(--accent); display: flex; align-items: center; gap: 8px; }}
        .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap: 20px; margin-bottom: 24px; }}
        .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }}
        .card h3 {{ font-size: 15px; margin-bottom: 14px; color: #fff; font-weight: 600; }}
        
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        th {{ text-align: left; padding: 10px; background: rgba(0,0,0,0.2); color: var(--text-muted); border-bottom: 1px solid var(--border); }}
        td {{ padding: 10px; border-bottom: 1px solid var(--border); }}
        tr:hover td {{ background: var(--surface-hover); }}
        .num {{ text-align: right; }}
        .tag-calido {{ color: #f87171; font-weight: 600; }}
        .tag-templado {{ color: #fbbf24; font-weight: 600; }}
        .tag-frio {{ color: #38bdf8; font-weight: 600; }}
        
        .footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border); text-align: center; font-size: 12px; color: var(--text-muted); }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Tablero Analítico BI — Huella de Carbono (ODS 12)</h1>
            <p>Integración ECV 2025 (DANE) + Temperatura Oficial IDEAM (API SODA) · Segunda Entrega UAO</p>
        </div>
        <div>
            <span class="badge">Origen: {data["source"]}</span>
        </div>
    </div>

    <!-- KPIs Principales -->
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-label">Hogares Analizados</div>
            <div class="kpi-val">{total_hogares:,}</div>
            <div class="kpi-sub">Muestra representativa DANE</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Huella Residencial Media</div>
            <div class="kpi-val">{avg_huella_total} <span style="font-size:16px;">kg CO₂/año</span></div>
            <div class="kpi-sub">Electricidad + Cocción</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Consumo Eléctrico Promedio</div>
            <div class="kpi-val">{avg_kwh} <span style="font-size:16px;">kWh/mes</span></div>
            <div class="kpi-sub">Estimado según tarifa CREG</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-label">Integración Clima (IDEAM)</div>
            <div class="kpi-val">{pct_con_clima}%</div>
            <div class="kpi-sub">Hogares cruzados con éxito</div>
        </div>
    </div>

    <!-- R1 y R2 -->
    <div class="section-title">📊 Línea Base y Consumo Residencial (R1 y R2)</div>
    <div class="grid-2">
        <div class="card">
            <h3>R1: Huella Eléctrica por Estrato Socioeconómico</h3>
            <table>
                <thead>
                    <tr><th>Estrato</th><th class="num">Hogares</th><th class="num">kWh/mes Prom.</th><th class="num">kg CO₂ Eléctrico/año</th></tr>
                </thead>
                <tbody>
                    {"".join(f"<tr><td>Estrato {int(r.estrato)}</td><td class='num'>{int(r.hogares):,}</td><td class='num'>{r.avg_kwh:.1f}</td><td class='num'>{r.avg_co2:.1f}</td></tr>" for _, r in r1.iterrows())}
                </tbody>
            </table>
        </div>
        <div class="card">
            <h3>R2: Emisiones por Combustible de Cocción</h3>
            <table>
                <thead>
                    <tr><th>Combustible</th><th class="num">Hogares</th><th class="num">kg CO₂/Hogar</th><th class="num">Total Ton CO₂</th></tr>
                </thead>
                <tbody>
                    {"".join(f"<tr><td>{r.tipo_combustible}</td><td class='num'>{int(r.hogares):,}</td><td class='num'>{r.avg_co2_kg:.1f}</td><td class='num'>{r.total_co2_ton:,.1f}</td></tr>" for _, r in r2.iterrows())}
                </tbody>
            </table>
        </div>
    </div>

    <!-- R3 Reformulado -->
    <div class="section-title">🚗 R3 (Reformulado): Brecha en Huella Residencial según Tenencia de Vehículo Particular</div>
    <div class="card" style="margin-bottom: 24px;">
        <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 12px;">
            <strong>Nota metodológica:</strong> La ECV DANE indaga la tenencia del bien (P1077S15: Sí/No), no el combustible vehicular.
            Esta tabla compara la huella residencial (luz y gas) de los hogares propietarios de vehículo vs no propietarios a igual estrato socioeconómico.
        </p>
        <table>
            <thead>
                <tr><th>Estrato</th><th>¿Posee Vehículo?</th><th class="num">Hogares</th><th class="num">Consumo kWh/mes</th><th class="num">Huella Total Anual (kg CO₂)</th></tr>
            </thead>
            <tbody>
                {"".join(f"<tr><td>Estrato {int(r.estrato)}</td><td><span style='color:{'#10b981' if r.tiene_vehiculo=='Sí' else '#94a3b8'}'>{r.tiene_vehiculo}</span></td><td class='num'>{int(r.hogares):,}</td><td class='num'>{r.avg_kwh:.1f}</td><td class='num'>{r.avg_huella:.1f}</td></tr>" for _, r in r3.iterrows())}
            </tbody>
        </table>
    </div>

    <!-- R6 y R7 (Integración API IDEAM) -->
    <div class="section-title">🌡️ Requisitos Integrados con la API del IDEAM (R6 y R7)</div>
    <div class="grid-2">
        <div class="card">
            <h3>R6: Impacto del Piso Térmico en el Consumo Eléctrico</h3>
            <table>
                <thead>
                    <tr><th>Piso Térmico</th><th>Estrato</th><th class="num">Hogares</th><th class="num">kWh/mes</th><th class="num">kg CO₂/año</th></tr>
                </thead>
                <tbody>
                    {"".join(f"<tr><td class='tag-{r.piso_termico.lower()}'>{r.piso_termico}</td><td>Estrato {int(r.estrato)}</td><td class='num'>{int(r.hogares):,}</td><td class='num'>{r.avg_kwh:.1f}</td><td class='num'>{r.avg_co2:.1f}</td></tr>" for _, r in r6.head(9).iterrows())}
                </tbody>
            </table>
        </div>
        <div class="card">
            <h3>R7: Tenencia de Equipos de Climatización por Piso Térmico</h3>
            <table>
                <thead>
                    <tr><th>Piso Térmico</th><th class="num">% Aire Acondicionado</th><th class="num">% Ventilador</th><th class="num">Consumo Medio kWh</th></tr>
                </thead>
                <tbody>
                    {"".join(f"<tr><td class='tag-{r.piso_termico.lower()}'>{r.piso_termico}</td><td class='num'>{r.pct_aire}%</td><td class='num'>{r.pct_ventilador}%</td><td class='num'>{r.avg_kwh:.1f}</td></tr>" for _, r in r7.iterrows())}
                </tbody>
            </table>
        </div>
    </div>

    <div class="footer">
        Generado automáticamente por el Pipeline ETL · Data Warehouse MySQL: huella_carbono_dw_v2 · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
    </div>
</body>
</html>
"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    log.info("Dashboard HTML guardado exitosamente en %s", output_path)


if __name__ == "__main__":
    out_file = config.PROJECT_ROOT / "docs" / "evidence" / "dashboard_bi.html"
    try:
        data = fetch_data()
        generate_dashboard_html(data, out_file)
    except Exception as e:
        log.error("Error generando dashboard: %s", e)
