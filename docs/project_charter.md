# Ontario Wildfire Impact and Forecasting Analytics

## Project Charter

**Status:** Draft version 0.2 
**Project type:** Academic and Independent Project  
**Author:** Batool Altarawneh  
**Date:** August 2026

## 1. Problem Statement

Ontario's 2026 wildfire season is running significantly above the 10-year average (453 fires YTD vs. 349 in 2025 vs. a 312 average, as of mid-July 2026). 
Elevated fire activity degrades regional air quality and, in severe cases, forces community evacuations. Public dashboards typically show fire activity, air quality, or evacuation news as separate, disconnected feeds, there is no single, accessible view that traces the causal chain from fire activity → air quality impact → community disruption, nor one that attempts to forecast near-term air quality risk from that chain.

This project builds that connected view for a small set of Ontario cities during the 2026 fire season, and adds a forecasting component (multivariate LSTM vs. naive-persistence baseline) to demonstrate applied time-series deep learning on real environmental data.

## 2. Project Goals

1.  Combine three real public data sources (CWFIS fire data, Environment Canada AQHI history, Ontario.ca active fires feed) plus a manually compiled evacuation event log into a coherent, documented dataset.
2. Build and honestly evaluate a next-day AQHI forecasting model: naive-persistence baseline → multivariate LSTM.
3. Present findings as a Tableau story (fire map + AQI trend/forecast overlay + evacuation/community impact).
4. Run the whole thing as a lightweight Agile process (charter → backlog → sprints → retro) as a demonstration of process discipline, not just technical output.

## 3. Success Criteria

The project will be considered successful when the following conditions are met.

1. All data sources are real and sourced from the public locations named above; any synthetic/placeholder data is explicitly labeled as such in the README and never presented as real.
2. Baseline (naive persistence / moving average) is implemented and reported *before* any deep learning work begins.
3. LSTM is compared against the baseline using at least one honest error metric (e.g., RMSE/MAE) across all cities in scope, including any cities/periods where the LSTM underperforms.
4. Star-schema data model documented (fact/dim tables).
5.  Tableau story is functional and tells the fire → air quality → disruption narrative without overstating certainty.
6. README + methodology doc clearly state: dataset size, refresh cadence (static/periodic, not streaming), known limitations, and what is/isn't production-grade.
7. Any public-facing claim about a skill used in this project (e.g. in the README or a project summary) is only made after the underlying skill is actually working code in this repo not before.

## 4. Project Scope

The project will focus on four Ontario cities.

1. Thunder Bay

2. Toronto

3. Kingston

4. Barrie

Thunder Bay represents a city closer to active wildfire regions. Toronto represents a large downstream city that may experience smoke impacts. Kingston provides a geographically distinct location along the same general smoke corridor. Barrie is included because it has its own AQHI monitoring station and has appeared in air quality warning coverage.

The main project period is the 2026 wildfire season. Additional historical AQHI data may be used to provide enough observations for model training and evaluation.

## 5. Data Sources

The project will use four sources.

### 5.1 Canadian Wildland Fire Information System

CWFIS fire occurrence data will provide information about wildfire activity. Data will be accessed through the public WFS endpoint.

### 5.2 Environment and Climate Change Canada AQHI Data

Current AQHI data will be collected through the GeoMet API. Historical AQHI data will be collected through Air Quality Ontario where needed.

### 5.3 Ontario Active Fires Data

Ontario's active fires feed will provide additional situational and map context.

### 5.4 Evacuation Event Log

Evacuation events will be manually collected from reliable public news coverage such as CBC and CTV. This table will be used only for descriptive annotations in the Tableau story.

The evacuation log will not be treated as a live data feed or as a modeled variable.

## 6. Deliverables

The project will produce the following deliverables.

1. A documented project charter.

2. A product backlog with epics, user stories, tasks, and Definitions of Done.

3. Python scripts for data extraction, cleaning, transformation, and loading.

4. A PostgreSQL star schema containing the project data.

5. An exploratory data analysis notebook.

6. A locally scheduled Airflow DAG for daily data collection and loading.

7. Naive persistence and moving average forecasting models.

8. A univariate LSTM model for initial learning and testing.

9. A multivariate LSTM model for next day AQHI forecasting.

10. A model evaluation report with results for each city.

11. A Tableau story.

12. A README, methodology document, and project retrospective.

## 7. Items Outside the Project Scope

The following items are not part of this project.

1. **Not** a real-time or streaming pipeline. Data refresh is periodic, and may be automated on a daily schedule via a locally-run Airflow DAG (decided during Phase 1); this remains fundamentally different from real-time/event-driven streaming.
2. **Not** an always-on, cloud-hosted service. Any scheduled automation (e.g. the Airflow DAG) runs locally, on-demand while actively working on the project; not as a 24/7 hosted production system.
3. **Not** deployed to production or intended for operational/public-safety use.
4. **Not** GPU/cloud training; dataset is small (one fire season, a handful of cities); CPU training is sufficient and appropriate. GPU/cloud is out of scope unless project scope changes materially.
5. **Not** a live evacuation feed — the evacuation log is manually compiled from public news coverage (CBC/CTV) and labeled as a static, non-authoritative log.
6. **Not** an exhaustive multi-year climate model; scope is bounded to the 2026 fire season (plus enough historical AQHI data to give the LSTM a meaningful lookback/training window).
7. **Not** a province-wide or arbitrarily-scaled model; scope is fixed at 4 cities: **Thunder Bay** (fire-source-adjacent), **Toronto** (major downstream smoke-impact city), **Kingston** (geographically distinct third point on the same corridor), and **Barrie** (has its own AQHI monitoring station — weather.gc.ca onaq-016 / airqualityontario.com site 47045 — and is directly named in current smoke/air-quality-warning coverage). Each additional city is a real cost (one more data source to pull/clean/validate in Sprint 1), accepted here because the data supports it.

## 8. Constraints
| Constraint | Detail |
|---|---|
| Compute | CPU only, no GPU |
| Data freshness | Periodic/manual refresh, not streaming |
| Data scope | One fire season (2026), small set of Ontario cities |
| Team | Solo, portfolio context |
| Timeline | Flexible, self-paced |
| Tooling | SQL (T-SQL/Postgres), Python (pandas, NumPy, scikit-learn, Prophet, XGBoost), Power BI experience → Tableau for this project, Airflow, Docker, Git |
| Skill claims | No skill (e.g., TensorFlow/PyTorch) is claimed anywhere as known/used until demonstrated working in this project |

## 9. Planned Tools

The project may use the following tools where appropriate.

1. Python

2. pandas

3. NumPy

4. scikit learn

5. TensorFlow and Keras

6. PostgreSQL

7. Apache Airflow

8. Docker

9. Git and GitHub

10. Tableau

11. Jira

A tool will only be described as a demonstrated project skill after it has been used successfully in the repository.

## 10. Stakeholders and Intended Users

Although this is a solo project, it is designed for three main audiences.

### 10.1 Project Builder

The builder needs a structured project that develops practical data engineering, time series modeling, visualization, and project management skills.

### 10.2 Technical Reviewer

A technical reviewer needs enough documentation and evidence to evaluate the quality of the work without reading every line of code.

### 10.3 Future Project Maintainer

Future review or extension of the project should be possible without repeating all of the original research and decisions.

## 11. Key Risks and Decisions

### 11.1 Limited Evacuation Data

Evacuation events may be too limited and irregular for statistical modeling.

**Decision:** The evacuation log will be used as a descriptive annotation layer in Tableau. It will not be used as an input feature or prediction target.

### 11.2 AQHI Historical Data Availability

The LSTM requires enough historical AQHI data for training, validation, and testing.

Air Quality Ontario allows historical station data to be retrieved over a long period. This should provide enough observations for model development. Station level availability must still be checked before modeling begins.

### 11.3 Wildfire and Air Quality Attribution

Wildfires are an important contributor to poor air quality, but AQHI values may also be affected by weather, local pollution, and smoke movement from other regions.

**Decision:** The project will describe wildfire activity as a contributing factor. It will not claim that wildfire activity is the only cause of AQHI changes.

### 11.4 City Selection

The city scope is limited to Thunder Bay, Toronto, Kingston, and Barrie.

Kingston will remain in the project only if its AQHI station provides adequate historical coverage. If the available data is not sufficient, London may be considered as a replacement.

### 11.5 Model Complexity

An LSTM may be too complex for a relatively small environmental dataset.

**Decision:** The LSTM will only be considered useful if it is evaluated against simple baseline models. If it does not outperform the baselines, that result will be reported honestly.

## 12. Project Definition of Done

The project will be complete when all of the following conditions are met.

1. The data pipeline runs successfully using real data.

2. The star schema is implemented and documented.

3. The exploratory analysis identifies missing data, coverage issues, and major data quality concerns.

4. Both baseline models are implemented and evaluated.

5. The LSTM model produces forecasts for all cities in scope.

6. The LSTM results are compared directly with the baseline results.

7. Limitations and underperformance cases are documented.

8. The Tableau story is complete and understandable without a verbal explanation.

9. The README and methodology document match the actual completed work.

10. A project retrospective has been completed.

## 13. Scope Decision Log

### Decision 1

**Date:** July 2026

**Decision:** The city scope was set to Thunder Bay, Toronto, Kingston, and Barrie.

**Reason:** These cities provide different geographic and air quality perspectives while keeping the project manageable.

### Decision 2

**Date:** July 2026

**Decision:** A locally scheduled Airflow DAG was added.

**Reason:** This demonstrates practical workflow automation without changing the project into a real time or production system.

### Decision 3

**Date:** July 2026

**Decision:** The data foundation sprint was extended to ten business days.

**Reason:** Additional time was required for the Airflow work and data validation.

### Decision 4

**Date:** July 2026

**Decision:** Evacuation events were kept as descriptive annotations.

**Reason:** The available data is not sufficient for reliable statistical modeling.

### Decision 5

**Date:** July 2026

**Decision:** Baseline models must be completed before LSTM development.

**Reason:** This provides a fair standard for evaluating whether the LSTM adds value.

### Decision 6

**Date:** August 3, 2026

**Decision:** Sprint 1 was extended to August 21, 2026, and the Airflow DAG work was moved from Sprint 1 to Sprint 2.

**Reason:** Data-source extraction and validation required more investigation than originally estimated. The remaining star-schema design, transformation, PostgreSQL loading, data-quality validation, and exploratory analysis could not be completed responsibly by the original August 5 deadline. Airflow automation is logically separable from the usable data foundation, because the extraction scripts can be run manually while the database and baseline models are developed.

## 14. Next Step

The next step is to complete the remaining Sprint 1 data-foundation work by August 21, 2026.

The immediate priorities are:

1. Complete and document the evacuation event log.
2. Extract and validate hourly ECCC weather data for the four selected cities.
3. Design and implement the PostgreSQL star schema.
4. Consolidate the extraction, cleaning, and transformation workflow.
5. Load the validated data into PostgreSQL.
6. Complete the exploratory data analysis and the initial wildfire–AQHI relationship review.
7. Consolidate the data-source and column documentation.

The Airflow DAG has been moved to Sprint 2 and will be implemented after the standalone data pipeline is stable
