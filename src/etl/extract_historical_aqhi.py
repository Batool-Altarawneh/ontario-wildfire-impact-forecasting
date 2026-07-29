import re
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests


# ---------------------------------------------------------
# AIR QUALITY ONTARIO WEBSITE
# ---------------------------------------------------------

# This webpage returns historical AQHI tables.
#
# It is an HTML webpage, not a JSON API.
AQO_BASE_URL = (
    "https://www.airqualityontario.com/"
    "aqhi/search.php"
)


# ---------------------------------------------------------
# AQHI VALUE TYPES
# ---------------------------------------------------------

# The show_day values were confirmed manually
# through the Air Quality Ontario search form.
#
# show_day = 0:
# One AQHI value per day at 4:00 PM.
#
# show_day = 2:
# The maximum AQHI value recorded during each day.
VALUE_TYPES = {
    0: "daily_4pm",
    2: "daily_max",
}


# ---------------------------------------------------------
# PROJECT STATIONS
# ---------------------------------------------------------

# Air Quality Ontario uses numeric station IDs.
#
# These IDs are different from the letter-based location IDs used by GeoMet.
#
# Dictionary structure:
#
# station_id: (project city, AQO station name)
STATIONS = {
    47045: (
        "Barrie",
        "Barrie",
    ),
    52023: (
        "Kingston",
        "Kingston",
    ),
    63200: (
        "Thunder Bay",
        "Thunder Bay",
    ),
    31129: (
        "Toronto",
        "Toronto Downtown",
    ),
    33003: (
        "Toronto",
        "Toronto East",
    ),
    34021: (
        "Toronto",
        "Toronto North",
    ),
    35125: (
        "Toronto",
        "Toronto West",
    ),
}


# Historical years selected for this project.
YEARS = [
    2024,
    2025,
    2026,
]


# Wait between requests so the script does not
# send many requests to the government website
# at the same time.
REQUEST_DELAY_SECONDS = 1.5


# ---------------------------------------------------------
# TEST MODE
# ---------------------------------------------------------

# Keep this True for the first test.
#
# The script will download only:
#
# Barrie
# 2026
# daily 4:00 PM and daily maximum values
#
# After confirming that the result is correct,
# change this value to False to run all 42 requests.
TEST_MODE = False


def clean_column_names(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Clean the column names returned by pandas.read_html().

    HTML tables may contain spaces, capital letters,
    duplicated column names, or multi-level headers.

    This function changes the column names into simple
    lowercase names that are easier to work with.

    Example
    -------
    "Station Name" becomes "station_name".
    """

    cleaned_names = []

    # This dictionary helps us handle duplicate names.
    name_counts = {}

    for column in dataframe.columns:

        # Some HTML tables may create tuple column names
        # when the table header uses merged cells.
        if isinstance(column, tuple):
            column_parts = []

            for part in column:
                part_text = str(part).strip()

                # Ignore empty or unnamed header parts.
                if (
                    part_text
                    and not part_text.lower().startswith(
                        "unnamed"
                    )
                ):
                    # Avoid repeating the same header text.
                    if part_text not in column_parts:
                        column_parts.append(
                            part_text
                        )

            column_name = "_".join(
                column_parts
            )

        else:
            column_name = str(
                column
            ).strip()

        # Replace spaces and special characters
        # with underscores.
        column_name = re.sub(
            r"[^a-zA-Z0-9]+",
            "_",
            column_name,
        )

        column_name = (
            column_name
            .strip("_")
            .lower()
        )

        # Use a generic name if the column
        # does not have a readable header.
        if not column_name:
            column_name = "unnamed_column"

        # Handle duplicated column names.
        #
        # Example:
        #
        # aqhi
        # aqhi_2
        if column_name in name_counts:
            name_counts[column_name] += 1

            column_name = (
                f"{column_name}_"
                f"{name_counts[column_name]}"
            )

        else:
            name_counts[column_name] = 1

        cleaned_names.append(
            column_name
        )

    # Apply the cleaned column names.
    dataframe.columns = cleaned_names

    return dataframe


def find_aqhi_results_table(
    tables: list,
) -> pd.DataFrame:
    """
    Find the AQHI results table from the list of
    HTML tables returned by pandas.read_html().

    The expected results table should contain columns
    related to Date, AQHI, and Category.

    Returns an empty DataFrame if the correct table
    cannot be found.
    """

    for table in tables:

        # Combine all column names into one lowercase
        # text value so we can inspect them.
        column_text = " ".join(
            str(column).lower()
            for column in table.columns
        )

        # Check whether this looks like
        # the AQHI results table.
        has_date = "date" in column_text
        has_aqhi = "aqhi" in column_text
        has_category = "category" in column_text

        if (
            has_date
            and has_aqhi
            and has_category
        ):
            # Return a copy so that later changes
            # do not affect the original table.
            return table.copy()

    # Return an empty table when no matching
    # AQHI results table was found.
    return pd.DataFrame()


def fetch_aqo_year(
    station_id: int,
    year: int,
    show_day: int,
) -> pd.DataFrame:
    """
    Download one AQHI table from Air Quality Ontario.

    One request represents:

    - one station;
    - one year;
    - one AQHI value type.

    Parameters
    ----------
    station_id:
        Numeric Air Quality Ontario station ID.

    year:
        Historical year requested.

    show_day:
        AQHI value mode.

        0 means daily 4:00 PM values.
        2 means daily maximum values.

    Returns
    -------
    pandas.DataFrame
        The AQHI table returned by the website.
    """

    # Build the parameters expected by
    # the Air Quality Ontario search form.
    params = {
        "stationid": station_id,
        "show_day": show_day,

        # In year-view mode, start_day and start_month
        # appear to be ignored.
        #
        # We still send January 1 for clarity.
        "start_day": 1,
        "start_month": 1,

        # The requested year controls which year's
        # daily observations are returned.
        "start_year": year,

        # This is the value of the website's
        # search button.
        "submit_search": "Get AQHI values",
    }

    # Send the request to the website.
    response = requests.get(
        AQO_BASE_URL,
        params=params,
        timeout=60,
    )

    # Print the final URL created by requests.
    #
    # This is useful for debugging and documentation.
    print(
        f"  Request URL: "
        f"{response.url}"
    )

    # Print the page response before stopping
    # if the request failed.
    if not response.ok:
        print(
            f"  Request failed with status code "
            f"{response.status_code}."
        )

        print("  Server response:")
        print(response.text)

    # Stop this request if an HTTP error occurred.
    response.raise_for_status()

    # pandas.read_html() expects HTML text or
    # a file-like object.
    #
    # StringIO converts the response text into
    # a file-like object.
    try:
        tables = pd.read_html(
            StringIO(
                response.text
            )
        )

    except ValueError:
        # pandas raises ValueError when no
        # HTML tables are found.
        print(
            "  No HTML tables were found "
            "on the returned page."
        )

        return pd.DataFrame()

    # Look for the table containing the
    # AQHI results.
    results_table = find_aqhi_results_table(
        tables
    )

    if results_table.empty:
        print(
            "  The page contained HTML tables, "
            "but the AQHI results table "
            "could not be identified."
        )

        print(
            f"  Number of HTML tables found: "
            f"{len(tables)}"
        )

        return pd.DataFrame()

    # Clean the HTML table column names.
    results_table = clean_column_names(
        results_table
    )

    return results_table


def fetch_all_aqo_data(
    stations: dict,
    years: list,
) -> pd.DataFrame:
    """
    Download historical AQHI data for all requested
    stations, years, and AQHI value types.

    Parameters
    ----------
    stations:
        Dictionary containing station IDs,
        project cities, and station names.

    years:
        List of years to download.

    Returns
    -------
    pandas.DataFrame
        One combined table containing all
        successfully downloaded AQHI records.
    """

    # Each successfully downloaded table
    # will be added to this list.
    all_tables = []

    # Count how many requests are expected.
    total_expected_requests = (
        len(stations)
        * len(years)
        * len(VALUE_TYPES)
    )

    completed_requests = 0

    print(
        f"Expected requests: "
        f"{total_expected_requests}"
    )

    # Go through each selected AQO station.
    for station_id, station_information in (
        stations.items()
    ):
        # Separate the city and station name
        # stored inside the dictionary tuple.
        city = station_information[0]
        station_name = station_information[1]

        # Go through every requested year.
        for year in years:

            # Download both value types:
            #
            # daily_4pm
            # daily_max
            for show_day, value_type in (
                VALUE_TYPES.items()
            ):
                completed_requests += 1

                print(
                    f"\nRequest "
                    f"{completed_requests}/"
                    f"{total_expected_requests}"
                )

                print(
                    f"Fetching {station_name} "
                    f"({city}), "
                    f"{year}, "
                    f"{value_type}..."
                )

                try:
                    # Download one station/year/mode table.
                    table = fetch_aqo_year(
                        station_id=station_id,
                        year=year,
                        show_day=show_day,
                    )

                    # Continue to the next request
                    # if no AQHI table was returned.
                    if table.empty:
                        print(
                            "  No AQHI records "
                            "were returned."
                        )

                        continue

                    # Add project and source context
                    # to every row before combining tables.
                    table["city"] = city
                    table["station_name"] = (
                        station_name
                    )
                    table["station_id"] = (
                        station_id
                    )
                    table["requested_year"] = (
                        year
                    )
                    table["value_type"] = (
                        value_type
                    )
                    table["show_day_code"] = (
                        show_day
                    )

                    # Add the completed table
                    # to the list.
                    all_tables.append(
                        table
                    )

                    print(
                        f"  Retrieved "
                        f"{len(table)} rows."
                    )

                except requests.RequestException as error:
                    # A network or HTTP error for one
                    # request should not stop all other
                    # station/year requests.
                    print(
                        f"  Request failed: "
                        f"{error}"
                    )

                except Exception as error:
                    # Catch an unexpected parsing error,
                    # print it, and continue the run.
                    print(
                        f"  Unexpected error: "
                        f"{error}"
                    )

                finally:
                    # Wait after every request, whether
                    # it succeeds or fails.
                    time.sleep(
                        REQUEST_DELAY_SECONDS
                    )

    # Return an empty DataFrame if every
    # request failed or returned no records.
    if not all_tables:
        return pd.DataFrame()

    # Combine all downloaded tables
    # into one DataFrame.
    combined_dataframe = pd.concat(
        all_tables,
        ignore_index=True,
        sort=False,
    )

    return combined_dataframe

def find_possible_daily_max_date_anomalies(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find suspicious daily maximum date patterns.

    The pattern is:
    - A daily_max date appears more than once.
    - The immediately previous calendar date is missing.

    This function only creates a quality report.
    It does not change or delete any raw records.
    """

    # Keep only daily maximum records.
    daily_max_df = dataframe[
        dataframe["value_type"] == "daily_max"
    ].copy()

    # Store all detected problems here.
    anomaly_records = []

    # Check each station and year separately.
    for (
        station_id,
        station_name,
        requested_year,
    ), station_year_df in daily_max_df.groupby(
        [
            "station_id",
            "station_name",
            "requested_year",
        ]
    ):
        # All dates available for this station and year.
        observed_dates = set(
            station_year_df[
                "date"
            ].dropna()
        )

        # Find dates that appear more than once.
        duplicate_date_mask = (
            station_year_df.duplicated(
                subset=["date"],
                keep=False,
            )
        )

        duplicate_dates = (
            station_year_df.loc[
                duplicate_date_mask,
                "date",
            ]
            .dropna()
            .drop_duplicates()
            .sort_values()
        )

        # Inspect every duplicated date.
        for duplicate_date in duplicate_dates:
            previous_date = (
                duplicate_date
                - pd.Timedelta(days=1)
            )

            # Do not compare with a date
            # from a different year.
            if previous_date.year != requested_year:
                continue

            # Continue if the previous date exists.
            if previous_date in observed_dates:
                continue

            rows_for_date = station_year_df[
                station_year_df["date"]
                == duplicate_date
            ]

            # Combine the times into one text value.
            times = " | ".join(
                rows_for_date[
                    "time"
                ]
                .astype(str)
                .tolist()
            )

            # Combine the AQHI values into one text value.
            aqhi_values = " | ".join(
                rows_for_date[
                    "aqhi_raw"
                ]
                .astype(str)
                .tolist()
            )

            anomaly_records.append(
                {
                    "station_id": station_id,
                    "station_name": station_name,
                    "requested_year": requested_year,
                    "missing_previous_date": previous_date,
                    "duplicated_reported_date": duplicate_date,
                    "records_on_duplicated_date": len(
                        rows_for_date
                    ),
                    "reported_times": times,
                    "reported_aqhi_values": aqhi_values,
                    "issue_type": (
                        "possible_date_boundary_anomaly"
                    ),
                }
            )

    return pd.DataFrame(
        anomaly_records
    )


if __name__ == "__main__":
    print(
        "Starting historical AQHI extraction "
        "from Air Quality Ontario..."
    )

    # -----------------------------------------------------
    # SELECT TEST OR FULL RUN
    # -----------------------------------------------------

    if TEST_MODE:
        print(
            "\nTEST MODE is enabled."
        )

        print(
            "Only Barrie 2026 will be downloaded."
        )

        # Test one station.
        stations_to_download = {
            47045: (
                "Barrie",
                "Barrie",
            )
        }

        # Test one year.
        years_to_download = [
            2026
        ]

        output_filename = (
            "aqo_test_barrie_2026.csv"
        )
        anomaly_output_filename = (
            "aqo_test_barrie_2026_anomalies.csv"
        )

    else:
        print(
            "\nFULL MODE is enabled."
        )

        print(
            "All seven stations, three years, "
            "and two AQHI value types "
            "will be downloaded."
        )

        stations_to_download = STATIONS
        years_to_download = YEARS

        output_filename = (
            "aqo_historical_aqhi_"
            "2024_2026.csv"
        )
        anomaly_output_filename = (
        "aqo_daily_max_date_anomalies_"
        "2024_2026.csv"
    )

    # Run the extraction.
    df = fetch_all_aqo_data(
        stations=stations_to_download,
        years=years_to_download,
    )

    print(
        f"\nTotal rows retrieved: "
        f"{len(df)}"
    )

    # Continue only when data was returned.
    if not df.empty:
        print(
            f"Number of columns: "
            f"{len(df.columns)}"
        )

        print("\nColumns returned:")
        print(
            df.columns.tolist()
        )

        print("\nFirst ten rows:")
        print(
            df.head(10).to_string(
                index=False
            )
        )

        # Display the number of rows returned
        # for each station, year, and value type.
        print(
            "\nRows per station, year, "
            "and value type:"
        )

        row_summary = (
            df.groupby(
                [
                    "city",
                    "station_name",
                    "station_id",
                    "requested_year",
                    "value_type",
                ],
                dropna=False,
            )
            .size()
            .reset_index(
                name="row_count"
            )
        )

        print(
            row_summary.to_string(
                index=False
            )
        )

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        print("\nValidation checks")

        print(
            f"Missing city values: "
            f"{df['city'].isna().sum()}"
        )

        print(
            f"Missing station names: "
            f"{df['station_name'].isna().sum()}"
        )

        print(
            f"Missing station IDs: "
            f"{df['station_id'].isna().sum()}"
        )

        print(
            f"Missing requested years: "
            f"{df['requested_year'].isna().sum()}"
        )

        print(
            f"Missing value types: "
            f"{df['value_type'].isna().sum()}"
        )

        # Find the column that contains the date.
        date_column = None

        for column in df.columns:
            if column == "date":
                date_column = column
                break

              # Start with an empty anomaly report.
        #
        # It will be filled only when a valid
        # Date column exists.
        anomaly_report = pd.DataFrame()

        if date_column is not None:
            # Convert the Date column into
            # real pandas datetime values.
            df["date"] = pd.to_datetime(
                df["date"],
                errors="coerce",
            )

           

            # Remove the plus sign only for creating
            # a numeric lower-bound value.
            #
            # For a raw value of 10+, the numeric value
            # becomes 10, but aqhi_is_10_plus remains True
            # to show that the real value may be higher.
                        # Preserve the AQHI value exactly
            # as returned by Air Quality Ontario.
            df["aqhi_raw"] = (
                df["aqhi"]
                .astype("string")
                .str.strip()
            )

            # Mark values reported as 10+.
            df["aqhi_is_10_plus"] = (
                df["aqhi_raw"] == "10+"
            )

            # Create a numeric lower-bound value.
            #
            # Example:
            # "10+" becomes 10,
            # while aqhi_is_10_plus remains True.
            df["aqhi_numeric"] = pd.to_numeric(
                df["aqhi_raw"].str.replace(
                    "+",
                    "",
                    regex=False,
                ),
                errors="coerce",
            )

            # ---------------------------------------------
            # REMOVE THE EMPTY aqhi_1 COLUMN
            # ---------------------------------------------

            if "aqhi_1" in df.columns:
                aqhi_1_non_null = (
                    df["aqhi_1"]
                    .notna()
                    .sum()
                )

                # Drop the column only when every
                # value inside it is empty.
                if aqhi_1_non_null == 0:
                    df = df.drop(
                        columns=["aqhi_1"]
                    )

                    print(
                        "Dropped aqhi_1 because "
                        "it was completely empty."
                    )

                else:
                    print(
                        "Warning: aqhi_1 contains "
                        f"{aqhi_1_non_null} values "
                        "and was not dropped."
                    )

            # ---------------------------------------------
            # DATE VALIDATION
            # ---------------------------------------------

            print(
                "\nUnique dates by station, year, "
                "and value type:"
            )

            unique_date_summary = (
                df.groupby(
                    [
                        "station_name",
                        "requested_year",
                        "value_type",
                    ]
                )["date"]
                .nunique()
                .reset_index(
                    name="unique_date_count"
                )
            )

            print(
                unique_date_summary.to_string(
                    index=False
                )
            )

            print(
                f"\nMissing or invalid dates: "
                f"{df['date'].isna().sum()}"
            )

            print(
                f"Earliest date returned: "
                f"{df['date'].min()}"
            )

            print(
                f"Latest date returned: "
                f"{df['date'].max()}"
            )

            # Check whether each returned date
            # belongs to the requested year.
            valid_dates = df[
                "date"
            ].notna()

            year_mismatches = (
                df.loc[
                    valid_dates,
                    "date",
                ].dt.year
                != df.loc[
                    valid_dates,
                    "requested_year",
                ]
            ).sum()

            print(
                f"Dates outside requested year: "
                f"{year_mismatches}"
            )

            # Count repeated station/date/value-type
            # combinations without deleting them.
            duplicate_daily_records = (
                df.duplicated(
                    subset=[
                        "station_id",
                        "value_type",
                        "date",
                    ]
                ).sum()
            )

            print(
                f"Duplicate station/date/value-type "
                f"records: "
                f"{duplicate_daily_records}"
            )

            # ---------------------------------------------
            # AQHI VALIDATION
            # ---------------------------------------------

            # Rows where AQHI is truly missing.
            missing_aqhi_rows = df[
                df["aqhi_raw"].isna()
            ]

            # Rows where AQHI was reported as 10+.
            capped_aqhi_rows = df[
                df["aqhi_is_10_plus"]
            ]

            print(
                f"Truly missing AQHI values: "
                f"{len(missing_aqhi_rows)}"
            )

            print(
                f"AQHI values reported as 10+: "
                f"{len(capped_aqhi_rows)}"
            )

            if not missing_aqhi_rows.empty:
                print(
                    "\nRows with truly missing AQHI:"
                )

                print(
                    missing_aqhi_rows[
                        [
                            "date",
                            "time",
                            "aqhi_raw",
                            "category",
                            "station_name",
                            "value_type",
                        ]
                    ].to_string(
                        index=False
                    )
                )

            # ---------------------------------------------
            # DAILY MAXIMUM ANOMALY REPORT
            # ---------------------------------------------

            anomaly_report = (
                find_possible_daily_max_date_anomalies(
                    df
                )
            )

            print(
                "\nPossible daily maximum "
                "date-boundary anomalies:"
            )

            print(
                "Number of flagged "
                "station-year dates: "
                f"{len(anomaly_report)}"
            )

            if not anomaly_report.empty:
                print(
                    anomaly_report.to_string(
                        index=False
                    )
                )

        else:
            print(
                "Date column was not found."
            )  


                # -------------------------------------------------
        # SAVE OUTPUT
        # -------------------------------------------------

        # Create the raw data folder if it
        # does not already exist.
        output_folder = Path(
            "data/raw"
        )

        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ---------------------------------------------
        # SAVE THE ANOMALY QUALITY REPORT
        # ---------------------------------------------

        # Save the anomaly report only when
        # suspicious daily maximum patterns were found.
        if not anomaly_report.empty:
            anomaly_output_file = (
                output_folder
                / anomaly_output_filename
            )

            anomaly_report.to_csv(
                anomaly_output_file,
                index=False,
            )

            print(
                f"\nQuality report saved to: "
                f"{anomaly_output_file}"
            )

        else:
            print(
                "\nNo daily maximum anomalies "
                "were found, so no anomaly report "
                "was created."
            )

        # ---------------------------------------------
        # SAVE THE MAIN AQHI DATASET
        # ---------------------------------------------

        output_file = (
            output_folder
            / output_filename
        )

        # Save the complete extracted dataset.
        #
        # index=False prevents pandas from adding
        # an unnecessary row-number column.
        df.to_csv(
            output_file,
            index=False,
        )

        print(
            f"\nMain AQHI data file saved to: "
            f"{output_file}"
        )
    else:
        print(
            "\nNo historical AQHI data "
            "was retrieved."
        )

        print(
            "No output file was created."
        )