# TSDD Depth Matcher - Working Guide

This guide explains exactly what the project does and how anyone can run it.

## 1) What this code does

The matcher takes:
- A TSDD segment file (start/end coordinates + DFO range)
- A depth points file (point coordinates + depth)

It then:
1. Validates and standardizes columns
2. Checks which depth points fall within a user buffer around each TSDD start/end segment
3. Assigns each matched point to the closest qualifying segment (no forced matching)
4. Calculates nearest distance and interpolated DFO
5. Creates an Excel report with detailed results, summaries, unmatched points, and QC checks

## 2) Files in this project

- tsdd_depth_matcher.py: Main desktop workflow (file pickers + terminal progress)
- web_app.py: Streamlit web upload/download interface
- requirements.txt: Python dependencies
- sample_tsdd_segments.csv: Example TSDD input
- sample_depth_points.csv: Example depth input

## 3) Input format requirements

### A) TSDD segment file (CSV/XLSX/XLS)
One row = one segment.

Required columns (recommended exact names):
- start_latitude
- start_longitude
- end_latitude
- end_longitude
- dfo_start
- dfo_end

Optional column:
- road

### B) Depth points file (CSV/XLSX/XLS)
One row = one depth point.

Required columns (recommended exact names):
- latitude
- longitude
- depth

### C) Data quality rules
- Coordinates must be numeric and valid lat/lon ranges
- dfo_start and dfo_end should be numeric to compute estimated_dfo
- Rows with invalid coordinates are removed

## 4) Local setup (one-time)

1. Open terminal in project folder
2. Create/activate virtual environment (if needed)
3. Install packages:

pip install -r requirements.txt

## 5) Run desktop workflow (Python script)

Command:

python tsdd_depth_matcher.py

Then follow prompts:
1. Select TSDD file
2. Select depth file
3. Enter buffer distance in feet
4. Choose output folder

During matching:
- Terminal shows a progress bar updated every 10%

## 6) Run web workflow (browser upload/download)

Command:

streamlit run web_app.py

Then in browser:
1. Upload TSDD file
2. Upload depth file
3. Set buffer distance
4. Click Run Matching
5. Download output workbook

## 7) Matching logic (important)

- A point is matched only if it lies within the buffer of at least one segment
- If multiple segments qualify, the closest one is chosen
- If none qualify, point stays unmatched

This means points are not force-assigned to every TSDD segment.

## 8) Output workbook structure

Output file name:
- depth_points_matched.xlsx

Sheets:
1. Matched Points
2. Segment Summary
3. Unmatched Points
4. QC Overview
5. QC Flags

## 9) Key output columns

### Matched Points
- matched_segment_id
- matched_road
- matched_dfo_start
- matched_dfo_end
- estimated_dfo
- nearest_distance_feet
- in_region

### Segment Summary
- matched_point_count
- in_region_point_count
- average_depth_in_region
- average_depth_in_region_no_outliers
- min_depth_in_region
- max_depth_in_region

Outlier rule for average_depth_in_region_no_outliers:
- Remove depth values outside mean ± 1 standard deviation (computed per segment)
- Average the remaining values

### Unmatched Points
- All depth rows where in_region is False

### QC Overview
High-level checks such as:
- total/matched/unmatched points
- match rate percent
- distance statistics on matched rows
- near-buffer-edge count
- segments with zero matches
- missing depth count
- DFO range sanity count

### QC Flags
Row-level booleans for quick triage:
- qc_unmatched
- qc_depth_missing
- qc_near_buffer_edge
- qc_dfo_out_of_range

## 10) Recommended QC review flow

1. Check QC Overview first:
   - Match rate percent
   - Unmatched points count
   - Segments with zero in-region points
2. Open QC Flags and filter True values
3. Review Unmatched Points to determine if buffer should increase
4. Validate a few rows manually in Matched Points for distance/DFO reasonableness

## 11) Performance notes

Current implementation is optimized with:
- Segment-based candidate prefiltering
- Vectorized distance math for candidate points
- Reduced progress output frequency

If runtime is still high:
- Reduce unnecessary rows in inputs
- Confirm coordinates are in expected area (bad coordinates can inflate work)
- Start with a smaller test subset to validate settings

## 12) Common issues and fixes

### Issue: Missing required column
- Ensure required headers are present
- Prefer exact header names shown in this guide

### Issue: Too many unmatched points
- Increase buffer distance
- Check coordinate quality and coordinate system assumptions

### Issue: Outlier-adjusted average is blank
- Can happen when no in-region depth rows exist for that segment
- Can also occur if all candidate depth values are invalid/missing after cleaning

## 13) Sharing with other users

You have two options:
- Local script usage: users run python tsdd_depth_matcher.py
- Hosted usage: deploy web_app.py and share URL

For internal/sensitive data, prefer internal hosting with access control.

---
If you want, add your team-specific defaults (buffer, naming conventions, deployment URL) at the top of this document.
