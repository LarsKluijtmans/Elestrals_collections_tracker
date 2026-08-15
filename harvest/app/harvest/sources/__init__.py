"""The connector registry.

Same contract as phase 1's importer sources: connectors register here, the runner resolves by
name and never imports a connector module directly, and adding a source is one file plus one
config row.

One difference, and it is deliberate. This registry holds **factories, not instances**. A
connector is stateful for the length of a run — it holds a `PoliteClient` carrying that source's
rate-limit bucket and, for eBay's API, an OAuth token with an expiry. Sharing one instance across
concurrent runs would share the bucket, which is the one thing a rate limiter must not do.

`describe_source()` exists so `--list` and the admin console can show what is registered without
constructing credentials for sources nobody is about to run.

## What ships

| Connector | Mode | Reports sales | Why it is here |
|---|---|---|---|
| `ebay_sold` | scrape | **yes** | The reason ADR-004 was taken: real sale prices and dates |
| `ebay_browse` | official_api | no | Free, published, no approval queue. Asking prices, which are worth having labelled as such |
| `shopify_*` | official_api | no | Retail prices from hobby shops, one source per shop |

The licensed aggregator from ADR-003 is **not** here. It was declined on cost, and its adapter
was deleted rather than left inert — a connector nobody may use is a maintenance burden pretending
to be an option.
"""
from __future__ import annotations

from collections.abc import Callable

from ..canonical import HarvestDescriptor, HarvestSource

SourceFactory = Callable[[], HarvestSource]

SOURCES: dict[str, SourceFactory] = {}


class UnknownSource(LookupError):
    pass


class SourceNotConfigured(RuntimeError):
    """Registered, but missing the credentials or the wiring it needs to run."""


def register(name: str, factory: SourceFactory) -> None:
    SOURCES[name] = factory


def new_source(name: str) -> HarvestSource:
    try:
        factory = SOURCES[name]
    except KeyError:
        raise UnknownSource(
            f"Unknown source {name!r}. Registered: {', '.join(sorted(SOURCES)) or '(none)'}"
        ) from None
    return factory()


def describe_source(name: str) -> HarvestDescriptor:
    return new_source(name).describe()


def available_sources() -> list[str]:
    return sorted(SOURCES)


# The one place connector modules are imported.
from .ebay_browse import EbayBrowseAdapter  # noqa: E402
from .ebay_sold import EbaySoldAdapter  # noqa: E402
from .shopify_storefront import ShopifyStorefrontAdapter, configured_shops  # noqa: E402

register(EbaySoldAdapter.name, EbaySoldAdapter)
register(EbayBrowseAdapter.name, EbayBrowseAdapter)

# One registered source per configured shop, because one shop is one set of terms. Bundling them
# behind a single `shopify` source would mean a single review note covering sites with different
# terms, which is the FR-1 gate defeated by tidiness.
for _shop in configured_shops():
    register(
        ShopifyStorefrontAdapter.name_for(_shop),
        lambda shop=_shop: ShopifyStorefrontAdapter(shop),
    )
