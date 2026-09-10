"""Finostat server.

Serves index.html with live numbers baked in, and backs the endpoints the page
already polls: /api/quotes, /api/sheet, /api/news and /api/news/stream.

Standard library only -- no pip install, no build step:

    python3 app.py
"""
from __future__ import annotations

import html
import json
import logging
import mimetypes
import os
import queue
import re
import signal
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, quote

import config
import feeds
import finch
import founder
import legal
import news
import alerts as alertsmod
import account
import assessment
import auth as authmod
import backup
import book
import brief
import broker
import builder
import cas
import econ
import econ_pages
import holidays
import events
import chains
import contracts
import indices
import mailer
import pages
import payments
import recorder
import strategies
import universe
import videos

logging.basicConfig(
    level=os.environ.get("FINOSTAT_LOG", "INFO").upper(),
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("finostat")

FEED = feeds.build_feed()
NEWS = news.NewsHub()
RECORDER = recorder.Recorder()
AUTH = authmod.Auth()
ALERTS = alertsmod.AlertEngine(AUTH.path, send_email=mailer.send_alert_email,
                               user_email=AUTH.email_for)
BACKUP = backup.DailyBackup(AUTH.path, AUTH.path.parent / "backups")
ASSESS = assessment.Assessments(AUTH.path)
BRIEFS = brief.Briefs(AUTH.path)
PAYMENTS = payments.Payments(AUTH.path)
RENEWALS = payments.RenewalReminder(AUTH, mailer.send_plain)
VIDEOS = videos.YouTubeFeed(cache=AUTH.path.parent / "videos.json")
BROKERS = broker.Brokers(AUTH.path)
_BROKER_CACHE: dict = {}          # user_id -> (ts, payload) so the panel's polling does not hammer Upstox


def _broker_client(user):
    acc = BROKERS.get(user["id"], "upstox")
    if acc is None:
        return None, {"error": "no broker connected", "connected": False}
    if acc["expired"] or not acc["token"]:
        return None, {"error": "Upstox session expired — reconnect", "connected": True, "expired": True}
    return broker.Upstox(acc["token"]), acc


def _safe_next(raw: str) -> str:
    """Only same-site paths may be a post-login destination."""
    raw = (raw or "").strip()
    if raw.startswith("/") and not raw.startswith("//") and "\\" not in raw and len(raw) < 200 and re.fullmatch(r"[A-Za-z0-9/_\-?=&%.#+]*", raw):
        return raw
    return ""


def _grant_and_notify(order_id: str, payment_id: str, source: str):
    """Activate an order (idempotent) and send the receipt + owner note once."""
    grant = payments.activate(AUTH, PAYMENTS, order_id, payment_id, source)
    if grant is None:
        return None
    email = AUTH.email_for(grant["user_id"]) or ""
    lines = payments.receipt_lines(grant, email)
    threading.Thread(target=mailer.send_plain, args=(email, f"Finostat receipt — {payments.LABEL[grant['plan']]} active", "Thank you. Your plan is active now.", lines), daemon=True).start()
    threading.Thread(target=mailer.send_owner_note, args=(f"Finostat payment: {email} — {grant['plan']} {grant['period']} ₹{grant['amount'] / 100:,.0f}", lines + [f"via {source}"]), daemon=True).start()
    return grant
CONSTITUENTS = indices.Constituents("NIFTY50")
FEED.index_members = CONSTITUENTS.members
CHAINS = chains.ChainManager(FEED, getattr(FEED, "contracts", None) or contracts.ContractIndex())
BRIEF = brief.Scheduler(FEED, CHAINS, BRIEFS, AUTH.path.parent / "brief.trigger")
CAS = cas.Recorder(FEED, CHAINS, cas.Store(AUTH.path))
BOOK = book.Store(AUTH.path)
HOLIDAYS = holidays.Holidays(AUTH.path)
ECON = econ.Econ(AUTH.path, holidays=HOLIDAYS)
EVENTS = events.Calendar(lambda: CONTRACTS_OF(FEED), CHAINS, cache=AUTH.path.parent / "events.json", econ=ECON)


def _book_payload(user) -> dict:
    """Every open position (paper + broker) marked off the live chains."""
    positions = BOOK.open_positions(user["id"])
    client, _acc = _broker_client(user)
    if client is not None:
        try:
            positions += book.broker_positions(client.positions(), CONTRACTS_OF(FEED))
        except broker.BrokerError as exc:
            log.debug("book: broker positions unavailable: %s", exc)
    marked = []
    for p in positions:
        try:
            chain = CHAINS.chain(p["u"], int(p["expiry"]))
        except Exception:
            chain = {}
        if "rows" not in chain:
            chain = {}
        marked.append(book.mark(p, chain))
    quotes = FEED.snapshot().get("quotes") or []
    return {"positions": marked, "totals": book.totals(marked, quotes), "scenarios": book.scenarios(marked),
            "closed": BOOK.closed_positions(user["id"], 15), "broker": client is not None}


def _plan_of(user) -> str:
    """Anonymous visitors get the free tier's entitlements; the point of Starter
    being free is that people can try the index builder before signing in."""
    return (user or {}).get("plan") or "starter"


def CONTRACTS_OF(feed):
    """The contract index the chains use (the feed builds it at resolve time)."""
    return getattr(feed, "contracts", None) or CHAINS.contracts


def _paid(user) -> bool:
    """Desk or Pro (and not expired): the terminal and its data streams."""
    return authmod.entitled(_plan_of(user), "terminal")


# Everything the terminal page pulls. Finch's live examples use /api/quotes,
# /api/chain and /api/strategy (index only), which stay open so the free
# course keeps its live numbers.
TERMINAL_APIS = {"/api/sheet", "/api/sheet/stream", "/api/mini", "/api/history", "/api/news", "/api/news/stream",
                 "/api/symbols", "/api/quote", "/api/underlyings", "/api/alerts"}


def _gate(user, ukey: str):
    """(ok, error payload). Index chains are Starter; stock chains need Desk."""
    feature = "builder_index" if ukey in contracts.INDEX_UNDERLYINGS else "builder_stocks"
    plan = _plan_of(user)
    if authmod.entitled(plan, feature):
        return True, None
    need = authmod.ENTITLEMENTS[feature]
    return False, {"error": "plan required", "need": need, "plan": plan,
                   "signed_in": user is not None, "feature": feature}
PUBLIC_URL = os.environ.get("FINOSTAT_PUBLIC_URL", "").strip().rstrip("/")
# Search-engine ownership proofs. Both are public tokens, set as plain env in fly.toml.
#   GOOGLE_SITE_VERIFICATION  -> <meta name="google-site-verification"> on the homepage
#   BING_SITE_VERIFICATION    -> <meta name="msvalidate.01">
#   GOOGLE_VERIFY_FILE        -> serves /google<hex>.html (the "HTML file" method)
SITE_VERIFY = {k: os.environ.get(k, "").strip() for k in ("GOOGLE_SITE_VERIFICATION", "BING_SITE_VERIFICATION", "GOOGLE_VERIFY_FILE")}
_VERIFY_FILE_RE = re.compile(r"^google[0-9a-f]{8,32}\.html$")

# Routes the marketing page links to that are not built yet. They get an
# on-brand 404 instead of a stack trace, so a stray click never looks broken.
KNOWN_ROUTES: dict = {}
KNOWN_PREFIXES = ("/strategies/",)

# URLs the original marketing page advertised that were never built. Anything
# that already crawled or bookmarked them lands somewhere real.
RETIRED = {"/analysis": "/dashboard", "/live-session": "/contact", "/blog": "/finch",
           "/tools/gift-nifty": "/dashboard", "/tools": "/dashboard"}

# The old /learn URLs (linked from the homepage since launch) map onto Finch chapters.
LEARN_REDIRECTS = {
    "/learn": "/finch",
    "/learn/options-greeks": "/finch/the-greeks",
    "/learn/implied-volatility": "/finch/implied-volatility",
    "/learn/option-chain-analysis": "/finch/reading-the-chain",
    "/learn/how-to-read-the-sheets": "/finch/option-pricing",
}

# Static serving is an ALLOWLIST, not "anything under the project root".
# The root contains server/ -- which will contain .env with the Kite api_secret
# once it is configured. Serving the tree wholesale would publish it.
STATIC_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".avif",
    ".css", ".js", ".map", ".txt", ".xml", ".json", ".webmanifest",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".pdf", ".mp4", ".webm",
}
STATIC_DENY_DIRS = {"server", "deploy", "tests", "node_modules", "__pycache__"}


def _load() -> dict:
    """Process cost, so a market-open check can see what the universe costs."""
    try:
        import resource
        ru = resource.getrusage(resource.RUSAGE_SELF)
        rss = ru.ru_maxrss
        if sys.platform != "darwin":       # linux reports KB, macOS bytes
            rss *= 1024
        return {"rss_mb": round(rss / 1048576, 1), "cpu_s": round(ru.ru_utime + ru.ru_stime, 1),
                "threads": threading.active_count(), "uptime_s": int(time.time() - _STARTED)}
    except Exception:
        return {}


_STARTED = time.time()


def _json_safe(payload: dict | list) -> bytes:
    return json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")


BOOTSTRAP_RE = re.compile(r"<script>\s*window\.FINO\s*=\s*\{.*?\}\s*;?\s*</script>", re.S)


def _script_safe(payload) -> str:
    """JSON that is safe to embed inside a <script> block."""
    return json.dumps(payload, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")


class SnapshotHub:
    """Fans feed snapshots out to browsers over SSE.

    Slow subscribers are dropped rather than allowed to back-pressure the feed,
    and only the newest snapshot is ever kept per subscriber -- a browser that
    stalls for a second wants the current sheet, not a queued history of it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue] = []

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=1)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def publish(self, snapshot: dict) -> None:
        payload = {
            "rows": snapshot.get("sheet", {}).get("rows", []),
            "quotes": snapshot.get("quotes", []),
            "mini": snapshot.get("mini", []),
            "atm": snapshot.get("atm"),
            "straddle": snapshot.get("straddle"),
            "live": snapshot.get("live"),
        }
        with self._lock:
            targets = list(self._subscribers)
        for q in targets:
            try:
                q.get_nowait()      # drop the stale one
            except queue.Empty:
                pass
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass

    def count(self) -> int:
        with self._lock:
            return len(self._subscribers)


SHEETS = SnapshotHub()


class Page:
    """index.html, re-rendered from disk whenever it changes."""

    def __init__(self, path):
        self.path = path
        self._mtime = None
        self._raw = ""
        self._lock = threading.Lock()

    def _raw_html(self) -> str:
        mtime = self.path.stat().st_mtime
        with self._lock:
            if mtime != self._mtime:
                self._raw = self.path.read_text(encoding="utf-8")
                self._mtime = mtime
            return self._raw

    def render(self) -> bytes:
        doc = self._raw_html()
        snap = FEED.snapshot()
        live = bool(snap.get("live"))

        boot = _script_safe({
            "symbol": snap.get("symbol"),
            "atm": snap.get("atm"),
            "sheet": snap.get("sheet", {}).get("rows", []),
            "mini": snap.get("mini", []),
            "straddle": snap.get("straddle"),
            "live": live,
        })
        tag = f"<script>window.FINO={boot};</script>"
        # index.html ships with a static window.FINO seed. Replace it outright --
        # injecting alongside it would let the stale seed win and quietly serve
        # yesterday's prices.
        doc, hits = BOOTSTRAP_RE.subn(lambda _m: tag, doc, count=1)
        if not hits:
            doc = doc.replace("<script>", tag + "\n<script>", 1)

        # The hero badge and the wire indicator should tell the truth.
        doc = doc.replace('<span class="r"><span>DEMO</span></span>',
                          f'<span class="r"><span>{"LIVE" if live else "DEMO"}</span></span>', 1)

        items = NEWS.latest(40)
        if items:
            doc = doc.replace('<span id="wire-live">STATIC</span>',
                              '<span id="wire-live">LIVE</span>', 1)
            doc = re.sub(
                r'(<ul class="wire-list" id="wire-list">).*?(</ul>)',
                lambda m: m.group(1) + self._wire(items) + m.group(2),
                doc, count=1, flags=re.S,
            )
        # Latest YouTube uploads: section markup, its CSS, and the click-to-play script.
        doc = doc.replace("<!--VIDEOS-->", videos.render_section(VIDEOS.latest(6), videos.load_reels()), 1)
        doc = doc.replace("/*VIDEOS_CSS*/", videos.CSS, 1)
        doc = doc.replace("<!--EVENTS-->", _home_events(), 1)
        doc = doc.replace("/*EVENTS_CSS*/", econ._HOME_CSS, 1)
        doc = doc.replace("</body>", "<script>" + videos.JS + "</script>\n</body>", 1)
        metas = ""
        if SITE_VERIFY["GOOGLE_SITE_VERIFICATION"]:
            metas += f'<meta name="google-site-verification" content="{html.escape(SITE_VERIFY["GOOGLE_SITE_VERIFICATION"], quote=True)}">\n'
        if SITE_VERIFY["BING_SITE_VERIFICATION"]:
            metas += f'<meta name="msvalidate.01" content="{html.escape(SITE_VERIFY["BING_SITE_VERIFICATION"], quote=True)}">\n'
        if metas:
            doc = doc.replace("</head>", metas + "</head>", 1)
        # First-visit trader assessment (the page's own JS decides whether to pop it).
        doc = doc.replace("</body>", assessment.widget_html() + "\n</body>", 1)
        return doc.encode("utf-8")

    @staticmethod
    def _wire(items) -> str:
        out = []
        for n in items:
            esc = lambda s: html.escape(str(s), quote=True)
            out.append(
                f'<li data-cat="{esc(n["category"])}" class="{"hot" if n["hot"] else ""}">'
                f'<time data-ts="{n["ts"]}">--:--</time>'
                f'<div><a href="{esc(n["url"])}" target="_blank" rel="noopener">{esc(n["text"])}</a>'
                f'<div class="meta"><span class="tag {esc(n["category"].lower())}">{esc(n["category"])}</span>'
                f'<span>{esc(n["handle"])}</span></div></div></li>'
            )
        return "".join(out)


_HOME_EVENTS: dict = {"at": 0.0, "html": ""}


def _home_events() -> str:
    """The homepage calendar strip, re-rendered at most every five minutes."""
    now = time.time()
    if now - _HOME_EVENTS["at"] > 300:
        try:
            _HOME_EVENTS["html"] = econ.home_section(ECON)
        except Exception:
            log.exception("home events strip failed")
            _HOME_EVENTS["html"] = ""
        _HOME_EVENTS["at"] = now
    return _HOME_EVENTS["html"]


PAGE = Page(config.STATIC_ROOT / "index.html")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Finostat"
    sys_version = ""

    def log_message(self, fmt, *args):  # quieter than the default
        log.debug("%s %s", self.address_string(), fmt % args)

    # -- helpers ------------------------------------------------------------
    def _send(self, body: bytes, ctype: str, status: int = 200, cache: str = "no-store"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, payload, status: int = 200):
        self._send(_json_safe(payload), "application/json; charset=utf-8", status)

    def _redirect(self, location: str, extra_headers=()):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        for name, value in extra_headers:
            self.send_header(name, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _secure(self) -> bool:
        return (self.headers.get("X-Forwarded-Proto", "").lower() == "https"
                or PUBLIC_URL.startswith("https://"))

    def _client_ip(self) -> str:
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() if fwd else (self.client_address[0] if self.client_address else "")

    def _base_url(self) -> str:
        if PUBLIC_URL:
            return PUBLIC_URL
        host = self.headers.get("Host", "localhost")
        return ("https://" if self._secure() else "http://") + host

    def _current_user(self):
        sid = authmod.Auth.sid_from_cookie_header(self.headers.get("Cookie"))
        return AUTH.user_for_session(sid)

    def _read_body(self, limit: int = 64 * 1024) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            return b""
        if length <= 0 or length > limit:
            return b""
        return self.rfile.read(length)

    # -- routing ------------------------------------------------------------
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        try:
            if route in ("/", "/index.html"):
                return self._send(PAGE.render(), "text/html; charset=utf-8")
            if route == "/dashboard":
                user = self._current_user()
                paid = _paid(user)
                return self._send(pages.render_dashboard(FEED.snapshot(), locked=not paid, signed_in=user is not None,
                                                         plan=_plan_of(user)),
                                  "text/html; charset=utf-8", cache="no-store")
            if (route in TERMINAL_APIS or route.startswith("/api/alerts/")) and not _paid(self._current_user()):
                return self._json({"error": "plan required", "need": "desk", "feature": "terminal",
                                   "signed_in": self._current_user() is not None}, 402)
            if _VERIFY_FILE_RE.match(route[1:]) and route[1:] == SITE_VERIFY["GOOGLE_VERIFY_FILE"]:
                return self._send(f"google-site-verification: {route[1:]}\n".encode(), "text/html; charset=utf-8", cache="public, max-age=3600")
            if route.startswith("/calendar/") and route.count("/") == 2:
                body = econ_pages.render(route[len("/calendar/"):], holidays=HOLIDAYS, contracts=CONTRACTS_OF(FEED))
                if body is not None:
                    return self._send(body, "text/html; charset=utf-8", cache="public, max-age=3600")
            if route == "/calendar":
                qs = parse_qs(parsed.query)
                d = qs.get("d", [""])[0]
                anchor = None
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                    try:
                        anchor = econ.date.fromisoformat(d)
                    except ValueError:
                        anchor = None
                return self._send(econ.render(ECON, anchor), "text/html; charset=utf-8", cache="public, max-age=300")
            if route == "/api/expiries":
                today = econ.datetime.now(econ.IST).date()
                return self._json({"expiries": econ_pages.expiry_rows(CONTRACTS_OF(FEED), today, HOLIDAYS.dates())})
            if route == "/api/holidays":
                return self._json({"holidays": HOLIDAYS.all(), "fetched": HOLIDAYS.fetched})
            if route == "/api/calendar":
                qs = parse_qs(parsed.query)
                try:
                    days = max(1, min(60, int(qs.get("days", ["14"])[0])))
                except ValueError:
                    days = 14
                today = econ.datetime.now(econ.IST).date()
                return self._json({"events": ECON.events(today, today + econ.timedelta(days=days)), "fetched": ECON.fetched})
            if route == "/brief":
                return self._send(brief.render_index(BRIEFS), "text/html; charset=utf-8", cache="public, max-age=300")
            if route.startswith("/brief/"):
                date = route[len("/brief/"):]
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                    try:
                        extra = econ.brief_block(ECON, econ.date.fromisoformat(date))
                    except ValueError:
                        extra = ""
                    body = brief.render_day(BRIEFS, date, extra=extra, extra_css=econ._BRIEF_CSS)
                    if body is not None:
                        return self._send(body, "text/html; charset=utf-8", cache="public, max-age=300")
            if route == "/broker/upstox/connect":
                user = self._current_user()
                if user is None:
                    return self._redirect("/login?next=%2Fdashboard")
                if not _paid(user):
                    return self._redirect("/account?plan=desk")
                if not broker.configured():
                    return self._send(b"Broker connections are not switched on yet.", "text/plain; charset=utf-8", 503)
                return self._redirect(broker.authorize_url(BROKERS.new_state(user["id"], "upstox")))
            if route == "/broker/upstox/callback":
                qs = parse_qs(parsed.query)
                st = BROKERS.pop_state(qs.get("state", [""])[0])
                code = qs.get("code", [""])[0]
                user = self._current_user()
                if st is None or user is None or st[0] != user["id"] or not code:
                    log.warning("broker callback rejected (state ok=%s, signed in=%s)", st is not None, user is not None)
                    return self._redirect("/dashboard?broker=failed#p-broker")
                try:
                    info = broker.exchange_code(code)
                except broker.BrokerError as exc:
                    log.warning("upstox token exchange failed: %s", exc)
                    return self._redirect("/dashboard?broker=failed#p-broker")
                BROKERS.connect(user["id"], "upstox", info, broker.token_expiry())
                _BROKER_CACHE.pop(user["id"], None)
                log.info("broker connected: user %s -> upstox %s", user["id"], info.get("uid"))
                return self._redirect("/dashboard?broker=connected#p-broker")
            if route == "/api/broker":
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                if not _paid(user):
                    return self._json({"error": "plan required", "need": "desk"}, 402)
                out = BROKERS.status(user["id"])
                client, acc = _broker_client(user)
                if client is not None:
                    cached = _BROKER_CACHE.get(user["id"])
                    if cached and time.time() - cached[0] < 5:
                        out["upstox"] = cached[1]
                    else:
                        live = {}
                        for k, fn in (("funds", client.funds), ("positions", client.positions), ("orders", client.orders)):
                            try:
                                live[k] = fn()
                            except broker.BrokerError as exc:
                                live[k + "_error"] = str(exc)
                        _BROKER_CACHE[user["id"]] = (time.time(), live)
                        BROKERS.touch(user["id"], "upstox")
                        out["upstox"] = live
                elif acc.get("expired"):
                    out["upstox"] = {"expired": True}
                out["recent"] = BROKERS.recent_orders(user["id"], 10)
                out["can_trade"] = broker.trade_allowed(user["email"])
                return self._json(out)
            if route == "/api/events":
                if not _paid(self._current_user()):
                    return self._json({"error": "plan required", "need": "desk", "feature": "terminal"}, 402)
                try:
                    days = max(1, min(60, int(parse_qs(parsed.query).get("days", ["21"])[0])))
                except ValueError:
                    days = 21
                return self._json(EVENTS.calendar(days))
            if route == "/api/book":
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                if not _paid(user):
                    return self._json({"error": "plan required", "need": "desk", "feature": "terminal"}, 402)
                return self._json(_book_payload(user))
            if route == "/api/cas":
                if not _paid(self._current_user()):
                    return self._json({"error": "plan required", "need": "desk", "feature": "terminal"}, 402)
                qs = parse_qs(parsed.query)
                u = qs.get("u", ["NIFTY 50"])[0]
                if u not in cas.UNDERLYINGS:
                    return self._json({"error": "unknown index"}, 400)
                date = qs.get("date", [""])[0]
                if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                    return self._json({"error": "bad date"}, 400)
                return self._json(CAS.get(u, date or None))
            if route == "/api/videos":
                return self._json({"channel": videos.CHANNEL_URL, "videos": VIDEOS.latest(15), **VIDEOS.status()})
            if route == "/api/brief":
                rec = BRIEFS.latest()
                return self._json(rec or {"error": "no brief yet"}, 200 if rec else 404)
            if route == "/sitemap.xml":
                static = (config.STATIC_ROOT / "sitemap.xml").read_text(encoding="utf-8")
                xml = static.replace("</urlset>", brief.sitemap_entries(BRIEFS) + "</urlset>")
                return self._send(xml.encode("utf-8"), "application/xml; charset=utf-8", cache="public, max-age=3600")
            if route == "/about":
                return self._redirect("/founders")
            if route in RETIRED or route.startswith("/tools/"):
                return self._redirect(RETIRED.get(route, "/dashboard#p-builder"))
            if route in legal.PAGES:
                return self._send(legal.render(route), "text/html; charset=utf-8", cache="public, max-age=600")
            if route in ("/founders", "/founder"):
                return self._send(founder.render(), "text/html; charset=utf-8", cache="public, max-age=600")
            if route == "/assessment":
                return self._send(assessment.render_page(), "text/html; charset=utf-8", cache="public, max-age=300")
            if route == "/finch":
                return self._send(finch.render_index(), "text/html; charset=utf-8", cache="public, max-age=300")
            if route.startswith("/finch/"):
                body = finch.render_chapter(route[len("/finch/"):])
                if body is not None:
                    return self._send(body, "text/html; charset=utf-8", cache="public, max-age=300")
            if route in LEARN_REDIRECTS:
                return self._redirect(LEARN_REDIRECTS[route])
            if route.startswith("/learn/"):
                return self._redirect("/finch")
            if route in ("/login", "/signup"):
                qs = parse_qs(parsed.query)
                state = qs.get("state", ["form"])[0]
                nxt = _safe_next(qs.get("next", [""])[0])
                plan = qs.get("plan", [""])[0]
                if not nxt and plan in ("desk", "pro"):
                    nxt = f"/account?plan={plan}"
                return self._send(pages.render_login(state, mailer.configured(), nxt),
                                  "text/html; charset=utf-8", cache="no-store")
            if route == "/auth/verify":
                qs = parse_qs(parsed.query)
                token = qs.get("token", [""])[0]
                nxt = _safe_next(qs.get("next", [""])[0]) or "/dashboard"
                uid = AUTH.redeem_link(token)
                if uid is None:
                    return self._redirect("/login?state=expired")
                sid = AUTH.create_session(uid)
                return self._redirect(nxt, [("Set-Cookie", authmod.Auth.cookie_header(sid, self._secure()))])
            if route in ("/account", "/upgrade"):
                user = self._current_user()
                if user is None:
                    return self._redirect("/login?next=" + quote("/account" + (("?" + parsed.query) if parsed.query else ""), safe=""))
                return self._send(account.render(user, AUTH.plan_status(user["id"]), PAYMENTS.history(user["id"]), AUTH.get_prefs(user["id"]).get("phone") or ""),
                                  "text/html; charset=utf-8", cache="no-store")
            if route == "/api/me":
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                return self._json({"email": user["email"], "plan": user.get("plan", "starter"),
                                   "plan_until": user.get("plan_until"), "payments": payments.any_configured(),
                                   "entitlements": authmod.entitlements(user.get("plan", "starter")),
                                   "prefs": AUTH.get_prefs(user["id"])})
            if route == "/api/alerts":
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                return self._json({"alerts": ALERTS.list_for(user["id"]),
                                   "events": ALERTS.events_for(user["id"])})
            if route.startswith("/strategies/"):
                slug = route[len("/strategies/"):]
                snap = FEED.snapshot()
                computed = strategies.compute(
                    slug, snap.get("sheet", {}).get("rows", []),
                    snap.get("atm"), snap.get("straddle"))
                if computed is not None:
                    body = pages.render_strategy(slug, snap, computed)
                    if body is not None:
                        return self._send(body, "text/html; charset=utf-8")
            if route == "/api/strategies":
                snap = FEED.snapshot()
                return self._json({
                    "symbol": snap.get("symbol"), "live": snap.get("live"),
                    "atm": snap.get("atm"),
                    "strategies": strategies.compute_all(
                        snap.get("sheet", {}).get("rows", []),
                        snap.get("atm"), snap.get("straddle")),
                })
            if route == "/api/quotes":
                return self._json(FEED.snapshot().get("quotes", []))
            if route == "/api/sheet":
                snap = FEED.snapshot()
                return self._json({"rows": snap.get("sheet", {}).get("rows", []),
                                   "symbol": snap.get("symbol"), "atm": snap.get("atm"),
                                   "straddle": snap.get("straddle"), "live": snap.get("live")})
            if route == "/api/mini":
                return self._json(FEED.snapshot().get("mini", []))
            if route == "/api/status":
                snap = FEED.snapshot()
                return self._json({"feed": FEED.name, "live": snap.get("live"),
                                   "error": snap.get("error"), "headlines": len(NEWS.latest(999)),
                                   "ticks": snap.get("ticks"), "sheet_subscribers": SHEETS.count(),
                                   "interval": getattr(FEED, "interval", None),
                                   "recorder": RECORDER.stats(),
                                   "auth": {"smtp_configured": mailer.configured(), "payments": payments.any_configured(), "payments_test": payments.test_mode(),
                     "providers": [p["id"] + ("(test)" if p["test"] else "") for p in payments.providers() if p["configured"]]},
            "brief": {"last": BRIEF.last, "dates": BRIEFS.dates(3)},
            "videos": VIDEOS.status(),
            "broker": {"configured": broker.configured()},
            "cas": {"date": CAS.date, "sessions": {u: len(s.points) for u, s in CAS.today.items()}},
            "events": {"results": len(EVENTS.results), "fetched": EVENTS.fetched, "error": EVENTS.error},
            "econ": {"fetched": ECON.fetched, "error": ECON.error},
            "holidays": {"count": len(HOLIDAYS.all()), "fetched": HOLIDAYS.fetched, "error": HOLIDAYS.error},
                                   "alerts": ALERTS.stats(),
                                   "universe": len(snap.get("universe") or {}),
                                   "load": _load(),
                                   "backup": BACKUP.stats(),
                                   "indices": {"nifty50": CONSTITUENTS.stats()},
                                   "chains": CHAINS.stats(),
                                   "time": time.time()})
            if route == "/api/symbols":
                qs = parse_qs(parsed.query)
                snap = FEED.snapshot()
                if qs.get("group", [""])[0].lower() in ("nifty50", "n50"):
                    return self._json(universe.group(snap.get("universe") or {}, "n50"))
                try:
                    limit = int(qs.get("limit", ["20"])[0])
                except ValueError:
                    limit = 20
                return self._json(universe.search(snap.get("universe") or {}, snap.get("quotes") or [],
                                                  qs.get("q", [""])[0], limit))
            if route == "/api/quote":
                keys = [k for k in parse_qs(parsed.query).get("s", [""])[0].split(",") if k]
                snap = FEED.snapshot()
                return self._json(universe.lookup(snap.get("universe") or {}, snap.get("quotes") or [], keys))
            if route == "/api/underlyings":
                user = self._current_user()
                plan = _plan_of(user)
                return self._json({"underlyings": CHAINS.underlyings(), "plan": plan,
                                   "signed_in": user is not None,
                                   "entitlements": authmod.entitlements(plan)})
            if route == "/api/chain":
                qs = parse_qs(parsed.query)
                ukey = qs.get("u", [""])[0]
                ok, err = _gate(self._current_user(), ukey)
                if not ok:
                    return self._json(err, 403)
                try:
                    expiry = int(qs.get("expiry", ["0"])[0]) or None
                except ValueError:
                    expiry = None
                out = CHAINS.chain(ukey, expiry)
                return self._json(out, 404 if "error" in out and "rows" not in out else 200)
            if route == "/api/history":
                qs = parse_qs(parsed.query)
                since = None
                try:
                    if qs.get("since"): since = float(qs["since"][0])
                except ValueError:
                    pass
                try:
                    limit = max(1, min(2000, int(qs.get("limit", ["300"])[0])))
                except ValueError:
                    limit = 300
                return self._json(RECORDER.history(since=since, limit=limit))
            if route == "/api/news":
                limit = 30
                try:
                    limit = max(1, min(200, int(parse_qs(parsed.query).get("limit", ["30"])[0])))
                except ValueError:
                    pass
                return self._json(NEWS.latest(limit))
            if route == "/api/news/stream":
                return self._stream()
            if route == "/api/sheet/stream":
                return self._sheet_stream()
            return self._static(route)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser went away mid-response
        except Exception:
            log.exception("error handling %s", self.path)
            try:
                self._json({"error": "internal"}, 500)
            except OSError:
                pass

    def do_POST(self):
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        try:
            if route == "/auth/request":
                body = self._read_body().decode("utf-8", "replace")
                email = authmod.normalize_email(parse_qs(body).get("email", [""])[0])
                if email is None:
                    return self._redirect("/login?state=invalid")
                token = AUTH.create_link(email, ip=self._client_ip())
                if token is None:
                    return self._redirect("/login?state=limited")
                nxt = _safe_next(parse_qs(body).get("next", [""])[0])
                link = f"{self._base_url()}/auth/verify?token={quote(token, safe='')}" + (f"&next={quote(nxt, safe='')}" if nxt else "")
                if not mailer.send_magic_link(email, link):
                    return self._redirect("/login?state=failed")
                return self._redirect("/login?state=sent" + (f"&next={quote(nxt, safe='')}" if nxt else ""))
            if route == "/auth/logout":
                sid = authmod.Auth.sid_from_cookie_header(self.headers.get("Cookie"))
                AUTH.destroy_session(sid)
                return self._redirect("/", [("Set-Cookie", authmod.Auth.clear_cookie_header(self._secure()))])
            if route == "/api/alerts" or route.startswith("/api/alerts/"):
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                if not _paid(user):
                    return self._json({"error": "plan required", "need": "desk", "feature": "terminal", "signed_in": True}, 402)
                if self.headers.get("X-Requested-With") != "fetch":
                    return self._json({"error": "bad request"}, 400)
                if route == "/api/alerts":
                    try:
                        payload = json.loads(self._read_body().decode("utf-8"))
                    except ValueError:
                        return self._json({"error": "invalid json"}, 400)
                    if not isinstance(payload, dict):
                        return self._json({"error": "expected an object"}, 400)
                    snap = FEED.snapshot()
                    symbols = {q.get("symbol") for q in snap.get("quotes", [])} | set((snap.get("universe") or {}).keys())
                    rule, err = alertsmod.validate(payload, symbols or None)
                    if rule is None:
                        return self._json({"error": err}, 400)
                    created = ALERTS.create(user["id"], rule)
                    if created is None:
                        return self._json({"error": f"limit of {alertsmod.MAX_PER_USER} alerts"}, 409)
                    return self._json({"ok": True, "alert": created})
                parts = route.split("/")           # /api/alerts/<id>/<action>
                if len(parts) == 5 and parts[3].isdigit() and parts[4] in ("rearm", "delete"):
                    fn = ALERTS.rearm if parts[4] == "rearm" else ALERTS.delete
                    return self._json({"ok": fn(user["id"], int(parts[3]))})
                return self._json({"error": "not found"}, 404)
            if route == "/api/strategy":
                try:
                    body = json.loads(self._read_body().decode("utf-8"))
                except ValueError:
                    return self._json({"error": "invalid json"}, 400)
                if not isinstance(body, dict):
                    return self._json({"error": "expected an object"}, 400)
                ukey = str(body.get("u", ""))
                ok, err = _gate(self._current_user(), ukey)
                if not ok:
                    return self._json(err, 403)
                expiry = body.get("expiry")
                expiry = int(expiry) if isinstance(expiry, (int, float)) and expiry else None
                chain = CHAINS.chain(ukey, expiry)
                if "rows" not in chain:
                    return self._json(chain, 404)
                strikes = [r["strike"] for r in chain["rows"]]
                preset = body.get("preset")
                if preset:
                    legs = builder.preset_legs(str(preset), chain["atm"], chain["step"], strikes)
                    if legs is None:
                        return self._json({"error": "preset needs strikes outside the loaded chain"}, 400)
                else:
                    raw = body.get("legs")
                    if not isinstance(raw, list) or not raw or len(raw) > 8:
                        return self._json({"error": "1-8 legs required"}, 400)
                    legs = []
                    for l in raw:
                        try:
                            right, strike, qty = str(l["right"]).upper(), int(l["strike"]), int(l["qty"])
                        except (KeyError, TypeError, ValueError):
                            return self._json({"error": "each leg needs right, strike, qty"}, 400)
                        if right not in ("CE", "PE") or strike not in strikes or not (-10 <= qty <= 10) or qty == 0:
                            return self._json({"error": f"bad leg {l}"}, 400)
                        legs.append({"right": right, "strike": strike, "qty": qty})
                by_strike = {r["strike"]: r for r in chain["rows"]}
                ivs = {}
                for l in legs:
                    side = by_strike[l["strike"]].get(l["right"].lower())
                    if not side:
                        return self._json({"error": "chain still warming; try again in a moment", "warming": True}, 409)
                    l["price"] = side["ltp"]
                    l["iv"] = side.get("iv")
                    l["delta"] = side.get("delta")
                    if side.get("iv"):
                        ivs[(l["right"], l["strike"])] = side["iv"] / 100.0
                metrics = builder.evaluate(chain["spot"], legs, chain["lot"], chain["t_years"], ivs)
                return self._json({"underlying": ukey, "name": chain["name"], "kind": chain["kind"],
                                   "spot": chain["spot"], "expiry": chain["expiry"], "expiries": chain["expiries"],
                                   "lot": chain["lot"], "atm": chain["atm"], "step": chain["step"],
                                   "strikes": strikes, "legs": legs, "metrics": metrics,
                                   "live": chain["live"], "warming": chain["warming"]})
            if route in ("/api/book/open", "/api/book/close", "/api/book/delete"):
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                if self.headers.get("X-Requested-With") != "fetch":
                    return self._json({"error": "bad request"}, 400)
                if not _paid(user):
                    return self._json({"error": "plan required", "need": "desk"}, 402)
                try:
                    body = json.loads(self._read_body().decode("utf-8") or "{}")
                except ValueError:
                    return self._json({"error": "invalid json"}, 400)
                if route == "/api/book/open":
                    ukey = str(body.get("u", ""))
                    ok, err = _gate(user, ukey)
                    if not ok:
                        return self._json(err, 403)
                    try:
                        expiry = int(body.get("expiry") or 0)
                        lots = max(1, min(50, int(body.get("lots") or 1)))
                    except (TypeError, ValueError):
                        return self._json({"error": "bad expiry or lots"}, 400)
                    chain = CHAINS.chain(ukey, expiry)
                    if "rows" not in chain:
                        return self._json(chain, 404)
                    legs, entries = [], []
                    for l in list(body.get("legs") or [])[:8]:
                        try:
                            right, strike, qty = str(l["right"]).upper(), int(l["strike"]), int(l["qty"])
                        except (KeyError, TypeError, ValueError):
                            return self._json({"error": "each leg needs right, strike, qty"}, 400)
                        side = book._side(chain, strike, right)
                        if right not in ("CE", "PE") or qty == 0 or not side or side.get("ltp") is None:
                            return self._json({"error": f"{strike} {right} is not priced on the chain yet"}, 400)
                        legs.append({"right": right, "strike": strike, "qty": qty})
                        entries.append(float(l.get("price") or side["ltp"]))
                    if not legs:
                        return self._json({"error": "no legs"}, 400)
                    try:
                        pid = BOOK.open(user["id"], ukey, chain["expiry"], legs, lots, entries, chain["lot"], str(body.get("note", "")))
                    except ValueError as exc:
                        return self._json({"error": str(exc)}, 400)
                    return self._json({"ok": True, "id": pid})
                try:
                    pid = int(body.get("id"))
                except (TypeError, ValueError):
                    return self._json({"error": "bad id"}, 400)
                if route == "/api/book/delete":
                    return self._json({"ok": BOOK.delete(user["id"], pid)})
                pos = next((p for p in BOOK.open_positions(user["id"]) if p["id"] == pid), None)
                if pos is None:
                    return self._json({"error": "not found"}, 404)
                chain = CHAINS.chain(pos["u"], int(pos["expiry"]))
                m = book.mark(pos, chain if "rows" in chain else {})
                exits = [l["mark"] for l in m["legs"]]
                return self._json({"ok": BOOK.close(user["id"], pid, exits), "pnl": m["pnl"] if m["priced"] else None})
            if route in ("/api/broker/disconnect", "/api/broker/order", "/api/broker/cancel"):
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                if self.headers.get("X-Requested-With") != "fetch":
                    return self._json({"error": "bad request"}, 400)
                if not _paid(user):
                    return self._json({"error": "plan required", "need": "desk"}, 402)
                try:
                    body = json.loads(self._read_body().decode("utf-8") or "{}")
                except ValueError:
                    return self._json({"error": "invalid json"}, 400)
                if route == "/api/broker/disconnect":
                    BROKERS.disconnect(user["id"], str(body.get("broker", "upstox")))
                    _BROKER_CACHE.pop(user["id"], None)
                    return self._json({"ok": True})
                client, acc = _broker_client(user)
                if client is None:
                    return self._json(acc, 409)
                if route == "/api/broker/cancel":
                    try:
                        return self._json({"ok": True, "data": client.cancel(str(body.get("order_id", "")))})
                    except broker.BrokerError as exc:
                        return self._json({"error": str(exc)}, 502)
                # place a builder strategy
                if not broker.trade_allowed(user["email"]):
                    return self._json({"error": "Order routing is not open to your account yet (positions and funds are). It switches on once Finostat is empanelled with Upstox."}, 403)
                if body.get("confirm") is not True:
                    return self._json({"error": "confirm the ticket first"}, 400)
                ukey = str(body.get("u", ""))
                ok, err = _gate(user, ukey)
                if not ok:
                    return self._json(err, 403)
                r = CHAINS.resolve(ukey)
                if r is None:
                    return self._json({"error": "unknown underlying"}, 400)
                name = r[0]
                try:
                    expiry = int(body.get("expiry") or 0)
                except (TypeError, ValueError):
                    expiry = 0
                if expiry not in CONTRACTS_OF(FEED).expiries(name):
                    return self._json({"error": "pick a live expiry"}, 400)
                lots = int(body.get("lots") or 1)
                product, otype = str(body.get("product", "D")).upper(), str(body.get("order_type", "MARKET")).upper()
                tag = f"fino{user['id']}"[:20]
                try:
                    plan = broker.plan_orders(list(body.get("legs") or []), lambda right, k: CONTRACTS_OF(FEED).key_for(name, expiry, k, right),
                                              lots, product, otype, tag)
                except (broker.BrokerError, ValueError, TypeError) as exc:
                    return self._json({"error": str(exc)}, 400)
                results = broker.execute(client, plan)
                BROKERS.record_order(user["id"], "upstox", body.get("legs"), results, tag)
                _BROKER_CACHE.pop(user["id"], None)
                log.info("broker order: user %s %s lots=%d %s -> %s", user["id"], ukey, lots, [p["leg"] for p in plan], results)
                return self._json({"ok": all(x["ok"] for x in results), "results": results, "sent": len(results), "planned": len(plan)})
            if route == "/api/pay/order":
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                if self.headers.get("X-Requested-With") != "fetch":
                    return self._json({"error": "bad request"}, 400)
                if not payments.any_configured():
                    return self._json({"error": "online payment is not switched on yet"}, 503)
                try:
                    body = json.loads(self._read_body().decode("utf-8"))
                except ValueError:
                    return self._json({"error": "invalid json"}, 400)
                plan, period = str(body.get("plan", "")), str(body.get("period", "monthly"))
                enabled = [p["id"] for p in payments.providers() if p["configured"]]
                provider = str(body.get("provider") or (enabled[0] if enabled else ""))
                if provider not in enabled:
                    return self._json({"error": "that payment option is not available"}, 400)
                try:
                    if provider == "cashfree":
                        phone = assessment.clean_phone(str(body.get("phone", ""))) or (AUTH.get_prefs(user["id"]).get("phone") or "")
                        if not phone:
                            return self._json({"error": "Enter a 10-digit Indian mobile number for Cashfree", "need_phone": True}, 400)
                        AUTH.set_prefs(user["id"], {"phone": phone})
                        order = PAYMENTS.create_cashfree(user, plan, period, phone)
                    else:
                        order = PAYMENTS.create(user, plan, period)
                except payments.PaymentError as exc:
                    return self._json({"error": str(exc)}, 502)
                return self._json(order)
            if route == "/api/pay/verify":
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                if self.headers.get("X-Requested-With") != "fetch":
                    return self._json({"error": "bad request"}, 400)
                try:
                    body = json.loads(self._read_body().decode("utf-8"))
                except ValueError:
                    return self._json({"error": "invalid json"}, 400)
                oid, pid, sig = (str(body.get(k, "")) for k in ("order_id", "payment_id", "signature"))
                row = PAYMENTS.get(oid)
                if row is None or row["user_id"] != user["id"]:
                    return self._json({"error": "unknown order"}, 404)
                if row.get("provider") == "cashfree":
                    if row["status"] != "paid":
                        try:
                            pid = PAYMENTS.confirm_cashfree(oid)
                        except payments.PaymentError as exc:
                            return self._json({"error": str(exc)}, 502)
                        if not pid:
                            return self._json({"error": "Cashfree has not confirmed this payment yet. If money was debited it will be activated automatically within a minute — refresh.", "pending": True}, 409)
                    else:
                        pid = row["payment_id"]
                elif not payments.verify_payment_signature(oid, pid, sig):
                    log.warning("payment signature mismatch for order %s (user %s)", oid, user["id"])
                    return self._json({"error": "signature mismatch"}, 400)
                grant = _grant_and_notify(oid, pid, "verify")
                st = AUTH.plan_status(user["id"])
                return self._json({"ok": True, "plan": st["plan"], "until": st["until"], "already": grant is None})
            if route == "/api/pay/cashfree/webhook":
                raw = self._read_body(limit=256 * 1024)
                if not payments.verify_cashfree_webhook(raw, self.headers.get("x-webhook-timestamp", ""), self.headers.get("x-webhook-signature", "")):
                    log.warning("cashfree webhook: BAD signature (%d bytes, ts=%s, ip=%s)", len(raw), self.headers.get("x-webhook-timestamp", "-"), self._client_ip())
                    return self._json({"error": "bad signature"}, 400)
                try:
                    evt = json.loads(raw.decode("utf-8"))
                except ValueError:
                    return self._json({"error": "invalid json"}, 400)
                data = evt.get("data") or {}
                oid = ((data.get("order") or {}).get("order_id"))
                pay = data.get("payment") or {}
                log.info("cashfree webhook: signature ok, type=%s order=%s status=%s known=%s", evt.get("type"), oid, pay.get("payment_status"), bool(oid and PAYMENTS.get(oid)))
                if evt.get("type") == "PAYMENT_SUCCESS_WEBHOOK" and str(pay.get("payment_status", "")).upper() == "SUCCESS" and oid and PAYMENTS.get(oid):
                    _grant_and_notify(oid, str(pay.get("cf_payment_id") or "cf"), "webhook")
                return self._json({"ok": True})
            if route == "/api/pay/webhook":
                raw = self._read_body(limit=256 * 1024)
                if not payments.verify_webhook_signature(raw, self.headers.get("X-Razorpay-Signature", "")):
                    log.warning("razorpay webhook: BAD signature (%d bytes, ip=%s)", len(raw), self._client_ip())
                    return self._json({"error": "bad signature"}, 400)
                log.info("razorpay webhook: signature ok (%d bytes)", len(raw))
                try:
                    evt = json.loads(raw.decode("utf-8"))
                except ValueError:
                    return self._json({"error": "invalid json"}, 400)
                kind = evt.get("event", "")
                pay = ((evt.get("payload") or {}).get("payment") or {}).get("entity") or {}
                oid, pid = pay.get("order_id"), pay.get("id")
                if kind in ("payment.captured", "order.paid") and oid and pid and PAYMENTS.get(oid):
                    _grant_and_notify(oid, pid, "webhook")
                return self._json({"ok": True})
            if route == "/api/assessment":
                if self.headers.get("X-Requested-With") != "fetch":
                    return self._json({"error": "bad request"}, 400)
                try:
                    body = json.loads(self._read_body().decode("utf-8"))
                except ValueError:
                    return self._json({"error": "invalid json"}, 400)
                result, err, status = ASSESS.submit(body, self._client_ip())
                if err:
                    return self._json({"error": err}, status)
                answers, _ = assessment.validate(body)
                threading.Thread(target=mailer.send_owner_note,
                                 args=(f"Trader assessment: {answers['name']} — {result['profile']} {result['score']}/{result['total']}",
                                       assessment.owner_lines(answers, result)), daemon=True).start()
                return self._json(result)
            if route == "/api/assessment/quote":
                if self.headers.get("X-Requested-With") != "fetch":
                    return self._json({"error": "bad request"}, 400)
                try:
                    body = json.loads(self._read_body().decode("utf-8"))
                except ValueError:
                    return self._json({"error": "invalid json"}, 400)
                try:
                    aid = int(body.get("id"))
                except (TypeError, ValueError):
                    return self._json({"error": "Not found"}, 404)
                q, err = ASSESS.add_quote(aid, str(body.get("token", "")), str(body.get("quote", "")), bool(body.get("allow")))
                if err:
                    return self._json({"error": err}, 404 if err == "Not found" else 400)
                threading.Thread(target=mailer.send_owner_note,
                                 args=(f"Finostat quote from {q['name']}" + (" (OK to publish)" if q["allow"] else " (private)"),
                                       [f"{q['name']} <{q['email']}> wrote:", "", f"“{q['quote']}”", "",
                                        "Quotable on the homepage: " + ("YES — first name + city only" if q["allow"] else "NO — private feedback"),
                                        "All quotes:  fly ssh console --app finostat -C \"python3 /app/server/admin.py quotes\""]), daemon=True).start()
                return self._json({"ok": True})
            if route == "/auth/upgrade":
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                if self.headers.get("X-Requested-With") != "fetch":
                    return self._json({"error": "bad request"}, 400)
                try:
                    body = json.loads(self._read_body().decode("utf-8"))
                except ValueError:
                    body = {}
                plan = str(body.get("plan", "desk")).lower()
                rid = AUTH.request_upgrade(user["id"], plan, str(body.get("note", ""))[:500])
                if rid is None:
                    return self._json({"error": "invalid plan or too many requests"}, 429)
                mailer.send_owner_note(
                    f"Finostat upgrade request: {user['email']} -> {plan}",
                    [f"{user['email']} (currently {user.get('plan','starter')}) requested the {plan} plan.",
                     f"Note: {body.get('note') or '-'}",
                     f"Grant it with:  fly ssh console --app finostat -C \"python3 /app/server/admin.py set-plan {user['email']} {plan}\""])
                return self._json({"ok": True, "request": rid})
            if route == "/api/me/prefs":
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                # A custom header is not sendable by a plain HTML form, which is
                # what makes this a CSRF gate on top of SameSite cookies.
                if self.headers.get("X-Requested-With") != "fetch":
                    return self._json({"error": "bad request"}, 400)
                try:
                    updates = json.loads(self._read_body().decode("utf-8"))
                except ValueError:
                    return self._json({"error": "invalid json"}, 400)
                if not isinstance(updates, dict):
                    return self._json({"error": "expected an object"}, 400)
                AUTH.set_prefs(user["id"], updates)
                return self._json({"ok": True})
            return self._json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            log.exception("error handling POST %s", self.path)
            try:
                self._json({"error": "internal"}, 500)
            except OSError:
                pass

    # -- server sent events -------------------------------------------------
    def _stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")  # so nginx does not buffer it
        self.end_headers()

        q = NEWS.subscribe()
        try:
            backlog = NEWS.latest(40)
            if backlog:
                self.wfile.write(b"event: news\ndata: " + _json_safe(backlog) + b"\n\n")
                self.wfile.flush()
            while True:
                try:
                    items = q.get(timeout=20)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")  # keep proxies from timing out
                    self.wfile.flush()
                    continue
                self.wfile.write(b"event: news\ndata: " + _json_safe(items) + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            NEWS.unsubscribe(q)

    def _sheet_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        q = SHEETS.subscribe()
        try:
            snap = FEED.snapshot()
            SHEETS.publish(snap)          # send the current state immediately
            while True:
                try:
                    payload = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                self.wfile.write(b"event: sheet\ndata: " + _json_safe(payload) + b"\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            SHEETS.unsubscribe(q)

    # -- files and unbuilt routes ------------------------------------------
    def _static(self, route: str):
        rel = route.lstrip("/")
        parts = [p for p in rel.split("/") if p]
        # Never serve dotfiles, source directories, or the html backups.
        if (not parts
                or any(p.startswith(".") for p in parts)
                or any(p.lower() in STATIC_DENY_DIRS for p in parts[:-1])
                or parts[-1].lower() in STATIC_DENY_DIRS):
            return self._not_built(route)

        root = config.STATIC_ROOT.resolve()
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            return self._send(b"Forbidden", "text/plain; charset=utf-8", 403)
        if candidate.suffix.lower() not in STATIC_SUFFIXES:
            return self._not_built(route)
        if not candidate.is_file():
            return self._not_built(route)
        ctype = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        return self._send(candidate.read_bytes(), ctype, cache="public, max-age=3600")

    def _not_built(self, route: str):
        title = KNOWN_ROUTES.get(route)
        if not title and route.startswith(KNOWN_PREFIXES):
            title = route.rsplit("/", 1)[-1].replace("-", " ").capitalize()
        known = bool(title)
        title = title or "Page not found"
        note = ("This page is linked from the site but has not been built yet."
                if known else "That route does not exist.")
        body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — Finostat</title>
<style>
:root{{color-scheme:dark}}
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#0c0626;
color:#f1edff;font:15px/1.5 "IBM Plex Sans",system-ui,sans-serif;text-align:center;padding:24px}}
.k{{font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:11.5px;letter-spacing:.16em;
text-transform:uppercase;color:#f5c842}}
h1{{font-family:"Barlow Condensed",Impact,sans-serif;font-weight:600;font-size:clamp(38px,7vw,64px);
line-height:1;text-transform:uppercase;margin:14px 0 12px}}
p{{color:#a89ccf;max-width:46ch;margin:0 auto}}
a{{display:inline-block;margin-top:26px;padding:12px 20px;border:1px solid #4a34a0;color:#f1edff;
text-decoration:none;font-family:"IBM Plex Mono",ui-monospace,monospace;font-size:12px;
letter-spacing:.08em;text-transform:uppercase}}
a:hover{{border-color:#f5c842;color:#f5c842}}
</style></head><body><div>
<span class="k">{'HTTP 404 · not built' if known else 'HTTP 404'}</span>
<h1>{html.escape(title)}</h1><p>{note}</p><a href="/">← Back to Finostat</a>
</div></body></html>"""
        self._send(body.encode("utf-8"), "text/html; charset=utf-8", 404)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main() -> int:
    FEED.add_listener(SHEETS.publish)
    FEED.add_listener(RECORDER.on_snapshot)
    FEED.add_listener(ALERTS.on_snapshot)
    RECORDER.start()
    ALERTS.start()
    BACKUP.start()
    CONSTITUENTS.start()
    CHAINS.start()
    BRIEF.start()
    RENEWALS.start()
    VIDEOS.start()
    CAS.start()
    EVENTS.start()
    HOLIDAYS.start()
    ECON.start()
    FEED.start()
    NEWS.start()
    server = Server((config.HOST, config.PORT), Handler)

    def shutdown(*_a):
        log.info("shutting down")
        FEED.stop()
        NEWS.stop()
        RECORDER.stop()
        ALERTS.stop()
        BACKUP.stop()
        CONSTITUENTS.stop()
        CHAINS.stop()
        BRIEF.stop()
        RENEWALS.stop()
        VIDEOS.stop()
        CAS.stop()
        CAS.flush()
        EVENTS.stop()
        ECON.stop()
        HOLIDAYS.stop()
        # A consistent copy first, then fold the WAL: whatever happens to the
        # live file during the machine stop, the next boot can restore this.
        BACKUP.run_now()
        AUTH.checkpoint()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    snap = FEED.snapshot()
    log.info("feed=%s live=%s", FEED.name, snap.get("live"))
    if snap.get("error"):
        log.warning("feed error: %s", snap["error"])
    log.info("serving http://%s:%d", config.HOST, config.PORT)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
