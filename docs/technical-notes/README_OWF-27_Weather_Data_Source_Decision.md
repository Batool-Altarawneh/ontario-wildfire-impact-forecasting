# OWF-27: Weather Data Source Decision

## Work Item

**Jira ID:** OWF-27  
**Title:** Confirm where temperature and wind fields will come from  
**Project:** Ontario Wildfire Impact and Forecasting Analytics  
**Sprint:** Sprint 1: Data and Airflow  
**Status:** Ready to close  
**Decision date:** July 30, 2026

---

## 1. Purpose

The purpose of OWF-27 was to determine where the project should obtain weather variables needed for wildfire context and city-level AQHI forecasting.

The required variables are:

- Temperature
- Relative humidity
- Wind speed
- Wind direction
- Precipitation

The main question was whether the weather fields already included in the CWFIS hotspot data were sufficient, or whether a separate weather source was required for Barrie, Kingston, Thunder Bay, and Toronto.

This README documents the investigation, the problems encountered, how each problem was resolved, the evidence used, the final source design, the selected weather stations, and the implementation requirements for the follow-up extraction task.

---

## 2. Project Context

The project connects wildfire activity with air-quality impacts in four Ontario cities:

- Barrie
- Kingston
- Thunder Bay
- Toronto

The forecasting target is city-level AQHI. Wildfires may be located far from the city where smoke is eventually observed. Because of this, the project needs to distinguish between two different weather contexts:

1. Weather at the wildfire location
2. Weather at the city where AQHI is measured and forecast

This distinction became the central design decision in OWF-27.

---

## 3. Initial Observation

The existing CWFIS hotspot extraction already contained the following fields:

| CWFIS Field | Meaning |
|---|---|
| `temp` | Temperature |
| `rh` | Relative humidity |
| `ws` | Wind speed |
| `wd` | Wind direction |
| `pcp` | Precipitation |

At first, it appeared possible that no additional weather source would be needed.

The initial hypothesis was:

> If CWFIS already provides temperature, humidity, wind, and precipitation with every hotspot record, those fields may satisfy the project's weather requirements.

I did not close the task based only on the field names. I first verified what the fields represent and whether they match the geographic level required by the forecasting problem.

---

## 4. Problem 1: The CWFIS Fields Were Easy to Misinterpret

### Problem

The presence of weather columns in a hotspot record could be interpreted as meaning that CWFIS provides weather for the four target cities.

That interpretation would be incorrect.

### Investigation

The CWFIS weather fields are associated with the wildfire or hotspot location. They are used as part of the fire-weather context and Fire Weather Index calculations.

The values are not necessarily direct sensor readings taken exactly at the hotspot coordinates. They are estimated from available weather-station observations and represent conditions at or near the fire location.

### Resolution

I separated weather into two distinct analytical roles:

#### Fire-site weather

Weather describing conditions where the fire is burning.

This includes:

- Temperature near the hotspot
- Relative humidity near the hotspot
- Wind speed and direction near the hotspot
- Precipitation near the hotspot

These variables help explain fire behaviour, spread potential, and local fire conditions.

#### City-level weather

Weather describing conditions in Barrie, Kingston, Thunder Bay, or Toronto.

This includes:

- Temperature in the city
- Relative humidity in the city
- Wind speed and direction in the city
- Precipitation in the city

These variables help explain the local conditions associated with city-level AQHI and smoke impact.

### Result

CWFIS is sufficient for fire-site weather, but it is not sufficient for city-level weather.

A second weather source is required.

---

## 5. Decision 1: Use a Two-Source Weather Design

The final source design is:

| Weather Context | Source | Purpose |
|---|---|---|
| Fire-site weather | CWFIS hotspot data | Describe weather conditions at or near the wildfire location |
| City-level weather | ECCC Historical Climate Data | Provide weather observations for the four AQHI target cities |

This design avoids forcing one dataset to serve two different geographic purposes.

It also preserves the meaning of each variable:

- CWFIS variables remain linked to the fire location.
- ECCC variables remain linked to the city location.

---

## 6. Problem 2: Daily Weather Stations Were Not Sufficient

### Problem

The ECCC Historical Climate Data portal provides both daily and hourly station records.

Daily stations can provide useful daily temperature and precipitation summaries, but wind speed and wind direction may not be available at the level required by this project.

Wind is not optional in this use case. It is one of the mechanisms connecting a fire in one region to smoke exposure in another city.

### Resolution

I selected hourly climate stations rather than daily-only stations.

The hourly records provide the detailed weather fields needed for the project, including:

- Temperature
- Relative humidity
- Precipitation
- Wind speed
- Wind direction

The project will aggregate the hourly data to daily features after extraction. This gives full control over the aggregation logic instead of relying on a pre-aggregated daily product.

### Result

The station selection rule became:

> Select an hourly station with coverage for the 2024-2026 project window and with the required temperature, humidity, precipitation, and wind fields.

---

## 7. Station Selection Method

I used the following process for each city:

1. Search the ECCC Historical Climate Data portal by city name or proximity.
2. Review all available stations near the city.
3. Exclude daily-only stations because they do not meet the wind requirement.
4. Confirm that hourly coverage includes the 2024-2026 project period.
5. Review the station details:
   - Station name
   - Climate ID
   - Operator
   - Coordinates
   - Elevation
   - WMO or TC identifier where available
6. Compare stations at the same or nearby physical location.
7. Prefer a station that:
   - Is hourly
   - Has continuous coverage
   - Is geographically representative of the city
   - Includes the required weather fields
   - Is operated by ECCC-MSC when an appropriate ECCC-MSC option exists
8. Validate an actual CSV sample rather than relying only on station metadata.
9. Retain nearby alternatives as fallback stations when appropriate.

The operator was used as a practical decision factor, not as proof of data completeness. Full missingness and field-coverage checks still need to be performed programmatically during the extraction task.

---

## 8. Barrie Station Investigation

### Candidates

| Station | Interval | Decision |
|---|---|---|
| BARRIE LANDFILL | Daily | Rejected |
| BARRIE-ORO | Hourly | Selected |

### Problem

BARRIE LANDFILL was only available as a daily station. It did not satisfy the hourly wind requirement.

### Resolution

I selected BARRIE-ORO and inspected the hourly report.

### Evidence

The station report showed the required columns:

- Temperature
- Relative humidity
- Precipitation amount
- Wind direction
- Wind speed

Station details:

| Attribute | Value |
|---|---|
| Station name | BARRIE-ORO |
| Climate ID | `6117700` |
| Operator | ECCC-MSC |
| WMO ID | `71314` |
| TC ID | `XBI` |
| Latitude | 44 degrees 29 minutes N |
| Longitude | 79 degrees 33 minutes W |
| Elevation | 289.0 m |

### Result

**Barrie primary station: BARRIE-ORO, Climate ID `6117700`.**

---

## 9. Kingston Station Investigation

### Candidates

| Station | Climate ID | Operator |
|---|---:|---|
| KINGSTON A | `6104149` | NAVCAN |
| KINGSTON A | `6104152` | NAVCAN |
| KINGSTON CLIMATE | `6104142` | ECCC-MSC |

### Problem 1: Duplicate Station Names

Two separate records were both named KINGSTON A.

### Investigation

The two KINGSTON A records had:

- The same coordinates
- The same elevation
- The same TC ID, `YGK`
- The same NAVCAN operator

This indicated that they represented the same physical airport site under different climate records, likely because of an instrumentation or record-management transition.

### Resolution

I did not treat the duplicate names as two meaningfully different geographic locations. I compared them with the separate KINGSTON CLIMATE station.

### Problem 2: Potential Precipitation Completeness

The airport records were operated by NAVCAN. Based on the station and data documentation reviewed during this task, NAVCAN-operated records could present a risk for complete hourly precipitation availability.

KINGSTON CLIMATE was a separate nearby ECCC-MSC station and provided a cleaner candidate for the complete target variable set.

### Candidate Details

#### KINGSTON A, Climate ID `6104152`

| Attribute | Value |
|---|---|
| Operator | NAVCAN |
| Latitude | 44 degrees 13 minutes 33 seconds N |
| Longitude | 76 degrees 35 minutes 48 seconds W |
| Elevation | 92.4 m |
| TC ID | `YGK` |

#### KINGSTON CLIMATE, Climate ID `6104142`

| Attribute | Value |
|---|---|
| Operator | ECCC-MSC |
| Latitude | 44 degrees 13 minutes 24 seconds N |
| Longitude | 76 degrees 35 minutes 58 seconds W |
| Elevation | 93.0 m |
| WMO ID | `71820` |
| TC ID | `TKG` |

The stations are geographically very close, so distance alone did not determine the result.

### CSV Validation

I downloaded and inspected the January 2024 hourly CSV for KINGSTON CLIMATE.

File checked:

`en_climate_hourly_ON_6104142_01-2024_P1H.csv`

Expected row count:

- January has 31 days.
- 31 days multiplied by 24 hours equals 744 hourly records.
- The file contained exactly 744 rows.

Field completeness:

| Field | Available Rows | Missing Rows | Missing Percentage |
|---|---:|---:|---:|
| Temperature | 744 | 0 | 0.00% |
| Relative humidity | 744 | 0 | 0.00% |
| Precipitation amount | 744 | 0 | 0.00% |
| Wind direction | 714 | 30 | 4.03% |
| Wind speed | 725 | 19 | 2.55% |

Precipitation validation:

| Check | Result |
|---|---:|
| Hours with precipitation greater than 0 | 91 |
| Hours with 0.0 mm precipitation | 653 |
| Maximum hourly precipitation | 4.3 mm |
| Monthly precipitation total | 96.7 mm |

This confirmed that the precipitation column was populated and that `0.0` represented a valid no-precipitation observation rather than a missing value.

Some missing wind-direction values can occur during calm conditions, when wind direction is not meaningful. Other flagged missing records must still be handled explicitly.

### Result

**Kingston primary station: KINGSTON CLIMATE, Climate ID `6104142`.**

The two KINGSTON A records can be retained as fallback sources if the full-period quality check identifies unexpected gaps.

---

## 10. Thunder Bay Station Investigation

### Candidates

| Station | Climate ID | Operator |
|---|---:|---|
| THUNDER BAY | `6048260` | NAVCAN |
| THUNDER BAY A | `6048262` | NAVCAN |
| THUNDER BAY CS | `6048268` | ECCC-MSC |

### Problem

THUNDER BAY and THUNDER BAY A were separate climate records for essentially the same NAVCAN airport location.

The project needed one primary station with a clear and consistent decision rule.

### Investigation

The two NAVCAN records had the same airport location characteristics and TC ID `YQT`.

THUNDER BAY CS was a separate ECCC-MSC station at nearly the same location.

Station details for THUNDER BAY CS:

| Attribute | Value |
|---|---|
| Station name | THUNDER BAY CS |
| Climate ID | `6048268` |
| Operator | ECCC-MSC |
| WMO ID | `71667` |
| TC ID | `ZTB` |
| Latitude | 48 degrees 22 minutes 10 seconds N |
| Longitude | 89 degrees 19 minutes 38 seconds W |
| Elevation | 199.4 m |

### Resolution

I applied the same selection logic used for Kingston:

- Use an hourly station.
- Prefer the nearby ECCC-MSC station when it provides the required variables.
- Keep the NAVCAN airport records as possible fallbacks.
- Perform a full programmatic completeness check during extraction.

### Result

**Thunder Bay primary station: THUNDER BAY CS, Climate ID `6048268`.**

This selection is justified by station type, operator consistency, proximity, and the requirement for a complete hourly weather feature set. It is still subject to the full 2024-2026 validation in the extraction task.

---

## 11. Toronto Station Investigation

### Candidates

| Station | Interval | Operator | Decision |
|---|---|---|---|
| TORONTO CITY | Hourly | ECCC-MSC | Selected |
| TORONTO CITY CENTRE | Hourly | NAVCAN | Fallback |
| TORONTO INTL A | Hourly | NAVCAN | Fallback |
| TORONTO NORTH YORK | Daily | CCN | Rejected |

### Problem 1: Geographic Representativeness

Toronto has multiple weather stations, but they do not represent the same part of the city.

- TORONTO INTL A represents Pearson Airport.
- TORONTO CITY CENTRE represents the Billy Bishop airport area.
- TORONTO NORTH YORK is not hourly.
- TORONTO CITY is an hourly ECCC-MSC station within Toronto.

The forecasting target is city-level AQHI, so a station representing the urban area is preferable to a farther airport station when the required fields and coverage are available.

### Problem 2: Daily-Only Option

TORONTO NORTH YORK was available only as daily data and therefore did not satisfy the hourly wind requirement.

### Resolution

I selected TORONTO CITY because it met the combined requirements:

- Hourly interval
- ECCC-MSC operator
- City-level geographic representation
- 2024-2026 coverage
- Better alignment with the Toronto AQHI use case than Pearson Airport

Selected station:

| Attribute | Value |
|---|---|
| Station name | TORONTO CITY |
| Climate ID | `6158355` |
| Operator | ECCC-MSC |

### Result

**Toronto primary station: TORONTO CITY, Climate ID `6158355`.**

TORONTO CITY CENTRE and TORONTO INTL A can be retained as fallbacks. TORONTO NORTH YORK is excluded from the primary hourly-weather pipeline.

---

## 12. Final Station Mapping

| City | Selected Station | Climate ID | Operator | Role |
|---|---|---:|---|---|
| Barrie | BARRIE-ORO | `6117700` | ECCC-MSC | Primary |
| Kingston | KINGSTON CLIMATE | `6104142` | ECCC-MSC | Primary |
| Thunder Bay | THUNDER BAY CS | `6048268` | ECCC-MSC | Primary |
| Toronto | TORONTO CITY | `6158355` | ECCC-MSC | Primary |

The final mapping uses one ECCC-MSC hourly station for each target city.

This produces a consistent source strategy, but consistency was not the only reason for selection. Each station was also evaluated for interval, location, coverage, and expected variable availability.

---

## 13. Final OWF-27 Decision

The project will use a two-source weather architecture.

### Source A: CWFIS

CWFIS will supply weather associated with wildfire or hotspot locations:

- `temp`
- `rh`
- `ws`
- `wd`
- `pcp`

These fields will be treated as fire-site weather context.

### Source B: ECCC Historical Climate Data

ECCC will supply hourly city-level weather for:

- Barrie
- Kingston
- Thunder Bay
- Toronto

These observations will be extracted from the four selected stations and transformed into daily model features.

### Final Decision Statement

> CWFIS will provide fire-site weather context, while ECCC Historical Climate Data will provide hourly city-level temperature, relative humidity, precipitation, wind speed, and wind direction for Barrie, Kingston, Thunder Bay, and Toronto.

---

## 14. Required Transformations

The source decision is complete, but several transformations must be implemented in the extraction and cleaning pipeline.

### 14.1 Wind Direction Unit

ECCC labels wind direction as:

`Wind Dir (10s deg)`

The stored number represents tens of degrees.

Examples:

| Raw Value | Direction in Degrees |
|---:|---:|
| 27 | 270 degrees |
| 18 | 180 degrees |
| 9 | 90 degrees |

Transformation:

```text
wind_direction_degrees = wind_direction_10s_deg * 10
```

### 14.2 Wind Direction Is Circular

Wind direction must not be averaged using a normal arithmetic mean.

For example:

- 350 degrees
- 10 degrees

The correct average direction is close to 0 degrees, not 180 degrees.

For daily aggregation, wind should be converted into vector components using a meteorological-direction-aware transformation. A common approach is:

```text
theta = wind_direction_degrees converted to radians
wind_u = -wind_speed * sin(theta)
wind_v = -wind_speed * cos(theta)
```

The daily mean vector can then be converted back into a direction if a daily directional feature is required.

### 14.3 Precipitation

The precipitation field must distinguish between:

- `0.0`: a valid observation meaning no precipitation
- Blank or missing: no recorded value
- `M` flag: missing observation

Zero precipitation must never be converted to null.

### 14.4 Calm Wind

A missing wind direction can be valid when wind speed is zero because there is no meaningful direction during calm conditions.

The pipeline should distinguish:

- Missing direction with wind speed equal to zero
- Missing direction while wind speed is greater than zero
- Wind records explicitly flagged as missing

### 14.5 Time Zone and Daylight Saving Time

The ECCC hourly reports are presented in Local Standard Time.

The portal notes that one hour must be added where and when Daylight Saving Time is observed.

Before joining weather with AQHI and wildfire data, timestamps must be normalized consistently.

The follow-up task should:

1. Parse the source timestamp explicitly.
2. Preserve the original local source time.
3. Apply the correct Ontario time-zone rules.
4. Create a normalized UTC timestamp.
5. Define the daily boundary used for aggregation.
6. Use the same time standard across weather, AQHI, and wildfire datasets.

### 14.6 Hourly-to-Daily Aggregation

The exact feature set should be confirmed before model training, but the initial daily transformations should include:

| Variable | Proposed Daily Aggregation |
|---|---|
| Temperature | Mean, minimum, maximum |
| Relative humidity | Mean, minimum, maximum |
| Precipitation | Sum |
| Wind speed | Mean and maximum |
| Wind direction | Vector-based daily mean or daily `u` and `v` components |
| Observation count | Number of valid hourly observations |
| Missingness | Missing percentage by field and day |

The daily feature table should preserve enough quality information to identify days based on incomplete hourly records.

---

## 15. Data Quality Rules for the Follow-Up Extraction

The January 2024 Kingston check confirmed that the selected source can provide the required variables, but one month at one station does not prove full completeness across all stations and years.

OWF-30 must perform systematic validation for every station from 2024 through the latest available 2026 date.

Required checks:

1. Expected hourly row count by month
2. Duplicate timestamp detection
3. Missing percentage for each required field
4. Flag frequency by field
5. Valid numeric ranges
6. Invalid wind-direction values
7. Negative precipitation values
8. Gaps longer than a defined threshold
9. Station identity consistency
10. Coverage start and end dates
11. Daylight Saving Time transitions
12. Daily aggregation completeness

Suggested validation thresholds should be documented rather than silently applied.

A day should not be treated as fully observed unless it meets a defined minimum hourly-observation requirement.

---

## 16. Problems and Resolutions Summary

| Problem | Resolution | Result |
|---|---|---|
| CWFIS appeared to provide all weather needs | Verified the geographic meaning of the fields | CWFIS retained for fire-site weather only |
| City weather was still required | Added ECCC as the city-level source | Two-source architecture selected |
| Daily stations may not include required wind detail | Required hourly stations | Hourly extraction selected |
| Duplicate KINGSTON A records created ambiguity | Compared location, operator, IDs, and coverage | KINGSTON CLIMATE selected |
| Kingston precipitation availability was uncertain | Downloaded and profiled January 2024 CSV | Precipitation and required fields confirmed |
| Thunder Bay had duplicate airport records | Applied the validated station-selection method | THUNDER BAY CS selected |
| Toronto stations represented different areas | Compared interval, operator, and city relevance | TORONTO CITY selected |
| Wind direction uses tens of degrees | Documented multiplication by 10 | Transformation requirement defined |
| Wind direction cannot use arithmetic averaging | Defined vector-based aggregation | Daily wind logic identified |
| ECCC uses Local Standard Time | Flagged explicit DST and UTC handling | Time-normalization requirement defined |
| Operator type does not prove completeness | Deferred full-period checks to OWF-30 | Programmatic validation required |

---

## 17. Acceptance Criteria for OWF-27

OWF-27 can be considered complete because the following questions have been answered:

- The source of fire-site temperature, humidity, wind, and precipitation is confirmed.
- The source of city-level weather is confirmed.
- Hourly data was selected instead of daily-only data.
- One primary ECCC station was selected for each city.
- Duplicate and alternative station records were reviewed.
- The Kingston source was validated using an actual hourly CSV.
- Wind-direction units and circular aggregation requirements were identified.
- Time-zone and Daylight Saving Time handling was identified.
- Full-period data-quality checks were assigned to the extraction task.

---

## 18. Items Not Completed in OWF-27

The following work is intentionally outside the scope of this decision task:

- Downloading all monthly files for all four cities
- Automating ECCC extraction
- Calculating full 2024-2026 missingness
- Finalizing fallback-station rules
- Cleaning all source flags
- Normalizing timestamps
- Aggregating hourly observations to daily features
- Joining weather with AQHI
- Joining city weather with wildfire features
- Training or updating the LSTM
- Measuring the predictive value of each weather feature

These items belong in the follow-up implementation task.

---

## 19. Follow-Up Work Item

### Proposed Jira Item

**OWF-30: Extract and prepare hourly ECCC weather data for selected cities**

### Objective

Build a repeatable extraction and transformation process for hourly ECCC weather data from the four selected climate stations.

### Proposed Scope

1. Store the station mapping in configuration.
2. Download monthly hourly CSV files for 2024-2026.
3. Preserve raw files unchanged.
4. Standardize column names and data types.
5. Add city, station name, Climate ID, and extraction metadata.
6. Parse and normalize timestamps.
7. Handle Daylight Saving Time explicitly.
8. Convert wind direction from tens of degrees to degrees.
9. Create wind vector features.
10. Preserve source flags.
11. Profile missingness and data coverage.
12. Apply documented data-quality rules.
13. Aggregate hourly observations to daily city features.
14. Write raw and cleaned outputs.
15. Prepare the daily table for the AQHI and wildfire joins.
16. Add automated tests and logging.
17. Document fallback-station behaviour.

### Recommended Station Configuration

```yaml
weather_stations:
  barrie:
    station_name: BARRIE-ORO
    climate_id: "6117700"
    operator: ECCC-MSC

  kingston:
    station_name: KINGSTON CLIMATE
    climate_id: "6104142"
    operator: ECCC-MSC

  thunder_bay:
    station_name: THUNDER BAY CS
    climate_id: "6048268"
    operator: ECCC-MSC

  toronto:
    station_name: TORONTO CITY
    climate_id: "6158355"
    operator: ECCC-MSC
```

---

## 20. Final Outcome

OWF-27 began with a simple question: whether the CWFIS weather fields were enough for the project.

The investigation showed that the answer depended on location.

CWFIS already provides useful weather context at the fire location, so no second fire-site extraction is needed. However, the AQHI model predicts conditions in cities that may be far from the fire. City-level weather therefore requires a separate source.

I selected ECCC Historical Climate Data for city-level weather, required hourly rather than daily-only stations, reviewed the candidate stations for all four cities, resolved duplicate station records, validated Kingston with an actual CSV, and documented the required transformations and quality checks.

The final design is:

- CWFIS for fire-site weather
- ECCC hourly station data for city-level weather
- BARRIE-ORO for Barrie
- KINGSTON CLIMATE for Kingston
- THUNDER BAY CS for Thunder Bay
- TORONTO CITY for Toronto

With this decision documented, OWF-27 is ready to be marked Done. The implementation continues in OWF-30.
