# Supuestos, cambios de requisitos y trazabilidad

Documento pedido por el profesor tras la primera entrega: (1) coherencia de R3, (2) trazabilidad
requisito → dato → KPI → evidencia, (3) rigor en los supuestos que convierten gasto en consumo y emisiones.

---

## 1. Bitácora de cambios de requisitos

| Fecha | Requisito | Redacción original (primera entrega) | Qué pasó | Redacción nueva |
|---|---|---|---|---|
| 2026-10-20 | **R3** | "¿Cuál es el peso porcentual de los vehículos particulares en las emisiones totales del hogar?" | **No es respondible con los datos.** La ECV solo informa si el hogar tiene carro (`P1077S15`, 1 = sí, 2 = no); no trae combustible, kilómetros ni gasto de transporte. Con la huella actual (energía + cocina) no se puede calcular el peso del vehículo. La primera entrega lo resolvió midiendo otra cosa sin cambiar el texto del requisito, y eso es lo que el profesor señaló. | **R3':** "¿Cómo se compara la huella de carbono anual por energía y cocina de los hogares con vehículo particular frente a los hogares sin vehículo, a igual estrato?" |

**Decisión:** se reformula R3 de forma explícita (no se incorporan datos nuevos). R3' mide una **asociación**,
no emisiones de transporte. Queda declarado como limitación que las emisiones del vehículo **no** están
incluidas en `huella_total_anual_kg`.

**Hallazgo de la primera entrega que R3' debe interpretar con cuidado:** los hogares sin carro mostraron mayor
huella (≈1.232 kg) que los que tienen (≈1.030 kg). Es contraintuitivo y probablemente se debe a variables
que confunden (ruralidad y combustible de cocina), no al vehículo. Por eso R3' compara **por estrato** y la
interpretación debe decirlo.

---

## 1.1 Bitácora de decisiones de integración

| ID | Fecha | Decisión | Por qué | Alternativa descartada |
|---|---|---|---|---|
| D-02 | 2026-10-20 | **Vaupés (código DANE 97) queda sin clima y se excluye de R6 y R7.** Sus 1.509 hogares (≈1,7 % de la ECV) se conservan en R1–R5 con `fk_clima` NULL y `clima_emparejado = 0`. | La consulta real al IDEAM (3 ventanas de 2025) devolvió 32 de 33 departamentos; Vaupés no tiene estaciones con datos. Sin medición no hay temperatura que usar. Evidencia: `docs/evidence/cobertura_api_ideam_2025.md`. | **Asignarle 0 °C:** es un dato inventado, no una ausencia. Vaupés es amazónico y cálido; un 0 lo clasificaría como "Frío" y sesgaría R6 y R7 (hogares cálidos mezclados con fríos), además de violar la regla de rango y de promedios. **Imputar la temperatura de un departamento vecino:** supone una similitud climática que no medimos. |
| D-03 | 2026-10-20 | **Umbral de DQ17 sube de 20 a 30 departamentos con datos.** | Base empírica: 32 de 33 observados. Con 30 se tolera perder hasta 3 sin avisar. Severidad Warning porque R1–R5 no dependen de la API. | Dejar 20: no tenía respaldo y no detectaría una pérdida seria de cobertura. |

## 2. Trazabilidad requisito → KPI → evidencia

| Req. | Pregunta | Datos | Dimensiones / medida | KPI | Consulta SQL | Gráfica del dashboard | Evidencia |
|---|---|---|---|---|---|---|---|
| R1 | Huella por estrato | ECV servicios | `dim_ubicacion.estrato`, `huella_total_anual_kg` | Huella media por estrato | `sql/` (pendiente) | pendiente | `docs/evidence/` (pendiente) |
| R2 | Cocina por combustible | ECV servicios | `dim_combustibles`, `emisiones_coccion_kg` | Emisiones medias por combustible | pendiente | pendiente | pendiente |
| R3' | Huella con vs sin vehículo, por estrato | ECV condiciones | `dim_hogar.tiene_vehiculo`, `dim_ubicacion.estrato` | Huella media por estrato y tenencia de vehículo | pendiente | pendiente | pendiente |
| R4 | Por departamento | ECV vivienda | `dim_ubicacion.nombre_departamento` | Huella media por departamento | pendiente | pendiente | pendiente |
| R5 | Por tamaño del hogar | ECV características | `dim_hogar.num_personas` | Huella por persona | pendiente | pendiente | pendiente |
| R6 | kWh y CO₂ eléctrico: cálido vs templado/frío, por estrato | ECV + API IDEAM | `dim_clima.piso_termico`, `kwh_consumidos_estimados`, `emisiones_energia_kg` | kWh/mes y kg CO₂/año por piso térmico y estrato | pendiente | pendiente | pendiente |
| R7 | % hogares con equipo (confirmar P1077S11/S12) vs temperatura | ECV + API IDEAM | `dim_hogar.bien_p1077s11/12`, `dim_clima.temp_media_c` | % de hogares con equipo por departamento y su temperatura | pendiente | pendiente | pendiente |

Cada fila "pendiente" se completa con la consulta real, la captura legible del dashboard y su interpretación.

---

## 3. Supuestos para convertir gasto en consumo y emisiones

**Estado:** los valores salen del código de la primera entrega (`src/transform.py`). **Ninguno tiene fuente
documentada todavía.** Cada fila debe completarse con fuente, fecha y efecto; si no hay fuente verificable, se deja
declarado como supuesto propio y su limitación.

| ID | Supuesto | Valor usado | Dónde se usa | Fuente | Efecto en el resultado | Estado |
|---|---|---|---|---|---|---|
| S1 | El pago mensual de energía (`P5018`) dividido entre una tarifa por estrato da los kWh | Tarifa $/kWh: E1 460 · E2 570 · E3 970 · E4 1150 · E5 y E6 1380 (`data/reference/dim_tarifas.csv`) | `kwh_consumidos_estimados` | PENDIENTE (la tabla no cita fuente) | Si la tarifa real es distinta, los kWh cambian en proporción inversa. Una tarifa única por estrato ignora diferencias entre empresas y el límite de subsistencia | Sin fuente |
| S2 | La tarifa de estratos 1–3 es un promedio que ya incluye el subsidio | Subsidio 60 / 50 / 15 % solo en el consumo de subsistencia | S1 | PENDIENTE | Si el hogar pasa del consumo de subsistencia, parte del consumo se paga a tarifa plena y los kWh quedan sobrestimados | Sin fuente |
| S3 | El factor de emisión eléctrica es constante todo el año | 0,097 kg CO₂/kWh (`dim_factor_electrico.csv`, atribuido a XM) | `emisiones_energia_kg` | PENDIENTE: confirmar valor y año publicados | Escala todas las emisiones eléctricas por igual | Verificar |
| S4 | El gas natural se factura y su precio es uniforme | 1.800 COP/m³ | Emisiones de cocina (gas natural, `P3163`) | PENDIENTE | Precio distinto cambia los m³ estimados | Sin fuente |
| S5 | El gasto en GLP/otros (`P8540`) se convierte con un precio único | 3.200 COP/kg | Emisiones de cocina (GLP) | PENDIENTE | Mismo efecto que S4. R2 de la primera entrega ya lo reconoció como limitación | Sin fuente |
| S6 | Poder calorífico de los combustibles | Gas natural 37,2 MJ/m³ · GLP 47,3 MJ/kg · leña 15,6 MJ/kg | Conversión a TJ | PENDIENTE | Pequeño frente a S4/S5, pero debe citarse | Sin fuente |
| S7 | Consumo fijo de leña por hogar que la usa | 150 kg/mes (~5 kg/día) | Emisiones de cocina (leña) | PENDIENTE (el código dice "IDEAM, promedio rural") | **No depende del gasto del hogar**: todo hogar con leña recibe el mismo valor. Es el supuesto más fuerte | Sin fuente |
| S8 | Factores de emisión por combustible | Leña 112.000 · GLP 63.100 · gas natural 56.100 kg/TJ (`dim_combustibles.csv`) | Emisiones de cocina | PENDIENTE. *Esto no aparece en el material del curso; coincide con valores por defecto del IPCC (2006), a confirmar.* | Define la escala de las emisiones de cocina | Verificar |
| S9 | **Inconsistencia a decidir:** la tabla dice que la leña es carbono neutro y "no suma al total neto de CO₂", pero el código le aplica el factor completo (112.000) y la suma | — | `emisiones_coccion_kg`, `huella_total_anual_kg` | — | Puede sobrestimar mucho la huella de hogares rurales con leña, y afecta R2, R3', R4 | **Decisión pendiente** |
| S10 | Los hogares con estrato inválido (7 u 8 en la primera entrega; 12 en la corrida actual) se reclasifican a estrato 0 | Estrato 0 | `dim_ubicacion` | Decisión de la primera entrega | No tienen tarifa (`fk_tarifa_energia` nulo) y se excluyen de R1/R6 por estrato | Documentado |
| S11 | Los nulos de `P5018` se imputan con la mediana del estrato; los outliers se truncan al P99; los ceros de estrato ≠ 1 se imputan | Mediana por estrato · P99 | `transform.py` | Perfilamiento de la primera entrega | ≈19.969 nulos imputados: más de 1 de cada 5 hogares tiene el consumo eléctrico estimado | Justificar con el perfilamiento |
| S12 | No se calculan emisiones del vehículo | — | `huella_total_anual_kg` | Limitación de datos (R3) | La huella total **no** incluye transporte | Declarado |
| S13 | (Segunda entrega) La temperatura promedio de un departamento representa a todos sus hogares | Media ponderada por lecturas de las estaciones del IDEAM, 2025 | `dim_clima` | API IDEAM `sbwg-7ju4`; cobertura medida en `docs/evidence/cobertura_api_ideam_2025.md` | Oculta diferencias internas (por altitud). Arauca, Guainía y Guaviare tienen **1** estación y Vichada 3; Cundinamarca (44) y Boyacá (34) promedian estaciones de alturas muy distintas. Los valores no están validados por el IDEAM | Declarado |
| S15 | (Segunda entrega) Vaupés no tiene temperatura y se excluye de R6 y R7 | — (NULL, nunca 0) | `fk_clima`, `clima_emparejado` | Decisión D-02 | R6 y R7 se calculan sobre 32 de 33 departamentos (≈98,3 % de los hogares) | Declarado |
| S14 | (Segunda entrega) Corte de piso térmico | >24 °C cálido · 18–24 templado · <18 frío | `dim_clima.piso_termico` | Convención general, a confirmar | Cambiar el corte reasigna departamentos | Confirmar |

**Cómo llenar cada fila:** (1) fuente con enlace y año, (2) valor exacto, (3) una frase de efecto en la huella,
(4) si no hay fuente, escribir "supuesto propio" y el motivo. Lo que no tenga respaldo no se presenta como dato.
