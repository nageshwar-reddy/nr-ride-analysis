# NR Ride Analysis 🚴 [![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://nr-ride-analysis.streamlit.app/)

A Streamlit web app to analyse endurance rides by detecting long pauses in GPX files and generating a detailed Excel summary with per-segment metrics.

---

## What It Does

Upload a GPX file from your ride and the app will:

- **Detect pauses** — identifies stops longer than a configurable duration
- **Per-segment metrics** — for each riding segment between pauses:
  - Average speed, cadence, heart rate, and power
  - Elevation gain and loss
  - Segment distance and duration
- **Cumulative distance** — distance from the start at each pause
- **Timing** — IST time and relative time from ride start for each pause
- **Location links** — clickable Google Maps link for every pause location
- **Reverse geocoding** *(optional)* — human-readable place names for each pause
- **Excel summary** — downloadable `.xlsx` with all details, formatted and ready to use

---

## How to Use

**Online (recommended):**

Go to [nr-ride-analysis.streamlit.app](https://nr-ride-analysis.streamlit.app/) — no installation needed.

1. Upload a `.gpx` file or a `.zip` archive containing multiple GPX files
2. Adjust settings if needed:
   - **Low-speed threshold** *(default: 0.1 m/s)* — speed below which movement is treated as a pause
   - **Minimum pause duration** *(default: 120 seconds)* — shortest pause to detect
3. Optionally enable **reverse geocoding** for location names
4. Click **Analyze My Ride**
5. Download the Excel summary

---

## Running Locally

```bash
git clone https://github.com/nageshwar-reddy/nr-ride-analysis
cd nr-ride-analysis
pip install -r requirements.txt
streamlit run streamlit_app.py
```

---

## Excel Output Columns

| Column | Description |
|---|---|
| Segment # | Segment sequence number |
| Segment Distance (km) | Distance covered in this segment |
| Segment Duration | Riding time for this segment |
| Seg. End IST | IST clock time at segment end / pause start |
| Break Duration | Duration of the pause |
| Avg Speed (km/h) | Average moving speed for the segment |
| Avg Cadence | Average cadence (rpm) |
| Avg HR | Average heart rate (bpm) |
| Elev Gain (m) | Elevation gained in the segment |
| Elev Loss (m) | Elevation lost in the segment |
| Avg Power (W) | Average power output |
| Cumulative Distance (km) | Total distance from ride start |
| Seg. End Relative | Time elapsed from ride start (HH:MM:SS) |
| Location | Reverse-geocoded place name *(if enabled)* |
| Google Maps Link | Clickable link to pause location |
| Break Duration (seconds) | Numeric duration for analysis |
| Drift (meters) | Distance drifted during the pause |
| Latitude / Longitude | Coordinates of the pause |

---

## Dependencies

- [gpxpy](https://github.com/tkrajina/gpxpy) — GPX parsing
- [geopy](https://github.com/geopy/geopy) — distance calculations and reverse geocoding
- [streamlit](https://streamlit.io/) — web app framework
- [pandas](https://pandas.pydata.org/) — data handling
- [openpyxl](https://openpyxl.readthedocs.io/) — Excel file generation
- [google-cloud-storage](https://cloud.google.com/storage/docs/reference/libraries) — cloud storage

---

## Feedback & Contributions

Found a bug or have a suggestion? Please open a [GitHub Issue](https://github.com/nageshwar-reddy/nr-ride-analysis/issues).

Happy riding! 🚴‍♂️💨
