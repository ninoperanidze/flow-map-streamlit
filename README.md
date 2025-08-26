# Flow Map Streamlit App

This Streamlit app visualizes flows between countries using data from Google Drive. It features interactive maps, filters, and automatic data loading.

## Features
- Interactive flow map between origin and destination countries
- Bubbles sized by sum of flow values (obsValue)
- Filters for origin, destination, row sector, and column sector
- Loads only the required files from a public Google Drive folder
- Limits data for performance (top destinations, top flows)

## How to Run Locally

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/flow-map-streamlit.git
   cd flow-map-streamlit
   ```
2. (Optional) Create and activate a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Mac/Linux
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the app:
   ```
   streamlit run app.py
   ```

## Data
- The app automatically downloads the following files from a public Google Drive folder:
  - `flatfile_eu-ic-io_ind-by-ind_23ed_2021.csv`
  - `Map of routes data.csv`
  - `nace.csv`
- Only these files are used, even if other files are present in the folder.

## Deployment
- Push your code to GitHub.
- Deploy for free on [Streamlit Community Cloud](https://streamlit.io/cloud).

## Requirements
See `requirements.txt` for Python dependencies.

## License
MIT
