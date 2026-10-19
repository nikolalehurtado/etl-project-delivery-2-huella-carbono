# Reglas de calidad (BORRADOR — Persona 2 debe validarlas y justificar cada umbral)

Las reglas ya estan implementadas en `src/validation.py` (cada Expectation lleva su ID en `meta`).
Un umbral elegido solo porque los datos actuales lo cumplen **no es aceptable** (enunciado, 8.1):
cada umbral marcado PROVISIONAL necesita una base analitica, contractual, historica u operativa
que salga del perfilamiento (`notebooks/`).

| ID | Fuente / capa | Atributo(s) | Dimension | Regla | Metrica / umbral | Severidad | Req. | Base del umbral |
|----|---------------|-------------|-----------|-------|------------------|-----------|------|-----------------|
| DQ01 | ECV servicios (raw) | columnas requeridas | Validez (contrato) | Estan todas las columnas requeridas | 100% | Critical | R1-R5 | Contrato de la fuente |
| DQ02 | ECV servicios (raw) | DIRECTORIO, SECUENCIA_P | Completitud | Sin nulos: identifican al hogar | 100% | Critical | R1-R7 | Grano de la tabla de hechos |
| DQ03 | ECV servicios (raw) | DIRECTORIO + SECUENCIA_P | Unicidad | Un hogar por fila | >= 99% | Warning | R1-R7 | PROVISIONAL (fase 1 elimino 212 duplicados) |
| DQ04 | ECV servicios (raw) | P5018 | Completitud | Pago de luz informado | >= 70% | Warning | R1, R6 | PROVISIONAL (con menos, la huella dependeria mas de la imputacion) |
| DQ05 | ECV servicios (raw) | P5010 | Validez | Estrato entre 1 y 6 | >= 99,9% | Warning | R1, R6 | Estratos validos en Colombia; fase 1 reclasifico 7 y 8 |
| DQ06 | ECV vivienda (raw) | columnas requeridas | Validez (contrato) | Estan todas las columnas | 100% | Critical | R4, R6, R7 | Contrato de la fuente |
| DQ07 | ECV vivienda (raw) | P1_DEPARTAMENTO | Completitud | Sin nulos: es la llave de integracion | 100% | Critical | R6, R7 | Llave de integracion |
| DQ08 | ECV vivienda (raw) | P1_DEPARTAMENTO | Validez | Codigo DIVIPOLA valido (33 departamentos) | 100% | Critical | R6, R7 | `data/reference/dane_departamentos.csv` |
| DQ09 | ECV caracteristicas (raw) | claves del hogar | Completitud | Sin nulos en las claves | 100% | Critical | R5 | Se usa para contar integrantes |
| DQ10 | ECV condiciones (raw) | P1077S15 | Validez | Dominio {1, 2} | 100% | Critical | R3 | Diccionario DANE |
| DQ11 | ECV condiciones (raw) | P1077S11, P1077S12 | Validez | Dominio {1, 2} | 100% | Warning | R7 | Confirmar significado en el diccionario DANE |
| DQ12 | API IDEAM (raw) | columnas de la consulta | Validez (contrato) | Estan todas las columnas | 100% | Critical | R6, R7 | Contrato de la API |
| DQ13 | API IDEAM (raw) | filas | Completitud | La extraccion trae al menos 1 fila | >= 1 | Critical | R6, R7 | Sin datos no hay R6 ni R7 |
| DQ14 | API IDEAM (raw) | departamento | Completitud | Llave de integracion informada | >= 99% | Critical | R6, R7 | PROVISIONAL |
| DQ15 | API IDEAM (raw) | minimo, maximo | Validez | Temperatura entre -15 y 50 C | >= 99,5% | Critical | R6, R7 | Rango fisico plausible; la ficha avisa de fallas de sensor. PROVISIONAL |
| DQ16 | API IDEAM (raw) | window_start | Consistencia temporal | Ventana dentro de 2025 | 100% | Critical | R6, R7 | Compatibilidad con la ECV 2025 |
| DQ17 | API IDEAM (raw) | departamento | Completitud (cobertura) | Departamentos distintos con datos | >= 20 | Warning | R6, R7 | PROVISIONAL: calibrar con `scripts/verificar_cobertura_api.py` |
| DQ18 | API IDEAM (raw) | latitud, longitud | Validez | Coordenadas dentro de Colombia | >= 99% | Warning | R6, R7 | Limites geograficos del pais |

Pendiente: reglas de la compuerta de datos **preparados** (esquema, dominios, indicadores de
emparejamiento ECV-API, unicidad en el grano, llaves listas para la carga).
