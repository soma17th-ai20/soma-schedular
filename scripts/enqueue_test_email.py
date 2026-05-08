"""Redis 큐 + Celery 워커 경로 검증.

워커가 떠 있어야 발송됨. 큐 적재 자체는 워커 없이도 성공.
사용: python -m scripts.enqueue_test_email [수신자_이메일]
"""
import sys

from app import config
from app.tasks import send_email_task


def main() -> None:
    to = sys.argv[1] if len(sys.argv) > 1 else config.TEST_EMAIL_TO
    if not to:
        raise SystemExit("수신자 이메일이 필요합니다. 인자로 넘기거나 .env 의 TEST_EMAIL_TO 를 설정하세요.")
    res = send_email_task.delay(
        to=to,
        subject="[학교공지 알림] Celery 큐 발송 테스트",
        body=(
            "이 메시지는 Redis 큐 → Celery 워커 경로로 발송되었습니다.\n\n"
            "— 학교공지 알림봇"
        ),
    )
    print(f"queued task id={res.id} to={to}")


if __name__ == "__main__":
    main()
