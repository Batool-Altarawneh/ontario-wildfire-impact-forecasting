-- Date dimension used for daily analysis.
-- The actual calendar date is used as the primary key because it is already unique
-- and makes joins easier to read.

CREATE TABLE analytics.dim_date (
    date_id DATE PRIMARY KEY,

    -- These values are generated from date_id so they cannot get out of sync
    -- with the actual date.
    year SMALLINT
        GENERATED ALWAYS AS (
            EXTRACT(YEAR FROM date_id)::SMALLINT
        ) STORED,

    month SMALLINT
        GENERATED ALWAYS AS (
            EXTRACT(MONTH FROM date_id)::SMALLINT
        ) STORED,

    -- ISO day of week: Monday = 1 and Sunday = 7.
    day_of_week SMALLINT
        GENERATED ALWAYS AS (
            EXTRACT(ISODOW FROM date_id)::SMALLINT
        ) STORED,

    -- Fire season definition has not been finalized yet,
    -- so this stays nullable for now.
    is_fire_season BOOLEAN
);