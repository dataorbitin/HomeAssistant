from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True, hide_input_in_errors=True
    )

    database_url: SecretStr = SecretStr("postgresql+psycopg://localhost/home_assistant")
    migration_database_url: SecretStr = SecretStr("")
    supabase_url: str = ""
    supabase_key: SecretStr = SecretStr("")
    evolution_api_base_url: str = Field(
        default="http://localhost:8080",
        validation_alias=AliasChoices("EVOLUTION_API_BASE_URL", "EVOLUTION_API_URL"),
    )
    evolution_api_instance: str = Field(
        default="home-assistance",
        validation_alias=AliasChoices("EVOLUTION_API_INSTANCE", "EVOLUTION_INSTANCE"),
    )
    evolution_api_key: SecretStr = SecretStr("")
    webhook_secret: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    app_env: Literal["development", "test", "production"] = "development"
    admin_api_key: SecretStr = SecretStr("")
    default_society_name: str = "Megapolis"
    max_context_messages: int = Field(default=8, ge=0, le=30)
    max_context_characters: int = Field(default=6000, ge=0, le=20000)
    llm_timeout_seconds: float = Field(default=20, gt=0, le=120)
    evolution_timeout_seconds: float = Field(default=15, gt=0, le=60)
    evolution_max_attempts: int = Field(default=3, ge=1, le=5)
    outbox_poll_seconds: float = Field(default=3, ge=0.1, le=60)
    outbox_enabled: bool = True
    store_raw_payloads: bool = False

    @field_validator("evolution_api_base_url", "openai_base_url")
    @classmethod
    def valid_base_url(cls, value: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.query
        ):
            raise ValueError("Expected an HTTP(S) base URL without credentials or query parameters")
        return value.rstrip("/")

    @model_validator(mode="after")
    def production_requirements(self):
        if self.app_env == "production":
            if (
                self.database_url.get_secret_value()
                == "postgresql+psycopg://localhost/home_assistant"
            ):
                raise ValueError("DATABASE_URL is required in production")
            for field in ("evolution_api_key", "openai_api_key", "admin_api_key"):
                if not getattr(self, field).get_secret_value():
                    raise ValueError(f"{field.upper()} is required in production")
            if len(self.webhook_secret.get_secret_value()) < 32:
                raise ValueError("WEBHOOK_SECRET must have at least 32 characters in production")
            if not self.openai_model:
                raise ValueError("OPENAI_MODEL is required in production")
            if not self.database_url.get_secret_value().startswith(("postgres://", "postgresql")):
                raise ValueError("Production requires PostgreSQL")
            if not all(
                url.startswith("https://")
                for url in (self.evolution_api_base_url, self.openai_base_url)
            ):
                raise ValueError("Production API base URLs must use HTTPS")
        return self
