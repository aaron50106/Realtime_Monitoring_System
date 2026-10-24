from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

from services.api_client import APIClient


def _to_taipei_time(series: pd.Series) -> pd.Series:
    utc_series = pd.to_datetime(series, errors="coerce", utc=True)
    return utc_series.dt.tz_convert("Asia/Taipei")


TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def _taipei_now_naive() -> datetime:
    return datetime.now(TAIPEI_TZ).replace(tzinfo=None)


def _to_utc_iso_from_taipei_naive(value: datetime) -> str:
    taipei_aware = value.replace(tzinfo=TAIPEI_TZ)
    return taipei_aware.astimezone(timezone.utc).isoformat()


st.title("Analytics")

if not st.session_state.get("token"):
    st.warning("Please login on Home page first.")
    st.stop()

client = APIClient(st.session_state.api_base_url, st.session_state.token)

st.caption("All displayed times are UTC+8. Daily aggregation follows Taiwan midnight.")

with st.form("analytics-query-form"):
    category = st.text_input("Category (optional)", value="Water_Level")
    col1, col2 = st.columns(2)
    with col1:
        start_dt = st.datetime_input(
            "Start Time (UTC+8)",
            value=_taipei_now_naive() - timedelta(hours=1),
        )
    with col2:
        end_dt = st.datetime_input("End Time (UTC+8)", value=_taipei_now_naive())
    granularity = st.selectbox("Granularity", ["minute", "hour", "day"], index=1)
    submitted = st.form_submit_button("Run Query")

if submitted:
    params = {
        "category": category or None,
        "start_time": _to_utc_iso_from_taipei_naive(start_dt),
        "end_time": _to_utc_iso_from_taipei_naive(end_dt),
    }

    try:
        summary = client.analytics_summary(params)
        by_category = client.analytics_by_category(params)
        trend = client.analytics_trend({**params, "granularity": granularity})
    except Exception as exc:
        st.error(f"Analytics query failed: {exc}")
        st.stop()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Count", summary["total_count"])
    m2.metric("Average", "-" if summary["avg_value"] is None else f"{summary['avg_value']:.2f}")
    m3.metric("Minimum", "-" if summary["min_value"] is None else f"{summary['min_value']:.2f}")
    m4.metric("Maximum", "-" if summary["max_value"] is None else f"{summary['max_value']:.2f}")

    st.subheader("By Category")
    category_df = pd.DataFrame(by_category["items"])
    if category_df.empty:
        st.info("No category aggregation data found.")
    else:
        st.dataframe(category_df, width="stretch")

    st.subheader("Trend")
    trend_df = pd.DataFrame(trend["points"])
    if trend_df.empty:
        st.info("No trend points found.")
    else:
        trend_df["bucket"] = pd.to_datetime(trend_df["bucket"], errors="coerce", utc=True)
        trend_df["bucket_taipei"] = _to_taipei_time(trend_df["bucket"])
        trend_fig = px.line(trend_df, x="bucket_taipei", y="avg_value", markers=True)
        st.plotly_chart(trend_fig, width="stretch")
        trend_df["bucket_taipei"] = trend_df["bucket_taipei"].map(
            lambda value: value.isoformat(sep=" ", timespec="seconds")
        )
        st.dataframe(
            trend_df[["bucket_taipei", "count", "avg_value", "min_value", "max_value"]],
            width="stretch",
        )

    st.subheader("Export")
    st.caption("Excel: timestamp is UTC (+00:00); timestamp_taipei is Taiwan time (+08:00).")
    excel_bytes = client.analytics_export_excel(params)
    st.download_button(
        "Download Excel",
        data=excel_bytes,
        file_name="analytics_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
