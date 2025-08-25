import time
from contextlib import contextmanager

@contextmanager
def timer(name: str):
    t0 = time.time()
    try:
        yield
    finally:
        dt = (time.time() - t0) * 1000.0
        print(f"[timer] {name}: {dt:.1f} ms")
