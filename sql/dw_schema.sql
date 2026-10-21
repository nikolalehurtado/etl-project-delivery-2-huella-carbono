-- =========================================================================
-- PROYECTO: ETL Segunda Entrega — Huella de Carbono en Hogares Colombianos (ODS 12)
-- ARCHIVO : sql/dw_schema.sql
-- MOTOR   : MySQL 8.0 (InnoDB, UTF8MB4)
-- AUTORES : Nikol Hurtado, David Aponte, Diana Panesso, Sebastián Celorio
-- DESCRIPCIÓN: Esquema en estrella refinado (Fase 2) que integra la ECV 2025
--              del DANE con la temperatura oficial del IDEAM (API SODA).
--              Soporta los requisitos analíticos R1 a R7.
-- =========================================================================

-- Tabla de auditoría para trazabilidad de cargas (Pruebas A, B y C)
CREATE TABLE IF NOT EXISTS etl_audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL,
    loaded_at DATETIME NOT NULL,
    table_name VARCHAR(50) NOT NULL,
    rows_loaded INT NOT NULL,
    status VARCHAR(20) NOT NULL,
    INDEX idx_audit_run (run_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------
-- DIMENSIONES
-- -----------------------------------------------------------------

-- dim_hogar: Un registro por hogar encuestado en la ECV 2025.
-- Grano: combinación única de DIRECTORIO + SECUENCIA_P.
CREATE TABLE IF NOT EXISTS dim_hogar (
    sk_hogar INT PRIMARY KEY,
    directorio VARCHAR(50) NOT NULL,
    secuencia_p VARCHAR(20) NOT NULL,
    num_personas INT NOT NULL DEFAULT 1,
    tiene_vehiculo VARCHAR(10) NOT NULL DEFAULT 'No',
    bien_p1077s11 VARCHAR(10) NOT NULL DEFAULT 'No', -- bien P1077S11 (R7): significado por CONFIRMAR en el diccionario DANE
    bien_p1077s12 VARCHAR(10) NOT NULL DEFAULT 'No', -- bien P1077S12 (R7): significado por CONFIRMAR en el diccionario DANE
    INDEX idx_hogar_vehiculo (tiene_vehiculo),
    INDEX idx_hogar_bienes (bien_p1077s11, bien_p1077s12)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dim_ubicacion: Ubicación geográfica departamental y estrato socioeconómico.
-- Grano: combinación única de (codigo_departamento, estrato).
CREATE TABLE IF NOT EXISTS dim_ubicacion (
    sk_ubicacion INT PRIMARY KEY,
    codigo_departamento INT NOT NULL,
    nombre_departamento VARCHAR(100) NOT NULL,
    estrato INT NOT NULL,
    INDEX idx_ubicacion_depto (codigo_departamento),
    INDEX idx_ubicacion_estrato (estrato)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dim_clima: Clima oficial 2025 agregado por departamento desde la API del IDEAM.
-- Grano: un registro por departamento (código DIVIPOLA).
CREATE TABLE IF NOT EXISTS dim_clima (
    sk_clima INT PRIMARY KEY,
    codigo_departamento INT NOT NULL,
    nombre_departamento VARCHAR(100) NOT NULL,
    anio INT NOT NULL,
    temp_media_c DECIMAL(5,2) NOT NULL,
    temp_min_c DECIMAL(5,2) NULL,
    temp_max_c DECIMAL(5,2) NULL,
    n_estaciones INT NOT NULL,
    n_lecturas INT NOT NULL,
    piso_termico VARCHAR(50) NOT NULL,
    INDEX idx_clima_depto (codigo_departamento),
    INDEX idx_clima_piso (piso_termico)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dim_combustibles: Tipo de combustible para cocción y factores IPCC (kg CO₂ / TJ).
CREATE TABLE IF NOT EXISTS dim_combustibles (
    sk_combustible INT PRIMARY KEY,
    tipo_combustible VARCHAR(100) NOT NULL,
    factor_emision_kg_tj DECIMAL(12,2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- dim_tarifas: Tarifa promedio estimada de energía eléctrica por estrato (CREG).
CREATE TABLE IF NOT EXISTS dim_tarifas (
    sk_tarifa INT PRIMARY KEY,
    estrato_aplica INT NOT NULL,
    costo_promedio_kwh DECIMAL(10,2) NOT NULL,
    INDEX idx_tarifa_estrato (estrato_aplica)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------
-- TABLA DE HECHOS
-- -----------------------------------------------------------------

-- fact_huella_carbono: Medición anual estimada de la huella de carbono residencial.
-- Grano: un registro por hogar encuestado (DIRECTORIO + SECUENCIA_P).
CREATE TABLE IF NOT EXISTS fact_huella_carbono (
    sk_fact INT PRIMARY KEY,
    fk_hogar INT NOT NULL,
    fk_ubicacion INT NOT NULL,
    fk_clima INT NULL,
    fk_combustible_cocina INT NULL,
    fk_tarifa_energia INT NULL,
    clima_emparejado TINYINT NOT NULL DEFAULT 0,
    kwh_consumidos_estimados DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    emisiones_energia_kg DECIMAL(12,4) NOT NULL DEFAULT 0.0000,
    emisiones_coccion_kg DECIMAL(12,4) NOT NULL DEFAULT 0.0000,
    huella_total_anual_kg DECIMAL(12,4) NOT NULL DEFAULT 0.0000,

    CONSTRAINT fk_fact_hogar FOREIGN KEY (fk_hogar) REFERENCES dim_hogar (sk_hogar) ON DELETE RESTRICT,
    CONSTRAINT fk_fact_ubicacion FOREIGN KEY (fk_ubicacion) REFERENCES dim_ubicacion (sk_ubicacion) ON DELETE RESTRICT,
    CONSTRAINT fk_fact_clima FOREIGN KEY (fk_clima) REFERENCES dim_clima (sk_clima) ON DELETE RESTRICT,
    CONSTRAINT fk_fact_combustible FOREIGN KEY (fk_combustible_cocina) REFERENCES dim_combustibles (sk_combustible) ON DELETE RESTRICT,
    CONSTRAINT fk_fact_tarifa FOREIGN KEY (fk_tarifa_energia) REFERENCES dim_tarifas (sk_tarifa) ON DELETE RESTRICT,

    INDEX idx_fact_clima_emp (clima_emparejado),
    INDEX idx_fact_fk_ubi (fk_ubicacion),
    INDEX idx_fact_fk_clima (fk_clima)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
