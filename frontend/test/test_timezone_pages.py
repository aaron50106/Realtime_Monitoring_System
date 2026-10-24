import copy
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


FRONTEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def api_client_class(monkeypatch):
    monkeypatch.syspath_prepend(str(FRONTEND))
    from services.api_client import APIClient
    return APIClient


def _page(name):
    app = AppTest.from_file(str(FRONTEND / "pages" / name))
    app.session_state["token"] = "synthetic-token"
    app.session_state["api_base_url"] = "http://invalid.test"
    app.session_state["current_user"] = {"id": 1, "role": "admin"}
    return app


def test_admin_displays_taipei_without_changing_cached_api_data(monkeypatch, api_client_class):
    users = [
        {"id": 2, "username": "second", "role": "user", "created_at": "2026-10-20T16:00:00Z"},
        {"id": 1, "username": "first", "role": "admin", "created_at": "2026-10-20T17:00:00"},
    ]
    response = {"items": users, "page": 1, "size": 20, "total": 2, "total_pages": 1}
    monkeypatch.setattr(
        api_client_class, "admin_list_users", lambda *args, **kwargs: copy.deepcopy(response),
    )
    app = _page("3_admin.py").run()
    next(button for button in app.button if button.label == "Load Users").click().run()
    assert not app.exception
    displayed = app.dataframe[0].value
    assert list(displayed["created_at (UTC+8)"]) == [
        "2026-10-21 00:00:00+08:00", "2026-10-21 01:00:00+08:00",
    ]
    assert app.session_state["admin_users"] == users
    assert [item["id"] for item in app.session_state["admin_user_options"]] == [1, 2]
    assert json.loads(app.json[0].value) == {
        "page": 1, "size": 20, "total": 2, "total_pages": 1,
    }


def test_analytics_day_bucket_displays_local_midnight(monkeypatch, api_client_class):
    monkeypatch.setattr(api_client_class, "analytics_summary", lambda *args, **kwargs: {
        "total_count": 2, "avg_value": 15, "min_value": 10, "max_value": 20,
    })
    monkeypatch.setattr(api_client_class, "analytics_by_category", lambda *args, **kwargs: {"items": []})
    monkeypatch.setattr(api_client_class, "analytics_trend", lambda *args, **kwargs: {
        "points": [{
            "bucket": "2026-10-20T16:00:00Z", "count": 2,
            "avg_value": 15, "min_value": 10, "max_value": 20,
        }],
    })
    monkeypatch.setattr(api_client_class, "analytics_export_excel", lambda *args, **kwargs: b"test")
    app = _page("2_analytics.py").run()
    app.selectbox[0].set_value("day")
    next(button for button in app.button if button.label == "Run Query").click().run()
    assert not app.exception
    assert app.dataframe[0].value["bucket_taipei"].iloc[0] == "2026-10-21 00:00:00+08:00"
    figure = json.loads(app.get("plotly_chart")[0].proto.spec)
    assert figure["data"][0]["x"] == ["2026-10-21T00:00:00+08:00"]
