from redis import Redis
from rq import Queue
from ..core.config import get_settings

_redis = None
_queue = None

def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.REDIS_URL)
    return _redis

def get_queue() -> Queue:
    global _queue
    if _queue is None:
        settings = get_settings()
        _queue = Queue(settings.RQ_QUEUE, connection=get_redis(),
                       default_timeout=settings.RQ_JOB_TTL,
                       result_ttl=settings.RQ_RESULT_TTL,
                       failure_ttl=settings.RQ_FAILURE_TTL)
    return _queue
