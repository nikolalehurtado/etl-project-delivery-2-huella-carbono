-- =========================================================================
-- PROYECTO: ETL Segunda Entrega — Huella de Carbono en Hogares Colombianos (ODS 12)
-- ARCHIVO : sql/analytical_queries.sql
-- MOTOR   : MySQL 8.0 (Data Warehouse: huella_carbono_dw_v2)
-- AUTORES : Nikol Hurtado, David Aponte, Diana Panesso, Sebastián Celorio
-- DESCRIPCIÓN: Consultas analíticas SQL para responder de extremo a extremo
--              los requisitos R1 a R7 directamente contra el Data Warehouse.
-- =========================================================================

-- -------------------------------------------------------------------------
-- R1: Huella Eléctrica por Estrato Socioeconómico y Piso Térmico
-- Pregunta analítica: ¿Cuál es el consumo promedio mensual de kWh y la
-- huella de carbono eléctrica anual según el estrato socioeconómico?
-- -------------------------------------------------------------------------
SELECT 
    u.estrato,
    COUNT(f.sk_fact) AS total_hogares,
    ROUND(AVG(f.kwh_consumidos_estimados), 2) AS avg_kwh_mensual,
    ROUND(AVG(f.emisiones_energia_kg), 2) AS avg_co2_electrico_anual_kg,
    ROUND(SUM(f.emisiones_energia_kg) / 1000.0, 2) AS total_emisiones_electricas_ton
FROM 
    fact_huella_carbono f
JOIN 
    dim_ubicacion u ON f.fk_ubicacion = u.sk_ubicacion
GROUP BY 
    u.estrato
ORDER BY 
    u.estrato ASC;


-- -------------------------------------------------------------------------
-- R2: Emisiones por Combustible de Cocción
-- Pregunta analítica: ¿Cómo varían las emisiones de cocción según el tipo
-- de combustible utilizado (gas natural, GLP o leña) por departamento?
-- -------------------------------------------------------------------------
SELECT 
    u.nombre_departamento,
    c.tipo_combustible,
    COUNT(f.sk_fact) AS total_hogares,
    ROUND(SUM(f.emisiones_coccion_kg) / 1000.0, 2) AS total_emisiones_coccion_ton,
    ROUND(AVG(f.emisiones_coccion_kg), 2) AS avg_emisiones_hogar_coccion_kg
FROM 
    fact_huella_carbono f
JOIN 
    dim_ubicacion u ON f.fk_ubicacion = u.sk_ubicacion
JOIN 
    dim_combustibles c ON f.fk_combustible_cocina = c.sk_combustible
GROUP BY 
    u.nombre_departamento, 
    c.tipo_combustible
ORDER BY 
    total_emisiones_coccion_ton DESC;


-- -------------------------------------------------------------------------
-- R3: Brecha en la Huella Residencial según Tenencia de Vehículo Particular
-- REFORMULACIÓN EXPLÍCITA (Retroalimentación Docente):
-- La ECV DANE (P1077S15) registra la tenencia del activo (Sí/No), no el gasto
-- ni kilometraje en transporte. R3 evalúa la diferencia en la huella
-- residencial total (energía + cocción) entre hogares con y sin vehículo
-- controlando por estrato socioeconómico.
-- -------------------------------------------------------------------------
SELECT 
    u.estrato,
    h.tiene_vehiculo,
    COUNT(f.sk_fact) AS total_hogares,
    ROUND(AVG(f.kwh_consumidos_estimados), 2) AS avg_kwh_mes,
    ROUND(AVG(f.huella_total_anual_kg), 2) AS avg_huella_residencial_anual_kg,
    ROUND(STDDEV(f.huella_total_anual_kg), 2) AS desv_huella_residencial_kg
FROM 
    fact_huella_carbono f
JOIN 
    dim_hogar h ON f.fk_hogar = h.sk_hogar
JOIN 
    dim_ubicacion u ON f.fk_ubicacion = u.sk_ubicacion
GROUP BY 
    u.estrato,
    h.tiene_vehiculo
ORDER BY 
    u.estrato ASC, 
    h.tiene_vehiculo DESC;


-- -------------------------------------------------------------------------
-- R4: Priorización Geográfica Departamental (Huella Total y Per Cápita)
-- Pregunta analítica: ¿Cuáles departamentos presentan la mayor huella de
-- carbono residencial per cápita y acumulada?
-- -------------------------------------------------------------------------
SELECT 
    u.nombre_departamento,
    COUNT(f.sk_fact) AS total_hogares,
    SUM(h.num_personas) AS total_poblacion_muestral,
    ROUND(SUM(f.huella_total_anual_kg) / SUM(h.num_personas), 2) AS huella_per_capita_anual_kg,
    ROUND(SUM(f.huella_total_anual_kg) / 1000.0, 2) AS huella_total_departamental_ton
FROM 
    fact_huella_carbono f
JOIN 
    dim_ubicacion u ON f.fk_ubicacion = u.sk_ubicacion
JOIN 
    dim_hogar h ON f.fk_hogar = h.sk_hogar
GROUP BY 
    u.nombre_departamento
ORDER BY 
    huella_per_capita_anual_kg DESC;


-- -------------------------------------------------------------------------
-- R5: Eficiencia por Tamaño del Hogar (Economías de Escala Residenciales)
-- Pregunta analítica: ¿Existe una relación inversa entre el número de
-- integrantes del hogar y la emisión per cápita (eficiencia energética)?
-- -------------------------------------------------------------------------
SELECT 
    h.num_personas AS integrantes_hogar,
    COUNT(f.sk_fact) AS total_hogares,
    ROUND(AVG(f.huella_total_anual_kg), 2) AS avg_huella_hogar_kg,
    ROUND(AVG(f.huella_total_anual_kg / h.num_personas), 2) AS avg_huella_per_capita_kg
FROM 
    fact_huella_carbono f
JOIN 
    dim_hogar h ON f.fk_hogar = h.sk_hogar
WHERE 
    h.num_personas <= 8 -- Filtro para evitar distorsión de outliers extremos
GROUP BY 
    h.num_personas
ORDER BY 
    h.num_personas ASC;


-- =========================================================================
-- REQUISITOS INTEGRADOS CON LA API DEL IDEAM (R6 y R7)
-- =========================================================================

-- -------------------------------------------------------------------------
-- R6: Comparación de Consumo Eléctrico según Piso Térmico Oficial (IDEAM)
-- Pregunta analítica: ¿Cuántos kWh/mes y kg CO₂ eléctrico más generan los
-- hogares en departamentos cálidos (>24°C) que en templados o fríos, a igual estrato?
-- Demuestra el valor analítico de integrar la API de temperatura oficial.
-- -------------------------------------------------------------------------
SELECT 
    u.estrato,
    c.piso_termico,
    ROUND(AVG(c.temp_media_c), 2) AS temp_promedio_c,
    COUNT(f.sk_fact) AS total_hogares,
    ROUND(AVG(f.kwh_consumidos_estimados), 2) AS avg_kwh_mensual,
    ROUND(AVG(f.emisiones_energia_kg), 2) AS avg_co2_electrico_anual_kg
FROM 
    fact_huella_carbono f
JOIN 
    dim_ubicacion u ON f.fk_ubicacion = u.sk_ubicacion
JOIN 
    dim_clima c ON f.fk_clima = c.sk_clima
WHERE 
    f.clima_emparejado = 1
GROUP BY 
    u.estrato, 
    c.piso_termico
ORDER BY 
    u.estrato ASC, 
    avg_kwh_mensual DESC;


-- -------------------------------------------------------------------------
-- R7: Tenencia de Equipos de Climatización vs. Temperatura Departamental
-- Pregunta analítica: ¿El porcentaje de hogares con equipos de refrigeración/aire
-- aumenta con la temperatura del departamento, y cuál es el impacto en su huella eléctrica?
-- -------------------------------------------------------------------------
SELECT 
    c.nombre_departamento,
    c.temp_media_c,
    c.piso_termico,
    COUNT(f.sk_fact) AS total_hogares,
    ROUND(100.0 * SUM(CASE WHEN h.bien_p1077s11 = 'Sí' THEN 1 ELSE 0 END) / COUNT(f.sk_fact), 2) AS pct_hogares_equipo_clima_11,
    ROUND(100.0 * SUM(CASE WHEN h.bien_p1077s12 = 'Sí' THEN 1 ELSE 0 END) / COUNT(f.sk_fact), 2) AS pct_hogares_equipo_clima_12,
    ROUND(AVG(f.kwh_consumidos_estimados), 2) AS avg_kwh_mensual,
    ROUND(AVG(f.emisiones_energia_kg), 2) AS avg_co2_electrico_kg
FROM 
    fact_huella_carbono f
JOIN 
    dim_clima c ON f.fk_clima = c.sk_clima
JOIN 
    dim_hogar h ON f.fk_hogar = h.sk_hogar
WHERE 
    f.clima_emparejado = 1
GROUP BY 
    c.nombre_departamento, 
    c.temp_media_c, 
    c.piso_termico
ORDER BY 
    c.temp_media_c DESC;
