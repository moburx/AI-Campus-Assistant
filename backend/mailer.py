"""Имэйл илгээх модуль.

EMAIL_MODE:
- console (анхдагч): имэйлийг илгээхгүй, терминалд хэвлэнэ. Хөгжүүлэлтэд.
- smtp: SMTP серверээр (жишээ нь Gmail + App Password) жинхэнээр илгээнэ.

Шалгах: python -m backend.mailer you@example.com
"""

import logging
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 15
MAX_OUTBOX_SIZE = 50

# console горимд илгээсэн имэйлүүд (тест болон хөгжүүлэлтэд шалгахад).
outbox: list = []


class EmailError(Exception):
    """Имэйл илгээж чадаагүй (тохиргоо дутуу эсвэл SMTP алдаа)."""


def get_email_mode() -> str:
    mode = os.getenv("EMAIL_MODE", "console").strip().lower()
    if mode not in ("console", "smtp"):
        raise EmailError(f"Unknown EMAIL_MODE: {mode}")
    return mode


def get_smtp_settings() -> dict:
    settings = {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", "").strip(),
        # Gmail App Password-ийг "abcd efgh ijkl mnop" гэж хуулдаг тул зайг арилгана.
        "password": os.getenv("SMTP_PASSWORD", "").replace(" ", ""),
    }
    if not settings["user"] or not settings["password"]:
        raise EmailError("SMTP_USER and SMTP_PASSWORD must be set when EMAIL_MODE=smtp")
    return settings


def build_message(to: str, subject: str, text: str, html: str | None = None) -> EmailMessage:
    if not to or "@" not in to:
        raise EmailError("Invalid recipient address")
    # Толгой мөрөнд мөр шилжилт орвол өөр толгой нэмэгдэх аюултай (header injection).
    if any(ch in value for value in (to, subject) for ch in "\r\n"):
        raise EmailError("Recipient and subject must be a single line")

    sender_address = os.getenv("EMAIL_FROM") or os.getenv("SMTP_USER") or "no-reply@localhost"
    sender_name = os.getenv("EMAIL_FROM_NAME", "AI Campus Assistant")

    message = EmailMessage()
    message["From"] = formataddr((sender_name, sender_address))
    message["To"] = to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=sender_address.split("@")[-1] or "localhost")
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")
    return message


def _print_to_console(message: EmailMessage) -> None:
    outbox.append(message)
    del outbox[:-MAX_OUTBOX_SIZE]

    body = message.get_body(preferencelist=("plain",))
    print(
        "\n----- [EMAIL_MODE=console] email not sent -----\n"
        f"To: {message['To']}\nSubject: {message['Subject']}\n\n"
        f"{body.get_content().strip() if body else ''}\n"
        "-----------------------------------------------\n",
        flush=True,
    )


def create_ssl_context() -> ssl.SSLContext:
    """Сертификат шалгадаг SSL context.

    macOS дээрх python.org-ийн Python системийн сертификатыг уншдаггүй тул
    (CERTIFICATE_VERIFY_FAILED) certifi багцын сертификатуудыг ашиглана.
    Шалгалтыг унтраах нь аюултай тул хэзээ ч унтраахгүй.
    """
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _send_with_smtp(message: EmailMessage, smtp_class=smtplib.SMTP) -> None:
    settings = get_smtp_settings()
    try:
        with smtp_class(settings["host"], settings["port"], timeout=SMTP_TIMEOUT_SECONDS) as server:
            server.starttls(context=create_ssl_context())
            server.login(settings["user"], settings["password"])
            server.send_message(message)
    except smtplib.SMTPAuthenticationError as error:
        raise EmailError(
            "SMTP login failed. For Gmail, use a 16-character App Password, not your normal password."
        ) from error
    except (smtplib.SMTPException, OSError) as error:
        raise EmailError(f"Could not send email: {error}") from error


def send_email(to: str, subject: str, text: str, html: str | None = None, smtp_class=smtplib.SMTP) -> None:
    """Имэйл илгээнэ. Амжилтгүй бол EmailError шиднэ."""
    message = build_message(to.strip(), subject.strip(), text, html)

    if get_email_mode() == "console":
        _print_to_console(message)
        return

    _send_with_smtp(message, smtp_class=smtp_class)
    logger.info("Email sent to %s: %s", message["To"], message["Subject"])


def main(argv: list) -> int:
    if len(argv) != 2:
        print("Usage: python -m backend.mailer you@example.com")
        return 2

    from dotenv import load_dotenv

    load_dotenv(".env")
    try:
        send_email(
            argv[1],
            "AI Campus Assistant test email",
            "If you can read this, email sending works. 🎉",
        )
    except EmailError as error:
        print(f"Failed: {error}")
        return 1

    print(f"OK (EMAIL_MODE={get_email_mode()})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
