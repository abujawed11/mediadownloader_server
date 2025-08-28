# app/api/routes/jobs_bus.py  
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio, json
from ...services.redis_conn import get_redis

router = APIRouter()

@router.websocket("/ws/tasks")
async def ws_tasks_bus(websocket: WebSocket):
    """WebSocket bus for all task updates"""
    await websocket.accept()
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    pubsub.psubscribe("tasks:*")

    try:
        last_ping = asyncio.get_event_loop().time()
        while True:
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] in ("message", "pmessage"):
                try:
                    data = msg["data"].decode("utf-8")
                    await websocket.send_text(data)
                except Exception:
                    break

            now = asyncio.get_event_loop().time()
            if now - last_ping > 30:
                await websocket.send_text(json.dumps({
                    "type": "ping",
                    "timestamp": now
                }))
                last_ping = now

            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            pubsub.punsubscribe("tasks:*")
            pubsub.close()
        except Exception:
            pass

# Legacy endpoint for backward compatibility
@router.websocket("/ws/jobs")
async def ws_jobs_bus_legacy(websocket: WebSocket):
    """Legacy WebSocket bus - redirects to tasks"""
    await ws_tasks_bus(websocket)
