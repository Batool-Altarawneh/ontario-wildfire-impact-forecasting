import requests
import pandas as pd


# GeoMet API endpoint that contains realtime AQHI observations
GEOMET_URL = (
    "https://api.weather.gc.ca/"
    "collections/aqhi-observations-realtime/items"
)


# Approximate Ontario bounding box
#
# The order is:
# minimum longitude,
# minimum latitude,
# maximum longitude,
# maximum latitude
ONTARIO_BBOX = "-95.5,41.5,-74.0,57.0"


def fetch_all_aqhi_ontario(
    limit_per_page: int = 500,
) -> pd.DataFrame:
    """
    Download all AQHI observations currently available inside the approximate Ontario bounding box.

    The function uses pagination because the API does not return all records in one request.

    Parameters
    ----------
    limit_per_page:
        Number of records requested in each API call.

    Returns
    -------
    pandas.DataFrame
        A table containing the AQHI observation properties.
    """

    # This list will store the records from every page
    all_records = []

    # Offset tells the API where the current page begins
    offset = 0

    while True:
        # Parameters sent to the GeoMet API
        params = {
            "bbox": ONTARIO_BBOX,
            "limit": limit_per_page,
            "offset": offset,
            "f": "json",
        }

        print(
            f"Requesting AQHI records "
            f"starting at offset {offset}..."
        )

        # Send the request to the API
        response = requests.get(
            GEOMET_URL,
            params=params,
            timeout=60,
        )

        # Print the detailed response if the API rejects the request
        if not response.ok:
            print("\nRequest failed.")
            print(f"Status code: {response.status_code}")
            print("Server response:")
            print(response.text)

        # Stop the program if an HTTP error occurred
        response.raise_for_status()

        # Convert the JSON response into a Python dictionary
        data = response.json()

        # Get the list of GeoJSON features
        #
        # If the response does not contain "features",
        # an empty list will be returned
        features = data.get("features", [])

        # An empty page means there are no more records
        if len(features) == 0:
            break

        # Process every feature in the current page
        for feature in features:
            # The properties section contains fields such as:
            # location_id, location_name_en, aqhi,
            # observation_datetime, and latest
            properties = feature.get("properties", {}).copy()

            # The coordinates are stored inside geometry
            geometry = feature.get("geometry", {})
            coordinates = geometry.get("coordinates", [])

            # GeoJSON coordinates are ordered as:
            # longitude, latitude
            if len(coordinates) >= 2:
                properties["longitude"] = coordinates[0]
                properties["latitude"] = coordinates[1]
            else:
                properties["longitude"] = None
                properties["latitude"] = None

            # Add the record only if properties is not empty
            if properties:
                all_records.append(properties)

        print(
            f"Received {len(features)} records. "
            f"Total so far: {len(all_records)}"
        )

        # numberMatched is the total number of records
        # that match the bounding box
        number_matched = data.get("numberMatched")

        # Move the offset forward by the number of records
        # actually received in this page
        offset += len(features)

        # Stop when all matching records have been retrieved
        if (
            number_matched is not None
            and offset >= number_matched
        ):
            break

        # If the page contains fewer records than requested,
        # it is probably the final page
        if len(features) < limit_per_page:
            break

    # Convert the complete list into a pandas DataFrame
    aqhi_df = pd.DataFrame(all_records)

    return aqhi_df


if __name__ == "__main__":
    print(
        "Downloading all available AQHI observations "
        "inside the Ontario bounding box..."
    )

    # Call the function
    df = fetch_all_aqhi_ontario(
        limit_per_page=500,
    )

    print(f"\nTotal records retrieved: {len(df)}")

    # Continue only if the API returned data
    if not df.empty:
        print(f"Number of columns: {len(df.columns)}")

        print("\nColumns returned:")
        print(df.columns.tolist())

        # Convert the observation timestamp to a real
        # pandas datetime column
        df["observation_datetime"] = pd.to_datetime(
            df["observation_datetime"],
            errors="coerce",
            utc=True,
        )

        # Create a table containing one row per location
        station_columns = [
            "location_id",
            "location_name_en",
            "longitude",
            "latitude",
        ]

        stations = (
            df[station_columns]
            .drop_duplicates()
            .sort_values(
                by="location_name_en",
                na_position="last",
            )
        )

        print("\nDistinct AQHI locations in the bounding box:")
        print(
            stations.to_string(
                index=False,
            )
        )

        # Find the real date coverage of the collection
        earliest_date = df[
            "observation_datetime"
        ].min()

        latest_date = df[
            "observation_datetime"
        ].max()

        print("\nDate coverage")
        print(f"Earliest observation: {earliest_date}")
        print(f"Latest observation:   {latest_date}")

        # Basic validation checks
        print("\nValidation checks")

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
            f"Duplicate observation IDs: "
            f"{df['id'].duplicated().sum()}"
        )

        print(
            f"Number of distinct locations: "
            f"{df['location_id'].nunique()}"
        )

        # Save the station list for review
        output_file = (
            "data/raw/"
            "aqhi_geomet_location_discovery.csv"
        )

        stations.to_csv(
            output_file,
            index=False,
        )

        print(
            f"\nStation discovery file saved to: "
            f"{output_file}"
        )

    else:
        print(
            "\nNo AQHI observations were returned "
            "for the selected bounding box."
        )