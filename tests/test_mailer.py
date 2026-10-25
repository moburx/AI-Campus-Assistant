import smtplib
import ssl

import pytest

from backend import mailer


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in ("EMAIL_MODE", "EMAIL_FROM", "EMAIL_FROM_NAME", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD"):
        monkeypatch.delenv(name, raising=False)
    mailer.outbox.clear()
    yield
    mailer.outbox.clear()


class FakeSMTP:
    """smtplib.SMTP-ийн оронд: юу дуудагдсаныг тэмдэглэнэ."""

    instances = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.calls = []
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.calls.append("quit")

    def starttls(self, context=None):
        self.calls.append("starttls")
        self.context = context

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, message):
        self.sent.append(message)


class BadLoginSMTP(FakeSMTP):
    def login(self, user, password):
        raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")


class DownSMTP(FakeSMTP):
    def __init__(self, *args, **kwargs):
        raise OSError("Network is unreachable")


def use_smtp(monkeypatch):
    monkeypatch.setenv("EMAIL_MODE", "smtp")
    monkeypatch.setenv("SMTP_USER", "campus.bot@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "abcd efgh ijkl mnop")
    FakeSMTP.instances.clear()


# ---------- console горим ----------
def test_console_mode_is_default_and_does_not_use_smtp(capsys):
    mailer.send_email("student@example.com", "Hello", "Body text", smtp_class=DownSMTP)

    assert len(mailer.outbox) == 1
    assert mailer.outbox[0]["To"] == "student@example.com"
    printed = capsys.readouterr().out
    assert "Subject: Hello" in printed
    assert "Body text" in printed


def test_console_outbox_keeps_only_recent_messages():
    for number in range(mailer.MAX_OUTBOX_SIZE + 5):
        mailer.send_email("a@example.com", f"Mail {number}", "x")

    assert len(mailer.outbox) == mailer.MAX_OUTBOX_SIZE
    assert mailer.outbox[-1]["Subject"] == f"Mail {mailer.MAX_OUTBOX_SIZE + 4}"


# ---------- Мессеж бүтээх ----------
def test_message_has_text_and_html_parts(monkeypatch):
    monkeypatch.setenv("EMAIL_FROM", "bot@example.com")

    message = mailer.build_message("a@example.com", "Hi", "plain", "<p>html</p>")

    assert message["From"] == "AI Campus Assistant <bot@example.com>"
    assert message.get_body(("plain",)).get_content().strip() == "plain"
    assert message.get_body(("html",)).get_content().strip() == "<p>html</p>"


@pytest.mark.parametrize(
    "to, subject",
    [
        ("not-an-email", "Hi"),
        ("", "Hi"),
        ("a@example.com\r\nBcc: evil@example.com", "Hi"),
        ("a@example.com", "Hi\nBcc: evil@example.com"),
    ],
)
def test_bad_recipient_or_subject_is_rejected(to, subject):
    with pytest.raises(mailer.EmailError):
        mailer.build_message(to, subject, "body")


def test_unknown_mode_is_an_error(monkeypatch):
    monkeypatch.setenv("EMAIL_MODE", "carrier-pigeon")

    with pytest.raises(mailer.EmailError):
        mailer.send_email("a@example.com", "Hi", "body")


# ---------- smtp горим ----------
def test_smtp_mode_uses_starttls_and_login(monkeypatch):
    use_smtp(monkeypatch)

    mailer.send_email("student@example.com", "Hello", "Body", smtp_class=FakeSMTP)

    server = FakeSMTP.instances[0]
    assert (server.host, server.port) == ("smtp.gmail.com", 587)
    assert server.timeout == mailer.SMTP_TIMEOUT_SECONDS
    # App Password доторх зай арилсан байх ёстой.
    assert server.calls[:2] == ["starttls", ("login", "campus.bot@gmail.com", "abcdefghijklmnop")]
    assert server.sent[0]["To"] == "student@example.com"
    assert "campus.bot@gmail.com" in server.sent[0]["From"]
    assert mailer.outbox == []
    # Сертификат шалгалт идэвхтэй байх ёстой.
    assert server.context.verify_mode == ssl.CERT_REQUIRED
    assert server.context.check_hostname is True


def test_smtp_mode_without_credentials_fails(monkeypatch):
    monkeypatch.setenv("EMAIL_MODE", "smtp")

    with pytest.raises(mailer.EmailError, match="SMTP_USER"):
        mailer.send_email("a@example.com", "Hi", "body", smtp_class=FakeSMTP)


def test_wrong_gmail_password_gives_helpful_error(monkeypatch):
    use_smtp(monkeypatch)

    with pytest.raises(mailer.EmailError, match="App Password"):
        mailer.send_email("a@example.com", "Hi", "body", smtp_class=BadLoginSMTP)


def test_network_error_becomes_email_error(monkeypatch):
    use_smtp(monkeypatch)

    with pytest.raises(mailer.EmailError, match="Could not send"):
        mailer.send_email("a@example.com", "Hi", "body", smtp_class=DownSMTP)


# ---------- CLI ----------
def test_cli_needs_one_address(capsys):
    assert mailer.main(["mailer"]) == 2
    assert "Usage" in capsys.readouterr().out


def test_cli_sends_test_email_in_console_mode(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)  # жинхэнэ .env уншихгүйн тулд

    assert mailer.main(["mailer", "me@example.com"]) == 0
    assert mailer.outbox[0]["To"] == "me@example.com"
    assert "OK (EMAIL_MODE=console)" in capsys.readouterr().out


def test_ssl_context_uses_certifi_bundle():
    certifi = pytest.importorskip("certifi")

    context = mailer.create_ssl_context()

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.cert_store_stats()["x509_ca"] > 0
    assert certifi.where()
