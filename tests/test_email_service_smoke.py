from app.services.email import send_email


def test_send_email_smoke_without_smtp_config(monkeypatch) -> None:
    for key in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM", "SMTP_TLS"):
        monkeypatch.delenv(key, raising=False)

    sent = send_email(
        to="smoke@example.com",
        subject="Smoke email",
        body_html="<p>This is a smoke email.</p>",
        body_text="This is a smoke email.",
    )

    assert sent is False
