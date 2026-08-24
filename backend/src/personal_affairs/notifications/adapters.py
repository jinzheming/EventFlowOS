from dataclasses import dataclass

import httpx

from personal_affairs.config import Settings
from personal_affairs.domain.enums import DeliveryChannel


@dataclass(frozen=True)
class NotificationResult:
    ok: bool
    status_code: int
    provider_message_id: str | None = None
    body: str | None = None


class NotificationAdapter:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def send(self, channel: DeliveryChannel, title: str, body: str) -> NotificationResult:
        if channel == DeliveryChannel.IN_APP:
            return NotificationResult(ok=True, status_code=200, provider_message_id="in_app")
        if channel == DeliveryChannel.FEISHU:
            return await self._send_feishu(title, body)
        if channel == DeliveryChannel.NTFY:
            return await self._send_ntfy(title, body)
        return NotificationResult(ok=False, status_code=400, body="unsupported channel")

    async def _send_feishu(self, title: str, body: str) -> NotificationResult:
        if not self.settings.feishu_webhook_url:
            return NotificationResult(ok=False, status_code=503, body="Feishu webhook is not configured")
        payload = {"msg_type": "text", "content": {"text": f"{title}\n{body}"}}
        async with httpx.AsyncClient(timeout=self.settings.notification_provider_timeout_seconds) as client:
            response = await client.post(self.settings.feishu_webhook_url, json=payload)
        return NotificationResult(response.is_success, response.status_code, body=response.text[:500])

    async def _send_ntfy(self, title: str, body: str) -> NotificationResult:
        if not self.settings.ntfy_topic_url:
            return NotificationResult(ok=False, status_code=503, body="ntfy topic is not configured")
        async with httpx.AsyncClient(timeout=self.settings.notification_provider_timeout_seconds) as client:
            response = await client.post(
                self.settings.ntfy_topic_url,
                content=body.encode("utf-8"),
                headers={"Title": title},
            )
        return NotificationResult(response.is_success, response.status_code, body=response.text[:500])
