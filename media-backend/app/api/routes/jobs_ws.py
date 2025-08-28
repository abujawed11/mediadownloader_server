# app/api/routes/jobs_ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json, asyncio
from ...services.redis_conn import get_redis
from ...services.job_queue import get_task_status

router = APIRouter()

async def safe_send_json(websocket: WebSocket, data: dict) -> bool:
    """Safely send JSON data to websocket, return False if connection is closed"""
    try:
        # Check if connection is still open
        if hasattr(websocket, 'client_state'):
            if websocket.client_state.value == 3:  # DISCONNECTED
                return False
        await websocket.send_text(json.dumps(data))
        return True
    except (RuntimeError, ConnectionResetError, WebSocketDisconnect) as e:
        print(f"WebSocket connection closed: {e}")
        return False
    except Exception as e:
        print(f"WebSocket send failed: {e}")
        return False

@router.websocket("/ws/tasks/{task_id}")
async def ws_task_progress(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time Celery task progress"""
    try:
        await websocket.accept()
        print(f"WebSocket connection accepted for task {task_id}")
    except Exception as e:
        print(f"Failed to accept WebSocket connection: {e}")
        return

    # Send initial status
    try:
        status = get_task_status(task_id)
        # Convert backend format to frontend format
        if status:
            frontend_status = {
                "id": task_id,  # Frontend expects 'id' not 'task_id'
                "status": status.get("status", "queued"),
                "progress01": status.get("progress", 0),
                "message": status.get("message", ""),
                **status
            }
            if not await safe_send_json(websocket, frontend_status):
                return
    except Exception as e:
        error_msg = {
            "id": task_id,  # Frontend expects 'id' not 'task_id'
            "status": "error", 
            "message": f"Failed to get initial status: {e}"
        }
        if not await safe_send_json(websocket, error_msg):
            return

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
                    # Data is already in frontend format from celery_tasks.py
                    if not await safe_send_json(websocket, data):
                        print(f"WebSocket disconnected while sending pub/sub message for task {task_id}")
                        break
                    
                    # Close connection AFTER sending final status
                    if data.get("status") in ["completed", "failed"] or data.get("finished") or data.get("failed"):
                        print(f"Task {task_id} completed, closing connection after delay")
                        # Send final status then break after a short delay
                        await asyncio.sleep(0.1)
                        break
                        
                except Exception as e:
                    print(f"Error processing pub/sub message: {e}")
                    pass

            now = asyncio.get_event_loop().time()
            
            # Periodic status check (every 5 seconds) as fallback
            if now - last_status_check > 5.0:
                try:
                    status = get_task_status(task_id)
                    if status:
                        # Convert to frontend format
                        frontend_status = {
                            "id": task_id,
                            "status": status.get("status", "queued"),
                            "progress01": status.get("progress", 0),
                            "message": status.get("message", ""),
                            **status
                        }
                        if not await safe_send_json(websocket, frontend_status):
                            print(f"WebSocket disconnected during periodic status check for task {task_id}")
                            break
                        last_status_check = now
                        
                        # Close if task finished
                        if status.get("status") in ["success", "failure", "completed", "failed"]:
                            print(f"Task {task_id} completed (periodic check), closing connection")
                            await asyncio.sleep(0.1)
                            break
                        
                except Exception as e:
                    print(f"Error checking task status: {e}")
                    pass
            
            # Send periodic ping
            if now - last_ping > 20:
                ping_data = {
                    "id": task_id,  # Frontend expects 'id'
                    "type": "ping",
                    "timestamp": now
                }
                if not await safe_send_json(websocket, ping_data):
                    print(f"WebSocket disconnected during ping for task {task_id}")
                    break
                last_ping = now

            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        print(f"WebSocket client disconnected for task {task_id}")
        pass
    except Exception as e:
        print(f"WebSocket error for task {task_id}: {e}")
        # Try to send error message if connection is still alive
        error_msg = {
            "id": task_id,
            "status": "error", 
            "message": f"WebSocket error: {e}"
        }
        await safe_send_json(websocket, error_msg)
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
