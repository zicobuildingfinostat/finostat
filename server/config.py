"""Configuration, read from the environment (or a .env file next to this one).

Nothing secret is ever stored in this repository. Copy .env.example to .env,
fill it in, and keep .env out of version control.
"""
import os
import pathlib

_HERE = pathlib.Path(__file__).resolve().parent


def _load_dotenv() -> None:
    path = _HERE / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


HOST = os.environ.get("FINOSTAT_HOST", "127.0.0.1")
# Railway, Render and Fly inject $PORT and route to it. Binding anything else
# makes the deploy look healthy while the site is unreachable, so fall back to
# it before the default. FINOSTAT_PORT still wins when set explicitly.
PORT = _int("FINOSTAT_PORT", _int("PORT", 8000))

# "kite" uses the broker feed below; "simulator" (the default) needs no credentials.
FEED = os.environ.get("FINOSTAT_FEED", "simulator").strip().lower()

# --- Upstox (recommended) ---------------------------------------------------
# An Analytics Token from https://account.upstox.com/developer/apps is valid for
# a YEAR and needs no daily re-login, which is why this is the default broker.
UPSTOX_ACCESS_TOKEN = os.environ.get("UPSTOX_ACCESS_TOKEN", "").strip()

# --- Zerodha Kite Connect ---------------------------------------------------
KITE_API_KEY = os.environ.get("KITE_API_KEY", "").strip()
KITE_API_SECRET = os.environ.get("KITE_API_SECRET", "").strip()
KITE_ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN", "").strip()
KITE_BASE = "https://api.kite.trade"

# Kite's /quote endpoint is rate limited to 1 request/second. Stay under it.
# Only the REST feed polls; the WebSocket ticker is pushed and ignores this.
POLL_INTERVAL = _float("FINOSTAT_POLL_INTERVAL", 1.1)

# The simulator talks to nobody, so it can run at the refresh rate the site
# actually advertises.
SIM_INTERVAL = _float("FINOSTAT_SIM_INTERVAL", 0.2)

# --- Sheet shape ------------------------------------------------------------
SHEET_SYMBOL = os.environ.get("FINOSTAT_SYMBOL", "NIFTY").strip().upper()
SHEET_ROWS = _int("FINOSTAT_SHEET_ROWS", 9)      # strikes shown in the hero sheet
SHEET_STEP = _int("FINOSTAT_SHEET_STEP", 50)     # strike interval
SHEET_WING = _int("FINOSTAT_SHEET_WING", 100)    # butterfly wing width, in points

MINI_SYMBOL = os.environ.get("FINOSTAT_MINI_SYMBOL", "BANKNIFTY").strip().upper()

# Stock universe streamed alongside the index tape: "nse" (all NSE equities,
# F&O-flagged), "nse+bse" (adds BSE equity groups A/B/T/X/XT on a second
# socket), or "none".
UNIVERSE = os.environ.get("FINOSTAT_UNIVERSE", "nse").strip().lower()
MINI_STEP = _int("FINOSTAT_MINI_STEP", 100)

# --- News wire --------------------------------------------------------------
NEWS_REFRESH = _float("FINOSTAT_NEWS_REFRESH", 120.0)
NEWS_MAX = _int("FINOSTAT_NEWS_MAX", 120)
# Verified reachable with a plain urllib request. Moneycontrol and Business
# Standard both 403 on a non-browser user agent, so they are deliberately absent.
NEWS_FEEDS = [
    ("FIN", "Economic Times", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("FIN", "ET Stocks", "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"),
    ("FIN", "Livemint", "https://www.livemint.com/rss/markets"),
    ("GEO", "BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("GEO", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
]

STATIC_ROOT = _HERE.parent
