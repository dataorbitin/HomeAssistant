from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Intent(StrEnum):
    FIND_SERVICE = "FIND_SERVICE"
    GREETING = "GREETING"
    THANK_YOU = "THANK_YOU"
    FEEDBACK = "FEEDBACK"
    UNKNOWN = "UNKNOWN"


class ServiceIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: Intent
    service_category: str | None = Field(
        default=None, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    requirement: str | None = Field(default=None, max_length=1000)
    urgency: Literal["LOW", "NORMAL", "HIGH"] | None = None
    preferred_time: str | None = Field(default=None, max_length=120)
    recommendation_rank: int | None = Field(default=None, ge=1, le=3)
    rating: int | None = Field(default=None, ge=1, le=5)
    feedback: str | None = Field(default=None, max_length=1000)
    contacted: bool = False
