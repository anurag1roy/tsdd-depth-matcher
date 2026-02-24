"""
TSDD Depth Matcher

Matches depth points to the nearest TSDD segment (defined by start/end latitude/longitude)
and flags whether each depth point falls within a user-provided buffer distance.

Inputs:
1) TSDD file (CSV/XLSX/XLS) with columns for:
   - start latitude, start longitude
   - end latitude, end longitude
   - DFO start, DFO end
   - optional road name
2) Depth points file (CSV/XLSX/XLS) with columns for:
   - latitude, longitude, depth

Output:
- Excel file with original depth rows + nearest TSDD association + in-region flag
"""

import math
import os
from io import BytesIO

import numpy as np
import pandas as pd


EARTH_RADIUS_FEET = 20902231.0


def read_table(file_path):
    """Read CSV or Excel file into a DataFrame."""
    extension = os.path.splitext(file_path)[1].lower()
    if extension == ".csv":
        return pd.read_csv(file_path)
    if extension in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)
    raise ValueError(f"Unsupported file type: {extension}")


def read_table_from_upload(uploaded_file):
    """Read CSV or Excel from uploaded file-like object."""
    extension = os.path.splitext(uploaded_file.name)[1].lower()
    if extension == ".csv":
        uploaded_file.seek(0)
        return pd.read_csv(uploaded_file)
    if extension in [".xlsx", ".xls"]:
        uploaded_file.seek(0)
        return pd.read_excel(uploaded_file)
    raise ValueError(f"Unsupported file type: {extension}")


def find_column(df, aliases, required=True):
    """Find first matching column name by case-insensitive alias list."""
    normalized = {col.strip().lower(): col for col in df.columns}
    for alias in aliases:
        alias_key = alias.strip().lower()
        if alias_key in normalized:
            return normalized[alias_key]

    if required:
        raise ValueError(f"Missing required column. Expected one of: {aliases}")
    return None


def to_numeric_coordinates(df, lat_col, lon_col):
    """Convert coordinate columns to numeric and drop invalid rows."""
    out = df.copy()
    out[lat_col] = pd.to_numeric(out[lat_col], errors="coerce")
    out[lon_col] = pd.to_numeric(out[lon_col], errors="coerce")

    valid_mask = (
        out[lat_col].notna()
        & out[lon_col].notna()
        & (out[lat_col] >= -90)
        & (out[lat_col] <= 90)
        & (out[lon_col] >= -180)
        & (out[lon_col] <= 180)
    )
    removed = int((~valid_mask).sum())
    if removed > 0:
        print(f"Warning: Removed {removed} rows with invalid coordinates")
    return out.loc[valid_mask].copy()


def read_tsdd_segments(file_path):
    """Read and standardize TSDD segment rows."""
    df = read_table(file_path)
    return standardize_tsdd_segments(df)


def standardize_tsdd_segments(df):
    """Standardize TSDD segment DataFrame to required schema."""

    start_lat_col = find_column(df, ["start_lat", "start_latitude", "from_lat", "from_latitude", "s_lat"])
    start_lon_col = find_column(df, ["start_lon", "start_longitude", "from_lon", "from_longitude", "s_lon"])
    end_lat_col = find_column(df, ["end_lat", "end_latitude", "to_lat", "to_latitude", "e_lat"])
    end_lon_col = find_column(df, ["end_lon", "end_longitude", "to_lon", "to_longitude", "e_lon"])
    dfo_start_col = find_column(df, ["dfo_start", "start_dfo", "from_dfo"])
    dfo_end_col = find_column(df, ["dfo_end", "end_dfo", "to_dfo"])
    road_col = find_column(df, ["road", "road_name", "route", "route_name", "name"], required=False)

    standardized = df.rename(
        columns={
            start_lat_col: "start_latitude",
            start_lon_col: "start_longitude",
            end_lat_col: "end_latitude",
            end_lon_col: "end_longitude",
            dfo_start_col: "dfo_start",
            dfo_end_col: "dfo_end",
            **({road_col: "road"} if road_col else {}),
        }
    )

    standardized = to_numeric_coordinates(standardized, "start_latitude", "start_longitude")
    standardized = to_numeric_coordinates(standardized, "end_latitude", "end_longitude")
    standardized["dfo_start"] = pd.to_numeric(standardized["dfo_start"], errors="coerce")
    standardized["dfo_end"] = pd.to_numeric(standardized["dfo_end"], errors="coerce")

    standardized = standardized.reset_index(drop=True)
    standardized["segment_id"] = standardized.index + 1
    if "road" not in standardized.columns:
        standardized["road"] = pd.NA

    return standardized


def read_depth_points(file_path):
    """Read and standardize depth points."""
    df = read_table(file_path)
    return standardize_depth_points(df)


def standardize_depth_points(df):
    """Standardize depth-points DataFrame to required schema."""
    lat_col = find_column(df, ["latitude", "lat", "point_lat", "y"])
    lon_col = find_column(df, ["longitude", "lon", "long", "point_lon", "x"])
    depth_col = find_column(df, ["depth", "depth_value", "measured_depth"])

    standardized = df.rename(
        columns={
            lat_col: "latitude",
            lon_col: "longitude",
            depth_col: "depth",
        }
    )
    standardized = to_numeric_coordinates(standardized, "latitude", "longitude")
    standardized["depth"] = pd.to_numeric(standardized["depth"], errors="coerce")
    standardized = standardized.reset_index(drop=True)
    standardized["depth_point_id"] = standardized.index + 1
    return standardized


def to_local_feet(lat, lon, origin_lat, origin_lon):
    """Project lat/lon to local feet using equirectangular approximation."""
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    origin_lat_rad = math.radians(origin_lat)
    origin_lon_rad = math.radians(origin_lon)

    x = (lon_rad - origin_lon_rad) * math.cos(origin_lat_rad) * EARTH_RADIUS_FEET
    y = (lat_rad - origin_lat_rad) * EARTH_RADIUS_FEET
    return x, y


def point_to_segment_metrics_feet(point_lat, point_lon, start_lat, start_lon, end_lat, end_lon):
    """Return (distance_feet, position_fraction) for point to segment in local projection."""
    origin_lat = (start_lat + end_lat + point_lat) / 3.0
    origin_lon = (start_lon + end_lon + point_lon) / 3.0

    px, py = to_local_feet(point_lat, point_lon, origin_lat, origin_lon)
    ax, ay = to_local_feet(start_lat, start_lon, origin_lat, origin_lon)
    bx, by = to_local_feet(end_lat, end_lon, origin_lat, origin_lon)

    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    ab_len_sq = abx * abx + aby * aby

    if ab_len_sq == 0:
        return math.hypot(px - ax, py - ay), 0.0

    t = (apx * abx + apy * aby) / ab_len_sq
    t = max(0.0, min(1.0, t))

    nearest_x = ax + t * abx
    nearest_y = ay + t * aby
    return math.hypot(px - nearest_x, py - nearest_y), t


def point_to_segment_metrics_feet_vectorized(point_lats, point_lons, start_lat, start_lon, end_lat, end_lon):
    """Vectorized point-to-segment metrics for many points against one segment."""
    origin_lat = (start_lat + end_lat) / 2.0
    origin_lon = (start_lon + end_lon) / 2.0

    origin_lat_rad = math.radians(origin_lat)
    origin_lon_rad = math.radians(origin_lon)

    point_lat_rad = np.radians(point_lats)
    point_lon_rad = np.radians(point_lons)
    start_lat_rad = math.radians(start_lat)
    start_lon_rad = math.radians(start_lon)
    end_lat_rad = math.radians(end_lat)
    end_lon_rad = math.radians(end_lon)

    px = (point_lon_rad - origin_lon_rad) * math.cos(origin_lat_rad) * EARTH_RADIUS_FEET
    py = (point_lat_rad - origin_lat_rad) * EARTH_RADIUS_FEET
    ax = (start_lon_rad - origin_lon_rad) * math.cos(origin_lat_rad) * EARTH_RADIUS_FEET
    ay = (start_lat_rad - origin_lat_rad) * EARTH_RADIUS_FEET
    bx = (end_lon_rad - origin_lon_rad) * math.cos(origin_lat_rad) * EARTH_RADIUS_FEET
    by = (end_lat_rad - origin_lat_rad) * EARTH_RADIUS_FEET

    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    ab_len_sq = abx * abx + aby * aby

    if ab_len_sq == 0:
        distances = np.hypot(px - ax, py - ay)
        positions = np.zeros_like(distances)
        return distances, positions

    t = (apx * abx + apy * aby) / ab_len_sq
    t = np.clip(t, 0.0, 1.0)

    nearest_x = ax + t * abx
    nearest_y = ay + t * aby
    distances = np.hypot(px - nearest_x, py - nearest_y)
    return distances, t


def match_depth_to_tsdd_segments(depth_df, tsdd_df, buffer_feet, progress_callback=None):
    """Assign points only if they fall within buffer of a segment; no forced matching."""
    total_points = len(depth_df)
    total_segments = len(tsdd_df)

    point_lats = depth_df["latitude"].to_numpy(dtype=float)
    point_lons = depth_df["longitude"].to_numpy(dtype=float)

    best_distance = np.full(total_points, np.inf, dtype=float)
    best_segment_row_index = np.full(total_points, -1, dtype=int)
    best_position_fraction = np.full(total_points, np.nan, dtype=float)

    buffer_radians = buffer_feet / EARTH_RADIUS_FEET
    buffer_degrees_lat = math.degrees(buffer_radians)

    for seg_idx, (_, segment_row) in enumerate(tsdd_df.iterrows(), start=1):
        start_lat = float(segment_row["start_latitude"])
        start_lon = float(segment_row["start_longitude"])
        end_lat = float(segment_row["end_latitude"])
        end_lon = float(segment_row["end_longitude"])

        mid_lat = (start_lat + end_lat) / 2.0
        cos_mid = max(math.cos(math.radians(mid_lat)), 1e-6)
        buffer_degrees_lon = buffer_degrees_lat / cos_mid

        min_lat = min(start_lat, end_lat) - buffer_degrees_lat
        max_lat = max(start_lat, end_lat) + buffer_degrees_lat
        min_lon = min(start_lon, end_lon) - buffer_degrees_lon
        max_lon = max(start_lon, end_lon) + buffer_degrees_lon

        candidate_mask = (
            (point_lats >= min_lat)
            & (point_lats <= max_lat)
            & (point_lons >= min_lon)
            & (point_lons <= max_lon)
        )
        candidate_indices = np.where(candidate_mask)[0]
        if candidate_indices.size == 0:
            if progress_callback is not None:
                progress_callback(seg_idx, total_segments)
            continue

        candidate_lats = point_lats[candidate_indices]
        candidate_lons = point_lons[candidate_indices]
        candidate_distances, candidate_positions = point_to_segment_metrics_feet_vectorized(
            candidate_lats,
            candidate_lons,
            start_lat,
            start_lon,
            end_lat,
            end_lon,
        )

        in_buffer = candidate_distances <= buffer_feet
        if np.any(in_buffer):
            in_buffer_indices = candidate_indices[in_buffer]
            in_buffer_distances = candidate_distances[in_buffer]
            in_buffer_positions = candidate_positions[in_buffer]

            improves_best = in_buffer_distances < best_distance[in_buffer_indices]
            if np.any(improves_best):
                final_indices = in_buffer_indices[improves_best]
                best_distance[final_indices] = in_buffer_distances[improves_best]
                best_segment_row_index[final_indices] = int(segment_row.name)
                best_position_fraction[final_indices] = in_buffer_positions[improves_best]

        if progress_callback is not None:
            progress_callback(seg_idx, total_segments)

    output_df = depth_df.copy()
    output_df["matched_segment_id"] = pd.NA
    output_df["matched_road"] = pd.NA
    output_df["matched_dfo_start"] = pd.NA
    output_df["matched_dfo_end"] = pd.NA
    output_df["estimated_dfo"] = pd.NA
    output_df["nearest_distance_feet"] = pd.NA
    output_df["in_region"] = False

    matched_mask = best_segment_row_index >= 0
    matched_point_indices = np.where(matched_mask)[0]

    for point_idx in matched_point_indices:
        segment_idx = best_segment_row_index[point_idx]
        segment_row = tsdd_df.iloc[segment_idx]
        dfo_start = segment_row["dfo_start"]
        dfo_end = segment_row["dfo_end"]
        estimated_dfo = pd.NA
        if pd.notna(dfo_start) and pd.notna(dfo_end):
            estimated_dfo = float(dfo_start) + float(best_position_fraction[point_idx]) * (float(dfo_end) - float(dfo_start))

        output_df.at[point_idx, "matched_segment_id"] = int(segment_row["segment_id"])
        output_df.at[point_idx, "matched_road"] = segment_row.get("road", pd.NA)
        output_df.at[point_idx, "matched_dfo_start"] = dfo_start
        output_df.at[point_idx, "matched_dfo_end"] = dfo_end
        output_df.at[point_idx, "estimated_dfo"] = round(estimated_dfo, 3) if pd.notna(estimated_dfo) else pd.NA
        output_df.at[point_idx, "nearest_distance_feet"] = round(float(best_distance[point_idx]), 2)
        output_df.at[point_idx, "in_region"] = True

    return output_df


def build_segment_summary(result_df, tsdd_df):
    """Build per-segment summary including average in-region depth."""
    summary = tsdd_df[
        [
            "segment_id",
            "road",
            "start_latitude",
            "start_longitude",
            "end_latitude",
            "end_longitude",
            "dfo_start",
            "dfo_end",
        ]
    ].copy()

    matched_counts = result_df.groupby("matched_segment_id").size().rename("matched_point_count")

    in_region_df = result_df[result_df["in_region"]].copy()
    in_region_counts = in_region_df.groupby("matched_segment_id").size().rename("in_region_point_count")
    avg_depth = in_region_df.groupby("matched_segment_id")["depth"].mean().rename("average_depth_in_region")
    min_depth = in_region_df.groupby("matched_segment_id")["depth"].min().rename("min_depth_in_region")
    max_depth = in_region_df.groupby("matched_segment_id")["depth"].max().rename("max_depth_in_region")

    def _mean_without_outliers(depth_series):
        numeric_depth = pd.to_numeric(depth_series, errors="coerce").dropna()
        if numeric_depth.empty:
            return pd.NA

        mean_value = numeric_depth.mean()
        std_value = numeric_depth.std()

        if pd.isna(std_value) or std_value == 0:
            return float(mean_value)

        lower_bound = mean_value - std_value
        upper_bound = mean_value + std_value
        kept_values = numeric_depth[(numeric_depth >= lower_bound) & (numeric_depth <= upper_bound)]
        if kept_values.empty:
            return pd.NA
        return float(kept_values.mean())

    avg_depth_no_outliers = (
        in_region_df.groupby("matched_segment_id")["depth"]
        .apply(_mean_without_outliers)
        .rename("average_depth_in_region_no_outliers")
    )

    summary = summary.merge(matched_counts, left_on="segment_id", right_index=True, how="left")
    summary = summary.merge(in_region_counts, left_on="segment_id", right_index=True, how="left")
    summary = summary.merge(avg_depth, left_on="segment_id", right_index=True, how="left")
    summary = summary.merge(avg_depth_no_outliers, left_on="segment_id", right_index=True, how="left")
    summary = summary.merge(min_depth, left_on="segment_id", right_index=True, how="left")
    summary = summary.merge(max_depth, left_on="segment_id", right_index=True, how="left")

    summary["matched_point_count"] = summary["matched_point_count"].fillna(0).astype(int)
    summary["in_region_point_count"] = summary["in_region_point_count"].fillna(0).astype(int)
    summary["average_depth_in_region"] = summary["average_depth_in_region"].round(3)
    summary["average_depth_in_region_no_outliers"] = summary["average_depth_in_region_no_outliers"].round(3)
    summary["min_depth_in_region"] = summary["min_depth_in_region"].round(3)
    summary["max_depth_in_region"] = summary["max_depth_in_region"].round(3)

    return summary


def build_qc_overview(result_df, tsdd_df, buffer_feet):
    """Build high-level QC metrics as a key/value table."""
    total_points = len(result_df)
    matched_points = int(result_df["in_region"].sum())
    unmatched_points = total_points - matched_points
    match_rate_pct = round((matched_points / total_points) * 100, 2) if total_points else 0.0

    matched_df = result_df[result_df["in_region"]].copy()
    distance_series = pd.to_numeric(matched_df["nearest_distance_feet"], errors="coerce")
    near_edge_count = int((distance_series >= (0.9 * buffer_feet)).sum()) if not distance_series.empty else 0

    missing_depth_count = int(result_df["depth"].isna().sum()) if "depth" in result_df.columns else 0
    zero_match_segments = int((build_segment_summary(result_df, tsdd_df)["in_region_point_count"] == 0).sum())

    dfo_estimated = pd.to_numeric(matched_df["estimated_dfo"], errors="coerce")
    dfo_start = pd.to_numeric(matched_df["matched_dfo_start"], errors="coerce")
    dfo_end = pd.to_numeric(matched_df["matched_dfo_end"], errors="coerce")
    dfo_min = pd.concat([dfo_start, dfo_end], axis=1).min(axis=1)
    dfo_max = pd.concat([dfo_start, dfo_end], axis=1).max(axis=1)
    dfo_out_of_range = int(((dfo_estimated < dfo_min) | (dfo_estimated > dfo_max)).fillna(False).sum())

    metrics = [
        ("total_depth_points", total_points),
        ("matched_points_in_region", matched_points),
        ("unmatched_points", unmatched_points),
        ("match_rate_percent", match_rate_pct),
        ("buffer_feet", float(buffer_feet)),
        ("mean_distance_feet_matched", round(float(distance_series.mean()), 3) if not distance_series.empty else pd.NA),
        ("p95_distance_feet_matched", round(float(distance_series.quantile(0.95)), 3) if not distance_series.empty else pd.NA),
        ("near_buffer_edge_count_90pct_plus", near_edge_count),
        ("segments_with_zero_in_region_points", zero_match_segments),
        ("rows_with_missing_depth", missing_depth_count),
        ("dfo_out_of_range_count", dfo_out_of_range),
    ]

    return pd.DataFrame(metrics, columns=["metric", "value"])


def build_qc_flags(result_df, buffer_feet):
    """Build row-level QC flags for quick review of potential issues."""
    qc_df = result_df.copy()
    qc_df["qc_unmatched"] = ~qc_df["in_region"]
    qc_df["qc_depth_missing"] = qc_df["depth"].isna()

    distances = pd.to_numeric(qc_df["nearest_distance_feet"], errors="coerce")
    qc_df["qc_near_buffer_edge"] = qc_df["in_region"] & distances.ge(0.9 * buffer_feet)

    dfo_estimated = pd.to_numeric(qc_df["estimated_dfo"], errors="coerce")
    dfo_start = pd.to_numeric(qc_df["matched_dfo_start"], errors="coerce")
    dfo_end = pd.to_numeric(qc_df["matched_dfo_end"], errors="coerce")
    dfo_min = pd.concat([dfo_start, dfo_end], axis=1).min(axis=1)
    dfo_max = pd.concat([dfo_start, dfo_end], axis=1).max(axis=1)
    qc_df["qc_dfo_out_of_range"] = ((dfo_estimated < dfo_min) | (dfo_estimated > dfo_max)).fillna(False)

    flagged = qc_df[
        qc_df[["qc_unmatched", "qc_depth_missing", "qc_near_buffer_edge", "qc_dfo_out_of_range"]].any(axis=1)
    ].copy()
    return flagged


def build_output_tables(result_df, tsdd_df, buffer_feet):
    """Build all output tables used by CLI and web app."""
    segment_summary_df = build_segment_summary(result_df, tsdd_df)
    unmatched_df = result_df[~result_df["in_region"]].copy()
    qc_overview_df = build_qc_overview(result_df, tsdd_df, buffer_feet)
    qc_flags_df = build_qc_flags(result_df, buffer_feet)
    return {
        "Matched Points": result_df,
        "Segment Summary": segment_summary_df,
        "Unmatched Points": unmatched_df,
        "QC Overview": qc_overview_df,
        "QC Flags": qc_flags_df,
    }


def build_output_workbook_bytes(tables_by_sheet_name):
    """Create Excel workbook bytes from sheet-name/DataFrame mapping."""
    output_buffer = BytesIO()
    with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
        for sheet_name, table_df in tables_by_sheet_name.items():
            table_df.to_excel(writer, index=False, sheet_name=sheet_name)
    output_buffer.seek(0)
    return output_buffer.getvalue()


class TerminalProgressReporter:
    """Terminal-friendly progress indicator for long matching runs."""

    def __init__(self, total_items):
        self.total_items = max(int(total_items), 1)
        self._last_step = -1
        self._finished = False

    def update(self, processed_items, total_items):
        percent = int((processed_items / max(total_items, 1)) * 100)
        step = percent // 10
        is_complete = processed_items >= total_items

        if step != self._last_step or is_complete:
            self._last_step = step
            bar_width = 30
            filled = int((percent / 100) * bar_width)
            bar = "#" * filled + "-" * (bar_width - filled)
            print(
                f"\rProgress [{bar}] {percent:3d}% ({processed_items:,}/{total_items:,} segments)",
                end="",
                flush=True,
            )

        if processed_items >= total_items and not self._finished:
            self._finished = True
            print()


def main():
    """GUI-driven workflow for matching depth points to TSDD segments."""
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog
    except ImportError as error:
        raise RuntimeError(
            "Tkinter is required for desktop GUI mode. "
            "Use the Streamlit app (`streamlit run web_app.py`) in environments without Tk support."
        ) from error

    root = tk.Tk()
    root.withdraw()

    try:
        tsdd_file = filedialog.askopenfilename(
            title="Select TSDD file (start/end lat/lon + DFO start/end)",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx"),
                ("Excel files (legacy)", "*.xls"),
                ("All supported files", "*.csv;*.xlsx;*.xls"),
            ],
        )
        if not tsdd_file:
            messagebox.showinfo("Cancelled", "No TSDD file selected. Exiting.")
            return

        depth_file = filedialog.askopenfilename(
            title="Select depth points file (latitude, longitude, depth)",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Excel files", "*.xlsx"),
                ("Excel files (legacy)", "*.xls"),
                ("All supported files", "*.csv;*.xlsx;*.xls"),
            ],
        )
        if not depth_file:
            messagebox.showinfo("Cancelled", "No depth points file selected. Exiting.")
            return

        buffer_feet = simpledialog.askfloat(
            "Buffer Distance",
            "Enter buffer distance in feet:\n(points with nearest distance <= buffer are in-region)",
            minvalue=0.0,
            initialvalue=50.0,
        )
        if buffer_feet is None:
            messagebox.showinfo("Cancelled", "No buffer distance provided. Exiting.")
            return

        output_folder = filedialog.askdirectory(title="Select output folder")
        if not output_folder:
            messagebox.showinfo("Cancelled", "No output folder selected. Exiting.")
            return

        print("Reading TSDD segments...")
        tsdd_df = read_tsdd_segments(tsdd_file)
        print(f"Loaded {len(tsdd_df)} TSDD segments")

        print("Reading depth points...")
        depth_df = read_depth_points(depth_file)
        print(f"Loaded {len(depth_df)} depth points")

        if tsdd_df.empty or depth_df.empty:
            raise ValueError("One or both input files have no valid rows after validation.")

        print("Matching depth points to buffered TSDD segments...")
        terminal_progress = TerminalProgressReporter(len(tsdd_df))
        result_df = match_depth_to_tsdd_segments(
            depth_df,
            tsdd_df,
            buffer_feet,
            progress_callback=terminal_progress.update,
        )

        output_tables = build_output_tables(result_df, tsdd_df, buffer_feet)
        segment_summary_df = output_tables["Segment Summary"]
        unmatched_df = output_tables["Unmatched Points"]
        qc_flags_df = output_tables["QC Flags"]

        output_path = os.path.join(output_folder, "depth_points_matched.xlsx")
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for sheet_name, table_df in output_tables.items():
                table_df.to_excel(writer, index=False, sheet_name=sheet_name)

        in_region_count = int(result_df["in_region"].sum())
        total_count = len(result_df)
        unmatched_count = len(unmatched_df)
        print(f"Matched {total_count} depth points. In-region: {in_region_count}")
        print(f"QC flags: {len(qc_flags_df)} row(s)")

        messagebox.showinfo(
            "Success",
            "Matching complete.\n\n"
            f"Output: {output_path}\n"
            f"Total depth points: {total_count}\n"
            f"In-region points: {in_region_count}\n"
            f"Unmatched points: {unmatched_count}\n"
            f"Summary rows: {len(segment_summary_df)}\n"
            f"QC flagged rows: {len(qc_flags_df)}\n"
            f"Buffer: {buffer_feet} feet",
        )

    except Exception as error:
        messagebox.showerror("Error", f"Processing failed: {error}")
    finally:
        root.destroy()


if __name__ == "__main__":
    print("TSDD Depth Matcher")
    print("=" * 50)
    print("This script will:")
    print("1. Read TSDD segments with start/end lat/lon and DFO start/end")
    print("2. Read depth points with latitude/longitude/depth")
    print("3. Ask for a buffer distance in feet")
    print("4. Match points only when they fall in a buffered start/end segment")
    print("5. Show progress in terminal")
    print("6. Export Matched, Segment Summary, Unmatched, and QC sheets")
    print("=" * 50)
    main()
