from rq import Worker
from ..services.redis_conn import get_redis
from ..core.config import get_settings

def run():
    settings = get_settings()
    with get_redis() as conn:
        w = Worker([settings.RQ_QUEUE], connection=conn)
        w.work(with_scheduler=True)

if __name__ == "__main__":
    run()
