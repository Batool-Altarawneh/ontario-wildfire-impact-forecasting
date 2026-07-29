from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

# Existing raw CSV created by the full extraction.
INPUT_FILE = Path(
    "data/raw/aqo_historical_aqhi_2024_2026.csv"
)

# AQO historical AQHI page.
AQO_BASE_URL = (
    "https://www.airqualityontario.com/"
    "aqhi/search.php"
)

# Thunder Bay station information.
STATION_ID = 63200
YEAR = 2025
VALUE_TYPE = "daily_4pm"
SHOW_DAY = 0

# The one conflicting date discovered
# by the quality diagnostic.
TARGET_DATE = "2025-03-25"
TARGET_TIME = "4:00 pm EDT"


def find_results_table(
    tables: list[pd.DataFrame],
) -> pd.DataFrame:
    """
    Find the AQHI results table returned
    by pandas.read_html().
    """

    for table in tables:
        column_text = " ".join(
            str(column).lower()
            for column in table.columns
        )

        if (
            "date" in column_text
            and "aqhi" in column_text
            and "category" in column_text
        ):
            return table.copy()

    return pd.DataFrame()


if __name__ == "__main__":
    print(
        "Starting Thunder Bay conflict diagnosis..."
    )

    # -----------------------------------------------------
    # PART 1: CHECK THE SAVED CSV
    # -----------------------------------------------------

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Input file not found: {INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    saved_conflict_rows = df[
        (df["station_id"] == STATION_ID)
        & (
            df["station_name"]
            == "Thunder Bay"
        )
        & (
            df["requested_year"]
            == YEAR
        )
        & (
            df["value_type"]
            == VALUE_TYPE
        )
        & (
            df["date"]
            == pd.Timestamp(TARGET_DATE)
        )
        & (
            df["time"]
            == TARGET_TIME
        )
    ].copy()

    print(
        "\n========================================"
    )
    print(
        "ROWS SAVED IN THE RAW CSV"
    )
    print(
        "========================================"
    )

    print(
        f"\nRows found: "
        f"{len(saved_conflict_rows)}"
    )

    if saved_conflict_rows.empty:
        print(
            "No matching rows were found "
            "in the saved CSV."
        )

    else:
        print(
            saved_conflict_rows.to_string(
                index=False
            )
        )

        print(
            "\nDistinct AQHI raw values:"
        )

        print(
            saved_conflict_rows[
                "aqhi_raw"
            ].unique()
        )

        print(
            "\nDistinct categories:"
        )

        print(
            saved_conflict_rows[
                "category"
            ].unique()
        )

    # -----------------------------------------------------
    # PART 2: FETCH THE AQO PAGE AGAIN
    # -----------------------------------------------------

    params = {
        "stationid": STATION_ID,
        "show_day": SHOW_DAY,
        "start_day": 1,
        "start_month": 1,
        "start_year": YEAR,
        "submit_search": "Get AQHI values",
    }

    response = requests.get(
        AQO_BASE_URL,
        params=params,
        timeout=60,
    )

    print(
        f"\nRequest URL:\n"
        f"{response.url}"
    )

    response.raise_for_status()

    # Save the exact HTML returned by AQO.
    html_output_file = Path(
        "data/raw/"
        "aqo_thunder_bay_2025_daily_4pm_"
        "conflict_debug.html"
    )

    html_output_file.write_text(
        response.text,
        encoding="utf-8",
    )

    print(
        f"\nRaw HTML saved to: "
        f"{html_output_file}"
    )

    # -----------------------------------------------------
    # PART 3: CHECK PANDAS-PARSED HTML
    # -----------------------------------------------------

    tables = pd.read_html(
        StringIO(
            response.text
        )
    )

    print(
        f"\nNumber of HTML tables found: "
        f"{len(tables)}"
    )

    results_table = find_results_table(
        tables
    )

    print(
        "\n========================================"
    )
    print(
        "PANDAS-PARSED SOURCE ROWS"
    )
    print(
        "========================================"
    )

    if results_table.empty:
        print(
            "AQHI results table could not "
            "be identified."
        )

    else:
        # Convert only for filtering.
        parsed_dates = pd.to_datetime(
            results_table["Date"],
            errors="coerce",
        )

        source_conflict_rows = results_table[
            (parsed_dates == pd.Timestamp(TARGET_DATE))
            & (
                results_table["Time"]
                == TARGET_TIME
            )
        ]

        print(
            f"\nSource rows found: "
            f"{len(source_conflict_rows)}"
        )

        print(
            source_conflict_rows.to_string(
                index=False
            )
        )

    # -----------------------------------------------------
    # PART 4: CHECK ORIGINAL HTML ROWS
    # -----------------------------------------------------

    print(
        "\n========================================"
    )
    print(
        "ORIGINAL RAW HTML ROWS"
    )
    print(
        "========================================"
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    matching_raw_rows = 0

    for table_index, html_table in enumerate(
        soup.find_all("table")
    ):
        for row_index, html_row in enumerate(
            html_table.find_all("tr")
        ):
            cells = html_row.find_all(
                [
                    "th",
                    "td",
                ]
            )

            cell_values = [
                cell.get_text(
                    " ",
                    strip=True,
                )
                for cell in cells
            ]

            row_text = " | ".join(
                cell_values
            )

            if (
                TARGET_DATE in row_text
                and TARGET_TIME in row_text
            ):
                matching_raw_rows += 1

                print(
                    f"\nHTML table: "
                    f"{table_index}"
                )

                print(
                    f"HTML row: "
                    f"{row_index}"
                )

                print(
                    f"Cell values: "
                    f"{cell_values}"
                )

                print(
                    "Raw row HTML:"
                )

                print(
                    str(html_row)
                )

    print(
        f"\nMatching original HTML rows: "
        f"{matching_raw_rows}"
    )

    print(
        "\nThe saved raw dataset was not changed."
    )