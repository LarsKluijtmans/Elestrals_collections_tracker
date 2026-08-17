# Deploying Elestral Vault

**Six containers**, running on the platform's Docker network and published through a Cloudflare
tunnel:

| Container | Is |
|---|---|
| `elestrals-web` | nginx + the built SPA. Also the only thing published — it proxies to both backends |
| `elestrals-api` | the collection backend. Owns `elestrals` |
| `harvest-api` | the scraper backend. Owns `elestrals_harvest`, connects as its **own** MySQL user |
| `harvest-worker` | Celery. Runs the scans, which are hours long and do not belong in a request |
| `harvest-beat` | the schedule: light scans, deep scans, rollup, sweeper, quarantine probe, FX |
| `harvest-redis` | broker and result backend only. Nothing here is a source of truth |

## Topology: one public hostname

The SPA is served at `elestrals.larskluijtmans.com` and calls its API at `/api/*` on **that same
origin**; nginx proxies those to `elestrals-api:9000`. The browser therefore makes no
cross-origin request to our backend and needs no CORS.

**The admin console reaches the second backend at `/harvest/*` on the same origin**, which nginx
proxies to `harvest-api:9100` with the prefix stripped. Same hostname, different path — and
deliberately *not* routed through `elestrals-api`, because proxying one backend through the other
would make the collection backend a dependency of the admin console and undo half of FR-13.

The trailing slash on that `proxy_pass` is load-bearing: without it nginx forwards `/harvest/`
too and every harvest route 404s.

The sibling Ligretto deployment started split-origin, with a separate `ligrettoapi.` hostname,
and moved off it because that hostname's DNS proved unreliable. This is set up the way that one
ended up. A second hostname for the API still works if you want it — `CORS_ORIGINS` already
lists the web origin — but nothing requires it.

The one cross-origin call the browser does make is PKCE login against the platform's login-api,
which is why `connect-src` in the nginx CSP names `https://auth.aangifteportal.nl`. Change that
host and you must change the CSP with it, or `react-auth` reports "unable to reach the
authentication service".

## Prerequisites

**The platform stack must be up** — it owns the `platform_default` network and the MySQL server:

```bash
cd ../auth && docker compose up -d
```

**The database and a scoped user** (once):

```sql
CREATE DATABASE elestrals CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'elestrals_app'@'%' IDENTIFIED BY '<password>';
GRANT ALL PRIVILEGES ON elestrals.* TO 'elestrals_app'@'%';
```

The app never uses the platform's own `app` or root credentials.

**The harvest schema and its own user** (intent 002, once):

`harvest-api` is a second backend and connects as a **different MySQL user**. The split is not
cosmetic — it is the isolation FR-13 is built on, and it is enforced by privilege rather than by
convention, so a blocked, broken or rewritten scraper cannot reach the data the collection tracker
serves. `harvest/tests/test_grants_mysql.py` asserts every line of this by attempting each
forbidden read and write; run it against the real database before the first release.

```sql
CREATE DATABASE elestrals_harvest CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'elestrals_harvest'@'%' IDENTIFIED BY '<password>';

-- The harvester owns its own schema outright.
GRANT ALL PRIVILEGES ON elestrals_harvest.* TO 'elestrals_harvest'@'%';

-- ...and reads exactly four catalog tables, because the matcher has to resolve titles against
-- real printings. TABLE-level, not `elestrals.*`: a schema-wide grant would hand the harvester
-- every user's inventory the moment somebody adds a table.
GRANT SELECT ON elestrals.sets            TO 'elestrals_harvest'@'%';
GRANT SELECT ON elestrals.cards           TO 'elestrals_harvest'@'%';
GRANT SELECT ON elestrals.printings       TO 'elestrals_harvest'@'%';
GRANT SELECT ON elestrals.sealed_products TO 'elestrals_harvest'@'%';

FLUSH PRIVILEGES;
```

**The other direction is ONE table, and it has to wait.** `price_daily` is the entire contract
between the services — listings, runs, match notes and rejected rows stay admin-only on the
harvester's side. But the table does not exist until the harvest migration creates it, so this grant
runs **after** `alembic upgrade head` on `harvest-api`, not with the block above:

```sql
GRANT SELECT ON elestrals_harvest.price_daily TO 'elestrals_app'@'%';
FLUSH PRIVILEGES;
```

Running it early fails with `ERROR 1146: Table 'elestrals_harvest.price_daily' doesn't exist`. Found
the hard way on the first real deploy, 2026-08-17.

Deliberately **not** granted, and worth stating so nobody adds them for convenience:
`elestrals_harvest` gets no write on anything in `elestrals`, and no read at all on
`inventory_items` or `user_profiles` — the harvester has no business knowing who owns what.
`elestrals_app` gets no write on `price_daily` and no read on anything else of the harvester's.

Then, once per deployment:

```bash
docker compose exec harvest-api alembic upgrade head
```

Two Alembic trees, two version tables. Neither service migrates the other's schema, and neither
release job runs the other's migrations.

**Two platform clients**, which are not interchangeable:

| | Grant types | Redirect URIs | Origins | Secret lives in |
|---|---|---|---|---|
| **Elestral Vault backend** (M2M) | `client_credentials` | **none** | **none** | `.env`, server-side only |
| **Elestral Vault web** (public) | `authorization_code`, `refresh_token` | `https://elestrals.larskluijtmans.com/`, `http://localhost:5173/` | `https://elestrals.larskluijtmans.com`, `http://localhost:5173` | **nowhere** — PKCE needs none |

An M2M client has no redirect URI: `client_credentials` never redirects. Register the redirect
URIs with the **trailing slash**, because that is exactly what the app sends
(`${window.location.origin}/`).

The M2M client also needs a **service-account RBAC role** granting all seven scopes:
`users:read`, `logs:write`, `usage:write`, `notifications:send`, `notifications:configure`,
`storage:read`, `storage:write`. Without it the client still mints tokens — they just carry
`openid` and nothing else, and every platform call 403s into a deliberately swallowed exception.
The startup check exists to catch precisely that and names what is missing.

## Deploy

The frontend bundle is built **on the host**, because `@lars-kluijtmans/react-auth` and
`react-login` are not published to npm and resolve from the sibling `../auth` checkout:

```bash
powershell -ExecutionPolicy Bypass -File scripts\use-local-sdks.ps1
cd frontend && npm run build && cd ..

cp .env.example .env          # DATABASE_URL, HARVEST_DATABASE_URL + M2M credentials
docker compose up -d --build
```

Schema — **two trees, and the order matters** because of the `price_daily` grant above:

```bash
docker compose exec elestrals-api alembic upgrade head
docker compose exec harvest-api   alembic upgrade head
# ...then the deferred GRANT, now that elestrals_harvest.price_daily exists.
```

Register the scrapers. They arrive **disabled with no terms-review note**, which is ADR-004
working rather than something to fix:

```bash
docker compose exec harvest-api python -m app.harvest --sync-sources
docker compose exec harvest-api python -m app.harvest --list
```

Verify:

```bash
curl http://127.0.0.1:9530/api/v1/health          # elestrals-api, through nginx
curl http://127.0.0.1:9530/harvest/api/v1/health  # harvest-api, through nginx
docker compose ps                                 # all six
```

`harvest-beat` reports **no health status at all**, and that is deliberate. The image's
`HEALTHCHECK` curls `:9100`, which only `harvest-api` serves — three roles share one image on
purpose (one build, one tag, one thing to be sure of), but that means two of them inherit a probe
they can never pass. `harvest-worker` overrides it with `celery inspect ping`, which asks a worker
the right question; beat has neither a port nor a broker connection to interrogate, so its check is
disabled and `restart: unless-stopped` covers the only failure mode it has.

A permanently red light is worse than no light — it is the one that gets ignored on the day it
means something.

The harvest health check reports `database`, `redis` **and** `conduct` — whether it obeys
`robots.txt` and whether it identifies itself. That last one is ADR-004's posture surfaced as an
operational fact rather than left in a document.

Then prove the boundary, which is the one thing SQLite cannot test:

```bash
HARVEST_TEST_MYSQL_URL=mysql+pymysql://elestrals_harvest:...@127.0.0.1:9306/elestrals_harvest \nELESTRALS_TEST_MYSQL_URL=mysql+pymysql://elestrals_app:...@127.0.0.1:9306/elestrals \n  pytest harvest/tests/test_grants_mysql.py -m mysql
```

16 tests, each attempting a read or write that must be refused. **Point them at the two narrowly
granted users, never at root** — root passes every one of them while proving nothing.

## The nightly snapshot — set this up on day one

`elestrals-api` has exactly one scheduled job, and it is the one thing in phase 1 whose value
depends on having run *in the past*:

```bash
docker compose exec elestrals-api python -m app.jobs --snapshot
```

It writes one `collection_snapshots` row per user per day: how many cards they hold and how many
distinct printings. **Nothing in phase 1 reads it.** Phase 2's portfolio chart does, and the counts
for 3 March exist only if something wrote them on 3 March — so a night missed is a permanent hole in
somebody's history. `--on YYYY-MM-DD` fills a gap, but only with the *current* collection, which
makes it a repair tool rather than a way to reconstruct the past.

Add it to `cron` on the host, shortly after midnight UTC:

```
15 0 * * *  cd /path/to/elestrals && docker compose exec -T elestrals-api python -m app.jobs --snapshot
```

Safe to run twice — `uq_collection_snapshot_user_day` makes a second run an update, and the update
deliberately leaves `total_value_cents` alone so re-running cannot blank a day phase 2 has valued.
There is no Celery here on purpose: one job that finishes in seconds does not justify a broker.

The same entrypoint carries the projection repair tool, if `set_completion` is ever wrong:

```bash
docker compose exec elestrals-api python -m app.jobs --rebuild-completion <user_sub>
```

## Running the harvester by hand

The scrapers run on a beat schedule, but every step of the pipeline can be driven manually — which
is how you check whether a source still parses, or see the effect of a change without waiting for
the interval.

**From the admin console** (`/admin/harvest`, needs `elestrals:admin`):

| Control | Does |
|---|---|
| Run light scan / Run deep scan | queues a scan for that source; the run row appears immediately and its counters poll live |
| Stop | sets a flag the scan checks between queries, so it stops at a clean boundary and closes its own run row |
| **Recompute prices** | rebuilds `price_daily` for the chosen window, synchronously, and reports what it published |
| **Sweep stale runs** | fails runs orphaned by a deploy, so a stuck `running` row stops refusing a new scan |

The console needs `harvest-worker` and `harvest-redis` up: the trigger queues the work rather than
running it in the request. If the broker is down the trigger answers `503` and closes the run row
rather than leaving a phantom `running` behind. `Recompute prices` and `Sweep stale runs` are
synchronous and need neither.

**From the CLI**, which runs the scan **in-process** and therefore needs no worker and no Redis —
this is the one to reach for when the queue itself is what you are debugging:

```bash
docker compose exec harvest-api python -m app.harvest --list
docker compose exec harvest-api python -m app.harvest --source ebay_sold --mode light
docker compose exec harvest-api python -m app.harvest --source ebay_sold --mode deep
docker compose exec harvest-api python -m app.harvest --rollup    # full rebuild, no window cap
docker compose exec harvest-api python -m app.harvest --sweep
```

`--enable` requires both `--note` and `--accepted-by`, and there is no flag to skip either — that is
ADR-004 rather than ceremony. A risk accepted by nobody in particular, on the basis of a review
nobody wrote, is not an accepted risk.

Two things worth knowing:

- **A scan alone changes nothing a collector sees.** It writes `price_observations`; `/prices`,
  `/portfolio` and the card price tab all read `price_daily`. Recompute after scanning, or wait for
  the beat.
- **The rollup is a projection, so re-running it is always safe** and always the fix for a wrong
  number. The console's window is capped at 90 days because a synchronous full-history rebuild
  inside an HTTP request is a timeout waiting to happen; `--rollup` on the CLI has no cap.

## Publishing hostnames

In Cloudflare Zero Trust → your tunnel → Public Hostnames:

```
elestrals.larskluijtmans.com      ->  http://elestrals-web:80
elestrals-api.larskluijtmans.com  ->  http://elestrals-api:9000    (optional)
```

Cloudflared reaches those by **compose service name on the internal port**, not via a published
host port. Two options:

- **Add them to the platform's tunnel.** The co-locate override already puts both containers on
  `platform_default`, so its connector can see them. Nothing else to run.
- **Run our own connector**: put `TUNNEL_TOKEN` in `.env` and
  `docker compose --profile tunnel up -d`.

Note the platform's own zone is `aangifteportal.nl`; `larskluijtmans.com` is a different zone.
A single tunnel can route both as long as they are in the same Cloudflare account.

## Images and releases

`.github/workflows/publish-images.yml` mirrors the platform's, pushing to ghcr.io on a `vX.Y.Z`
tag or manual dispatch:

```
ghcr.io/<owner>/elestrals-api
ghcr.io/<owner>/elestrals-web
```

```bash
git tag v0.1.0 && git push origin v0.1.0
```

### The one prerequisite for CI

**Neither app installs from a clean checkout.** `lars-kluijtmans-admin-sdk==0.2.0` is not on
PyPI and `@lars-kluijtmans/react-auth@^0.2.0` is not on npm — both 404. The platform has publish
workflows for both, but they are `workflow_dispatch`-only and have not been run for 0.2.0.

Until they are, CI checks the `auth` repository out and vendors the SDKs from source — the same
shape as the platform vendoring its in-repo `libtenancy`/`libservice`, except ours lives in
another repo. That needs one repository secret:

- **`AUTH_REPO_TOKEN`** — a PAT with `repo` scope, if `LarsKluijtmans/auth` is private. Omit it
  and the built-in token is used, which only works if that repo is public.

Optional repository *variables* for the web image build: `VITE_LOGIN_CLIENT_ID`,
`VITE_REDIRECT_URI`, `VITE_LOGIN_API_URL`, `VITE_BACKEND_URL` (leave the last empty for
same-origin).

Once both SDKs are published, delete the bootstrap steps from both workflows and the
`adminsdk` build context from `backend/Dockerfile` — the ordinary installs will resolve.

## Ports

The platform publishes its services on `9xxx` **host** ports while they listen on `8xxx`
**inside** their containers. From inside `platform_default` you use the container port; from the
host you use the published one.

| | Container | Host |
|---|---|---|
| MySQL | 3306 | 9306 |
| login-api | 8010 | 9010 |
| auth-api | 8050 | 9050 |
| logs-api | 8030 | 9030 |
| branding-api | 8080 | 9120 |
| our API | 9000 | 9520 (debug only) |
| our web | 80 | 9530 (debug only) |

`:9000` on the host is `platform-management-api`, so a locally-run backend uses `:9500`.
