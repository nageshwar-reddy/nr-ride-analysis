"""
Streamlit Ride Analysis App

Run with:
    streamlit run streamlit_app.py

The app wraps the ``run_pause_trimmer`` function from *gpx_trimmer.py* to
trim long pauses from a single GPX track or a batch of tracks inside a ZIP
archive. Users can adjust the low‑speed threshold and minimum pause
duration used to identify long pauses.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path

import streamlit as st

from gpx_trimmer import run_pause_trimmer


def main() -> None:
    """Entry‑point for the Streamlit UI."""

    # ── Page config ────────────────────────────────────────────────────
    st.set_page_config(
        page_title="NR Ride Aanalysis",
        page_icon="🏃",
        layout="centered",
    )

    # ── Header / intro ────────────────────────────────────────────────
    st.title("NR Ride Analysis")

    st.markdown("A lightweight tool to analyse edurance rides.")

    st.markdown(
        "* I want to use this application analyse my endurance rides. "
        " Anyone with similar interests can use this app and suggest changes."
        " I inted to actively spend some of my free time in making this useful"
        " for me in improving my endurance.\n" 
        "* This application detects the long brekas in your ride GPX file "
        " and adds additional details like distance from the start, clickable location and more info\n",

    
    )
    st.markdown("")
    st.markdown(
        "Feel free to report any bugs or suggestions via [Github Issues](https://https://github.com/nageshwar-reddy/nr-ride-analysis/issues)."
    )
    st.markdown("---")

    st.subheader("How to Analyse")
    st.markdown(
        "* Upload either a single **.gpx** file or a **.zip** archive containing many GPX files.\n"
        "* Adjust the **low‑speed threshold** and **minimum pause duration** to define what is considered a"
        " long pause.\n"
        "* Click **Trim**; the processed file will be offered for download. You can also see the processing summary"
        " in the text area below.\n"
    )
    st.markdown("---")

    # ── File upload ───────────────────────────────────────────────────
    uploaded_file = st.file_uploader(
        "📂 Upload a GPX file or ZIP archive",
        type=["gpx", "zip"],
        accept_multiple_files=False,
    )

    # ── Parameter inputs ──────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        min_speed = st.number_input(
            "Low‑speed threshold (m/s)",
            value=0.1,
            step=0.001,
            format="%.3f",
            help="Points moving slower than this are considered part of a pause.",
        )
    with col2:
        min_pause = st.number_input(
            "Minimum pause duration (s)",
            value=240,
            step=1,
            help="Only pauses longer than this will be removed.",
        )

    st.markdown("---")
    enable_geocoding = st.checkbox(
        "🌍 Enable location lookup (reverse geocoding)",
        value=False,
        help="Fetch location names for each pause. Requires internet connection and may slow processing (~1 sec per unique location).",
    )

    # ── Process button ────────────────────────────────────────────────
    if uploaded_file is not None and st.button("Analyse"):
        with st.spinner("Processing... this may take a moment ☕"):
            # Save the upload to a temporary file so run_pause_trimmer can work with paths.
            with tempfile.TemporaryDirectory() as tmpdir:
                in_path = Path(tmpdir) / uploaded_file.name
                in_path.write_bytes(uploaded_file.getbuffer())

                # Capture stdout from run_pause_trimmer so we can show it in the UI.
                log_stream = io.StringIO()
                with contextlib.redirect_stdout(log_stream):
                    run_pause_trimmer(
                        str(in_path),
                        min_speed=float(min_speed),
                        min_pause_duration=int(min_pause),
                        enable_geocoding=enable_geocoding,
                    )
                log_text = log_stream.getvalue()

                # Determine where the trimmed file was written.
                out_path = in_path.with_stem(in_path.stem + "_trimmed")

                if not out_path.exists():
                    st.error("Processing completed but the trimmed file could not be found.")
                    st.code(log_text)
                    return

                # Read the trimmed GPX/ZIP for download.
                trimmed_data = out_path.read_bytes()
                mime = "application/zip" if out_path.suffix.lower() == ".zip" else "application/gpx+xml"

                # Check for Excel summary file
                excel_path = in_path.with_suffix(".xlsx")
                excel_data = None
                if excel_path.exists():
                    excel_data = excel_path.read_bytes()

        # ── Display results ───────────────────────────────────────────
        st.success("Done! See the summary below and download your trimmed file(s).")
        if enable_geocoding:
            st.info("💡 Tip: Maps links in the output below are clickable in most modern terminals. Copy the link to your browser to view the location.")
        st.code(log_text, language="text")

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Download trimmed file(s)",
                data=trimmed_data,
                file_name=out_path.name,
                mime=mime,
            )
        with col2:
            if excel_data:
                st.download_button(
                    label="📊 Download Excel summary",
                    data=excel_data,
                    file_name=excel_path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )


if __name__ == "__main__":
    main()
