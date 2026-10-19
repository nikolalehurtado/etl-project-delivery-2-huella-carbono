"""
Verifica la cobertura de la API de temperatura del IDEAM ANTES de correr el pipeline.

Consulta ventanas chicas (2 dias) en tres meses de 2025 y cuenta las estaciones con datos
por departamento. Uso (fuera de Docker):
    python scripts/verificar_cobertura_api.py
Requiere: pip install requests
"""

import time
from collections import defaultdict

import requests

URL = "https://www.datos.gov.co/resource/sbwg-7ju4.json"


def consultar(params, intentos=3):
    for i in range(1, intentos + 1):
        try:
            r = requests.get(URL, params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"   intento {i} fallo: {type(e).__name__}")
            time.sleep(5 * i)
    return None


print("=== 1. Ultima lectura disponible ===")
print(consultar({
    "$select": "fechaobservacion,departamento,nombreestacion,valorobservado",
    "$where": "codigosensor='0068' AND fechaobservacion >= '2026-09-01T00:00:00'",
    "$order": "fechaobservacion DESC",
    "$limit": 1,
}))

print("\n=== 2. Cobertura por departamento en 2025 ===")
ventanas = [("2025-03-10", "2025-03-12"), ("2025-06-10", "2025-06-12"), ("2025-09-10", "2025-09-12")]
cobertura = defaultdict(set)
for desde, hasta in ventanas:
    print(f"Ventana {desde} a {hasta}")
    filas = consultar({
        "$select": "departamento,codigoestacion,count(*) as lecturas",
        "$where": (f"codigosensor='0068' AND fechaobservacion >= '{desde}T00:00:00' "
                   f"AND fechaobservacion < '{hasta}T00:00:00'"),
        "$group": "departamento,codigoestacion",
        "$limit": 5000,
    })
    if filas is None:
        print("   sin respuesta")
        continue
    for f in filas:
        cobertura[f.get("departamento", "(vacio)")].add(f["codigoestacion"])
    print(f"   {len(filas)} estaciones con datos")

print("\nEstaciones por departamento (union de las 3 ventanas):")
for dep in sorted(cobertura):
    print(f"   {dep:45s} {len(cobertura[dep])}")
print(f"\nDepartamentos con datos: {len(cobertura)} (la ECV tiene 33)")

print("\n=== 3. Rango de valores (ventana de junio) ===")
print(consultar({
    "$select": "min(valorobservado) as minimo,max(valorobservado) as maximo,count(*) as n",
    "$where": ("codigosensor='0068' AND fechaobservacion >= '2025-06-10T00:00:00' "
               "AND fechaobservacion < '2025-06-12T00:00:00'"),
}))
