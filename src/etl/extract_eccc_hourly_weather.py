"""
OWF-48 - ECCC Hourly Weather Data Extraction

This script downloads hourly weather data for four Ontario cities:

- Barrie
- Kingston
- Thunder Bay
- Toronto

ECCC allows us to download one month for one station in each request.

The required project period is:
January 2024 to July 2026.

The script first runs in TEST_MODE using only:
Barrie - January 2024.

After the test works successfully, TEST_MODE can be changed to False
to download all stations and months.
"""

# Import the libraries needed by the script.
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests


# ---------------------------------------------------------
# 1. GENERAL SETTINGS
# ---------------------------------------------------------

# Official ECCC bulk-download URL.
BULK_DATA_URL = (
    "https://climate.weather.gc.ca/"
    "climate_data/bulk_data_e.html"
)

# Information about the four selected weather stations.
#
# station_id is the ID required by the ECCC download URL.
# climate_id is the public climate identifier for the station.
STATIONS = {
    42183: {
        "city": "Barrie",
        "station_name": "BARRIE-ORO",
        "climate_id": "6117700",
    },
    47267: {
        "city": "Kingston",
        "station_name": "KINGSTON CLIMATE",
        "climate_id": "6104142",
    },
    30682: {
        "city": "Thunder Bay",
        "station_name": "THUNDER BAY CS",
        "climate_id": "6048268",
    },
    31688: {
        "city": "Toronto",
        "station_name": "TORONTO CITY",
        "climate_id": "6158355",
    },
}

# The exact date range required for the project.
START_YEAR = 2024
START_MONTH = 1

END_YEAR = 2026
END_MONTH = 7

# timeframe=1 means hourly data in the ECCC download tool.
HOURLY_TIMEFRAME = 1

# Stop waiting if one request takes more than 60 seconds.
REQUEST_TIMEOUT = 60

# Wait between requests to avoid sending requests too quickly.
REQUEST_DELAY = 1.5

# Try a failed request up to three times.
MAX_RETRIES = 3

# Wait before retrying a failed request.
RETRY_WAIT = 5

# Keep this True during the first test.
# Change it to False only after the test is successful.
TEST_MODE = False


# ---------------------------------------------------------
# 2. FOLDER SETTINGS
# ---------------------------------------------------------

# Raw monthly files will be saved exactly as downloaded.
RAW_FOLDER = Path("data/raw/eccc_weather")

# The combined and cleaned dataset will be saved here.
PROCESSED_FOLDER = Path("data/processed/eccc_weather")

# A simple extraction summary will be saved here.
QUALITY_FOLDER = Path("data/quality/eccc_weather")


# ---------------------------------------------------------
# 3. CREATE THE LIST OF REQUIRED MONTHS
# ---------------------------------------------------------

def create_month_list(start_year, start_month, end_year, end_month):
    """
    Create a list containing every year and month in the required period.

    Example:
    [(2024, 1), (2024, 2), ..., (2026, 7)]
    """

    months = []

    current_year = start_year
    current_month = start_month

    # Continue until the current year/month passes the end date.
    while (current_year, current_month) <= (end_year, end_month):

        months.append((current_year, current_month))

        # Move to the next month.
        current_month += 1

        # After December, move to January of the next year.
        if current_month == 13:
            current_month = 1
            current_year += 1

    return months


# ---------------------------------------------------------
# 4. CHECK THAT THE RESPONSE LOOKS LIKE A CSV
# ---------------------------------------------------------

def response_is_valid(response):
    """
    Check whether the response looks like real ECCC weather data.

    A valid ECCC hourly CSV should contain a Date/Time column
    and should contain more than one line.
    """

    response_text = response.text

    has_date_column = "Date/Time" in response_text
    has_multiple_lines = response_text.count("\n") > 1

    if has_date_column and has_multiple_lines:
        return True

    return False


# ---------------------------------------------------------
# 5. DOWNLOAD ONE MONTH FOR ONE STATION
# ---------------------------------------------------------

def download_one_month(station_id, year, month, file_path):
    """
    Download one month of hourly weather data.

    The function returns True if the file was downloaded successfully.
    It returns False if all attempts fail.
    """

    # Parameters expected by the ECCC bulk-download tool.
    params = {
        "format": "csv",
        "stationID": station_id,
        "Year": year,
        "Month": month,
        "Day": 14,
        "timeframe": HOURLY_TIMEFRAME,
        "submit": "Download Data",
    }

    # Try the request more than once if a connection error happens.
    for attempt in range(1, MAX_RETRIES + 1):

        try:
            print(
                f"    Download attempt {attempt}/{MAX_RETRIES}"
            )

            response = requests.get(
                BULK_DATA_URL,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            # Raise an error for HTTP responses such as 404 or 500.
            response.raise_for_status()

            # Confirm that the response looks like weather data.
            if not response_is_valid(response):
                print(
                    "    The response did not look like a valid "
                    "ECCC hourly CSV."
                )
                return False

            # Save the original response bytes.
            # This preserves the raw file as downloaded.
            file_path.write_bytes(response.content)

            print(f"    Raw file saved: {file_path}")

            return True

        except requests.RequestException as error:
            print(f"    Request failed: {error}")

            # Wait before trying again.
            if attempt < MAX_RETRIES:
                wait_time = RETRY_WAIT * attempt

                print(
                    f"    Waiting {wait_time} seconds "
                    "before the next attempt..."
                )

                time.sleep(wait_time)

    print("    All download attempts failed.")

    return False


# ---------------------------------------------------------
# 6. CLEAN THE COLUMN NAMES
# ---------------------------------------------------------

def clean_column_names(dataframe):
    """
    Convert column names into a format that is easier to use.

    Example:
    'Date/Time (LST)' becomes 'date_time_lst'
    """

    dataframe.columns = (
        dataframe.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )

    return dataframe


# ---------------------------------------------------------
# 7. DOWNLOAD AND COMBINE ALL REQUIRED FILES
# ---------------------------------------------------------

def extract_weather_data(stations, required_months):
    """
    Download all required station/month combinations.

    Existing files are skipped so the script can continue after
    a partial failure without downloading everything again.
    """

    # Create the raw folder if it does not already exist.
    RAW_FOLDER.mkdir(parents=True, exist_ok=True)

    # All monthly DataFrames will be stored in this list.
    all_dataframes = []

    # Counters used in the final summary.
    downloaded_count = 0
    skipped_count = 0
    failed_count = 0

    # Store information about failed files.
    failed_files = []

    total_files = len(stations) * len(required_months)
    current_file_number = 0

    # First loop: station.
    for station_id, station_info in stations.items():

        city = station_info["city"]
        station_name = station_info["station_name"]
        climate_id = station_info["climate_id"]

        print("\n" + "=" * 60)
        print(f"Station: {station_name}")
        print(f"City: {city}")
        print(f"Station ID: {station_id}")
        print("=" * 60)

        # Second loop: year and month.
        for year, month in required_months:

            current_file_number += 1

            print(
                f"\n[{current_file_number}/{total_files}] "
                f"{city} - {year}-{month:02d}"
            )

            # Create a clear filename for the raw monthly file.
            raw_filename = (
                f"{city.lower().replace(' ', '_')}_"
                f"{station_id}_"
                f"{year}_"
                f"{month:02d}.csv"
            )

            raw_file_path = RAW_FOLDER / raw_filename

            # If the file already exists, do not download it again.
            if raw_file_path.exists():
                print("    File already exists. Skipping download.")

                skipped_count += 1

            else:
                download_successful = download_one_month(
                    station_id=station_id,
                    year=year,
                    month=month,
                    file_path=raw_file_path,
                )

                # Wait after each request.
                time.sleep(REQUEST_DELAY)

                if download_successful:
                    downloaded_count += 1

                else:
                    failed_count += 1

                    failed_files.append(
                        f"{city}, {station_id}, "
                        f"{year}-{month:02d}"
                    )

                    # Continue to the next month.
                    continue

            # Try to read the downloaded or existing CSV.
            try:
                monthly_dataframe = pd.read_csv(raw_file_path)

            except Exception as error:
                print(f"    Pandas could not read the CSV: {error}")

                failed_count += 1

                failed_files.append(
                    f"{city}, {station_id}, "
                    f"{year}-{month:02d}, CSV read error"
                )

                continue

            # Add project-specific station information.
            monthly_dataframe["project_city"] = city

            monthly_dataframe["project_station_name"] = (
                station_name
            )

            monthly_dataframe["project_station_id"] = station_id

            monthly_dataframe["project_climate_id"] = climate_id

            # Add the monthly DataFrame to the list.
            all_dataframes.append(monthly_dataframe)

            print(
                f"    Rows read: {len(monthly_dataframe)}"
            )

    # Return an empty DataFrame if nothing was downloaded.
    if len(all_dataframes) == 0:
        combined_dataframe = pd.DataFrame()

    else:
        # Combine all stations and months into one DataFrame.
        combined_dataframe = pd.concat(
            all_dataframes,
            ignore_index=True,
            sort=False,
        )

    extraction_stats = {
        "total_expected_files": total_files,
        "downloaded_files": downloaded_count,
        "skipped_existing_files": skipped_count,
        "failed_files_count": failed_count,
        "failed_files": failed_files,
    }

    return combined_dataframe, extraction_stats


# ---------------------------------------------------------
# 8. CREATE A SIMPLE EXTRACTION SUMMARY FILE
# ---------------------------------------------------------

def save_extraction_summary(stats, total_rows, summary_path):
    """
    Save a text file describing what happened during the extraction.
    """

    summary_lines = [
        "OWF-48 ECCC Weather Extraction Summary",
        "=" * 50,
        f"Total expected files: {stats['total_expected_files']}",
        f"Newly downloaded files: {stats['downloaded_files']}",
        (
            "Existing files skipped: "
            f"{stats['skipped_existing_files']}"
        ),
        f"Failed files: {stats['failed_files_count']}",
        f"Total combined rows: {total_rows}",
        "",
        "Failed file details:",
    ]

    if len(stats["failed_files"]) == 0:
        summary_lines.append("None")

    else:
        for failed_file in stats["failed_files"]:
            summary_lines.append(f"- {failed_file}")

    summary_text = "\n".join(summary_lines)

    summary_path.write_text(
        summary_text,
        encoding="utf-8",
    )


# ---------------------------------------------------------
# 9. MAIN PROGRAM
# ---------------------------------------------------------

def main():
    """
    Main function that controls the full extraction process.
    """

    print("=" * 60)
    print("OWF-48 - ECCC Hourly Weather Extraction")
    print("=" * 60)

    # Create the complete list from January 2024 to July 2026.
    all_required_months = create_month_list(
        START_YEAR,
        START_MONTH,
        END_YEAR,
        END_MONTH,
    )

    if TEST_MODE:
        print("\nTEST MODE is enabled.")
        print("Only Barrie - January 2024 will be processed.\n")

        # Use only the Barrie station.
        stations_to_use = {
            42183: STATIONS[42183]
        }

        # Use only January 2024.
        months_to_use = [
            (2024, 1)
        ]

    else:
        print("\nFULL MODE is enabled.")
        print(
            "All four stations from January 2024 "
            "to July 2026 will be processed.\n"
        )

        stations_to_use = STATIONS
        months_to_use = all_required_months

    # Run the extraction.
    weather_dataframe, extraction_stats = extract_weather_data(
        stations=stations_to_use,
        required_months=months_to_use,
    )

    total_rows = len(weather_dataframe)

    print("\n" + "=" * 60)
    print("EXTRACTION RESULTS")
    print("=" * 60)

    print(
        f"Expected files: "
        f"{extraction_stats['total_expected_files']}"
    )

    print(
        f"New files downloaded: "
        f"{extraction_stats['downloaded_files']}"
    )

    print(
        f"Existing files skipped: "
        f"{extraction_stats['skipped_existing_files']}"
    )

    print(
        f"Failed files: "
        f"{extraction_stats['failed_files_count']}"
    )

    print(f"Total rows: {total_rows}")

    # Stop if no usable data was found.
    if weather_dataframe.empty:
        print("\nNo weather data was available. Stopping.")
        return

    # Clean the column names.
    cleaned_dataframe = clean_column_names(
        weather_dataframe.copy()
    )

    print("\nRows per city:")

    print(
        cleaned_dataframe[
            "project_city"
        ].value_counts()
    )

    # Find a column that contains both "date" and "time".
    possible_date_columns = []

    for column in cleaned_dataframe.columns:
        if "date" in column and "time" in column:
            possible_date_columns.append(column)

    if len(possible_date_columns) > 0:
        date_column = possible_date_columns[0]

        print(f"\nDate column found: {date_column}")

        print(
            f"Minimum date: "
            f"{cleaned_dataframe[date_column].min()}"
        )

        print(
            f"Maximum date: "
            f"{cleaned_dataframe[date_column].max()}"
        )

    # Display a reminder about wind direction.
    possible_wind_columns = []

    for column in cleaned_dataframe.columns:
        if "wind_dir" in column:
            possible_wind_columns.append(column)

    if len(possible_wind_columns) > 0:
        wind_column = possible_wind_columns[0]

        print(
            f"\nReminder: {wind_column} is reported in "
            "tens of degrees."
        )

        print(
            "Example: a value of 27 represents 270 degrees."
        )

        print(
            "The value is not converted in this extraction script."
        )

    # Create output folders.
    PROCESSED_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    QUALITY_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Use UTC time in the output filename.
    timestamp = datetime.utcnow().strftime(
        "%Y%m%dT%H%M%SZ"
    )

    processed_file_path = (
        PROCESSED_FOLDER
        / f"eccc_hourly_weather_{timestamp}.csv"
    )

    summary_file_path = (
        QUALITY_FOLDER
        / f"eccc_weather_extraction_summary_{timestamp}.txt"
    )

    # Save the combined cleaned dataset.
    cleaned_dataframe.to_csv(
        processed_file_path,
        index=False,
    )

    # Save the extraction summary.
    save_extraction_summary(
        stats=extraction_stats,
        total_rows=total_rows,
        summary_path=summary_file_path,
    )

    print(
        f"\nProcessed dataset saved to:\n"
        f"{processed_file_path}"
    )

    print(
        f"\nExtraction summary saved to:\n"
        f"{summary_file_path}"
    )

    print("\nOWF-48 extraction completed.")


# Run main() only when this Python file is executed directly.
if __name__ == "__main__":
    main()