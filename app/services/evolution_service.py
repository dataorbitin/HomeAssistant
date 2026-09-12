import asyncio
import logging
import re
from urllib.parse import quote

import httpx

log = logging.getLogger(__name__)


class EvolutionDeliveryError(Exception):
    def __init__(self, code: str, ambiguous: bool = False):
        self.code, self.ambiguous = code, ambiguous
        super().__init__(code)


class EvolutionAPIClient:
    def __init__(self, settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client

    async def send_text_message(self, phone_number: str, message: str) -> str | None:
        # Synthetic seed phones cannot accidentally reach a real WhatsApp user.
        if not re.fullmatch(r"[1-9][0-9]{6,14}", phone_number):
            raise EvolutionDeliveryError("invalid_recipient")
        if not self.settings.evolution_api_key.get_secret_value():
            raise EvolutionDeliveryError("not_configured")
        for attempt in range(self.settings.evolution_max_attempts):
            try:
                response = await self.client.post(
                    self.settings.evolution_api_base_url
                    + "/message/sendText/"
                    + quote(self.settings.evolution_api_instance, safe=""),
                    headers={"apikey": self.settings.evolution_api_key.get_secret_value()},
                    json={"number": phone_number, "text": message},
                    timeout=self.settings.evolution_timeout_seconds,
                )
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
                # These failures happen before the request is sent.
                if attempt + 1 < self.settings.evolution_max_attempts:
                    log.warning(
                        "evolution_retry attempt=%d reason=%s", attempt + 1, type(exc).__name__
                    )
                    await asyncio.sleep(0.25 * 2**attempt)
                    continue
                raise EvolutionDeliveryError("connect_failed") from None
            except httpx.HTTPError:
                # Read/write failures may occur AFTER acceptance: never blind-retry a POST.
                raise EvolutionDeliveryError("transport_unknown", ambiguous=True) from None
            if response.status_code == 429:
                if attempt + 1 < self.settings.evolution_max_attempts:
                    log.warning("evolution_retry attempt=%d reason=rate_limit", attempt + 1)
                    await asyncio.sleep(0.25 * 2**attempt)
                    continue
                raise EvolutionDeliveryError("rate_limited")
            if response.status_code >= 500 or response.status_code == 408:
                raise EvolutionDeliveryError("upstream_unknown", ambiguous=True)
            if not 200 <= response.status_code < 300:
                raise EvolutionDeliveryError("upstream_rejected")
            try:
                payload = response.json()
                external_id = payload.get("key", {}).get("id")
                if isinstance(external_id, str) and len(external_id) <= 200:
                    return external_id
            except (ValueError, AttributeError):
                pass
            return None
        raise EvolutionDeliveryError("attempts_exhausted")
