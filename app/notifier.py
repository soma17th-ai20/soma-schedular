import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app import config


def send_email(to: str, subject: str, body: str, html: str | None = None) -> None:
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        raise RuntimeError("SMTP_USER / SMTP_PASSWORD 환경변수가 설정되지 않았습니다.")
    if not to:
        raise ValueError("수신자(to) 가 비어 있습니다.")

    msg = EmailMessage()
    msg["From"] = formataddr((config.EMAIL_FROM_NAME, config.EMAIL_FROM))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    if html:
        msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
        smtp.send_message(msg)
