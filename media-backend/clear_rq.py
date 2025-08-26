import os
from redis import Redis
from rq import Queue
from rq.registry import StartedJobRegistry, ScheduledJobRegistry, DeferredJobRegistry, FailedJobRegistry

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE = os.getenv("QUEUE_NAME", "media")

conn = Redis.from_url(REDIS_URL)
q = Queue(QUEUE, connection=conn)

q.empty()
for Reg in (StartedJobRegistry, ScheduledJobRegistry, DeferredJobRegistry):
    reg = Reg(QUEUE, connection=conn)
    for jid in reg.get_job_ids():
        reg.remove(jid, delete_job=True)

FailedJobRegistry(QUEUE, connection=conn).cleanup(0)

print(f"Cleared queue '{QUEUE}' and registries on {REDIS_URL}.")
