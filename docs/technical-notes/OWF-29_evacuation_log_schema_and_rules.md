# OWF-29 — Evacuation Log Schema and Governance Rules

## Project

Ontario Wildfire Impact and Forecasting Analytics

## Work Item

OWF-29 — Label the evacuation log as manually collected and descriptive-only

## Author

Batool Altarawneh

## Purpose

This document defines the schema, source rules, inclusion criteria, status rules, duplicate-handling rules, and governance boundaries for the manually compiled evacuation log created under OWF-28.

It was written before any real events were collected so that every entry follows the same standard from the beginning. This avoids changing the rules halfway through the collection process and having to revise earlier records.

This document also satisfies the project requirement in `project_charter.md`, Section 5.4 and Section 11.1, that the evacuation log be clearly identified as a manual, descriptive, non-live source that is excluded from model training.

---

## 1. Explicit Limitation Statement

The evacuation log is a descriptive annotation layer only.

It is:

- Manually compiled from public news coverage.
- Intended to provide community-impact context in the Tableau story.
- A point-in-time project file.
- Reviewed and updated manually.
- Kept separate from the forecasting dataset.

It is not:

- A live evacuation feed.
- An official or authoritative emergency-management source.
- A complete record of every Ontario evacuation in 2026.
- Automatically refreshed.
- Used as a predictor, model input, target, or training feature for the AQHI forecasting model.
- A substitute for official evacuation notices or emergency instructions.

This limitation was established during the project risk review documented in `project_charter.md`, Section 11.1, because evacuation events are too sparse, irregular, and inconsistently reported to support reliable statistical modeling.

---

## 2. File Location

The governance document is stored at:

```text
docs/technical-notes/OWF-29_evacuation_log_schema_and_rules.md
```

The manually collected evacuation log created under OWF-28 is stored at:

```text
data/manual/evacuation_log/ontario_evacuation_log_2026.csv
```

The `data/manual/` location is used because the file is created manually from reviewed sources rather than downloaded directly from an API or automated public feed.

---

## 3. Final Schema

| Column | Type | Description |
|---|---|---|
| `event_id` | Text | Sequential project identifier using the format `EVAC-001`, `EVAC-002`, and so on. |
| `community` | Text | The specific community, town, municipality, or First Nation that was evacuated. |
| `nearby_project_city` | Controlled text | One of `Barrie`, `Kingston`, `Thunder Bay`, `Toronto`, or `Not applicable`. |
| `evacuation_start_date` | Date | Date the evacuation was ordered or began, stored as `YYYY-MM-DD`. |
| `evacuation_end_date` | Date or blank | Date residents were confirmed able to return, stored as `YYYY-MM-DD`. It remains blank when the evacuation is ongoing or the end date cannot be confirmed. |
| `event_status` | Controlled text | One of `Ongoing`, `Lifted`, or `Unknown`. |
| `status_as_of_date` | Date | Date on which the current row status was last reviewed or confirmed, stored as `YYYY-MM-DD`. |
| `related_fire_id` | Text or blank | Cross-reference to a `FIELD_AGENCY_FIRE_ID` from the OWF-26 Ontario active fires dataset, only when a source explicitly confirms the connection. |
| `source_name` | Text | Name of the organization that published the initial evacuation article, such as `CBC News` or `CTV News`. |
| `source_publication_date` | Date | Publication date of the initial source article, stored as `YYYY-MM-DD`. |
| `source_url` | URL | Direct link to the original article used to confirm the evacuation. |
| `secondary_source_name` | Text or blank | Name of a follow-up source used to confirm an update, lifting, extension, or return. |
| `secondary_source_publication_date` | Date or blank | Publication date of the follow-up source, stored as `YYYY-MM-DD`. |
| `secondary_source_url` | URL or blank | Direct link to the follow-up article. |
| `notes` | Free text | Brief factual summary of the event. Interpretation, unsupported assumptions, and causal claims not stated by the source are not allowed. |

---

## 4. Column Rules

### 4.1 `event_id`

Each distinct evacuation event receives one unique identifier.

Format:

```text
EVAC-001
EVAC-002
EVAC-003
```

Identifiers are assigned sequentially and are never reused.

A second evacuation of the same community receives a new ID if residents returned after the first event and were later evacuated again.

### 4.2 `community`

This field records the actual place that was evacuated.

It should use the community name stated in the source article.

Examples may include:

- a First Nation;
- a municipality;
- a town;
- a settlement;
- a specific neighbourhood, when the source clearly identifies it.

The project does not rename or simplify the community unless a consistent spelling decision is documented.

### 4.3 `nearby_project_city`

Allowed values:

```text
Barrie
Kingston
Thunder Bay
Toronto
Not applicable
```

This field provides narrative context for the Tableau story.

It does not mean that the evacuation occurred inside that project city.

`Not applicable` is used when no reasonable geographic or narrative association exists.

No community should be forced into one of the four city categories simply to avoid a blank value.

### 4.4 `evacuation_start_date`

This field records the date the evacuation was ordered or began.

The date must be supported by the source.

If the article gives a clear date but not an exact time, the date is still recorded.

If the article does not allow the start date to be confirmed, the event should not be entered until another acceptable source is found.

### 4.5 `evacuation_end_date`

This field remains a true date field.

It contains only:

```text
YYYY-MM-DD
```

or a blank value.

Text such as:

```text
Ongoing
Not known
Ongoing as of 2026-08-03
```

must not be written in this column.

Status information belongs in `event_status`, and the date of the latest review belongs in `status_as_of_date`.

This design avoids mixed data types and makes later loading into PostgreSQL easier.

### 4.6 `event_status`

Allowed values:

| Value | Meaning |
|---|---|
| `Ongoing` | The most recent reviewed source indicates that residents have not yet returned. |
| `Lifted` | A reviewed source confirms that the evacuation order was lifted or residents were allowed to return. |
| `Unknown` | The latest status could not be confirmed after reviewing available acceptable sources. |

No alternative spellings or status labels should be used.

For example, values such as `Active`, `Still evacuated`, `Ended`, or `Complete` should not be entered.

### 4.7 `status_as_of_date`

This field records the date the row was last reviewed or confirmed.

It is not automatically the same as the article publication date.

Examples:

- If an article published on July 10 is reviewed on July 12 and no later update is available, `status_as_of_date` may be July 12.
- If a follow-up article published on July 20 confirms that residents returned, the row should be updated and `status_as_of_date` should reflect the date of that review.

This field makes it clear when the event status was last checked.

### 4.8 `related_fire_id`

This field is optional.

It may only be populated when an acceptable source explicitly identifies the fire connected to the evacuation.

The project must not assign a fire ID based only on:

- geographic proximity;
- similar dates;
- fire size;
- an out-of-control status;
- assumptions based on a nearby fire;
- visual comparison with a map.

For example, a large fire in the Thunder Bay region must not automatically be linked to an evacuation unless the source confirms that connection.

If the source names a fire but the name cannot be matched confidently to a `FIELD_AGENCY_FIRE_ID`, the field remains blank and the source wording may be recorded in `notes`.

### 4.9 Source fields

The initial source is preserved in:

```text
source_name
source_publication_date
source_url
```

A later update is preserved separately in:

```text
secondary_source_name
secondary_source_publication_date
secondary_source_url
```

The original evacuation article should not be overwritten by a later return article.

Keeping both references preserves the evidence for:

- the beginning of the event;
- the later status update;
- the lifting date, when available.

If more than two sources are required, additional references may be described in `notes`, but the main evidence should remain in the structured source fields.

### 4.10 `notes`

The notes field contains a short factual summary.

Acceptable content includes:

- who was evacuated;
- why the article says the evacuation occurred;
- whether residents were moved to another community;
- whether vulnerable residents were prioritized;
- whether the evacuation was later lifted;
- whether the source named a specific fire.

The notes field must not include:

- personal interpretation;
- unsupported causal claims;
- speculation;
- assumptions about which fire caused the event;
- conclusions not stated by the source;
- emotional or promotional wording.

---

## 5. Source Rules

### 5.1 Accepted publishers

The primary intended sources are:

- CBC News
- CTV News

These sources match the project scope defined in `project_charter.md`, Section 5.4.

### 5.2 Original article rule

Only the original publishing organization’s own article should be used.

Accepted example:

```text
A CBC article hosted on cbc.ca
```

Not accepted when the original is available:

```text
A Yahoo News repost of the same CBC or Canadian Press story
A news aggregator
A copied article on another website
A social media post that links to or summarizes the event
```

The purpose of this rule is to keep each entry traceable to the original reviewed source.

### 5.3 Working-link rule

Every event must have a working `source_url`.

The URL must point to the specific article used to confirm the event, not only to:

- a publisher homepage;
- a topic page;
- a search-results page;
- a social media account.

### 5.4 Follow-up source rule

A follow-up article may be used to confirm:

- extension of the evacuation;
- change in the number of evacuees;
- relocation information;
- lifting of the evacuation;
- return of residents;
- revised cause or fire attribution.

The follow-up source is recorded in the secondary source fields.

The original source remains preserved.

### 5.5 Source-publication date

The article publication date is stored separately from:

- the event start date;
- the event end date;
- the status review date.

These dates may differ and should not be treated as interchangeable.

---

## 6. Inclusion Criteria

An event is included only when all applicable criteria are satisfied.

### 6.1 Geographic scope

Any confirmed wildfire-related evacuation in Ontario during the covered period may be included.

The log is not limited to communities close to:

- Barrie;
- Kingston;
- Thunder Bay;
- Toronto.

This decision reflects the descriptive purpose of the table. Major community impacts may occur far from the four modeling cities.

### 6.2 Time window

The collection window is:

```text
January 1, 2026 through the project data cutoff date
```

The exact cutoff date should be recorded when the log is finalized or refreshed.

Historical 2024 and 2025 evacuations are not backfilled for this table.

Those earlier years are used in AQHI and weather datasets to support modeling history, but the evacuation log is a descriptive layer for the 2026 Ontario wildfire season.

### 6.3 Confirmed evacuations only

Only confirmed or implemented evacuations are included.

Accepted wording may include:

```text
evacuation ordered
mandatory evacuation
residents evacuated
community evacuated
residents transported out of the community
```

Excluded event types include:

```text
evacuation alert
evacuation warning
prepare to evacuate
community on standby
possible evacuation
precautionary notice
```

An alert may be entered only if a later accepted source confirms that it became an actual evacuation.

The event start date must reflect the confirmed implementation date rather than the earlier alert date.

### 6.4 Wildfire relationship

The source must indicate that the evacuation was related to wildfire activity, wildfire smoke, or a named wildfire.

Events caused only by unrelated emergencies are outside the scope of this log.

### 6.5 Minimum evidence

Each row must have enough evidence to confirm:

- the community;
- that an evacuation actually occurred;
- the evacuation start date;
- the wildfire relationship;
- the original source.

If these points cannot be confirmed, the event should not be added.

---

## 7. Exclusion Criteria

An event is excluded when:

- it is only an alert or warning;
- it occurred outside Ontario;
- it occurred outside the 2026 collection window;
- the source does not confirm that an evacuation occurred;
- the event is unrelated to wildfire activity;
- only an aggregator or repost is available and the original source cannot be reviewed;
- the community cannot be identified;
- the date cannot be confirmed;
- the event duplicates an existing continuous evacuation period.

Excluded items may be kept in temporary research notes, but they must not be added to the final CSV.

---

## 8. Duplicate Handling

One row represents:

```text
one community + one continuous evacuation period
```

Multiple articles about the same continuous event do not create additional rows.

Examples of follow-up coverage that should update the same row:

- initial evacuation order;
- extension;
- update on evacuee numbers;
- relocation update;
- announcement that residents may return.

A new row is created only when the same community experiences a genuinely separate evacuation.

Example:

1. Community evacuated in June.
2. Residents returned.
3. Community evacuated again in August.

This represents two distinct events and requires two separate `event_id` values.

---

## 9. Status Update Procedure

When a new follow-up source is found:

1. Confirm that it refers to the same event.
2. Preserve the original source fields.
3. Add the follow-up article to the secondary source fields.
4. Update `event_status`.
5. Update `evacuation_end_date` if the return date is confirmed.
6. Update `status_as_of_date`.
7. Revise `notes` only when the new information is factual and relevant.
8. Do not create a duplicate row.

If the status cannot be confirmed after a reasonable search:

```text
event_status = Unknown
```

The end-date field remains blank.

---

## 10. Manual Collection Procedure

For each possible evacuation event:

1. Search CBC and CTV for 2026 Ontario wildfire evacuation coverage.
2. Open the original article.
3. Confirm that an evacuation occurred.
4. Confirm the community name.
5. Confirm the start date.
6. Confirm that the event was related to wildfire activity.
7. Check whether the event already exists in the log.
8. Assign the next available `event_id`.
9. Record the original source details.
10. Search for follow-up coverage.
11. Record the current status.
12. Add an end date only if a source confirms it.
13. Add a related fire ID only if the connection is explicitly supported.
14. Write a short factual note.
15. Set `status_as_of_date` to the date the row was reviewed.
16. Save the CSV.
17. Review the row for unsupported assumptions.

---

## 11. Quality Checks Before Finalizing the Log

Before OWF-28 is considered complete, the file should be checked for:

- unique `event_id` values;
- valid date format;
- controlled `event_status` values;
- controlled `nearby_project_city` values;
- missing source URLs;
- duplicate community and start-date combinations;
- end dates earlier than start dates;
- `Lifted` events without an end date;
- `Ongoing` events with an end date;
- related fire IDs without explicit support;
- aggregator links;
- speculative notes;
- inconsistent community spelling;
- events outside Ontario;
- alerts incorrectly entered as evacuations.

---

## 12. Consistency Rules

The following rules apply to all rows:

- Dates use `YYYY-MM-DD`.
- Blank optional values remain blank.
- Missing values are not replaced with guesses.
- `Unknown` is used only for status, not as a date value.
- Community names follow the source wording.
- URLs point directly to articles.
- Fire IDs are never inferred.
- Notes remain factual and concise.
- The log is updated manually.
- The log is never treated as model-ready training data.

---

## 13. Known Limitations

### 13.1 Media coverage limitation

The log cannot include events that received no CBC or CTV coverage.

### 13.2 Geographic representation limitation

Remote communities and communities with less national or regional media attention may be underrepresented.

### 13.3 Fire ID limitation

Many news articles do not provide an official fire ID.

As a result, `related_fire_id` may remain blank for many entries.

### 13.4 Status limitation

A lack of follow-up coverage may make it impossible to confirm whether an evacuation is ongoing or lifted.

Such events are recorded as:

```text
event_status = Unknown
```

with a documented `status_as_of_date`.

### 13.5 Point-in-time limitation

The log reflects the sources reviewed up to the recorded project cutoff date.

It does not update automatically.

### 13.6 Non-authoritative limitation

The log must not be used for emergency decisions or public-safety instructions.

### 13.7 Modeling limitation

The evacuation log is excluded from forecasting features and training data.

Its purpose is descriptive and narrative.

---

## 14. Relationship to OWF-28

OWF-29 defines the rules.

OWF-28 creates and populates the actual log.

The OWF-28 CSV must use the schema in this document exactly unless a later change is documented.

The empty template header is:

```csv
event_id,community,nearby_project_city,evacuation_start_date,evacuation_end_date,event_status,status_as_of_date,related_fire_id,source_name,source_publication_date,source_url,secondary_source_name,secondary_source_publication_date,secondary_source_url,notes
```

---

## 15. Relationship to the Project Charter

This document implements the evacuation-log decisions described in:

```text
docs/project_charter.md
```

Relevant sections include:

- Section 5.4 — Evacuation Event Log
- Section 7 — Items Outside the Project Scope
- Section 11.1 — Limited Evacuation Data
- Section 13 — Scope Decision Log

The charter states that the evacuation log is manually collected, descriptive-only, and excluded from modeling.

This governance document turns that high-level decision into specific collection and data-entry rules.

---

## 16. Acceptance Criteria for OWF-29

OWF-29 is complete when:

- the schema is documented;
- every column has a clear type and meaning;
- accepted sources are defined;
- original articles are required;
- aggregator reposts are excluded;
- the geographic scope is defined;
- the time window is defined;
- confirmed evacuations are separated from alerts;
- the duplicate rule is documented;
- event status uses controlled values;
- ongoing events do not place text inside the end-date field;
- source publication dates are stored separately;
- initial and follow-up source links can both be preserved;
- fire IDs require explicit evidence;
- the descriptive-only limitation is stated clearly;
- modeling exclusion is stated clearly;
- the output file location is documented;
- the OWF-28 template header is defined.

---

## 17. Final Governance Statement

The Ontario wildfire evacuation log is a manually reviewed descriptive dataset created to add community-impact context to the project.

It does not attempt to represent every evacuation, operate as a live feed, or replace official emergency information.

Each row must be supported by an original CBC or CTV article, represent a confirmed evacuation rather than an alert, follow the fixed schema, preserve source evidence, and avoid unsupported fire attribution.

The log is used only for descriptive annotations in the Tableau story.

It is excluded from AQHI forecasting, model training, and statistical inference.
