from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect

if __package__ and __package__.startswith("app."):
    from ..config import Settings
    from ..core.security import decode_access_token
    from ..models.user import User
    from .auth import get_current_user
else:
    from config import Settings
    from core.security import decode_access_token
    from models.user import User
    from api.auth import get_current_user

router = APIRouter(tags=["realtime"])


async def _authenticate_websocket(websocket: WebSocket) -> int | None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return None

    settings = Settings()
    try:
        payload = decode_access_token(
            token=token,
            secret_key=settings.jwt_secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
    except jwt.PyJWTError:
        await websocket.close(code=4401, reason="Invalid token")
        return None

    subject = payload.get("sub")
    if subject is None:
        await websocket.close(code=4401, reason="Missing subject")
        return None

    try:
        return int(subject)
    except ValueError:
        await websocket.close(code=4401, reason="Invalid subject")
        return None


@router.websocket("/ws/realtime")
async def realtime_stream(websocket: WebSocket) -> None:
    user_id = await _authenticate_websocket(websocket)
    if user_id is None:
        return

    manager = websocket.app.state.realtime_manager
    service = websocket.app.state.realtime_service

    await service.ensure_started()
    await manager.connect(websocket)

    await websocket.send_json({"event": "connected", "user_id": user_id})

    try:
        while True:
            # use receive to wait for client heartbeat/close event
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
        raise


@router.get("/realtime/status")
async def realtime_status(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    manager = request.app.state.realtime_manager
    service = request.app.state.realtime_service
    return {
        "running": service.running,
        "connected_clients": manager.connected_count,
        "current_user": current_user.username,
    }