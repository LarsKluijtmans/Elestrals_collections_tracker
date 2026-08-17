"""Price harvesting — the two scans that keep `market_listings` and `price_observations` true.

    python -m app.harvest --list
    python -m app.harvest --source ebay_browse --mode deep
    python -m app.harvest --source ebay_browse --mode light

Read `gate.py` before adding a source, and `models/market_listing.py` before assuming a
disappeared listing was a sale. Neither is a formality: one is the requirement that decides
whether a source may run at all, the other is the difference between a price history and a
plausible-looking fiction.
"""
