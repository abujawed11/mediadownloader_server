# Media Backend (FastAPI + RQ + yt-dlp + FFmpeg + Redis)

## Dev quickstart (Linux/WSL2)
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip ffmpeg redis-server
python3.11 -m venv .venv && source .venv/bin/activate
pip install -U pip wheel && pip install -r requirements.txt
# terminal A:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# terminal B:
python -m app.workers.worker
