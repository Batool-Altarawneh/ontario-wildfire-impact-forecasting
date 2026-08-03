"""
OWF-26 - Extract Ontario active fire data

This script:
1. Downloads all fire records from the Ontario ArcGIS REST service.
2. Uses pagination so no records are missed.
3. Preserves the original source fields.
4. Creates separate cleaned and interpreted columns.
5. Logs every distinct status, cause, and response code.
6. Saves raw, cleaned, active-only, and quality-report files.

Important:
- Stage-of-control codes are treated as confirmed.
- Fire-cause and response-type interpretations remain provisional.
- The script does not replace or delete the original source fields.
"""

import requests
import pandas as pd

from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------
# 1. SOURCE SETTINGS
# ---------------------------------------------------------------------

# ArcGIS REST query endpoint for Ontario fire records.
ARCGIS_URL = (
    "https://ws.lioservices.lrc.gov.on.ca/arcgis1061a/rest/services/"
    "MNRF/Ontario_Fires_Map/MapServer/0/query"
)

# The service supports up to 5,000 records per request.
# I use 2,000 to keep each request smaller and easier to troubleshoot.
PAGE_SIZE = 2000

# Request timeout in seconds.
REQUEST_TIMEOUT_SECONDS = 60


# ---------------------------------------------------------------------
# 2. CODE MAPPINGS
# ---------------------------------------------------------------------

# These stage-of-control meanings were confirmed from official
# CWFIS / CIFFC documentation.
STAGE_OF_CONTROL_LABELS = {
    "OC": "Out of Control",
    "BH": "Being Held",
    "UC": "Under Control",
    "EX": "Out (Extinguished)",
}

# BM appeared frequently in the Ontario data.
# It is likely "Being Monitored", but the exact code meaning
# has not been confirmed in published documentation.
STAGE_OF_CONTROL_LABELS_PROVISIONAL = {
    "BM": "Being Monitored (provisional, unconfirmed code)",
}

# Include BM provisionally so likely ongoing fires are not excluded.
ACTIVE_STAGE_CODES = {"OC", "BH", "UC", "BM"}

## Confirmed via CIFFC's official "Stages of Control & Response Types" PDF.

RESPONSE_TYPE_LABELS = {
    "FUL": "Full Response",
    "MOD": "Modified Response",
    "MON": "Monitored Response",
}

# The national catalogue documents these broad cause categories.
# Ontario returned "L" in the live data, so the script logs values
# outside this documented set instead of forcing them into a category.
DOCUMENTED_NATIONAL_CAUSE_CODES = {"H", "N", "U"}

# These fields contained -1 in the sample data.
# The source does not clearly document the meaning of -1, so the script
# adds flags instead of silently changing the original values.
SENTINEL_FIELDS = [
    "FIELD_LOCATION",
    "FIELD_PERCENT_CONTAINED",
    "FIELD_SEVERITY_NEAREST_DSR",
    "FIELD_AGENCY_PREPARE_LEVEL",
    "FIELD_FIRE_TYPE_ICS",
]


# ---------------------------------------------------------------------
# 3. SMALL HELPER FUNCTIONS
# ---------------------------------------------------------------------

def clean_text_column(series):
    """
    Convert a pandas column to text and remove extra spaces.

    The original source column is not changed.
    This helper is only used when creating new cleaned columns.
    """
    return series.astype("string").str.strip()


def convert_epoch_ms_to_utc(value):
    """
    Convert one Unix timestamp from milliseconds to a UTC datetime.

    Example source value:
        1785449040000

    If the value is missing or invalid, pandas returns NaT.
    """
    return pd.to_datetime(value, unit="ms", utc=True, errors="coerce")


# ---------------------------------------------------------------------
# 4. DOWNLOAD THE DATA
# ---------------------------------------------------------------------

def fetch_all_fire_records():
    """
    Download all records from the Ontario ArcGIS REST service.

    ArcGIS may return only part of the result in one response.
    The script uses resultOffset to request the next page.

    Returns:
        pandas DataFrame containing all downloaded records.
    """

    all_records = []
    offset = 0

    # Add the same download time to every row in this snapshot.
    downloaded_at_utc = datetime.now(timezone.utc).isoformat()

    while True:
        print(f"Requesting records starting at offset {offset}...")

        # These parameters are sent to the ArcGIS REST service.
        params = {
            "where": "1=1",                 # Return every record.
            "outFields": "*",               # Return every attribute field.
            "returnGeometry": "true",       # Include point coordinates.
            "outSR": 4326,                  # Return longitude/latitude coordinates.
            "f": "geojson",                 # Request GeoJSON output.
            "resultRecordCount": PAGE_SIZE,
            "resultOffset": offset,
            "orderByFields": "OBJECTID ASC" # Keep pagination in a stable order.
        }

        try:
            response = requests.get(
                ARCGIS_URL,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            # Raise an error for HTTP responses such as 404 or 500.
            response.raise_for_status()

            data = response.json()

        except requests.RequestException as error:
            raise RuntimeError(
                f"The Ontario fire-data request failed at offset {offset}."
            ) from error

        except ValueError as error:
            raise RuntimeError(
                "The service response could not be read as JSON."
            ) from error

        # ArcGIS may return an error message inside a successful HTTP response.
        if "error" in data:
            raise RuntimeError(f"ArcGIS returned an error: {data['error']}")

        features = data.get("features", [])

        # If there are no features, there is nothing else to download.
        if len(features) == 0:
            print("No more records were returned.")
            break

        # Each feature contains:
        # - properties: the fire attributes
        # - geometry: the point coordinates
        for feature in features:
            properties = feature.get("properties", {}).copy()
            geometry = feature.get("geometry") or {}
            coordinates = geometry.get("coordinates") or []

            # GeoJSON coordinate order is longitude first, then latitude.
            if len(coordinates) >= 2:
                properties["geometry_longitude"] = coordinates[0]
                properties["geometry_latitude"] = coordinates[1]
            else:
                properties["geometry_longitude"] = None
                properties["geometry_latitude"] = None

            # Keep extra source and snapshot information.
            properties["source_feature_id"] = feature.get("id")
            properties["geometry_type"] = geometry.get("type")
            properties["snapshot_downloaded_at_utc"] = downloaded_at_utc
            properties["source_url"] = ARCGIS_URL

            all_records.append(properties)

        print(
            f"Received {len(features)} records. "
            f"Total downloaded so far: {len(all_records)}"
        )

        # ArcGIS uses this flag to tell us whether more records exist.
        more_records_exist = data.get("exceededTransferLimit", False)

        if not more_records_exist:
            print("The service reports that the final page was reached.")
            break

        # Move the offset forward by the number of records received.
        offset += len(features)

    return pd.DataFrame(all_records)


# ---------------------------------------------------------------------
# 5. CREATE CLEANED AND INTERPRETED COLUMNS
# ---------------------------------------------------------------------

def build_cleaned_dataset(raw_df):
    """
    Create analysis-friendly columns without overwriting source columns.

    The returned DataFrame still contains every original FIELD_* column.
    New columns are added for cleaned text, readable dates, labels,
    active-fire flags, provisional interpretations, and quality flags.
    """

    cleaned_df = raw_df.copy()

    # -------------------------------------------------------------
    # A. Clean important text fields
    # -------------------------------------------------------------

    if "FIELD_AGENCY_FIRE_ID" in cleaned_df.columns:
        cleaned_df["fire_id"] = clean_text_column(
            cleaned_df["FIELD_AGENCY_FIRE_ID"]
        )

    if "FIELD_AGENCY_CODE" in cleaned_df.columns:
        cleaned_df["agency_code"] = clean_text_column(
            cleaned_df["FIELD_AGENCY_CODE"]
        )

    if "FIELD_STAGE_OF_CONTROL_STATUS" in cleaned_df.columns:
        cleaned_df["stage_of_control_code"] = clean_text_column(
            cleaned_df["FIELD_STAGE_OF_CONTROL_STATUS"]
        )

        # Add a label only for the officially confirmed status codes.
        cleaned_df["stage_of_control_label"] = (
            cleaned_df["stage_of_control_code"]
            .map(STAGE_OF_CONTROL_LABELS)
        )

        # Add a separate label for provisional status codes such as BM.
        cleaned_df["stage_of_control_label_provisional"] = (
            cleaned_df["stage_of_control_code"]
            .map(STAGE_OF_CONTROL_LABELS_PROVISIONAL)
        )

        # Show whether the mapping is confirmed, provisional, or unknown.
        cleaned_df["stage_of_control_mapping_status"] = "Unmapped"

        confirmed_mask = cleaned_df["stage_of_control_label"].notna()
        provisional_mask = (
            cleaned_df["stage_of_control_label_provisional"].notna()
        )

        cleaned_df.loc[
            confirmed_mask,
            "stage_of_control_mapping_status",
        ] = "Confirmed"

        cleaned_df.loc[
            provisional_mask,
            "stage_of_control_mapping_status",
        ] = "Provisional"

        # Create one convenient display label.
        # Use the confirmed label first.
        # If it is missing, use the provisional label.
        # If both are missing, show Unmapped.
        cleaned_df["stage_of_control_display_label"] = (
            cleaned_df["stage_of_control_label"]
            .fillna(cleaned_df["stage_of_control_label_provisional"])
            .fillna("Unmapped")
        )

        # BM is included provisionally in the active-fire output.
        cleaned_df["is_active_fire"] = (
            cleaned_df["stage_of_control_code"]
            .isin(ACTIVE_STAGE_CODES)
        )

    if "FIELD_AGENCY_FIRE_CAUSE" in cleaned_df.columns:
        cleaned_df["agency_fire_cause_code"] = clean_text_column(
            cleaned_df["FIELD_AGENCY_FIRE_CAUSE"]
        )

    if "FIELD_SYSTEM_FIRE_CAUSE" in cleaned_df.columns:
        cleaned_df["system_fire_cause_code"] = clean_text_column(
            cleaned_df["FIELD_SYSTEM_FIRE_CAUSE"]
        )

    if "FIELD_RESPONSE_TYPE" in cleaned_df.columns:
        cleaned_df["response_type_code"] = clean_text_column(
            cleaned_df["FIELD_RESPONSE_TYPE"]
        )

        # This label is explicitly marked provisional.
        cleaned_df["response_type_label"] = (
            cleaned_df["response_type_code"]
            .map(RESPONSE_TYPE_LABELS)
            .fillna("Unmapped")
        )

    # -------------------------------------------------------------
    # B. Create numeric analysis columns
    # -------------------------------------------------------------

    if "FIELD_FIRE_SIZE" in cleaned_df.columns:
        cleaned_df["fire_size_hectares"] = pd.to_numeric(
            cleaned_df["FIELD_FIRE_SIZE"],
            errors="coerce",
        )

    if "FIELD_LATITUDE" in cleaned_df.columns:
        cleaned_df["latitude"] = pd.to_numeric(
            cleaned_df["FIELD_LATITUDE"],
            errors="coerce",
        )
    else:
        cleaned_df["latitude"] = cleaned_df["geometry_latitude"]

    if "FIELD_LONGITUDE" in cleaned_df.columns:
        cleaned_df["longitude"] = pd.to_numeric(
            cleaned_df["FIELD_LONGITUDE"],
            errors="coerce",
        )
    else:
        cleaned_df["longitude"] = cleaned_df["geometry_longitude"]

    # -------------------------------------------------------------
    # C. Convert timestamps from epoch milliseconds to UTC
    # -------------------------------------------------------------

    timestamp_columns = {
        "FIELD_SITUATION_REPORT_DATE": "situation_report_datetime_utc",
        "FIELD_STATUS_DATE": "status_datetime_utc",
        "REFRESHED_DATETIME": "refreshed_datetime_utc",
    }

    for source_column, new_column in timestamp_columns.items():
        if source_column in cleaned_df.columns:
            cleaned_df[new_column] = cleaned_df[source_column].apply(
                convert_epoch_ms_to_utc
            )

    # -------------------------------------------------------------
    # D. Add a provisional cause interpretation
    # -------------------------------------------------------------

    # Start every row as unmapped.
    cleaned_df["cause_interpretation_provisional"] = "Unmapped"
    cleaned_df["cause_mapping_status"] = "Requires review"

    # The sample repeatedly showed LTG and L together.
    # This is interpreted as Lightning with high confidence,
    # but it is not used to force an L -> N national roll-up.
    required_cause_columns = {
        "agency_fire_cause_code",
        "system_fire_cause_code",
    }

    if required_cause_columns.issubset(cleaned_df.columns):
        lightning_mask = (
            cleaned_df["agency_fire_cause_code"].eq("LTG")
            & cleaned_df["system_fire_cause_code"].eq("L")
        )

        cleaned_df.loc[
            lightning_mask,
            "cause_interpretation_provisional",
        ] = "Lightning"

        cleaned_df.loc[
            lightning_mask,
            "cause_mapping_status",
        ] = "High-confidence provisional"

    # -------------------------------------------------------------
    # E. Flag -1 sentinel values without deleting them
    # -------------------------------------------------------------

    for field in SENTINEL_FIELDS:
        if field in cleaned_df.columns:
            cleaned_df[f"{field}_is_minus_one"] = cleaned_df[field].eq(-1)

    return cleaned_df


# ---------------------------------------------------------------------
# 6. BUILD A CODE-FREQUENCY REPORT
# ---------------------------------------------------------------------

def build_code_frequency_report(raw_df):
    """
    Count every distinct value in the important coded fields.

    This report helps discover undocumented values from the full pull.
    It does not guess their meanings.
    """

    fields_to_check = [
        "FIELD_STAGE_OF_CONTROL_STATUS",
        "FIELD_AGENCY_FIRE_CAUSE",
        "FIELD_SYSTEM_FIRE_CAUSE",
        "FIELD_RESPONSE_TYPE",
        "FIELD_AGENCY_CODE",
    ]

    report_parts = []

    for field in fields_to_check:
        if field not in raw_df.columns:
            continue

        # Convert values to strings so missing values can be shown clearly.
        values = raw_df[field].astype("string").fillna("<MISSING>").str.strip()

        counts = (
            values
            .value_counts(dropna=False)
            .rename_axis("code_value")
            .reset_index(name="record_count")
        )

        counts.insert(0, "field_name", field)
        report_parts.append(counts)

    if len(report_parts) == 0:
        return pd.DataFrame(
            columns=["field_name", "code_value", "record_count"]
        )

    return pd.concat(report_parts, ignore_index=True)


# ---------------------------------------------------------------------
# 7. BUILD BASIC DATA-QUALITY CHECKS
# ---------------------------------------------------------------------

def build_validation_report(raw_df, cleaned_df):
    """
    Create a small table of basic validation results.
    """

    checks = []

    def add_check(check_name, value):
        checks.append({
            "check_name": check_name,
            "value": value,
        })

    add_check("total_records", len(raw_df))

    if "FIELD_AGENCY_FIRE_ID" in raw_df.columns:
        add_check(
            "missing_fire_ids",
            int(raw_df["FIELD_AGENCY_FIRE_ID"].isna().sum()),
        )

    if "OBJECTID" in raw_df.columns:
        add_check(
            "duplicate_objectids",
            int(raw_df["OBJECTID"].duplicated().sum()),
        )

    if "latitude" in cleaned_df.columns:
        add_check(
            "missing_latitude",
            int(cleaned_df["latitude"].isna().sum()),
        )

    if "longitude" in cleaned_df.columns:
        add_check(
            "missing_longitude",
            int(cleaned_df["longitude"].isna().sum()),
        )

    if "fire_size_hectares" in cleaned_df.columns:
        add_check(
            "missing_fire_size",
            int(cleaned_df["fire_size_hectares"].isna().sum()),
        )
        add_check(
            "minimum_fire_size_hectares",
            cleaned_df["fire_size_hectares"].min(),
        )
        add_check(
            "maximum_fire_size_hectares",
            cleaned_df["fire_size_hectares"].max(),
        )

    if "stage_of_control_mapping_status" in cleaned_df.columns:
        add_check(
            "confirmed_stage_records",
            int(
                cleaned_df["stage_of_control_mapping_status"]
                .eq("Confirmed")
                .sum()
            ),
        )

        add_check(
            "provisional_stage_records",
            int(
                cleaned_df["stage_of_control_mapping_status"]
                .eq("Provisional")
                .sum()
            ),
        )

        add_check(
            "unmapped_stage_records",
            int(
                cleaned_df["stage_of_control_mapping_status"]
                .eq("Unmapped")
                .sum()
            ),
        )

    if "cause_mapping_status" in cleaned_df.columns:
        add_check(
            "cause_codes_requiring_review",
            int(
                cleaned_df["cause_mapping_status"]
                .eq("Requires review")
                .sum()
            ),
        )

    return pd.DataFrame(checks)


# ---------------------------------------------------------------------
# 8. PRINT IMPORTANT CODE WARNINGS
# ---------------------------------------------------------------------

def print_code_warnings(code_report):
    """
    Print warnings for codes that need review.
    """

    if code_report.empty:
        print("No code-frequency report was created.")
        return

    # Check stage-of-control values.
    stage_rows = code_report[
        code_report["field_name"].eq("FIELD_STAGE_OF_CONTROL_STATUS")
    ]

    observed_stage_codes = set(stage_rows["code_value"])
    known_stage_codes = (
        set(STAGE_OF_CONTROL_LABELS.keys())
        | set(STAGE_OF_CONTROL_LABELS_PROVISIONAL.keys())
    )

    unknown_stage_codes = (
        observed_stage_codes
        - known_stage_codes
        - {"<MISSING>"}
    )

    provisional_stage_codes_found = (
    observed_stage_codes
        & set(STAGE_OF_CONTROL_LABELS_PROVISIONAL.keys())
    )

    if provisional_stage_codes_found:
        print(
            "NOTICE - Provisional stage-of-control codes included:",
            sorted(provisional_stage_codes_found),
        )

    if unknown_stage_codes:
        print(
            "WARNING - Undocumented stage-of-control codes found:",
            sorted(unknown_stage_codes),
        )

    # Check system cause values against the documented H/N/U set.
    cause_rows = code_report[
        code_report["field_name"].eq("FIELD_SYSTEM_FIRE_CAUSE")
    ]

    observed_cause_codes = set(cause_rows["code_value"])
    values_outside_documented_set = observed_cause_codes - (
        DOCUMENTED_NATIONAL_CAUSE_CODES | {"<MISSING>"}
    )

    if values_outside_documented_set:
        print(
            "NOTICE - System cause values outside documented H/N/U set:",
            sorted(values_outside_documented_set),
        )
        print(
            "These values are preserved and must be reviewed. "
            "The observed L value is provisionally interpreted as Lightning."
        )


# ---------------------------------------------------------------------
# 9. SAVE ALL OUTPUT FILES
# ---------------------------------------------------------------------

def save_outputs(raw_df, cleaned_df, code_report, validation_report):
    """
    Save raw, processed, active-only, and quality-report files.
    """

    raw_folder = Path("data/raw/ontario_active_fires")
    processed_folder = Path("data/processed/ontario_active_fires")
    quality_folder = Path("data/quality/ontario_active_fires")

    raw_folder.mkdir(parents=True, exist_ok=True)
    processed_folder.mkdir(parents=True, exist_ok=True)
    quality_folder.mkdir(parents=True, exist_ok=True)

    # Include time in the filename so multiple daily snapshots are not overwritten.
    snapshot_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    raw_path = (
        raw_folder
        / f"ontario_fires_raw_{snapshot_name}.csv"
    )

    cleaned_path = (
        processed_folder
        / f"ontario_fires_cleaned_{snapshot_name}.csv"
    )

    active_path = (
        processed_folder
        / f"ontario_active_fires_{snapshot_name}.csv"
    )

    code_report_path = (
        quality_folder
        / f"ontario_fire_code_frequency_{snapshot_name}.csv"
    )

    validation_path = (
        quality_folder
        / f"ontario_fire_validation_{snapshot_name}.csv"
    )

    raw_df.to_csv(raw_path, index=False)
    cleaned_df.to_csv(cleaned_path, index=False)
    code_report.to_csv(code_report_path, index=False)
    validation_report.to_csv(validation_path, index=False)

    #  Active-only file includes every code in ACTIVE_STAGE_CODES,
    # which currently includes BM on a provisional basis (see above).
    if "is_active_fire" in cleaned_df.columns:
        active_df = cleaned_df[cleaned_df["is_active_fire"]].copy()
    else:
        active_df = cleaned_df.copy()

    active_df.to_csv(active_path, index=False)

    print("\nFiles saved:")
    print(f"Raw snapshot:        {raw_path}")
    print(f"Cleaned snapshot:    {cleaned_path}")
    print(f"Active fires only:   {active_path}")
    print(f"Code report:         {code_report_path}")
    print(f"Validation report:   {validation_path}")


# ---------------------------------------------------------------------
# 10. MAIN PROGRAM
# ---------------------------------------------------------------------

def main():
    """
    Run the complete OWF-26 extraction process.
    """

    print("=" * 60)
    print("OWF-26 - Ontario Active Fires Extraction")
    print("=" * 60)

    # Step 1: Download the source records.
    raw_df = fetch_all_fire_records()

    print(f"\nTotal records downloaded: {len(raw_df)}")

    # Stop safely if the service returned no records.
    if raw_df.empty:
        print("No fire records were returned. No files were created.")
        return

    # Step 2: Create cleaned and interpreted columns.
    cleaned_df = build_cleaned_dataset(raw_df)

    # Step 3: Build code and validation reports.
    code_report = build_code_frequency_report(raw_df)
    validation_report = build_validation_report(raw_df, cleaned_df)

    # Step 4: Print the discovered codes and important warnings.
    print("\nCode frequency report:")
    print(code_report.to_string(index=False))

    print("\nValidation report:")
    print(validation_report.to_string(index=False))

    print()
    print_code_warnings(code_report)

    # Step 5: Save all outputs.
    save_outputs(
        raw_df=raw_df,
        cleaned_df=cleaned_df,
        code_report=code_report,
        validation_report=validation_report,
    )

    print("\nOWF-26 extraction completed successfully.")


# This condition means:
# Run main() only when this file is executed directly.
# Do not run main() automatically if the file is imported by another script.
if __name__ == "__main__":
    main()
