CREATE TABLE analytics.dim_city (
    city_id     SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    city_name   VARCHAR(100) NOT NULL UNIQUE,
    region      VARCHAR(100) NOT NULL,
    latitude    NUMERIC(9,6) NOT NULL
                    CHECK (latitude BETWEEN -90 AND 90),
    longitude   NUMERIC(9,6) NOT NULL
                    CHECK (longitude BETWEEN -180 AND 180)
);