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
import news
import auth as authmod
import mailer
import pages
import recorder
import strategies

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
PUBLIC_URL = os.environ.get("FINOSTAT_PUBLIC_URL", "").strip().rstrip("/")

# Routes the marketing page links to that are not built yet. They get an
# on-brand 404 instead of a stack trace, so a stray click never looks broken.
KNOWN_ROUTES = {
    "/analysis": "Analysis tools", "/live-session": "Book a live session",
    "/learn": "Learn", "/blog": "Blog", "/about": "About", "/founders": "Founders",
    "/contact": "Contact", "/terms": "Terms of service", "/privacy": "Privacy policy",
}
KNOWN_PREFIXES = ("/tools/", "/strategies/", "/learn/")

# Static serving is an ALLOWLIST, not "anything under the project root".
# The root contains server/ -- which will contain .env with the Kite api_secret
# once it is configured. Serving the tree wholesale would publish it.
STATIC_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".avif",
    ".css", ".js", ".map", ".txt", ".xml", ".json", ".webmanifest",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".pdf", ".mp4", ".webm",
}
STATIC_DENY_DIRS = {"server", "deploy", "tests", "node_modules", "__pycache__"}


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
                return self._send(pages.render_dashboard(FEED.snapshot()),
                                  "text/html; charset=utf-8")
            if route in ("/login", "/signup"):
                state = parse_qs(parsed.query).get("state", ["form"])[0]
                return self._send(pages.render_login(state, mailer.configured()),
                                  "text/html; charset=utf-8", cache="no-store")
            if route == "/auth/verify":
                token = parse_qs(parsed.query).get("token", [""])[0]
                uid = AUTH.redeem_link(token)
                if uid is None:
                    return self._redirect("/login?state=expired")
                sid = AUTH.create_session(uid)
                return self._redirect("/dashboard",
                                      [("Set-Cookie", authmod.Auth.cookie_header(sid, self._secure()))])
            if route == "/api/me":
                user = self._current_user()
                if user is None:
                    return self._json({"error": "not signed in"}, 401)
                return self._json({"email": user["email"], "prefs": AUTH.get_prefs(user["id"])})
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
                                   "auth": {"smtp_configured": mailer.configured()},
                                   "time": time.time()})
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
                link = f"{self._base_url()}/auth/verify?token={quote(token, safe='')}"
                if not mailer.send_magic_link(email, link):
                    return self._redirect("/login?state=failed")
                return self._redirect("/login?state=sent")
            if route == "/auth/logout":
                sid = authmod.Auth.sid_from_cookie_header(self.headers.get("Cookie"))
                AUTH.destroy_session(sid)
                return self._redirect("/", [("Set-Cookie", authmod.Auth.clear_cookie_header(self._secure()))])
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
    RECORDER.start()
    FEED.start()
    NEWS.start()
    server = Server((config.HOST, config.PORT), Handler)

    def shutdown(*_a):
        log.info("shutting down")
        FEED.stop()
        NEWS.stop()
        RECORDER.stop()
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
