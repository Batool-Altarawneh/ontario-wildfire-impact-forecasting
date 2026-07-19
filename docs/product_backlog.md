# Ontario Wildfire Impact and Forecasting Analytics

## Product Backlog

**Status:** Draft version 0.2  
**Project type:** Academic and Independent Project  
**Prepared by:** Batool Altarawneh  
**Date:** July 2026

This backlog follows the scope defined in the project charter and the schedule in the project phase plan. The work is organized into six epics and six sprints. Sprint 1 focuses on the data foundation. The baseline models must be completed before any LSTM work begins.

## Project Scope

The project covers four Ontario cities:

1. Thunder Bay
2. Toronto
3. Kingston
4. Barrie

The project uses the following data sources:

1. CWFIS wildfire data
2. Environment and Climate Change Canada AQHI data, with historical data from Air Quality Ontario where needed
3. Ontario active fires data
4. A manually collected evacuation event log based on public news coverage

The main analysis period is the 2026 wildfire season. Additional historical AQHI data may be used for model training and evaluation.

## Epic 1: Data Pipeline

**Sprint:** Sprint 1  
**Duration:** 10 business days  
**Dates:** July 23 to August 5, 2026

### Purpose

Build a reliable data foundation before starting any forecasting work. The data will be collected, cleaned, checked, and loaded into a PostgreSQL star schema. The three live data pulls will later be scheduled through a local Airflow DAG.

### User Stories

1. As the project owner, I need wildfire and AQHI data for all four cities so I can prepare the daily modeling dataset.
2. As the project owner, I need the data stored in one consistent schema so the same tables can support analysis, modeling, and Tableau.
3. As a reviewer, I need each source to be traceable so I can confirm that the project uses real public data.
4. As the project owner, I need the recurring data pulls scheduled locally so I do not have to repeat the same manual steps each day.

### Tasks

- [ ] Confirm the Kingston AQHI station and review its historical data coverage
- [ ] Record the station name, station ID, available date range, and any major gaps
- [ ] Decide whether Kingston will remain in scope or be replaced by London if the coverage is not sufficient
- [ ] Pull CWFIS wildfire data for the selected 2026 date range
- [ ] Pull current AQHI data from the Environment and Climate Change Canada GeoMet API
- [ ] Download the required historical AQHI data from Air Quality Ontario
- [ ] Pull the Ontario active fires data needed for map and situational context
- [ ] Confirm where temperature and wind fields will come from within the selected Environment and Climate Change Canada data
- [ ] Create the evacuation event log with community, date, nearby city, source, and notes
- [ ] Label the evacuation log as manually collected and descriptive only
- [ ] Review sample files from every source and document the available columns
- [ ] Sketch the star schema before writing the database code
- [ ] Create the city, date, and station dimension tables
- [ ] Create the daily observation fact table
- [ ] Write Python extraction scripts for each source
- [ ] Write cleaning and transformation steps using pandas
- [ ] Load the cleaned data into PostgreSQL
- [ ] Add basic checks for duplicates, missing values, date coverage, and invalid values
- [ ] Create an EDA notebook with coverage summaries and distribution checks
- [ ] Review the first relationship between wildfire activity and AQHI without making a causal claim
- [ ] Test each extraction and loading script separately
- [ ] Create the local Airflow DAG after the individual scripts are working
- [ ] Add one Airflow task for each live source, followed by transformation and database loading tasks
- [ ] Add retries and basic failure logging
- [ ] Schedule the DAG to run daily on the local Airflow instance
- [ ] Run the DAG successfully on a schedule at least once
- [ ] Document the DAG structure and local setup

### Definition of Done

- [ ] All four data sources have been collected and their origins are documented
- [ ] Kingston's historical AQHI coverage has been confirmed, or a replacement city has been documented
- [ ] The PostgreSQL star schema is implemented and documented
- [ ] The fact and dimension tables contain real project data
- [ ] The EDA notebook identifies missing data, coverage issues, and major quality concerns
- [ ] The evacuation table is clearly labeled as manually collected and is not used as a model input
- [ ] The extraction and loading scripts work outside Airflow
- [ ] The Airflow DAG completes successfully on a local daily schedule
- [ ] Retry and failure logging have been tested
- [ ] The documentation states that the workflow is local and scheduled, not real time or production hosted

## Epic 2: Baseline Modeling

**Sprint:** Sprint 2  
**Duration:** 3 business days  
**Dates:** August 6 to August 10, 2026

### Purpose

Create simple forecasting methods that will be used as comparison points for the LSTM. These results must be completed and saved before deep learning work begins.

### User Stories

1. As the project owner, I need a simple forecast using today's AQHI so I have a basic performance benchmark.
2. As the project owner, I need a moving average forecast so the LSTM is compared with more than one baseline.
3. As a reviewer, I need the same train and test periods used across all models so the comparison is fair.

### Tasks

- [ ] Choose and document the time based train and test split
- [ ] Keep the split consistent for the baseline and LSTM models
- [ ] Build a naive persistence forecast for each city
- [ ] Build a moving average forecast for each city
- [ ] Select the moving average window and record the reason for the choice
- [ ] Calculate MAE and RMSE for both baselines by city
- [ ] Create a results table for the four cities
- [ ] Write a short summary of the baseline results
- [ ] Commit the baseline code and results before starting Sprint 3

### Definition of Done

- [ ] Both baseline methods run for every city in scope
- [ ] MAE and RMSE are reported separately for each city
- [ ] The train and test split is saved and documented
- [ ] Baseline results are committed before the LSTM work begins
- [ ] No changes are made to the split after reviewing the LSTM results unless the full comparison is rerun and documented

## Epic 3: LSTM Modeling

This epic is divided into two sprints. Sprint 3 covers the univariate model. Sprint 4 extends it to a multivariate model and includes limited tuning.

## Sprint 3: Univariate LSTM Fundamentals

**Duration:** 6 business days  
**Dates:** August 11 to August 18, 2026

### Purpose

Learn and test the basic LSTM workflow using AQHI from one city before adding more features and cities.

### User Stories

1. As the project owner, I need to understand the main LSTM concepts before building the model.
2. As the project owner, I need a small univariate model so I can test the data preparation and training process with limited complexity.
3. As a reviewer, I need the main model choices explained so the work is understandable and reproducible.

### Tasks

- [ ] Write a short explanation of LSTM gates, cell state, and vanishing gradients in my own words
- [ ] Select one city for the first univariate model
- [ ] Prepare AQHI lookback windows for that city
- [ ] Fit all preprocessing steps using the training data only
- [ ] Build and train a small univariate LSTM using TensorFlow and Keras
- [ ] Save the training and validation loss history
- [ ] Add dropout after the first model is working
- [ ] Compare the loss curves before and after dropout
- [ ] Record the lookback length, number of units, epochs, batch size, and learning rate
- [ ] Write a short reason for each main choice
- [ ] Save the model output and notes in the repository

### Definition of Done

- [ ] The LSTM concept notes are written in my own words
- [ ] The univariate input windows are created correctly
- [ ] The model trains and produces forecasts for the selected city
- [ ] Training and validation loss curves are saved
- [ ] Dropout is tested and the result is documented
- [ ] The main model settings and reasons are recorded

## Sprint 4: Multivariate LSTM and Tuning

**Duration:** 6 business days  
**Dates:** August 19 to August 26, 2026

### Purpose

Extend the working univariate model to use AQHI, wildfire activity, temperature, and wind across all four cities.

### User Stories

1. As the project owner, I need a multivariate dataset so the model can use more than AQHI history alone.
2. As the project owner, I need forecasts for every city in scope so the final comparison is complete.
3. As a reviewer, I need the tuning process to be limited and documented rather than presented as an unexplained automated search.

### Tasks

- [ ] Prepare the multivariate feature set using AQHI, fire count, temperature, and wind
- [ ] Check feature availability and missing values for each city
- [ ] Scale each feature using parameters fitted on the training data only
- [ ] Decide whether to use one shared model or separate city models
- [ ] Document the reason for the shared or separate model decision
- [ ] Build the multivariate lookback windows
- [ ] Train the model for all four cities
- [ ] Compare a small number of lookback lengths
- [ ] Compare a small number of hidden unit settings
- [ ] Compare a small number of dropout rates
- [ ] Compare a small number of learning rates
- [ ] Review the training and validation curves for overfitting
- [ ] Save the selected settings and the reason for each final choice
- [ ] Generate next day AQHI forecasts for each city

### Definition of Done

- [ ] The final feature set is documented
- [ ] Scaling is fitted on training data only
- [ ] The shared model or separate model decision is documented
- [ ] The model produces forecasts for all cities in scope
- [ ] The tuning process is limited, clear, and reproducible
- [ ] Any signs of overfitting or limited validation data are documented
- [ ] The final settings are saved with short reasons

## Epic 4: Evaluation and Retrospective

**Sprint:** Sprint 5  
**Duration:** 4 business days  
**Dates:** August 27 to September 1, 2026

### Purpose

Compare the LSTM with both baseline models and document the results honestly for each city. This sprint also includes a short review of the project process.

### User Stories

1. As a reviewer, I need a direct comparison between the LSTM and both baseline methods for each city.
2. As the project owner, I need to identify where the LSTM performs well and where it does not.
3. As the project owner, I need a retrospective so I can record what worked and what should change in a future project.

### Tasks

- [ ] Calculate MAE and RMSE for the LSTM by city
- [ ] Combine the LSTM and baseline results in one comparison table
- [ ] Create forecast versus actual plots for each city
- [ ] Review periods where the LSTM performs worse than the baselines
- [ ] Check whether performance changes during high AQHI periods
- [ ] Record the main findings without overstating the model's value
- [ ] Document data limitations and modeling limitations
- [ ] Write a short retrospective covering what went well
- [ ] Record work that took longer than planned
- [ ] Record what I would change in a future version of the project

### Definition of Done

- [ ] One comparison table includes both baselines and the LSTM for every city
- [ ] MAE and RMSE are reported by city
- [ ] Forecast versus actual plots are complete
- [ ] Any underperformance is documented rather than omitted
- [ ] The evaluation explains that wildfire activity is one contributing factor and not the only cause of AQHI changes
- [ ] The retrospective is saved in the repository

## Epic 5: Tableau Story

**Sprint:** Sprint 6  
**Duration:** Shared with Epic 6  
**Dates:** September 2 to September 9, 2026

### Purpose

Present the data and model results in a clear Tableau story that connects wildfire activity, AQHI conditions, forecasts, and evacuation events.

### User Stories

1. As a reviewer, I need a visual summary of the project without having to read the code first.
2. As the project owner, I need the evacuation events presented as context and not as model output.
3. As a viewer, I need clear labels and explanations so the story can be understood without a verbal presentation.

### Tasks

- [ ] Plan the order of the Tableau story pages
- [ ] Build the wildfire map using CWFIS and Ontario active fires data
- [ ] Build AQHI history views for the four cities
- [ ] Add actual and forecast AQHI values to the city views
- [ ] Include the baseline and LSTM results where the comparison is useful
- [ ] Add evacuation events as manually collected annotations
- [ ] Make the evacuation layer visually different from the modeled data
- [ ] Add titles, captions, filters, and source notes
- [ ] State that the work is an Academic and Independent Project
- [ ] Review the full story for unclear or overstated claims

### Definition of Done

- [ ] The Tableau story includes the wildfire map, AQHI trends, forecasts, and evacuation annotations
- [ ] The four cities can be reviewed clearly
- [ ] Evacuation events are labeled as manually collected context
- [ ] Model output and descriptive data are visually distinct
- [ ] Data sources and important limitations are visible
- [ ] The story can be followed without a separate verbal explanation

## Epic 6: Documentation

**Sprint:** Sprint 6  
**Duration:** Shared with Epic 5  
**Dates:** September 2 to September 9, 2026

### Purpose

Complete the README, methodology notes, and final project documentation using the work that was actually completed in the repository.

### User Stories

1. As a reviewer, I need clear setup and methodology notes so I can understand how the project was completed.
2. As the project owner, I need the documentation to match the code, data, and results in the repository.
3. As a future maintainer, I need enough detail to review or extend the project later.

### Tasks

- [ ] Write the README with the project purpose and scope
- [ ] List the data sources and include source links
- [ ] Add the project folder structure and setup instructions
- [ ] Add the PostgreSQL star schema diagram
- [ ] Explain the extraction, cleaning, and loading process
- [ ] Explain the local Airflow workflow and schedule
- [ ] Describe the baseline models and LSTM approach
- [ ] Add the final MAE and RMSE results
- [ ] Document the dataset size and date coverage
- [ ] Document missing data and other known limitations
- [ ] State that the project is not real time, production ready, or intended for public safety decisions
- [ ] Check every listed skill against working code in the repository
- [ ] Add the project retrospective
- [ ] Complete a final consistency check across the charter, phase plan, backlog, code, and README

### Definition of Done

- [ ] The README and methodology notes reflect the completed work
- [ ] Data sources, date coverage, and dataset size are documented
- [ ] The star schema and Airflow workflow are explained
- [ ] Model methods, results, and limitations are included
- [ ] No documentation describes the project as real time or production ready
- [ ] No tool or skill is claimed unless it is supported by working project files
- [ ] The charter, backlog, phase plan, and final repository are consistent

## Sprint Schedule

| Sprint | Main Work | Duration | Dates |
|---|---|---:|---|
| Sprint 1 | Data foundation and local Airflow DAG | 10 business days | July 23 to August 5, 2026 |
| Sprint 2 | Baseline modeling | 3 business days | August 6 to August 10, 2026 |
| Sprint 3 | Univariate LSTM | 6 business days | August 11 to August 18, 2026 |
| Sprint 4 | Multivariate LSTM and tuning | 6 business days | August 19 to August 26, 2026 |
| Sprint 5 | Evaluation and retrospective | 4 business days | August 27 to September 1, 2026 |
| Sprint 6 | Tableau story and documentation | 6 business days | September 2 to September 9, 2026 |

The planned total is 39 business days. The dates may change as the work progresses. A sprint should not begin until the required work from the previous sprint is complete.
