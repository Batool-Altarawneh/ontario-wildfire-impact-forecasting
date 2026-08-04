# OWF-48 - ECCC Hourly Weather Data Extraction

## Project

Ontario Wildfire Impact and Forecasting Analytics

## Work Item

OWF-48 - Extract ECCC hourly weather data for the selected Ontario cities

## Author

Batool Altarawneh

## Project Type

Academic and independent portfolio project

## Completion Status

Complete as an hourly weather extraction and preliminary coverage-validation task.

The extraction pipeline is working and the required January 2024 through July 2026 files were downloaded successfully for all four cities. The output has complete monthly row counts and the intended start and end timestamps.

Field-level missing-value analysis, timestamp normalization, weather transformations, daily aggregation, and model-ready preparation remain separate follow-up work.

---

## 1. Purpose of This Task

The purpose of OWF-48 was to build a repeatable Python extraction process for historical hourly weather observations from Environment and Climate Change Canada.

The project needs city-level weather because wildfire activity alone does not explain changes in the Air Quality Health Index. AQHI can also be affected by wind, humidity, temperature, precipitation, local pollution, and smoke transport conditions.

The four project cities are:

- Barrie
- Kingston
- Thunder Bay
- Toronto

The required extraction period was:

```text
January 1, 2024 through July 31, 2026
```

The main objectives were to:

1. Confirm the correct ECCC bulk-download method.
2. Identify the exact internal station IDs required by the download tool.
3. Preserve the previously selected station mapping from OWF-27.
4. Download hourly observations for all four stations.
5. Preserve every original monthly CSV.
6. Make the script restartable after a partial failure.
7. Test the process on one station and one month before scaling it.
8. Combine the downloaded files into one project dataset.
9. Add project-specific city and station metadata.
10. Standardize column names without changing source values.
11. Validate monthly row counts and the overall date range.
12. Record unresolved transformation and quality requirements honestly.

This task focused on extraction and preliminary structural validation. It did not silently convert units, fill missing values, normalize time zones, or create final daily modeling features.

---

## 2. Relationship to OWF-27

OWF-27 answered the source-design question: where should temperature, humidity, wind, and precipitation come from?

That investigation produced a two-source weather design:

| Weather context | Source |
|---|---|
| Weather at wildfire or hotspot locations | CWFIS fields |
| Weather at the four project cities | ECCC Historical Climate Data |

The CWFIS hotspot records already include useful weather fields near fire locations. However, a city may be far from the wildfire itself. The AQHI forecast therefore also requires weather measured near the city.

OWF-27 selected one primary hourly ECCC station for each city. OWF-48 implemented the download process for those selected stations.

---

## 3. Why Hourly Weather Was Required

Daily weather summaries would have been easier to download and manage, but hourly observations were selected for several reasons.

Hourly data preserves:

- changes in wind speed during the day;
- changes in wind direction;
- short precipitation events;
- temperature and humidity cycles;
- the ability to align weather with hourly AQHI observations;
- the ability to define custom daily aggregation rules later;
- the number of valid observations behind each daily feature.

This is important because wind conditions can change substantially within one day. A daily average alone may hide the period when smoke was transported toward a city.

The hourly source also allows the project to calculate daily features later, such as:

| Source variable | Possible later daily features |
|---|---|
| Temperature | mean, minimum, maximum |
| Relative humidity | mean, minimum, maximum |
| Precipitation | total |
| Wind speed | mean and maximum |
| Wind direction | vector-based mean or wind components |
| Observation availability | valid hourly count and missing percentage |

OWF-48 preserves the hourly source data so those decisions can be made during transformation and EDA rather than being forced during extraction.

---

## 4. ECCC Source Used

The source used in OWF-48 was the Environment and Climate Change Canada Historical Climate Data bulk-download service.

The base download endpoint is:

```text
https://climate.weather.gc.ca/climate_data/bulk_data_e.html
```

The confirmed request pattern is:

```text
https://climate.weather.gc.ca/climate_data/bulk_data_e.html
?format=csv
&stationID={STATION_ID}
&Year={YEAR}
&Month={MONTH}
&Day=14
&timeframe=1
&submit=Download+Data
```

The parameters used by the script are:

| Parameter | Meaning |
|---|---|
| `format=csv` | Return CSV data |
| `stationID` | Internal ECCC station ID required by the bulk tool |
| `Year` | Requested year |
| `Month` | Requested month |
| `Day=14` | Placeholder used by the official request pattern |
| `timeframe=1` | Hourly data |
| `submit=Download Data` | Download action |

The service returns one station and one month per request.

This limitation directly affected the script design. The required period contains 31 months, and the project has four cities:

```text
31 months x 4 stations = 124 station-month requests
```

---

## 5. How the Bulk-Download Pattern Was Confirmed

### 5.1 Initial Problem

The ECCC station page contained a link called `Get More Data`.

I expected the link to open a normal form where I could select:

- hourly data;
- CSV format;
- a start date;
- an end date.

Instead, the link opened an Apache directory index:

```text
/cmc/climate/Get_More_Data_Plus_de_donnees/
```

The page listed files such as:

```text
Command_Lines_EN.txt
Station Inventory EN.csv
```

At first, this looked like the wrong page because it was not a regular web form.

### 5.2 Investigation

I did not guess URL parameters immediately.

I reviewed the files exposed by the official directory, especially the English command-line instructions. That information confirmed that ECCC supports direct bulk requests and showed the required parameter structure.

I then tested a real request for Barrie-Oro using:

- Station ID `42183`
- Year `2024`
- Month `1`
- Hourly timeframe
- CSV format

### 5.3 Resolution

The direct request returned a valid hourly CSV for January 2024.

This confirmed:

- the bulk endpoint;
- the parameter names;
- the hourly timeframe code;
- the use of the internal Station ID;
- the one-month-per-request behaviour.

### 5.4 Result

The extraction script could be built from a verified request pattern rather than an assumed URL.

This followed the same project rule used for the other data sources: verify the real source behaviour manually before automating it.

---

## 6. Station Identification Problem

### 6.1 The Two-ID System

ECCC uses more than one identifier for a station.

The selected stations were originally documented using Climate IDs, such as:

```text
BARRIE-ORO Climate ID: 6117700
```

However, the bulk-download endpoint does not use the Climate ID. It requires a different numeric value called `Station ID`.

Using the wrong identifier would either return no data or download data for the wrong record.

### 6.2 Resolution

I used the official ECCC station inventory to cross-check the selected station names, Climate IDs, internal Station IDs, coordinates, and other station metadata.

The final mapping used by OWF-48 is:

| Project city | Station name | Climate ID | Station ID | Hourly coverage shown in inventory |
|---|---|---:|---:|---|
| Barrie | BARRIE-ORO | `6117700` | `42183` | 2003-2026 |
| Kingston | KINGSTON CLIMATE | `6104142` | `47267` | 2008-2026 |
| Thunder Bay | THUNDER BAY CS | `6048268` | `30682` | 2000-2026 |
| Toronto | TORONTO CITY | `6158355` | `31688` | 2002-2026 |

The coordinates, WMO information, station names, and IDs aligned with the earlier manual station research.

### 6.3 Result

All four selected stations were confirmed using one official inventory source.

The script stores both identifier types:

- `project_station_id`
- `project_climate_id`

This prevents the two systems from being confused later.

---

## 7. Why These Four Stations Were Retained

The station-selection reasoning was completed in OWF-27, but it is summarized here because the extraction depends on it.

### Barrie

Selected station:

```text
BARRIE-ORO
Climate ID: 6117700
Station ID: 42183
```

Reason:

- hourly coverage;
- ECCC-MSC source;
- appropriate proximity to Barrie;
- required weather fields available.

### Kingston

Selected station:

```text
KINGSTON CLIMATE
Climate ID: 6104142
Station ID: 47267
```

Reason:

- hourly coverage;
- ECCC-MSC operator;
- appropriate city representation;
- selected instead of ambiguous airport records;
- an earlier monthly CSV test confirmed the required fields.

### Thunder Bay

Selected station:

```text
THUNDER BAY CS
Climate ID: 6048268
Station ID: 30682
```

Reason:

- hourly coverage;
- ECCC-MSC source;
- appropriate location;
- better alignment with the project’s city-level weather requirement than alternative airport records.

### Toronto

Selected station:

```text
TORONTO CITY
Climate ID: 6158355
Station ID: 31688
```

Reason:

- hourly coverage;
- ECCC-MSC source;
- city-level representation;
- better alignment with the Toronto AQHI use case than Pearson Airport;
- daily-only alternatives were not suitable for the hourly pipeline.

---

## 8. Exact Extraction Window

The project period was set explicitly in the script:

```python
START_YEAR = 2024
START_MONTH = 1

END_YEAR = 2026
END_MONTH = 7
```

The script creates a list of all required year-month pairs:

```text
2024-01
2024-02
...
2025-12
2026-01
...
2026-07
```

This produces exactly 31 months per station.

The end month was set explicitly instead of using the computer’s current month. This makes the extraction reproducible. A future run will not silently expand the project dataset beyond July 2026 unless the code is intentionally updated.

---

## 9. Script Location

The extraction script is stored at:

```text
src/etl/extract_eccc_hourly_weather.py
```

This matches the repository structure used for the other data-source extractors:

```text
src/etl/extract_cwfis_hotspots.py
src/etl/extract_current_aqhi.py
src/etl/extract_historical_aqhi.py
src/etl/extract_ontario_active_fires.py
src/etl/extract_eccc_hourly_weather.py
```

The script must be run from the project root because its output paths are relative to that location.

---

## 10. Output Folder Design

The script separates raw, processed, and quality outputs.

```text
data/
├── raw/
│   └── eccc_weather/
├── processed/
│   └── eccc_weather/
└── quality/
    └── eccc_weather/
```

### Raw folder

```text
data/raw/eccc_weather/
```

Contains one original CSV for each station-month combination.

Example:

```text
barrie_42183_2024_01.csv
kingston_47267_2025_06.csv
thunder_bay_30682_2026_07.csv
toronto_31688_2024_12.csv
```

The raw files are preserved exactly as downloaded.

### Processed folder

```text
data/processed/eccc_weather/
```

Contains the combined dataset with:

- standardized column names;
- project city;
- project station name;
- Station ID;
- Climate ID.

Example output:

```text
eccc_hourly_weather_20260803T185712Z.csv
```

### Quality folder

```text
data/quality/eccc_weather/
```

Contains a text summary of the extraction.

Example output:

```text
eccc_weather_extraction_summary_20260803T185712Z.txt
```

---

## 11. Script Design

The script was designed around reliability and traceability rather than only downloading files as quickly as possible.

### 11.1 Configuration Section

The script stores:

- the ECCC endpoint;
- station metadata;
- start and end dates;
- request timeout;
- delay between requests;
- retry count;
- retry wait time;
- test mode;
- output folders.

Keeping these values near the top makes the script easier to review and update.

### 11.2 Month-List Creation

A function builds the required month sequence from the start month through the end month.

The logic:

1. Start at January 2024.
2. Add the current year-month pair to a list.
3. Increase the month by one.
4. After December, move to January of the next year.
5. Stop after July 2026.

This avoids manually writing 31 month values and reduces the risk of skipping a month.

### 11.3 Response Validation

A successful HTTP status does not guarantee that the response is a valid data file.

The server could return:

- an error page;
- an empty result;
- HTML;
- a CSV without observations.

The script checks that the response contains:

```text
Date/Time
```

and more than one line.

If those conditions are not met, the response is not saved as valid weather data.

### 11.4 Retry Logic

Network requests can fail because of:

- a temporary connection problem;
- a timeout;
- an HTTP server error.

The script allows up to three attempts for a failed request.

It waits longer after each failure:

```text
Attempt 1 failure: wait 5 seconds
Attempt 2 failure: wait 10 seconds
```

The full run did not require retries, but the logic remains important for future reproducibility.

### 11.5 Politeness Delay

The script waits 1.5 seconds after each new request.

This prevents the program from sending 124 requests as quickly as possible to a public government service.

The delay increases runtime slightly, but it is a more responsible extraction pattern.

### 11.6 Resumability

Before downloading a file, the script checks whether the expected raw file already exists.

If it exists:

1. The download is skipped.
2. The existing file is read from disk.
3. The file is still included in the combined output.

This means a partial run does not have to restart from the first request.

It also made the transition from test mode to full mode efficient: the January 2024 Barrie test file was reused rather than downloaded again.

### 11.7 Raw-File Preservation

New downloads are written as response bytes:

```python
file_path.write_bytes(response.content)
```

This preserves the original monthly files instead of rewriting them through pandas.

The processed output is separate from the source files.

### 11.8 Reading and Combining Files

After a file is downloaded or found on disk, pandas reads it into a DataFrame.

The script adds:

```text
project_city
project_station_name
project_station_id
project_climate_id
```

Every monthly DataFrame is added to a list.

At the end, `pandas.concat()` combines them into one table.

### 11.9 Column-Name Standardization

The source column names contain spaces, punctuation, parentheses, and units.

The script standardizes names by:

1. removing outside spaces;
2. converting text to lowercase;
3. replacing non-alphanumeric characters with underscores;
4. removing underscores from the beginning and end.

Example:

```text
Date/Time (LST)
```

becomes:

```text
date_time_lst
```

This change makes the fields easier to use in Python and PostgreSQL.

The values inside the columns are not transformed during this step.

### 11.10 Timestamped Outputs

The combined dataset and summary use a UTC timestamp in their filenames.

This prevents one run from overwriting a previous result and makes each output traceable to a specific execution.

---

## 12. Test-Mode Strategy

### 12.1 Why Test Mode Was Added

The full extraction required 124 station-month requests.

Running all requests before proving the request pattern would have increased the cost of any mistake. Possible problems included:

- incorrect Station ID;
- wrong timeframe code;
- invalid CSV parsing;
- unexpected column names;
- wrong output paths;
- response validation failure.

### 12.2 Test Configuration

The script initially used:

```python
TEST_MODE = True
```

This reduced the extraction to:

```text
Barrie-Oro
January 2024
Station ID 42183
```

### 12.3 Test Command

From the repository root:

```bash
python src/etl/extract_eccc_hourly_weather.py
```

### 12.4 Test Result

The test downloaded:

```text
data/raw/eccc_weather/barrie_42183_2024_01.csv
```

The script read:

```text
744 rows
```

The expected calculation was:

```text
31 days x 24 hours = 744 rows
```

The detected timestamp range was:

```text
2024-01-01 00:00
through
2024-01-31 23:00
```

The test produced:

```text
Failed files: 0
```

It also successfully generated:

- one processed combined file;
- one extraction summary;
- cleaned column names;
- the wind-direction unit reminder.

### 12.5 Test Conclusion

The request pattern, Station ID, file parsing, folder creation, column cleaning, and output generation all worked.

Only after this test passed was `TEST_MODE` changed to `False`.

---

## 13. Resumability Test

The January Barrie file created during test mode remained inside the raw folder.

When the full run started, the first file produced this message:

```text
File already exists. Skipping download.
Rows read: 744
```

This confirmed that the script did not send a duplicate request.

The final full-run summary reported:

```text
New files downloaded: 123
Existing files skipped: 1
```

The skipped file was still read and included in the processed dataset.

This was direct evidence that resumability worked as designed.

---

## 14. Full Extraction

After test mode succeeded, the script was changed to:

```python
TEST_MODE = False
```

The same command was used:

```bash
python src/etl/extract_eccc_hourly_weather.py
```

The full run processed:

```text
4 stations x 31 months = 124 expected files
```

The request order was:

1. Barrie, January 2024 through July 2026
2. Kingston, January 2024 through July 2026
3. Thunder Bay, January 2024 through July 2026
4. Toronto, January 2024 through July 2026

The script displayed the current file number and total count during the run, for example:

```text
[63/124] Thunder Bay - 2024-01
[100/124] Toronto - 2024-07
[124/124] Toronto - 2026-07
```

This made it possible to monitor progress and identify a failure position if one occurred.

---

## 15. Full-Run Result

The final extraction summary was:

```text
Expected files: 124
New files downloaded: 123
Existing files skipped: 1
Failed files: 0
Total rows: 90,528
```

No request failed.

No retry was required.

The combined row counts were:

| City | Rows |
|---|---:|
| Barrie | 22,632 |
| Kingston | 22,632 |
| Thunder Bay | 22,632 |
| Toronto | 22,632 |
| Total | 90,528 |

The detected date range was:

```text
Minimum: 2024-01-01 00:00
Maximum: 2026-07-31 23:00
```

The processed output was:

```text
data/processed/eccc_weather/eccc_hourly_weather_20260803T185712Z.csv
```

The extraction summary was:

```text
data/quality/eccc_weather/eccc_weather_extraction_summary_20260803T185712Z.txt
```

---

## 16. Calendar-Based Validation

The first structural validation compared monthly row counts with the expected number of hours in each calendar month.

### 31-day months

Expected:

```text
31 x 24 = 744 rows
```

Observed examples:

```text
January: 744
March: 744
May: 744
July: 744
August: 744
October: 744
December: 744
```

### 30-day months

Expected:

```text
30 x 24 = 720 rows
```

Observed examples:

```text
April: 720
June: 720
September: 720
November: 720
```

### February 2024

2024 was a leap year.

Expected:

```text
29 x 24 = 696 rows
```

Observed:

```text
696 rows per city
```

### February 2025 and February 2026

These were not leap years.

Expected:

```text
28 x 24 = 672 rows
```

Observed:

```text
672 rows per city
```

### Result

Every month had the expected number of hourly rows.

This is a useful validation because a parser problem, accidental filtering, missing file, or incomplete response would likely create a monthly row-count mismatch.

---

## 17. Total-Row Validation

The complete period contains:

```text
2024: 366 days
2025: 365 days
January through July 2026: 212 days
```

Total:

```text
366 + 365 + 212 = 943 days
```

Expected rows per city:

```text
943 days x 24 hours = 22,632 rows
```

Expected rows for four cities:

```text
22,632 x 4 = 90,528 rows
```

Observed:

```text
22,632 rows per city
90,528 rows total
```

### Result

The final combined row count exactly matched the calendar calculation.

This confirmed that the concatenation step included all four cities and all required months.

---

## 18. Date-Range Validation

The intended start was:

```text
2024-01-01 00:00
```

The intended end was:

```text
2026-07-31 23:00
```

The processed data reported exactly those values.

### Result

The extraction was not truncated at the beginning or end.

The explicit project window was followed correctly.

---

## 19. Problems, Investigations, Resolutions, and Results

## 19.1 `Get More Data` did not open a normal date-range form

### Problem

The station-page link opened a directory index instead of the expected download form.

### Investigation

I reviewed the official files listed in the directory, including the English command-line instructions and station inventory.

### Resolution

The instructions revealed the official bulk-download endpoint and parameter pattern.

### Result

I built the script from confirmed parameters rather than guessed ones.

---

## 19.2 Climate ID and Station ID were easy to confuse

### Problem

The station decisions were documented using Climate IDs, but the bulk tool required Station IDs.

### Investigation

I used the official station inventory to match station name, Climate ID, Station ID, coordinates, WMO information, and coverage.

### Resolution

I created an explicit mapping containing both identifier types.

### Result

All four requests used the correct internal Station IDs, and both IDs were added to the processed output.

---

## 19.3 The service supports one month per request

### Problem

A single request could not download the complete 2024-2026 range for one station.

### Investigation

The verified URL format included one `Year` and one `Month` value.

### Resolution

I generated the full list of 31 required months and used nested station and month loops.

### Result

The script created 124 station-month combinations without manually listing each request.

---

## 19.4 The extraction volume was larger than the earlier sources

### Problem

The full run required 124 requests. A failure late in the run could have wasted time if every request had to be repeated.

### Resolution

I added file-existence checks before each request.

### Result

The script is resumable. Existing raw files are reused, and the test file was successfully skipped during the full run.

---

## 19.5 An HTTP success response might not be valid weather data

### Problem

A status code alone does not prove that the server returned a usable CSV.

### Resolution

The script checks for a `Date/Time` header and multiple lines before saving a response.

### Result

An empty page or error document will not be treated as a successful weather file.

---

## 19.6 Network failures were possible

### Problem

A long multi-request run can be interrupted by timeouts or temporary server problems.

### Resolution

I added:

- a 60-second timeout;
- up to three attempts;
- increasing waits between attempts.

### Result

The full extraction did not need any retries, but the script remains safer for future runs.

---

## 19.7 Public-server request rate needed to be controlled

### Problem

Sending 124 requests without a pause would be unnecessarily aggressive.

### Resolution

I added a 1.5-second delay after each new request.

### Result

The extraction completed successfully while using a more responsible request pattern.

---

## 19.8 Raw source files needed to remain unchanged

### Problem

Combining and cleaning the data could make it difficult to prove what ECCC originally returned.

### Resolution

I stored every original monthly response separately and created the combined file in a different folder.

### Result

The project retains a traceable raw layer and a separate processed layer.

---

## 19.9 Source column names were difficult to use programmatically

### Problem

The ECCC headers contain spaces, punctuation, parentheses, and units.

### Resolution

I standardized only the column names.

### Result

Fields such as:

```text
Date/Time (LST)
```

became:

```text
date_time_lst
```

The original source values were not changed.

---

## 19.10 Wind direction uses a non-obvious unit

### Problem

The source reports wind direction in tens of degrees.

A value such as:

```text
27
```

represents:

```text
270 degrees
```

Using the raw value as if it were ordinary degrees would be incorrect.

### Resolution

The extraction script prints a reminder and leaves the source value unchanged.

### Result

The unit issue is visible and documented. The conversion will be performed deliberately during transformation rather than silently inside extraction.

---

## 19.11 Wind direction cannot be averaged with a simple arithmetic mean

### Problem

Direction is circular.

For example, an arithmetic average of:

```text
350 degrees and 10 degrees
```

would incorrectly produce:

```text
180 degrees
```

even though both observations are near north.

### Resolution

The extraction preserves the original direction values.

The later transformation stage should use:

- vector components;
- sine and cosine features;
- or a circular mean.

### Result

OWF-48 does not create a misleading daily average.

---

## 19.12 ECCC timestamps are in Local Standard Time

### Problem

The source timestamp field is labelled:

```text
date_time_lst
```

The ECCC documentation notes that Local Standard Time is used. Ontario also observes Daylight Saving Time, so direct alignment with AQHI or wildfire timestamps requires care.

### Resolution

OWF-48 preserves the source timestamp and does not pretend it is UTC.

The follow-up transformation must:

1. preserve the original local source time;
2. apply the correct Ontario time-zone rules;
3. create a normalized timestamp;
4. define the daily boundary;
5. align all sources to the same standard.

### Result

No unsupported time conversion was applied during extraction.

---

## 19.13 Complete row counts do not prove every weather value is present

### Problem

Every expected hourly row exists, but an existing row may still contain a blank value for:

- temperature;
- humidity;
- wind speed;
- wind direction;
- precipitation;
- pressure;
- other fields.

### Resolution

I separated structural extraction validation from field-level data-quality profiling.

### Result

OWF-48 can report complete files, rows, and timestamps without making the unsupported claim that every measurement value is complete.

A detailed missingness and range analysis remains follow-up work.

---

## 20. Data Governance Principles Used

### Preserve the raw source

The original monthly CSV files are stored unchanged.

### Separate extraction from transformation

OWF-48 downloads and combines data but does not apply uncertain modeling transformations.

### Keep identifiers explicit

Climate ID and Station ID are stored in separate fields.

### Verify before automating

The bulk pattern was confirmed through a real browser and CSV test before the full loop was written.

### Test before scaling

One station and one month were processed before the 124-file run.

### Make the process restartable

Existing files are reused instead of downloaded again.

### Do not hide units

The wind-direction unit is documented and preserved.

### Do not claim more validation than was performed

The extraction has complete structural coverage, but field-level completeness still needs to be measured.

### Preserve uncertainty for later decisions

Time-zone handling, missing values, source flags, and daily aggregation rules are deferred rather than guessed.

---

## 21. Current Output Fields

The exact ECCC columns are preserved after column-name standardization.

The script also adds these project metadata fields:

| Field | Purpose |
|---|---|
| `project_city` | Project city represented by the station |
| `project_station_name` | Selected ECCC station name |
| `project_station_id` | Internal ID used by the download endpoint |
| `project_climate_id` | Public Climate ID used in ECCC station records |

The main time field found in the output is:

```text
date_time_lst
```

The wind-direction field found in the output is:

```text
wind_dir_10s_deg
```

The exact processed schema should be documented again after field-level profiling and type conversion are completed.

---

## 22. What OWF-48 Completed

OWF-48 completed the following:

- confirmed the official ECCC bulk-download process;
- confirmed the required URL parameters;
- confirmed the four internal Station IDs;
- cross-validated the Station IDs against the selected Climate IDs;
- implemented a repeatable Python extractor;
- implemented one-station test mode;
- implemented retries and timeouts;
- implemented a delay between requests;
- implemented response validation;
- implemented resumability;
- preserved 124 raw monthly files;
- combined all station-month files;
- added project station metadata;
- standardized column names;
- saved a processed snapshot;
- saved an extraction summary;
- validated expected monthly row counts;
- validated expected rows per city;
- validated the overall row count;
- validated the minimum and maximum timestamps;
- documented the wind-direction unit;
- preserved Local Standard Time without an unsupported conversion.

---

## 23. What OWF-48 Did Not Complete

The following items were intentionally not performed inside this extraction task:

- full missing-value profiling by field;
- duplicate timestamp analysis;
- weather-range validation;
- source-flag frequency analysis;
- Local Standard Time to UTC conversion;
- Daylight Saving Time normalization;
- wind-direction conversion to degrees;
- wind vector feature creation;
- hourly-to-daily aggregation;
- imputation;
- fallback-station substitution;
- AQHI joins;
- wildfire-distance joins;
- PostgreSQL loading;
- Airflow scheduling;
- baseline or LSTM modeling.

These tasks should be handled in transformation, quality, schema, EDA, and orchestration work items.

---

## 24. Recommended Next Data-Quality Checks

The next validation script should inspect the processed dataset and create auditable reports.

Recommended checks:

1. Count rows by city, year, and month.
2. Confirm expected hourly row counts.
3. Parse `date_time_lst` explicitly.
4. Detect duplicate city-station-timestamp combinations.
5. Detect missing timestamp intervals.
6. Calculate missing percentages for each weather field.
7. Calculate missing percentages by city and year.
8. Profile source flags.
9. Check temperature ranges.
10. Check relative-humidity ranges.
11. Check wind-speed ranges.
12. Check wind-direction values.
13. Check for negative precipitation.
14. Check station metadata consistency.
15. Review Local Standard Time and Daylight Saving Time handling.
16. Define minimum hourly coverage for a valid daily aggregate.
17. Save machine-readable CSV reports and a written summary.

The quality work should distinguish:

- a missing row;
- a present row with missing measurements;
- calm wind with missing direction;
- non-calm wind with missing direction;
- flagged source values;
- true invalid values.

---

## 25. Git and Raw-Data Handling

The extraction produced 124 raw monthly CSV files.

The recommended repository pattern is:

- exclude `data/raw/eccc_weather/` from Git;
- keep the extraction script;
- keep the processed dataset if its size fits the repository policy;
- keep the quality summary;
- keep this README;
- document how raw files can be regenerated.

Suggested `.gitignore` entry:

```gitignore
data/raw/eccc_weather/
```

Before committing, verify:

```bash
git status
```

The 124 raw CSV files should not appear as staged files if the raw folder is intentionally excluded.

The extraction remains reproducible because the script, station mapping, date range, and source URL are documented.

---

## 26. How to Run the Script

### 26.1 Activate the environment

Use the project virtual environment.

Example in Git Bash:

```bash
source venv/Scripts/activate
```

The exact activation command can vary by terminal.

### 26.2 Confirm required packages

The script requires:

```text
pandas
requests
```

Install them if necessary:

```bash
pip install pandas requests
```

### 26.3 Run from the repository root

The command must be executed from the project root:

```bash
python src/etl/extract_eccc_hourly_weather.py
```

This is important because the script uses relative paths beginning with:

```text
data/
```

### 26.4 Test mode

In the script:

```python
TEST_MODE = True
```

Run:

```bash
python src/etl/extract_eccc_hourly_weather.py
```

Expected scope:

```text
Barrie-Oro
January 2024
One file
744 rows
```

### 26.5 Full mode

After the test succeeds:

```python
TEST_MODE = False
```

Run the same command:

```bash
python src/etl/extract_eccc_hourly_weather.py
```

Expected scope:

```text
4 stations
31 months per station
124 total files
90,528 total rows
```

### 26.6 Re-running the script

Existing monthly raw files will be skipped and read from disk.

A new processed file and summary can still be generated from the available raw files.

---

## 27. Expected Full-Run Summary

For the fixed January 2024 through July 2026 scope, a successful run should report values consistent with:

```text
Expected files: 124
Failed files: 0
Total rows: 90,528
```

If the January 2024 Barrie test file already exists before full mode, the first full run should report:

```text
New files downloaded: 123
Existing files skipped: 1
```

If all raw files already exist, a later run should report:

```text
New files downloaded: 0
Existing files skipped: 124
```

The combined dataset should still contain:

```text
22,632 rows per city
90,528 rows total
```

---

## 28. Acceptance Criteria

OWF-48 can be considered complete as an extraction task because:

- the correct ECCC bulk endpoint was confirmed;
- the hourly request parameters were confirmed;
- one primary station was used for each project city;
- Station IDs and Climate IDs were documented separately;
- January 2024 through July 2026 was extracted;
- all 124 station-month combinations were available;
- all raw monthly files were preserved;
- the script can resume after a partial run;
- invalid-looking responses are rejected;
- connection failures can be retried;
- requests include a politeness delay;
- one-station test mode passed;
- full mode passed;
- monthly row counts match calendar length;
- each city has exactly 22,632 rows;
- the final dataset has exactly 90,528 rows;
- the date range is exactly correct;
- no extraction request failed;
- no retry was needed in the recorded full run;
- the combined processed file was generated;
- the extraction summary was generated;
- known unit and time-zone issues were documented rather than hidden.

---

## 29. Known Limitations

### Field-level missingness has not yet been summarized

Complete hourly rows do not guarantee complete values in every weather field.

### Local Standard Time requires later normalization

The timestamps must not be joined directly to differently standardized sources without a documented rule.

### Wind direction remains in tens of degrees

The source unit is preserved.

### Wind direction requires circular treatment

A simple arithmetic mean should not be used for daily aggregation.

### Raw-file volume is high

The 124 raw files should normally be excluded from Git and regenerated when required.

### The date range is fixed

The script intentionally ends in July 2026. Updating the end date changes the expected request count and output size.

### The extraction is not scheduled

The script is run manually. Airflow was moved to a separate work item.

### No fallback station was used

The primary stations returned complete structural coverage. Rules for replacing missing primary-station measurements with another station have not been defined.

### The processed file is not yet model-ready

It still requires quality profiling, type conversion, time normalization, feature engineering, and aggregation.

---

## 30. Final Result

OWF-48 achieved its extraction objective.

I confirmed the ECCC bulk-download pattern using the official `Get More Data` resources rather than guessing the request format. I then cross-validated the selected stations and resolved the difference between public Climate IDs and the internal Station IDs required by the download endpoint.

The final script downloaded one hourly CSV per station and month for:

```text
Barrie
Kingston
Thunder Bay
Toronto
```

over:

```text
January 2024 through July 2026
```

The full extraction processed:

```text
124 expected station-month files
123 new downloads
1 existing test file reused
0 failed files
0 retries required
90,528 combined rows
```

Each city contributed exactly:

```text
22,632 hourly rows
```

The monthly counts matched real calendar lengths, including the 2024 leap-year February. The combined timestamp range matched the project window exactly:

```text
2024-01-01 00:00
through
2026-07-31 23:00
```

No extraction or structural coverage anomaly appeared in the recorded full run.

The original monthly files were preserved, the processed dataset was created separately, and an extraction summary was generated. The script also documents that wind direction is stored in tens of degrees and that ECCC timestamps are Local Standard Time.

OWF-48 is complete as a repeatable extraction and preliminary coverage-validation task. Detailed field-level validation, timestamp normalization, daily weather feature creation, database loading, and orchestration remain follow-up work.

---

## 31. Closing Summary for Jira

Completed the ECCC hourly weather extraction for Barrie, Kingston, Thunder Bay, and Toronto using the selected stations from OWF-27.

Confirmed the official bulk-download URL and the internal Station IDs required by the endpoint. Implemented a repeatable Python script with test mode, retries, timeout handling, a politeness delay, response validation, raw-file preservation, resumability, project metadata, standardized column names, a combined processed output, and an extraction summary.

The full January 2024 through July 2026 run completed all 124 station-month combinations with zero failures. It produced 90,528 rows in total, with 22,632 rows per city. Monthly row counts matched calendar length, including leap-year February 2024, and the final timestamp range was exactly 2024-01-01 00:00 through 2026-07-31 23:00.

The extraction and structural coverage are complete. Field-level missingness, timestamp normalization, wind transformation, daily aggregation, PostgreSQL loading, and Airflow scheduling will be handled separately.

---

## 32. Source and Repository References

### ECCC bulk-download endpoint

```text
https://climate.weather.gc.ca/climate_data/bulk_data_e.html
```

### Official `Get More Data` resource directory

```text
https://collaboration.cmc.ec.gc.ca/cmc/climate/Get_More_Data_Plus_de_donnees/
```

### Extraction script

```text
src/etl/extract_eccc_hourly_weather.py
```

### Raw monthly outputs

```text
data/raw/eccc_weather/
```

### Processed output

```text
data/processed/eccc_weather/
```

### Quality summary

```text
data/quality/eccc_weather/
```

### Related station-decision documentation

```text
docs/technical-notes/README_OWF-27_Weather_Data_Source_Decision.md
```
