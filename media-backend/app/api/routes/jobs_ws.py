# app/api/routes/jobs_ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json, asyncio
from ...services.redis_conn import get_queue, get_redis

router = APIRouter()

@router.websocket("/ws/jobs/{job_id}")
async def ws_job_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()

    # Snapshot so UI has immediate state
    try:
        q = get_queue()
        job = q.fetch_job(job_id)
        if job:
            snap = {"id": job_id, **(job.meta or {})}
        else:
            snap = {"id": job_id, "status": "not_found", "progress01": 0.0}
        await websocket.send_text(json.dumps(snap))
    except Exception:
        pass

    # Live Pub/Sub stream
    r = get_redis()
    pubsub = r.pubsub()
    channel = f"jobs:{job_id}"
    pubsub.subscribe(channel)

    try:
        last_ping = asyncio.get_event_loop().time()
        while True:
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg["type"] == "message":
                await websocket.send_text(msg["data"].decode("utf-8"))

            now = asyncio.get_event_loop().time()
            if now - last_ping > 20:
                await websocket.send_text(json.dumps({"id": job_id, "type": "ping"}))
                last_ping = now

            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except Exception:
            pass
