from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

from services.api_client import APIClient


def _http_error_message(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        try:
            data = exc.response.json()
            return f"{exc.response.status_code} - {json.dumps(data, ensure_ascii=False)}"
        except ValueError:
            return f"{exc.response.status_code} - {exc.response.text}"
    return str(exc)


def _to_taipei_time(series: pd.Series) -> pd.Series:
    utc_series = pd.to_datetime(series, errors="coerce", utc=True)
    return utc_series.dt.tz_convert("Asia/Taipei")


TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def _taipei_now_naive() -> datetime:
    return datetime.now(TAIPEI_TZ).replace(tzinfo=None)


def _to_utc_iso_from_taipei_naive(value: datetime) -> str:
    taipei_aware = value.replace(tzinfo=TAIPEI_TZ)
    return taipei_aware.astimezone(timezone.utc).isoformat()


st.title("Data Management")

if not st.session_state.get("token"):
    st.warning("Please login on Home page first.")
    st.stop()

client = APIClient(st.session_state.api_base_url, st.session_state.token)
current_user = st.session_state.get("current_user") or {}
can_write = current_user.get("role") in {"admin", "user"}

if "records_data" not in st.session_state:
    st.session_state.records_data = []
if "records_meta" not in st.session_state:
    st.session_state.records_meta = {}

st.subheader("Query Records")
with st.form("records-query-form"):
    q1, q2, q3, q4 = st.columns(4)
    with q1:
        page = st.number_input("Page", min_value=1, value=1, step=1)
    with q2:
        size = st.number_input("Size", min_value=1, max_value=100, value=20, step=1)
    with q3:
        sort_by = st.selectbox("Sort By", ["timestamp", "value", "title", "category"], index=0)
    with q4:
        sort_order = st.selectbox("Sort Order", ["desc", "asc"], index=0)

    f1, f2, f3 = st.columns(3)
    with f1:
        category = st.text_input("Category (optional)", value="")
    with f2:
        use_time_range = st.checkbox("Use Time Range (UTC+8)", value=False)
    with f3:
        pass

    t1, t2 = st.columns(2)
    with t1:
        start_time_taipei = st.datetime_input(
            "Start Time (UTC+8)",
            value=_taipei_now_naive() - timedelta(hours=1),
            disabled=not use_time_range,
        )
    with t2:
        end_time_taipei = st.datetime_input(
            "End Time (UTC+8)",
            value=_taipei_now_naive(),
            disabled=not use_time_range,
        )

    query_submitted = st.form_submit_button("Load Records")

if query_submitted:
    try:
        start_time_utc = _to_utc_iso_from_taipei_naive(start_time_taipei) if use_time_range else None
        end_time_utc = _to_utc_iso_from_taipei_naive(end_time_taipei) if use_time_range else None
        result = client.list_data_records(
            page=int(page),
            size=int(size),
            category=category or None,
            start_time=start_time_utc,
            end_time=end_time_utc,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except Exception as exc:
        st.error(f"Load records failed: {_http_error_message(exc)}")
    else:
        st.session_state.records_data = result["items"]
        st.session_state.records_meta = {
            "page": result["page"],
            "size": result["size"],
            "total": result["total"],
            "total_pages": result["total_pages"],
        }
        st.success("Records loaded.")

records = st.session_state.records_data
if records:
    st.write(st.session_state.records_meta)
    records_df = pd.DataFrame(records)
    if "timestamp" in records_df.columns:
        records_df["timestamp"] = _to_taipei_time(records_df["timestamp"])
    st.dataframe(records_df, width="stretch")

if not can_write:
    st.info("Current role is viewer: create/update/delete/import actions are disabled.")
    st.stop()

st.subheader("Create Record")
with st.form("create-record-form"):
    c1, c2 = st.columns(2)
    with c1:
        create_title = st.text_input("Title", value="")
        create_value = st.number_input("Value", value=0.0, step=0.1, format="%.4f")
    with c2:
        create_category = st.text_input("Category", value="Water_Level")
        create_with_timestamp = st.checkbox("Set Timestamp (UTC+8)", value=False)
        create_timestamp_taipei = st.datetime_input(
            "Timestamp (UTC+8)",
            value=_taipei_now_naive(),
            disabled=not create_with_timestamp,
        )
    create_submitted = st.form_submit_button("Create")

if create_submitted:
    payload = {
        "title": create_title,
        "value": float(create_value),
        "category": create_category,
    }
    if create_with_timestamp:
        payload["timestamp"] = _to_utc_iso_from_taipei_naive(create_timestamp_taipei)
    try:
        created = client.create_data_record(payload)
    except Exception as exc:
        st.error(f"Create failed: {_http_error_message(exc)}")
    else:
        st.success(f"Created record id={created['id']}")

st.subheader("Update Record")
default_record_id = int(records[0]["id"]) if records else 1
with st.form("update-record-form"):
    u1, u2, u3 = st.columns(3)
    with u1:
        update_id = st.number_input("Record ID", min_value=1, value=default_record_id, step=1)
    with u2:
        update_title = st.text_input("New Title (optional)", value="")
        update_category = st.text_input("New Category (optional)", value="")
    with u3:
        update_value_raw = st.text_input("New Value (optional)", value="")
        update_with_timestamp = st.checkbox("Set Timestamp (UTC+8)", value=False)
        update_timestamp_taipei = st.datetime_input(
            "New Timestamp (UTC+8)",
            value=_taipei_now_naive(),
            disabled=not update_with_timestamp,
        )
    update_submitted = st.form_submit_button("Update")

if update_submitted:
    payload: dict[str, object] = {}
    if update_title.strip():
        payload["title"] = update_title.strip()
    if update_category.strip():
        payload["category"] = update_category.strip()
    if update_value_raw.strip():
        try:
            payload["value"] = float(update_value_raw.strip())
        except ValueError:
            st.error("New Value must be numeric.")
            payload = {}
    if update_with_timestamp:
        payload["timestamp"] = _to_utc_iso_from_taipei_naive(update_timestamp_taipei)

    if not payload:
        st.warning("Provide at least one field to update.")
    else:
        try:
            updated = client.update_data_record(int(update_id), payload)
        except Exception as exc:
            st.error(f"Update failed: {_http_error_message(exc)}")
        else:
            st.success(f"Updated record id={updated['id']}")

st.subheader("Delete Record")
with st.form("delete-record-form"):
    delete_id = st.number_input("Record ID to delete", min_value=1, value=default_record_id, step=1)
    delete_submitted = st.form_submit_button("Delete")

if delete_submitted:
    try:
        client.delete_data_record(int(delete_id))
    except Exception as exc:
        st.error(f"Delete failed: {_http_error_message(exc)}")
    else:
        st.success(f"Deleted record id={int(delete_id)}")

st.subheader("Import JSON")
json_template = {
    "records": [
        {
            "title": "sensor-1",
            "value": 52.4,
            "category": "Water_Level",
            "timestamp": "2026-10-24T12:00:00+08:00",
        }
    ]
}
json_text = st.text_area("JSON payload", value=json.dumps(json_template, ensure_ascii=False, indent=2), height=180)
if st.button("Import JSON"):
    try:
        parsed = json.loads(json_text)
        if isinstance(parsed, list):
            parsed = {"records": parsed}
        result = client.import_data_records_json(parsed)
    except json.JSONDecodeError as exc:
        st.error(f"JSON parse failed: {exc}")
    except Exception as exc:
        st.error(f"JSON import failed: {_http_error_message(exc)}")
    else:
        st.success(f"Imported JSON records: {result['inserted_count']}")

st.subheader("Import CSV")
uploaded_csv = st.file_uploader("Upload CSV", type=["csv"])
if st.button("Import CSV"):
    if uploaded_csv is None:
        st.warning("Please upload a CSV file first.")
    else:
        try:
            result = client.import_data_records_csv(
                filename=uploaded_csv.name,
                content=uploaded_csv.getvalue(),
            )
        except Exception as exc:
            st.error(f"CSV import failed: {_http_error_message(exc)}")
        else:
            st.success(f"Imported CSV records: {result['inserted_count']}")
