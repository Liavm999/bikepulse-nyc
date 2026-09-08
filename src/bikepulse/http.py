"""Small resilient JSON client built on the standard library."""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)


class SourceRequestError(RuntimeError):
    """Raised after a source request exhausts its retry budget."""


def get_json(url: str, *, timeout: float, max_attempts: int) -> dict[str, Any]:
    """Fetch and decode JSON, retrying transient network and server errors."""
    request = Request(url, headers={"User-Agent": "bikepulse-nyc/0.1 (+portfolio project)"})
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed configured URLs
                if response.status >= 500:
                    raise HTTPError(url, response.status, "server error", response.headers, None)
                payload = json.load(response)
                if not isinstance(payload, dict):
                    raise ValueError("expected a JSON object")
                return payload
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
            last_error = error
            retryable = not isinstance(error, HTTPError) or error.code in {408, 429} or error.code >= 500
            if attempt == max_attempts or not retryable:
                break
            delay = min(2 ** (attempt - 1), 8) + random.uniform(0, 0.25)
            LOGGER.warning("request failed; retrying", extra={"url": url, "attempt": attempt})
            time.sleep(delay)

    raise SourceRequestError(f"failed to fetch {url} after {max_attempts} attempts") from last_error

