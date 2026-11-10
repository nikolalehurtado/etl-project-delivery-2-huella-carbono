import time
import json
import os
from decimal import Decimal
from kafka import KafkaProducer
import pymysql
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Configuración de conexión a MySQL (Data Warehouse en puerto 3307)
DB_HOST = os.getenv("MYSQL_HOST", "localhost")
DB_PORT = int(os.getenv("MYSQL_PORT", 3307))
DB_USER = os.getenv("MYSQL_USER", "root")
DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
DB_NAME = os.getenv("MYSQL_DATABASE", "huella_carbono_dw_v2")

# Configuración de Kafka
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "huella-metrics-topic"

def get_mysql_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

def fetch_metrics():
    """Extrae las 3 métricas requeridas de la tabla de hechos en el DW"""
    connection = get_mysql_connection()
    try:
        with connection.cursor() as cursor:
            query = """
                SELECT 
                    ROUND(AVG(huella_total_anual_kg), 2) AS avg_huella_total,
                    ROUND(AVG(kwh_consumidos_estimados), 2) AS avg_kwh_consumidos,
                    ROUND(AVG(emisiones_coccion_kg), 2) AS avg_emisiones_coccion
                FROM fact_huella_carbono;
            """
            cursor.execute(query)
            result = cursor.fetchone()
            return result
    finally:
        connection.close()

def convert_decimals(obj):
    """Convierte objetos Decimal a float para que sean compatibles con JSON"""
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj

def run_producer():
    print(f"Conectando al broker de Kafka en {KAFKA_BROKER}...")
    producer = KafkaProducer(
        bootstrap_servers=[KAFKA_BROKER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    print(f"Productor iniciado. Enviando métricas al topic '{KAFKA_TOPIC}'...")
    
    try:
        while True:
            metrics = fetch_metrics()
            payload = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "metrics": metrics
            }
            
            # Limpiar los Decimal antes de enviarlos a JSON/Kafka
            clean_payload = convert_decimals(payload)
            
            producer.send(KAFKA_TOPIC, value=clean_payload)
            producer.flush()
            print(f"[Enviado] -> {clean_payload}")
            
            # Esperar 5 segundos antes de la siguiente transmisión
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nProductor detenido por el usuario.")
    finally:
        producer.close()

if __name__ == "__main__":
    run_producer()