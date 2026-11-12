"""Entry point: scrape the Creative Center, analyse and write dashboard data.

Usage:
    python -m tt_trends.scrape                 # full run (all countries)
    python -m tt_trends.scrape --countries DE US --workers 4
    python -m tt_trends.scrape --out path/to/site   # write somewhere else
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import agent, analysis, config, render
from .client import ApiError, fetch_hashtags

log = logging.getLogger("tt_trends")


def build_jobs(countries: list[str]) -> list[tuple[str, int, int | None]]:
    jobs: list[tuple[str, int, int | None]] = []
    for country in countries:
        for period, per_industry in config.PERIODS.items():
            jobs.append((country, period, None))
            if per_industry:
                jobs.extend((country, period, ind) for ind in config.INDUSTRIES)
    return jobs


def run(countries: list[str], workers: int) -> tuple[dict, dict]:
    jobs = build_jobs(countries)
    log.info("Fetching %d lists (%d countries) with %d workers", len(jobs), len(countries), workers)

    # raw[country][period][list_key] = items
    raw: dict[str, dict[str, dict[str, list]]] = {}
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_hashtags, c, p, i): (c, p, i) for c, p, i in jobs}
        for done, fut in enumerate(as_completed(futures), 1):
            country, period, industry = futures[fut]
            key = "all" if industry is None else analysis.industry_key(industry)
            try:
                items = fut.result()
            except ApiError as exc:
                failed.append(f"{country}/{period}/{key}")
                log.warning("%s", exc)
                continue
            raw.setdefault(country, {}).setdefault(str(period), {})[key] = items
            if done % 100 == 0:
                log.info("  %d/%d done", done, len(jobs))

    data: dict[str, dict[str, dict]] = {}
    for country in countries:
        for period in config.PERIODS:
            lists = raw.get(country, {}).get(str(period))
            if not lists:
                continue
            items = analysis.merge_lists(lists)
            for item in items:  # momentum is computed on the full curve; shrink for output
                item["curve"] = analysis.downsample(item["curve"], config.MAX_CURVE_POINTS)
            top = [i["name"] for i in items if "all" in i["ranks"]]
            data_until = max((i["curveEnd"] for i in items), default=0)
            data.setdefault(country, {})[str(period)] = {
                "items": items, "top": top, "dataUntil": data_until,
            }

    stats = {"requests": len(jobs), "failed": len(failed), "failedLists": failed[:50]}
    return data, stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--countries", nargs="*", default=list(config.COUNTRIES),
                        help="ISO country codes (default: all)")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, default=config.SITE_DIR,
                        help="Output directory for index.html and data/ (default: ./site)")
    parser.add_argument("--max-failure-rate", type=float, default=0.3,
                        help="Abort without writing if more lists than this fail")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    countries = [c.upper() for c in args.countries if c.upper() in config.COUNTRIES]
    if not countries:
        parser.error("no valid countries given")

    now = analysis.utcnow()
    data, stats = run(countries, args.workers)

    failure_rate = stats["failed"] / max(1, stats["requests"])
    if failure_rate > args.max_failure_rate or not data:
        log.error("Failure rate %.0f%% too high - keeping previous data.", failure_rate * 100)
        return 1

    data_dir = args.out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    history_path = data_dir / "history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else {}
    analysis.update_history(history, data, now)

    latest = {
        "generatedAt": now.isoformat(timespec="seconds"),
        "defaultCountry": config.DEFAULT_COUNTRY,
        "siteUrl": config.SITE_URL,
        "countries": {c: config.COUNTRIES[c] for c in countries},
        "industries": {analysis.industry_key(k): v for k, v in config.INDUSTRIES.items()},
        "periods": [str(p) for p in config.PERIODS],
        "data": data,
        "global": {str(p): analysis.global_trends(data, str(p)) for p in config.PERIODS},
        "stats": stats,
    }

    (data_dir / "latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, separators=(",", ":"))
    )
    history_path.write_text(json.dumps(history, ensure_ascii=False, separators=(",", ":")))
    render.render_dashboard(latest, args.out)
    agent.write_agent_files(latest, args.out)

    total = sum(len(b["items"]) for p in data.values() for b in p.values())
    log.info("Done: %d hashtag entries, %d failed lists.", total, stats["failed"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
