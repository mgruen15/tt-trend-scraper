"""Token-efficient, machine-oriented export of the trend data for AI agents.

Writes (relative to the site root):
    llms.txt              reading guide for agents (entry point)
    agent/<CC>.tsv        one row per trending hashtag in that country, pre-scored
    agent/global.tsv      hashtags trending in several countries
    agent/top.tsv         top 10 opportunities per country
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import config
from .analysis import industry_key

MOM = {"rising": "R", "peak": "H", "fading": "F", "steady": "S"}
SLUG = {industry_key(k): v for k, v in config.INDUSTRY_SLUGS.items()}

COLUMNS = [
    "s", "tag", "ind", "top", "m7", "v7", "p7", "vpp", "dv", "c7",
    "m30", "v30", "c30", "m90", "c90", "g", "fl", "cr",
]


def compact(n: int | None) -> str:
    """26332488 -> 26.3M, 1846 -> 1.8K, 950 -> 950."""
    if n is None:
        return "-"
    sign = "-" if n < 0 else ""
    n = abs(n)
    for div, suf in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= div:
            v = n / div
            return f"{sign}{v:.0f}{suf}" if v >= 100 else f"{sign}{v:.1f}{suf}".replace(".0" + suf, suf)
    return f"{sign}{n}"


def digits(curve: list[int]) -> str:
    """Encode a 0-100 curve as one digit (0-9) per point."""
    if not curve:
        return "-"
    peak = max(curve) or 100
    return "".join(str(min(9, int(v / peak * 9 + 0.5))) for v in curve)


def _date(ts: int) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else "?"


def _access_points(creators: list[dict]) -> int:
    """Reward hashtags where small accounts are among the top creators."""
    if not creators:
        return 5
    smallest = min(c["followers"] for c in creators)
    if smallest < 10_000:
        return 15
    if smallest < 100_000:
        return 10
    if smallest < 1_000_000:
        return 5
    return 0


def build_rows(country: str, latest: dict) -> list[dict]:
    periods = latest["data"].get(country, {})
    by_tag: dict[str, dict[str, dict]] = {}
    for period, block in periods.items():
        for item in block["items"]:
            by_tag.setdefault(item["name"], {})[period] = item

    spread: dict[str, int] = {}
    for period in ("7", "30"):
        for g in latest["global"].get(period, []):
            spread.setdefault(g["name"], len(g["countries"]))

    # vpp percentile within the country (based on 7d, else 30d, else 90d)
    def base(entry: dict) -> dict:
        return entry.get("7") or entry.get("30") or entry.get("90")

    vpps = sorted(base(e)["viewsPerPost"] for e in by_tag.values())

    def vpp_pct(v: int) -> float:
        if len(vpps) < 2:
            return 0.5
        below = sum(1 for x in vpps if x < v)
        return below / (len(vpps) - 1)

    rows = []
    for tag, entry in by_tag.items():
        b = base(entry)
        i7, i30, i90 = entry.get("7"), entry.get("30"), entry.get("90")

        if i7:
            mom_pts = {"rising": 40, "peak": 25, "steady": 10, "fading": 0}[i7["momentum"]]
        elif i30:
            mom_pts = {"rising": 20, "peak": 12}.get(i30["momentum"], 0)
        else:
            mom_pts = 0
        g = spread.get(tag, 1)
        flags = ""
        if any(e.get("isNew") for e in entry.values()):
            flags += "N"
        if i7 and i30 and i90:
            flags += "E"
        if i7 and not i30 and not i90:
            flags += "X"
        fresh = min(10, 5 * flags.count("N") + 5 * flags.count("X"))
        raw_score = (
            mom_pts
            + 20 * vpp_pct(b["viewsPerPost"])
            + _access_points(b["creators"])
            + min(g - 1, 4) * 2.5
            + fresh
        )
        industries = sorted({k for e in entry.values() for k in e["industries"]}, key=int)
        top = "|".join(
            f"{p}:{e['ranks']['all']}" for p, e in sorted(entry.items(), key=lambda kv: int(kv[0]))
            if "all" in e["ranks"]
        )
        rows.append({
            "s": round(raw_score * 100 / 95),
            "tag": tag,
            "ind": "+".join(SLUG.get(k, k) for k in industries) or "-",
            "top": top or "-",
            "m7": MOM[i7["momentum"]] if i7 else "-",
            "v7": compact(i7["views"]) if i7 else "-",
            "p7": compact(i7["posts"]) if i7 else "-",
            "vpp": compact(b["viewsPerPost"]),
            "dv": compact(i7["viewsDelta"]) if i7 and i7.get("viewsDelta") else "-",
            "c7": digits(i7["curve"]) if i7 else "-",
            "m30": MOM[i30["momentum"]] if i30 else "-",
            "v30": compact(i30["views"]) if i30 else "-",
            "c30": digits(i30["curve"]) if i30 else "-",
            "m90": MOM[i90["momentum"]] if i90 else "-",
            "c90": digits(i90["curve"]) if i90 else "-",
            "g": str(g),
            "fl": flags or "-",
            "cr": ",".join(f"{c['handle']}:{compact(c['followers'])}" for c in b["creators"]) or "-",
        })
    rows.sort(key=lambda r: (-r["s"], r["tag"]))
    return rows


def _tsv(rows: list[dict], cols: list[str]) -> str:
    return "\n".join("\t".join(str(r[c]).replace("\t", " ") for c in cols) for r in rows)


def write_agent_files(latest: dict, out_dir: Path) -> None:
    agent_dir = out_dir / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    gen = latest["generatedAt"][:16].replace("+00:00", "") + "Z"

    top_rows = []
    for country in latest["data"]:
        rows = build_rows(country, latest)
        until = max((b.get("dataUntil", 0) for b in latest["data"][country].values()), default=0)
        header = (
            f"#ttr1 country={country} gen={gen} data_until={_date(until)} rows={len(rows)} "
            f"sort=s_desc guide={config.SITE_URL}llms.txt\n"
            + "\t".join(COLUMNS) + "\n"
        )
        (agent_dir / f"{country}.tsv").write_text(header + _tsv(rows, COLUMNS) + "\n", encoding="utf-8")
        for r in rows[:10]:
            top_rows.append({"cc": country, **r})

    top_cols = ["cc", "s", "tag", "ind", "m7", "v7", "vpp", "g", "fl"]
    (agent_dir / "top.tsv").write_text(
        f"#ttr1 top10_per_country gen={gen}\n" + "\t".join(top_cols) + "\n"
        + _tsv(top_rows, top_cols) + "\n", encoding="utf-8")

    glob_rows = []
    for period in ("7", "30"):
        for g in latest["global"].get(period, []):
            glob_rows.append({
                "p": period, "tag": g["name"], "g": len(g["countries"]),
                "m": MOM.get(g["momentum"], "S"), "v": compact(g["views"]),
                "ind": "+".join(SLUG.get(k, k) for k in g["industries"]) or "-",
                "cc": ",".join(g["countries"]),
            })
    glob_cols = ["p", "tag", "g", "m", "v", "ind", "cc"]
    (agent_dir / "global.tsv").write_text(
        f"#ttr1 multi_country_trends gen={gen}\n" + "\t".join(glob_cols) + "\n"
        + _tsv(glob_rows, glob_cols) + "\n", encoding="utf-8")

    (out_dir / "llms.txt").write_text(guide(latest, gen), encoding="utf-8")


def guide(latest: dict, gen: str) -> str:
    base = config.SITE_URL
    countries = " ".join(latest["countries"])
    slugs = " ".join(sorted(SLUG.values()))
    return f"""# TikTok Trend Radar — agent guide (format ttr1, generated {gen})
Source: TikTok Creative Center public hashtag trends, scraped 4x/day. Data lags ~2 days (see data_until).
Purpose: help you pick hashtags/topics and script a TikTok video with maximum viral potential.

## Files (plain TSV, tab-separated, first line = metadata, second line = column names)
{base}agent/<CC>.tsv   all trending hashtags of one country, sorted by score s (desc). <CC> in: {countries}
{base}agent/top.tsv    top 10 per country (cross-market overview)
{base}agent/global.tsv hashtags trending in >=2 countries (p=period days, g=#countries, cc=country list)
{base}data/latest.json full raw JSON (large; only if TSV is insufficient)
Fetch ONLY the country file(s) you need. Default market if user gives none: DE.

## Columns of <CC>.tsv
s    opportunity score 0-100 (see formula). Higher = better bet to ride now.
tag  hashtag without '#'. Video page: https://www.tiktok.com/tag/<tag>
ind  industries ({slugs}); '+' joins several
top  overall top-3 rank(s) as period:rank, e.g. 7:1|30:3 (official Creative Center ranking)
m7/m30/m90 momentum of the popularity curve in that period: R=rising (peak is now, growing) H=high (>=60% of peak) F=fading (past peak, <60%) S=no signal; '-' = not in that period's lists
v7/v30 views in period, p7 posts in last 7d (K/M/B suffixes)
vpp  average views per post (reach per video; high = undersaturated, each video gets many views)
dv   views gained since previous scrape (~6h), 7d list
c7/c30/c90 popularity curve, one digit per point (0=low..9=period peak), oldest->newest. c7 daily (7 pts), c30 ~20 pts, c90 30 pts (3-day buckets)
g    number of countries where tag currently trends
fl   flags: N=new (first seen <24h) E=evergreen (in 7d,30d and 90d lists) X=flash (only in 7d list = fresh wave)
cr   top creators handle:followers (study their videos at https://www.tiktok.com/@<handle>)

## Score formula (max 100)
s = (momentum7[R40 H25 S10 F0; if absent use 30d: R20 H12] + 20*vpp_percentile_in_country
     + access[smallest top-creator <10K:15 <100K:10 <1M:5 else 0] + min(g-1,4)*2.5 + fresh[N:+5 X:+5]) *100/95
Interpretation: R + high vpp + small creators in cr = algorithm currently pushes this tag to newcomers.

## Recipe: from user request to script
1. Identify user's market (CC) and niche -> map niche to ind slug(s).
2. Fetch agent/<CC>.tsv. Filter rows whose ind matches the niche; also keep top ~10 rows overall (cross-niche trends to piggyback).
3. Primary tag: highest s with m7 in R/H. Prefer X/N (early wave) for virality, E for reliable steady reach. Avoid m7=F unless E (evergreen niche).
4. Read c7: rising tail (e.g. 1259) = post within 24-72h; plateau (9999) = saturated, needs a twist; falling (9631) = too late.
5. Hashtag set: 1 primary trend tag + 1-2 niche tags from same ind + optionally 1 broad tag with large v7. 3-5 tags total.
6. Script: hook in the first 1-2 s that explicitly references the trend (sound/format/phrase behind the tag), payoff early, 15-35 s, on-screen text + spoken line mirroring the tag topic, end with a loop or question to drive comments. (General TikTok heuristics, not derived from this data.)
7. If unsure what a tag is about: inspect https://www.tiktok.com/tag/<tag> and the cr creators before scripting.

## Caveats
Only top 3 per industry/country/period are public, so lists are wide not deep. Rankings come from TikTok's ads Creative Center. Values in a row may come from different period lists.
"""
