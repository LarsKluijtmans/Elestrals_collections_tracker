"""Backend configuration. Everything comes from the environment (a `.env` file in dev) — no
secrets or URLs are hard-coded. See `.env.example`."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "elestral-vault"
    environment: str = "local"  # local | staging | production

    # --- Our own database --------------------------------------------------------
    # The platform's MySQL instance, our own `elestrals` schema. We never touch
    # `platform`, `auth_{company}` or `tenant_{company}`.
    database_url: str = "mysql+pymysql://root:root@127.0.0.1:3306/elestrals?charset=utf8mb4"
    db_echo: bool = False

    # --- Platform service URLs (point these at your deployment) ------------------
    login_api_url: str = "http://127.0.0.1:8010"
    auth_api_url: str = "http://127.0.0.1:8050"
    logs_api_url: str = "http://127.0.0.1:8030"
    notifications_api_url: str = "http://127.0.0.1:8020"
    storage_api_url: str = "http://127.0.0.1:8070"

    # The `iss` the Login API stamps on tokens — MUST equal its TOKEN_ISSUER. We pin
    # `iss` during verification, so a mismatch here rejects every token.
    token_issuer: str = "http://127.0.0.1:8010"

    # --- M2M service account (server-side ONLY — never shipped to the browser) ---
    m2m_client_id: str = ""
    m2m_client_secret: str = ""

    # --- Behaviour toggles ------------------------------------------------------
    enable_enrichment: bool = True          # call auth-api to enrich the profile
    enable_project_logging: bool = True     # forward error/security entries to logs-api
    enable_usage_metering: bool = True      # record feature usage to logs-api
    log_category: str = "elestrals"         # default category stamped on log events
    jwks_cache_seconds: int = 300

    # Bound the in-memory forward buffer so a long logs-api outage cannot grow without end.
    log_forward_buffer_max: int = 1000

    # --- Operator access to /api/v1/admin/* -------------------------------------
    # The platform has no app-level role for us yet, so operator status is asserted from
    # the token's `scope` claim, with a dev-only allowlist of subjects as the escape hatch.
    # Provisional: replace with platform RBAC once it exposes an app role. A non-operator
    # gets 403 either way — never a filtered-down 200.
    operator_scope: str = "elestrals:operator"
    operator_subs: str = ""  # comma-separated JWT subs, for local development

    # Comma-separated browser origins allowed to call this API (CORS).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def operator_subs_list(self) -> list[str]:
        return [s.strip() for s in self.operator_subs.split(",") if s.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
