"""The only way an adapter reaches the network.

Four things every outbound request gets, none of them optional:

* **A host it cannot leave.** The client is constructed for one host and rejects any URL that
  resolves elsewhere, including via a redirect. The NFR is "allowlisted hosts only — the
  scraper cannot be steered to arbitrary URLs", and a source that can return a `next` link is
  a source that can point it at somebody's internal network.
* **An honest identity.** `User-Agent: elestral-vault-harvester/1.0 (+contact@example.com)`.
  We are identifiable to every site we read, which is the difference between a bot someone can
  ask to slow down and a bot someone has to block.
* **A rate limit.** Per source, from config.
* **Backoff that listens.** `Retry-After` is obeyed when the server sends one. Retrying a 429
  on our own schedule is arguing with the answer.

`follow_redirects=False` on purpose. A redirect off-host is exactly the case the allowlist
exists for, and following it silently would launder the request through a check that already
passed.
"""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import httpx

from .rate_limit import TokenBucket

#: Retried. Everything else — 400, 401, 403, 404 — is an answer, not a hiccup, and retrying it
#: just spends someone else's capacity on a request that will fail again.
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})

#: A decision rather than a failure. Raised as `SourceRefused` so FR-18's block counter sees it.
#: 451 is in here because "unavailable for legal reasons" is about as clear a refusal as exists.
REFUSAL_STATUS = frozenset({401, 403, 451})


class SourceUnavailable(RuntimeError):
    """The source could not be read after retries. Fails one source, never the whole run."""


class SourceRefused(SourceUnavailable):
    """The source is refusing us, rather than failing.

    A 503 is an outage; a 403, an exhausted 429 or a challenge page is a *decision*. FR-18 counts
    these and quarantines the source once they are sustained, because retrying into a block is
    how a temporary block becomes a permanent one. Under ADR-004 this is an expected operating
    condition, not an incident.
    """


class OffHostRequest(RuntimeError):
    """An adapter tried to leave its declared host. A bug, or an attempt to steer us."""


def build_user_agent(contact: str) -> str:
    return f"elestral-vault-harvester/1.0 (+{contact})"


class PoliteClient:
    """One per source per run. Not shared: the rate limit is per source."""

    def __init__(
        self,
        *,
        host: str,
        user_agent: str,
        bucket: TokenBucket,
        timeout: float = 20.0,
        max_retries: int = 3,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        scheme: str = "https",
        expect: str = "json",
    ) -> None:
        self._host = host
        self._scheme = scheme
        #: "json" or "text". A connector reading HTML sets "text"; the difference matters
        #: because a JSON connector receiving HTML has almost certainly been served a challenge
        #: page, and `_decode` turns that into a refusal rather than an empty result.
        self._expect = expect
        self._user_agent = user_agent
        self._bucket = bucket
        self._max_retries = max_retries
        self._sleep = sleep
        self._client = client or httpx.Client(timeout=timeout, follow_redirects=False)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PoliteClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        not_found_ok: bool = False,
    ) -> dict[str, Any] | None:
        """`not_found_ok` turns a 404 into `None` instead of an error.

        The light scan needs it: "this listing is gone" is the answer it went looking for, and
        an ended listing is the single most common 404 this codebase will ever see.
        """
        return self._request(
            "GET", path, params=params, headers=headers, not_found_ok=not_found_ok
        )

    def get_text(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        not_found_ok: bool = False,
    ) -> str | None:
        """The HTML path. Same pacing, same allowlist, same refusal handling."""
        payload = self._request(
            "GET", path, params=params, headers=headers, not_found_ok=not_found_ok
        )
        return None if payload is None else payload.get("text")

    def post_json(
        self,
        path: str,
        *,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        # Never `None`: `not_found_ok` is a read-path concession and is not offered here.
        return self._request("POST", path, data=data, headers=headers) or {}

    def _url(self, path: str) -> str:
        """Absolute paths only, and an absolute URL must already be on our host."""
        if path.startswith("http://") or path.startswith("https://"):
            parsed = urlparse(path)
            if parsed.hostname != self._host:
                raise OffHostRequest(
                    f"Refusing {parsed.hostname!r}: this client is bound to {self._host!r}."
                )
            return path
        return f"{self._scheme}://{self._host}{path if path.startswith('/') else '/' + path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        not_found_ok: bool = False,
    ) -> dict[str, Any] | None:
        url = self._url(path)
        # Identity is stamped per request, not on the client, and last so a caller cannot
        # override it. Setting it as a client default instead would lose it entirely whenever
        # an httpx client is injected — which is every test, and any future custom wiring.
        merged = {
            "Accept": (
                "application/json" if self._expect == "json"
                else "text/html,application/xhtml+xml"
            ),
            **(headers or {}),
            "User-Agent": self._user_agent,
        }
        last_error = ""

        for attempt in range(self._max_retries + 1):
            self._bucket.acquire()
            try:
                response = self._client.request(
                    method, url, params=params, data=data, headers=merged
                )
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt == self._max_retries:
                    break
                self._sleep(self._backoff(attempt, None))
                continue

            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}"
                if attempt == self._max_retries:
                    break
                self._sleep(self._backoff(attempt, response.headers.get("Retry-After")))
                continue

            if response.is_redirect:
                # See the module docstring: a redirect is the allowlist's whole point.
                raise OffHostRequest(
                    f"{url} redirected to {response.headers.get('Location')!r}; redirects are "
                    "not followed because the destination has not been cleared."
                )

            if response.status_code == 404 and not_found_ok:
                return None

            if response.status_code in REFUSAL_STATUS:
                # Not retried: this is an answer. Escalated as a refusal so FR-18's counter sees
                # it and the source can be quarantined before we make things worse.
                raise SourceRefused(
                    f"{method} {url} → HTTP {response.status_code}: the source is refusing us"
                )

            if response.status_code >= 400:
                raise SourceUnavailable(
                    f"{method} {url} → HTTP {response.status_code}. Body: "
                    f"{response.text[:200]!r}"
                )

            return self._decode(response, url)

        # An exhausted 429 is a refusal, not an outage — the source told us to stop and we ran
        # out of patience rather than out of luck.
        error = SourceRefused if last_error == "HTTP 429" else SourceUnavailable
        raise error(
            f"{method} {url} failed after {self._max_retries + 1} attempts. Last: {last_error}"
        )

    def _decode(self, response: httpx.Response, url: str) -> dict[str, Any] | None:
        if self._expect == "text":
            return {"text": response.text}
        try:
            return response.json()
        except ValueError:
            # A 200 that is not the JSON we asked for is the shape a challenge or interstitial
            # page takes. Treating it as an empty result would report a block as a quiet market.
            raise SourceRefused(
                f"{url} returned HTTP 200 that is not JSON — a challenge or interstitial page is "
                f"the usual cause. First bytes: {response.text[:120]!r}"
            ) from None

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> float:
        """Exponential with jitter, unless the server named a delay — then use theirs."""
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass  # HTTP-date form; fall through to our own schedule
        # Jitter matters once more than one source runs on the same schedule: without it they
        # retry in lockstep and re-create the burst that caused the 429.
        return (2.0**attempt) + random.uniform(0, 0.5)
