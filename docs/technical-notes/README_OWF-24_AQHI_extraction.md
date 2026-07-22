# OWF-24 - Current AQHI Extraction from ECCC GeoMet

## Overview

This stage implements the current Air Quality Health Index (AQHI) extraction workflow for the **Ontario Wildfire Impact and Forecasting Analytics** project.

The goal of OWF-24 was to:

- understand how AQHI data is exposed by Environment and Climate Change Canada (ECCC);
- confirm which reporting locations are available for the four project cities;
- determine the actual time window retained by the realtime collection;
- build a repeatable extraction script;
- preserve all hourly observations for the selected locations;
- validate the extracted data before committing the work.

This task focuses only on **current/recent AQHI observations**. Historical AQHI data required for model training will be collected separately in **OWF-25**.

---

## Source Selected

The extraction uses the ECCC GeoMet OGC API - Features collection:

```text
https://api.weather.gc.ca/collections/aqhi-observations-realtime/items
```

The collection returns AQHI observations as GeoJSON features.

Each feature contains:

- a `geometry` section with longitude and latitude;
- a `properties` section with the location ID, location name, AQHI value, observation timestamp, and other metadata.

This was a better fit than WMS or WCS because the project requires clean, row-level station/location observations rather than map images or raster grids.

Official references:

- [GeoMet AQHI observations collection](https://api.weather.gc.ca/collections/aqhi-observations-realtime/items?f=html)
- [GeoMet OGC API technical documentation](https://eccc-msc.github.io/open-data/msc-geomet/ogc_api_en/)
- [Government of Canada AQHI scale](https://www.canada.ca/en/environment-climate-change/services/air-quality-health-index/about.html)

---

## Initial API Inspection

Before writing the extraction function, a small browser request was used to inspect the response structure:

```text
https://api.weather.gc.ca/collections/aqhi-observations-realtime/items?bbox=-95.5,41.5,-74.0,57.0&limit=5&f=json
```

The response confirmed that:

- the collection returns a GeoJSON `FeatureCollection`;
- observations are hourly;
- each observation has a unique ID;
- `location_id` can be used as a stable location identifier;
- `location_name_en` provides a readable location name;
- `observation_datetime` is provided in UTC;
- `aqhi` is numeric;
- coordinates are stored in GeoJSON order: longitude, latitude;
- pagination uses `limit` and `offset`;
- the response includes `numberMatched` and `numberReturned`.

A sample observation contained fields such as:

```text
location_id: FCWYG
location_name_en: Toronto Downtown
observation_datetime: 2026-07-19T23:00:00Z
aqhi: 3.22
latest: false
```

---

## Exploration Script

An exploratory script was created:

```text
src/etl/explore_aqhi_geomet.py
```

Its purpose was to answer two questions before building the final extractor:

1. Which AQHI locations are actually available inside the Ontario bounding box?
2. What is the real date coverage of the collection?

The script:

- requested all observations inside the approximate Ontario bounding box;
- paginated using `limit=500` and increasing `offset` values;
- extracted `location_id`, `location_name_en`, longitude, and latitude;
- created a distinct location list;
- converted `observation_datetime` to UTC datetime values;
- calculated the minimum and maximum available timestamps;
- ran basic missing-value and duplicate checks.

The discovery output was saved as:

```text
data/raw/aqhi_geomet_location_discovery.csv
```

---

## Exploration Results

The first full exploration returned:

```text
Total records retrieved: 2706
Distinct locations: 41
Earliest observation: 2026-07-19 00:00:00+00:00
Latest observation:   2026-07-21 17:00:00+00:00
```

Validation results:

```text
Missing location IDs: 0
Missing location names: 0
Missing AQHI values: 0
Missing observation dates: 0
Duplicate observation IDs: 0
```

This confirmed that the realtime collection retained only a short rolling window rather than a long historical series.

### Actual realtime window

The final extraction later covered:

```text
2026-07-19 00:00:00+00:00
to
2026-07-22 00:00:00+00:00
```

This is approximately three days of hourly observations.

The result confirmed an important architectural decision:

- **GeoMet realtime AQHI** will support current and recurring pipeline updates.
- **Air Quality Ontario historical data** will be required for the deeper historical backfill and model training in OWF-25.

The realtime collection cannot provide enough historical data for LSTM training by itself.

---

## Selected Project Locations

Three project cities had one clear AQHI location:

| City | `location_id` | `location_name_en` |
|---|---|---|
| Barrie | `FAFFD` | Barrie |
| Kingston | `FEVJR` | Kingston |
| Thunder Bay | `FCWFX` | Thunder Bay |

Toronto had five available locations:

| Project city | `location_id` | `location_name_en` |
|---|---|---|
| Toronto | `FEUZB` | Toronto |
| Toronto | `FCWYG` | Toronto Downtown |
| Toronto | `FDQBU` | Toronto East |
| Toronto | `FDQBX` | Toronto North |
| Toronto | `FCKTB` | Toronto West |

The final extraction therefore includes eight AQHI locations representing four project cities.

---

## Toronto Design Decision

Toronto has meaningful spatial variation and multiple AQHI reporting locations. A single representative location was not selected during extraction.

The five Toronto locations are kept as separate raw records because:

- selecting one location immediately would create an unsupported assumption;
- averaging all five locations during extraction would remove spatial detail;
- the realtime window is too short to determine whether the locations behave similarly;
- keeping the raw detail allows later comparison during exploratory data analysis;
- the decision can be supported by historical completeness, correlations, high-AQHI events, and geographic patterns.

All five locations receive:

```text
city = Toronto
```

Their individual `location_id` and `location_name_en` values are retained.

Possible later decisions during EDA include:

- retaining all Toronto sub-locations separately;
- calculating a Toronto daily average;
- calculating a Toronto daily maximum;
- selecting one representative location;
- using different Toronto zones in the dashboard.

No aggregation decision has been made yet.

---

## Unconfirmed Meaning of `FEUZB`

The location:

```text
FEUZB — Toronto
```

has a general name, but it has not been confirmed whether it represents:

- a city-wide AQHI aggregate;
- a specific individual reporting location;
- a reporting zone connected to one or more physical monitoring stations.

The name `Toronto` alone is not sufficient evidence that it is a city-wide average.

Therefore, FEUZB is currently treated as one separate Toronto location, not as the authoritative city-level AQHI value.

This will be investigated later using the AQHI station metadata and the historical Air Quality Ontario source.

---

## First Server-Side Filtering Attempt

After discovering the eight required location IDs, the first extraction design attempted to reduce the API response using a CQL2 `IN` filter:

```text
location_id IN ('FAFFD','FEVJR','FCWFX','FEUZB','FCWYG','FDQBU','FDQBX','FCKTB')
```

The request also included:

```text
filter-lang=cql2-text
```

### Error received

The API returned:

```text
HTTP 400
Invalid filter language
```

### Diagnosis

The request failed before any observations were processed. The server rejected the supplied filter-language parameter.

### First correction

The following changes were made:

- removed `filter-lang=cql2-text`;
- changed the field reference to `properties.location_id`;
- retained the `IN (...)` expression.

The corrected filter was:

```text
properties.location_id IN ('FAFFD','FEVJR','FCWFX','FEUZB','FCWYG','FDQBU','FDQBX','FCKTB')
```

---

## Second Server-Side Filtering Attempt

The corrected request no longer produced an HTTP error.

However, it returned:

```text
Total records retrieved: 0
```

This was important because a successful HTTP response does not automatically mean the filter worked as intended.

The selected location IDs had already been verified through the exploration pull, so zero records did not indicate that the locations were absent. It indicated that the multi-location server-side filter was not producing the expected result for this collection.

---

## Final Filtering Solution

The final implementation uses:

1. a bounding-box request that was already proven to work;
2. full pagination through the available Ontario-area observations;
3. client-side filtering in pandas/Python using the eight confirmed `location_id` values.

The final logic is:

```text
GeoMet bbox extraction
        ↓
paginate through all available records
        ↓
inspect each feature
        ↓
keep only records whose location_id is in SELECTED_LOCATIONS
        ↓
add longitude, latitude, and project city
        ↓
validate
        ↓
save raw CSV
```

### Why client-side filtering was chosen

Client-side filtering was selected because:

- the bounding-box query had already been tested successfully;
- the eight location IDs had already been confirmed from the live API;
- the CQL2 `IN` attempt first failed and then returned zero matches;
- the realtime collection is small enough for the bounding-box pull to remain practical;
- the logic is transparent and easy to validate;
- it avoids silently trusting a server-side filter that returned an incorrect empty result.

This is a deliberate reliability decision, not an accidental workaround.

The code should be revisited later if a verified server-side location filter becomes available.

---

## Final Extraction Script

The production-oriented OWF-24 extraction script is:

```text
src/etl/extract_current_aqhi.py
```

The script:

- requests all current AQHI observations inside the approximate Ontario bounding box;
- uses `limit=500`;
- paginates with `offset`;
- checks HTTP errors;
- prints the encoded request URL for troubleshooting;
- reads each GeoJSON feature;
- filters records using the selected location IDs;
- extracts longitude and latitude from `geometry`;
- adds a project-level `city` column;
- converts `observation_datetime` to a UTC pandas datetime;
- sorts the data by time, city, and location ID;
- validates location coverage;
- validates missing values;
- checks duplicate observation IDs and complete rows;
- saves the result only when records are returned.

The raw output file is:

```text
data/raw/aqhi_geomet_current.csv
```

---

## Final Extraction Results

The successful final run returned:

```text
Total API records inside bbox: 2993
Selected project records: 584
Number of columns: 16
Expected AQHI locations: 8
Returned AQHI locations: 8
Distinct project cities: 4
```

Every selected location had exactly 73 hourly observations:

| City | Location | Records |
|---|---|---:|
| Barrie | Barrie | 73 |
| Kingston | Kingston | 73 |
| Thunder Bay | Thunder Bay | 73 |
| Toronto | Toronto | 73 |
| Toronto | Toronto Downtown | 73 |
| Toronto | Toronto East | 73 |
| Toronto | Toronto North | 73 |
| Toronto | Toronto West | 73 |

The counts reconcile:

```text
8 locations × 73 hourly observations = 584 rows
```

The full bounding-box result also reconciles:

```text
41 locations × 73 hourly observations = 2993 rows
```

This consistency provides a strong completeness check for the final pull.

---

## Final Date Coverage

The successful final extraction covered:

```text
Earliest observation: 2026-07-19 00:00:00+00:00
Latest observation:   2026-07-22 00:00:00+00:00
```

The difference is 72 hours. Including both endpoints gives 73 hourly observations per location.

This confirms that, at the time of the run, the realtime collection contained approximately three days of data.

Because this is a live collection, the row count and date window may change between executions.

---

## Final Validation Results

The final validation checks returned:

```text
Number of rows: 584
Number of columns: 16

Missing city values: 0
Missing location IDs: 0
Missing location names: 0
Missing AQHI values: 0
Missing observation dates: 0
Missing longitude values: 0
Missing latitude values: 0

Duplicate observation IDs: 0
Duplicate full rows: 0

Distinct AQHI locations: 8
Distinct project cities: 4

Missing expected location IDs: []
Unexpected location IDs: []
```

These results confirm that:

- all eight expected locations were present;
- no unexpected locations entered the final dataset;
- the required analytical fields were complete;
- every observation ID was unique;
- there were no duplicated complete rows.

---

## Thunder Bay High-AQHI Observation

The extracted data included a raw AQHI value of:

```text
Thunder Bay AQHI = 11.00
```

The public Canadian AQHI scale reports values above 10 as:

```text
10+ : Very High Health Risk
```

The value appeared in consecutive hourly observations, so it represents a sustained high-AQHI episode within the short extracted window rather than one isolated row.

However, this observation is not treated as proof that:

- wildfire smoke was the sole cause;
- the full 2026 wildfire season was above average;
- Thunder Bay experienced identical conditions across the entire city.

The episode will be cross-checked later against:

- CWFIS hotspot activity;
- active-fire data;
- smoke and air-quality alerts;
- historical AQHI patterns;
- weather and wind conditions.

GeoMet realtime AQHI values are treated as preliminary observations and should be presented with an appropriate quality-control limitation.

---

## Output Schema

The final DataFrame contains 16 columns:

```text
location_name_fr
observation_datetime_text_en
observation_datetime_text_fr
location_name_en
location_id
observation_type
special_notes_en
aqhi_type
special_notes_fr
observation_datetime
id
aqhi
latest
longitude
latitude
city
```

Important analytical fields include:

| Field | Purpose |
|---|---|
| `id` | Unique observation identifier |
| `city` | Project-level city grouping |
| `location_id` | Stable GeoMet location identifier |
| `location_name_en` | Detailed reporting location name |
| `observation_datetime` | UTC observation timestamp |
| `aqhi` | Raw AQHI value |
| `latest` | GeoMet flag identifying a latest observation |
| `longitude` | Location longitude |
| `latitude` | Location latitude |

---

## Raw Data Decision

All hourly observations are preserved.

The extraction does not:

- aggregate hourly values into daily values;
- average Toronto locations;
- choose one Toronto representative;
- filter only `latest=true`;
- remove high AQHI values;
- infer wildfire causation;
- merge GeoMet with historical station data.

These decisions belong in later transformation and EDA stages.

---

## Current File Behaviour

The output file currently uses a fixed name:

```text
data/raw/aqhi_geomet_current.csv
```

This means a later run will overwrite the previous snapshot.

This is acceptable during development, but the scheduled Airflow workflow should later use one of these approaches:

1. save timestamped snapshots; or
2. load observations into a database and use `id` as the deduplication/upsert key.

The observation `id` is the preferred natural key because the validation showed it was unique.

---

## Known Limitations

### 1. Short retention window

The realtime collection retained only approximately three days during testing.

It is suitable for current updates, not historical training.

### 2. Live data changes

The number of records can change between runs as new hourly observations are added and older observations leave the rolling window.

For example:

```text
Initial exploration: 2706 bbox records
Final extraction:    2993 bbox records
```

This increase occurred because the live collection was updated between executions.

### 3. Client-side filtering

The script downloads all records inside the bounding box and filters the selected locations locally.

This is reliable for the current data volume but is less bandwidth-efficient than a working server-side filter.

### 4. Toronto representation is unresolved

The project retains five Toronto locations, and no city-wide aggregation method has been selected yet.

### 5. FEUZB meaning is unresolved

It has not been confirmed whether FEUZB is a city-wide aggregate or an individual reporting location.

### 6. Realtime quality control

Realtime values should be treated as preliminary and validated when used for important analytical claims.

### 7. AQHI does not establish causation

A high AQHI value does not independently prove that wildfire smoke caused the event. Fire, smoke, weather, and historical data must be combined before making causal statements.

---

## Lessons Learned

### Inspect the real API before designing the extractor

The browser sample exposed the actual field names, pagination structure, location identifiers, and hourly time resolution.

### A successful HTTP response can still produce an incorrect result

The second CQL2 request returned HTTP success but zero rows. The result had to be evaluated against previously verified station availability.

### Separate extraction from transformation

The raw layer should preserve hourly observations and Toronto sub-location detail. Aggregation belongs later.

### Validate assumptions with data

The GeoMet collection was called realtime, but its actual retained period was measured directly rather than assumed.

### Preserve uncertainty explicitly

The meaning of FEUZB and the correct Toronto aggregation method remain open questions and are documented instead of hidden.

### Live sources require reproducible checks

Counts and date coverage can change between runs. Pagination, location coverage, uniqueness, and missing-value checks must run every time.

---

## OWF-24 Completion Criteria

OWF-24 is considered technically complete when:

- [x] the GeoMet AQHI API structure is understood;
- [x] all available Ontario-area locations are explored;
- [x] the four project cities are confirmed;
- [x] the eight selected location IDs are documented;
- [x] the short realtime window is measured;
- [x] the Toronto multi-location decision is documented;
- [x] FEUZB uncertainty is documented;
- [x] pagination is implemented and tested;
- [x] the CQL2 errors and correction path are documented;
- [x] client-side filtering is implemented;
- [x] all expected locations are returned;
- [x] validation checks pass;
- [x] the raw CSV is saved successfully;
- [ ] the final code and documentation are committed to GitHub.

---
