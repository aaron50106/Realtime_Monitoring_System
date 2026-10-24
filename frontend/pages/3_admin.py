from __future__ import annotations

import pandas as pd
import streamlit as st

from services.api_client import APIClient


def _build_sorted_user_options(users: list[dict]) -> list[dict]:
    options: list[dict] = []
    for user in users:
        user_id = user.get("id")
        if user_id is None:
            continue
        try:
            normalized_id = int(user_id)
        except (TypeError, ValueError):
            continue
        options.append(
            {
                "id": normalized_id,
                "username": user.get("username", ""),
                "role": user.get("role", ""),
            }
        )
    options.sort(key=lambda item: item["id"])
    return options


st.title("Admin")

if not st.session_state.get("token"):
    st.warning("Please login on Home page first.")
    st.stop()

current_user = st.session_state.get("current_user") or {}
if current_user.get("role") != "admin":
    st.error("Admin role is required to access this page.")
    st.stop()

client = APIClient(st.session_state.api_base_url, st.session_state.token)

if "admin_users" not in st.session_state:
    st.session_state.admin_users = []
if "admin_users_meta" not in st.session_state:
    st.session_state.admin_users_meta = {}
if "admin_user_options" not in st.session_state:
    st.session_state.admin_user_options = []

col1, col2, col3 = st.columns(3)
with col1:
    page = st.number_input("Page", min_value=1, value=1, step=1)
with col2:
    size = st.number_input("Size", min_value=1, max_value=100, value=20, step=1)
with col3:
    keyword = st.text_input("Keyword", value="")

filter_role = st.selectbox("Filter Role", ["", "admin", "user", "viewer"], index=0)

if st.button("Load Users"):
    try:
        data = client.admin_list_users(
            page=int(page),
            size=int(size),
            keyword=keyword or None,
            role=filter_role or None,
        )
    except Exception as exc:
        st.error(f"Load users failed: {exc}")
    else:
        st.session_state.admin_users = data["items"]
        st.session_state.admin_users_meta = data
        st.session_state.admin_user_options = _build_sorted_user_options(data["items"])
        st.success("Users loaded.")

users = st.session_state.admin_users
if users:
    users_df = pd.DataFrame(users)
    try:
        created_at_taipei = pd.to_datetime(
            users_df["created_at"], utc=True, format="mixed"
        ).dt.tz_convert("Asia/Taipei")
        users_df["created_at"] = created_at_taipei.map(
            lambda value: value.isoformat(sep=" ", timespec="seconds")
        )
    except (ValueError, TypeError) as exc:
        st.error(f"Unable to display user creation times in UTC+8: {exc}")
    else:
        st.dataframe(
            users_df.rename(columns={"created_at": "created_at (UTC+8)"}),
            width="stretch",
        )
    st.write({
        key: st.session_state.admin_users_meta[key]
        for key in ("page", "size", "total", "total_pages")
        if key in st.session_state.admin_users_meta
    })

    st.subheader("Update User Role")
    user_id_input_mode = st.radio(
        "User ID input mode",
        ["Manual Input", "Dropdown (sorted by ID)"],
        horizontal=True,
    )

    user_options = st.session_state.admin_user_options
    if user_id_input_mode == "Dropdown (sorted by ID)" and user_options:
        selected_user = st.selectbox(
            "Select User ID",
            options=user_options,
            format_func=lambda item: f"id={item['id']} | {item['username']} ({item['role']})",
        )
        user_id = int(selected_user["id"])
    else:
        default_user_id = int(users[0]["id"])
        user_id = st.number_input("User ID", min_value=1, value=default_user_id, step=1)

    role = st.selectbox("New Role", ["admin", "user", "viewer"], index=1)
    if st.button("Apply Role Update"):
        try:
            updated = client.admin_update_role(int(user_id), role)
        except Exception as exc:
            st.error(f"Role update failed: {exc}")
        else:
            st.success(f"Updated {updated['username']} to role={updated['role']}")
