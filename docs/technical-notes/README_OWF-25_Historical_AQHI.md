# OWF-25 — Historical AQHI Extraction from Air Quality Ontario

## 1. Purpose

OWF-25 was created to download the historical Air Quality Health Index (AQHI) data required for the Ontario Wildfire Impact and Forecasting Analytics project.

The realtime AQHI feed from Environment and Climate Change Canada GeoMet only provided approximately three days of observations during testing. That window was useful for current monitoring, but it was not sufficient for time-series model development. An LSTM model needs a much longer sequence of daily observations to learn seasonality, recurring air-quality patterns, and changes in AQHI over time.

The objective of this task was to:

- identify the correct historical AQHI source;
- understand how the Air Quality Ontario website accepts search parameters;
- map the project cities to Air Quality Ontario station identifiers;
- download historical AQHI data for 2024, 2025, and 2026 year-to-date;
- preserve both daily 4:00 PM AQHI values and daily maximum AQHI values;
- validate the returned data before using it in transformation or modeling;
- document source-level data quality issues without changing the raw records.

This task focused on extraction and raw-data validation. It did not attempt to create a model-ready dataset or correct uncertain source records.

---

## 2. Source

Historical AQHI data was downloaded from the Air Quality Ontario AQHI search page:

```text
https://www.airqualityontario.com/aqhi/search.php
```

This source is an older PHP-based web search tool. It does not return JSON through a modern REST API. The results are returned as an HTML page containing an AQHI table.

The final request structure was discovered through manual browser testing:

```text
https://www.airqualityontario.com/aqhi/search.php
    ?stationid={STATION_ID}
    &show_day={MODE}
    &start_day={DAY}
    &start_month={MONTH}
    &start_year={YEAR}
    &submit_search=Get+AQHI+values
```

The important parameters are:

| Parameter | Meaning |
|---|---|
| `stationid` | Numeric Air Quality Ontario station identifier |
| `show_day=0` | Show one AQHI value per day at 4:00 PM |
| `show_day=2` | Show the daily maximum AQHI value |
| `start_year` | Controls the year returned in year-view mode |
| `start_day` | Included because the form requires it, but it appeared to be ignored in year-view mode |
| `start_month` | Included because the form requires it, but it appeared to be ignored in year-view mode |
| `submit_search` | Value of the website search button |

Manual testing showed that year-view requests returned data beginning on January 1 even when another day and month were provided. The extractor therefore sends January 1 for clarity and validates the returned dates after download.

---

## 3. Historical Window

I selected the following years:

```text
2024
2025
2026 year-to-date
```

This gave the project approximately two and a half years of daily AQHI history.

The 2026 extraction returned data through July 28, 2026, which was the latest date available during the full run.

The historical range was selected because:

- 2026 alone would provide too few daily observations for meaningful sequence modeling;
- 2024 and 2025 provide additional seasonal context;
- the longer AQHI history can support exploratory analysis and univariate baseline models;
- the final multivariate training window can later be restricted to dates that also have matching wildfire and weather features.

---

## 4. Station Mapping

Air Quality Ontario uses numeric station identifiers. These identifiers are different from the letter-based location identifiers used by GeoMet.

The final Air Quality Ontario mapping used in OWF-25 was:

| Project city | AQO station ID | AQO station name |
|---|---:|---|
| Barrie | `47045` | Barrie |
| Kingston | `52023` | Kingston |
| Thunder Bay | `63200` | Thunder Bay |
| Toronto | `31129` | Toronto Downtown |
| Toronto | `33003` | Toronto East |
| Toronto | `34021` | Toronto North |
| Toronto | `35125` | Toronto West |

Air Quality Ontario did not provide a general station named only `Toronto`. It provided four separate Toronto reporting zones.

GeoMet had an additional location named `Toronto` with the identifier `FEUZB`, but Air Quality Ontario had no direct equivalent. This is useful evidence for the future Toronto aggregation decision, but it does not prove what `FEUZB` represents. I therefore did not map `FEUZB` to an Air Quality Ontario station.

The extraction used seven Air Quality Ontario stations in total.

---

## 5. AQHI Value Types

Two historical modes were confirmed through manual testing.

### 5.1 Daily 4:00 PM values

```text
show_day=0
```

This mode returns one official AQHI observation at 4:00 PM for each date when the value is available.

The intended meaning is:

```text
AQHI at 4:00 PM on the reported date
```

### 5.2 Daily maximum values

```text
show_day=2
```

This mode returns the maximum AQHI observation shown by the historical search for each reporting period.

The intended meaning is:

```text
Maximum AQHI reported for the day
```

Both modes were preserved in the raw data because they represent different forecasting targets.

The final target variable was not forced during extraction. The decision between next-day 4:00 PM AQHI and next-day maximum AQHI was deferred until data quality profiling and exploratory analysis.

---

## 6. Files Created for OWF-25

### Main extraction script

```text
src/etl/extract_historical_aqhi.py
```

Purpose:

- build Air Quality Ontario requests;
- loop across all stations, years, and AQHI value types;
- parse the HTML results table;
- add project metadata;
- validate the downloaded data;
- save the combined raw dataset;
- create a report for possible daily-maximum date-boundary anomalies.

### Daily-maximum HTML diagnostic

```text
src/etl/diagnose_aqo_daily_max_html.py
```

Purpose:

- inspect the raw HTML for a known duplicated-date window;
- compare `pandas.read_html()` output with the original HTML rows;
- determine whether duplicated dates were caused by pandas or by the source page;
- inspect links or hidden metadata that might contain a correct reporting date.

### Full quality diagnostic

```text
src/etl/diagnose_aqo_full_quality.py
```

Purpose:

- load the completed historical CSV locally;
- identify rows outside the requested year;
- investigate Thunder Bay daily 4:00 PM row inflation;
- separate exact duplicate rows from conflicting records;
- create quality reports without making new requests or changing the raw dataset.

### Thunder Bay conflict diagnostic

```text
src/etl/diagnose_thunder_bay_conflict.py
```

Purpose:

- isolate the one Thunder Bay date and time that had two different AQHI values;
- compare the saved CSV, pandas-parsed source table, and original HTML;
- confirm whether the conflict existed in the Air Quality Ontario source.

---

## 7. Dependencies

The scripts used the following Python libraries:

```text
pandas
requests
lxml
beautifulsoup4
```

`pandas.read_html()` required an HTML parser. The first test failed because `lxml` was not installed.

The missing dependency was installed with:

```bash
pip install lxml
```

BeautifulSoup was used for raw HTML inspection:

```bash
pip install beautifulsoup4
```

These dependencies should be included in `requirements.txt`.

---

## 8. Extraction Method

### Step 1: Build the request

The extractor created one request for each combination of:

```text
station
year
value type
```

The total number of requests was:

```text
7 stations × 3 years × 2 value types = 42 requests
```

### Step 2: Send the request

The script used `requests.get()` with a 60-second timeout.

It printed the final request URL for traceability and debugging.

### Step 3: Parse the HTML

The response was an HTML page, so the extractor used:

```python
pd.read_html(StringIO(response.text))
```

The page contained two tables:

- table 0: the AQHI colour scale and category legend;
- table 1: the historical AQHI result table.

The function `find_aqhi_results_table()` selected the table whose columns contained `Date`, `AQHI`, and `Category`.

### Step 4: Clean the column names

The HTML column names were standardized to lowercase names with underscores.

For example:

```text
AQHI.1 → aqhi_1
```

### Step 5: Add source context

Each table was tagged with:

- project city;
- station name;
- station ID;
- requested year;
- value type;
- `show_day` code.

### Step 6: Combine the results

All successfully downloaded tables were combined with:

```python
pd.concat(..., ignore_index=True)
```

### Step 7: Respect the source server

The extractor waited 1.5 seconds between requests:

```python
time.sleep(1.5)
```

This prevented the script from sending all 42 requests at once.

### Step 8: Save the raw output

The final combined dataset was saved as:

```text
data/raw/aqo_historical_aqhi_2024_2026.csv
```

The daily-maximum anomaly report was saved as:

```text
data/raw/aqo_daily_max_date_anomalies_2024_2026.csv
```

---

## 9. Test Run

Before running all 42 requests, I tested the extractor using:

```text
Barrie
2026
daily_4pm
daily_max
```

The test configuration used:

```python
TEST_MODE = True
```

### Test results

| Value type | Rows returned | Unique dates |
|---|---:|---:|
| `daily_4pm` | 208 | 208 |
| `daily_max` | 209 | 202 |

Total test rows:

```text
417
```

Test date range:

```text
2026-01-01 to 2026-07-28
```

The test found:

- zero invalid dates;
- zero dates outside the requested year;
- one truly missing AQHI value;
- five values reported as `10+`;
- seven repeated station/date/value-type combinations;
- seven possible daily-maximum date-boundary anomalies.

The test files were:

```text
data/raw/aqo_test_barrie_2026.csv
data/raw/aqo_test_barrie_2026_anomalies.csv
```

The test run was important because it identified the source-level data issues before the full extraction.

---

## 10. Full Extraction Result

The full extraction completed successfully.

```text
Requests completed: 42 of 42
Failed requests: 0
Total rows: 13,347
Stations: 7
Years: 3
Value types: 2
Earliest returned date: 2024-01-01
Latest returned date: 2026-07-28
```

No values were missing in:

- `city`;
- `station_name`;
- `station_id`;
- `requested_year`;
- `value_type`;
- parsed `date`.

The full output file was:

```text
data/raw/aqo_historical_aqhi_2024_2026.csv
```

---

## 11. Full Row Counts

### Barrie

| Year | Value type | Rows |
|---:|---|---:|
| 2024 | daily 4:00 PM | 363 |
| 2024 | daily maximum | 367 |
| 2025 | daily 4:00 PM | 362 |
| 2025 | daily maximum | 366 |
| 2026 | daily 4:00 PM | 208 |
| 2026 | daily maximum | 209 |

### Kingston

| Year | Value type | Rows |
|---:|---|---:|
| 2024 | daily 4:00 PM | 364 |
| 2024 | daily maximum | 367 |
| 2025 | daily 4:00 PM | 364 |
| 2025 | daily maximum | 366 |
| 2026 | daily 4:00 PM | 209 |
| 2026 | daily maximum | 209 |

### Thunder Bay

| Year | Value type | Rows |
|---:|---|---:|
| 2024 | daily 4:00 PM | 433 |
| 2024 | daily maximum | 367 |
| 2025 | daily 4:00 PM | 516 |
| 2025 | daily maximum | 365 |
| 2026 | daily 4:00 PM | 206 |
| 2026 | daily maximum | 207 |

### Toronto Downtown

| Year | Value type | Rows |
|---:|---|---:|
| 2024 | daily 4:00 PM | 364 |
| 2024 | daily maximum | 367 |
| 2025 | daily 4:00 PM | 361 |
| 2025 | daily maximum | 363 |
| 2026 | daily 4:00 PM | 209 |
| 2026 | daily maximum | 209 |

### Toronto East

| Year | Value type | Rows |
|---:|---|---:|
| 2024 | daily 4:00 PM | 362 |
| 2024 | daily maximum | 367 |
| 2025 | daily 4:00 PM | 365 |
| 2025 | daily maximum | 366 |
| 2026 | daily 4:00 PM | 209 |
| 2026 | daily maximum | 209 |

### Toronto North

| Year | Value type | Rows |
|---:|---|---:|
| 2024 | daily 4:00 PM | 364 |
| 2024 | daily maximum | 367 |
| 2025 | daily 4:00 PM | 362 |
| 2025 | daily maximum | 366 |
| 2026 | daily 4:00 PM | 208 |
| 2026 | daily maximum | 209 |

### Toronto West

| Year | Value type | Rows |
|---:|---|---:|
| 2024 | daily 4:00 PM | 362 |
| 2024 | daily maximum | 367 |
| 2025 | daily 4:00 PM | 362 |
| 2025 | daily maximum | 364 |
| 2026 | daily 4:00 PM | 208 |
| 2026 | daily maximum | 209 |

---

## 12. Data Quality Problems and How They Were Handled

## 12.1 The wrong historical page initially appeared relevant

### Problem

Air Quality Ontario also provides a general historical search tool for pollutant concentrations such as:

- PM2.5;
- ozone;
- nitrogen dioxide;
- sulfur dioxide.

That source was not the correct source for this task because OWF-25 required historical AQHI values.

### Resolution

I used the AQHI-specific search page:

```text
https://www.airqualityontario.com/aqhi/search.php
```

### File responsible

The final source was implemented in:

```text
src/etl/extract_historical_aqhi.py
```

### Result

The extraction returned AQHI, category, date, and time rather than raw pollutant measurements.

Raw pollutant history remains a possible future feature source, but it was not included in OWF-25.

---

## 12.2 The request parameters were unknown

### Problem

The website uses an older PHP form. Guessing query parameter names returned the search form instead of historical results.

### Resolution

I manually submitted a search in the browser and copied the generated URL.

The Barrie test revealed the real parameter structure and confirmed:

```text
stationid=47045
show_day=0
start_year=2026
submit_search=Get+AQHI+values
```

A second manual test confirmed:

```text
show_day=2
```

for daily maximum values.

### File responsible

The confirmed parameters were added to:

```text
src/etl/extract_historical_aqhi.py
```

### Result

The script reproduced the browser request reliably.

---

## 12.3 Air Quality Ontario and GeoMet use different identifiers

### Problem

GeoMet uses codes such as:

```text
FAFFD
FEVJR
FCWFX
```

Air Quality Ontario uses numeric IDs such as:

```text
47045
52023
63200
```

### Resolution

I created an explicit station dictionary in:

```text
src/etl/extract_historical_aqhi.py
```

The dictionary stores:

```text
AQO station ID → project city and AQO station name
```

### Result

Each row contains both a project city and a source station identifier.

No station names or station IDs were missing in the final dataset.

---

## 12.4 The page contains an AQHI legend table before the results table

### Problem

`pandas.read_html()` found two HTML tables.

The first table was the AQHI colour legend, not the historical observation table.

Selecting `tables[0]` would have parsed the wrong table.

### Resolution

I created:

```python
find_aqhi_results_table()
```

inside:

```text
src/etl/extract_historical_aqhi.py
```

The function searches for a table with columns containing:

```text
Date
AQHI
Category
```

### Result

The extractor correctly selected table 1, the historical AQHI results table.

This was independently confirmed by:

```text
src/etl/diagnose_aqo_daily_max_html.py
```

---

## 12.5 The empty `aqhi_1` column

### Problem

The results table contained two HTML columns labelled AQHI.

After cleaning, pandas returned:

```text
aqhi
aqhi_1
```

The second column came from the coloured AQHI bar image.

### Diagnostic result

In the Barrie test:

```text
aqhi_1 non-null count: 0
```

It remained empty across the full extraction.

### Resolution

The extractor drops `aqhi_1` only when its non-null count is zero.

### File responsible

```text
src/etl/extract_historical_aqhi.py
```

### Result

The final CSV does not contain the empty presentation-only column.

The real numeric or text AQHI value remains in the dataset.

---

## 12.6 Missing AQHI values

### Problem

Some source rows contained a date and time but no AQHI value or category.

### Full result

```text
Truly missing AQHI values: 136
```

### Resolution

The values were not filled during extraction.

The original missing state was preserved in:

```text
aqhi_raw
aqhi_numeric
category
```

### File responsible

```text
src/etl/extract_historical_aqhi.py
```

### Treatment decision

The raw layer keeps these records unchanged.

Missing-value treatment will be decided during transformation and model preparation. Possible later options include:

- keeping the row as missing;
- excluding the row from a specific target series;
- using time-series imputation only when justified;
- reporting station-level completeness.

### Result

No artificial AQHI values were introduced during OWF-25.

---

## 12.7 AQHI values reported as `10+`

### Problem

The source sometimes reports:

```text
10+
```

This is a valid AQHI category value, not a missing value.

A direct numeric conversion would turn it into `NaN`.

### Full result

```text
AQHI values reported as 10+: 54
```

### Resolution

The extractor preserves three fields:

```text
aqhi_raw
aqhi_is_10_plus
aqhi_numeric
```

For `10+`:

```text
aqhi_raw = "10+"
aqhi_is_10_plus = True
aqhi_numeric = 10
```

The value `10` is only a numeric lower bound. The Boolean flag preserves the fact that the actual AQHI was reported above 10.

### File responsible

```text
src/etl/extract_historical_aqhi.py
```

### Result

`10+` values are usable in numeric checks without losing their original meaning.

---

## 12.8 Daily-maximum missing-date and duplicated-date pattern

### Problem

In `daily_max` mode, some dates were absent while the following date appeared twice with different times.

Example from Barrie 2026:

| Missing date | Duplicated reported date |
|---|---|
| 2026-02-01 | 2026-02-02 |
| 2026-03-03 | 2026-03-04 |
| 2026-04-07 | 2026-04-08 |
| 2026-04-20 | 2026-04-21 |
| 2026-07-11 | 2026-07-12 |
| 2026-07-20 | 2026-07-21 |
| 2026-07-25 | 2026-07-26 |

### Initial concern

This could have been caused by:

- incorrect pandas parsing;
- a table-selection error;
- a hidden date inside a link;
- the source page itself.

### Diagnostic file

```text
src/etl/diagnose_aqo_daily_max_html.py
```

### Diagnostic steps

The script:

1. fetched Barrie 2026 daily maximum HTML;
2. printed every table found by pandas;
3. selected the historical results table;
4. printed the suspicious rows before cleanup;
5. parsed the original HTML using BeautifulSoup;
6. inspected the original `<tr>` rows;
7. searched for links or hidden date metadata.

### Diagnostic result

The original HTML contained:

```text
2026-02-02, 12:00 am EST, AQHI 4
2026-02-02, 8:00 am EST, AQHI 6
```

The date `2026-02-01` was absent.

No hidden links were available in those rows.

### Conclusion

This is a source-level data anomaly. It is not caused by pandas or by the extraction script.

### Detection method

The function:

```python
find_possible_daily_max_date_anomalies()
```

in:

```text
src/etl/extract_historical_aqhi.py
```

flags cases where:

- a `daily_max` date appears more than once;
- the immediately previous calendar date is absent.

### Full result

```text
Possible within-year daily-maximum date-boundary anomalies: 147
```

### Treatment decision

The extractor does not:

- subtract one day;
- move either row to the missing date;
- select the larger value;
- remove the repeated rows.

The raw records remain exactly as returned by the source.

The anomaly report is saved separately:

```text
data/raw/aqo_daily_max_date_anomalies_2024_2026.csv
```

A transformation rule will only be applied after a defensible reporting-date definition is established.

---

## 12.9 Dates outside the requested year

### Problem

The full extraction found:

```text
Dates outside requested year: 14
```

### Diagnostic file

```text
src/etl/diagnose_aqo_full_quality.py
```

### Diagnostic steps

The script created:

```text
actual_year = year(date)
```

and compared it with:

```text
requested_year
```

It then saved every mismatch.

### Result

All 14 mismatches:

- occurred in `daily_max` mode;
- occurred on January 1 of the following year;
- appeared once for each of the seven stations for requested year 2024;
- appeared once for each of the seven stations for requested year 2025.

Examples:

```text
requested_year=2024, returned_date=2025-01-01
requested_year=2025, returned_date=2026-01-01
```

Most occurred near midnight, although the exact time varied and one returned observation occurred later in the day. The internal cause cannot be proven from the HTML alone.

### Output report

```text
data/processed/aqo_quality_reports/aqo_year_mismatch_rows.csv
```

### Detector gap

The original daily-maximum anomaly detector skipped comparisons that crossed into another year:

```python
if previous_date.year != requested_year:
    continue
```

This meant the 14 year-boundary rows were not included in the 147 within-year anomaly count.

### Treatment decision

The 14 rows remain in the raw dataset.

They are documented as year-boundary source anomalies and must be handled explicitly during transformation.

They are not automatically reassigned to December 31 because the source does not provide enough metadata to prove that correction for every row.

---

## 12.10 Thunder Bay daily 4:00 PM row inflation

### Problem

Thunder Bay returned far more `daily_4pm` rows than expected:

```text
2024: 433 rows
2025: 516 rows
```

A normal full year should contain approximately 365 or 366 daily records.

### Diagnostic file

```text
src/etl/diagnose_aqo_full_quality.py
```

### Diagnostic steps

The script:

1. isolated Thunder Bay station `63200`;
2. kept only `daily_4pm`;
3. limited the inspection to 2024 and 2025;
4. compared row counts with unique dates;
5. identified dates appearing more than once;
6. counted exact duplicate rows;
7. checked time values;
8. checked same-date and same-time records with different AQHI values.

### Diagnostic result

#### 2024

```text
Rows: 433
Unique dates: 363
Extra rows: 70
```

#### 2025

```text
Rows: 516
Unique dates: 363
Extra rows: 153
```

Combined results:

```text
Dates appearing more than once: 223
Rows belonging to repeated dates: 446
Rows that are part of exact duplicate groups: 444
Same date/time combinations with different AQHI values: 1
```

The two valid times shown were:

```text
4:00 pm EST
4:00 pm EDT
```

The difference between EST and EDT reflected daylight-saving time, not an unexpected observation time.

### Exact-duplicate interpretation

The 444 rows represent 222 identical pairs.

A future `drop_duplicates()` operation would remove 222 redundant copies, not 444 unique observations.

### Treatment decision

The raw file keeps all rows.

During transformation:

- exact duplicate rows can be safely deduplicated;
- the one conflicting pair must not be resolved by ordinary deduplication.

---

## 12.11 Thunder Bay conflicting AQHI values

### Problem

One Thunder Bay date and time had two different AQHI values:

```text
Station: Thunder Bay
Date: 2025-03-25
Time: 4:00 pm EDT
Value 1: 3
Value 2: 2
Category for both: low risk
```

### Diagnostic file

```text
src/etl/diagnose_thunder_bay_conflict.py
```

### Diagnostic steps

The script compared the conflict across three levels:

1. the saved raw CSV;
2. the table parsed by pandas from a fresh source request;
3. the original HTML rows parsed with BeautifulSoup.

It also saved the full source page as:

```text
data/raw/aqo_thunder_bay_2025_daily_4pm_conflict_debug.html
```

### Diagnostic result

The saved CSV contained both values.

`pandas.read_html()` returned both values.

The original HTML contained two separate rows:

```text
2025-03-25, 4:00 pm EDT, AQHI 3
2025-03-25, 4:00 pm EDT, AQHI 2
```

Both rows used:

- the same station;
- the same date;
- the same time;
- the same category;
- the same link;
- the same HTML row identifier pattern.

### Conclusion

The conflict exists in the Air Quality Ontario source.

It is not an extraction or parsing error.

### Treatment decision

The raw layer keeps both records.

The transformation layer should:

- flag the records as a source-value conflict;
- avoid selecting `2`, `3`, the maximum, or the average without evidence;
- exclude the date from a numeric target series if a single authoritative value cannot be established;
- retain the category-level observation if the analysis only uses the risk category, since both values are `low risk`.

---

## 13. Quality Reports Created

The full quality diagnostic saved reports in:

```text
data/processed/aqo_quality_reports/
```

Files created:

```text
aqo_year_mismatch_rows.csv
thunder_bay_daily_4pm_year_summary.csv
thunder_bay_daily_4pm_duplicate_dates.csv
thunder_bay_daily_4pm_duplicate_rows.csv
thunder_bay_daily_4pm_time_summary.csv
thunder_bay_daily_4pm_exact_duplicates.csv
thunder_bay_daily_4pm_datetime_conflicts.csv
```

These reports were created from the saved historical CSV. They did not change the raw dataset.

---

## 14. Final Raw Dataset Columns

After validation and removal of the empty HTML artifact column, the main dataset contains:

| Column | Description |
|---|---|
| `date` | Date returned by Air Quality Ontario |
| `time` | Observation time including EST or EDT |
| `aqhi` | AQHI value as originally parsed from the HTML table |
| `category` | AQHI health-risk category |
| `city` | Project city |
| `station_name` | Air Quality Ontario station name |
| `station_id` | Numeric Air Quality Ontario station ID |
| `requested_year` | Year sent in the request |
| `value_type` | `daily_4pm` or `daily_max` |
| `show_day_code` | `0` for daily 4:00 PM or `2` for daily maximum |
| `aqhi_raw` | Original AQHI value preserved as text |
| `aqhi_is_10_plus` | Boolean flag for values reported as `10+` |
| `aqhi_numeric` | Numeric AQHI value; `10+` is represented as lower bound 10 |

The empty column `aqhi_1` was removed only after confirming that it contained no values.

---

## 15. Data Preservation Rules

The following rules were used throughout OWF-25:

1. The raw CSV must remain as close as possible to the source output.
2. Missing AQHI values are not imputed during extraction.
3. `10+` is not treated as missing.
4. Daily-maximum dates are not shifted based on an unproven assumption.
5. Repeated daily-maximum rows are not removed during extraction.
6. Thunder Bay exact duplicates are documented but retained in the raw layer.
7. The Thunder Bay conflicting pair is preserved.
8. Quality issues are written to separate reports.
9. Correction and model-preparation rules belong in a later transformation task.
10. Diagnostic scripts must not overwrite or modify the raw dataset.

---

## 16. Recommended Transformation Rules

The next task should create a processed AQHI dataset without changing the raw files.

A future script such as:

```text
src/etl/transform_aqo_historical_aqhi.py
```

should apply documented rules such as:

### Exact duplicates

- remove only exact duplicate rows;
- record how many redundant copies were removed;
- do not use a broad station/date-only deduplication rule.

### Conflicting source values

- create a `source_value_conflict` flag;
- preserve both conflicting source records in an audit table;
- exclude unresolved conflicts from a numeric target series.

### `10+` values

- preserve `aqhi_raw`;
- preserve `aqhi_is_10_plus`;
- treat `aqhi_numeric=10` as a lower bound, not an exact value;
- consider censored-value handling during modeling.

### Missing AQHI

- calculate completeness by station, year, and value type;
- avoid filling gaps before reviewing their duration and context;
- document any imputation method used later.

### Daily-maximum date anomalies

- preserve an anomaly flag;
- include both within-year and year-boundary cases;
- do not shift dates until the reporting definition can be justified;
- consider using an alternative hourly source to reconstruct daily maximum values.

### Toronto

- keep the four Toronto zones separate in the raw and processed station-level datasets;
- defer any city-wide aggregation to EDA;
- document the selected aggregation rule if one is later used.

---

## 17. Modeling Implications

The extraction preserved both candidate targets, but their quality differs.

### Daily 4:00 PM AQHI

Advantages:

- fixed observation time;
- clearer date meaning;
- easier alignment across stations;
- most duplicate problems are exact duplicates that can be removed safely.

Known issues:

- missing values;
- one confirmed conflicting Thunder Bay source value;
- occasional station-level gaps.

### Daily maximum AQHI

Advantages:

- better representation of the highest daily health risk;
- potentially more relevant to wildfire-smoke impact.

Known issues:

- systematic missing-date and duplicated-date pattern;
- 147 flagged within-year anomalies;
- 14 year-boundary spillover rows;
- uncertain reporting-date interpretation.

### Current position

The final model target was not changed inside OWF-25.

Based on the observed data quality, daily 4:00 PM AQHI is currently the cleaner candidate for the first forecasting baseline. Daily maximum AQHI should not be used as the primary target until the date-boundary issue is resolved or the daily maximum is reconstructed from a reliable hourly source.

This is a modeling recommendation, not a transformation applied to the raw data.

---

## 18. How to Run the Files

### Test extraction

In:

```text
src/etl/extract_historical_aqhi.py
```

set:

```python
TEST_MODE = True
```

Run:

```bash
python src/etl/extract_historical_aqhi.py
```

### Full extraction

Set:

```python
TEST_MODE = False
```

Run:

```bash
python src/etl/extract_historical_aqhi.py
```

### Daily-maximum HTML diagnostic

```bash
python src/etl/diagnose_aqo_daily_max_html.py
```

### Full local quality diagnostic

```bash
python src/etl/diagnose_aqo_full_quality.py
```

### Thunder Bay conflict diagnostic

```bash
python src/etl/diagnose_thunder_bay_conflict.py
```

---

## 19. Final Result

OWF-25 successfully downloaded and validated historical AQHI data from Air Quality Ontario.

Final extraction result:

```text
42 successful requests
13,347 raw rows
7 stations
3 requested years
2 AQHI value types
136 truly missing AQHI values
54 values reported as 10+
384 repeated station/date/value-type combinations
147 flagged within-year daily-maximum date anomalies
14 additional year-boundary mismatch rows
444 Thunder Bay rows belonging to exact duplicate groups
1 unresolved Thunder Bay same-date/time source conflict
```

The final primary files are:

```text
data/raw/aqo_historical_aqhi_2024_2026.csv
data/raw/aqo_daily_max_date_anomalies_2024_2026.csv
```

The raw extraction is complete.

The data is not yet model-ready because the documented quality issues still require transformation rules. OWF-25 therefore completes the download, source characterization, and raw validation work. Deduplication, conflict flags, missing-value treatment, and final target selection belong to the next data-processing stage.

---

## 20. OWF-25 Completion Status

The following OWF-25 requirements were completed:

- [x] Identified the correct historical AQHI source
- [x] Confirmed the Air Quality Ontario request parameters
- [x] Confirmed both historical value modes
- [x] Created the seven-station project mapping
- [x] Tested the extraction on Barrie 2026
- [x] Downloaded 2024, 2025, and 2026 year-to-date
- [x] Completed all 42 requests
- [x] Saved the combined raw dataset
- [x] Preserved `10+` values correctly
- [x] Preserved missing values
- [x] Diagnosed the daily-maximum date issue at the raw HTML level
- [x] Created a daily-maximum anomaly report
- [x] Identified and reported year-boundary rows
- [x] Diagnosed Thunder Bay exact duplicates
- [x] Confirmed the Thunder Bay conflicting value in the original HTML
- [x] Preserved the raw data without unsupported corrections
- [x] Documented the remaining transformation work

OWF-25 is complete as a historical data extraction and raw-data validation task.
