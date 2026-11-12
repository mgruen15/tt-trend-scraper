"""Render the self-contained dashboard (index.html) from the template."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from . import config

PLACEHOLDER = "/*__TREND_DATA__*/null"


def render_dashboard(latest: dict, out_dir: Path = config.SITE_DIR) -> Path:
    """Write <out_dir>/index.html with the data inlined, so the file works standalone."""
    template = config.TEMPLATE_PATH.read_text(encoding="utf-8")
    if PLACEHOLDER not in template:
        raise RuntimeError(f"Placeholder {PLACEHOLDER!r} missing in template")
    payload = json.dumps(latest, ensure_ascii=False, separators=(",", ":"))
    # Prevent the JSON from closing the <script> tag early.
    payload = payload.replace("</", "<\\/")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "index.html"
    out.write_text(template.replace(PLACEHOLDER, payload), encoding="utf-8")
    # GitHub Pages: serve files as-is.
    (out_dir / ".nojekyll").touch()
    return out


def main(argv: list[str] | None = None) -> int:
    """Re-render index.html from <dir>/data/latest.json (handy while editing the template)."""
    out_dir = Path((argv or sys.argv[1:] or [str(config.SITE_DIR)])[0])
    latest = json.loads((out_dir / "data" / "latest.json").read_text(encoding="utf-8"))
    print(f"Wrote {render_dashboard(latest, out_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
