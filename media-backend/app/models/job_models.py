from enum import Enum

class JobStatus(str, Enum):
    queued = "queued"
    downloading = "downloading"
    merging = "merging"
    done = "done"
    error = "error"
    paused = "paused"
    canceled = "canceled"
