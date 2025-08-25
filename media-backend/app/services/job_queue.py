from rq import Queue
from app.services.redis_conn import get_redis

_q = None

def default_queue() -> Queue:
    global _q
    if _q is None:
        _q = Queue("default", connection=get_redis())
    return _q

def enqueue_extract(url: str):
    from app.workers.tasks.extract import extract_info_task
    return default_queue().enqueue(extract_info_task, url)

def enqueue_merge(url: str, fmt_selector: str, title_hint: str = ""):
    from app.workers.tasks.download_merge import download_merge_task
    return default_queue().enqueue(download_merge_task, url, fmt_selector, title_hint)
