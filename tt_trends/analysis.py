"""Normalisation, merging and trend analysis of raw Creative Center items."""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from . import config


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def industry_key(industry_id: int | str) -> str:
    """Short industry key, e.g. 14000000000 -> "14"."""
    return str(_int(industry_id) // 1_000_000_000)


def normalize_item(raw: dict) -> dict:
    """Reduce a raw API item to the fields the dashboard needs."""
    curve = [round(float(p.get("value") or 0)) for p in raw.get("popularityCurve") or []]
    creators = [
        {
            "handle": c.get("handleName") or "",
            "followers": _int(c.get("followedCnt")),
        }
        for c in raw.get("topCreators") or []
        if c.get("handleName")
    ]
    return {
        "name": raw.get("hashtagName") or "",
        "views": _int(raw.get("vv")),
        "posts": _int(raw.get("publishCnt")),
        "industries": sorted({industry_key(i) for i in raw.get("industryIDs") or []}, key=int),
        "curve": curve,
        "creators": creators,
    }


def momentum(curve: list[float]) -> tuple[str, int]:
    """Classify the popularity curve (values 0-100, normalised to the period peak).

    Returns (label, score). The score is the difference between the recent and the
    early part of the curve and ranges from -100 (collapsing) to +100 (exploding).
    Labels:
      "rising"  – curve is at/near its maximum right now and clearly growing
      "peak"    – still on a high level (>= 60 % of the period maximum)
      "fading"  – maximum lies in the past and the curve dropped below 60 %
      "steady"  – no usable curve (too short or all zero)
    """
    values = [float(v) for v in curve if v is not None]
    n = len(values)
    peak = max(values, default=0)
    if n < 3 or peak <= 0:
        return "steady", 0

    tail = max(2, n // 4)
    recent = mean(values[-tail:])
    early = mean(values[: max(2, n // 2)])
    score = round((recent - early) / peak * 100)
    peak_idx = max(range(n), key=lambda i: values[i])
    rel_last = values[-1] / peak * 100

    if peak_idx >= n - 2 and rel_last >= 50 and score > 10:
        return "rising", score
    if rel_last >= 60:
        return "peak", score
    return "fading", score


def merge_lists(lists: dict[str, list[dict]]) -> list[dict]:
    """Merge the per-industry top lists of one country/period into a unique list.

    `lists` maps a list key ("all" or an industry key) to raw API items.
    """
    merged: dict[str, dict] = {}
    for list_key, items in lists.items():
        for raw in items:
            item = normalize_item(raw)
            if not item["name"]:
                continue
            rank = _int(raw.get("rankIndex"), 99)
            existing = merged.get(item["name"])
            if existing is None:
                item["ranks"] = {}
                existing = merged[item["name"]] = item
            else:
                # Different lists may report slightly different numbers; keep the max.
                existing["views"] = max(existing["views"], item["views"])
                existing["posts"] = max(existing["posts"], item["posts"])
                existing["industries"] = sorted(
                    set(existing["industries"]) | set(item["industries"]), key=int
                )
            existing["ranks"][list_key] = rank
            if list_key != "all" and list_key not in existing["industries"]:
                existing["industries"] = sorted({*existing["industries"], list_key}, key=int)

    result = list(merged.values())
    for item in result:
        label, score = momentum(item["curve"])
        item["momentum"] = label
        item["momentumScore"] = score
        item["viewsPerPost"] = round(item["views"] / item["posts"]) if item["posts"] else 0
    result.sort(key=lambda i: (i["ranks"].get("all", 99), -i["views"]))
    return result


def global_trends(data: dict, period: str, min_countries: int = 2) -> list[dict]:
    """Hashtags that trend in several countries at once for the given period."""
    by_tag: dict[str, dict] = {}
    for country, periods in data.items():
        block = periods.get(period)
        if not block:
            continue
        for item in block["items"]:
            entry = by_tag.setdefault(
                item["name"],
                {"name": item["name"], "countries": [], "views": 0, "posts": 0,
                 "industries": set(), "momentum": {}},
            )
            entry["countries"].append(country)
            entry["views"] += item["views"]
            entry["posts"] += item["posts"]
            entry["industries"].update(item["industries"])
            entry["momentum"][item["momentum"]] = entry["momentum"].get(item["momentum"], 0) + 1

    result = []
    for entry in by_tag.values():
        if len(entry["countries"]) < min_countries:
            continue
        entry["industries"] = sorted(entry["industries"], key=int)
        entry["momentum"] = max(entry["momentum"].items(), key=lambda kv: kv[1])[0]
        result.append(entry)
    result.sort(key=lambda e: (-len(e["countries"]), -e["views"]))
    return result[:50]


# ---------------------------------------------------------------------------
# History handling
# ---------------------------------------------------------------------------

def update_history(history: dict, data: dict, now: datetime) -> dict:
    """Update the rolling history and annotate `data` items with history info.

    History layout (timestamps are unix seconds to keep the file small):
        {"_meta": {"started": ts, "updated": ts},
         "entries": {"DE|7": {"hashtag": {"fs": first_seen, "ls": last_seen,
                                          "s": [[ts, views], ...]}}}}

    Adds to every item: isNew (first seen within 24 h, once we have tracked
    for more than 24 h) and viewsDelta (vs. the previous snapshot or None).
    """
    now_ts = int(now.timestamp())
    meta = history.setdefault("_meta", {"started": now_ts})
    new_cutoff = now_ts - 24 * 3600
    tracking_long_enough = meta["started"] <= new_cutoff
    entries = history.setdefault("entries", {})

    for country, periods in data.items():
        for period, block in periods.items():
            bucket = entries.setdefault(f"{country}|{period}", {})
            for item in block["items"]:
                h = bucket.get(item["name"])
                if h is None:
                    h = bucket[item["name"]] = {"fs": now_ts, "ls": now_ts, "s": []}
                prev = h["s"][-1] if h["s"] else None
                h["ls"] = now_ts
                h["s"] = (h["s"] + [[now_ts, item["views"]]])[-config.HISTORY_MAX_POINTS:]

                item["isNew"] = tracking_long_enough and h["fs"] >= new_cutoff
                item["viewsDelta"] = item["views"] - prev[1] if prev else None

    # Prune hashtags that have not been seen for a while.
    cutoff = now_ts - config.HISTORY_RETENTION_DAYS * 86400
    for key, bucket in list(entries.items()):
        for name in [n for n, h in bucket.items() if h["ls"] < cutoff]:
            del bucket[name]
        if not bucket:
            del entries[key]
    meta["updated"] = now_ts
    return history


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)
