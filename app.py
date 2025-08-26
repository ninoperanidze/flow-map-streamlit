
import numpy as np
import pydeck as pdk
import os
import pandas as pd
import streamlit as st
import gdown

st.set_page_config(page_title="Flow Map - Data Merge Only", layout="wide")
st.title("Flow Map (Local Files: Data Merge Only)")


# --- Google Drive setup ---
folder_id = "16CaF7Qlnk-524nD9afUrUs3OtQoKna3v"
required_files = [
    "flatfile_eu-ic-io_ind-by-ind_23ed_2021.csv",
    "Map of routes data.csv",
    "nace.csv"
]
out_dir = "gdown_temp"
os.makedirs(out_dir, exist_ok=True)
gdown.download_folder(id=folder_id, output=out_dir, quiet=True, use_cookies=False)
files = {f: os.path.join(out_dir, f) for f in os.listdir(out_dir) if f in required_files}

if not all(f in files for f in required_files):
    st.error("Required files not found in Google Drive folder. Please ensure the following files are present: flatfile_eu-ic-io-ind-by-ind_23ed_2021.csv, Map of routes data.csv, nace.csv")
    st.stop()

# Load datasets
main_df = pd.read_csv(files["flatfile_eu-ic-io_ind-by-ind_23ed_2021.csv"])
countries_df = pd.read_csv(files["Map of routes data.csv"])
nace_df = pd.read_csv(files["nace.csv"])

# Always use first two columns for NACE
nace_df = nace_df.iloc[:, :2]
nace_df.columns = ["Code", "Name"]
nace_df["Code"] = nace_df["Code"].astype(str).str.strip()

# Use column indices for countries file
country_col = countries_df.columns[1]  # 2nd col: country code
lat_col = countries_df.columns[2]      # 3rd col: latitude
lon_col = countries_df.columns[3]      # 4th col: longitude

# Merge main_df with countries_df for origin and destination
merged_df = main_df.merge(countries_df[[country_col, lat_col, lon_col]], left_on="refArea", right_on=country_col, how="left")
merged_df = merged_df.rename(columns={lat_col: "origin_lat", lon_col: "origin_lon"})
merged_df = merged_df.merge(countries_df[[country_col, lat_col, lon_col]], left_on="counterpartArea", right_on=country_col, how="left")
merged_df = merged_df.rename(columns={lat_col: "dest_lat", lon_col: "dest_lon"})

# Merge with NACE for rowIi and colIi
merged_df = merged_df.merge(nace_df, left_on="rowIi", right_on="Code", how="left")
merged_df = merged_df.rename(columns={"Name": "rowIi_name"})
merged_df = merged_df.merge(nace_df, left_on="colIi", right_on="Code", how="left")
merged_df = merged_df.rename(columns={"Name": "colIi_name"})

# Remove unnecessary columns
drop_cols = [country_col, f"{country_col}_y", "Code", "Code_y", f"{country_col}_x", "Code_x"]
merged_df = merged_df.drop(columns=[c for c in drop_cols if c in merged_df.columns])


# --- FILTERS ---

st.sidebar.header("Filters")
origin_options = sorted(merged_df["refArea"].dropna().unique())
dest_options = sorted(merged_df["counterpartArea"].dropna().unique())
row_options = sorted(merged_df["rowIi_name"].dropna().unique())
col_options = sorted(merged_df["colIi_name"].dropna().unique())

selected_origin = st.sidebar.multiselect("Origin country", origin_options, default=origin_options)
selected_dest = st.sidebar.multiselect("Destination country", dest_options, default=dest_options)
selected_row = st.sidebar.multiselect("Row sector (name)", row_options, default=row_options)
selected_col = st.sidebar.multiselect("Col sector (name)", col_options, default=col_options)

# Filter data
filtered_df = merged_df[
    merged_df["refArea"].isin(selected_origin) &
    merged_df["counterpartArea"].isin(selected_dest) &
    merged_df["rowIi_name"].isin(selected_row) &
    merged_df["colIi_name"].isin(selected_col)
]


# Limit destination countries: default ES, IT, PL, user can select up to 20
dest_options = sorted(merged_df["counterpartArea"].dropna().unique())
default_dest = [c for c in dest_options if c in ["ES", "IT", "PL"]]
selected_dest = st.sidebar.multiselect(
    "Destination country (max 20)", dest_options, default=default_dest, max_selections=20
)
filtered_df = filtered_df[filtered_df["counterpartArea"].isin(selected_dest)]

# Limit lines (flows) to top 25 by obsValue
filtered_df = filtered_df.sort_values("obsValue", ascending=False).head(25)

# --- MAP DATA PREP ---
bubble_df = filtered_df.groupby(["counterpartArea", "dest_lat", "dest_lon"], as_index=False)["obsValue"].sum()
arc_df = filtered_df.copy()

# --- PYDECK MAP ---
center_lat = float(np.nanmean([arc_df["origin_lat"].mean(), arc_df["dest_lat"].mean()]))
center_lon = float(np.nanmean([arc_df["origin_lon"].mean(), arc_df["dest_lon"].mean()]))
view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=2)

max_obs = float(max(1.0, arc_df["obsValue"].max()))

arc_layer = pdk.Layer(
    "ArcLayer",
    data=arc_df,
    get_source_position="[origin_lon, origin_lat]",
    get_target_position="[dest_lon, dest_lat]",
    get_width=f"(obsValue/{max_obs})*8 + 1",
    get_tilt=15,
    pickable=True,
    auto_highlight=True,
)

bubble_layer = pdk.Layer(
    "ScatterplotLayer",
    data=bubble_df,
    get_position="[dest_lon, dest_lat]",
    get_radius="(obsValue/{}) * 200000 + 20000".format(bubble_df["obsValue"].max()),
    get_fill_color="[30, 144, 255, 160]",
    pickable=True,
)

tooltip_text = "Origin: {refArea}\nDestination: {counterpartArea}\nValue: {obsValue}\nRow: {rowIi_name}\nCol: {colIi_name}"

r = pdk.Deck(
    layers=[arc_layer, bubble_layer],
    initial_view_state=view,
    map_provider="carto",
    map_style="light",
    tooltip={"text": tooltip_text},
)

st.subheader("Flow Map")
st.pydeck_chart(r, use_container_width=True)