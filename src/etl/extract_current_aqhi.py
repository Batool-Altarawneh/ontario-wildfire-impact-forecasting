import requests
import pandas as pd

from pathlib import Path


# ---------------------------------------------------------
# GEOMET API SETTINGS
# ---------------------------------------------------------

# GeoMet API endpoint that contains
# realtime AQHI observations
GEOMET_URL = (
    "https://api.weather.gc.ca/"
    "collections/aqhi-observations-realtime/items"
)


# Approximate Ontario bounding box
#
# GeoJSON and OGC APIs use this coordinate order:
#
# minimum longitude,
# minimum latitude,
# maximum longitude,
# maximum latitude
#
# The bounding box is only used to retrieve the available
# AQHI observations around Ontario.
ONTARIO_BBOX = "-95.5,41.5,-74.0,57.0"


# ---------------------------------------------------------
# PROJECT AQHI LOCATIONS
# ---------------------------------------------------------

# AQHI locations selected for this project
#
# The dictionary key is the location_id returned by GeoMet.
# The dictionary value is the project city name.
#
# Barrie, Kingston, and Thunder Bay each have one location.
#
# Toronto has five locations. We will keep them separate
# during extraction and decide later during EDA whether they
# should be combined into one Toronto-level AQHI value.
SELECTED_LOCATIONS = {
    "FAFFD": "Barrie",
    "FEVJR": "Kingston",
    "FCWFX": "Thunder Bay",
    "FEUZB": "Toronto",
    "FCWYG": "Toronto",
    "FDQBU": "Toronto",
    "FDQBX": "Toronto",
    "FCKTB": "Toronto",
}


def fetch_current_aqhi(
    limit_per_page: int = 500,
) -> pd.DataFrame:
    """
    Download the AQHI observations currently available
    inside the approximate Ontario bounding box.

    The function retrieves all available locations inside
    the bounding box and then keeps only the eight locations
    selected for this project.

    This approach is used because the multi-location CQL2
    filter did not return records for this collection.

    Parameters
    ----------
    limit_per_page:
        Maximum number of records requested from the API
        in each page.

    Returns
    -------
    pandas.DataFrame
        A table containing the AQHI observations for the
        selected project locations.
    """

    # This list will store the selected observations
    # collected from every API page.
    selected_records = []

    # This variable counts all observations returned
    # by the API before filtering by location ID.
    total_api_records = 0

    # Offset tells the API where the current page begins.
    #
    # The first page starts at offset 0.
    offset = 0

    while True:
        # Parameters sent to the GeoMet API.
        params = {
            # Retrieve records inside the approximate
            # Ontario bounding box.
            "bbox": ONTARIO_BBOX,

            # Maximum number of records returned
            # in the current request.
            "limit": limit_per_page,

            # Starting position of the current page.
            "offset": offset,

            # Return the response as GeoJSON.
            "f": "json",
        }

        print(
            f"\nRequesting AQHI records "
            f"starting at offset {offset}..."
        )

        # Send the request to the GeoMet API.
        response = requests.get(
            GEOMET_URL,
            params=params,
            timeout=60,
        )

        # Print the final URL produced by requests.
        #
        # This is useful when debugging API requests.
        print(
            f"Request URL: "
            f"{response.url}"
        )

        # Show the server response before stopping
        # if the request was unsuccessful.
        if not response.ok:
            print("\nRequest failed.")

            print(
                f"Status code: "
                f"{response.status_code}"
            )

            print("Server response:")
            print(response.text)

        # Stop the program if an HTTP error occurred.
        response.raise_for_status()

        # Convert the JSON response into
        # a Python dictionary.
        data = response.json()

        # Get the GeoJSON features.
        #
        # If the response does not contain a features key,
        # an empty list will be returned.
        features = data.get(
            "features",
            [],
        )

        # An empty page means that no more
        # observations are available.
        if len(features) == 0:
            break

        # Add the number of records returned
        # in this page to the API total.
        total_api_records += len(features)

        # Count how many selected records
        # are found in the current page.
        selected_in_current_page = 0

        # Process every observation in the page.
        for feature in features:
            # Get a copy of the properties section.
            #
            # Properties contains fields such as:
            #
            # location_id
            # location_name_en
            # observation_datetime
            # aqhi
            # latest
            properties = feature.get(
                "properties",
                {},
            ).copy()

            # Read the observation's location ID.
            location_id = properties.get(
                "location_id"
            )

            # Ignore locations that are not included
            # in the project's selected location list.
            if location_id not in SELECTED_LOCATIONS:
                continue

            # Get the geometry section.
            geometry = feature.get(
                "geometry",
                {},
            )

            # Get the coordinates from the geometry.
            #
            # GeoJSON stores point coordinates as:
            #
            # longitude, latitude
            coordinates = geometry.get(
                "coordinates",
                [],
            )

            # Add longitude and latitude as regular
            # columns inside the observation record.
            if len(coordinates) >= 2:
                properties["longitude"] = (
                    coordinates[0]
                )

                properties["latitude"] = (
                    coordinates[1]
                )

            else:
                # Use missing values if valid
                # coordinates are unavailable.
                properties["longitude"] = None
                properties["latitude"] = None

            # Add the project city grouping.
            #
            # For example:
            #
            # FCWYG -> Toronto
            # FDQBU -> Toronto
            # FAFFD -> Barrie
            properties["city"] = (
                SELECTED_LOCATIONS.get(
                    location_id
                )
            )

            # Add the completed observation
            # to the selected records list.
            selected_records.append(
                properties
            )

            selected_in_current_page += 1

        print(
            f"Received {len(features)} API records. "
            f"Selected {selected_in_current_page} "
            f"project records."
        )

        print(
            f"Total API records so far: "
            f"{total_api_records}"
        )

        print(
            f"Total selected records so far: "
            f"{len(selected_records)}"
        )

        # numberMatched represents the total number
        # of records matching the bounding box.
        number_matched = data.get(
            "numberMatched"
        )

        # Move the offset forward by the number
        # of API records actually received.
        offset += len(features)

        # Stop when the number of downloaded API records
        # reaches the total reported by the server.
        if (
            number_matched is not None
            and offset >= number_matched
        ):
            break

        # A page containing fewer records than requested
        # is normally the final page.
        if len(features) < limit_per_page:
            break

    # Convert all selected records
    # into a pandas DataFrame.
    aqhi_df = pd.DataFrame(
        selected_records
    )

    return aqhi_df


if __name__ == "__main__":
    print(
        "Downloading current AQHI observations "
        "for the selected project locations..."
    )

    # Run the extraction function.
    df = fetch_current_aqhi(
        limit_per_page=500,
    )

    print(
        f"\nTotal selected records retrieved: "
        f"{len(df)}"
    )

    # Continue with validation and saving
    # only when observations were returned.
    if not df.empty:
        print(
            f"Number of columns: "
            f"{len(df.columns)}"
        )

        print("\nColumns returned:")
        print(
            df.columns.tolist()
        )

        # Convert observation_datetime from text
        # into a real pandas datetime column.
        #
        # utc=True keeps all timestamps in UTC.
        #
        # errors="coerce" changes invalid timestamps
        # into missing datetime values called NaT.
        df["observation_datetime"] = (
            pd.to_datetime(
                df["observation_datetime"],
                errors="coerce",
                utc=True,
            )
        )

        # Sort the final data by observation time,
        # city, and location ID.
        #
        # This makes the saved file easier to inspect.
        df = df.sort_values(
            by=[
                "observation_datetime",
                "city",
                "location_id",
            ]
        ).reset_index(
            drop=True
        )

        # Select useful columns to display
        # in the terminal preview.
        preview_columns = [
            "city",
            "location_id",
            "location_name_en",
            "observation_datetime",
            "aqhi",
            "longitude",
            "latitude",
        ]

        print("\nFirst twenty selected observations:")

        print(
            df[
                preview_columns
            ]
            .head(20)
            .to_string(
                index=False
            )
        )

        # -------------------------------------------------
        # LOCATION SUMMARY
        # -------------------------------------------------

        # Count the number of observations
        # retrieved for each location.
        records_by_location = (
            df.groupby(
                [
                    "city",
                    "location_id",
                    "location_name_en",
                ]
            )
            .size()
            .reset_index(
                name="record_count"
            )
            .sort_values(
                by=[
                    "city",
                    "location_name_en",
                ]
            )
        )

        print("\nRecords by AQHI location:")

        print(
            records_by_location.to_string(
                index=False
            )
        )

        # -------------------------------------------------
        # EXPECTED LOCATION CHECK
        # -------------------------------------------------

        # Get the location IDs actually returned
        # by the API.
        returned_location_ids = set(
            df[
                "location_id"
            ]
            .dropna()
            .unique()
        )

        # Get the eight location IDs expected
        # by this project.
        expected_location_ids = set(
            SELECTED_LOCATIONS.keys()
        )

        # Find expected locations that were not returned.
        missing_location_ids = (
            expected_location_ids
            - returned_location_ids
        )

        # Find unexpected locations.
        #
        # This should be an empty set because the records
        # were filtered using SELECTED_LOCATIONS.
        unexpected_location_ids = (
            returned_location_ids
            - expected_location_ids
        )

        print("\nLocation coverage checks")

        print(
            f"Expected AQHI locations: "
            f"{len(expected_location_ids)}"
        )

        print(
            f"Returned AQHI locations: "
            f"{len(returned_location_ids)}"
        )

        print(
            f"Missing expected location IDs: "
            f"{sorted(missing_location_ids)}"
        )

        print(
            f"Unexpected location IDs: "
            f"{sorted(unexpected_location_ids)}"
        )

        # -------------------------------------------------
        # DATE COVERAGE
        # -------------------------------------------------

        # Find the earliest and latest timestamps
        # available in the selected data.
        earliest_date = df[
            "observation_datetime"
        ].min()

        latest_date = df[
            "observation_datetime"
        ].max()

        print("\nDate coverage")

        print(
            f"Earliest observation: "
            f"{earliest_date}"
        )

        print(
            f"Latest observation:   "
            f"{latest_date}"
        )

        # -------------------------------------------------
        # DATA VALIDATION CHECKS
        # -------------------------------------------------

        print("\nValidation checks")

        print(
            f"Number of rows: "
            f"{len(df)}"
        )

        print(
            f"Number of columns: "
            f"{len(df.columns)}"
        )

        print(
            f"Missing city values: "
            f"{df['city'].isna().sum()}"
        )

        print(
            f"Missing location IDs: "
            f"{df['location_id'].isna().sum()}"
        )

        print(
            f"Missing location names: "
            f"{df['location_name_en'].isna().sum()}"
        )

        print(
            f"Missing AQHI values: "
            f"{df['aqhi'].isna().sum()}"
        )

        print(
            f"Missing observation dates: "
            f"{df['observation_datetime'].isna().sum()}"
        )

        print(
            f"Missing longitude values: "
            f"{df['longitude'].isna().sum()}"
        )

        print(
            f"Missing latitude values: "
            f"{df['latitude'].isna().sum()}"
        )

        # Check duplicated observation IDs.
        #
        # Each GeoMet observation should have
        # a unique ID.
        print(
            f"Duplicate observation IDs: "
            f"{df['id'].duplicated().sum()}"
        )

        # Check duplicated complete rows.
        print(
            f"Duplicate full rows: "
            f"{df.duplicated().sum()}"
        )

        print(
            f"Distinct AQHI locations: "
            f"{df['location_id'].nunique()}"
        )

        print(
            f"Distinct project cities: "
            f"{df['city'].nunique()}"
        )

        # -------------------------------------------------
        # SAVE THE RAW FILE
        # -------------------------------------------------

        # Create the raw-data folder
        # if it does not already exist.
        output_folder = Path(
            "data/raw"
        )

        output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Define the raw output filename.
        output_file = (
            output_folder
            / "aqhi_geomet_current.csv"
        )

        # Save the selected AQHI observations.
        #
        # index=False prevents pandas from creating
        # an extra index column in the CSV file.
        df.to_csv(
            output_file,
            index=False,
        )

        print(
            f"\nFile saved to: "
            f"{output_file}"
        )

    else:
        # Do not create an empty output file
        # when no observations are returned.
        print(
            "\nNo AQHI observations were returned "
            "for the selected project locations."
        )

        print(
            "No output file was created."
        )