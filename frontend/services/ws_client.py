from __future__ import annotations

import json
import queue
import threading
from urllib.parse import urlencode, urlsplit, urlunsplit

import websocket


class RealtimeWSClient:
    def __init__(self, ws_base_url: str, token: str, output_queue: queue.Queue) -> None:
        self.ws_base_url = ws_base_url.rstrip("/")
        self.token = token
        self.output_queue = output_queue
        self._thread: threading.Thread | None = None
        self._ws_app: websocket.WebSocketApp | None = None

    def _build_url(self) -> str:
        normalized_base = self._normalize_ws_base_url(self.ws_base_url)
        parsed = urlsplit(normalized_base)
        path = parsed.path.rstrip("/")

        target_suffix = "/api/v1/ws/realtime"
        if path.endswith(target_suffix):
            final_path = path
        elif path.endswith("/api/v1"):
            final_path = f"{path}/ws/realtime"
        elif path:
            final_path = f"{path}{target_suffix}"
        else:
            final_path = target_suffix

        query = urlencode({"token": self.token})
        return urlunsplit((parsed.scheme, parsed.netloc, final_path, query, ""))

    @staticmethod
    def _normalize_ws_base_url(base_url: str) -> str:
        raw = base_url.strip()
        if "://" not in raw:
            return f"ws://{raw}"
        if raw.startswith("http://"):
            return "ws://" + raw[len("http://") :]
        if raw.startswith("https://"):
            return "wss://" + raw[len("https://") :]
        return raw

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return

        self._ws_app = websocket.WebSocketApp(
            self._build_url(),
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._thread = threading.Thread(
            target=lambda: self._ws_app.run_forever(ping_interval=20, ping_timeout=10),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._ws_app is not None:
            self._ws_app.close()
            self._ws_app = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _on_message(self, _ws, message: str) -> None:
        try:
            payload = json.loads(message)
            if isinstance(payload, dict) and payload.get("event") == "connected":
                return
            self.output_queue.put(payload)
        except Exception as exc:
            self.output_queue.put({"_error": f"ws_message_parse_error: {exc}"})

    def _on_error(self, _ws, error) -> None:
        self.output_queue.put({"_error": f"ws_error: {error}"})

    def _on_close(self, _ws, code, reason) -> None:
        self._ws_app = None
        self.output_queue.put({"_info": f"ws_closed: code={code}, reason={reason}"})
