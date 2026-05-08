from celery import Celery
from celery.schedules import crontab

from app import config

celery_app = Celery(
    "schedular",
    broker=config.REDIS_URL,
    backend=config.REDIS_URL,
    include=["app.tasks"],
)

celery_app.conf.update(
    timezone="Asia/Seoul",
    enable_utc=False,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

# 매시 :00, :30 에 디스패처 실행 (기획서: 30분 주기)
celery_app.conf.beat_schedule = {
    "dispatch-pending-notifications-every-30-min": {
        "task": "app.tasks.dispatch_pending_notifications",
        "schedule": crontab(minute="*/30"),
    },
}
