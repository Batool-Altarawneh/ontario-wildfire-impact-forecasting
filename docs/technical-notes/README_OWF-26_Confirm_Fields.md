# OWF-26: Ontario Active Fire Data Extraction and Validation

## Work Item

**Jira ID:** OWF-26  
**Title:** Extract Ontario active fire data  
**Project:** Ontario Wildfire Impact and Forecasting Analytics  
**Sprint:** Sprint 1: Data and Airflow  
**Status:** Ready to close  
**Primary implementation date:** July 31, 2026  
**Validation completed:** August 2, 2026

\---

## 1\. Purpose

The purpose of OWF-26 was to build a reliable extraction process for Ontario wildfire records and produce an analysis-ready active-fire dataset for the wider Ontario Wildfire Impact and Forecasting Analytics project.

The work was not limited to downloading a CSV. I needed to understand the Ontario source, identify the available fields, preserve the original source values, interpret coded fields carefully, separate confirmed mappings from provisional mappings, validate the output, and investigate values that could indicate source or processing errors.

The final implementation:

* Downloads all Ontario fire records from the Ontario ArcGIS REST service.
* Uses pagination so the script remains safe if the number of records grows.
* Requests GeoJSON and extracts point geometry.
* Preserves the original source columns.
* Adds cleaned and analysis-friendly columns without overwriting the source values.
* Converts source timestamps from epoch milliseconds to UTC datetimes.
* Separates confirmed status labels from provisional status labels.
* Produces an active-only dataset.
* Creates code-frequency and validation reports.
* Flags undocumented and sentinel values rather than silently replacing them.
* Uses a separate validation script to inspect the largest reported fire-size value.

This README documents the objective, the source investigation, every major problem, the attempted solutions, the final code decisions, the mapping dictionaries, the confidence assigned to each interpretation, the output files, the result of each step, the remaining limitations, and the final outcome.

\---

## 2\. Scope

OWF-26 covers extraction and validation of Ontario fire records.

The scope includes:

1. Identify a usable Ontario government fire-data endpoint.
2. Download all available records.
3. Preserve raw source data.
4. Create cleaned columns for analysis.
5. Identify which fire records should be included in the active-fire output.
6. Document confirmed, provisional, and unresolved code meanings.
7. Generate validation and code-frequency reports.
8. Review the maximum fire-size value to determine whether it is a legitimate extreme observation or a processing error.
9. Save timestamped outputs so snapshots are not overwritten.

The scope does not include:

* Building a recurring Airflow DAG.
* Forecasting fire spread.
* Updating the source records.
* Correcting values inside the Ontario source.
* Forcing Ontario-specific values into national code categories.
* Inferring undocumented meanings for `MNP`, `MDP`, or `-1`.

Recurring scheduling should be handled in a separate task so extraction logic and orchestration remain separate concerns.

\---

## 3\. Final File Structure

The implementation uses the following repository files and output locations.

```text
src/
└── etl/
    ├── extract\_ontario\_active\_fires.py
    └── check\_largest\_ontario\_fire.py

data/
├── raw/
│   └── ontario\_active\_fires/
│       └── ontario\_fires\_raw\_20260731T045931Z.csv
├── processed/
│   └── ontario\_active\_fires/
│       ├── ontario\_fires\_cleaned\_20260731T045931Z.csv
│       └── ontario\_active\_fires\_20260731T045931Z.csv
└── quality/
    └── ontario\_active\_fires/
        ├── ontario\_fire\_code\_frequency\_20260731T045931Z.csv
        └── ontario\_fire\_validation\_20260731T045931Z.csv
```

### Main files

|File|Purpose|
|-|-|
|`src/etl/extract\_ontario\_active\_fires.py`|Downloads, cleans, interprets, validates, and saves Ontario fire records.|
|`src/etl/check\_largest\_ontario\_fire.py`|Reads the cleaned snapshot and prints the record with the largest fire size for manual validation.|
|`data/raw/ontario\_active\_fires/ontario\_fires\_raw\_20260731T045931Z.csv`|Raw snapshot with source fields and extraction metadata.|
|`data/processed/ontario\_active\_fires/ontario\_fires\_cleaned\_20260731T045931Z.csv`|Full cleaned snapshot containing all 641 records.|
|`data/processed/ontario\_active\_fires/ontario\_active\_fires\_20260731T045931Z.csv`|Active-only output containing confirmed active statuses plus provisional `BM`.|
|`data/quality/ontario\_active\_fires/ontario\_fire\_code\_frequency\_20260731T045931Z.csv`|Frequency table for stage, cause, response, and agency codes.|
|`data/quality/ontario\_active\_fires/ontario\_fire\_validation\_20260731T045931Z.csv`|Validation results for row counts, missing values, duplicates, sizes, and mapping confidence.|

\---

## 4\. Source Selection

### 4.1 Selected source

The selected source is the Ontario Ministry of Natural Resources ArcGIS REST service.

Service directory:

```text
https://ws.lioservices.lrc.gov.on.ca/arcgis1061a/rest/services/MNRF/Ontario\_Fires\_Map/MapServer
```

Selected layer:

```text
https://ws.lioservices.lrc.gov.on.ca/arcgis1061a/rest/services/MNRF/Ontario\_Fires\_Map/MapServer/0
```

Query endpoint used by the script:

```text
https://ws.lioservices.lrc.gov.on.ca/arcgis1061a/rest/services/MNRF/Ontario\_Fires\_Map/MapServer/0/query
```

### 4.2 Why Layer 0 was selected

The service contains several layers, including general Ontario fires and status-based layers such as active, out, and new fires.

I selected Layer 0 as the primary extraction source because:

* It was directly tested.
* It returned the complete set of fire records in one consistent schema.
* It included all important fire attributes.
* It allowed me to classify active records using the returned stage-of-control field.
* It avoided depending on separate filtered layers that could use undocumented filter rules.
* It made the raw-to-cleaned lineage easier to explain.

The status-specific layers can still be used later for comparison, but they were not required for the primary extraction.

### 4.3 Verified service capabilities

The ArcGIS service reports:

* `MaxRecordCount = 5000`
* GeoJSON support
* Advanced query support
* `orderBy` support
* Pagination support
* Point geometry

The selected Ontario Fires layer exposes fields including:

* `OBJECTID`
* `FIELD\_LOCATION`
* `FIELD\_LATITUDE`
* `FIELD\_LONGITUDE`
* `FIELD\_AGENCY\_FIRE\_ID`
* `FIELD\_FIRE\_SIZE`
* `FIELD\_AGENCY\_FIRE\_CAUSE`
* `FIELD\_SYSTEM\_FIRE\_CAUSE`
* `FIELD\_SITUATION\_REPORT\_DATE`
* `FIELD\_STATUS\_DATE`
* `FIELD\_AGENCY\_DATA\_TIMEZONE`
* `FIELD\_STAGE\_OF\_CONTROL\_STATUS`
* `FIELD\_PERCENT\_CONTAINED`
* `FIELD\_RESPONSE\_TYPE`
* `FIELD\_SEVERITY\_NEAREST\_DSR`
* `FIELD\_FIRE\_WAS\_PERSCRIBED`
* `FIELD\_AGENCY\_PREPARE\_LEVEL`
* `FIELD\_FIRE\_TYPE\_ICS`
* `FIELD\_AGENCY\_CODE`
* `REFRESHED\_DATETIME`

The service metadata does not publish coded-value domains for the status, cause, or response fields. Because of that, code interpretation required separate documentation review and empirical validation.

\---

## 5\. Data Flow

The final process is:

```text
Ontario ArcGIS REST Layer 0
        |
        v
fetch\_all\_fire\_records()
        |
        v
Raw pandas DataFrame
        |
        +------------------------------+
        |                              |
        v                              v
build\_cleaned\_dataset()      build\_code\_frequency\_report()
        |                              |
        v                              v
Cleaned DataFrame             Code-frequency DataFrame
        |
        v
build\_validation\_report()
        |
        v
Validation DataFrame
        |
        v
save\_outputs()
        |
        +--> Raw snapshot
        +--> Cleaned snapshot
        +--> Active-only snapshot
        +--> Code-frequency report
        +--> Validation report

Separate manual quality check:

Cleaned snapshot
        |
        v
check\_largest\_ontario\_fire.py
        |
        v
Largest-fire record printed for review
```

\---

## 6\. Implementation Walkthrough

## 6.1 Source settings

File:

```text
src/etl/extract\_ontario\_active\_fires.py
```

The source settings define the ArcGIS query endpoint, page size, and request timeout.

```python
ARCGIS\_URL = (
    "https://ws.lioservices.lrc.gov.on.ca/arcgis1061a/rest/services/"
    "MNRF/Ontario\_Fires\_Map/MapServer/0/query"
)

PAGE\_SIZE = 2000
REQUEST\_TIMEOUT\_SECONDS = 60
```

### Reasoning

The service maximum is 5,000 records per request. I used 2,000 records per page because it is below the service maximum and easier to troubleshoot. The July 31 snapshot contained only 641 records, so it fit in one page, but the pagination logic remains important for future runs.

### Result

The script is not dependent on the current row count. It can continue requesting additional pages if the service grows beyond one response.

\---

## 6.2 Mapping dictionaries

The script uses separate dictionaries to prevent confirmed mappings from being mixed with provisional mappings.

### Confirmed stage-of-control dictionary

```python
STAGE\_OF\_CONTROL\_LABELS = {
    "OC": "Out of Control",
    "BH": "Being Held",
    "UC": "Under Control",
    "EX": "Out (Extinguished)",
}
```

These four mappings are supported by CWFIS, CIFFC, and Natural Resources Canada documentation.

### Provisional stage-of-control dictionary

```python
STAGE\_OF\_CONTROL\_LABELS\_PROVISIONAL = {
    "BM": "Being Monitored (provisional, unconfirmed code)",
}
```

`BM` is deliberately stored in a separate dictionary because the exact published mapping `BM = Being Monitored` was not found.

### Active-code set

```python
ACTIVE\_STAGE\_CODES = {"OC", "BH", "UC", "BM"}
```

`BM` is included provisionally so the active-only file does not silently exclude 115 likely ongoing fires.

### Confirmed response-type dictionary

```python
RESPONSE\_TYPE\_LABELS = {
    "FUL": "Full Response",
    "MOD": "Modified Response",
    "MON": "Monitored Response",
}
```

These response meanings are directly described in the CIFFC document titled *Stages of Control \& Response Types*.

### Documented national cause-code set

```python
DOCUMENTED\_NATIONAL\_CAUSE\_CODES = {"H", "N", "U"}
```

This set is used for comparison and warnings. The script does not force Ontario's `L` value into another national category.

### Sentinel fields

```python
SENTINEL\_FIELDS = \[
    "FIELD\_LOCATION",
    "FIELD\_PERCENT\_CONTAINED",
    "FIELD\_SEVERITY\_NEAREST\_DSR",
    "FIELD\_AGENCY\_PREPARE\_LEVEL",
    "FIELD\_FIRE\_TYPE\_ICS",
]
```

These fields contained `-1` in observed data. The script creates flags rather than deleting or replacing the original values.

\---

## 6.3 Helper functions

### `clean\_text\_column(series)`

Purpose:

* Converts a column to pandas string type.
* Removes leading and trailing spaces.
* Creates cleaned values without changing the original source column.

```python
def clean\_text\_column(series):
    return series.astype("string").str.strip()
```

### `convert\_epoch\_ms\_to\_utc(value)`

Purpose:

* Converts ArcGIS date values from Unix epoch milliseconds to timezone-aware UTC datetimes.
* Returns `NaT` for invalid or missing values instead of stopping the pipeline.

```python
def convert\_epoch\_ms\_to\_utc(value):
    return pd.to\_datetime(value, unit="ms", utc=True, errors="coerce")
```

### Result

The source timestamps become readable and usable in analysis while the original epoch-millisecond fields remain available.

\---

## 6.4 Download function

Function:

```text
fetch\_all\_fire\_records()
```

### Steps performed

1. Create an empty record list.
2. Start `resultOffset` at zero.
3. Create one UTC extraction timestamp for the full snapshot.
4. Send a request to the ArcGIS query endpoint.
5. Request all fields with `outFields=\*`.
6. Request geometry.
7. Request output coordinates in EPSG:4326.
8. Request GeoJSON.
9. Order by `OBJECTID ASC` for stable pagination.
10. Check HTTP errors.
11. Check JSON-decoding errors.
12. Check ArcGIS errors returned inside a successful HTTP response.
13. Read each feature's properties and geometry.
14. Extract longitude and latitude from the GeoJSON coordinate array.
15. Add source metadata and extraction time.
16. Continue if the service reports another page.
17. Return all records as a pandas DataFrame.

### Request parameters

```python
params = {
    "where": "1=1",
    "outFields": "\*",
    "returnGeometry": "true",
    "outSR": 4326,
    "f": "geojson",
    "resultRecordCount": PAGE\_SIZE,
    "resultOffset": offset,
    "orderByFields": "OBJECTID ASC",
}
```

### Why stable ordering matters

Pagination without a stable order can produce duplicate or missed records if the service returns rows in a different order between page requests. Ordering by `OBJECTID ASC` reduces that risk.

### Geometry handling

GeoJSON stores point coordinates in this order:

```text
\[longitude, latitude]
```

The script explicitly assigns:

```python
properties\["geometry\_longitude"] = coordinates\[0]
properties\["geometry\_latitude"] = coordinates\[1]
```

This prevents latitude and longitude from being reversed.

### Result of the July 31 run

```text
Requesting records starting at offset 0...
Received 641 records. Total downloaded so far: 641
The service reports that the final page was reached.
```

The source returned 641 records in one page.

\---

## 6.5 Cleaned dataset builder

Function:

```text
build\_cleaned\_dataset(raw\_df)
```

### Design rule

The cleaned dataset starts with:

```python
cleaned\_df = raw\_df.copy()
```

The source fields are retained. New fields are added beside them.

### Cleaned identifiers and codes

The function creates:

* `fire\_id`
* `agency\_code`
* `stage\_of\_control\_code`
* `agency\_fire\_cause\_code`
* `system\_fire\_cause\_code`
* `response\_type\_code`

### Stage-of-control fields

The cleaned output separates status confidence into multiple fields:

|Column|Purpose|
|-|-|
|`stage\_of\_control\_code`|Cleaned raw code.|
|`stage\_of\_control\_label`|Label from the confirmed dictionary only.|
|`stage\_of\_control\_label\_provisional`|Label from the provisional dictionary only.|
|`stage\_of\_control\_mapping\_status`|`Confirmed`, `Provisional`, or `Unmapped`.|
|`stage\_of\_control\_display\_label`|Convenient final display label.|
|`is\_active\_fire`|Boolean flag used to create the active-only output.|

Example output:

|Code|Confirmed label|Provisional label|Mapping status|Active|
|-|-|-|-|-:|
|`OC`|Out of Control|null|Confirmed|True|
|`BH`|Being Held|null|Confirmed|True|
|`UC`|Under Control|null|Confirmed|True|
|`EX`|Out (Extinguished)|null|Confirmed|False|
|`BM`|null|Being Monitored (provisional, unconfirmed code)|Provisional|True|

### Numeric fields

The function creates numeric versions of:

* `fire\_size\_hectares`
* `latitude`
* `longitude`

Invalid numeric values are converted to `NaN` using `errors="coerce"`.

### Timestamp fields

The function creates:

* `situation\_report\_datetime\_utc`
* `status\_datetime\_utc`
* `refreshed\_datetime\_utc`

### Cause interpretation

The script creates:

* `cause\_interpretation\_provisional`
* `cause\_mapping\_status`

The implemented mapping is:

```text
LTG + L -> Lightning
```

This was based on an exact 421-record pairing in the extracted snapshot.

The script deliberately does not convert `L` to national code `N`. The Ontario value remains visible in the raw and cleaned code fields.

The full snapshot also showed an exact pairing:

```text
HUM + H -> 220 records
```

This is strong empirical evidence that `HUM/H` represents human-caused fires. However, no additional code change was made after the final run, so these 220 records remain marked `Requires review` in the generated validation report. This README documents the empirical relationship without claiming that the current script has mapped it.

### Sentinel flags

For each selected source field, the script adds a boolean column such as:

```text
FIELD\_PERCENT\_CONTAINED\_is\_minus\_one
```

This allows downstream analysis to distinguish a `-1` sentinel from a normal value without changing the raw field.

\---

## 6.6 Code-frequency report

Function:

```text
build\_code\_frequency\_report(raw\_df)
```

The function counts every distinct value in:

* `FIELD\_STAGE\_OF\_CONTROL\_STATUS`
* `FIELD\_AGENCY\_FIRE\_CAUSE`
* `FIELD\_SYSTEM\_FIRE\_CAUSE`
* `FIELD\_RESPONSE\_TYPE`
* `FIELD\_AGENCY\_CODE`

### Why this report is necessary

The source does not expose coded-value domains. A frequency report provides a reproducible way to discover the values actually present in a full pull.

It also prevents mappings from being built from only one or two sample records.

### Result

The July 31 snapshot produced:

#### Stage of control

|Code|Count|
|-|-:|
|`EX`|481|
|`BM`|115|
|`OC`|29|
|`BH`|10|
|`UC`|6|

#### Agency fire cause

|Code|Count|
|-|-:|
|`LTG`|421|
|`HUM`|220|

#### System fire cause

|Code|Count|
|-|-:|
|`L`|421|
|`H`|220|

#### Response type

|Code|Count|
|-|-:|
|`FUL`|496|
|`MON`|111|
|`MNP`|16|
|`MOD`|15|
|`MDP`|2|
|`-1`|1|

#### Agency

|Code|Count|
|-|-:|
|`ON`|641|

\---

## 6.7 Validation report

Function:

```text
build\_validation\_report(raw\_df, cleaned\_df)
```

The validation report checks:

* Total records
* Missing fire IDs
* Duplicate `OBJECTID` values
* Missing latitude
* Missing longitude
* Missing fire size
* Minimum fire size
* Maximum fire size
* Confirmed stage records
* Provisional stage records
* Unmapped stage records
* Cause records requiring review

### Final validation result

|Check|Value|
|-|-:|
|`total\_records`|641|
|`missing\_fire\_ids`|0|
|`duplicate\_objectids`|0|
|`missing\_latitude`|0|
|`missing\_longitude`|0|
|`missing\_fire\_size`|0|
|`minimum\_fire\_size\_hectares`|0.1|
|`maximum\_fire\_size\_hectares`|313,930.0|
|`confirmed\_stage\_records`|526|
|`provisional\_stage\_records`|115|
|`unmapped\_stage\_records`|0|
|`cause\_codes\_requiring\_review`|220|

### Reconciliation

```text
526 confirmed + 115 provisional = 641 total
```

There are no unmapped stage records after the `BM` handling was added.

\---

## 6.8 Warning logic

Function:

```text
print\_code\_warnings(code\_report)
```

The function compares observed values against known mappings.

### Stage warnings

Confirmed and provisional stage dictionaries are combined when checking whether a value is completely unknown.

`BM` is not printed as an undocumented error. It is printed as a provisional notice:

```text
NOTICE - Provisional stage-of-control codes included: \['BM']
```

### Cause warnings

The script compares observed system cause values against the documented national set `H/N/U`.

The output was:

```text
NOTICE - System cause values outside documented H/N/U set: \['L']
These values are preserved and must be reviewed.
The observed L value is provisionally interpreted as Lightning.
```

The important design decision is that the script preserves `L` rather than automatically changing it to another code.

\---

## 6.9 Output writer

Function:

```text
save\_outputs(raw\_df, cleaned\_df, code\_report, validation\_report)
```

The function creates the required folders and writes five timestamped CSV files.

The timestamp format is:

```text
YYYYMMDDTHHMMSSZ
```

Example:

```text
20260731T045931Z
```

### Why timestamped filenames are used

Timestamped filenames:

* Prevent a new run from overwriting the previous snapshot.
* Support historical comparison.
* Make the extraction time traceable.
* Prepare the project for future scheduled ingestion.

### Active-only filter

The active-only output is created from:

```python
active\_df = cleaned\_df\[cleaned\_df\["is\_active\_fire"]].copy()
```

For the July 31 snapshot, the expected active count is:

```text
OC  = 29
BH  = 10
UC  = 6
BM  = 115
Total = 160
```

`EX = 481` is excluded from the active-only file.

\---

## 6.10 Main function

Function:

```text
main()
```

The main function runs the complete process in order:

1. Download the source records.
2. Stop safely if no records are returned.
3. Build the cleaned dataset.
4. Build the code-frequency report.
5. Build the validation report.
6. Print the reports.
7. Print warnings.
8. Save all outputs.
9. Print a completion message.

The script uses:

```python
if \_\_name\_\_ == "\_\_main\_\_":
    main()
```

This prevents the extraction from running automatically if the file is imported into another Python module.

\---

## 7\. Problem Log and Resolutions

## Problem 1: The source used ArcGIS REST rather than the interfaces used in earlier tasks

### Problem

Earlier project tasks used services such as CWFIS WFS and GeoMet OGC API. The Ontario fire source uses ArcGIS REST, which has different request parameters and response behaviour.

### File

```text
src/etl/extract\_ontario\_active\_fires.py
```

### Resolution steps

1. Opened the ArcGIS service directory.
2. Identified Layer 0 as the general Ontario Fires feature layer.
3. Inspected the layer fields and capabilities.
4. Used the layer's `/query` endpoint.
5. Requested `f=geojson` for a standard feature structure.
6. Added ArcGIS-specific pagination using `resultOffset` and `resultRecordCount`.
7. Added explicit error handling for ArcGIS errors returned inside JSON.

### Result

The endpoint returned 641 fire records successfully.

\---

## Problem 2: One request could eventually become insufficient

### Problem

The current snapshot was below the service maximum, but relying on a single request would make the process fragile.

### File and function

```text
src/etl/extract\_ontario\_active\_fires.py
fetch\_all\_fire\_records()
```

### Resolution steps

1. Set `PAGE\_SIZE = 2000`.
2. Started `offset = 0`.
3. Requested rows in stable `OBJECTID` order.
4. Checked `exceededTransferLimit`.
5. Increased the offset by the number of returned features when another page existed.
6. Stopped only when the service reported the final page or returned no records.

### Result

The July 31 snapshot required only one request, but the extraction remains pagination-safe.

\---

## Problem 3: GeoJSON coordinates could be reversed

### Problem

GeoJSON uses `\[longitude, latitude]`, while people often read coordinates as latitude followed by longitude.

### File and function

```text
src/etl/extract\_ontario\_active\_fires.py
fetch\_all\_fire\_records()
```

### Resolution steps

1. Read the coordinate array.
2. Assigned index `0` to `geometry\_longitude`.
3. Assigned index `1` to `geometry\_latitude`.
4. Used source latitude and longitude fields as the preferred cleaned numeric coordinates when available.
5. Retained geometry-derived coordinates as backup values.

### Result

The cleaned snapshot had zero missing latitude values and zero missing longitude values.

\---

## Problem 4: ArcGIS returned dates as epoch milliseconds

### Problem

Values such as `FIELD\_STATUS\_DATE` were not immediately readable.

### File and function

```text
src/etl/extract\_ontario\_active\_fires.py
convert\_epoch\_ms\_to\_utc()
build\_cleaned\_dataset()
```

### Resolution steps

1. Identified the source values as Unix epoch milliseconds.
2. Converted with `unit="ms"`.
3. Set `utc=True`.
4. Used `errors="coerce"` so invalid values become `NaT`.
5. Kept original source date fields unchanged.

### Result

Readable UTC fields were created for situation report, status, and refresh timestamps.

\---

## Problem 5: The service did not publish coded-value domains

### Problem

The ArcGIS layer listed the code fields but did not publish exact value definitions.

### Files and functions

```text
src/etl/extract\_ontario\_active\_fires.py
build\_code\_frequency\_report()
print\_code\_warnings()
```

### Resolution steps

1. Preserved raw code fields.
2. Counted every distinct code in the full pull.
3. Compared observed values with external official documentation.
4. Separated confirmed and provisional mappings.
5. Left unresolved values unmapped.
6. Printed warnings and notices instead of hiding discrepancies.

### Result

Every stage, cause, response, and agency code in the 641-row snapshot was visible in the quality report.

\---

## Problem 6: `BM` appeared in 115 records but was not in the first confirmed dictionary

### Initial result

The first run returned:

```text
BM = 115 records
```

The first mapping included only:

```text
OC, BH, UC, EX
```

This caused all 115 `BM` records to appear as unmapped and excluded them from the active-only output.

### Investigation

The research found:

* Official sources consistently defined `OC`, `BH`, `UC`, and `EX`.
* Ontario's forest-fire-management page described a concept called `being observed` with code `BOB`.
* National terminology work described replacing the term `Being Observed` with `Being Monitored`.
* No reviewed source explicitly stated the exact mapping `BM = Being Monitored`.
* `BM` was common, representing 115 of 641 records, so it was unlikely to be a random data error.
* It was not `EX`, and excluding it would likely undercount ongoing monitored fires.

### Decision criteria

I considered two options:

1. Exclude `BM` until exact documentation was found.
2. Include `BM` provisionally and label the uncertainty explicitly.

I selected the second option because it preserved the raw code, avoided silently excluding a large category, and kept the uncertainty visible.

### File and code changes

File:

```text
src/etl/extract\_ontario\_active\_fires.py
```

Changes:

```python
STAGE\_OF\_CONTROL\_LABELS\_PROVISIONAL = {
    "BM": "Being Monitored (provisional, unconfirmed code)",
}

ACTIVE\_STAGE\_CODES = {"OC", "BH", "UC", "BM"}
```

Additional fields were added:

* `stage\_of\_control\_label\_provisional`
* `stage\_of\_control\_mapping\_status`
* `stage\_of\_control\_display\_label`

Validation was changed to count confirmed, provisional, and truly unmapped records separately.

The warning logic was changed so `BM` is printed as provisional rather than unknown.

### Result after rerun

```text
confirmed\_stage\_records = 526
provisional\_stage\_records = 115
unmapped\_stage\_records = 0
```

The totals reconcile exactly:

```text
526 + 115 = 641
```

The active-only output now includes `BM` and contains approximately 160 records for this snapshot.

\---

## Problem 7: Response-type codes required documentation

### Observed values

```text
FUL = 496
MON = 111
MNP = 16
MOD = 15
MDP = 2
-1  = 1
```

### Investigation

The CIFFC *Stages of Control \& Response Types* document directly defines:

* `FUL` as Full Response.
* `MOD` as Modified Response.
* `MON` as Monitored Response.

The reviewed material did not provide a confirmed definition for:

* `MNP`
* `MDP`
* `-1`

### File

```text
src/etl/extract\_ontario\_active\_fires.py
```

### Resolution steps

1. Promoted `FUL`, `MOD`, and `MON` to the confirmed `RESPONSE\_TYPE\_LABELS` dictionary.
2. Renamed the generated field to `response\_type\_label`.
3. Allowed `MNP`, `MDP`, and `-1` to fall through to `Unmapped`.
4. Preserved the original `FIELD\_RESPONSE\_TYPE` and cleaned `response\_type\_code` values.
5. Avoided guessing that `MNP` or `MDP` represented a patrol or other subtype.

### Result

Three response types are documented and mapped. Eighteen `MNP/MDP` records and one `-1` record remain traceable and unresolved without affecting active/inactive classification.

\---

## Problem 8: Ontario cause codes did not match the expected national pattern exactly

### Observed pairings

```text
LTG + L = 421 records
HUM + H = 220 records
```

The national catalogue described broad codes including `H`, `N`, and `U`, but the Ontario live feed used `L` rather than `N` for the lightning-related rows.

### Risk

Automatically converting `L` to `N` would alter the source meaning without a verified rule.

### File and functions

```text
src/etl/extract\_ontario\_active\_fires.py
build\_cleaned\_dataset()
print\_code\_warnings()
```

### Resolution steps

1. Preserved agency and system cause codes.
2. Verified the pair frequencies across the complete pull.
3. Interpreted `LTG/L` as Lightning with high empirical confidence.
4. Did not force `L` into national code `N`.
5. Printed a notice that `L` falls outside the documented national `H/N/U` set.
6. Kept `HUM/H` documented as an exact empirical relationship, but did not make another code change after the final run.

### Result

The raw values remain fully traceable. Lightning is interpreted in the current script, while the 220 human-caused records remain marked for review in the generated validation report.

\---

## Problem 9: `-1` could be a sentinel rather than a real value

### Problem

Several source fields contained `-1`. The service metadata did not clearly define its meaning.

### Risk

Replacing `-1` with null without evidence could destroy source information. Treating it as a normal value could also mislead analysis.

### File

```text
src/etl/extract\_ontario\_active\_fires.py
```

### Resolution steps

1. Preserved the original value.
2. Created a separate boolean flag for each selected field.
3. Left interpretation to downstream validation.

### Result

The source remains unchanged, while analysts can filter or investigate sentinel values explicitly.

\---

## Problem 10: The maximum fire size looked large enough to be a unit or parsing error

### Validation finding

The validation report returned:

```text
maximum\_fire\_size\_hectares = 313930.0
```

A value this large could theoretically result from:

* Incorrect units.
* A decimal-placement error.
* Square metres mislabeled as hectares.
* A bad join.
* A parsing problem.
* A legitimate very large wildfire.

### Separate validation file

```text
src/etl/check\_largest\_ontario\_fire.py
```

### Validation script steps

1. Set the cleaned snapshot path.
2. Confirmed the file exists.
3. Read the cleaned CSV.
4. Confirmed the dataset is not empty.
5. Checked that required columns exist.
6. Converted `fire\_size\_hectares` to numeric.
7. Found the maximum size.
8. Selected every record equal to the maximum.
9. Printed identity, status, cause, dates, and coordinates.

### First execution attempt

The script was initially called directly from Git Bash:

```bash
src/etl/check\_largest\_ontario\_fire.py
```

Git Bash attempted to interpret the Python file as a shell script and returned errors such as:

```text
from: command not found
import: command not found
syntax error near unexpected token
```

### Correction

The file was run through the Python interpreter:

```bash
python src/etl/check\_largest\_ontario\_fire.py
```

### Output

```text
File loaded successfully: data\\processed\\ontario\_active\_fires\\ontario\_fires\_cleaned\_20260731T045931Z.csv
Total records in the file: 641

Largest fire size found:
313,930.0 hectares
Number of records with this maximum size: 1

fire\_id: THU\_FIRE\_036
fire\_size\_hectares: 313930.0
stage\_of\_control\_code: OC
stage\_of\_control\_display\_label: Out of Control
agency\_fire\_cause\_code: LTG
situation\_report\_datetime\_utc: 2026-07-12 16:57:00+00:00
status\_datetime\_utc: 2026-07-24 23:02:00+00:00
latitude: 50.6828
longitude: -89.468
```

### External consistency check

The identity, coordinates, status, cause, and size were consistent with public reporting for Thunder Bay 36 in northwestern Ontario.

The Ontario fire information page also notes that fire perimeters and reported sizes may differ because not every perimeter is mapped every day and perimeter estimates are updated as new mapping becomes available.

### Decision

The value was retained.

It is documented as:

```text
Reviewed - valid extreme observation
```

It was not treated as a parsing error, a unit error, or a reason to remove the row.

### Result

The largest value passed manual validation as a legitimate extreme observation in this extracted snapshot.

\---

## Problem 11: The extraction script should not be expanded indefinitely

### Problem

Two small response codes remained unresolved, and recurring Airflow scheduling was still an open design question.

### Decision

OWF-26 was considered complete because:

* The extraction works.
* The active classification works.
* Raw values are preserved.
* Unknown response codes are visible.
* The unresolved response codes do not affect active/inactive classification.
* The outlier was checked separately.

No additional changes were made to the main extraction script after the final successful run.

Recurring Airflow scheduling should be created as a separate work item.

\---

## 8\. Investigation Timeline and Attempts

### Attempt 1: Identify and query the Ontario source

* Opened the Ontario ArcGIS REST directory.
* Selected Layer 0.
* Confirmed fields, point geometry, GeoJSON support, maximum record count, and pagination support.
* Built the first extraction script.

Result:

* 641 records downloaded successfully.

### Attempt 2: Apply the documented four stage mappings

Initial confirmed dictionary:

```text
OC, BH, UC, EX
```

Result:

* 115 `BM` records appeared unmapped.
* The active-only output contained only `OC`, `BH`, and `UC`.

### Attempt 3: Research `BM`

Reviewed:

* CWFIS stage definitions.
* CIFFC terminology.
* Natural Resources Canada active-fire metadata.
* Ontario forest-fire-management terminology.
* National common-terminology recommendations.

Finding:

* The concept of observed or monitored fires is official.
* Ontario documentation used `BOB` for Being Observed.
* National terminology connected Being Observed with Being Monitored.
* The exact string `BM` was not explicitly documented in the reviewed sources.

Decision:

* Include `BM` provisionally.
* Keep it separate from confirmed mappings.

### Attempt 4: Update validation and rerun

Changes:

* Added provisional dictionary.
* Added provisional label field.
* Added mapping-status field.
* Added display label.
* Added `BM` to the active set.
* Changed validation counts.
* Changed warning logic.

Result:

```text
526 confirmed
115 provisional
0 unmapped
641 total
```

### Attempt 5: Confirm response codes

Finding:

* `FUL`, `MOD`, and `MON` were explicitly defined by CIFFC.
* `MNP`, `MDP`, and `-1` were not resolved.

Decision:

* Map the three confirmed values.
* Leave the others unmapped.

### Attempt 6: Validate cause relationships empirically

Finding:

```text
LTG/L = 421 of 421
HUM/H = 220 of 220
```

Decision:

* Keep raw values.
* Interpret `LTG/L` as Lightning in the script.
* Do not force `L` to national `N`.
* Document `HUM/H` as an exact empirical pairing, while leaving the generated 220 records marked for review because no final code change was made.

### Attempt 7: Validate the 313,930-hectare record

* Created a separate check script.
* First called it as a Bash command and received shell errors.
* Corrected the command to use `python`.
* Confirmed the record was `THU\_FIRE\_036`, Out of Control, lightning-caused, and located in northwestern Ontario.
* Compared it with public reporting.

Decision:

* Retain as a valid extreme observation.

### Final decision

* Close OWF-26.
* Keep `MNP`, `MDP`, and `-1` unresolved.
* Keep `BM` provisional.
* Keep the large fire record.
* Handle recurring scheduling separately.

\---

## 9\. Mapping Confidence Register

The percentages below are project confidence ratings used to communicate the strength of each interpretation. They are not statistical probabilities and are not produced by a formal calibration model.

|Field|Code or relationship|Interpretation|Confidence|Status|Basis|
|-|-|-|-:|-|-|
|Stage of control|`OC`|Out of Control|100%|Confirmed|Official CWFIS, CIFFC, and NRCan documentation.|
|Stage of control|`BH`|Being Held|100%|Confirmed|Official CWFIS, CIFFC, and NRCan documentation.|
|Stage of control|`UC`|Under Control|100%|Confirmed|Official CWFIS, CIFFC, and NRCan documentation.|
|Stage of control|`EX`|Out / Extinguished|100%|Confirmed|Official CWFIS, CIFFC, and NRCan documentation.|
|Stage of control|`BM`|Being Monitored|85%|Provisional|Strong conceptual and frequency evidence, but exact published code mapping not found.|
|Response type|`FUL`|Full Response|100%|Confirmed|CIFFC response-type document.|
|Response type|`MOD`|Modified Response|100%|Confirmed|CIFFC response-type document.|
|Response type|`MON`|Monitored Response|100%|Confirmed|CIFFC response-type document.|
|Response type|`MNP`|Unknown|0% interpretation confidence|Unmapped|No exact reviewed definition. Raw value preserved.|
|Response type|`MDP`|Unknown|0% interpretation confidence|Unmapped|No exact reviewed definition. Raw value preserved.|
|Response type|`-1`|Unknown sentinel or missing category|0% interpretation confidence|Unmapped|No exact reviewed definition. Raw value preserved.|
|Fire cause|`LTG` + `L`|Lightning|99%|High-confidence empirical interpretation|Exact 421/421 pairing across the snapshot.|
|Fire cause|`HUM` + `H`|Human-caused|99%|High-confidence empirical finding|Exact 220/220 pairing across the snapshot; not added to the final script mapping.|
|Fire size|`313930.0` for `THU\_FIRE\_036`|Legitimate extreme observation|99%|Manually reviewed|Identity, location, status, cause, and external reporting were consistent.|

### Why `BM` is not assigned 100%

The meaning is highly plausible, but the exact code string was not found in the reviewed published documentation. The README therefore keeps the distinction between:

* Confirmed concept: monitored or observed fires are a real official category.
* Unconfirmed exact mapping: the Ontario feed's exact `BM` abbreviation.

### Why `LTG/L` and `HUM/H` are not assigned 100%

The pairings are exact in this snapshot, but the confidence is empirical rather than based on an explicit source data dictionary for these exact Ontario codes.

\---

## 10\. Final Run Output

Command:

```bash
python src/etl/extract\_ontario\_active\_fires.py
```

Successful run summary:

```text
============================================================
OWF-26 - Ontario Active Fires Extraction
============================================================
Requesting records starting at offset 0...
Received 641 records. Total downloaded so far: 641
The service reports that the final page was reached.

Total records downloaded: 641
```

### Code frequencies

```text
FIELD\_STAGE\_OF\_CONTROL\_STATUS
EX  481
BM  115
OC   29
BH   10
UC    6

FIELD\_AGENCY\_FIRE\_CAUSE
LTG 421
HUM 220

FIELD\_SYSTEM\_FIRE\_CAUSE
L 421
H 220

FIELD\_RESPONSE\_TYPE
FUL 496
MON 111
MNP  16
MOD  15
MDP   2
-1    1

FIELD\_AGENCY\_CODE
ON 641
```

### Validation

```text
total\_records                    641
missing\_fire\_ids                   0
duplicate\_objectids                0
missing\_latitude                   0
missing\_longitude                  0
missing\_fire\_size                  0
minimum\_fire\_size\_hectares       0.1
maximum\_fire\_size\_hectares  313930.0
confirmed\_stage\_records          526
provisional\_stage\_records        115
unmapped\_stage\_records             0
cause\_codes\_requiring\_review     220
```

### Notices

```text
NOTICE - Provisional stage-of-control codes included: \['BM']
NOTICE - System cause values outside documented H/N/U set: \['L']
```

### Saved files

```text
Raw snapshot:
data/raw/ontario\_active\_fires/ontario\_fires\_raw\_20260731T045931Z.csv

Cleaned snapshot:
data/processed/ontario\_active\_fires/ontario\_fires\_cleaned\_20260731T045931Z.csv

Active fires only:
data/processed/ontario\_active\_fires/ontario\_active\_fires\_20260731T045931Z.csv

Code report:
data/quality/ontario\_active\_fires/ontario\_fire\_code\_frequency\_20260731T045931Z.csv

Validation report:
data/quality/ontario\_active\_fires/ontario\_fire\_validation\_20260731T045931Z.csv
```

\---

## 11\. Output File Details

## 11.1 Raw snapshot

File:

```text
data/raw/ontario\_active\_fires/ontario\_fires\_raw\_20260731T045931Z.csv
```

Contains:

* All returned source properties.
* Geometry longitude and latitude.
* Source feature ID.
* Geometry type.
* Snapshot download timestamp.
* Source URL.

Purpose:

* Preserve source lineage.
* Allow reprocessing without downloading again.
* Support audits and comparison with future snapshots.

\---

## 11.2 Cleaned snapshot

File:

```text
data/processed/ontario\_active\_fires/ontario\_fires\_cleaned\_20260731T045931Z.csv
```

Contains:

* Every raw source column.
* Cleaned codes and identifiers.
* Confirmed and provisional status labels.
* Mapping status.
* Active-fire flag.
* Numeric size and coordinates.
* UTC timestamps.
* Cause interpretation and review status.
* Sentinel flags.

Purpose:

* Main analysis-ready full dataset.
* Retains both active and out fires.
* Provides traceability between raw and interpreted values.

\---

## 11.3 Active-only snapshot

File:

```text
data/processed/ontario\_active\_fires/ontario\_active\_fires\_20260731T045931Z.csv
```

Filter:

```text
stage code in {OC, BH, UC, BM}
```

Purpose:

* Provide the current-fire subset used in later impact analysis.
* Exclude confirmed out/extinguished records.
* Include `BM` with an explicit provisional interpretation.

Expected July 31 count:

```text
160 records
```

\---

## 11.4 Code-frequency report

File:

```text
data/quality/ontario\_active\_fires/ontario\_fire\_code\_frequency\_20260731T045931Z.csv
```

Columns:

* `field\_name`
* `code\_value`
* `record\_count`

Purpose:

* Detect new or undocumented codes.
* Compare values between snapshots.
* Support mapping decisions using the entire pull.

\---

## 11.5 Validation report

File:

```text
data/quality/ontario\_active\_fires/ontario\_fire\_validation\_20260731T045931Z.csv
```

Columns:

* `check\_name`
* `value`

Purpose:

* Confirm basic completeness.
* Detect duplicate IDs.
* Check coordinate and size availability.
* Reconcile confidence categories.
* Surface extreme values and unresolved cause mappings.

\---

## 12\. Reproduction Instructions

## 12.1 Requirements

The script requires:

* Python
* `pandas`
* `requests`

Install dependencies if needed:

```bash
pip install pandas requests
```

## 12.2 Run from the repository root

Repository location used during development:

```text
/d/ontario-wildfire-analytics/ontario-wildfire-impact-forecasting
```

Activate the virtual environment according to the project setup, then run:

```bash
python src/etl/extract\_ontario\_active\_fires.py
```

## 12.3 Confirm output files

```bash
ls data/raw/ontario\_active\_fires/
ls data/processed/ontario\_active\_fires/
ls data/quality/ontario\_active\_fires/
```

## 12.4 Run the largest-fire check

```bash
python src/etl/check\_largest\_ontario\_fire.py
```

Do not run the Python path by itself in Git Bash unless the file has an appropriate shebang and executable permissions. The tested command uses the Python interpreter explicitly.

## 12.5 Confirm active count

Example Git Bash command:

```bash
python -c "import pandas as pd, glob; f=sorted(glob.glob('data/processed/ontario\_active\_fires/ontario\_active\_fires\_\*.csv'))\[-1]; df=pd.read\_csv(f); print('Active records:', len(df)); print(df\['stage\_of\_control\_code'].value\_counts())"
```

Expected values for the July 31 snapshot:

```text
Active records: 160
BM 115
OC  29
BH  10
UC   6
```

The exact values can change in future live-source snapshots.

\---

## 13\. Data Governance Principles Used

### Preserve source values

No raw status, cause, response, timestamp, size, or coordinate value is deleted or replaced.

### Separate data from interpretation

The original code and its readable label are stored in different columns.

### Separate confirmed from provisional mappings

`BM` is not placed in the confirmed status dictionary.

### Do not force cross-system normalization

Ontario's system cause `L` is not automatically converted to national code `N`.

### Make uncertainty queryable

Uncertainty is stored in fields such as:

* `stage\_of\_control\_mapping\_status`
* `stage\_of\_control\_label\_provisional`
* `cause\_mapping\_status`
* `cause\_interpretation\_provisional`

### Prefer explicit unresolved values over invented meanings

`MNP`, `MDP`, and `-1` remain `Unmapped`.

### Validate unusual values before removing them

The 313,930-hectare value was investigated rather than deleted as an assumed outlier.

### Keep extraction separate from orchestration

The extraction script is complete. Airflow scheduling belongs in a separate follow-up item.

\---

## 14\. Known Limitations

### Live data changes

The source is operational and can change between runs. Counts and reported fire sizes are snapshot-specific.

### `BM` remains provisional

The exact published code mapping was not found. The active classification decision is documented and reversible.

### `MNP` and `MDP` remain unresolved

These codes are preserved but not interpreted.

### `-1` remains unresolved

The value is treated as a sentinel candidate and preserved.

### Cause mapping is partly empirical

`LTG/L` and `HUM/H` relationships are supported by exact pairings in this snapshot, but the Ontario service does not publish coded-value domains for these fields.

### The current generated validation file still reports 220 cause records requiring review

This is expected because the final script maps `LTG/L` but does not map `HUM/H`.

### Perimeters and reported sizes may be revised

A fire's size can change after new mapping flights, perimeter refinement, merging, or source updates. The 313,930-hectare decision applies to this snapshot.

### No recurring schedule in OWF-26

The script must be run manually until a separate Airflow task is implemented.

\---

## 15\. Suggested Follow-up Work

These items are outside the completed OWF-26 scope:

1. Create an Airflow DAG for recurring Ontario fire snapshots.
2. Add source-freshness checks.
3. Compare each new snapshot with the previous snapshot.
4. Alert when a new stage, cause, or response code appears.
5. Contact the Ontario data owner for exact definitions of `BM`, `MNP`, `MDP`, and `-1`.
6. Decide whether to add `HUM/H` to a formal cause mapping after documentation review.
7. Add unit tests for pagination, timestamp conversion, mappings, and output filters.
8. Add a data dictionary for all cleaned columns.
9. Add snapshot retention and archive rules.

\---

## 16\. Final Result

OWF-26 achieved its objective.

The extraction pipeline successfully downloaded and processed 641 Ontario fire records from the Ontario ArcGIS REST service.

The final snapshot had:

* 641 total records.
* 0 missing fire IDs.
* 0 duplicate `OBJECTID` values.
* 0 missing latitude values.
* 0 missing longitude values.
* 0 missing fire-size values.
* 526 records with confirmed stage mappings.
* 115 records with the provisional `BM` mapping.
* 0 truly unmapped stage records.
* 160 likely active records when `BM` is included.
* 481 out/extinguished records.

The code-frequency report exposed all observed status, cause, response, and agency values.

The response types `FUL`, `MOD`, and `MON` were confirmed. `MNP`, `MDP`, and `-1` remain preserved and unmapped.

The cause relationships `LTG/L` and `HUM/H` were exact across all 641 records. The script interprets `LTG/L` as Lightning and preserves `L` without forcing it into the national `N` category.

The largest fire-size record was manually reviewed using a separate script. `THU\_FIRE\_036` at 313,930 hectares was retained as a legitimate extreme observation rather than treated as a processing or unit error.

The work item can be closed without further changes to the extraction script. Recurring Airflow scheduling should be tracked separately.

\---

## 17\. Source Links

### Primary Ontario data source

Ontario ArcGIS REST service directory:

```text
https://ws.lioservices.lrc.gov.on.ca/arcgis1061a/rest/services/MNRF/Ontario\_Fires\_Map/MapServer
```

Ontario Fires Layer 0:

```text
https://ws.lioservices.lrc.gov.on.ca/arcgis1061a/rest/services/MNRF/Ontario\_Fires\_Map/MapServer/0
```

Ontario Fires Layer 0 query endpoint:

```text
https://ws.lioservices.lrc.gov.on.ca/arcgis1061a/rest/services/MNRF/Ontario\_Fires\_Map/MapServer/0/query
```

Ontario forest fires page and interactive map context:

```text
https://www.ontario.ca/page/forest-fires
```

### Stage-of-control and response documentation

CIFFC, *Stages of Control \& Response Types*:

```text
https://ciffc.net/pdfs/stages-of-control-and-response.pdf
```

CWFIS frequently asked questions:

```text
https://cwfis.cfs.nrcan.gc.ca/en/faq
```

CWFIS data catalogue:

```text
https://cwfis.cfs.nrcan.gc.ca/datamart
```

Natural Resources Canada, *Federal Geospatial Platform Active Wildfires in Canada* metadata:

```text
https://cwfis.cfs.nrcan.gc.ca/downloads/activefires/activefires\_metadata\_NAP\_ISO\_19115\_2003\_EN.pdf
```

Common terminology and data standards report:

```text
https://www.ccfm.org/wp-content/uploads/2020/08/Developing-more-common-language-terminology-and-data-standards-for-wildland-fire-management-in-Canada.pdf
```

Ontario forest fire management terminology:

```text
https://www.ontario.ca/page/forest-fire-management
```

### Contextual reporting used during the `BM` and outlier investigation

Yahoo Canada wildfire live coverage:

```text
https://www.yahoo.com/news/live/canada-wildfires-bc-braces-for-intense-firefighting-week-as-smoke-spreads-135834012.html
```

CBC background on stages of control:

```text
https://amp.cbc.ca/lite/story/1.6869916
```

Thunder Bay 36 reporting with the 313,930-hectare value:

```text
https://fftimes.com/news/district-news/thunder-bay-36-largest-wildfire-in-ontario-history-by-far/
```

APTN News article containing the exact 313,930-hectare Thunder Bay 36 value and Gull Bay evacuation context:

```text
https://www.aptnnews.ca/national-news/first-nations-chief-says-government-mpp-is-lying-about-meeting-with-him/
```

The CIFFC, CWFIS, Natural Resources Canada, Ontario government, and Ontario ArcGIS sources are the primary technical evidence. News links are contextual support and are not used as the main basis for code definitions.

\---

## 

