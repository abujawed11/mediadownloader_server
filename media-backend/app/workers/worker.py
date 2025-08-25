from rq import Worker, Queue, Connection
from app.services.redis_conn import get_redis

if __name__ == "__main__":
    with Connection(get_redis()):
        Worker([Queue("default")]).work()
