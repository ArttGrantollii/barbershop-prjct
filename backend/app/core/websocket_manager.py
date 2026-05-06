from collections import defaultdict

from fastapi import WebSocket


class SlotConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, room: str) -> None:
        await websocket.accept()
        self._rooms[room].add(websocket)

    def disconnect(self, websocket: WebSocket, room: str) -> None:
        self._rooms[room].discard(websocket)
        if not self._rooms[room]:
            self._rooms.pop(room, None)

    async def broadcast(self, room: str, message: dict) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._rooms.get(room, set())):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(ws, room)


manager = SlotConnectionManager()
