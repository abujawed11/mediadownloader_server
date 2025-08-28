# app/api/routes/jobs_ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json, asyncio
from ...services.redis_conn import get_redis
from ...services.job_queue import get_task_status

router = APIRouter()

@router.websocket("/ws/tasks/{task_id}")
async def ws_task_progress(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time Celery task progress"""
    await websocket.accept()

    # Send initial status
    try:
        status = get_task_status(task_id)
        await websocket.send_text(json.dumps(status))
    except Exception as e:
        await websocket.send_text(json.dumps({
            "task_id": task_id, 
            "status": "error", 
            "message": f"Failed to get initial status: {e}"
        }))

    # Listen for Redis pub/sub updates
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    channel = f"tasks:{task_id}"
    pubsub.subscribe(channel)

    try:
        last_ping = asyncio.get_event_loop().time()
        last_status_check = last_ping
        
        while True:
            # Check for pub/sub messages
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if msg and msg["type"] == "message":
                try:
                    data = json.loads(msg["data"].decode("utf-8"))
                    await websocket.send_text(json.dumps(data))
                    
                    # Close connection if task is finished
                    if data.get("status") in ["completed", "failed"]:
                        break
                        
                except Exception as e:
                    pass

            now = asyncio.get_event_loop().time()
            
            # Periodic status check (every 5 seconds) as fallback
            if now - last_status_check > 5.0:
                try:
                    status = get_task_status(task_id)
                    await websocket.send_text(json.dumps(status))
                    last_status_check = now
                    
                    # Close if task finished
                    if status.get("status") in ["success", "failure"]:
                        break
                        
                except Exception:
                    pass
            
            # Send periodic ping
            if now - last_ping > 20:
                await websocket.send_text(json.dumps({
                    "task_id": task_id, 
                    "type": "ping",
                    "timestamp": now
                }))
                last_ping = now

            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(json.dumps({
                "task_id": task_id,
                "status": "error", 
                "message": f"WebSocket error: {e}"
            }))
        except:
            pass
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except Exception:
            pass

# Frontend expects individual job endpoints
@router.websocket("/ws/jobs/{job_id}")
async def ws_job_progress_legacy(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for individual job progress - matches frontend expectations"""
    await ws_task_progress(websocket, job_id)
