from app.services.email import send_email as _smtp_send_email


def send_email(*, to_email: str, subject: str, body: str) -> bool:
    return _smtp_send_email(
        to=to_email,
        subject=subject,
        body_html=None,
        body_text=body,
    )
