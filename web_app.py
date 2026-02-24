import time

import streamlit as st

from tsdd_depth_matcher import (
    build_output_tables,
    build_output_workbook_bytes,
    match_depth_to_tsdd_segments,
    read_table_from_upload,
    standardize_depth_points,
    standardize_tsdd_segments,
)


st.set_page_config(page_title="TSDD Depth Matcher", layout="wide")
st.title("TSDD Depth Matcher")
st.caption(
    "Upload two files (TSDD segments + depth points), run matching, and download one Excel workbook with matches, summaries, unmatched rows, and QC checks."
)

with st.expander("Required input columns", expanded=False):
    st.markdown(
        """
- **TSDD file**: `start_latitude`, `start_longitude`, `end_latitude`, `end_longitude`, `dfo_start`, `dfo_end`, optional `road`
- **Depth file**: `latitude`, `longitude`, `depth`
- **Output**: `depth_points_matched.xlsx` with `Matched Points`, `Segment Summary`, `Unmatched Points`, `QC Overview`, and `QC Flags`
"""
    )

col1, col2 = st.columns(2)
with col1:
    tsdd_upload = st.file_uploader("Upload TSDD file", type=["csv", "xlsx", "xls"])
with col2:
    depth_upload = st.file_uploader("Upload Depth file", type=["csv", "xlsx", "xls"])

buffer_feet = st.number_input("Buffer distance (feet)", min_value=0.0, value=50.0, step=5.0)

run_clicked = st.button("Run Matching", type="primary", use_container_width=True)

if run_clicked:
    if tsdd_upload is None or depth_upload is None:
        st.error("Please upload both TSDD and depth files.")
    else:
        try:
            with st.spinner("Reading and validating files..."):
                tsdd_raw = read_table_from_upload(tsdd_upload)
                depth_raw = read_table_from_upload(depth_upload)
                tsdd_df = standardize_tsdd_segments(tsdd_raw)
                depth_df = standardize_depth_points(depth_raw)

            if tsdd_df.empty or depth_df.empty:
                st.error("One or both files have no valid rows after validation.")
            else:
                total_segments = len(tsdd_df)
                progress_bar = st.progress(0, text="Preparing matching...")
                progress_text = st.empty()
                last_progress_update = {"pct": -1}

                def streamlit_progress(processed_items, total_items):
                    pct = int((processed_items / max(total_items, 1)) * 100)
                    if pct != last_progress_update["pct"]:
                        last_progress_update["pct"] = pct
                        progress_bar.progress(
                            min(pct, 100),
                            text=f"Matching segments: {processed_items:,}/{total_items:,} ({pct}%)",
                        )
                        progress_text.caption(
                            f"Processed {processed_items:,} of {total_items:,} TSDD segments"
                        )

                start_time = time.time()
                result_df = match_depth_to_tsdd_segments(
                    depth_df,
                    tsdd_df,
                    buffer_feet,
                    progress_callback=streamlit_progress,
                )
                elapsed = time.time() - start_time

                output_tables = build_output_tables(result_df, tsdd_df, buffer_feet)
                workbook_bytes = build_output_workbook_bytes(output_tables)

                matched_count = int(result_df["in_region"].sum())
                unmatched_count = int((~result_df["in_region"]).sum())

                progress_bar.progress(100, text="Matching complete")
                progress_text.caption(f"Completed in {elapsed:.1f} seconds")

                metric_col1, metric_col2, metric_col3 = st.columns(3)
                metric_col1.metric("Depth points", f"{len(result_df):,}")
                metric_col2.metric("Matched in region", f"{matched_count:,}")
                metric_col3.metric("Unmatched", f"{unmatched_count:,}")

                st.download_button(
                    label="Download Output Workbook",
                    data=workbook_bytes,
                    file_name="depth_points_matched.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

                with st.expander("Preview: Matched Points (first 25 rows)", expanded=True):
                    st.dataframe(output_tables["Matched Points"].head(25), use_container_width=True)

                with st.expander("Preview: Segment Summary", expanded=False):
                    st.dataframe(output_tables["Segment Summary"], use_container_width=True)

                with st.expander("Preview: QC Overview", expanded=False):
                    st.dataframe(output_tables["QC Overview"], use_container_width=True)

        except Exception as error:
            st.error(f"Processing failed: {error}")
