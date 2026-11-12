"""Static configuration: countries, industries and periods offered by the Creative Center."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Default output directory. In CI this is a checkout of the `data` branch.
SITE_DIR = ROOT / "site"
TEMPLATE_PATH = ROOT / "dashboard" / "template.html"

API_URL = "https://ads.tiktok.com/CreativeOne/KnowledgeAPI/GetHashtagList"
REFERER = "https://ads.tiktok.com/creative/creativeCenter/trends/hashtag"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# Without a login the API returns at most the top 3 hashtags per query.
# We therefore query every industry separately to widen the picture.
PAGE_LIMIT = 3

# Countries offered in the Creative Center country picker (ISO code -> German label).
COUNTRIES: dict[str, str] = {
    "DE": "Deutschland",
    "US": "USA",
    "GB": "Großbritannien",
    "FR": "Frankreich",
    "IT": "Italien",
    "ES": "Spanien",
    "AR": "Argentinien",
    "AU": "Australien",
    "BR": "Brasilien",
    "CA": "Kanada",
    "CO": "Kolumbien",
    "EG": "Ägypten",
    "ID": "Indonesien",
    "IL": "Israel",
    "JP": "Japan",
    "KR": "Südkorea",
    "MY": "Malaysia",
    "MX": "Mexiko",
    "PH": "Philippinen",
    "SA": "Saudi-Arabien",
    "SG": "Singapur",
    "ZA": "Südafrika",
    "TW": "Taiwan",
    "TH": "Thailand",
    "TR": "Türkei",
    "AE": "VAE",
    "VN": "Vietnam",
}

# Industry IDs used by the API (verified against live responses).
INDUSTRIES: dict[int, str] = {
    10000000000: "Bildung",
    11000000000: "Fahrzeuge & Verkehr",
    12000000000: "Baby, Kinder & Mutterschaft",
    13000000000: "Finanzen",
    14000000000: "Beauty & Körperpflege",
    15000000000: "Tech & Elektronik",
    16000000000: "Haushaltsgeräte",
    17000000000: "Reisen",
    18000000000: "Haushaltsprodukte",
    19000000000: "Haustiere",
    20000000000: "Apps",
    21000000000: "Heimwerken",
    22000000000: "Mode & Accessoires",
    23000000000: "News & Entertainment",
    24000000000: "Business Services",
    25000000000: "Games",
    27000000000: "Essen & Trinken",
    28000000000: "Sport & Outdoor",
    29000000000: "Gesundheit",
}

# Period (days) -> whether every industry is queried (True) or only the overall ranking.
PERIODS: dict[int, bool] = {
    7: True,
    30: True,
    90: False,
}

DEFAULT_COUNTRY = "DE"

# How long hashtags stay in history after they were last seen.
HISTORY_RETENTION_DAYS = 30
# Number of snapshots kept per hashtag (4 runs/day -> 2 days).
HISTORY_MAX_POINTS = 8
