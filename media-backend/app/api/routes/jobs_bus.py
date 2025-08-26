# app/api/routes/jobs_bus.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio, json
from ...services.redis_conn import get_redis

router = APIRouter()

@router.websocket("/ws/jobs")
async def ws_jobs_bus(websocket: WebSocket):
    await websocket.accept()
    r = get_redis()
    p = r.pubsub()
    p.psubscribe("jobs:*")

    try:
        last_ping = asyncio.get_event_loop().time()
        while True:
            msg = p.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] in ("message", "pmessage"):
                data = msg["data"]
                try:
                    await websocket.send_text(data.decode("utf-8"))
                except Exception:
                    # if sending fails, close out
                    break

            now = asyncio.get_event_loop().time()
            if now - last_ping > 20:
                # keepalive
                await websocket.send_text(json.dumps({"type": "ping"}))
                last_ping = now

            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            p.punsubscribe("jobs:*")
            p.close()
        except Exception:
            pass
