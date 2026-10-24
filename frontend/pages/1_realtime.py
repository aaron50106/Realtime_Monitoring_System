from __future__ import annotations

import queue
import time
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from services.api_client import APIClient
from services.ws_client import RealtimeWSClient

MAX_POINTS = 500
MAX_MESSAGES_PER_REFRESH = 200
RECONNECT_COOLDOWN_SECONDS = 5
FRAGMENT_REFRESH_SECONDS = 2
NO_UPDATE_FULL_RERUN_SECONDS = 25
CHART_POINTS_PER_CATEGORY = 20


def _to_taipei_time(series: pd.Series) -> pd.Series:
    utc_series = pd.to_datetime(series, errors="coerce", utc=True)
    return utc_series.dt.tz_convert("Asia/Taipei")


def _compute_xaxis_range(time_series: pd.Series) -> list[pd.Timestamp]:
    sorted_series = time_series.dropna().sort_values()
    one_second = pd.to_timedelta(1, unit="s")
    sixty_seconds = pd.to_timedelta(60, unit="s")
    if sorted_series.empty:
        now = pd.Timestamp.now(tz="Asia/Taipei")
        return [now - sixty_seconds, now]

    first = pd.Timestamp(sorted_series.iloc[0])
    last = pd.Timestamp(sorted_series.iloc[-1])
    span = last - first
    if span <= one_second:
        left = first - sixty_seconds
        right = first + sixty_seconds
        return [pd.Timestamp(left), pd.Timestamp(right)]

    padding_seconds = max(5.0, span.total_seconds() * 0.08)
    padding = pd.to_timedelta(padding_seconds, unit="s")
    left = first - padding
    right = last + padding
    return [pd.Timestamp(left), pd.Timestamp(right)]


def _start_ws_client() -> None:
    ws_client = RealtimeWSClient(
        ws_base_url=st.session_state.ws_base_url,
        token=st.session_state.token,
        output_queue=st.session_state.ws_queue,
    )
    ws_client.start()
    st.session_state.ws_client = ws_client


def _ensure_ws_health() -> bool:
    ws_running = st.session_state.ws_client is not None and st.session_state.ws_client.is_alive()
    if st.session_state.ws_client is not None and not ws_running:
        st.warning("WebSocket disconnected. Attempting to recover...")
        st.session_state.ws_client = None

    if (
        not ws_running
        and st.session_state.ws_auto_reconnect
        and time.time() - st.session_state.ws_last_reconnect_try >= RECONNECT_COOLDOWN_SECONDS
    ):
        st.session_state.ws_last_reconnect_try = time.time()
        _start_ws_client()
        ws_running = st.session_state.ws_client is not None and st.session_state.ws_client.is_alive()
    return ws_running


def _render_realtime_charts_panel() -> None:
    ws_running = _ensure_ws_health()

    processed = 0
    while processed < MAX_MESSAGES_PER_REFRESH:
        try:
            msg = st.session_state.ws_queue.get_nowait()
        except queue.Empty:
            break
        processed += 1
        if "_error" in msg:
            st.error(msg["_error"])
            continue
        if "_info" in msg:
            st.info(msg["_info"])
            continue
        st.session_state.realtime_points.append(msg)
        st.session_state.ws_last_data_monotonic = time.monotonic()

    queue_backlog = st.session_state.ws_queue.qsize()
    if queue_backlog > 0:
        st.caption(f"WS queue backlog: {queue_backlog} (auto draining in next refresh)")

    st.session_state.realtime_points = st.session_state.realtime_points[-MAX_POINTS:]

    latest_time_text = "-"
    latest_age_seconds = "-"
    if st.session_state.realtime_points:
        df = pd.DataFrame(st.session_state.realtime_points)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df = df.dropna(subset=["timestamp"])
        df["timestamp_taipei"] = _to_taipei_time(df["timestamp"])
        latest_time = df["timestamp_taipei"].max()
        if pd.notna(latest_time):
            latest_time_text = latest_time.strftime("%Y-%m-%d %H:%M:%S")
            latest_age_seconds = f"{int((pd.Timestamp.now(tz='Asia/Taipei') - latest_time).total_seconds())}s"
    else:
        df = pd.DataFrame()

    st.caption(
        f"WebSocket: {'Connected' if ws_running else 'Disconnected'} | "
        f"Queue backlog: {queue_backlog} | "
        f"Latest point time (UTC+8): {latest_time_text} | Age: {latest_age_seconds}"
    )

    if (
        ws_running
        and st.session_state.ws_last_data_monotonic > 0
        and time.monotonic() - st.session_state.ws_last_data_monotonic >= NO_UPDATE_FULL_RERUN_SECONDS
        and time.monotonic() - st.session_state.ws_last_forced_rerun_monotonic >= NO_UPDATE_FULL_RERUN_SECONDS
    ):
        st.session_state.ws_last_forced_rerun_monotonic = time.monotonic()
        st.warning(
            f"No new realtime data for {NO_UPDATE_FULL_RERUN_SECONDS}s. "
            "Triggering full rerun for recovery..."
        )
        st.rerun()

    if df.empty:
        st.info("No realtime data received yet.")
        return

    chart_df = df.sort_values("timestamp_taipei").copy()
    chart_df["value_label"] = chart_df["value"].map(lambda v: f"{v:.2f}")

    water_df = (
        chart_df[chart_df["category"].str.lower().str.contains("water", na=False)]
        .tail(CHART_POINTS_PER_CATEGORY)
    )
    temp_df = (
        chart_df[chart_df["category"].str.lower().str.contains("temp", na=False)]
        .tail(CHART_POINTS_PER_CATEGORY)
    )

    st.subheader("Live Dashboard")
    dash1, dash2 = st.columns(2)
    with dash1:
        if water_df.empty:
            st.info("No Water Level data yet.")
        else:
            row = water_df.iloc[-1]
            st.markdown(
                f"""
                <div style="padding:16px;border:1px solid #d9d9d9;border-radius:12px;">
                    <div style="font-size:1.05rem;color:#666;">Water Level</div>
                    <div style="font-size:2.4rem;font-weight:700;line-height:1.1;">{row['value']:.2f}</div>
                    <div style="font-size:0.9rem;color:#888;">{row['timestamp_taipei'].strftime('%H:%M:%S')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with dash2:
        if temp_df.empty:
            st.info("No Temperature data yet.")
        else:
            row = temp_df.iloc[-1]
            st.markdown(
                f"""
                <div style="padding:16px;border:1px solid #d9d9d9;border-radius:12px;">
                    <div style="font-size:1.05rem;color:#666;">Temperature</div>
                    <div style="font-size:2.4rem;font-weight:700;line-height:1.1;">{row['value']:.2f}</div>
                    <div style="font-size:0.9rem;color:#888;">{row['timestamp_taipei'].strftime('%H:%M:%S')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.subheader("Realtime Time-series Line Charts")

    c1, c2 = st.columns(2)
    with c1:
        if water_df.empty:
            st.info("No Water Level data yet.")
        else:
            water_fig = px.line(
                water_df,
                x="timestamp_taipei",
                y="value",
                markers=True,
                text="value_label",
            )
            water_fig.update_traces(
                line={"width": 3},
                marker={"size": 8},
                textposition="top center",
            )
            water_fig.update_layout(
                height=520,
                font={"size": 16},
                title={"text": "Water Level (UTC+8)", "font": {"size": 22}},
                xaxis_title="Time (UTC+8)",
                yaxis_title="Water Level",
                xaxis={"range": _compute_xaxis_range(water_df["timestamp_taipei"])},
                margin={"l": 20, "r": 20, "t": 60, "b": 20},
            )
            st.plotly_chart(water_fig, width="stretch", key="realtime-line-chart-water")

    with c2:
        if temp_df.empty:
            st.info("No Temperature data yet.")
        else:
            temp_fig = px.line(
                temp_df,
                x="timestamp_taipei",
                y="value",
                markers=True,
                text="value_label",
            )
            temp_fig.update_traces(
                line={"width": 3},
                marker={"size": 8},
                textposition="top center",
            )
            temp_fig.update_layout(
                height=520,
                font={"size": 16},
                title={"text": "Temperature (UTC+8)", "font": {"size": 22}},
                xaxis_title="Time (UTC+8)",
                yaxis_title="Temperature",
                xaxis={"range": _compute_xaxis_range(temp_df["timestamp_taipei"])},
                margin={"l": 20, "r": 20, "t": 60, "b": 20},
            )
            st.plotly_chart(temp_fig, width="stretch", key="realtime-line-chart-temp")


st.title("Realtime Monitoring")

if not st.session_state.get("token"):
    st.warning("Please login on Home page first.")
    st.stop()

if "ws_auto_reconnect" not in st.session_state:
    st.session_state.ws_auto_reconnect = True
if "ws_last_reconnect_try" not in st.session_state:
    st.session_state.ws_last_reconnect_try = 0.0
if "ws_last_data_monotonic" not in st.session_state:
    st.session_state.ws_last_data_monotonic = 0.0
if "ws_last_forced_rerun_monotonic" not in st.session_state:
    st.session_state.ws_last_forced_rerun_monotonic = 0.0

client = APIClient(st.session_state.api_base_url, st.session_state.token)

col1, col2, col3 = st.columns([1, 1, 1.4])
with col1:
    if st.button("Start WebSocket"):
        if st.session_state.ws_client is None or not st.session_state.ws_client.is_alive():
            _start_ws_client()
            st.success("WebSocket started.")
        else:
            st.info("WebSocket is already running.")
with col2:
    if st.button("Stop WebSocket"):
        if st.session_state.ws_client is not None:
            st.session_state.ws_client.stop()
            st.session_state.ws_client = None
            st.info("WebSocket stopped.")
with col3:
    st.session_state.ws_auto_reconnect = st.checkbox(
        "Auto reconnect when disconnected",
        value=st.session_state.ws_auto_reconnect,
    )

st.subheader("Connection Snapshot (Fixed Area)")
ws_running_snapshot = (
    st.session_state.ws_client is not None and st.session_state.ws_client.is_alive()
)
service_running_snapshot = "N/A"
connected_clients_snapshot = "N/A"
try:
    status_snapshot = client.realtime_status()
    service_running_snapshot = status_snapshot.get("running")
    connected_clients_snapshot = status_snapshot.get("connected_clients")
except Exception as exc:
    st.warning(f"Realtime status check failed: {exc}")

s1, s2, s3 = st.columns(3)
s1.metric("WebSocket", "Connected" if ws_running_snapshot else "Disconnected")
s2.metric("Generator", str(service_running_snapshot))
s3.metric("Connected Clients", str(connected_clients_snapshot))

if hasattr(st, "fragment"):
    @st.fragment(run_every=f"{FRAGMENT_REFRESH_SECONDS}s")
    def _refreshing_fragment() -> None:
        _render_realtime_charts_panel()

    st.caption(
        f"UI update mode: partial refresh every {FRAGMENT_REFRESH_SECONDS}s "
        f"(only chart area updates; header/buttons remain fixed)"
    )
    _refreshing_fragment()
else:
    st_autorefresh(interval=NO_UPDATE_FULL_RERUN_SECONDS * 1000, key="realtime-refresh")
    st.caption(
        f"UI update mode: fallback full rerun every {NO_UPDATE_FULL_RERUN_SECONDS}s "
        "(upgrade Streamlit for no-flicker partial refresh)"
    )
    _render_realtime_charts_panel()
