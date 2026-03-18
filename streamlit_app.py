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
        page_title="NR Ride Analysis",
        page_icon="🚴",
        layout="centered",
    )

    # ── Custom CSS for warm, colorful styling ─────────────────────────
    st.markdown("""
        <style>
        /* Main background with warm gradient */
        .stApp {
            background: linear-gradient(135deg, #FFF8E7 0%, #FFE8CC 100%);
        }

        /* All body text - dark for readability */
        p, div, span, li, label {
            color: #2C1810 !important;
        }

        /* Title styling */
        h1 {
            color: #D84315 !important;
            text-align: center;
            font-size: 3em !important;
            margin-bottom: 0.2em !important;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        }

        /* Subtitle styling */
        .subtitle {
            text-align: center;
            color: #E65100;
            font-size: 1.3em;
            margin-bottom: 2em;
            font-weight: 500;
        }

        /* Section headers */
        h3 {
            color: #D84315 !important;
            border-bottom: 3px solid #FF8A65;
            padding-bottom: 0.5em;
            margin-top: 1.5em !important;
        }

        h4 {
            color: #E65100 !important;
        }

        /* Input labels */
        .stNumberInput label, .stCheckbox label, .stFileUploader label {
            color: #BF360C !important;
            font-weight: 600 !important;
        }

        /* Input fields background */
        .stNumberInput input {
            background-color: white !important;
            color: #2C1810 !important;
        }

        /* File uploader */
        .stFileUploader > div {
            background-color: white;
            border: 2px dashed #FF8A65;
            border-radius: 10px;
            padding: 1em;
        }

        /* Button styling */
        .stButton > button {
            background: linear-gradient(135deg, #FF6F00 0%, #FF8F00 100%);
            color: white !important;
            font-size: 1.2em;
            font-weight: bold;
            padding: 0.75em 2em;
            border-radius: 30px;
            border: none;
            box-shadow: 0 4px 10px rgba(255,111,0,0.3);
            transition: all 0.3s ease;
        }

        .stButton > button:hover {
            background: linear-gradient(135deg, #E65100 0%, #FF6F00 100%);
            transform: translateY(-2px);
            box-shadow: 0 6px 15px rgba(255,111,0,0.4);
        }

        /* Download button styling */
        .stDownloadButton > button {
            background: linear-gradient(135deg, #2E7D32 0%, #43A047 100%);
            color: white !important;
            border-radius: 20px;
            font-weight: 600;
            padding: 0.6em 1.5em;
        }

        .stDownloadButton > button:hover {
            background: linear-gradient(135deg, #1B5E20 0%, #2E7D32 100%);
        }

        /* Instructions expander */
        .streamlit-expanderHeader {
            background-color: #FFE0B2 !important;
            border-radius: 10px;
            font-weight: 600;
            color: #BF360C !important;
        }

        .streamlit-expanderHeader:hover {
            background-color: #FFCC80 !important;
        }

        /* Expander content text */
        .streamlit-expanderContent {
            background-color: #FFF3E0;
            border-radius: 0 0 10px 10px;
            color: #2C1810 !important;
        }

        .streamlit-expanderContent p,
        .streamlit-expanderContent li {
            color: #3E2723 !important;
        }

        /* Success/Info/Warning boxes */
        .stSuccess, .stInfo, .stWarning {
            background-color: white !important;
            color: #2C1810 !important;
        }

        /* Code blocks */
        .stCodeBlock {
            background-color: #F5F5F5 !important;
        }

        /* Horizontal rule */
        hr {
            border-color: #FFAB91 !important;
        }

        /* Checkbox */
        .stCheckbox {
            color: #2C1810 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────
    st.markdown("# 🚴 NR Ride Analysis")
    st.markdown('<p class="subtitle">Analyze your endurance rides with ease</p>', unsafe_allow_html=True)

    st.markdown("")

    # ══════════════════════════════════════════════════════════════════
    # INTERACTIVE ELEMENTS - TOP SECTION
    # ══════════════════════════════════════════════════════════════════

    # ── File upload ───────────────────────────────────────────────────
    st.markdown("### 📂 Upload Your Ride File")
    uploaded_file = st.file_uploader(
        "Choose a GPX file or ZIP archive",
        type=["gpx", "zip"],
        accept_multiple_files=False,
        help="Single GPX file or ZIP containing multiple GPX files"
    )

    st.markdown("")

    # ── Parameter inputs ──────────────────────────────────────────────
    st.markdown("### ⚙️ Adjust Settings")

    col1, col2 = st.columns(2)
    with col1:
        min_speed = st.number_input(
            "🐌 Low-speed threshold (m/s)",
            value=0.1,
            step=0.001,
            format="%.3f",
            help="Points moving slower than this are considered part of a pause.",
        )
    with col2:
        min_pause = st.number_input(
            "⏱️ Minimum pause duration (seconds)",
            value=240,
            step=10,
            help="Only pauses longer than this will be detected.",
        )

    enable_geocoding = st.checkbox(
        "🌍 Enable location names (reverse geocoding)",
        value=False,
        help="Fetch readable location names for each pause. Requires internet and adds ~1 second per unique location.",
    )

    st.markdown("")

    # ── Process button ────────────────────────────────────────────────
    process_clicked = uploaded_file is not None and st.button("🚀 Analyze My Ride", type="primary", use_container_width=True)

    # ══════════════════════════════════════════════════════════════════
    # INSTRUCTIONS - BOTTOM SECTION
    # ══════════════════════════════════════════════════════════════════

    st.markdown("---")

    with st.expander("📖 How to Use This App", expanded=False):
        st.markdown("""
        #### Quick Start Guide

        1. **Upload your file** 📤
           - Single GPX file from your ride
           - ZIP archive containing multiple GPX files for batch processing

        2. **Configure parameters** 🎛️
           - **Low-speed threshold**: Speed below which movement is considered a pause (default: 0.1 m/s)
           - **Minimum pause duration**: Only pauses longer than this will be detected (default: 240 seconds/4 minutes)

        3. **Optional: Enable geocoding** 🗺️
           - Get readable location names for each pause
           - Requires internet connection
           - May add processing time

        4. **Click Analyze** ✨
           - Processing summary will appear below
           - Download your trimmed file and Excel summary
           - Maps links are clickable - copy to your browser to view locations

        #### What This App Does

        This tool analyzes endurance rides by detecting long breaks/pauses in your GPX files and provides:
        - Distance from start for each pause
        - Duration of each pause
        - Clickable location links (if geocoding enabled)
        - Excel summary with all details
        - Trimmed GPX file(s) for further analysis

        Perfect for long-distance cycling, audax rides, and endurance training analysis!
        """)

    with st.expander("ℹ️ About This Project", expanded=False):
        st.markdown("""
        This is a personal project to analyze endurance rides. Anyone with similar interests
        can use this app and suggest improvements.

        **Feedback & Suggestions**
        Found a bug or have an idea? Please share via [GitHub Issues](https://github.com/nageshwar-reddy/nr-ride-analysis/issues)

        Happy riding! 🚴‍♂️💨
        """)

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════
    # PROCESSING & RESULTS
    # ══════════════════════════════════════════════════════════════════

    if process_clicked:
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
        st.markdown("### ✅ Analysis Complete!")
        st.success("Your ride has been analyzed! See the detailed summary below and download your files.")

        if enable_geocoding:
            st.info("💡 **Tip**: Map links in the output are clickable. Copy them to your browser to view the exact pause locations on a map.")

        st.markdown("#### 📊 Processing Summary")
        st.code(log_text, language="text")

        st.markdown("#### 💾 Download Your Files")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Download Trimmed GPX",
                data=trimmed_data,
                file_name=out_path.name,
                mime=mime,
                use_container_width=True
            )
        with col2:
            if excel_data:
                st.download_button(
                    label="📊 Download Excel Summary",
                    data=excel_data,
                    file_name=excel_path.name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.markdown('<div style="padding: 2em; text-align: center; color: #999;">No Excel summary available</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
