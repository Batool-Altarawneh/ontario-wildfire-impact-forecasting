# Ontario Wildfire Impact and Forecasting Analytics

## Project Status

This is an academic and independent portfolio project focused on the relationship between wildfire activity, air quality, and community impact in Ontario. The current work is part of Sprint 1, Data Foundation and Airflow DAG.

The first completed technical task in this sprint was the extraction of CWFIS wildfire hotspot data.

## CWFIS Hotspot Extraction

### Task

**Jira ticket:** OWF-23  
**Script:** `src/etl/extract_cwfis_hotspots.py`  
**Output folder:** `data/raw`

The goal of this task was to build a reusable Python extraction function that retrieves wildfire hotspot records from the Canadian Wildland Fire Information System and returns the results as a pandas DataFrame.

The extraction needed to support:

1. A user-defined date range
2. Geographic filtering
3. Pagination for large result sets
4. Basic request and response validation
5. Saving the raw output as a CSV file

## Understanding the Data Source

CWFIS provides geospatial data through a Web Feature Service rather than a typical REST API. A WFS request specifies the service version, request type, data layer, output format, and optional server-side filters.

The public endpoint used in this task is:

```text
https://cwfis.cfs.nrcan.gc.ca/geoserver/public/wfs
```

The selected layer is:

```text
public:hotspots
```

This layer was chosen because it contains timestamped satellite-detected hotspot records. It is more suitable for daily fire-activity analysis than a current active-fire snapshot because it supports date-range queries and can later be aggregated by day and geographic area.

A hotspot should not be interpreted as one confirmed wildfire. A large wildfire may produce many hotspot observations across different satellite passes and locations.

## Initial Design Decisions

### Geographic scope

The extraction uses an approximate rectangular bounding box that covers Ontario with a small buffer:

```text
Minimum latitude: 41.5
Maximum latitude: 57.0
Minimum longitude: -95.5
Maximum longitude: -74.0
```

The bounding box is applied on the CWFIS server through the query filter. This reduces the amount of unrelated data downloaded from the full CWFIS layer.

### Date range

The first small test used:

```text
2026-07-01 to 2026-07-03
```

After the extraction and pagination logic were validated, the full raw pull used:

```text
2026-01-01 to 2026-07-20
```

January 1 is treated as the extraction start date. It is not being presented as the official start of Ontario's wildfire season. The final modeling period will be selected after the data is geographically cleaned and reviewed during exploratory analysis.

### Raw versus processed data

The extraction script is intentionally limited to data collection. It does not calculate distances to cities, create modeling features, or apply the exact Ontario boundary polygon.

Those steps belong in the transformation stage so the raw file remains unchanged and traceable to the original source.

## Implementation

The script imports:

```python
import requests
import pandas as pd

from datetime import datetime
from pathlib import Path
```

The main parts of the script are:

### Configuration

The WFS endpoint, hotspot layer name, and geographic boundaries are stored as named constants at the top of the file. This makes the source and extraction scope easy to find and change.

### Date validation

The `check_date_format()` function confirms that dates are entered using the `YYYY-MM-DD` format. It also allows the main extraction function to check that the start date is not later than the end date.

### Server-side filter

The script builds a CQL filter containing:

1. Start timestamp
2. End timestamp
3. Minimum and maximum latitude
4. Minimum and maximum longitude

The filtering is completed by GeoServer before the records are sent to the local machine.

### WFS request parameters

The request uses:

```text
service = WFS
version = 2.0.0
request = GetFeature
typeNames = public:hotspots
outputFormat = application/json
```

The response is GeoJSON. Each feature contains geometry and properties. The script extracts only the `properties` section because it already includes plain `lat` and `lon` fields along with the hotspot attributes.

### Pagination

The layer contains many records, so a single request is not enough for a full season pull. The script uses:

```text
count
startIndex
sortBy
```

`count` controls the number of records requested per page. `startIndex` identifies where the next page begins. `sortBy` provides a stable order so records are not skipped or repeated across pages.

The final ordering is:

```text
rep_date ascending, uid ascending
```

### Error handling

The request uses a timeout and checks the HTTP response. If the server rejects a request, the script prints the response status and the detailed GeoServer message before raising the error.

This was important during debugging because the server returned a useful XML exception message that was not visible in the original traceback alone.

### Output

The final DataFrame is saved to the raw data folder. The file name includes the geographic scope and selected date range:

```text
cwfis_hotspots_ontario_bbox_2026-01-01_to_2026-07-20.csv
```

The raw CSV is excluded from GitHub because it is generated data and is relatively large. The extraction script remains in version control so the dataset can be reproduced.

## Errors and Corrections

### Error 1: HTTP 400 response

The first paginated request returned an HTTP 400 error. The original traceback showed that the request failed but did not clearly explain why.

To improve debugging, the script was updated to print:

```python
response.status_code
response.text
```

before calling `response.raise_for_status()`.

### Error 2: Pagination without a stable order

The detailed GeoServer message was:

```text
Cannot do natural order without a primary key, please add it or specify a manual sort over existing attributes
```

The problem was not the internet connection, date range, or bounding box. The problem was that pagination used `startIndex`, but the layer did not provide a primary key that GeoServer could use for natural ordering.

The correction was to add a manual sort:

```python
"sortBy": "rep_date A,uid A"
```

This gave the server a stable order for every page.

### Pagination validation

Pagination was tested intentionally with a page size of 1,000 records for the three-day test period.

The requests returned:

```text
Page 1: 1,000 records
Page 2: 1,000 records
Page 3: 1,000 records
Page 4:   947 records
Total:  3,947 records
```

The total matched the result from the earlier single-page test, confirming that the pagination logic did not lose or duplicate records.

## Test Results

### Three-day test

**Date range:** July 1 to July 3, 2026  
**Rows:** 3,947  
**Columns:** 39

Validation results:

```text
Missing latitude values: 0
Missing longitude values: 0
Missing report dates: 0
Duplicate full rows: 0
Duplicate UID values: 0
Unique UID values: 3,947
```

The test also confirmed that the returned schema contains useful groups of fields.

### Location and time

```text
lat
lon
rep_date
rep_day
uid
```

### Satellite and source information

```text
source
sensor
satellite
agency
```

### Weather fields attached to hotspot records

```text
temp
rh
ws
wd
pcp
```

### Canadian Fire Weather Index fields

```text
ffmc
dmc
dc
isi
bui
fwi
```

### Additional fire behaviour fields

```text
ros
sfc
tfc
hfi
frp
estarea
```

The weather fields describe conditions associated with the hotspot location. They should not automatically be treated as weather conditions at Toronto, Kingston, Barrie, or Thunder Bay. Their completeness and suitability as model inputs will be evaluated later.

## Full Extraction Results

**Extraction range:** January 1 to July 20, 2026  
**Rows:** 161,729  
**Columns:** 39

Validation results:

```text
Earliest returned timestamp: 2026-01-01T19:19:00Z
Latest returned timestamp:   2026-07-20T20:36:00Z
Minimum latitude:  41.500034
Maximum latitude:  56.999890
Minimum longitude: -95.498870
Maximum longitude: -74.000110
Missing latitude values: 0
Missing longitude values: 0
Missing report dates: 0
Duplicate full rows: 0
Duplicate UID values: 0
Unique UID values: 161,729
```

The extraction completed successfully across more than 160 pages when using a page size of 1,000 records.

## Geographic Limitation Discovered

The first full-range records included agency codes such as `IA` and `MN`, with coordinates located in Iowa and Minnesota.

This happened because a rectangular bounding box can only approximate Ontario's real shape. The selected rectangle covers the province, but it also includes parts of nearby U.S. states and Canadian provinces that share the same latitude and longitude range.

This is a geographic filtering limitation, not an extraction bug. The query returned exactly what the bounding-box conditions requested.

The current raw file must therefore be described as:

```text
Ontario bounding-box hotspot extract
```

It should not yet be described as an Ontario-only hotspot dataset.

## Final Decision for This Stage

The raw extraction will remain unchanged. Exact province filtering will be completed in a separate transformation script using an Ontario boundary polygon.

The transformation stage will:

1. Convert the latitude and longitude fields into geographic point objects
2. Load an official or reliable Ontario boundary polygon
3. Keep only points located inside the province
4. Calculate the earliest observed Ontario hotspot date in the filtered dataset
5. Create city-level distance features
6. Compare different distance bands during exploratory analysis

Possible later features include:

```text
hotspots_within_100km
hotspots_within_250km
hotspots_within_500km
nearest_hotspot_distance
hotspots_in_northwestern_ontario
total_hotspots_in_ontario
```

The final model will not automatically use every proposed feature. Their distributions, missing values, and relationships with AQHI will be evaluated first.

## Final Outcome

OWF-23 produced a working and reusable CWFIS hotspot extraction script with:

1. Date validation
2. Server-side date filtering
3. Server-side bounding-box filtering
4. Paginated WFS requests
5. Stable sorting across pages
6. Clear request error reporting
7. GeoJSON property extraction
8. DataFrame output
9. Basic validation checks
10. Raw CSV export

The extraction logic is complete and tested. The remaining geographic cleanup belongs to the transformation stage and does not require changing the raw extraction design.

## Files for This Task

```text
src/etl/extract_cwfis_hotspots.py
data/raw/cwfis_hotspots_ontario_bbox_2026-01-01_to_2026-07-20.csv
```

The CSV file is generated locally and should remain excluded from GitHub.


