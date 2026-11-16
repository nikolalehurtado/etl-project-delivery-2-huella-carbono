import json
import os
from kafka import KafkaConsumer

# Configuración de Kafka
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC = "huella-metrics-topic"

def run_consumer():
    print(f"Conectando al broker de Kafka en {KAFKA_BROKER}...")
    
    # Inicializar el consumidor
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BROKER],
        auto_offset_reset='latest',  # Leer solo los mensajes nuevos a partir de ahora
        enable_auto_commit=True,
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    
    print(f"Consumidor suscrito al topic '{KAFKA_TOPIC}'. Esperando métricas en tiempo real...\n")
    print("-" * 55)
    
    try:
        # Bucle infinito escuchando mensajes nuevos
        for message in consumer:
            payload = message.value
            timestamp = payload.get("timestamp")
            metrics = payload.get("metrics")
            
            print(f"[{timestamp}] Nuevas métricas recibidas:")
            print(f"  -> Huella de CO2 Promedio:      {metrics.get('avg_huella_total')} kg/año")
            print(f"  -> Consumo Eléctrico Promedio:  {metrics.get('avg_kwh_consumidos')} kWh/mes")
            print(f"  -> Emisiones Cocción Promedio:  {metrics.get('avg_emisiones_coccion')} kg/año")
            print("-" * 55)
            
    except KeyboardInterrupt:
        print("\nConsumidor detenido por el usuario.")
    finally:
        consumer.close()

if __name__ == "__main__":
    run_consumer()