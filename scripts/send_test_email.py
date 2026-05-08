"""SMTP 단독 발송 검증.

Celery / Redis 없이 SMTP 경로만 점검. '실제 1건 성공' 의 가장 빠른 증명 경로.
사용: python -m scripts.send_test_email [수신자_이메일]
"""
import sys

from app import config
from app.notifier import send_email


def main() -> None:
    to = sys.argv[1] if len(sys.argv) > 1 else config.TEST_EMAIL_TO
    if not to:
        raise SystemExit("수신자 이메일이 필요합니다. 인자로 넘기거나 .env 의 TEST_EMAIL_TO 를 설정하세요.")
    send_email(
        to=to,
        subject="[학교공지 알림] SMTP 발송 테스트",
        body=(
            "SMTP 연결과 발송 경로가 정상 동작합니다.\n"
            "이 메일이 보이면 1건 실제 발송 성공.\n\n"
            "— 학교공지 알림봇"
        ),
    )
    print(f"sent to {to}")


if __name__ == "__main__":
    main()
