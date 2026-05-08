import logging
from typing import Any

from app.celery_app import celery_app
from app.notifier import send_email

logger = logging.getLogger(__name__)


def fetch_pending_notifications() -> list[dict[str, Any]]:
    """매칭 엔진(score>=7) 결과로 발송 대기중인 알림을 반환.

    DB(notifications 테이블) 가 붙기 전까지는 빈 리스트.
    AI 매칭 팀 결과물이 준비되면 이 함수만 교체하면 됨.
    """
    return []


@celery_app.task(name="app.tasks.dispatch_pending_notifications")
def dispatch_pending_notifications() -> dict[str, int]:
    """Celery Beat 가 30분마다 호출. 발송 대기 알림을 큐에 적재."""
    pending = fetch_pending_notifications()
    logger.info("dispatch: %d pending notifications", len(pending))
    for n in pending:
        send_email_task.delay(
            to=n["to"],
            subject=n["subject"],
            body=n["body"],
            html=n.get("html"),
        )
    return {"queued": len(pending)}


@celery_app.task(
    name="app.tasks.send_email_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def send_email_task(self, to: str, subject: str, body: str, html: str | None = None) -> dict[str, str]:
    """이메일 1건 발송. 실패 시 지수 백오프 재시도(최대 3회)."""
    send_email(to=to, subject=subject, body=body, html=html)
    logger.info("email sent: to=%s subject=%s", to, subject)
    return {"to": to, "status": "sent"}
