# GPX Trimmer 🏃 [![Streamlit app](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://gpx-trimmer.streamlit.app/)

A lightweight tool to trim long pauses from GPX tracks.

Some applications, e.g., Komoot, do not differentiate between **moving time** and **elapsed time** when the activity is imported as a GPX file. In such cases, the elapsed time remains inflated by the time spent paused during the activity, which does not reflect the actual activity statistics, especially if a long pause was taken, e.g., during a lunch break.

This application detects the **long** pauses in your GPX file and removes them, allowing you to obtain a more accurate representation of your activity.
* It only shifts the timestamps of the recorded points to remove long pauses; it does not modify other GPX data.
* To avoid spikes in the velocity profile, the timestamps of points after a long pause are shifted so that the transition speed matches the moving average speed.
* It targets both cases: 1) the GPX tracker paused tracking and there is a large time jump; 2) the GPX tracker continued recording during a pause.
* The data acquisition frequency does not matter.
* It provides a short summary of the pauses that are removed.


## How to Run

**Option 1: Running online:**

Go to the [Streamlit app link](https://gpx-trimmer.streamlit.app/)
 and follow the instructions.

**Option 2: Running locally:**

Clone this repository and set up the environment:
```bash
git clone https://github.com/ozhanozen/gpx-trimmer
cd gpx-trimmer
pip install -r requirements.txt
```

Option 2A: Run it as a local streamlit app:
```bash
streamlit run streamlit_app.py
```

Option 2B: Run it from the command-line:
```bash
./gpx_trimmer input_file_path --min_speed MIN_SPEED --min_pause_duration MIN_PAUSE_DURATION
```
or
```bash
python gpx_trimmer input_file_path --min_speed MIN_SPEED --min_pause_duration MIN_PAUSE_DURATION
```

---

## How to Trim

* Input either a single **.gpx** file or a **.zip** archive containing many GPX files.
* Adjust the **low‑speed threshold** and **minimum pause duration** to define what is considered a long pause.


---

Feel free to report any bugs or suggestions via [GitHub Issues](https://github.com/ozhanozen/gpx-trimmer/issues).

 

