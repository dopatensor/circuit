"""App configuration, read from environment variables and the repo's .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_DEMO_SECRET = "dev-only-demo-secret-change-me-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # "KEY=" in .env means "use the default"
    )

    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173"  # comma-separated

    database_url: str = "postgresql+psycopg://circuit:circuit@localhost:5432/circuit"
    db_connect_timeout_s: int = 5

    city_name: str = "Bengaluru"
    city_center_lat: float = 12.9716
    city_center_lng: float = 77.5946

    # Real logins: tokens signed by the auth provider (Clerk or Supabase), checked
    # against its published keys (JWKS). Issuer/audience are checked when set.
    jwks_url: str | None = None
    jwt_issuer: str | None = None
    jwt_audience: str | None = None

    # Demo logins: we sign short-lived tokens for seeded personas ourselves.
    demo_auth: bool = False
    demo_public: bool = False
    demo_jwt_secret: str = DEV_DEMO_SECRET
    demo_token_ttl_minutes: int = 8 * 60

    # Embeddings (Phase 4): "fastembed" runs BAAI/bge-small-en-v1.5 locally (downloads
    # ~130 MB once); "fake" is a fast deterministic stand-in for tests and offline use.
    embedding_provider: Literal["fastembed", "fake"] = "fastembed"
    embedding_cache_dir: str = str(Path.home() / ".cache" / "circuit" / "fastembed")

    # Matching weights (Phase 4): score = w1*complementarity + w2*affinity
    #   + w3*trust_path + w4*timing - w5*load_penalty
    match_w_complementarity: float = 0.50
    match_w_affinity: float = 0.20
    match_w_trust_path: float = 0.15
    match_w_timing: float = 0.10
    match_w_load_penalty: float = 0.15
    match_results_per_member: int = 20
    match_bridge_share: float = 0.25  # share of results reserved for bridge matches
    student_radius_km: float = 10.0  # hard distance filter for students
    match_refresh_hours: float = 6.0  # background job interval
    scheduler_enabled: bool = True

    # Warm intros (F5). Each member's weekly capacity is members.open_intro_slots: it
    # covers requests they receive and requests they are asked to pass on.
    intro_requests_per_week: int = 5  # how many requests one member may send per week
    intro_expiry_days: int = 14  # unanswered requests expire after this

    # Exchange circuits (F6): a weekly round (UTC), and 72 hours to accept or decline.
    circuit_round_day: Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"] = "mon"
    circuit_round_hour: int = Field(default=4, ge=0, le=23)
    circuit_consent_hours: int = 72

    # LLM onboarding (F1). Without a key the app falls back to manual pickers.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"
    anthropic_timeout_s: float = 20.0

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
        if (
            self.env == "production"
            and self.demo_auth
            and (self.demo_jwt_secret == DEV_DEMO_SECRET or len(self.demo_jwt_secret) < 32)
        ):
            raise ValueError("Set a random DEMO_JWT_SECRET of at least 32 characters.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
