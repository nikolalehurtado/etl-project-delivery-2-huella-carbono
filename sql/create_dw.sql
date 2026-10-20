-- Creación de la base de datos
CREATE DATABASE IF NOT EXISTS huella_carbono_dw_v2;
USE huella_carbono_dw_v2;

-- DIMENSIONES

CREATE TABLE IF NOT EXISTS dim_hogar (
    sk_hogar INT AUTO_INCREMENT PRIMARY KEY,
    id_directorio VARCHAR(50),
    id_secuencia_p VARCHAR(50),
    num_personas INT,
    tiene_vehiculo TINYINT(1)
);

CREATE TABLE IF NOT EXISTS dim_ubicacion (
    sk_ubicacion INT AUTO_INCREMENT PRIMARY KEY,
    codigo_departamento VARCHAR(10),
    nombre_departamento VARCHAR(100),
    estrato INT
);

CREATE TABLE IF NOT EXISTS dim_combustibles (
    sk_combustible INT AUTO_INCREMENT PRIMARY KEY,
    tipo_combustible VARCHAR(50),
    factor_emision DECIMAL(10,4)
);

CREATE TABLE IF NOT EXISTS dim_tarifas_energia (
    sk_tarifa_energia INT AUTO_INCREMENT PRIMARY KEY,
    estrato INT,
    tarifa_kwh DECIMAL(10,2)
);

-- NUEVA DIMENSIÓN: Clima (API IDEAM)
CREATE TABLE IF NOT EXISTS dim_clima (
    sk_clima INT AUTO_INCREMENT PRIMARY KEY,
    nombre_departamento VARCHAR(100) NOT NULL,
    temp_media_c DECIMAL(5,2),
    piso_termico VARCHAR(20) -- Cálido, Templado, Frío
);

-- TABLA DE HECHOS

CREATE TABLE IF NOT EXISTS fact_huella_carbono (
    sk_huella INT AUTO_INCREMENT PRIMARY KEY,
    fk_hogar INT,
    fk_ubicacion INT,
    fk_combustible INT,
    fk_tarifa_energia INT,
    fk_clima INT, -- NUEVA LLAVE FORÁNEA
    
    kwh_consumidos_estimados DECIMAL(10,2),
    emisiones_energia_kg DECIMAL(10,2),
    emisiones_coccion_kg DECIMAL(10,2),
    huella_total_anual_kg DECIMAL(10,2),
    
    FOREIGN KEY (fk_hogar) REFERENCES dim_hogar(sk_hogar),
    FOREIGN KEY (fk_ubicacion) REFERENCES dim_ubicacion(sk_ubicacion),
    FOREIGN KEY (fk_combustible) REFERENCES dim_combustibles(sk_combustible),
    FOREIGN KEY (fk_tarifa_energia) REFERENCES dim_tarifas_energia(sk_tarifa_energia),
    FOREIGN KEY (fk_clima) REFERENCES dim_clima(sk_clima) -- CONEXIÓN A DIM_CLIMA
);