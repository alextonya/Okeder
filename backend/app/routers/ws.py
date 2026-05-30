"""
WebSocket pour les mises à jour temps réel du nombre de commitments.
"""
import uuid
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# In-memory connection store — suffisant pour M0 (single instance)
_connections: dict[str, list[WebSocket]] = defaultdict(list)


@router.websocket("/events/{event_id}")
async def commitment_ws(websocket: WebSocket, event_id: uuid.UUID):
    key = str(event_id)
    await websocket.accept()
    _connections[key].append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive ping
    except WebSocketDisconnect:
        _connections[key].remove(websocket)


async def broadcast_commitment_update(proposal_id: str) -> None:
    """Envoie une mise à jour à tous les clients connectés sur l'event."""
    # proposal_id → event_id lookup via DB serait idéal, mais pour M0
    # on broadcaste sur proposal_id directement (le client écoute sur event_id)
    import json

    dead = []
    for ws in _connections.get(proposal_id, []):
        try:
            await ws.send_text(json.dumps({"type": "commitment_update", "proposal_id": proposal_id}))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connections[proposal_id].remove(ws)
