# Quick Start (Non-Technical)

Use this if you just want to run the tool and get results.

## What you need

1. **TSDD file** with these columns:
   - `start_latitude`
   - `start_longitude`
   - `end_latitude`
   - `end_longitude`
   - `dfo_start`
   - `dfo_end`
   - optional: `road`

2. **Depth file** with these columns:
   - `latitude`
   - `longitude`
   - `depth`

## Option A: Desktop script (easiest for your PC)

1. Open terminal in this project folder.
2. Run:

python tsdd_depth_matcher.py

3. Follow prompts:
   - Select TSDD file
   - Select Depth file
   - Enter buffer distance (feet)
   - Choose output folder

4. Wait for terminal progress to complete.

5. Open output file:
   - `depth_points_matched.xlsx`

## Option B: Web app (browser upload/download)

1. Run:

streamlit run web_app.py

2. Browser opens automatically.
3. Upload TSDD + Depth files.
4. Enter buffer distance.
5. Click **Run Matching**.
6. Click **Download Output Workbook**.

## What the output contains

Workbook: `depth_points_matched.xlsx`

- **Matched Points**: point-by-point results
- **Segment Summary**: summary per TSDD segment
- **Unmatched Points**: points not within buffer of any segment
- **QC Overview**: high-level quality checks
- **QC Flags**: rows to review first

## How to read it quickly

1. Start with **QC Overview**.
2. If unmatched count is high, increase buffer and run again.
3. Review **QC Flags** rows marked `True`.
4. Use **Segment Summary** for average depth values.

## Common fixes

- "Missing required column": rename headers to match this guide.
- Too many unmatched points: increase buffer distance.
- Very slow run: try smaller test file first, then full file.

## Need full details?

- Full guide: `WORKING_GUIDE.md`
- Technical details and setup: `README.md`
