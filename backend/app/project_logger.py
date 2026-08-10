"""Low-level forwarder into the platform's centralized logging (logs-api), via the M2M admin
SDK (`client.logs.write`).

Kept as its own module — the app-starter pattern — so the transport concern stays separate
from the routing decision. **Nothing calls this directly except
`services/logging_service.log_event()`**; call sites use `log_event`, which decides whether an
entry is forwarded at all.

Best-effort by contract: a logging hiccup must never break the request it describes, so every
failure is swallowed.
"""
from __future__ import annotations

from typing import Any

from .admin import get_admin
from .config import settings


def forward_to_platform(event: dict[str, Any]) -> bool:
    """Ship one already-redacted event to logs-api. Returns True if accepted."""
    if not settings.enable_project_logging:
        return False
    try:
        get_admin().logs.write([event])
        return True
    except Exception:
        return False
