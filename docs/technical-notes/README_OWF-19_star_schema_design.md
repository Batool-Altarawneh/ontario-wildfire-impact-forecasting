# OWF-19 Star Schema Design Decisions

## Purpose

This document records the schema design decisions made for OWF-19 before writing the PostgreSQL DDL and transformation logic.

The goal is to preserve not only the final schema shape, but also the questions that came up, the alternatives considered, the reasoning behind each choice, and the cases that are intentionally deferred until EDA or later sprints.

The main design objective is to support the Ontario Wildfire Impact & Forecasting Analytics project with a clean analytical structure that can serve both:

- city-level wildfire and air-quality analysis
- next-day AQHI forecasting with an LSTM model

The schema also needs to preserve source traceability, avoid hiding data-quality limitations, and keep descriptive-only datasets separate from model inputs where appropriate.

---

## 1. Main Fact Table Grain

### Question

Should the main analytical fact table be strictly one row per city per day, or should the database keep separate fact tables at the original source grains and aggregate them later at query/model-preparation time?

The sources do not naturally arrive at the same grain:

- AQHI is station/day or station/hour depending on source.
- CWFIS hotspots are individual geographic point events.
- ECCC weather is hourly.
- Ontario active fires is a live snapshot.
- Evacuations are event-based and can span multiple dates.

### Options Considered

#### Option A: Keep separate fact tables at source grain

Examples:

- hourly weather fact
- hotspot event fact
- AQHI station-level fact
- evacuation event fact

The final city-day dataset would then be produced through joins and aggregations during EDA or model preparation.

#### Option B: Fix the analytical/model grain as city-day

Keep source-level detail in staging, transform each source explicitly, and load only daily city-level features into the main model fact.

### Reasoning

The LSTM target is next-day AQHI per city, so the natural modeling grain is one row per city per day.

Keeping the main fact table at that grain makes the model dataset easier to reason about, validate, and reproduce. It also prevents hourly, point-event, station-level, and event-range records from being mixed into one table with inconsistent meaning.

At the same time, source detail should not be lost. The correct compromise is to preserve the original or near-original grain in staging and perform controlled transformations before loading the analytical fact.

### Decision

The main model/analytics fact table will use:

`one row per city per calendar day`

The table will be named:

`fact_city_daily`

Source-level detail will be preserved in staging tables and aggregated before loading `fact_city_daily`.

---

## 2. Toronto AQHI Grain and Aggregation

### Question

Toronto has multiple AQHI locations/stations depending on source. If station-level values are kept in the analytical fact, Toronto would have several rows per day while Barrie, Kingston, and Thunder Bay would not.

That would change the grain from city-day to city-or-zone-day.

The second question is whether Toronto should use a mean, maximum, or another aggregation rule.

### Options Considered

#### Option A: Keep Toronto zones/stations separate in the final fact

This preserves full spatial detail but breaks the simple city-day grain.

#### Option B: Aggregate Toronto to one daily city value before loading the fact

This keeps the final grain consistent across all four project cities.

Possible aggregation methods include:

- mean across Toronto stations/zones
- maximum across Toronto stations/zones
- another rule justified by EDA

### Reasoning

The schema grain should not depend on which AQHI aggregation rule eventually wins.

Choosing mean or max before inspecting within-Toronto variance would be arbitrary. However, leaving Toronto split into several rows would complicate the entire model schema immediately.

The safer design is therefore to lock the final city-day grain now while preserving station-level values in staging.

### Decision

Toronto will be represented as one city-level row per day in `fact_city_daily`.

The exact Toronto AQHI aggregation method is not fixed yet.

All station/zone-level AQHI observations will be preserved in staging. EDA will be used to compare station variance and determine whether mean, max, or another aggregation is most defensible.

The aggregation rule can change without changing the final fact-table grain.

---

## 3. Weather Aggregation

### Question

ECCC weather extraction is hourly, but `fact_city_daily` is daily.

Should hourly weather remain as a separate analytical fact and be aggregated later, or should it be converted to daily features before reaching the model fact?

### Options Considered

#### Option A: Keep an hourly weather fact

Model-preparation code would aggregate weather later.

#### Option B: Keep hourly weather in staging and load daily summaries into `fact_city_daily`

### Reasoning

The model and main analytical fact are daily. Repeating hourly aggregation in downstream notebooks or model scripts would create duplicated logic and make reproducibility harder.

The hourly data still has value for debugging and future work, so it should remain queryable in staging.

### Decision

ECCC hourly weather will be loaded at source grain into:

`staging.eccc_hourly_weather`

A transformation step will aggregate hourly data to city-day features before loading `fact_city_daily`.

Candidate daily weather fields include:

- `temp_mean`
- `temp_min`
- `temp_max`
- `precip_total`
- `wind_speed_mean`
- `wind_dir_mean_deg`
- `weather_data_available`

The exact final feature list can still be refined during transformation and EDA.

---

## 4. CWFIS Hotspot Aggregation

### Question

CWFIS hotspots are geographic point events, not city-day rows.

Should point-level hotspot records be kept as a separate analytical fact or transformed into city-day wildfire exposure features?

### Options Considered

#### Option A: Query point events directly during modeling

This would require distance calculations and aggregation every time the model dataset is prepared.

#### Option B: Preserve point events in staging and calculate reusable daily city-level features

### Reasoning

Distance-based aggregation is part of data transformation, not something that should be repeatedly reimplemented in model code.

Keeping point events in staging preserves traceability while the analytical fact receives only features aligned to the city-day grain.

### Decision

Raw/near-raw hotspot records will be loaded into:

`staging.cwfis_hotspots`

Derived features for `fact_city_daily` may include:

- `hotspots_within_100km`
- `hotspots_within_250km`
- `hotspots_within_500km`
- `nearest_hotspot_distance_km`
- `fire_data_available`

The final feature list can be refined during transformation and EDA.

---

## 5. Physical PostgreSQL Staging Layer

### Question

Should "staging" refer only to the existing file folders under `data/raw` and `data/processed`, or should PostgreSQL contain a physical `staging` schema?

### Options Considered

#### Option A: File-based staging only

Pipeline:

`raw files -> processed files -> final fact/dimension tables`

Python would perform most aggregation before a single final database load.

#### Option B: Physical PostgreSQL staging schema

Pipeline:

`raw files -> processed/validated files -> PostgreSQL staging -> transformations -> analytical schema`

### Reasoning

A physical staging schema creates a queryable checkpoint between extraction and transformation.

This allows transformation logic to be debugged directly in PostgreSQL without re-running extraction code. It also matches the OWF-19 work plan more closely: load source data, transform it, and then populate analytical tables.

The tradeoff is additional scaffolding. Each extraction source needs a staging-load step before its data contributes to the final fact.

At the current project scale, that extra work is acceptable and improves the data-engineering quality of the project.

### Decision

A physical PostgreSQL `staging` schema will be used.

The existing `data/raw` and `data/processed` folders remain part of the ingestion and validation pipeline. They do not replace database staging.

The intended flow is:

```text
Source
  -> data/raw
  -> data/processed
  -> PostgreSQL staging.*
  -> transformations
  -> analytical dimensions/facts
```
### PostgreSQL schema placement:

- `staging.*` contains source-grain staging tables loaded from validated extraction outputs.
- `analytics.*` contains analytical dimensions, facts, and descriptive/reference tables.

This separation keeps source-grain data physically distinct from transformed analytical data and makes the database layer boundaries explicit.

### SQL Execution Convention

DDL files are executed through the PostgreSQL client inside the `wildfire-postgres` Docker container using `docker exec -i`, because a local `psql` client is not installed.

This is the standing execution method for schema, staging, and fact-table DDL unless the local environment changes later.
---

## 6. Station Lineage and `dim_station`

### Question

Should station detail live only in raw/processed files and staging, or should there be a formal station reference dimension?

### Options Considered

#### Option A: No formal station dimension

Keep station metadata in source files and documentation only.

#### Option B: Create `dim_station`

Make station metadata and source ownership queryable inside PostgreSQL.

### Reasoning

The project uses multiple station systems:

- GeoMet
- AQO
- ECCC weather

Station identifiers are source-specific, and Toronto aggregation may need to be audited later.

A formal station table gives queryable lineage and makes it easier to determine which stations contributed to a city-level aggregate.

The table is not part of the grain of `fact_city_daily`; it exists primarily for source/reference lineage.

### Decision

Create:

`dim_station`

Planned fields:

- `station_id` as the warehouse primary key
- `source_station_id`
- `station_name`
- `source_system`
- `city_id`
- `latitude`
- `longitude`

A warehouse-generated/surrogate `station_id` is preferred over treating raw source IDs as globally unique.

The combination of `source_system` and `source_station_id` should uniquely identify a source station.

---

## 7. Missing Data Semantics: NULL vs Zero

### Problem

A missing value and a true zero are not the same thing.

This is especially important for count-based wildfire features.

For example:

- no hotspots found within 100 km after a successful source run is a real zero
- no valid CWFIS data for that city-day is unknown, not zero

If both cases are stored as `NULL`, the model cannot distinguish "no nearby fire activity" from "data collection gap."

If both are stored as `0`, a failed or missing extraction would be incorrectly treated as evidence that no fire activity occurred.

### Rule

`NULL` means the value is unknown because the source observation was unavailable, incomplete, invalid, or the extraction did not produce a valid observation.

`0` means the source was successfully available and the measured value was genuinely zero.

Per-source availability flags indicate whether a value is trustworthy.

### CWFIS Example

Successful CWFIS data with no hotspots within 100 km:

```text
hotspots_within_100km = 0
fire_data_available = TRUE
```

CWFIS data unavailable for the city-day:

```text
hotspots_within_100km = NULL
fire_data_available = FALSE
```

### AQHI and Weather

Missing AQHI and weather values remain `NULL`.

They are never replaced by zero simply to avoid missing data.

Zero can be a valid observed value for some weather variables, so zero must retain its physical meaning.

### Decision

Use explicit per-source availability flags, including:

- `aqhi_data_available`
- `weather_data_available`
- `fire_data_available`

Do not rely on a single generic completeness score as the only missingness indicator.

Any later imputation for model training belongs in the model-preparation stage and must not overwrite the warehouse meaning of the source data.

---

## 8. City-Day Row Population

### Question

Should a `fact_city_daily` row exist only when the AQHI target exists, or should rows also exist for dates with some available features but missing AQHI?

### Reasoning

Restricting the fact table to target-complete rows would make it convenient for training, but it would mix warehouse design with model-training eligibility.

Days without AQHI may still be useful for EDA, completeness analysis, debugging, or future forecasting workflows.

The availability flags provide a cleaner way to determine training eligibility later.

### Decision

The warehouse should not silently drop a city-day only because one source is missing.

Rows may contain legitimate `NULL` values, with per-source flags showing source availability.

The model-preparation pipeline will apply its own filters for training, including requiring a valid AQHI target when needed.

The exact population mechanism will be implemented during transformation, using the project date range and city set as the base city-day grid.

---

## 9. Evacuation Data Grain

### Question

Should evacuation data be forced into the city-day fact, or stored separately?

Evacuation events span date ranges and are explicitly descriptive-only, not LSTM model inputs.

### Reasoning

An evacuation is an event, not a daily measurement.

Trying to force it into `fact_city_daily` would duplicate the event across multiple days or require artificial daily expansion.

That would add complexity to the model fact for data that is not intended for the model.

### Decision

Evacuations will be stored separately in:

`fact_evacuation_events`

Grain:

`one row per evacuation event`

The table will link to `dim_city` where a mapped project city is available.

Planned fields include:

- `event_id`
- `city_id`
- `location_name` or community name
- `start_date`
- `end_date`
- `status`
- source/citation field
- `last_verified_date`

The existing evacuation source fields should be preserved where useful, including the explicitly recorded related fire ID only when supported by the source.

---

## 10. Evacuation Status and End-Date Semantics

### Problem

`end_date = NULL` can represent more than one real-world situation:

- the evacuation is still ongoing
- the end date is unknown

Therefore, status must not be inferred from whether `end_date` is null.

### Decision

The `status` column is authoritative.

Examples:

```text
status = Ongoing
end_date = NULL
```

means the evacuation is still active based on the latest verified information.

```text
status = Unknown
end_date = NULL
```

means the available source material does not establish the current/end state.

A missing `end_date` alone must never be used to infer status.

---

## 11. Evacuation History vs Latest Known State

### Question

When an evacuation status changes, should the table preserve every historical version or update the existing event row?

### Options Considered

#### Option A: Versioned status history

Append a new record whenever the event status changes.

This would support "as of date X, what did we know?" analysis.

#### Option B: Latest known state

Update the same event record as new verified information becomes available.

### Reasoning

The current evacuation governance rule already states that updates modify the same event row.

There is no identified Tableau or analytical requirement yet for historical status snapshots.

Adding event versioning now would introduce unnecessary complexity.

### Decision

`fact_evacuation_events` will store the latest known state of each event.

Status-history versioning is deferred.

If Tableau later requires historical status reporting, a separate history table can be added without changing the basic event definition.

---

## 12. Ontario Active Fires Snapshot

### Problem

OWF-26 produced a live Ontario active-fires snapshot.

It is not a historical daily time series.

Loading the snapshot into `fact_city_daily` would imply temporal coverage that does not exist.

Backfilling the same snapshot across historical dates would be incorrect.

### Options Considered

#### Option A: Derive active-fire model features from the single snapshot

Rejected because it would not represent historical conditions for earlier city-days.

#### Option B: Keep the data descriptive and separate from the model fact

### Decision

`ontario_active_fires` will not feed `fact_city_daily` in the current scope.

The extracted data will still be loaded into:

`staging.ontario_active_fires`

A separate descriptive/reference snapshot table will be created outside the model fact.

Preferred working name:

`ref_active_fires_snapshot`

This naming avoids calling it a conventional star-schema fact when the current dataset is closer to a reference snapshot than a measurable historical fact series.

If recurring active-fire snapshots are collected in a future sprint, the design can be revisited and city-day features can be derived from the accumulated time series.

---

## 13. AQHI Target Columns

### Question

The AQHI data currently supports both:

- daily 4 PM AQHI
- daily maximum AQHI

Should the fact table immediately select one target, or keep both until EDA is complete?

### Decision

`fact_city_daily` will retain both:

- `aqhi_daily_4pm`
- `aqhi_daily_max`

Any relevant raw quality indicator such as the 10+ flag will also be preserved in an appropriate form.

EDA and model development will determine which AQHI definition becomes the final forecasting target.

---

## 14. Separate `aqhi_target` Column

### Question

After EDA selects the preferred AQHI target, should the warehouse add a third `aqhi_target` column that duplicates either `aqhi_daily_4pm` or `aqhi_daily_max`?

### Options Considered

#### Option A: Add `aqhi_target`

The model always reads one generic target field.

#### Option B: Keep the warehouse measurements unchanged and select the target in model configuration/preparation

### Reasoning

A separate `aqhi_target` would duplicate an existing measurement.

It would also require updating warehouse data if the modeling decision changes.

The selected target is a modeling/configuration decision, not a new source measurement.

### Decision

Do not add a duplicate `aqhi_target` column at this stage.

Keep both source-derived AQHI measures in the fact table.

The model-preparation/configuration layer will select the chosen target column after EDA.

---

## 15. `dim_date` and Fire-Season Fields

### Question

Should wildfire-specific calendar features such as `is_fire_season` be precomputed in `dim_date`?

### Reasoning

A calendar dimension is a reasonable place for reusable calendar attributes.

However, the fire-season definition should not be invented as a fixed month range without documentation. Fire season boundaries can depend on official definitions, year, and conditions.

### Decision

`dim_date` may include:

`is_fire_season`

but the field will remain nullable or unpopulated until a documented rule is selected.

The rule must be documented using the same confirmed/provisional discipline used elsewhere in the project.

A possible future feature such as `day_of_fire_season` can also be considered later, but it is not required for the initial DDL.

---

# Locked Schema

## Dimensions

### `dim_city`

Grain:

`one row per project city`

Planned fields:

- `city_id` PK
- `city_name`
- `region`
- `latitude`
- `longitude`

Expected current row count: 4.

---

### `dim_date`

Grain:

`one row per calendar date`

Planned fields:

- `date_id` PK
- `full_date`
- `year`
- `month`
- `day_of_week`
- `is_fire_season` nullable until rule is documented

Additional standard calendar fields may be added if they have a clear analytical use.

---

### `dim_station`

Grain:

`one row per source station`

Planned fields:

- `station_id` PK
- `source_station_id`
- `station_name`
- `source_system`
- `city_id` FK
- `latitude`
- `longitude`

Expected source systems include:

- `geomet`
- `aqo`
- `eccc_weather`

This is primarily a lineage/reference dimension and does not change the grain of `fact_city_daily`.

---

# Physical Staging Tables

Each staging table should closely mirror the corresponding extraction output.

Only minimal transformations should happen during staging load, mainly:

- type conversion
- standardized column naming where necessary
- source metadata preservation
- validation needed to make the table loadable/queryable

Business aggregation belongs after staging.

Planned staging tables:

### `staging.cwfis_hotspots`

Source grain: individual hotspot point event.

Purpose: preserve hotspot observations before distance-based city/day aggregation.

### `staging.aqhi_geomet_current`

Source grain: source station/time observation.

Purpose: preserve current GeoMet AQHI detail and source station lineage.

### `staging.aqhi_aqo_historical`

Source grain: station-day observation.

Purpose: preserve historical AQO values, both AQHI modes, and relevant source/raw quality flags.

### `staging.ontario_active_fires`

Source grain: fire record in a specific extraction snapshot.

Purpose: preserve OWF-26 active-fire snapshot records without treating them as a historical daily model feature.

### `staging.eccc_hourly_weather`

Source grain: station-hour.

Purpose: preserve hourly weather before daily city aggregation.

### `staging.evacuation_log`

Source grain: curated evacuation event.

Purpose: optional queryable staging checkpoint before loading `fact_evacuation_events`.

Because the evacuation CSV is already curated and small, this staging step is not strictly necessary from a data-cleaning perspective, but keeping it makes the source-to-staging-to-analytics pattern consistent.

---

# Fact and Descriptive Tables

## `fact_city_daily`

Grain:

`one row per (city_id, date_id)`

Primary purpose:

- EDA
- city-level wildfire/air-quality analysis
- LSTM model dataset foundation

Planned column groups:

### Keys

- `city_id` FK
- `date_id` FK

The pair must be unique and should be enforced with a database-level `UNIQUE (city_id, date_id)` constraint, not only treated as a conceptual grain rule.

### AQHI

- `aqhi_daily_4pm`
- `aqhi_daily_max`
- AQHI raw/quality flag(s), including the 10+ case if needed
- `aqhi_data_available`

### Hotspot-derived features

- `hotspots_within_100km`
- `hotspots_within_250km`
- `hotspots_within_500km`
- `nearest_hotspot_distance_km`
- `fire_data_available`

### Weather-derived features

- `temp_mean`
- `temp_min`
- `temp_max`
- `precip_total`
- `wind_speed_mean`
- `wind_dir_mean_deg`
- `weather_data_available`

The final weather and fire feature lists can be adjusted during transformation/EDA without changing the city-day grain.

### Explicit Exclusions

The current Ontario active-fires snapshot does not belong in this fact.

Evacuation events do not belong in this fact.

Station IDs do not define the fact grain.

---

## `fact_evacuation_events`

Grain:

`one row per evacuation event, latest known state`

Planned fields:

- `event_id` PK
- `city_id` FK where applicable
- `location_name` / community
- `start_date`
- `end_date` nullable
- `status`
- source/citation field
- `last_verified_date`
- other curated source fields where justified

Status is authoritative.

`end_date IS NULL` must not be used to infer whether the event is ongoing or unknown.

---

## `ref_active_fires_snapshot`

Grain:

`one row per fire per captured snapshot`

Current purpose:

- descriptive analysis
- Tableau context
- source validation/reference
- possible foundation for a future historical snapshot series

It is not currently a model input.

If future automation collects repeated snapshots, this table can evolve or feed derived city-day active-fire features later.

---

# Data Flow

The agreed data flow is:

```text
External source
    |
    v
data/raw
    |
    v
validation / cleaning
    |
    v
data/processed
    |
    v
PostgreSQL staging.*
    |
    v
source-specific transformations
    |
    +--> station/city mapping
    +--> Toronto AQHI aggregation
    +--> hourly weather to daily aggregation
    +--> hotspot distance/count aggregation
    +--> availability flag derivation
    |
    v
analytical dimensions / facts
    |
    +--> EDA
    +--> Tableau
    +--> model preparation
    |
    v
LSTM target/feature selection
```

The raw and processed file layers remain traceable and should not be overwritten by analytical transformations.

---

# DDL Implementation Order

Note: This section describes database structural dependencies only (e.g., dimensions must exist before facts due to foreign keys; staging must exist before transformation logic can read from it). It does not represent the planned Jira execution order. For the actual OWF-19 work sequence and ticket mapping, see the ticket-based execution order documented later in this file.

The DDL should be written and reviewed in this order:

## 1. Dimensions

- `dim_city`
- `dim_date`
- `dim_station`

These establish the reference keys needed by downstream analytical tables.

## 2. PostgreSQL Staging Schema and Tables

- create `staging` schema
- create the six staging tables

These should remain close to source grain and should not include city-day business aggregation.

## 3. Facts and Descriptive Tables

- `fact_city_daily`
- `fact_evacuation_events`
- `ref_active_fires_snapshot`

Facts are created after the required dimensions because they depend on dimension foreign keys.

---

# Transformation Rules to Preserve During Implementation

The following rules are considered part of the design and should not be changed silently during coding:

1. `fact_city_daily` is strictly city-day grain.
2. Station-level data is preserved before aggregation.
3. Toronto is eventually one city-level AQHI observation per day in the model fact.
4. The Toronto aggregation method remains an EDA decision.
5. Hourly ECCC weather is aggregated before loading the city-day fact.
6. CWFIS point hotspots are transformed into city-day exposure features before loading the city-day fact.
7. `NULL` represents unknown/unavailable data, not a true zero.
8. A true zero is stored as `0` when the source ran successfully and the measured quantity was zero.
9. Source availability flags are separate from the measured values.
10. Missing AQHI or weather values are never automatically converted to zero.
11. Evacuations are descriptive event data, not LSTM features.
12. Evacuation status is explicit and is not inferred from `end_date`.
13. Evacuation rows represent the latest known state; no status-history table is required yet.
14. Ontario active fires remain outside the model fact while only snapshot coverage exists.
15. Both AQHI daily definitions remain in the fact through EDA/model comparison.
16. The model-preparation layer selects the final AQHI target; the warehouse does not need a duplicate `aqhi_target`.
17. Fire-season logic must be documented before `is_fire_season` is populated.
18. `fact_city_daily` must enforce a database-level uniqueness constraint on `(city_id, date_id)` so that no city can have more than one analytical row for the same calendar date.

---

# Deferred Decisions

These are intentionally not resolved in the initial schema design.

## Toronto AQHI aggregation rule

Candidates include mean, maximum, or another justified method.

Decision point: AQHI EDA.

## Final AQHI forecasting target

Candidates:

- daily 4 PM AQHI
- daily maximum AQHI

Decision point: EDA and model-development comparison.

## Final fire feature set

The initial distance/count fields are reasonable candidates, but redundant or weak features may be removed after EDA.

## Final weather feature set

Daily aggregation logic will be defined during transformation. Additional fields may be added if supported by source coverage and model value.

## Fire-season definition

No fixed calendar rule will be assumed without documentation.

## Evacuation status history

Not needed in the current scope. Can be added if Tableau or audit requirements later require historical state tracking.

## Historical active-fire features

Not possible from the single current snapshot. Revisit only if recurring snapshots are collected.

---

# Known Data-Quality Constraints That Affect the Schema

The schema is designed to preserve these constraints instead of hiding them.

## GeoMet

Realtime/current coverage is limited and does not provide the full project history.

This is one reason source availability must be explicit.

## AQO

Historical AQHI has known boundary/quality behavior that should remain traceable through staging and raw flags.

Both daily AQHI modes are retained until EDA determines their role.

## CWFIS

A successful query that finds no hotspots is not the same as unavailable source data.

This drives the zero-vs-NULL rule.

## ECCC

The source is hourly while the analytical fact is daily.

The raw hourly observations remain available in staging so daily transformation logic is auditable.

## Ontario Active Fires

Current extraction is snapshot-based.

The schema must not imply a historical time series that was never collected.

## Evacuation Log

Some events are Ongoing and some remain Unknown.

A null end date therefore has no independent status meaning.

---


# OWF-19 Jira Scope Alignment

The OWF-19 implementation tickets should reflect the architecture documented here so that ticket scope, code changes, and commit references remain consistent.

Recommended ticket scope:

## OWF-30 — Finalize and document the star schema design

Scope:

- record the agreed grain and table boundaries
- document staging, dimension, fact, and descriptive/reference layers
- document NULL-versus-zero semantics
- document availability-flag rules
- document Toronto AQHI decision boundaries
- document evacuation status handling
- document active-fire snapshot exclusion from the model fact
- maintain this design note as the reference artifact

## OWF-31 — Create city, date, and station dimension tables

Scope:

- create `dim_city`
- create `dim_date`
- create `dim_station`
- define keys, constraints, source-qualified station identity, and foreign-key relationships needed by downstream tables

## OWF-33 — Create PostgreSQL staging schema and source-grain staging tables

This replaces the older extraction-script wording because the extraction scripts were completed during Sprint 1.

Scope:

- create PostgreSQL `staging` schema
- create `staging.cwfis_hotspots`
- create `staging.aqhi_geomet_current`
- create `staging.aqhi_aqo_historical`
- create `staging.ontario_active_fires`
- create `staging.eccc_hourly_weather`
- create `staging.evacuation_log`
- keep staging tables close to source grain with minimal transformation

## OWF-32 — Create analytical fact and descriptive tables

Scope:

- create `fact_city_daily`
- enforce uniqueness on `(city_id, date_id)`
- create `fact_evacuation_events`
- create `ref_active_fires_snapshot`
- define foreign keys and table-level constraints
- keep active-fire snapshots and evacuation events outside the LSTM model fact

## OWF-34 — Write staging-to-analytics cleaning and transformation logic

Scope:

- aggregate hourly ECCC weather to city-day
- calculate CWFIS hotspot distance/count features
- aggregate Toronto AQHI to city-day using the rule selected through EDA
- derive source availability flags
- preserve NULL-versus-zero semantics
- map source stations and cities consistently
- prepare data for analytical-table loading

## OWF-35 — Load and populate PostgreSQL analytical tables

Scope:

- populate dimensions
- load validated source data into staging
- run transformations
- populate `fact_city_daily`
- populate `fact_evacuation_events`
- populate `ref_active_fires_snapshot`
- verify row counts and referential integrity

## OWF-36 — Add data-quality checks

Scope:

- duplicate checks
- `(city_id, date_id)` uniqueness validation
- missing-value checks
- availability-flag consistency checks
- date-coverage checks
- invalid-value/range checks
- foreign-key integrity checks
- zero-versus-NULL semantic checks where applicable

## OWF-37 — Create EDA notebook with coverage summaries and distribution checks

Scope:

- source/date coverage
- missingness patterns
- Toronto station/zone variance
- AQHI 4 PM versus daily-max comparison
- weather/fire feature distributions
- candidate feature diagnostics

## OWF-38 — Review the initial wildfire–AQHI relationship without making a causal claim

Scope:

- exploratory association only
- compare AQHI with wildfire exposure features
- document limitations and confounding factors
- avoid causal interpretation

Recommended implementation order:

```text
OWF-30  Design documentation
   |
   v
OWF-31  Dimensions
   |
   v
OWF-33  PostgreSQL staging schema/tables
   |
   v
OWF-32  Fact and descriptive/reference table DDL
   |
   v
OWF-34  Transformations
   |
   v
OWF-35  Load/populate analytical tables
   |
   v
OWF-36  Data-quality validation
   |
   v
OWF-37  EDA
   |
   v
OWF-38  Initial wildfire–AQHI relationship review
```

The ticket numbering does not need to match execution order. The important requirement is that each ticket title and description accurately describe the work that is committed under that ticket.


# Final Design Position

OWF-19 will use a layered database design rather than loading extraction outputs directly into a single fact table.

The database will preserve source grain in PostgreSQL staging, maintain explicit city, date, and station reference dimensions, and create a main city-day fact aligned with the forecasting target.

The schema deliberately separates:

- model-ready daily measures
- source-grain staging data
- event-based descriptive impact data
- snapshot-only descriptive fire data

The design prioritizes traceability over shortcuts and avoids filling temporal or data-quality gaps with assumptions.

The next implementation step is to write and review the DDL for:

1. `dim_city`
2. `dim_date`
3. `dim_station`
4. the `staging` schema
5. the six staging tables

After those are reviewed against this document, the fact and descriptive tables can be implemented.
