import json
import logging
import re
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.prompts.service_intent_prompt import SERVICE_INTENT_PROMPT
from app.schemas.intent import ServiceIntent

log = logging.getLogger(__name__)


class AIUnavailable(Exception):
    pass


class IntentExtractor(Protocol):
    async def extract(
        self, text: str, history: list[dict], categories: list[str]
    ) -> ServiceIntent: ...


def redact_contacts(text: str) -> str:
    return re.sub(r"(?<!\w)\+?\d[\d ()-]{5,}\d", "[contact omitted]", text)


class AIService:
    """OpenAI-compatible chat completions; output has no authority over database access."""

    def __init__(self, settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client

    async def extract(self, text: str, history: list[dict], categories: list[str]) -> ServiceIntent:
        if not self.settings.openai_api_key.get_secret_value() or not self.settings.openai_model:
            raise AIUnavailable("LLM not configured")
        schema = ServiceIntent.model_json_schema()
        messages = [
            {
                "role": "system",
                "content": SERVICE_INTENT_PROMPT
                + "\nCategories: "
                + json.dumps(categories)
                + "\nJSON schema: "
                + json.dumps(schema),
            }
        ]
        messages.extend(
            {"role": item["role"], "content": redact_contacts(item["content"])} for item in history
        )
        messages.append({"role": "user", "content": redact_contacts(text)})
        try:
            response = await self.client.post(
                self.settings.openai_base_url + "/chat/completions",
                headers={
                    "Authorization": "Bearer " + self.settings.openai_api_key.get_secret_value()
                },
                json={
                    "model": self.settings.openai_model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                    "max_tokens": 500,
                },
                timeout=self.settings.llm_timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return ServiceIntent.model_validate_json(content)
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            ValidationError,
        ) as exc:
            log.warning("intent_extraction_failed error=%s", type(exc).__name__)
            raise AIUnavailable("Intent extraction unavailable") from None
