from __future__ import annotations

from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from pickone.core.logging import get_logger
from pickone.core.outbox import enqueue

logger = get_logger(__name__)

OUTBOX_KIND_EMAIL = "send_email"


class EmailProvider(Protocol):
    async def send(self, *, to: str, subject: str, body: str) -> None: ...


class ConsoleProvider:
    async def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info("email_console", to=to, subject=subject, body=body)


class ResendProvider:
    def __init__(self, api_key: str, from_address: str, from_name: str) -> None:
        self._api_key = api_key
        self._from = f"{from_name} <{from_address}>"

    async def send(self, *, to: str, subject: str, body: str) -> None:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"from": self._from, "to": [to], "subject": subject, "text": body},
            )
            resp.raise_for_status()


def build_provider() -> EmailProvider:
    from pickone.core.config import get_settings

    settings = get_settings()
    if settings.email_provider == "resend":
        return ResendProvider(settings.resend_api_key, settings.mail_from, settings.mail_from_name)
    return ConsoleProvider()


class OutboxProvider:
    async def send(self, session: AsyncSession, *, to: str, subject: str, body: str) -> None:
        await enqueue(
            session, kind=OUTBOX_KIND_EMAIL, payload={"to": to, "subject": subject, "body": body}
        )


def verify_email_template(*, verify_url: str) -> tuple[str, str]:
    subject = "Verify your email — PickOne"
    body = f"One click and you're in.\n\n{verify_url}\n\nThis link works for 24 hours."
    return subject, body


def reset_password_template(*, reset_url: str) -> tuple[str, str]:
    subject = "Reset your password — PickOne"
    body = (
        f"Set a new password here.\n\n{reset_url}\n\n"
        "This link works for an hour. Didn't ask for this? Ignore it."
    )
    return subject, body
