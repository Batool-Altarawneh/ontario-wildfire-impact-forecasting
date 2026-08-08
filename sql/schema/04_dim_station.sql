-- Station reference dimension.
-- The warehouse uses its own station_id because station IDs come from
-- different source systems and may overlap.

CREATE TABLE analytics.dim_station (
    station_id SMALLINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    -- Original station ID from GeoMet, AQO, or ECCC.
    source_station_id VARCHAR(50) NOT NULL,

    station_name VARCHAR(150) NOT NULL,

    -- Text with a CHECK keeps the allowed source names controlled,
    -- but it is still easier to extend later than a Postgres ENUM.
    source_system VARCHAR(30) NOT NULL
        CHECK (source_system IN ('geomet', 'aqo', 'eccc_weather')),

    -- Each station is mapped to one of the project cities.
    city_id SMALLINT NOT NULL
        REFERENCES analytics.dim_city(city_id),

    latitude NUMERIC(9,6) NOT NULL
        CHECK (latitude BETWEEN -90 AND 90),

    longitude NUMERIC(9,6) NOT NULL
        CHECK (longitude BETWEEN -180 AND 180),

    -- A station ID only needs to be unique inside its own source system.
    UNIQUE (source_system, source_station_id)
);