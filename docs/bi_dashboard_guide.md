# Guía de Conexión del Dashboard BI al Data Warehouse MySQL

Esta guía detalla el procedimiento para conectar herramientas de Business Intelligence (Power BI Desktop, Metabase, Tableau o Streamlit) al Data Warehouse dimensional (`huella_carbono_dw_v2`) y responder a los requisitos **R1 a R7**.

---

## 1. Parámetros de Conexión

* **Motor:** MySQL 8.0
* **Host:** `localhost` (o `127.0.0.1`)
* **Puerto:** `3307` (mapeado en `docker-compose.yaml` al puerto interno 3306)
* **Base de datos:** `huella_carbono_dw_v2`
* **Usuario:** Variable `MYSQL_USER` de su archivo `.env`
* **Contraseña:** Variable `MYSQL_PASSWORD` de su archivo `.env`

---

## 2. Conexión desde Power BI Desktop

1. Abrir **Power BI Desktop**.
2. Seleccionar **Obtener Datos** $\rightarrow$ **Base de datos MySQL**.
3. En Servidor ingresar: `localhost:3307`.
4. En Base de datos ingresar: `huella_carbono_dw_v2`.
5. En Modo de conectividad de datos: Seleccionar **Importar** o **DirectQuery**.
6. Seleccionar las 6 tablas del Star Schema:
   * `dim_ubicacion`
   * `dim_hogar`
   * `dim_clima`
   * `dim_combustibles`
   * `dim_tarifas`
   * `fact_huella_carbono`
7. Verificar que las relaciones activas en el modelo coincidan con el diagrama estrella:
   * `fact_huella_carbono.fk_ubicacion` $\rightarrow$ `dim_ubicacion.sk_ubicacion` (1:*).
   * `fact_huella_carbono.fk_hogar` $\rightarrow$ `dim_hogar.sk_hogar` (1:*).
   * `fact_huella_carbono.fk_clima` $\rightarrow$ `dim_clima.sk_clima` (1:*).
   * `fact_huella_carbono.fk_combustible_cocina` $\rightarrow$ `dim_combustibles.sk_combustible` (1:*).
   * `fact_huella_carbono.fk_tarifa_energia` $\rightarrow$ `dim_tarifas.sk_tarifa` (1:*).

---

## 3. Matriz de Visualizaciones Recomendadas

| Requisito | Tipo de Visualización | Ejes / Campos | KPI Principal |
|---|---|---|---|
| **R1** | Gráfico de columnas agrupadas | Eje X: `dim_ubicacion.estrato`<br>Valores: `AVG(kwh_consumidos_estimados)` | Consumo medio mensual (kWh) y huella eléctrica (kg CO₂) |
| **R2** | Treemap o Gráfico de anillos | Categoría: `dim_combustibles.tipo_combustible`<br>Valores: `SUM(emisiones_coccion_kg)` | Total toneladas CO₂ por combustible de cocción |
| **R3 (Reformulado)** | Gráfico de barras combinadas | Eje X: `dim_ubicacion.estrato`<br>Leyenda: `dim_hogar.tiene_vehiculo`<br>Valores: `AVG(huella_total_anual_kg)` | Brecha en huella residencial según tenencia de carro particular |
| **R4** | Barras horizontales ordenadas (alternativa: mapa coroplético si Power BI reconoce los nombres de departamento) | Eje: `dim_ubicacion.nombre_departamento`<br>Valor: huella per cápita = `SUM(huella_total_anual_kg) / SUM(num_personas)` | Emisiones per cápita por departamento |
| **R5** | Gráfico de líneas | Eje X: `dim_hogar.num_personas`<br>Valores: `AVG(huella_total_anual_kg / num_personas)` | Curva de economías de escala residenciales |
| **R6 (API IDEAM)** | Gráfico de dispersión o columnas | Eje X: `dim_clima.temp_media_c`<br>Eje Y: `AVG(kwh_consumidos_estimados)`<br>Segmentación: `dim_clima.piso_termico` | Sobreconsumo eléctrico atribuible a pisos térmicos cálidos |
| **R7 (API IDEAM)** | Gráfico de dispersión con línea de tendencia | Eje X: `dim_clima.temp_media_c`<br>Eje Y: `% Hogares con aire acondicionado (bien_p1077s11)`; segunda serie: `% con ventilador (bien_p1077s12)` | Adopción de tecnologías de enfriamiento vs. temperatura |

---

## 3.1 Páginas del informe y capturas para la evidencia

* **Página 1 — Huella residencial (R1 a R5):** tarjetas de hogares, huella media y emisión eléctrica media; gráficas de R1 a R5; filtros de estrato y departamento. Captura: `docs/evidence/dashboard_p1_huella_residencial.png`.
* **Página 2 — Valor de la API (R6 y R7):** tarjetas de hogares con clima emparejado, kWh cálido contra frío y diferencia de CO₂; gráficas de R6 y R7; filtros de departamento y piso térmico. Captura: `docs/evidence/dashboard_p2_api_clima.png`.
* **Conexión:** captura del servidor `localhost:3307` y la base `huella_carbono_dw_v2` con las seis tablas seleccionadas: `docs/evidence/dashboard_conexion_mysql.png`.
* Guardar el informe como `dashboard/huella_carbono.pbix`.

## 4. Visualización Alternativa Autónoma (HTML/Web)

Si no dispone de Power BI en su entorno local, puede generar y visualizar el dashboard interactivo de forma inmediata ejecutando:

```bash
python scripts/dashboard_bi.py
```

El reporte se generará automáticamente en `docs/evidence/dashboard_bi.html` con todos los cálculos y tablas agregadas.
