import numpy as np
import pydeck as pdk
import os
import pandas as pd
import streamlit as st
import gdown

st.set_page_config(page_title="Flow Map - Data Merge Only", layout="wide")
st.title("Flow Map")

# --- Google Drive file setup ---
@st.cache_data(show_spinner=True)
def download_files_from_gdrive():
    """Download required files from Google Drive"""
    import os
    
    # Create temp directory if it doesn't exist
    out_dir = "gdown_temp"
    os.makedirs(out_dir, exist_ok=True)
    
    # Required files
    required_files = [
        "flatfile_eu-ic-io_ind-by-ind_23ed_2021.csv",
        "Map of routes data.csv", 
        "nace.csv"
    ]
    
    # Check if files already exist
    all_files_exist = all(os.path.exists(os.path.join(out_dir, filename)) for filename in required_files)
    
    if not all_files_exist:
        try:
            st.info("Downloading files from Google Drive...")
            # Download the entire folder using the public folder ID
            folder_id = "16CaF7Qlnk-524nD9afUrUs3OtQoKna3v"
            folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
            
            # Use gdown to download the entire folder
            gdown.download_folder(folder_url, output=out_dir, quiet=False, use_cookies=False)
            
            # Verify all required files were downloaded
            missing_files = [f for f in required_files if not os.path.exists(os.path.join(out_dir, f))]
            if missing_files:
                st.error(f"Missing files after download: {missing_files}")
                st.stop()
            else:
                st.success("All files downloaded successfully!")
                
        except Exception as e:
            st.error(f"Error downloading files from Google Drive: {e}")
            st.info("Please ensure the Google Drive folder is publicly accessible.")
            st.stop()
    
    return out_dir

# Download files from Google Drive
out_dir = download_files_from_gdrive()
main_file = os.path.join(out_dir, "flatfile_eu-ic-io_ind-by-ind_23ed_2021.csv")
countries_file = os.path.join(out_dir, "Map of routes data.csv")
nace_file = os.path.join(out_dir, "nace.csv")

# List of allowed country codes (from images)
allowed_countries = [
    "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GB", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "NL",
    "NO", "PL", "PT", "RO", "SE", "SI", "SK"
]

# Load datasets with Streamlit caching and filter by allowed countries
@st.cache_data(show_spinner=False)
def load_main():
    df = pd.read_csv(main_file)
    df = df[df["refArea"].isin(allowed_countries) & df["counterpartArea"].isin(allowed_countries)]
    return df

@st.cache_data(show_spinner=False)
def load_countries():
    df = pd.read_csv(countries_file)
    df = df[df[df.columns[1]].isin(allowed_countries)]
    return df

@st.cache_data(show_spinner=False)
def load_nace():
    df = pd.read_csv(nace_file)
    df = df.iloc[:, :2]
    df.columns = ["Code", "Name"]
    df["Code"] = df["Code"].astype(str).str.strip()
    return df

# Load data
main_df = load_main()
countries_df = load_countries()
nace_df = load_nace()

# Use column indices for countries file
country_col = countries_df.columns[1]  # 2nd col: country code
lat_col = countries_df.columns[2]      # 3rd col: latitude
lon_col = countries_df.columns[3]      # 4th col: longitude

# --- FILTERS ---
st.sidebar.header("Filters")

# Get unique options
origin_options = sorted(main_df["refArea"].dropna().unique())
dest_options = sorted(main_df["counterpartArea"].dropna().unique())

# Default destination
default_dest = ["ES"] if "ES" in dest_options else dest_options[:1]

# Initialize session state for filters
if "select_all_origin" not in st.session_state:
    st.session_state.select_all_origin = True
if "select_all_dest" not in st.session_state:
    st.session_state.select_all_dest = False
if "selected_origin" not in st.session_state:
    st.session_state.selected_origin = origin_options
if "selected_dest" not in st.session_state:
    st.session_state.selected_dest = default_dest

# Origin country selection
select_all_origin = st.sidebar.checkbox("Select all origin countries", key="select_all_origin")
if select_all_origin:
    st.session_state.selected_origin = origin_options
    selected_origin = origin_options
else:
    selected_origin = st.sidebar.multiselect(
        "Origin country", 
        origin_options, 
        default=st.session_state.selected_origin,
        key="origin_multiselect"
    )
    st.session_state.selected_origin = selected_origin

# Destination country selection
select_all_dest = st.sidebar.checkbox("Select all destination countries", key="select_all_dest")
if select_all_dest:
    st.session_state.selected_dest = dest_options
    selected_dest = dest_options
else:
    selected_dest = st.sidebar.multiselect(
        "Destination country", 
        dest_options, 
        default=st.session_state.selected_dest,
        key="dest_multiselect"
    )
    st.session_state.selected_dest = selected_dest

# Check for empty filters and warn user
if not selected_origin:
    st.warning("Please select at least one origin country.")
    st.stop()
if not selected_dest:
    st.warning("Please select at least one destination country.")
    st.stop()

# Filter main_df and merge with geographic data
@st.cache_data(show_spinner=False)
def prepare_merged_data(main_df, countries_df, nace_df, selected_origin, selected_dest):
    # Filter main data and exclude domestic flows (same origin and destination)
    # Use more memory-efficient filtering
    filtered_df = main_df[
        main_df["refArea"].isin(selected_origin) &
        main_df["counterpartArea"].isin(selected_dest) &
        (main_df["refArea"] != main_df["counterpartArea"])  # Exclude domestic flows
    ]
    
    # If dataset is too large, sample it to prevent memory issues
    if len(filtered_df) > 500000:  # If more than 500k rows
        st.info("Large dataset detected. Sampling data for better performance...")
        # Sample the data but keep the highest values
        filtered_df = filtered_df.nlargest(500000, 'obsValue')
    
    # Create a copy only after filtering
    filtered_df = filtered_df.copy()
    
    # Merge with countries data for origin coordinates
    merged_df = filtered_df.merge(
        countries_df[[country_col, lat_col, lon_col]], 
        left_on="refArea", 
        right_on=country_col, 
        how="left"
    )
    merged_df.rename(columns={lat_col: "origin_lat", lon_col: "origin_lon"}, inplace=True)
    merged_df.drop(columns=[country_col], inplace=True)
    
    # Merge with countries data for destination coordinates
    merged_df = merged_df.merge(
        countries_df[[country_col, lat_col, lon_col]], 
        left_on="counterpartArea", 
        right_on=country_col, 
        how="left"
    )
    merged_df.rename(columns={lat_col: "dest_lat", lon_col: "dest_lon"}, inplace=True)
    merged_df.drop(columns=[country_col], inplace=True)
    
    # Merge with NACE for row sectors
    merged_df = merged_df.merge(nace_df, left_on="rowIi", right_on="Code", how="left")
    merged_df.rename(columns={"Name": "rowIi_name"}, inplace=True)
    merged_df.drop(columns=["Code"], inplace=True)
    
    # Merge with NACE for column sectors
    merged_df = merged_df.merge(nace_df, left_on="colIi", right_on="Code", how="left")
    merged_df.rename(columns={"Name": "colIi_name"}, inplace=True)
    merged_df.drop(columns=["Code"], inplace=True)
    
    return merged_df

# Prepare merged data
merged_df = prepare_merged_data(main_df, countries_df, nace_df, selected_origin, selected_dest)

# Get sector options from merged data
row_name_options = sorted(merged_df["rowIi_name"].dropna().unique())
col_name_options = sorted(merged_df["colIi_name"].dropna().unique())

# Set default for col sectors (case-insensitive match)
default_col = [name for name in col_name_options if name.strip().lower() == "wholesale trade, except of motor vehicles and motorcycles"]
if not default_col:
    # Try partial match
    default_col = [name for name in col_name_options if "wholesale trade" in name.lower()]
if not default_col:
    default_col = col_name_options[:1]

# Initialize session state for sectors
if "select_all_row" not in st.session_state:
    st.session_state.select_all_row = True
if "select_all_col" not in st.session_state:
    st.session_state.select_all_col = False
if "selected_row" not in st.session_state:
    st.session_state.selected_row = row_name_options
if "selected_col" not in st.session_state:
    st.session_state.selected_col = default_col

# Origin sector selection
select_all_row = st.sidebar.checkbox("Select all origin sectors", key="select_all_row")
if select_all_row:
    st.session_state.selected_row = row_name_options
    selected_row = row_name_options
else:
    selected_row = st.sidebar.multiselect(
        "Origin sectors", 
        row_name_options, 
        default=st.session_state.selected_row,
        key="row_multiselect"
    )
    st.session_state.selected_row = selected_row

# Destination sector selection
select_all_col = st.sidebar.checkbox("Select all destination sectors", key="select_all_col")
if select_all_col:
    st.session_state.selected_col = col_name_options
    selected_col = col_name_options
else:
    selected_col = st.sidebar.multiselect(
        "Destination sectors", 
        col_name_options, 
        default=st.session_state.selected_col,
        key="col_multiselect"
    )
    st.session_state.selected_col = selected_col

# Check for empty sector filters
if not selected_row:
    st.warning("Please select at least one origin sector.")
    st.stop()
if not selected_col:
    st.warning("Please select at least one destination sector.")
    st.stop()

# Display Settings (after all filters)
st.sidebar.subheader("Display Settings")
num_flows = st.sidebar.number_input(
    "Number of top flows to display", 
    min_value=1, 
    max_value=50, 
    value=25, 
    step=1,
    key="num_flows"
)

# Apply sector filters
sector_filtered_df = merged_df[
    merged_df["rowIi_name"].isin(selected_row) &
    merged_df["colIi_name"].isin(selected_col)
].copy()

# Prevent map rendering if no data
if sector_filtered_df.empty:
    st.warning("No data available for the selected filters. Please adjust your selections.")
    st.stop()

# Calculate top 25 flows by obsValue - use ALL data first, then apply sector filters
@st.cache_data(show_spinner=False)
def get_top_flows_global(merged_df, selected_row, selected_col, top_n=25):
    # First get top flows from ALL sectors to ensure we have 25 lanes
    all_flows = (
        merged_df.groupby(["refArea", "counterpartArea"])["obsValue"]
        .sum()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
    )
    
    # Then filter the detailed data by sectors for the top flows
    top_flows_detailed = merged_df[
        merged_df["rowIi_name"].isin(selected_row) &
        merged_df["colIi_name"].isin(selected_col)
    ].merge(
        all_flows[["refArea", "counterpartArea"]],
        on=["refArea", "counterpartArea"],
        how="inner"
    )
    
    # If we don't have enough data after sector filtering, fall back to sector-filtered top flows
    if top_flows_detailed.empty or len(top_flows_detailed.groupby(["refArea", "counterpartArea"])) < 5:
        sector_flows = (
            merged_df[
                merged_df["rowIi_name"].isin(selected_row) &
                merged_df["colIi_name"].isin(selected_col)
            ].groupby(["refArea", "counterpartArea"])["obsValue"]
            .sum()
            .sort_values(ascending=False)
            .head(top_n)
            .reset_index()
        )
        
        top_flows_detailed = merged_df[
            merged_df["rowIi_name"].isin(selected_row) &
            merged_df["colIi_name"].isin(selected_col)
        ].merge(
            sector_flows[["refArea", "counterpartArea"]],
            on=["refArea", "counterpartArea"],
            how="inner"
        )
        
        return top_flows_detailed, sector_flows
    
    # Recalculate flow summary for the filtered data
    flow_summary = (
        top_flows_detailed.groupby(["refArea", "counterpartArea"])["obsValue"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    
    return top_flows_detailed, flow_summary

# Get top flows using the user-selected number
arc_df, flow_summary = get_top_flows_global(merged_df, selected_row, selected_col, num_flows)

# Prepare bubble data (destinations) - show bubbles only for destinations of displayed lanes
# Get unique destinations from the displayed flows
displayed_destinations = flow_summary["counterpartArea"].unique() if not flow_summary.empty else []

# Filter bubble data to only include destinations that appear in the displayed flows
bubble_df = (
    sector_filtered_df[sector_filtered_df["counterpartArea"].isin(displayed_destinations)]
    .groupby(["counterpartArea", "dest_lat", "dest_lon"], as_index=False)["obsValue"]
    .sum()
    .sort_values("obsValue", ascending=False)
)

# --- MAP VISUALIZATION ---
# Define colors
orange = [236, 108, 76]

# Calculate arc widths based on obsValue with thinner lines
def calculate_arc_width(obs_value, max_value, min_value):
    """Calculate arc width based on obsValue with thinner scaling"""
    if max_value == min_value:
        return 1
    
    # Use logarithmic scaling for better visual distinction
    import math
    
    # Avoid log(0) by adding small value
    safe_obs = max(obs_value, 1)
    safe_min = max(min_value, 1)
    safe_max = max(max_value, 1)
    
    # Logarithmic normalization
    log_obs = math.log(safe_obs)
    log_min = math.log(safe_min)
    log_max = math.log(safe_max)
    
    if log_max == log_min:
        return 1
    
    normalized = (log_obs - log_min) / (log_max - log_min)
    
    # Scale to even thinner width range (1-4 pixels) for thinner lines
    width = 1 + (normalized * 3)
    return max(1, int(width))

# Add arc widths to data based on flow summary values for better scaling
if not arc_df.empty and not flow_summary.empty:
    # Use flow summary values for consistent scaling across all arcs
    max_flow = flow_summary["obsValue"].max()
    min_flow = flow_summary["obsValue"].min()
    
    # Create a mapping of flow values for each origin-destination pair
    flow_mapping = dict(zip(
        flow_summary.apply(lambda x: f"{x['refArea']}_{x['counterpartArea']}", axis=1),
        flow_summary["obsValue"]
    ))
    
    # Apply width calculation based on aggregated flow values
    arc_df["flow_key"] = arc_df.apply(lambda x: f"{x['refArea']}_{x['counterpartArea']}", axis=1)
    arc_df["flow_total"] = arc_df["flow_key"].map(flow_mapping)
    arc_df["arc_width"] = arc_df["flow_total"].apply(
        lambda x: calculate_arc_width(x, max_flow, min_flow)
    )

# Create arc layer with less arch (lower tilt)
arc_layer = pdk.Layer(
    "ArcLayer",
    data=arc_df,
    get_source_position="[origin_lon, origin_lat]",
    get_target_position="[dest_lon, dest_lat]",
    get_source_color=orange,
    get_target_color=orange,
    get_width="arc_width",
    get_tilt=0.02,  # Further reduced from 0.05 to 0.02 for minimal arch
    pickable=True,
    auto_highlight=True,
)

# Create bubble layer with proper scaling
if not bubble_df.empty:
    max_bubble_value = bubble_df["obsValue"].max()
    min_bubble_value = bubble_df["obsValue"].min()
    
    # Calculate bubble radius with less sensitive scaling (square root scaling)
    def calculate_bubble_radius(obs_value, max_value, min_value):
        if max_value == min_value:
            return 25000  # Half of previous 50000
        
        # Normalize to 0-1 range
        normalized = (obs_value - min_value) / (max_value - min_value)
        
        # Apply square root scaling to make bubbles less sensitive to value differences
        # This compresses the range, making bubbles more similar in size
        sqrt_normalized = np.sqrt(normalized)
        
        # Scale to a slightly bigger radius range (20k-70k) for more visible bubbles
        radius = 20000 + (sqrt_normalized * 50000)
        return radius
    
    bubble_df["radius"] = bubble_df["obsValue"].apply(
        lambda x: calculate_bubble_radius(x, max_bubble_value, min_bubble_value)
    )

bubble_layer = pdk.Layer(
    "ScatterplotLayer",
    data=bubble_df,
    get_position="[dest_lon, dest_lat]",
    get_radius="radius",
    get_fill_color=orange + [160],
    get_line_color=[255, 255, 255],
    get_line_width=2,
    pickable=True,
)

# Calculate map center
if not arc_df.empty:
    center_lat = float(np.nanmean([arc_df["origin_lat"].mean(), arc_df["dest_lat"].mean()]))
    center_lon = float(np.nanmean([arc_df["origin_lon"].mean(), arc_df["dest_lon"].mean()]))
else:
    center_lat, center_lon = 54.5, 15.0  # Default center for Europe

view = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=4)

# Create tooltip
tooltip_text = "Origin: {refArea}\nDestination: {counterpartArea}\nValue: {obsValue}\nRow: {rowIi_name}\nCol: {colIi_name}"

# Create deck
r = pdk.Deck(
    layers=[arc_layer, bubble_layer],
    initial_view_state=view,
    map_provider="carto",
    map_style="light",
    tooltip={"text": tooltip_text},
)

# Display results
st.subheader(f"Top {len(flow_summary)} Lanes (Value in EUR)")
st.pydeck_chart(r, use_container_width=True)

# Display summary statistics
if not flow_summary.empty:
    st.subheader("Flow Summary")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Flows Displayed", len(flow_summary))
    
    with col2:
        st.metric("Total Value (EUR)", f"{flow_summary['obsValue'].sum():,.0f}")
    
    with col3:
        st.metric("Average Flow Value (EUR)", f"{flow_summary['obsValue'].mean():,.0f}")
    
    # Show top flows table
    st.subheader("Top Lanes")
    display_df = flow_summary.copy()
    display_df["obsValue"] = display_df["obsValue"].apply(lambda x: f"{x:,.0f}")
    display_df.columns = ["Origin", "Destination", "Value (EUR)"]
    st.dataframe(display_df, use_container_width=True)
