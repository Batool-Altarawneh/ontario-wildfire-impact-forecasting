from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------
# AIR QUALITY ONTARIO SETTINGS
# ---------------------------------------------------------

# Historical AQHI search webpage.
AQO_BASE_URL = (
    "https://www.airqualityontario.com/"
    "aqhi/search.php"
)


# Barrie station ID.
STATION_ID = 47045


# Year being investigated.
YEAR = 2026


# show_day = 2 requests daily maximum AQHI values.
SHOW_DAY = 2


# Dates around the first suspicious duplicate window.
#
# We include dates before and after the problem
# so we can understand the surrounding pattern.
TARGET_DATES = [
    "2026-01-30",
    "2026-01-31",
    "2026-02-01",
    "2026-02-02",
    "2026-02-03",
    "2026-02-04",
]


def find_pandas_results_table(
    tables: list[pd.DataFrame],
) -> tuple[int | None, pd.DataFrame]:
    """
    Find the AQHI results table from the tables
    returned by pandas.read_html().

    The correct table should contain columns related
    to Date, AQHI, and Category.

    Returns
    -------
    tuple
        The table index and the selected DataFrame.

        If no matching table is found, the index is None
        and the DataFrame is empty.
    """

    for table_index, table in enumerate(tables):

        # Combine the column names into one lowercase
        # text value for easier checking.
        column_text = " ".join(
            str(column).lower()
            for column in table.columns
        )

        has_date = "date" in column_text
        has_aqhi = "aqhi" in column_text
        has_category = "category" in column_text

        if (
            has_date
            and has_aqhi
            and has_category
        ):
            return table_index, table.copy()

    return None, pd.DataFrame()


def row_contains_target_date(
    row_text: str,
) -> bool:
    """
    Check whether text contains one of the dates
    being investigated.
    """

    return any(
        target_date in row_text
        for target_date in TARGET_DATES
    )




if __name__ == "__main__":
    print(
        "Downloading Barrie 2026 daily maximum "
        "AQHI HTML for diagnosis..."
    )

    # Parameters copied from the manually tested
    # Air Quality Ontario search form.
    params = {
        "stationid": STATION_ID,
        "show_day": SHOW_DAY,
        "start_day": 1,
        "start_month": 1,
        "start_year": YEAR,
        "submit_search": "Get AQHI values",
    }

    # Send the request.
    response = requests.get(
        AQO_BASE_URL,
        params=params,
        timeout=60,
    )

    print(
        f"\nRequest URL:\n"
        f"{response.url}"
    )

    # Show the server response if the request fails.
    if not response.ok:
        print("\nRequest failed.")
        print(
            f"Status code: "
            f"{response.status_code}"
        )
        print("Server response:")
        print(response.text)

    response.raise_for_status()

    # -----------------------------------------------------
    # SAVE THE ORIGINAL HTML
    # -----------------------------------------------------

    # Save the exact page returned by the website.
    #
    # This lets us open the page later and inspect
    # the original HTML manually if needed.
    output_folder = Path(
        "data/raw"
    )

    output_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    html_output_file = (
        output_folder
        / "aqo_barrie_2026_daily_max_debug.html"
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
    # PART 1: INSPECT PANDAS.READ_HTML OUTPUT
    # -----------------------------------------------------

    print(
        "\n========================================"
    )
    print(
        "PANDAS.READ_HTML DIAGNOSTIC"
    )
    print(
        "========================================"
    )

    try:
        # Read every HTML table found on the page.
        tables = pd.read_html(
            StringIO(
                response.text
            )
        )

    except ValueError:
        print(
            "No HTML tables were found."
        )

        tables = []

    print(
        f"\nNumber of tables found by pandas: "
        f"{len(tables)}"
    )

    # Display the structure of every parsed table.
    for table_index, table in enumerate(tables):
        print(
            f"\n--- Pandas table "
            f"{table_index} ---"
        )

        print(
            f"Shape: "
            f"{table.shape}"
        )

        print(
            f"Columns: "
            f"{table.columns.tolist()}"
        )

        print("First three rows:")

        print(
            table.head(3).to_string(
                index=False
            )
        )

    # Automatically locate the AQHI results table.
    results_table_index, results_table = (
        find_pandas_results_table(
            tables
        )
    )

    if results_table.empty:
        print(
            "\nPandas could not identify "
            "the AQHI results table."
        )

    else:
        print(
            f"\nAQHI results table selected: "
            f"{results_table_index}"
        )

        print(
            "\nPandas-parsed rows around "
            "January 30 to February 4:"
        )

        pandas_rows_found = 0

        # Inspect rows before applying any cleaning,
        # datetime conversion, or duplicate removal.
        for row_index, row in (
            results_table.iterrows()
        ):
            row_text = " | ".join(
                str(value)
                for value in row.tolist()
            )

            if row_contains_target_date(
                row_text
            ):
                pandas_rows_found += 1

                print(
                    f"\nPandas row index: "
                    f"{row_index}"
                )

                print(
                    row.to_dict()
                )

        if pandas_rows_found == 0:
            print(
                "No matching dates were found "
                "in the pandas table."
            )

    # -----------------------------------------------------
    # PART 2: INSPECT THE ORIGINAL HTML ROWS
    # -----------------------------------------------------

    print(
        "\n========================================"
    )
    print(
        "RAW HTML ROW DIAGNOSTIC"
    )
    print(
        "========================================"
    )

    # Parse the original HTML without using pandas.
    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    html_tables = soup.find_all(
        "table"
    )

    print(
        f"\nNumber of raw HTML tables found: "
        f"{len(html_tables)}"
    )

    matching_html_rows = 0

    # Inspect every raw HTML table and every row.
    for table_index, html_table in enumerate(
        html_tables
    ):
        # Get all rows inside the current HTML table.
        html_rows = html_table.find_all(
            "tr"
        )

        print(
            f"\nRaw HTML table {table_index}: "
            f"{len(html_rows)} rows"
        )

        for row_index, html_row in enumerate(
            html_rows
        ):
            # Get every table-header or table-data cell.
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

            # Continue unless this row contains
            # one of the suspicious dates.
            if not row_contains_target_date(
                row_text
            ):
                continue

            matching_html_rows += 1

            # Extract every link stored inside the row.
            links = []

            for link in html_row.find_all(
                "a"
            ):
                links.append(
                    {
                        "text": link.get_text(
                            " ",
                            strip=True,
                        ),
                        "href": link.get(
                            "href"
                        ),
                    }
                )

            print(
                f"\nRaw HTML table: "
                f"{table_index}"
            )

            print(
                f"Raw HTML row: "
                f"{row_index}"
            )

            print(
                f"Cell values: "
                f"{cell_values}"
            )

            print(
                f"Links: "
                f"{links}"
            )

    if matching_html_rows == 0:
        print(
            "\nNo matching dates were found "
            "in the raw HTML rows."
        )

    # -----------------------------------------------------
    # INTERPRETATION GUIDE
    # -----------------------------------------------------

    print(
        "\n========================================"
    )
    print(
        "HOW TO INTERPRET THE RESULT"
    )
    print(
        "========================================"
    )

    print(
        "\n1. If the duplicate February 2 rows "
        "appear in both the raw HTML and pandas, "
        "the issue comes from the website output, "
        "not from our cleanup code."
    )

    print(
        "\n2. If the raw HTML has one row but pandas "
        "creates two rows, the problem comes from "
        "pandas.read_html parsing."
    )

    print(
        "\n3. If both rows display February 2 but "
        "their href links contain different dates, "
        "the link may reveal the true reporting date."
    )

    print(
        "\n4. Do not shift or remove any dates until "
        "the raw HTML and link values confirm the rule."
    )