from pathlib import Path

import pandas as pd


# ---------------------------------------------------------
# FILE LOCATIONS
# ---------------------------------------------------------

# Historical AQHI data created by the full extraction.
INPUT_FILE = Path(
    "data/raw/aqo_historical_aqhi_2024_2026.csv"
)

# Save diagnostic reports separately.
#
# The raw file will not be changed.
OUTPUT_FOLDER = Path(
    "data/processed/aqo_quality_reports"
)


# ---------------------------------------------------------
# LOAD THE DATA
# ---------------------------------------------------------

def load_aqo_data() -> pd.DataFrame:
    """
    Load the historical AQHI CSV and prepare
    the columns needed for quality checks.
    """

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file was not found: {INPUT_FILE}"
        )

    dataframe = pd.read_csv(
        INPUT_FILE
    )

    # Confirm that the expected columns exist.
    required_columns = [
        "date",
        "time",
        "aqhi_raw",
        "aqhi_numeric",
        "category",
        "city",
        "station_name",
        "station_id",
        "requested_year",
        "value_type",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "The input file is missing these columns: "
            f"{missing_columns}"
        )

    # Convert date into a pandas datetime value.
    dataframe["date"] = pd.to_datetime(
        dataframe["date"],
        errors="coerce",
    )

    # Create the actual year returned by the website.
    dataframe["actual_year"] = (
        dataframe["date"].dt.year
    )

    return dataframe


# ---------------------------------------------------------
# CHECK 1: DATES OUTSIDE REQUESTED YEAR
# ---------------------------------------------------------

def find_year_mismatches(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find rows where the year inside the returned date
    is different from the year requested from AQO.

    Example:
    requested_year = 2024
    actual returned date = 2025-01-01
    """

    year_mismatches = dataframe[
        dataframe["date"].notna()
        & (
            dataframe["actual_year"]
            != dataframe["requested_year"]
        )
    ].copy()

    year_mismatches = year_mismatches.sort_values(
        by=[
            "station_name",
            "requested_year",
            "value_type",
            "date",
            "time",
        ]
    )

    return year_mismatches


# ---------------------------------------------------------
# CHECK 2: THUNDER BAY DAILY 4 PM
# ---------------------------------------------------------

def get_thunder_bay_daily_4pm(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Keep only Thunder Bay daily 4:00 PM records
    for 2024 and 2025.

    These are the two station-years with
    unexpectedly high row counts.
    """

    thunder_bay = dataframe[
        (dataframe["station_id"] == 63200)
        & (
            dataframe["station_name"]
            == "Thunder Bay"
        )
        & (
            dataframe["value_type"]
            == "daily_4pm"
        )
        & (
            dataframe["requested_year"].isin(
                [2024, 2025]
            )
        )
    ].copy()

    thunder_bay = thunder_bay.sort_values(
        by=[
            "requested_year",
            "date",
            "time",
        ]
    )

    return thunder_bay


def create_thunder_bay_year_summary(
    thunder_bay: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare total rows with unique dates.

    extra_rows shows how many records exist beyond
    the expected one-row-per-date structure.
    """

    summary = (
        thunder_bay.groupby(
            "requested_year"
        )
        .agg(
            row_count=(
                "date",
                "size",
            ),
            unique_date_count=(
                "date",
                "nunique",
            ),
            unique_time_count=(
                "time",
                "nunique",
            ),
            earliest_date=(
                "date",
                "min",
            ),
            latest_date=(
                "date",
                "max",
            ),
        )
        .reset_index()
    )

    summary["extra_rows"] = (
        summary["row_count"]
        - summary["unique_date_count"]
    )

    return summary


def find_thunder_bay_duplicate_dates(
    thunder_bay: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Find dates that appear more than once.

    Returns
    -------
    duplicate_date_summary:
        One row per repeated date, showing how many
        records and distinct values it contains.

    duplicate_rows:
        The actual individual records belonging
        to those repeated dates.
    """

    duplicate_date_summary = (
        thunder_bay.groupby(
            [
                "requested_year",
                "date",
            ]
        )
        .agg(
            record_count=(
                "date",
                "size",
            ),
            distinct_times=(
                "time",
                "nunique",
            ),
            distinct_aqhi_values=(
                "aqhi_raw",
                "nunique",
            ),
            distinct_categories=(
                "category",
                "nunique",
            ),
        )
        .reset_index()
    )

    # Keep only dates with more than one record.
    duplicate_date_summary = (
        duplicate_date_summary[
            duplicate_date_summary[
                "record_count"
            ] > 1
        ]
        .sort_values(
            by=[
                "requested_year",
                "date",
            ]
        )
    )

    duplicate_rows = thunder_bay.merge(
        duplicate_date_summary[
            [
                "requested_year",
                "date",
                "record_count",
                "distinct_times",
                "distinct_aqhi_values",
            ]
        ],
        on=[
            "requested_year",
            "date",
        ],
        how="inner",
    )

    duplicate_rows = duplicate_rows.sort_values(
        by=[
            "requested_year",
            "date",
            "time",
            "aqhi_raw",
        ]
    )

    return (
        duplicate_date_summary,
        duplicate_rows,
    )


def create_thunder_bay_time_summary(
    thunder_bay: pd.DataFrame,
) -> pd.DataFrame:
    """
    Count the time values returned in daily_4pm mode.

    Ideally, this mode should contain only a
    4:00 PM time value.
    """

    time_summary = (
        thunder_bay.groupby(
            [
                "requested_year",
                "time",
            ],
            dropna=False,
        )
        .size()
        .reset_index(
            name="row_count"
        )
        .sort_values(
            by=[
                "requested_year",
                "row_count",
            ],
            ascending=[
                True,
                False,
            ],
        )
    )

    return time_summary


def find_exact_duplicate_rows(
    thunder_bay: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find rows that are completely identical
    across the important source fields.
    """

    duplicate_columns = [
        "date",
        "time",
        "aqhi_raw",
        "aqhi_numeric",
        "category",
        "station_id",
        "requested_year",
        "value_type",
    ]

    exact_duplicate_mask = (
        thunder_bay.duplicated(
            subset=duplicate_columns,
            keep=False,
        )
    )

    exact_duplicate_rows = thunder_bay[
        exact_duplicate_mask
    ].sort_values(
        by=[
            "requested_year",
            "date",
            "time",
        ]
    )

    return exact_duplicate_rows


def find_same_datetime_conflicts(
    thunder_bay: pd.DataFrame,
) -> pd.DataFrame:
    """
    Find cases where the same date and time appear
    more than once but contain different AQHI values.

    This would be more serious than simple identical
    duplicate rows.
    """

    datetime_summary = (
        thunder_bay.groupby(
            [
                "requested_year",
                "date",
                "time",
            ],
            dropna=False,
        )
        .agg(
            record_count=(
                "date",
                "size",
            ),
            distinct_aqhi_values=(
                "aqhi_raw",
                "nunique",
            ),
            distinct_categories=(
                "category",
                "nunique",
            ),
        )
        .reset_index()
    )

    conflicts = datetime_summary[
        (
            datetime_summary["record_count"] > 1
        )
        & (
            datetime_summary[
                "distinct_aqhi_values"
            ] > 1
        )
    ].copy()

    return conflicts


# ---------------------------------------------------------
# MAIN PROGRAM
# ---------------------------------------------------------

if __name__ == "__main__":
    print(
        "Starting AQO historical quality diagnosis..."
    )

    df = load_aqo_data()

    print(
        f"\nRows loaded: {len(df)}"
    )

    OUTPUT_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -----------------------------------------------------
    # YEAR MISMATCH REPORT
    # -----------------------------------------------------

    year_mismatches = find_year_mismatches(
        df
    )

    print(
        "\n========================================"
    )
    print(
        "DATES OUTSIDE REQUESTED YEAR"
    )
    print(
        "========================================"
    )

    print(
        f"\nYear mismatch rows: "
        f"{len(year_mismatches)}"
    )

    if not year_mismatches.empty:
        year_mismatch_columns = [
            "station_name",
            "station_id",
            "requested_year",
            "actual_year",
            "date",
            "time",
            "aqhi_raw",
            "category",
            "value_type",
        ]

        print(
            year_mismatches[
                year_mismatch_columns
            ].to_string(
                index=False
            )
        )

        year_mismatch_file = (
            OUTPUT_FOLDER
            / "aqo_year_mismatch_rows.csv"
        )

        year_mismatches.to_csv(
            year_mismatch_file,
            index=False,
        )

        print(
            f"\nSaved to: "
            f"{year_mismatch_file}"
        )

    # -----------------------------------------------------
    # THUNDER BAY REPORT
    # -----------------------------------------------------

    thunder_bay = get_thunder_bay_daily_4pm(
        df
    )

    thunder_year_summary = (
        create_thunder_bay_year_summary(
            thunder_bay
        )
    )

    (
        thunder_duplicate_summary,
        thunder_duplicate_rows,
    ) = find_thunder_bay_duplicate_dates(
        thunder_bay
    )

    thunder_time_summary = (
        create_thunder_bay_time_summary(
            thunder_bay
        )
    )

    exact_duplicate_rows = (
        find_exact_duplicate_rows(
            thunder_bay
        )
    )

    datetime_conflicts = (
        find_same_datetime_conflicts(
            thunder_bay
        )
    )

    print(
        "\n========================================"
    )
    print(
        "THUNDER BAY DAILY 4 PM DIAGNOSTIC"
    )
    print(
        "========================================"
    )

    print(
        "\nYear summary:"
    )

    print(
        thunder_year_summary.to_string(
            index=False
        )
    )

    print(
        f"\nDates appearing more than once: "
        f"{len(thunder_duplicate_summary)}"
    )

    print(
        f"Rows belonging to repeated dates: "
        f"{len(thunder_duplicate_rows)}"
    )

    print(
        f"Completely identical duplicate rows: "
        f"{len(exact_duplicate_rows)}"
    )

    print(
        "Same date/time combinations with "
        f"different AQHI values: "
        f"{len(datetime_conflicts)}"
    )

    print(
        "\nTime values returned in daily_4pm mode:"
    )

    print(
        thunder_time_summary.to_string(
            index=False
        )
    )

    print(
        "\nFirst 60 rows belonging to "
        "repeated Thunder Bay dates:"
    )

    print(
        thunder_duplicate_rows[
            [
                "requested_year",
                "date",
                "time",
                "aqhi_raw",
                "aqhi_numeric",
                "category",
                "record_count",
                "distinct_times",
                "distinct_aqhi_values",
            ]
        ]
        .head(60)
        .to_string(
            index=False
        )
    )

    if not datetime_conflicts.empty:
        print(
            "\nSame date/time records with "
            "different AQHI values:"
        )

        print(
            datetime_conflicts.to_string(
                index=False
            )
        )

    # -----------------------------------------------------
    # SAVE THUNDER BAY REPORTS
    # -----------------------------------------------------

    thunder_year_summary.to_csv(
        OUTPUT_FOLDER
        / "thunder_bay_daily_4pm_year_summary.csv",
        index=False,
    )

    thunder_duplicate_summary.to_csv(
        OUTPUT_FOLDER
        / "thunder_bay_daily_4pm_duplicate_dates.csv",
        index=False,
    )

    thunder_duplicate_rows.to_csv(
        OUTPUT_FOLDER
        / "thunder_bay_daily_4pm_duplicate_rows.csv",
        index=False,
    )

    thunder_time_summary.to_csv(
        OUTPUT_FOLDER
        / "thunder_bay_daily_4pm_time_summary.csv",
        index=False,
    )

    exact_duplicate_rows.to_csv(
        OUTPUT_FOLDER
        / "thunder_bay_daily_4pm_exact_duplicates.csv",
        index=False,
    )

    datetime_conflicts.to_csv(
        OUTPUT_FOLDER
        / "thunder_bay_daily_4pm_datetime_conflicts.csv",
        index=False,
    )

    print(
        f"\nAll diagnostic reports saved to: "
        f"{OUTPUT_FOLDER}"
    )

    print(
        "\nThe raw AQHI dataset was not changed."
    )