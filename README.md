# TSDD Depth Matcher + KML Tools

Upload TSDD segment data and depth points to generate a matched Excel report with DFO mapping, segment summaries, outlier-adjusted averages, unmatched rows, and built-in QC checks. This repo also includes the original KML/KMZ path-generation utility.

For a complete end-to-end operating guide (inputs, run steps, outputs, QC, and troubleshooting), see `WORKING_GUIDE.md`.
For a one-page non-technical guide, see `QUICK_START.md`.

## Runtime Modes (Important)

This project supports two ways to run depth matching:

- **Web app mode (recommended for sharing):** `streamlit run web_app.py`
- **Desktop GUI mode (local only):** `python tsdd_depth_matcher.py`

Notes:

- `web_app.py` does **not** require `tkinter`.
- `tsdd_depth_matcher.py` desktop GUI uses `tkinter`, so it is intended for local machines with Tk support.
- Streamlit Cloud should run `web_app.py` as the main file.

## GitHub Repo About (Copy/Paste)

Use this in your GitHub repo **About** field:

`Upload TSDD segments and depth points to produce matched Excel outputs with DFO interpolation, segment summaries, outlier-aware averages, unmatched rows, and QC flags.`

## Features

- **Smart path fixing**: Automatically reorders paths with duplicate sequence numbers using geographic proximity
- **Case-insensitive headers**: Works with any case combination of Latitude, Longitude, Name, Sequence
- **Optional sequence input**: If Sequence is missing, corrected sequence is auto-generated from proximity
- **Multiple paths**: Creates separate KML files for each unique path name
- **Multiple formats**: Creates both individual KML files and a combined KMZ archive
- **Different colors**: Each path gets a unique, distinct color
- **User-friendly**: Simple GUI dialogs for file selection
- **Clean output**: Organized KML files with both paths and individual points

## Requirements

Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. **Run the script:**
   ```bash
   python kml_path_generator.py
   ```

2. **Select your input file** when prompted - CSV (.csv) or Excel (.xlsx, .xls) with these columns:
   - `Latitude` (or latitude, LATITUDE, etc.)
   - `Longitude` (or longitude, LONGITUDE, etc.)  
   - `Name` (or name, NAME, etc.)
   - `Sequence` (optional; if missing, the script auto-generates a corrected sequence)

3. **Choose output folder** where KML files will be saved

4. **Done!** The script will create:
   - Individual KML files for each unique path name
   - One combined KMZ file containing all path lines
   - One points-only KMZ file with all data points (no labels)
   - One Excel file with reorganized data and corrected sequences

## CSV/Excel Format Example

```csv
Latitude,Longitude,Name,Sequence
40.7128,-74.0060,Path_A,1
40.7614,-73.9776,Path_A,2
40.7831,-73.9712,Path_A,3
34.0522,-118.2437,Path_B,1
34.0736,-118.4004,Path_B,2
```

## What You Get

- **Individual KML files** for each path (e.g., `Path_A_path.kml`, `Path_B_path.kml`)
- **Combined KMZ file** (`combined_paths.kmz`) containing all paths in organized folders
- **Points KMZ file** (`all_points.kmz`) containing all data points organized by path (no labels)
- **Excel export** (`reorganized_data.xlsx`) with:
   - `Reorganized Points` sheet (`actual_sequence`, `corrected_sequence`)
   - `Path QA` sheet (per-path duplicates, jump ratio, reordered flag)
- **Clean path lines** connecting points in sequence order (no cluttered point markers)
- **Smart segmentation** - paths automatically split when data collection gaps >200 feet
- **Unique colors** for easy path identification

## Tips

- Points are connected using corrected sequence order
- If input Sequence exists, it is preserved in Excel as `actual_sequence`
- Corrected order is always exported as `corrected_sequence`
- For paths with duplicate/incorrect sequences, points are automatically reordered by geographic proximity
- Lines automatically split when consecutive points are more than 200 feet apart (prevents connecting distant locations)
- Path names will be used as filenames (spaces and special characters are replaced with underscores)
- Clean line display without individual point markers for uncluttered viewing
- You can open the generated KML files individually or use the combined KMZ file in Google Earth, Google Maps, or other mapping applications
- The KMZ file is perfect for sharing since it contains all paths in one convenient archive

## Sample Data

Use `sample_data.csv` or `sample_data.xlsx` to test the script with example coordinate data.

## TSDD Depth Matching (New)

Use `tsdd_depth_matcher.py` to associate depth points with the nearest TSDD segment and flag whether each point falls within a buffer around that segment.

### Run

```bash
python tsdd_depth_matcher.py
```

This is the **desktop GUI workflow** and requires `tkinter` (local machine with Tk support).

### Expected Inputs

1. **TSDD file** (CSV/XLSX/XLS), each row is one segment with:
   - start latitude
   - start longitude
   - end latitude
   - end longitude
   - DFO start
   - DFO end
   - optional road name

2. **Depth points file** (CSV/XLSX/XLS) with:
   - latitude
   - longitude
   - depth

The script asks for a runtime buffer (feet). A depth point is matched **only if** it falls within that buffer of a segment between its start/end coordinates. Points outside all buffered segments remain unmatched (`in_region=False`).
During matching, progress is shown in the terminal.

### Output

Creates `depth_points_matched.xlsx` with original depth columns plus:

- `matched_segment_id`
- `matched_road` (if road exists in TSDD file)
- `matched_dfo_start`
- `matched_dfo_end`
- `estimated_dfo` (interpolated along matched segment from DFO start/end)
- `nearest_distance_feet`
- `in_region`

Also adds a second sheet, `Segment Summary`, with one row per TSDD segment including:

- `matched_point_count`
- `in_region_point_count`
- `average_depth_in_region` (average of depth values for points within buffer between that segment start/end)
- `average_depth_in_region_no_outliers` (average after removing depths outside `mean ± 1 standard deviation` for that segment)
- `min_depth_in_region`
- `max_depth_in_region`

Also adds a third sheet, `Unmatched Points`, with depth points that were outside the buffer of all TSDD segments.

Also adds QC sheets:

- `QC Overview`: key sanity metrics (match rate, unmatched count, distance stats, near-buffer-edge count, zero-match segments, etc.)
- `QC Flags`: row-level flags for potential issues (`qc_unmatched`, `qc_depth_missing`, `qc_near_buffer_edge`, `qc_dfo_out_of_range`)

## Web App (Upload + Download)

Use `web_app.py` to let users upload files in browser and download `depth_points_matched.xlsx` directly.

### Run locally

```bash
pip install -r requirements.txt
streamlit run web_app.py
```

For Streamlit Community Cloud, set **Main file path** to `web_app.py`.

### What users do in the web app

1. Upload TSDD file
2. Upload depth file
3. Enter buffer (feet)
4. Click **Run Matching**
5. Download output workbook

### Hosting options

- **Streamlit Community Cloud** (quickest setup for demos)
- **Azure App Service / Azure Container Apps** (recommended for company/internal deployment)

For internal/sensitive data, prefer Azure hosting with org authentication and private network controls.