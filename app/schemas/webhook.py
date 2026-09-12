import re
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class IncomingMessage(BaseModel):
    model_config = ConfigDict(strict=True)
    external_message_id: str = Field(min_length=1, max_length=200)
    phone_number: str
    text: str = Field(min_length=1, max_length=4096)
    timestamp: datetime | None = None
    raw: dict

    @field_validator("phone_number")
    @classmethod
    def phone_is_e164_digits(cls, value):
        if not re.fullmatch(r"[1-9][0-9]{6,14}", value):
            raise ValueError("Invalid sender")
        return value

    @field_validator("text", "external_message_id")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Empty value")
        return value


def parse_webhook(payload: dict, instance: str) -> list[IncomingMessage]:
    event = payload.get("event")
    if not isinstance(event, str) or event.lower().replace("_", ".") != "messages.upsert":
        return []
    if payload.get("instance") != instance:
        return []
    data = payload.get("data")
    entries = data if isinstance(data, list) else [data]
    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key, message = entry.get("key"), entry.get("message")
        if (
            not isinstance(key, dict)
            or not isinstance(message, dict)
            or key.get("fromMe") is not False
        ):
            continue
        jid = key.get("remoteJid")
        if not isinstance(jid, str) or not jid.endswith("@s.whatsapp.net"):
            continue
        extended = message.get("extendedTextMessage")
        text_value = message.get("conversation")
        if text_value is None and isinstance(extended, dict):
            text_value = extended.get("text")
        timestamp = None
        raw_timestamp = entry.get("messageTimestamp")
        if isinstance(raw_timestamp, (int, float)) and not isinstance(raw_timestamp, bool):
            try:
                timestamp = datetime.fromtimestamp(raw_timestamp, UTC)
            except (OverflowError, OSError, ValueError):
                pass
        try:
            result.append(
                IncomingMessage(
                    external_message_id=key.get("id"),
                    phone_number=jid.removesuffix("@s.whatsapp.net"),
                    text=text_value,
                    timestamp=timestamp,
                    raw=entry,
                )
            )
        except ValidationError:
            continue
    return result
