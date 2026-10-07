"""App configuration, read from environment variables and the repo's .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"  # comma-separated

    database_url: str = "postgresql+psycopg://circuit:circuit@localhost:5432/circuit"
    db_connect_timeout_s: int = 5

    city_name: str = "Bengaluru"
    city_center_lat: float = 12.9716
    city_center_lng: float = 77.5946

    jwks_url: str | None = None
    demo_auth: bool = False
    demo_public: bool = False

    anthropic_api_key: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _refuse_demo_auth_in_production(self) -> "Settings":
        if self.env == "production" and self.demo_auth and not self.demo_public:
            raise ValueError(
                "DEMO_AUTH=true is not allowed when ENV=production. "
                "Set DEMO_PUBLIC=true only for a demo deployment that holds fake data."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
