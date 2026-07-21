import requests
import pandas as pd

from datetime import datetime
from pathlib import Path


# URL for the public CWFIS Web Feature Service
CWFIS_WFS_URL = (
    "https://cwfis.cfs.nrcan.gc.ca/geoserver/public/wfs"
)


# Name of the CWFIS layer that contains hotspot records
HOTSPOT_LAYER = "public:hotspots"


# Approximate geographic boundaries of Ontario
# These values include a small buffer around the province
ONTARIO_BBOX = {
    "min_lat": 41.5,
    "max_lat": 57.0,
    "min_lon": -95.5,
    "max_lon": -74.0,
}


def check_date_format(date_text: str) -> datetime:
    """
    Check that a date is written in YYYY-MM-DD format.

    The function returns the date as a datetime object
    if the format is correct.
    """

    try:
        return datetime.strptime(date_text, "%Y-%m-%d")

    except ValueError as error:
        raise ValueError(
            f"Invalid date: {date_text}. "
            "Please use YYYY-MM-DD format."
        ) from error


def fetch_cwfis_hotspots(
    start_date: str,
    end_date: str,
    page_size: int = 5000,
) -> pd.DataFrame:
    """
    Download CWFIS hotspot records located within the approximate Ontario bounding box.

    The bounding box may also include some locations outside Ontario because the province has an irregular geographic shape.

    Parameters
    ----------
    start_date:
        First date to include, written as YYYY-MM-DD.

    end_date:
        Last date to include, written as YYYY-MM-DD.

    page_size:
        Number of records requested from the server in each request.

    Returns
    -------
    pandas.DataFrame
        A table containing the hotspot properties.
    """

    # Check that both dates have the correct format
    start_datetime = check_date_format(start_date)
    end_datetime = check_date_format(end_date)

    # The start date should not be after the end date
    if start_datetime > end_datetime:
        raise ValueError(
            "The start date cannot be after the end date."
        )

    # Build the filter that will be sent to CWFIS
    #
    # The first two conditions filter the records by date.
    # The remaining conditions keep only locations
    # inside the approximate Ontario bounding box.
    cql_filter = (
        f"rep_date >= {start_date}T00:00:00Z AND "
        f"rep_date <= {end_date}T23:59:59Z AND "
        f"lat >= {ONTARIO_BBOX['min_lat']} AND "
        f"lat <= {ONTARIO_BBOX['max_lat']} AND "
        f"lon >= {ONTARIO_BBOX['min_lon']} AND "
        f"lon <= {ONTARIO_BBOX['max_lon']}"
)

    # This list will store records from all pages
    all_records = []

    # startIndex tells the server where each page begins
    start_index = 0

    while True:
        # Parameters sent with the WFS request
        params = {
              "service": "WFS",
              "version": "2.0.0",
              "request": "GetFeature",
              "typeNames": HOTSPOT_LAYER,
              "outputFormat": "application/json",
              "cql_filter": cql_filter,

    # Number of records returned in one request
    "count": page_size,

    # Starting position for the current page
    "startIndex": start_index,

    # GeoServer needs a fixed order when pagination is used.
    # A means ascending order.
    # Records are ordered first by date, then latitude,
    # and finally longitude.
    "sortBy": "rep_date A,uid A",
        }

        print(
            f"Requesting records starting at "
            f"index {start_index}..."
        )

        # Send the request to the CWFIS server
        response = requests.get(
            CWFIS_WFS_URL,
            params=params,
            timeout=60,
        )

        # If the server rejects the request, print its detailed message before stopping the program.
        if not response.ok:
            print("\nRequest failed.")
            print(f"Status code: {response.status_code}")
            print("Server response:")
            print(response.text)

        response.raise_for_status()

        # Convert the JSON response to a Python dictionary
        data = response.json()

        # Get the GeoJSON features
        #
        # Using .get() is safer than data["features"]
        # because it returns an empty list if the key is missing
        features = data.get("features", [])

        # An empty page means there are no more records
        if len(features) == 0:
            break

        # Go through every hotspot returned in this page
        for feature in features:
            # The properties section contains the actual fields
            # such as rep_date, lat, lon, temp, ws, and fwi
            properties = feature.get("properties", {})

            # Add the record only if properties is not empty
            if properties:
                all_records.append(properties)

        print(
            f"Received {len(features)} records. "
            f"Total so far: {len(all_records)}"
        )

        if len(features) < page_size:
            break

        # Move the starting position to the next page
        start_index += len(features)

    # Convert the complete list of records to a DataFrame
    hotspots_df = pd.DataFrame(all_records)

    return hotspots_df


if __name__ == "__main__":

    start_date = "2026-01-01"

   
    end_date = "2026-07-20"

    print(
        f"Downloading CWFIS hotspots from "
        f"{start_date} to {end_date}..."
    )

    # Call the extraction function
    df = fetch_cwfis_hotspots(
        start_date=start_date,
        end_date=end_date,
        page_size=5000,
    )

    print(f"\nRetrieved {len(df)} hotspot records.")

    # Show the first five records
    if not df.empty:
        print("\nFirst five records:")
        print(df.head())

        print("\nColumns returned:")
        print(df.columns.tolist())

        # Basic validation checks
        print("\nValidation checks")

        print(f"Number of rows: {len(df)}")
        print(f"Number of columns: {len(df.columns)}")

        print(f"Earliest date: {df['rep_date'].min()}")
        print(f"Latest date: {df['rep_date'].max()}")

        print(f"Minimum latitude: {df['lat'].min()}")
        print(f"Maximum latitude: {df['lat'].max()}")

        print(f"Minimum longitude: {df['lon'].min()}")
        print(f"Maximum longitude: {df['lon'].max()}")

        print(
            f"Missing latitude values: "
            f"{df['lat'].isna().sum()}"
        )

        print(
            f"Missing longitude values: "
            f"{df['lon'].isna().sum()}"
        )

        print(
            f"Missing report dates: "
            f"{df['rep_date'].isna().sum()}"
        )

        print(
            f"Duplicate full rows: "
            f"{df.duplicated().sum()}"
        )

        print(
            f"Duplicate UID values: "
            f"{df['uid'].duplicated().sum()}"
        )

        print(
            f"Unique UID values: "
            f"{df['uid'].nunique()}"
        )



    else:
        print(
            "\nNo hotspot records were returned "
            "for this date range and location."
        )

    # Create the raw-data folder if it does not exist
    output_folder = Path("data/raw")
    output_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Include the date range in the filename
    # so each extraction is easy to identify
    output_file = output_folder / (
        f"cwfis_hotspots_ontario_bbox_"
        f"{start_date}_to_{end_date}.csv"
    )

    # Save the raw records without the pandas index column
    df.to_csv(
        output_file,
        index=False,
    )

    print(f"\nFile saved to: {output_file}")