import queue
import streamlit as st
import os
from services.api_client import APIClient

st.set_page_config(page_title="Realtime Monitoring", layout="wide")

if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = os.getenv(
        "API_BASE_URL",
        "http://localhost:8000",
    )

if "ws_base_url" not in st.session_state:
    st.session_state.ws_base_url = os.getenv(
        "WS_BASE_URL",
        "ws://localhost:8000",
    )
if "token" not in st.session_state:
    st.session_state.token = None
if "current_user" not in st.session_state:
    st.session_state.current_user = None
if "ws_queue" not in st.session_state:
    st.session_state.ws_queue = queue.Queue()
if "ws_client" not in st.session_state:
    st.session_state.ws_client = None
if "realtime_points" not in st.session_state:
    st.session_state.realtime_points = []

st.title("即時資料分析與監控系統")

with st.sidebar:
    st.session_state.api_base_url = st.text_input("API URL", st.session_state.api_base_url)
    st.session_state.ws_base_url = st.text_input("WS URL", st.session_state.ws_base_url)

if not st.session_state.token:
    st.subheader("登入")
    u = st.text_input("Username")
    p = st.text_input("Password", type="password")
    if st.button("Login", type="primary"):
        try:
            c = APIClient(st.session_state.api_base_url)
            token = c.login(u, p)["access_token"]
            me = APIClient(st.session_state.api_base_url, token).me()
            st.session_state.token = token
            st.session_state.current_user = me
            st.success(f"登入成功：{me['username']} ({me['role']})")
            st.rerun()
        except Exception as e:
            st.error(f"登入失敗：{e}")
else:
    me = st.session_state.current_user
    st.success(f"已登入：{me['username']} ({me['role']})")
    if st.button("Logout"):
        if st.session_state.ws_client is not None:
            st.session_state.ws_client.stop()
            st.session_state.ws_client = None
        st.session_state.token = None
        st.session_state.current_user = None
        st.session_state.realtime_points = []
        st.rerun()

st.info("Demo version by Aaron")