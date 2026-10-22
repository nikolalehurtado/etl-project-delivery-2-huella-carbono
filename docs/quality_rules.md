# Reglas de Calidad — Huella de Carbono en Hogares Colombianos (ECV 2025 + API IDEAM)

**Responsable:** David Aponte (Persona 2 — API y Calidad de Datos)  
**Referencia al enunciado:** Secciones 8 y 9. Cada umbral tiene su base analítica, contractual o
histórica. Los umbrales anteriormente marcados PROVISIONAL han sido calibrados con el perfilamiento
documentado en `notebooks/01_perfilamiento_ecv_primaria.ipynb` y `notebooks/02_perfilamiento_api_ideam.ipynb`.

Las reglas están implementadas en `src/validation.py`. Cada `Expectation` lleva su `rule_id` en `meta`.

---

## Compuerta 1 — Datos Crudos ECV 2025 (raw)

| ID | Fuente / capa | Atributo(s) | Dimensión | Regla | Métrica / umbral | Severidad | Req. | Base del umbral |
|----|---------------|-------------|-----------|-------|------------------|-----------|------|-----------------|
| DQ01 | ECV servicios (raw) | columnas requeridas | Validez (contrato) | Están todas las columnas requeridas (`DIRECTORIO`, `SECUENCIA_P`, `P5018`, `P5010`, `P8536`, `P8540`, `P3163`) | 100% | Critical | R1–R5 | Contrato de la fuente: si falta una columna el pipeline no puede ejecutarse |
| DQ02 | ECV servicios (raw) | `DIRECTORIO`, `SECUENCIA_P` | Completitud | Sin nulos: son las llaves del grano de la tabla de hechos | 100% | Critical | R1–R7 | Sin llaves, el hogar no puede cruzarse con ninguna dimensión ni cargarse al DW |
| DQ03 | ECV servicios (raw) | `DIRECTORIO` + `SECUENCIA_P` | Unicidad | Un hogar por fila | ≥ 99% | Warning | R1–R7 | **Empírico:** fase 1 eliminó 212 duplicados en 88,432 filas (0.24%). Umbral 99%: >1% indica error de carga del CSV |
| DQ04 | ECV servicios (raw) | `P5018` (gasto electricidad) | Completitud | Pago de luz informado | ≥ 70% | Warning | R1, R6 | **Analítico:** fase 1 observó ~77%. Con <70%, la imputación domina el KPI eléctrico (R1, R6) |
| DQ05 | ECV servicios (raw) | `P5010` (estrato) | Validez | Estrato entre 1 y 6 | ≥ 99.9% | Warning | R1, R6 | **Empírico:** fase 1 registró 12 hogares con código 7/8 en 88,432 (0.014%). Estratos 7/8 = no residenciales |
| DQ06 | ECV vivienda (raw) | columnas requeridas | Validez (contrato) | Están todas las columnas (`DIRECTORIO`, `SECUENCIA_P`, `P1_DEPARTAMENTO`, `P1_MUNICIPIO`) | 100% | Critical | R4, R6, R7 | Contrato de la fuente |
| DQ07 | ECV vivienda (raw) | `P1_DEPARTAMENTO` | Completitud | Sin nulos: es la llave de integración ECV–API | 100% | Critical | R6, R7 | Nulo = hogar sin llave de cruce → sin temperatura → R6/R7 imposibles para ese hogar |
| DQ08 | ECV vivienda (raw) | `P1_DEPARTAMENTO` | Validez | Código DIVIPOLA válido (33 departamentos según `data/reference/dane_departamentos.csv`) | 100% | Critical | R6, R7 | **Contractual:** código inválido → JOIN incorrecto → KPIs climáticos contaminados |
| DQ09 | ECV características (raw) | `DIRECTORIO`, `SECUENCIA_P` | Completitud | Sin nulos en las llaves del hogar | 100% | Critical | R5 | Sin llaves, el group-count de personas por hogar es imposible → `dim_hogar.num_personas` nulo |
| DQ10 | ECV condiciones (raw) | `P1077S15` (carro particular) | Validez | Dominio `{1, 2}` | 100% | Critical | R3 | **Contractual (diccionario DANE):** 1=Sí, 2=No. Cualquier otro código = error de codificación DANE |
| DQ11 | ECV condiciones (raw) | `P1077S11`, `P1077S12` | Validez | Dominio `{1, 2}` | 100% | Warning | R7 | Warning porque alimenta solo R7 (P1077S11 = aire acondicionado, P1077S12 = ventilador o abanico, según el diccionario DANE ECV 2025); un valor fuera de dominio afecta ese requisito, no todo el análisis |

---

## Compuerta 2 — Datos Crudos API IDEAM (raw)

| ID | Fuente / capa | Atributo(s) | Dimensión | Regla | Métrica / umbral | Severidad | Req. | Base del umbral |
|----|---------------|-------------|-----------|-------|------------------|-----------|------|-----------------|
| DQ12 | API IDEAM (raw) | columnas de la consulta | Validez (contrato) | Están todas las columnas de la respuesta SODA (`codigoestacion`, `nombreestacion`, `departamento`, `municipio`, `latitud`, `longitud`, `suma`, `n`, `minimo`, `maximo`, `window_start`, `window_end`) | 100% | Critical | R6, R7 | Cambio de esquema en la API = error determinístico; no se reintenta |
| DQ13 | API IDEAM (raw) | filas | Completitud | La extracción trae al menos 1 fila | ≥ 1 | Critical | R6, R7 | 0 filas = sin datos climáticos = R6/R7 inviables |
| DQ14 | API IDEAM (raw) | `departamento` | Completitud | Llave de integración informada | ≥ 99% | Critical | R6, R7 | Umbral calibrado: estación sin nombre de departamento no puede contribuir a `dim_clima` |
| DQ15 | API IDEAM (raw) | `minimo`, `maximo` | Validez | Temperatura entre -15 °C y 50 °C | ≥ 99.5% | Critical | R6, R7 | **Físico + oficial:** rango plausible para Colombia. Ficha IDEAM avisa de fallas de sensor. Umbral 99.5%: hasta 0.5% de fallas tolerables |
| DQ16 | API IDEAM (raw) | `window_start` | Consistencia temporal | Ventana dentro del año 2025 (regex `^2025-`) | 100% | Critical | R6, R7 | **Contractual:** ECV es de 2025; clima de otro año es incompatible |
| DQ17 | API IDEAM (raw) | `departamento` | Completitud (cobertura) | Departamentos distintos con datos | ≥ 30 | Warning | R6, R7 | **Empírica (2026-10-20):** consulta real al IDEAM en 3 ventanas de 2 días de 2025 (mar, jun, sep) dio 32 de 33 departamentos; solo falta Vaupés. Con ≥ 30 se tolera perder hasta 3 sin avisar y se alerta si la cobertura cae más. Es Warning porque R1–R5 no dependen de la API. Limitación: se midió en 3 ventanas, no en todo el año. Evidencia: `docs/evidence/cobertura_api_ideam_2025.md` |
| DQ18 | API IDEAM (raw) | `latitud`, `longitud` | Validez | Coordenadas dentro de Colombia: lat ∈ [-5, 14], lon ∈ [-82, -66] | ≥ 99% | Warning | R6, R7 | **Geográfico:** límites de Colombia incluyendo San Andrés (-81.7°). Warning porque coordenadas corruptas no impiden el cálculo de temperatura |

---

## Compuerta 3 — Datos Preparados (validate_prepared)

Estas reglas se evalúan **después** de la transformación e integración y **antes** de la carga al DW.
Están implementadas en `src/validation.py` → `run_prepared_gate()`.

### fact_huella_carbono

| ID | Atributo(s) | Dimensión | Regla | Métrica / umbral | Severidad | Req. | Base del umbral |
|----|-------------|-----------|-------|------------------|-----------|------|-----------------|
| DQ19 | `sk_fact`, `fk_hogar` | Unicidad | Grano único: un hogar por fila | 100% | Critical | R1–R7 | Duplicados → doble conteo de emisiones → KPIs inflados |
| DQ20 | `fk_hogar`, `fk_ubicacion` | Completitud | FKs no nulas | 100% | Critical | R1–R7 | FK nula = fila no cargable al DW (rompe integridad referencial) |
| DQ21 | `clima_emparejado` | Emparejamiento | Al menos 50% de hogares con clima | media ≥ 0.5 | Warning | R6, R7 | **Analítico:** los dptos más poblados (Bogotá, Antioquia, Valle) deben tener estaciones IDEAM. <50% sugiere falla en la normalización de nombres o cobertura insuficiente de la API |
| DQ22 | `kwh_consumidos_estimados`, `emisiones_energia_kg`, `emisiones_coccion_kg`, `huella_total_anual_kg` | Validez | Emisiones ≥ 0 | 100% | Critical | R1–R7 | El modelo de huella no puede producir valores negativos (pago/tarifa ≥ 0 por construcción) |
| DQ23 | `huella_total_anual_kg` vs componentes | Consistencia interna | `huella_total ≥ emisiones_energia` y `huella_total ≥ emisiones_coccion` | 100% | Critical | R1–R7 | **Matemático:** la huella es la suma de las componentes; ningún componente puede ser mayor que el total |
| DQ24 | filas | Completitud | Al menos 1 hogar | ≥ 1 | Critical | R1–R7 | 0 filas = transformación vacía = carga sin sentido |
| DQ25 | columnas requeridas | Validez (contrato) | Están todas las columnas del modelo estrella | 100% | Critical | R1–R7 | Columna faltante = SQL de carga falla |

### dim_hogar

| ID | Atributo(s) | Dimensión | Regla | Métrica / umbral | Severidad | Req. | Base del umbral |
|----|-------------|-----------|-------|------------------|-----------|------|-----------------|
| DQ26 | `sk_hogar`, `num_personas`, `tiene_vehiculo`, `bien_p1077s11`, `bien_p1077s12` | Varios | Surrogate único; num_personas ≥ 1; tenencia en `{Sí, No}` | 100% / 100% / Warning | Critical/Warning | R1–R7 | `sk_hogar` duplicado = FK ambigua. `num_personas=0` imposible. Tenencia Warning pq viene de DQ11 (dominio ya validado en raw) |

### dim_ubicacion

| ID | Atributo(s) | Dimensión | Regla | Métrica / umbral | Severidad | Req. | Base del umbral |
|----|-------------|-----------|-------|------------------|-----------|------|-----------------|
| DQ27 | `sk_ubicacion`, `codigo_departamento`, `estrato` | Unicidad / Validez | Surrogate único; estrato en [0, 6]; código no nulo | 100% | Critical/Warning | R1–R7 | Estrato 0 = reclasificado en transform. Código 0 = departamento no identificado (máximo 1%) |

### dim_clima

| ID | Atributo(s) | Dimensión | Regla | Métrica / umbral | Severidad | Req. | Base del umbral |
|----|-------------|-----------|-------|------------------|-----------|------|-----------------|
| DQ28 | `sk_clima`, `codigo_departamento`, `temp_media_c`, `piso_termico` | Varios | 1 fila por departamento; temp en [-15, 50] °C; consistencia min ≤ media ≤ max; piso en dominio; ≥20 departamentos | 100% / Warning | Critical/Warning | R6, R7 | Post-limpieza: la fase de transformación ya excluye outliers de sensor. Umbral ≥20 dptos = mínimo estadístico |

### dim_tarifas

| ID | Atributo(s) | Dimensión | Regla | Métrica / umbral | Severidad | Req. | Base del umbral |
|----|-------------|-----------|-------|------------------|-----------|------|-----------------|
| DQ29 | `sk_tarifa`, `estrato_aplica`, `costo_promedio_kwh` | Validez | Surrogate único; estratos 1–6; costo > 0 | 100% | Critical | R1, R6 | **Operativo:** tarifa = 0 → kWh infinitos → huella eléctrica infinita |

### dim_combustibles

| ID | Atributo(s) | Dimensión | Regla | Métrica / umbral | Severidad | Req. | Base del umbral |
|----|-------------|-----------|-------|------------------|-----------|------|-----------------|
| DQ30 | `sk_combustible`, `tipo_combustible`, `factor_emision_kg_tj` | Validez | Surrogate único; factor > 0 | 100% | Critical | R2–R5 | **Físico:** todos los combustibles emiten CO₂ > 0. Factor = 0 → huella de cocción = 0 (incorrecto) |

---

## Política de Compuerta (implementada en `src/validation.py → enforce_policy()`)

| Severidad | Respuesta del pipeline | Re-ejecución |
|-----------|------------------------|--------------|
| **Critical** | La tarea falla (`ValueError`); las tareas posteriores no se ejecutan | No reintenta: los datos no cambian al repetir |
| **Warning** | Se registra en el log de Airflow y en el JSON de resultado GX; el pipeline continúa | Continúa: la política documentada lo permite |
| **Info** | Solo monitoreo; nunca bloquea | Continúa siempre |

---

## Trazabilidad Regla → Suite GX → Compuerta → Tarea Airflow

| Regla | Suite GX | Compuerta | Tarea Airflow |
|-------|----------|-----------|---------------|
| DQ01–DQ05 | `ecv_servicios_raw_suite` | 1 — Raw ECV | `validate_primary_raw` |
| DQ06–DQ08 | `ecv_vivienda_raw_suite` | 1 — Raw ECV | `validate_primary_raw` |
| DQ09 | `ecv_caracteristicas_raw_suite` | 1 — Raw ECV | `validate_primary_raw` |
| DQ10–DQ11 | `ecv_condiciones_raw_suite` | 1 — Raw ECV | `validate_primary_raw` |
| DQ12–DQ18 | `api_ideam_raw_suite` | 2 — Raw API | `validate_api_raw` |
| DQ19–DQ25 | `prepared_fact_huella_suite` | 3 — Preparados | `validate_prepared` |
| DQ26 | `prepared_dim_hogar_suite` | 3 — Preparados | `validate_prepared` |
| DQ27 | `prepared_dim_ubicacion_suite` | 3 — Preparados | `validate_prepared` |
| DQ28 | `prepared_dim_clima_suite` | 3 — Preparados | `validate_prepared` |
| DQ29 | `prepared_dim_tarifas_suite` | 3 — Preparados | `validate_prepared` |
| DQ30 | `prepared_dim_combustibles_suite` | 3 — Preparados | `validate_prepared` |
