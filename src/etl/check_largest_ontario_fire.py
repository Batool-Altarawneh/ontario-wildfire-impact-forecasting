"""
OWF-26 - Check the largest Ontario fire record

This small script reads the cleaned Ontario fire dataset,
finds the fire with the largest recorded size, and prints
the most useful fields for manual validation.
"""

from pathlib import Path

import pandas as pd


# -------------------------------------------------------------
# 1. SET THE FILE PATH
# -------------------------------------------------------------

# This is the cleaned file created by the OWF-26 extraction script.
# The r before the text makes the Windows path easier to read.
file_path = Path(
    "data/processed/ontario_active_fires/"
    "ontario_fires_cleaned_20260731T045931Z.csv"
)


# -------------------------------------------------------------
# 2. CHECK THAT THE FILE EXISTS
# -------------------------------------------------------------

# Before reading the file, check that the path is correct.
# This gives a clear error instead of a long pandas error message.
if not file_path.exists():
    raise FileNotFoundError(
        f"The cleaned Ontario fire file was not found:\n{file_path}"
    )


# -------------------------------------------------------------
# 3. READ THE CSV FILE
# -------------------------------------------------------------

# Load the cleaned CSV file into a pandas DataFrame.
df = pd.read_csv(file_path)

print(f"File loaded successfully: {file_path}")
print(f"Total records in the file: {len(df)}")


# -------------------------------------------------------------
# 4. CHECK THAT THE FILE IS NOT EMPTY
# -------------------------------------------------------------

if df.empty:
    raise ValueError("The cleaned fire dataset is empty.")


# -------------------------------------------------------------
# 5. CHECK THAT THE REQUIRED COLUMNS EXIST
# -------------------------------------------------------------

# These are the columns that will be used in this check.
required_columns = [
    "fire_id",
    "fire_size_hectares",
    "stage_of_control_code",
    "stage_of_control_display_label",
    "agency_fire_cause_code",
    "situation_report_datetime_utc",
    "status_datetime_utc",
    "latitude",
    "longitude",
]

# Find any columns that are missing from the file.
missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

# Stop the script if one or more required columns are missing.
if missing_columns:
    raise KeyError(
        "The following required columns are missing:\n"
        + "\n".join(missing_columns)
    )


# -------------------------------------------------------------
# 6. MAKE SURE FIRE SIZE IS NUMERIC
# -------------------------------------------------------------

# Convert the fire-size column to numbers.
# Any invalid value will become NaN instead of causing an error.
df["fire_size_hectares"] = pd.to_numeric(
    df["fire_size_hectares"],
    errors="coerce",
)

# Check whether the column contains at least one valid value.
if df["fire_size_hectares"].notna().sum() == 0:
    raise ValueError(
        "The fire_size_hectares column does not contain valid numbers."
    )


# -------------------------------------------------------------
# 7. FIND THE LARGEST FIRE SIZE
# -------------------------------------------------------------

# Find the maximum recorded fire size.
maximum_fire_size = df["fire_size_hectares"].max()

print("\nLargest fire size found:")
print(f"{maximum_fire_size:,.1f} hectares")


# -------------------------------------------------------------
# 8. SELECT THE RECORD WITH THE LARGEST SIZE
# -------------------------------------------------------------

# Select every record whose fire size equals the maximum value.
# Usually this will return one record, but there could be more than one.
outlier_records = df[
    df["fire_size_hectares"] == maximum_fire_size
].copy()

print(
    f"Number of records with this maximum size: "
    f"{len(outlier_records)}"
)


# -------------------------------------------------------------
# 9. CHOOSE THE COLUMNS TO DISPLAY
# -------------------------------------------------------------

columns_to_display = [
    "fire_id",
    "fire_size_hectares",
    "stage_of_control_code",
    "stage_of_control_display_label",
    "agency_fire_cause_code",
    "situation_report_datetime_utc",
    "status_datetime_utc",
    "latitude",
    "longitude",
]


# -------------------------------------------------------------
# 10. PRINT THE OUTLIER RECORD
# -------------------------------------------------------------

print("\nLargest fire record:")
print("-" * 80)

# index=False prevents pandas from printing the DataFrame row number.
print(
    outlier_records[columns_to_display]
    .to_string(index=False)
)