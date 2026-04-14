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
import datetime
import io
import tempfile
from pathlib import Path

import streamlit as st

from gpx_trimmer import run_pause_trimmer


_IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def _upload_to_gcs(local_path: Path, original_filename: str) -> tuple[str, str]:
    """Upload Excel file to GCS.

    Returns (blob_name, gcs_console_url) on success, raises on failure.
    Filename is prefixed with IST timestamp in YYYYMMDDHHmmSS format.
    """
    from google.cloud import storage
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_info(
        dict(st.secrets["gcs"]),
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    bucket_name = st.secrets["gcs_config"]["bucket_name"]
    client = storage.Client(
        credentials=credentials,
        project=st.secrets["gcs"]["project_id"],
    )
    bucket = client.bucket(bucket_name)

    now_ist = datetime.datetime.now(_IST)
    timestamp = now_ist.strftime("%Y%m%d%H%M%S")
    stem = Path(original_filename).stem
    blob_name = f"analyses/{now_ist:%Y-%m-%d}/{timestamp}_{stem}.xlsx"

    blob = bucket.blob(blob_name)
    blob.upload_from_filename(str(local_path))

    console_url = (
        f"https://console.cloud.google.com/storage/browser/_details/"
        f"{bucket_name}/{blob_name}?project={st.secrets['gcs']['project_id']}"
    )
    return blob_name, console_url


def _send_email(subject: str, body: str) -> None:
    """Send a notification email to the admin address via Gmail SMTP."""
    import smtplib
    from email.mime.text import MIMEText

    smtp_user = st.secrets["email"]["smtp_user"]
    smtp_password = st.secrets["email"]["smtp_password"]
    recipient = st.secrets["email"]["recipient"]

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = recipient

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def main() -> None:
    """Entry‑point for the Streamlit UI."""

    # ── Page config ────────────────────────────────────────────────────
    st.set_page_config(
        page_title="NR Ride Analysis",
        page_icon="🚴",
        layout="centered",
    )

    # ── Custom CSS for layout and spacing optimization ─────────────────
    st.markdown("""
        <style>
        /* Container padding for better spacing */
        .main {
            padding: 1rem 1rem;
        }

        /* Title styling - spacing only */
        h1 {
            text-align: center;
            font-size: 2.5em !important;
            margin-bottom: 0.3em !important;
            margin-top: 0 !important;
        }

        /* Subtitle styling - optimized spacing */
        .subtitle {
            text-align: center;
            font-size: 1.1em;
            margin-bottom: 0.8em !important;
            margin-top: 0 !important;
            font-weight: 500;
            line-height: 1.4;
        }

        /* Section headers - tighter spacing */
        h3 {
            padding-bottom: 0.5em;
            margin-top: 0.8em !important;
            margin-bottom: 0.8em !important;
            font-size: 1.4em !important;
        }

        /* Input labels */
        .stNumberInput label, .stCheckbox label, .stFileUploader label {
            font-weight: 600 !important;
            font-size: 0.95em !important;
        }

        /* File uploader */
        .stFileUploader > div {
            border-radius: 10px;
            padding: 1.5em;
            margin-bottom: 1em !important;
        }

        .stFileUploader section {
            border-radius: 10px;
        }

        /* File uploader button - Browse files */
        .stFileUploader button {
            font-weight: bold !important;
            font-size: 1em !important;
            padding: 0.5em 1.5em !important;
            border-radius: 8px !important;
        }

        /* Button styling */
        .stButton > button {
            font-size: 1.1em;
            font-weight: bold;
            padding: 0.7em 2em;
            border-radius: 30px;
            transition: all 0.3s ease;
            width: auto !important;
        }

        .stButton > button:hover {
            transform: translateY(-2px);
        }

        /* Download button styling */
        .stDownloadButton > button {
            border-radius: 20px;
            font-weight: 600;
            padding: 0.6em 1.5em;
        }

        /* Instructions expander */
        .streamlit-expanderHeader {
            border-radius: 10px;
            font-weight: 600;
        }

        .streamlit-expanderHeader:hover {
        }

        /* Expander content text */
        .streamlit-expanderContent {
            border-radius: 0 0 10px 10px;
        }

        /* Horizontal rule */
        hr {
            margin: 0.8em 0 !important;
        }

        /* Checkbox */
        .stCheckbox {
            margin-bottom: 1em !important;
        }

        /* Column spacing optimization */
        [data-testid="column"] {
            gap: 1em;
        }

        /* Markdown spacing optimization */
        .stMarkdown {
            margin-bottom: 0.5em !important;
        }

        /* Responsive design for mobile */
        @media (max-width: 768px) {
            h1 {
                font-size: 2em !important;
                margin-bottom: 0.4em !important;
            }
            
            .subtitle {
                font-size: 1em;
                margin-bottom: 0.6em !important;
            }
            
            h3 {
                font-size: 1.2em !important;
                margin-top: 0.6em !important;
            }
            
            .stButton > button {
                font-size: 1em;
                padding: 0.6em 1.5em;
                width: 100% !important;
            }
        }

        /* Responsive design for tablets */
        @media (max-width: 1024px) {
            .main {
                padding: 0.8rem 0.5rem;
            }
        }
        </style>
    """, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────
    st.markdown("# 🚴 NR Ride Analysis")
    st.markdown('<p class="subtitle">Analyze your endurance rides with ease</p>', unsafe_allow_html=True)

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
            value=120,
            step=10,
            help="Only pauses longer than this will be detected.",
        )

    enable_geocoding = st.checkbox(
        "🌍 Enable location names (reverse geocoding)",
        value=False,
        help="Fetch readable location names for each pause. Requires internet and adds ~1 second per unique location.",
    )

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
           - **Minimum pause duration**: Only pauses longer than this will be detected (default: 120 seconds/2 minutes)

        3. **Optional: Enable geocoding** 🗺️
           - Get readable location names for each pause
           - Requires internet connection
           - May add processing time

        4. **Click Analyze** ✨
           - Processing summary will appear below
           - Download the Excel summary with all details
           - Maps links are clickable - copy to your browser to view locations

        #### What This App Does

        This tool analyzes endurance rides by detecting long breaks/pauses in your GPX files and provides:
        - Distance from start for each pause
        - Duration of each pause
        - Per-segment metrics: avg speed, cadence, heart rate, power, elevation gain/loss
        - Clickable location links (if geocoding enabled)
        - Excel summary with all details

        Perfect for long-distance cycling, audax rides, and endurance training analysis!
        """)

    with st.expander("ℹ️ About This Project", expanded=False):
        st.markdown("""
        This is a personal project to analyze endurance rides. Anyone with similar interests
        can use this app and suggest improvements.

        **Data & Privacy**
        Analyzed results are saved anonymously for research and improvement purposes.
        No personally identifiable information is collected.

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

                # Check for Excel summary file
                excel_path = in_path.with_suffix(".xlsx")
                excel_data = None
                if excel_path.exists():
                    excel_data = excel_path.read_bytes()

                    # Upload to GCS while the temp file still exists on disk
                    try:
                        blob_name, console_url = _upload_to_gcs(excel_path, uploaded_file.name)
                        try:
                            _send_email(
                                subject=f"✅ Ride Analysis Saved: {uploaded_file.name}",
                                body=(
                                    f"File uploaded successfully to Google Cloud Storage.\n\n"
                                    f"Original file : {uploaded_file.name}\n"
                                    f"Stored as     : {blob_name}\n\n"
                                    f"View in GCS console:\n{console_url}"
                                ),
                            )
                        except Exception:
                            pass  # email failure is silent
                    except Exception as upload_err:
                        try:
                            _send_email(
                                subject=f"❌ Ride Analysis Upload Failed: {uploaded_file.name}",
                                body=(
                                    f"Cloud upload failed for file: {uploaded_file.name}\n\n"
                                    f"Error:\n{upload_err}"
                                ),
                            )
                        except Exception:
                            pass  # email failure is silent

        # ── Display results ───────────────────────────────────────────
        st.markdown("### ✅ Analysis Complete!")
        st.success("Your ride has been analyzed! See the detailed summary below.")

        if enable_geocoding:
            st.info("💡 **Tip**: Map links in the output are clickable. Copy them to your browser to view the exact pause locations on a map.")

        st.markdown("#### 📊 Processing Summary")
        st.code(log_text, language="text")

        if excel_data:
            st.markdown("#### 💾 Download")
            st.download_button(
                label="📊 Download Excel Summary",
                data=excel_data,
                file_name=excel_path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )


if __name__ == "__main__":
    main()
