import os
import sys
import cv2

# Fix macOS fork safety issue with OpenCV/NumPy
os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
# Limit threads in worker as per technical plan
os.environ["OMP_NUM_THREADS"] = "1"
cv2.setNumThreads(1)

from celery import Celery
from app.config import settings

celery_app = Celery(
    "stellaris_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["workers.tasks.build_index", "workers.tasks.analysis_tasks", "workers.tasks.run_matching"]
)

conf = {
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "UTC",
    "enable_utc": True,
    "broker_connection_retry_on_startup": True,
}

# On macOS, prefork causes SIGSEGV (signal 11) with OpenCV, ONNX Runtime, and Apple CoreFoundation SSL
if sys.platform == "darwin":
    conf["worker_pool"] = "solo"
else:
    conf["worker_concurrency"] = 4

celery_app.conf.update(conf)
