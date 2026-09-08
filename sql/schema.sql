CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS core.dim_station (
    station_id VARCHAR PRIMARY KEY,
    station_name VARCHAR NOT NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    capacity INTEGER,
    region_id VARCHAR,
    station_type VARCHAR,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS core.fact_station_status (
    run_id VARCHAR NOT NULL,
    snapshot_at TIMESTAMPTZ NOT NULL,
    station_id VARCHAR NOT NULL,
    last_reported_at TIMESTAMPTZ,
    bikes_available INTEGER NOT NULL,
    ebikes_available INTEGER NOT NULL,
    bikes_disabled INTEGER NOT NULL,
    docks_available INTEGER NOT NULL,
    docks_disabled INTEGER NOT NULL,
    is_installed BOOLEAN NOT NULL,
    is_renting BOOLEAN NOT NULL,
    is_returning BOOLEAN NOT NULL,
    PRIMARY KEY (run_id, station_id)
);

CREATE TABLE IF NOT EXISTS core.fact_weather (
    run_id VARCHAR PRIMARY KEY,
    observed_at TIMESTAMP NOT NULL,
    latitude DOUBLE NOT NULL,
    longitude DOUBLE NOT NULL,
    temperature_c DOUBLE,
    precipitation_mm DOUBLE,
    wind_speed_kmh DOUBLE
);

CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
    run_id VARCHAR PRIMARY KEY,
    loaded_at TIMESTAMPTZ NOT NULL,
    source_mode VARCHAR NOT NULL,
    station_rows INTEGER NOT NULL,
    status_rows INTEGER NOT NULL,
    weather_rows INTEGER NOT NULL
);

CREATE OR REPLACE VIEW marts.station_health AS
SELECT
    s.run_id,
    s.snapshot_at,
    d.station_id,
    d.station_name,
    d.latitude,
    d.longitude,
    d.capacity,
    s.bikes_available,
    s.ebikes_available,
    s.docks_available,
    s.bikes_disabled,
    s.docks_disabled,
    s.is_renting,
    s.is_returning,
    w.temperature_c,
    w.precipitation_mm,
    w.wind_speed_kmh,
    CASE
        WHEN NOT s.is_installed OR NOT s.is_renting OR NOT s.is_returning THEN 'offline'
        WHEN s.bikes_available <= {{ low_bike_threshold }} THEN 'low_bikes'
        WHEN s.docks_available <= {{ low_dock_threshold }} THEN 'low_docks'
        ELSE 'healthy'
    END AS health_status,
    CASE WHEN d.capacity > 0 THEN s.bikes_available::DOUBLE / d.capacity END AS bike_fill_ratio
FROM core.fact_station_status AS s
JOIN core.dim_station AS d USING (station_id)
LEFT JOIN core.fact_weather AS w USING (run_id);
