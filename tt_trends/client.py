"""Minimal client for the (anonymous) TikTok Creative Center hashtag API."""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request

from . import config


class ApiError(RuntimeError):
    pass


def fetch_hashtags(
    country: str,
    period: int,
    industry_id: int | None = None,
    *,
    retries: int = 4,
    timeout: float = 20.0,
) -> list[dict]:
    """Return the raw hashtag items for one country/period/industry combination."""
    body: dict = {
        "timeRange": period,
        "countryCode": country,
        "page": 1,
        "limit": config.PAGE_LIMIT,
    }
    if industry_id is not None:
        body["industryID"] = industry_id

    payload = json.dumps(body).encode()
    last_error: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(
            config.API_URL,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": config.USER_AGENT,
                "Origin": "https://ads.tiktok.com",
                "Referer": f"{config.REFERER}?region={country}&period={period}",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            base = data.get("BaseResp") or {}
            if base.get("StatusCode", -1) != 0:
                raise ApiError(f"API error: {data}")
            return data.get("items") or []
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ApiError) as exc:
            last_error = exc
            # Exponential backoff with jitter.
            time.sleep((2**attempt) + random.random())
    raise ApiError(
        f"Failed {country}/{period}d/industry={industry_id}: {last_error}"
    ) from last_error
