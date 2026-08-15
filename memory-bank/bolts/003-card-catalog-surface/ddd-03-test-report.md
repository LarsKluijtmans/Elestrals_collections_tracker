---
unit: 002-card-catalog
bolt: 003-card-catalog-surface
stage: test
status: partial
updated: 2026-08-10T17:00:00Z
---

# Test Report - Card Catalog Surface

## Automated

```
backend/.venv → pytest              119 passed in 1.26s   (46 new in this bolt)
frontend      → vitest run           12 passed in 9.95s   (new: the keyboard contract)
frontend      → npm run typecheck    clean
frontend      → npm run build        ✓ 5,065 modules, 971 kB (306 kB gzip)
```

| Suite | Count | Covers |
|---|---|---|
| `test_card_search.py` | 16 | all six tiers, total order, filters, wildcard escaping, paging, primary printing |
| `test_catalog_api.py` | 13 | the public surface signed out, cache headers, 404 codes, filter algebra |
| `test_catalog_health.py` | 9 | staleness classification, never-run, coverage shortfall, rejection rollup |
| `test_rarity_and_alt_text.py` | 8 | rarity order, primary-printing fallback and determinism, alt-text shape |
| `CardSearchBox.test.tsx` | 12 | the keyboard contract bolt 005 consumes |

### Coverage

| Scope | Coverage |
|---|---|
| Bolt-003 backend modules | **97%** |
| Whole `app/` | 84% |

## What the tests are actually pinning

**The total order, because the failure it prevents is silent.** Bolt 005 navigates results with
arrows and commits with `Enter`. If ordering wobbled between renders, the row under the cursor
could change between render and keypress and a collector would add the wrong printing with no
error anywhere. `test_order_is_stable_across_identical_queries` asserts it server-side;
`clamps at the ends instead of wrapping` asserts the client half, because a silent wrap from the
last row back to the first is the same bug wearing a different hat.

**That the public surface is genuinely public.** `test_catalog_api.py` contains no
`verify_token` override at all. If any of those routes ever gains an authenticated dependency,
every test in that file starts failing with a 401 rather than the route quietly becoming
user-specific behind a five-minute shared cache. `test_set_summary_has_no_user_specific_field`
guards the same rule from the other direction.

**That wildcards are literal.** `test_wildcards_in_a_term_are_literal` searches for `%%` and
expects nothing. Without the escaping in `escape_like`, that query returns the entire catalog.

**That `never_run` is a state, not a null.** A source that has never imported is exactly the one
an operator needs to see, and it has no rows to be found by — so `CatalogHealthService` iterates
the source *registry*, not the run table. `test_registered_source_with_no_runs_still_appears`
pins that.

## Deviations from the design, recorded

1. **`Gate` was restructured, and `AppShell` with it.** The design said the three public pages
   must work signed out; the existing gate rendered the login form over the *whole*
   application, so no anonymous visitor could have reached `/sets` at all. Login is now scoped
   to the routes that need a session (`RequireAuth`), and the rail hides authenticated
   destinations from anonymous visitors rather than inviting them into a sign-in wall. This is
   a change to bolt 001's components, made because the criterion could not otherwise be met.
2. **TanStack Query was added.** `tech-stack.md` mandates it for server state and the approved
   design specified it, but bolt 001 never installed it. Now a dependency, with the client
   configured in `App.tsx`.
3. **A frontend test runner was added** — vitest + Testing Library + happy-dom. The bolt's
   keyboard criterion is not assertable without one, and it is the contract bolt 005 depends
   on.
4. **happy-dom rather than jsdom.** jsdom's CSS colour chain (`cssstyle` →
   `@asamuzakjp/css-color`) `require()`s an ESM-only module and throws `ERR_REQUIRE_ESM` before
   any test runs, under both the `forks` and `threads` pools.
5. **`/admin/catalog/health` returns the rollup for the newest run across all sources**, rather
   than per-source rejection lists. Story 034 asks whether the catalog is healthy; per-source
   rejection history is a drill-down that belongs with the run detail endpoint, which already
   has it.


## Verified against real MySQL — 2026-08-11

The platform stack was already running (`../auth/docker-compose.yml`, 19 containers). Migrations
`0001`–`0003` applied to MySQL 8.4 cleanly, and `backend/scripts/verify_mysql.py` passed **24/24**
checks against it, `backend/scripts/bench.py` **5/5** NFR budgets. Both are re-runnable and clean
up after themselves.

What that closes for this bolt is listed below; anything still open stays listed as open.

| Was open | Now |
|---|---|
| `3-char prefix < 150ms p95` | ✅ **26.9ms p95** at 5,000 cards — 5.6× inside budget |
| `CASE` tiering and `coalesce` ordering under MySQL | ✅ exact-name ranks first, order stable across identical queries |
| Public pages serving anonymously | ✅ `GET /sets` and `/cards` return 200 with no `Authorization` header, `Cache-Control: public`, no `Vary` |

That measurement is also what ADR-002 was accepted without; it is now recorded there.

## Previously not met

**`3-character prefix returns ranked results in < 150ms p95` is NOT verified.** It cannot be:
the target is "with the full catalog loaded", the catalog has no cards (bolt 002's FE01 seed
ships empty by design), and no MySQL instance has ever run. Ranking *correctness* is fully
tested on SQLite; the latency number is unmeasured.

ADR-002 accepted a scan-and-rank design on the strength of a ~5,000-card estimate. That estimate
is from `unit-brief.md`, not from a measurement, and the ADR records the revisit trigger
(p95 > 100ms, or 100k cards) precisely so this stays a measurement rather than a belief.

## Not verified — needs a database, a browser, or both

| Criterion | Why |
|---|---|
| Search latency p95 | No MySQL, no catalog data |
| `CASE` tiering and `coalesce` ordering under MySQL | Verified on SQLite; MySQL's collation and NULL ordering differ |
| The three public pages rendering | Compiled, type-checked and unit-tested; never rendered in a browser |
| WCAG 2.2 AA in full | Alt text, `aria-activedescendant`, `role=option/listbox` and element names are asserted. Contrast ratios, focus visibility and a full axe pass are not |
| Completion rings with real data | They render their null state only — bolt 004 supplies the numbers |

## Story coverage

| Story | State |
|---|---|
| `010-card-search` | Complete bar the latency measurement |
| `011-set-browser` | Complete; rings render the null state as designed |
| `012-card-detail` | Complete |
| `034-admin-catalog-console` | Complete |
