#!/usr/bin/env python3
from __future__ import annotations

import copy
import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional, cast
import zipfile

import gpxpy
from gpxpy.gpx import GPX, GPXTrack, GPXTrackSegment
from geopy.distance import distance


def _hms(td: datetime.timedelta) -> str:
    """Format a timedelta as "Hh Mm Ss", omitting zero fields."""

    total = int(round(td.total_seconds()))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    parts: list[str] = []
    if h:
        parts.append(f"{h}h")
    if h or m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def _to_ist(dt: datetime.datetime) -> str:
    """Convert UTC datetime to IST time string (HH:MM:SS)."""
    ist_offset = datetime.timedelta(hours=5, minutes=30)
    ist_time = dt + ist_offset
    return ist_time.strftime("%H:%M:%S")


def _geocode_location(latitude: float, longitude: float, geocoder, cache: dict) -> str:
    """Reverse geocode with caching. Returns address or 'N/A' on failure."""
    import time

    # Round to ~1km precision for cache key
    cache_key = (round(latitude, 2), round(longitude, 2))

    if cache_key in cache:
        return cache[cache_key]

    try:
        time.sleep(1.1)  # Respect Nominatim rate limit (1 req/sec)
        location = geocoder.reverse(f"{latitude}, {longitude}", timeout=10)
        address = location.address if location else "N/A"
        cache[cache_key] = address
        return address
    except Exception:
        cache[cache_key] = "N/A"
        return "N/A"


def _print_pause_summary(stats: dict, *, tz_offset: int = 0, enable_geocoding: bool = False) -> None:
    """Human-readable reporting of pause-trimming operation.

    Args:
        stats: dict returned by ``_trim_track`` / ``run_pause_trimmer``.
        tz_offset: Kept for backward compatibility but no longer used.
        enable_geocoding: Whether to perform reverse geocoding for location names.
    """

    if "activity_start" in stats:
        t0 = stats["activity_start"]
    elif stats["pauses"]:
        t0 = min(p["start"] for p in stats["pauses"])
    else:  # no pauses found
        t0 = None

    # Initialize geocoder if enabled
    geocoder = None
    geo_cache = {}
    if enable_geocoding:
        from geopy.geocoders import Nominatim
        geocoder = Nominatim(user_agent="gpx_trimmer")

    print(f"Activity date  {stats['activity_start']:%Y-%m-%d}")
    print(f"Start time  {stats['activity_start']:%H:%M:%S} UTC")
    print(" ")
    print(f"{'Pause':>5}  {'IST Time':>10}  {'Duration':>12}  {'Removed':>12}  "
          f"{'Drift':>9}  {'Cum.Dist':>10}  {'Relative time':>15}  {'Location':>30}  {'Maps Link':>45}")

    for i, p in enumerate(stats["pauses"], 1):
        # Format Δt as HH:MM:SS (zero-padded, hours may exceed 24)
        if t0 is not None:
            rel_td = p["start"] - t0
            total = int(round(rel_td.total_seconds()))
            hh, rem = divmod(total, 3600)
            mm, ss = divmod(rem, 60)
            rel = f"{hh:02d}:{mm:02d}:{ss:02d}"
        else:
            rel = "—"

        gap = _hms(p["gap"])
        cut = _hms(p["removed"])
        drift = f"{round(p['drift']):>3}m"

        # NEW: Cumulative distance
        cum_dist = f"{p.get('cumulative_dist', 0)/1000:.2f} km"

        # NEW: IST time
        ist_time = _to_ist(p["start"])

        # NEW: Location
        if enable_geocoding and geocoder and 'latitude' in p:
            location = _geocode_location(p['latitude'], p['longitude'], geocoder, geo_cache)
            location = location[:28] + ".." if len(location) > 30 else location  # Truncate
        else:
            location = "—"

        # NEW: Google Maps link
        if 'latitude' in p and 'longitude' in p:
            maps_link = f"https://maps.google.com/?q={p['latitude']},{p['longitude']}"
        else:
            maps_link = "—"

        print(f"{i:>5}  {ist_time:>10}  {gap:>12}  {cut:>12}  {drift:>9}  "
              f"{cum_dist:>10}  {rel:>15}  {location:>30}  {maps_link}")

    print(" ")
    print(f"Original elapsed time {_hms(stats['orig_elapsed']):>12}")
    print(f"Trimmed elapsed time {_hms(stats['trimmed_elapsed']):>12}")
    print(f"Total pause time {_hms(stats['removed_time']):>12}")
    print("-" * 55)


def _write_excel_summary(stats: dict, output_path: Path, *, enable_geocoding: bool = False) -> None:
    """Write pause summary to an Excel file.

    Args:
        stats: dict returned by ``_trim_track`` containing pause information.
        output_path: Path where the Excel file should be saved.
        enable_geocoding: Whether geocoding was enabled (for location column).
    """
    import pandas as pd

    if not stats["pauses"]:
        return  # No pauses to write

    # Determine activity start for relative time calculation
    if "activity_start" in stats:
        t0 = stats["activity_start"]
    elif stats["pauses"]:
        t0 = min(p["start"] for p in stats["pauses"])
    else:
        t0 = None

    # Initialize geocoder if needed
    geocoder = None
    geo_cache = {}
    if enable_geocoding:
        from geopy.geocoders import Nominatim
        geocoder = Nominatim(user_agent="gpx_trimmer")

    # Build data rows
    rows = []
    for i, p in enumerate(stats["pauses"], 1):
        # Relative time
        if t0 is not None:
            rel_td = p["start"] - t0
            total = int(round(rel_td.total_seconds()))
            hh, rem = divmod(total, 3600)
            mm, ss = divmod(rem, 60)
            rel_time = f"{hh:02d}:{mm:02d}:{ss:02d}"
        else:
            rel_time = "—"

        # Duration and removed time
        gap_seconds = p["gap"].total_seconds()
        removed_seconds = p["removed"].total_seconds()

        # Formatted duration for display
        duration_formatted = _hms(p["gap"])

        # Cumulative distance
        cum_dist_km = p.get('cumulative_dist', 0) / 1000

        # IST time
        ist_time = _to_ist(p["start"])

        # Location
        location = "—"
        if enable_geocoding and geocoder and 'latitude' in p:
            location = _geocode_location(p['latitude'], p['longitude'], geocoder, geo_cache)

        # Google Maps link
        maps_link = ""
        if 'latitude' in p and 'longitude' in p:
            maps_link = f"https://maps.google.com/?q={p['latitude']},{p['longitude']}"

        rows.append({
            "Pause #": i,
            "IST Time": ist_time,
            "Duration": duration_formatted,
            "Drift (meters)": round(p['drift']),
            "Cumulative Distance (km)": round(cum_dist_km, 2),
            "Google Maps Link": maps_link,
            "Location": location,
            "Duration (seconds)": gap_seconds,
            "Relative Time": rel_time,
            "Latitude": p.get('latitude', ''),
            "Longitude": p.get('longitude', '')
        })

    # Create DataFrame
    df = pd.DataFrame(rows)

    # Add summary information as separate sheet data
    summary_data = {
        "Metric": [
            "Activity Date",
            "Start Time (UTC)",
            "Original Elapsed Time",
            "Trimmed Elapsed Time",
            "Total Pause Time Removed"
        ],
        "Value": [
            stats['activity_start'].strftime('%Y-%m-%d'),
            stats['activity_start'].strftime('%H:%M:%S'),
            _hms(stats['orig_elapsed']),
            _hms(stats['trimmed_elapsed']),
            _hms(stats['removed_time'])
        ]
    }
    summary_df = pd.DataFrame(summary_data)

    # Write to Excel with multiple sheets
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Pauses', index=False)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)

        # Define styles
        header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF', size=11)
        alt_fill = PatternFill(start_color='E7E6E6', end_color='E7E6E6', fill_type='solid')
        border = Border(
            left=Side(style='thin', color='D3D3D3'),
            right=Side(style='thin', color='D3D3D3'),
            top=Side(style='thin', color='D3D3D3'),
            bottom=Side(style='thin', color='D3D3D3')
        )
        center_align = Alignment(horizontal='center', vertical='center')
        left_align = Alignment(horizontal='left', vertical='center')

        # Format Pauses sheet
        ws_pauses = writer.sheets['Pauses']

        # Style header row
        for col_idx, cell in enumerate(ws_pauses[1], start=1):
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
            cell.border = border

            # Add note to Duration (seconds) header
            if col_idx == 8:  # Duration (seconds) column (now at position 8)
                cell.font = Font(bold=True, color='FFFFFF', size=9, italic=True)
                from openpyxl.comments import Comment
                cell.comment = Comment("Numeric value for pivot tables and analysis", "GPX Trimmer")

        # Style data rows
        for row_idx, row in enumerate(ws_pauses.iter_rows(min_row=2, max_row=len(df)+1), start=2):
            # Alternating row colors
            if row_idx % 2 == 0:
                fill = alt_fill
            else:
                fill = PatternFill(fill_type=None)

            for col_idx, cell in enumerate(row, start=1):
                cell.border = border
                cell.fill = fill

                # Center align specific columns: Pause #, IST Time, Duration, Drift, Cum Dist, Duration(sec), Relative Time
                if col_idx in [1, 2, 3, 4, 5, 8, 9]:
                    cell.alignment = center_align
                else:
                    cell.alignment = left_align

                # Make Duration (seconds) column subtle - for analysis/pivot
                if col_idx == 8:  # Duration (seconds) column (now at position 8)
                    cell.font = Font(color='808080', size=9)  # Gray text, smaller font

                # Format Google Maps Link as hyperlink
                if col_idx == 6 and cell.value:  # Google Maps Link column (now at position 6)
                    cell.hyperlink = cell.value
                    cell.font = Font(color='0563C1', underline='single')
                    cell.value = 'View on Maps'

        # Auto-adjust column widths
        for col_idx, column in enumerate(df.columns, start=1):
            column_letter = get_column_letter(col_idx)
            max_length = len(str(column)) + 2
            for cell in ws_pauses[column_letter][1:]:
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            ws_pauses.column_dimensions[column_letter].width = min(max_length + 2, 50)

        # Freeze header row
        ws_pauses.freeze_panes = 'A2'

        # Format Summary sheet
        ws_summary = writer.sheets['Summary']

        # Style header row
        for cell in ws_summary[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
            cell.border = border

        # Style data rows
        for row_idx, row in enumerate(ws_summary.iter_rows(min_row=2, max_row=len(summary_df)+1), start=2):
            if row_idx % 2 == 0:
                fill = alt_fill
            else:
                fill = PatternFill(fill_type=None)

            for cell in row:
                cell.border = border
                cell.fill = fill
                cell.alignment = left_align
                cell.font = Font(size=10)

        # Auto-adjust column widths for summary
        for col_idx in range(1, len(summary_df.columns) + 1):
            column_letter = get_column_letter(col_idx)
            max_length = 0
            for cell in ws_summary[column_letter]:
                try:
                    if cell.value and len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            ws_summary.column_dimensions[column_letter].width = max_length + 4

        # Make Metric column bold in summary
        for row in ws_summary.iter_rows(min_row=2, max_row=len(summary_df)+1, min_col=1, max_col=1):
            for cell in row:
                cell.font = Font(bold=True, size=10)

    print(f"Excel summary saved: {output_path.name}")


def _decode_name(info: zipfile.ZipInfo) -> str:
    """Return a proper string for *info.filename*.

    Some zips lack the UTF-8 flag; repair their names.
    """
    # bit 11 set → filename is already UTF-8
    if info.flag_bits & 0x800:
        return info.filename
    raw = info.filename.encode("cp437")  # undo zipfile's default decoding
    try:
        return raw.decode("utf-8")  # most likely correct
    except UnicodeDecodeError:
        return raw.decode("latin-1")  # graceful fallback


def _ts(t: Optional[datetime.datetime]) -> datetime.datetime:
    """Return *t* if it's a datetime, else raise."""
    if t is None:
        raise ValueError("GPX point is missing its <time> stamp")
    return cast(datetime.datetime, t)


def _trim_track(original: GPX, *, min_speed: float = 0.5, min_pause_duration: int = 600) -> Tuple[str, Dict]:
    """
    Trim long, low-speed pauses from a GPX track and shift all subsequent
    timestamps backward so that *elapsed time equals true moving time*.

    Args:
        original: The parsed GPX object to trim.
        min_speed: Speed threshold, in m s⁻¹, below which motion is considered
            stationary.
        min_pause_duration: Minimum pause length, in seconds, that must be sustained
            before it is removed.

    Returns:
        xml: The trimmed GPX, serialized as a single XML string with all
            namespace information preserved.
        stats: A dictionary containing
            * ``pauses``        – list of removed-pause dicts
            * ``removed_time``  – total pause time as ``timedelta``
            * ``pause_drift``  – total "drift" distance in metres
            * ``cum_shift``     – cumulative timestamp shift
            * ``orig_elapsed``  – elapsed time before trimming
            * ``trimmed_elapsed`` – elapsed time after trimming

    Notes:
        soft pause: *Sequence of points within ONE segment* whose instantaneous speed
            drops below `min_speed`. We keep just enough of the pause to cover the drift
            distance at the *average moving speed so far* and cut the rest.
        hard pause: Gap between two consecutive segments. Same rule: we keep the minimum time
            needed to traverse the straight- line distance at average speed and trim the excess.
        Returned `stats["pauses"]` rows therefore show gap ≥ removed ≥ 0  for **both** pause kinds.
    """
    # ── boilerplate: deep-copy and bookkeeping ──────────────────────────────
    trimmed = copy.deepcopy(original)
    trimmed.tracks = []  # we rebuild tracks from scratch

    stats = {  # aggregate totals + pause list
        "pauses": [],  # list[dict]
        "removed_time": datetime.timedelta(),
        "pause_drift": 0.0,
        "cum_shift": datetime.timedelta(),
    }

    # helper: clone → time-shift → append, keeping timestamps strictly monotonic
    def _append(dst_seg, src_pt, *, shift: datetime.timedelta, last_time: datetime.datetime | None):
        new = copy.deepcopy(src_pt)
        new.time -= shift  # apply global time shift

        # GPX consumers need monotonically increasing timestamps
        if last_time and new.time <= last_time:
            new.time = last_time + datetime.timedelta(milliseconds=1)
        dst_seg.points.append(new)
        return new.time  # → becomes the next last_time

    cum_shift = datetime.timedelta()  # total time removed so far
    cumulative_dist = 0.0  # total distance traveled (for pause tracking)

    # ────────────────────────── iterate over tracks & segments ──────────────
    for src_trk in original.tracks:
        dst_trk = GPXTrack()
        dst_trk.name = src_trk.name
        dst_trk.type = src_trk.type
        trimmed.tracks.append(dst_trk)

        moving_dist = moving_time = 0.0  # for average-speed estimates

        for seg_idx, src_seg in enumerate(src_trk.segments):
            dst_seg = GPXTrackSegment()
            dst_trk.segments.append(dst_seg)
            if not src_seg.points:
                continue

            last_written = _append(dst_seg, src_seg.points[0], shift=cum_shift, last_time=None)

            # state for a potential soft pause
            p_start_idx = None  # first low-speed pt index
            p_start_time = None  # timestamp of preceding pt
            p_drift = 0.0  # metres drifted during pause

            pts = src_seg.points
            for i in range(1, len(pts)):
                prev, curr = pts[i - 1], pts[i]
                dt = (_ts(curr.time) - _ts(prev.time)).total_seconds()
                if dt <= 0:  # duplicate / rewind in source
                    last_written = _append(dst_seg, curr, shift=cum_shift, last_time=last_written)
                    continue

                # instantaneous speed between two source points
                d_m = distance((prev.latitude, prev.longitude), (curr.latitude, curr.longitude)).m
                v = d_m / dt

                # ── LOW-SPEED block ──────────────────────────────────────
                if v < min_speed:  # inside a soft pause
                    if p_start_idx is None:  # first time we dip below v_min
                        p_start_idx, p_start_time = i, prev.time
                        p_drift = 0.0
                    p_drift += d_m
                    continue

                # ── LEAVING a soft pause ────────────────────────────────
                if p_start_idx is not None:
                    gap = _ts(curr.time) - _ts(p_start_time)

                    if gap.total_seconds() >= min_pause_duration:
                        # amount of that gap we must PRESERVE to maintain speed
                        v_avg = moving_dist / moving_time if moving_time else 0.0
                        keep = p_drift / v_avg if v_avg else 1.0
                        keep = min(keep, gap.total_seconds())  # never > gap
                        cut = gap - datetime.timedelta(seconds=keep)
                        # record stats
                        stats["pauses"].append(dict(
                            start=p_start_time,
                            gap=gap,
                            removed=cut,
                            drift=p_drift,
                            cumulative_dist=cumulative_dist,
                            latitude=prev.latitude,
                            longitude=prev.longitude
                        ))
                        stats["removed_time"] += cut
                        stats["pause_drift"] += p_drift
                        stats["cum_shift"] += cut
                        cum_shift += cut
                    else:  # pause too short → keep intact
                        for j in range(p_start_idx, i + 1):
                            last_written = _append(dst_seg, pts[j], shift=cum_shift, last_time=last_written)

                    p_start_idx = p_start_time = None
                    p_drift = 0.0

                # point is normal moving data
                last_written = _append(dst_seg, curr, shift=cum_shift, last_time=last_written)
                moving_dist += d_m
                moving_time += dt
                cumulative_dist += d_m

            # ── SOFT pause that reaches end of segment ──────────────────
            if p_start_idx is not None:
                gap = _ts(pts[-1].time) - _ts(p_start_time)
                if gap.total_seconds() >= min_pause_duration:
                    v_avg = moving_dist / moving_time if moving_time else 0.0
                    keep = p_drift / v_avg if v_avg else 1.0
                    keep = min(keep, gap.total_seconds())
                    cut = gap - datetime.timedelta(seconds=keep)

                    stats["pauses"].append(dict(
                        start=p_start_time,
                        gap=gap,
                        removed=cut,
                        drift=p_drift,
                        cumulative_dist=cumulative_dist,
                        latitude=pts[p_start_idx - 1].latitude,
                        longitude=pts[p_start_idx - 1].longitude
                    ))
                    stats["removed_time"] += cut
                    stats["pause_drift"] += p_drift
                    stats["cum_shift"] += cut
                    cum_shift += cut
                else:  # short pause → keep
                    for j in range(p_start_idx, len(pts)):
                        last_written = _append(dst_seg, pts[j], shift=cum_shift, last_time=last_written)

            # ── HARD pause (gap between segments) ───────────────────────
            nxt = seg_idx + 1
            if nxt < len(src_trk.segments) and src_trk.segments[nxt].points:
                last_pt = src_seg.points[-1]
                first_nx = src_trk.segments[nxt].points[0]
                dt_gap = (_ts(first_nx.time) - _ts(last_pt.time)).total_seconds()
                if dt_gap >= min_pause_duration:
                    d_gap = distance((last_pt.latitude, last_pt.longitude), (first_nx.latitude, first_nx.longitude)).m
                    v_avg = moving_dist / moving_time if moving_time else 0.0
                    keep = d_gap / v_avg if v_avg else 1.0
                    keep = min(keep, dt_gap)
                    cut = datetime.timedelta(seconds=dt_gap - keep)

                    stats["pauses"].append(dict(
                        start=last_pt.time,
                        gap=datetime.timedelta(seconds=dt_gap),
                        removed=cut,
                        drift=d_gap,
                        cumulative_dist=cumulative_dist,
                        latitude=last_pt.latitude,
                        longitude=last_pt.longitude
                    ))
                    stats["removed_time"] += cut
                    stats["pause_drift"] += d_gap
                    stats["cum_shift"] += cut
                    cum_shift += cut

    # ── overall elapsed times ───────────────────────────────────────────
    stats["activity_start"] = _ts(original.tracks[0].segments[0].points[0].time)
    stats["orig_elapsed"] = _ts(original.tracks[-1].segments[-1].points[-1].time) - _ts(
        original.tracks[0].segments[0].points[0].time
    )
    stats["trimmed_elapsed"] = _ts(trimmed.tracks[-1].segments[-1].points[-1].time) - _ts(
        trimmed.tracks[0].segments[0].points[0].time
    )

    return trimmed.to_xml(prettyprint=True), stats


def run_pause_trimmer(
    input_path: str | Path,
    *,
    min_speed: float = 0.1,
    min_pause_duration: int = 240,
    enable_geocoding: bool = False,
) -> None:
    """
    Trim every GPX track in *input_path*.

    Args:
        input_path: Either a single ``.gpx`` file or a ``.zip`` containing many GPX
            files (any sub-folder layout is preserved).
        min_speed : Low-speed threshold in m s⁻¹ (default 0.1).
        min_pause_duration : Minimum pause duration in seconds before it is removed (default 600).
        enable_geocoding : Enable reverse geocoding to show location names (default False).
    """
    input_path = Path(input_path)

    # ── helper for one GPX blob ────────────────────────────────────
    def _trim_and_report(xml: str, label: str) -> tuple[str, dict]:
        gpx = gpxpy.parse(xml)
        xml_out, stats = _trim_track(gpx, min_speed=min_speed, min_pause_duration=min_pause_duration)

        print(f"\n=== {label} ===\n")
        _print_pause_summary(stats, tz_offset=0, enable_geocoding=enable_geocoding)
        return xml_out, stats

    # ── single GPX on disk ────────────────────────────────────────
    if input_path.suffix.lower() != ".zip":
        xml_in = input_path.read_text(encoding="utf-8", errors="replace")
        xml_out, stats = _trim_and_report(xml_in, input_path.name)

        out_file = input_path.with_stem(input_path.stem + "_trimmed")
        out_file.write_text(xml_out, encoding="utf-8")
        print(f"\nCreated {out_file.name}")

        # Write Excel summary
        excel_file = input_path.with_suffix(".xlsx")
        _write_excel_summary(stats, excel_file, enable_geocoding=enable_geocoding)

        return

    # ── ZIP archive ───────────────────────────────────────────────
    out_zip = input_path.with_stem(input_path.stem + "_trimmed")
    trimmed_count = 0
    excel_files = []

    with zipfile.ZipFile(input_path) as zin, zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zout:

        # walk all entries
        for member in zin.infolist():
            arcname = _decode_name(member)  # repaired text
            p = Path(arcname)

            # skip non-GPX or macOS "resource-fork" files
            if p.suffix.lower() != ".gpx" or p.name.startswith("._"):
                continue

            # read → trim → write back
            xml_in = zin.read(member).decode("utf-8", errors="replace")
            xml_out, stats = _trim_and_report(xml_in, p.name)

            out_name = p.with_stem(p.stem + "_trimmed").as_posix()
            zout.writestr(out_name, xml_out.encode("utf-8"))
            trimmed_count += 1

            # Write Excel summary for this GPX file
            excel_file = input_path.parent / f"{p.stem}.xlsx"
            _write_excel_summary(stats, excel_file, enable_geocoding=enable_geocoding)
            excel_files.append(excel_file.name)

    if trimmed_count:
        print(f"\nCreated {out_zip.name} with {trimmed_count} trimmed track(s).")
        if excel_files:
            print(f"Created {len(excel_files)} Excel summary file(s): {', '.join(excel_files)}")
    else:
        print("No .gpx files found in the archive.")


if __name__ == "__main__":
    """Main entry point for command-line usage."""

    import argparse

    parser = argparse.ArgumentParser(prog="gpx_trimmer")
    parser.add_argument(
        "--min_speed",
        default=0.1,
        type=float,
        help="Minimum speed in m/s; points below this are considered part of a pause.",
    )
    parser.add_argument(
        "--min_pause_duration",
        default=240,
        type=int,
        help="Minimum pause duration in seconds; pauses longer than this will be trimmed.",
    )
    parser.add_argument(
        "--enable_geocoding",
        action="store_true",
        help="Enable reverse geocoding to show location names (requires internet).",
    )
    parser.add_argument("input_file_path", help="Input file path")
    args = parser.parse_args()

    run_pause_trimmer(
        args.input_file_path,
        min_speed=args.min_speed,
        min_pause_duration=args.min_pause_duration,
        enable_geocoding=args.enable_geocoding
    )
