from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.websocket_manager import manager

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/slots/{date}")
async def slot_updates(websocket: WebSocket, date: str) -> None:
    await manager.connect(websocket, room=date)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, room=date)
