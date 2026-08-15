"""Configuration for `harvest-api`, the second backend.

Two families of keys, and the split is deliberate:

* **Shared platform keys** keep the names `elestrals-api` uses — `TOKEN_ISSUER`, `LOGIN_API_URL`,
  `LOGS_API_URL`. One `.env` configures both services, and a token issuer that differed between
  them would be a silent authentication bug.
* **Everything this service owns is prefixed `HARVEST_`**, so the two never collide in that
  shared file.

Read `app/harvest/gate.py` before changing anything under "collection conduct". Several of those
are not tuning knobs; they are the difference between the posture ADR-004 chose and a different
one nobody agreed to.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "elestral-vault-harvest"
    environment: str = "local"  # local | staging | production

    # --- Our own schema ----------------------------------------------------------
    # `elestrals_harvest`, reached as a user holding NO write grant on `elestrals`. The
    # boundary is a database privilege, not a convention — see story 002 and the negative
    # tests in `tests/test_grants_mysql.py`.
    harvest_database_url: str = (
        "mysql+pymysql://elestrals_harvest:harvest@127.0.0.1:3306/elestrals_harvest"
        "?charset=utf8mb4"
    )
    db_echo: bool = False

    #: The phase-1 schema, read-only, for the catalog the matcher resolves titles against.
    #: Blank on the SQLite unit-test path, where everything is one unqualified database.
    catalog_schema: str = "elestrals"

    # --- Platform (shared names with elestrals-api) ------------------------------
    token_issuer: str = "http://127.0.0.1:8010"
    login_api_url: str = "http://127.0.0.1:8010"
    logs_api_url: str = "http://127.0.0.1:8030"
    jwks_cache_seconds: int = 300
    log_category: str = "elestrals"
    enable_project_logging: bool = False

    # --- Admin access -------------------------------------------------------------
    # Every `/api/v1/admin/*` route on this service requires this scope. Distinct from
    # phase 1's `elestrals:operator` on purpose: the person who can re-import the catalog
    # is not automatically the person who can start a scraper.
    admin_scope: str = "elestrals:admin"
    #: Local development only. Inert when ENVIRONMENT=production, and logged at startup if
    #: set there anyway. A subject allowlist is a convenience, not an authorisation system.
    harvest_admin_subs: str = ""

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Job runtime ---------------------------------------------------------------
    harvest_redis_url: str = "redis://127.0.0.1:6379/0"
    #: Beat cadences, in minutes. Configuration rather than code, because how often to read
    #: someone else's site is an operational decision.
    harvest_light_every_minutes: int = 60
    harvest_deep_every_minutes: int = 10080  # weekly
    harvest_rollup_every_minutes: int = 1440

    # --- Collection conduct (ADR-004) ----------------------------------------------
    #: Stamped into every outbound User-Agent. Empty means no scan starts: ADR-004 gave up
    #: politeness, not identifiability, and an anonymous bot is one that can only be blocked.
    harvest_contact_email: str = ""
    #: The outbound allowlist. A source whose host is not here cannot run, however it is
    #: configured. Shopify shops are merged in, because configuring one is already the
    #: deliberate act this list exists to require.
    harvest_allowed_hosts: str = (
        "www.ebay.com,api.ebay.com,api.sandbox.ebay.com,www.tcgplayer.com"
    )
    #: robots.txt is NOT consulted. ADR-004, recorded in NFR §Conduct. This flag exists so the
    #: decision is visible in configuration rather than only in a document, and so that
    #: turning it back on is one line rather than a re-implementation.
    harvest_obey_robots: bool = False

    harvest_request_timeout_seconds: float = 20.0
    harvest_max_retries: int = 3
    #: A run still `running` after this is swept to `failed` (FR-2). Above the 4-hour deep
    #: budget, so a slow run is not declared dead while it is still working.
    harvest_run_stale_after_minutes: int = 300

    # --- Scan shape ------------------------------------------------------------------
    harvest_deep_max_queries: int = 400
    harvest_deep_results_per_query: int = 100
    harvest_light_max_listings: int = 500
    harvest_light_recheck_after_hours: float = 12
    harvest_light_similar_queries: int = 25
    harvest_light_results_per_query: int = 20

    #: Below this the matcher's answer is a guess: no observation is written, and the listing
    #: is kept as a lead instead (FR-3).
    harvest_match_confidence_floor: float = 0.70

    # --- Block survival (FR-18) --------------------------------------------------------
    #: Refusals within one run before the source is quarantined. Not 1: a single 429 is
    #: ordinary traffic shaping and the HTTP layer already backs off for it.
    harvest_block_threshold: int = 5
    harvest_quarantine_minutes: int = 60
    #: Each consecutive quarantine multiplies the previous one, up to the ceiling.
    harvest_quarantine_backoff_factor: float = 4.0
    harvest_quarantine_max_minutes: int = 2880  # 48h

    # --- Rollups ------------------------------------------------------------------------
    #: 3× IQR. Beyond this a point is excluded from median and mean — and flagged, never
    #: deleted, because a silently dropped point is unauditable.
    harvest_outlier_iqr_factor: float = 3.0
    #: Fewer points than this and no exclusion is attempted; an IQR over three points is not
    #: a statistic.
    harvest_outlier_min_points: int = 4
    harvest_base_currency: str = "EUR"

    # --- Sources -------------------------------------------------------------------------
    ebay_marketplace_id: str = "EBAY_US"
    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    ebay_environment: str = "production"
    ebay_category_ids: str = ""  # optional narrowing, e.g. a trading-card category id
    ebay_filter: str = ""        # optional Browse filter expression
    #: The public search host the sold-listings connector reads. Separate from the API host
    #: because they are different sources with different terms and different review notes.
    ebay_web_host: str = "www.ebay.com"
    #: `host:CURRENCY` pairs — one source, one terms review, one kill switch per shop.
    harvest_shopify_shops: str = ""

    @property
    def admin_subs_list(self) -> list[str]:
        if self.is_production:
            return []  # inert in production, whatever the environment says
        return [s.strip() for s in self.harvest_admin_subs.split(",") if s.strip()]

    @property
    def allowed_hosts_list(self) -> list[str]:
        hosts = [h.strip().lower() for h in self.harvest_allowed_hosts.split(",") if h.strip()]
        for entry in self.harvest_shopify_shops.split(","):
            host = entry.split(":", 1)[0].strip().lower()
            if host and host not in hosts:
                hosts.append(host)
        return hosts

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
