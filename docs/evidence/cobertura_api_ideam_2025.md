# Evidencia: cobertura de la API del IDEAM en 2025

Ejecutado el 2026-10-20 con `scripts/verificar_cobertura_api.py` (salida original, sin editar).
Dataset `sbwg-7ju4` (Temperatura Ambiente del Aire), sensor `0068` (Temp Aire 2 m, °C).

```
=== 1. Ultima lectura disponible ===
[{'fechaobservacion': '2026-10-19T23:00:00.000', 'departamento': 'Antioquia', 'nombreestacion': 'MUSINGA AUT [11115040]', 'valorobservado': '19.4'}]

=== 2. Cobertura por departamento en 2025 ===
Ventana 2025-03-10 a 2025-03-12 -> 262 estaciones con datos
Ventana 2025-06-10 a 2025-06-12 -> 275 estaciones con datos
Ventana 2025-09-10 a 2025-09-12 -> 309 estaciones con datos

Estaciones por departamento (union de las 3 ventanas):
   AMAZONAS 2 | ANTIOQUIA 39 | ARAUCA 1 | ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA 2
   ATLANTICO 6 | BOGOTÁ 9 | BOLIVAR 9 | BOYACÁ 34 | CALDAS 8 | CAQUETA 3 | CASANARE 4 | CAUCA 9
   CESAR 6 | CHOCO 10 | CORDOBA 9 | CUNDINAMARCA 44 | GUAINÍA 1 | GUAVIARE 1 | HUILA 18
   LA GUAJIRA 12 | MAGDALENA 8 | META 10 | NARIÑO 15 | NORTE DE SANTANDER 12 | PUTUMAYO 2
   QUINDÍO 6 | RISARALDA 3 | SANTANDER 25 | SUCRE 4 | TOLIMA 22 | VALLE DEL CAUCA 9 | VICHADA 3

Departamentos con datos: 32 (la ECV tiene 33)

=== 3. Rango de valores (ventana de junio) ===
[{'minimo': '0', 'maximo': '35.6', 'n': '12665'}]
```

## Interpretación

- **32 de 33 departamentos** tienen estaciones con datos. **Falta Vaupés (código DANE 97).**
- Los 32 nombres del IDEAM se traducen al código DANE sin excepciones (verificado el 2026-10-20 con la función de normalización de `src/transform.py`).
- Cobertura desigual: Arauca, Guainía y Guaviare tienen **1 estación**; Vichada 3; Cundinamarca 44 y Boyacá 34.
- El mínimo de 0 °C en junio puede ser real (zonas de páramo) o una falla de sensor; la ficha del IDEAM advierte que los valores no están validados. No se corrige: queda documentado.
- Limitación: son 3 ventanas de 2 días, no el año completo.
