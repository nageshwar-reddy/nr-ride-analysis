# Ride Analysis 🏃 [![Streamlit app](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://gpx-trimmer.streamlit.app/)

For the original gpx trimmer applicaiton please refer to https://github.com/ozhanozen/gpx-trimmer

I want to use this application analyse my endurance rides. Anyone with similar interests can use this app and suggest changes. I inted to actively spend some of my free time in making this useful for me in improving my endurance. 

This application detects the **long** brekas in your ride GPX file and adds additional details like distance from the start, clickable location and more info,


## How to Run

**Option 1: Running online:**

Go to the [Streamlit app link](https://nr-ride-analysis.streamlit.app/)
 and follow the instructions.

**Option 2: Running locally:**

Clone this repository and set up the environment:
```bash
git clone https://github.com/ozhanozen/nr-ride-analysis
cd nr-ride-analysis
pip install -r requirements.txt
```

Option 2A: Run it as a local streamlit app:
```bash
streamlit run streamlit_app.py
```

Option 2B: Run it from the command-line:
```bash
./nr-ride-analysis input_file_path --min_speed MIN_SPEED --min_pause_duration MIN_PAUSE_DURATION
```
or
```bash
python nr-ride-analysis input_file_path --min_speed MIN_SPEED --min_pause_duration MIN_PAUSE_DURATION
```

---

## How to analyze

* Input either a single **.gpx** file or a **.zip** archive containing many GPX files.
* Adjust the **low‑speed threshold** and **minimum pause duration** to define what is considered a long pause.


---

Feel free to report any bugs or suggestions via [GitHub Issues](https://github.com/ozhanozen/nr-ride-analysis/issues).

 

