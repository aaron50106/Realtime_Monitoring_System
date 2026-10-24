from dataclasses import dataclass
from typing import Any
import requests


@dataclass
class APIClient:
    base_url: str
    token: str | None = None

    def _headers(self) -> dict[str, str]:
        h = {"accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _params(self, d: dict[str, Any] | None):
        if not d:
            return None
        return {k: v for k, v in d.items() if v not in (None, "", [])}

    # auth
    def login(self, username: str, password: str):
        r = requests.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"username": username, "password": password},
            headers=self._headers(),
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    def me(self):
        r = requests.get(f"{self.base_url}/api/v1/auth/me", headers=self._headers(), timeout=20)
        r.raise_for_status()
        return r.json()

    # realtime
    def realtime_status(self):
        r = requests.get(f"{self.base_url}/api/v1/realtime/status", headers=self._headers(), timeout=5)
        r.raise_for_status()
        return r.json()

    # analytics
    def analytics_summary(self, params: dict[str, Any]):
        r = requests.get(f"{self.base_url}/api/v1/analytics/summary", params=self._params(params), headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def analytics_by_category(self, params: dict[str, Any]):
        r = requests.get(f"{self.base_url}/api/v1/analytics/by-category", params=self._params(params), headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def analytics_trend(self, params: dict[str, Any]):
        r = requests.get(f"{self.base_url}/api/v1/analytics/trend", params=self._params(params), headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def analytics_export_excel(self, params: dict[str, Any]):
        r = requests.get(f"{self.base_url}/api/v1/analytics/export/excel", params=self._params(params), headers=self._headers(), timeout=60)
        r.raise_for_status()
        return r.content

    # admin
    def admin_list_users(self, page=1, size=20, keyword=None, role=None):
        params = {"page": page, "size": size, "keyword": keyword, "role": role}
        r = requests.get(f"{self.base_url}/api/v1/admin/users", params=self._params(params), headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    def admin_update_role(self, user_id: int, role: str):
        r = requests.patch(
            f"{self.base_url}/api/v1/admin/users/{user_id}/role",
            json={"role": role},
            headers=self._headers(),
            timeout=20,
        )
        r.raise_for_status()
        return r.json()

    # data records
    def list_data_records(
        self,
        *,
        page: int = 1,
        size: int = 20,
        category: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        sort_by: str = "timestamp",
        sort_order: str = "desc",
    ):
        params = {
            "page": page,
            "size": size,
            "category": category,
            "start_time": start_time,
            "end_time": end_time,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        r = requests.get(
            f"{self.base_url}/api/v1/data-records",
            params=self._params(params),
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def create_data_record(self, payload: dict[str, Any]):
        r = requests.post(
            f"{self.base_url}/api/v1/data-records",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def update_data_record(self, record_id: int, payload: dict[str, Any]):
        r = requests.put(
            f"{self.base_url}/api/v1/data-records/{record_id}",
            json=payload,
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def delete_data_record(self, record_id: int):
        r = requests.delete(
            f"{self.base_url}/api/v1/data-records/{record_id}",
            headers=self._headers(),
            timeout=30,
        )
        r.raise_for_status()
        return {"status": "deleted"}

    def import_data_records_json(self, payload: dict[str, Any]):
        r = requests.post(
            f"{self.base_url}/api/v1/data-records/import/json",
            json=payload,
            headers=self._headers(),
            timeout=60,
        )
        r.raise_for_status()
        return r.json()

    def import_data_records_csv(self, *, filename: str, content: bytes):
        files = {"file": (filename, content, "text/csv")}
        r = requests.post(
            f"{self.base_url}/api/v1/data-records/import/csv",
            files=files,
            headers={"Authorization": self._headers().get("Authorization", "")},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()