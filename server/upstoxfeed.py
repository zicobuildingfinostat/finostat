"""Upstox Market Data Feed V3.

Chosen over Kite for two reasons that matter in production:

  * the **Analytics Token is valid for a year**, so the site does not go dark
    every morning waiting for someone to re-run a browser login, and
  * the **instrument master needs no authentication at all**, so strike and
    expiry resolution works before a single credential is configured.

The feed is protobuf over a WebSocket. `miniproto` decodes it and `wsclient`
carries it; neither needs a third-party package.
"""
from __future__ import annotations

import gzip
import json
import logging
import threading
import time
import urllib.error
import urllib.request
from datetime import date, datetime

import config
import miniproto as mp
import sheets
import wsclient
from feeds import TAPE, Feed

log = logging.getLogger("finostat.upstox")

INSTRUMENTS = {
    "NSE": "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz",
    "BSE": "https://assets.upstox.com/market-quote/instruments/exchange/BSE.json.gz",
    "MCX": "https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz",
}

FEED_URL = "wss://api.upstox.com/v3/feed/market-data-feed"
AUTHORIZE_URL = "https://api.upstox.com/v3/feed/market-data-feed/authorize"

# Cloudflare fronts the Upstox API and blocks requests with no User-Agent.
USER_AGENT = "Finostat/1.0 (+https://finostat.com)"

# Tape label -> Upstox instrument_key. Resolved from the instrument master, so
# these are the documented keys rather than guesses.
TAPE_KEYS = {
    "NIFTY 50": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
    "SENSEX": "BSE_INDEX|SENSEX",
    "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
    "INDIA VIX": "NSE_INDEX|India VIX",
}

# Underlying -> (spot instrument_key, option `name` in the master, strike step)
UNDERLYINGS = {
    "NIFTY":     ("NSE_INDEX|Nifty 50", "NIFTY", "NSE", 50),
    "BANKNIFTY": ("NSE_INDEX|Nifty Bank", "BANKNIFTY", "NSE", 100),
    "FINNIFTY":  ("NSE_INDEX|Nifty Fin Service", "FINNIFTY", "NSE", 50),
    "SENSEX":    ("BSE_INDEX|SENSEX", "SENSEX", "BSE", 100),
}

# Feed.ltpc = 1 ; LTPC.ltp = 1, LTPC.cp = 4 ; FeedResponse.feeds = 2
F_FEEDS, F_LTPC, F_LTP, F_CP = 2, 1, 1, 4
F_FULLFEED, F_MARKETFF, F_INDEXFF = 2, 1, 2


class UpstoxError(RuntimeError):
    pass


class UpstoxFeed(Feed):
    name = "upstox"

    PUBLISH_INTERVAL = 0.12
    BACKOFF_MAX = 30.0

    @property
    def interval(self) -> float:
        """Pushed, not polled -- report how often snapshots are republished."""
        return self.PUBLISH_INTERVAL

    def __init__(self) -> None:
        super().__init__()
        if not config.UPSTOX_ACCESS_TOKEN:
            raise UpstoxError(
                "UPSTOX_ACCESS_TOKEN is not set. Generate an Analytics Token at "
                "https://account.upstox.com/developer/apps (valid one year) and put "
                "it in server/.env"
            )
        self._master: dict[str, list[dict]] = {}
        self._master_day: date | None = None
        self._prices: dict[str, float] = {}
        self._closes: dict[str, float] = {}
        self._meta: dict[str, dict] = {}
        self._spot_key: str | None = None
        self._ws: wsclient.WebSocket | None = None
        self._dirty = threading.Event()
        self._ticks = 0
        self._stop_extra = threading.Event()
        self._uni_dirty = True
        self._universe_cache: dict = {}
        self._members_seen: set | None = None

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="upstox", daemon=True)
        self._thread.start()
        threading.Thread(target=self._publisher, name="upstox-publish", daemon=True).start()

    def stop(self) -> None:
        super().stop()
        self._dirty.set()
        if self._ws is not None:
            self._ws.close()

    def refresh(self) -> None:
        """Pushed, not polled."""

    # -- instrument master --------------------------------------------------
    def _instruments(self, exchange: str) -> list[dict]:
        today = date.today()
        if self._master_day != today:
            self._master.clear()
            self._master_day = today
        if exchange in self._master:
            return self._master[exchange]
        url = INSTRUMENTS.get(exchange)
        if not url:
            raise UpstoxError(f"no instrument master for {exchange}")
        log.info("downloading %s instrument master", exchange)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=90) as resp:
                rows = json.loads(gzip.decompress(resp.read()).decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise UpstoxError(f"instrument master download failed: {exc}") from exc
        self._master[exchange] = rows
        log.info("%s: %d instruments", exchange, len(rows))
        return rows

    def _nearest_expiry(self, rows: list[dict], name: str) -> int | None:
        """Expiries are epoch milliseconds in the master file."""
        now = time.time() * 1000
        future = sorted({r["expiry"] for r in rows
                         if r.get("name") == name
                         and r.get("instrument_type") in ("CE", "PE")
                         and r.get("expiry")
                         and r["expiry"] >= now})
        return future[0] if future else None

    # -- resolution ---------------------------------------------------------
    def _resolve(self) -> list[str]:
        sym = config.SHEET_SYMBOL
        if sym not in UNDERLYINGS:
            raise UpstoxError(f"unsupported FINOSTAT_SYMBOL={sym}")
        spot_key, opt_name, exchange, step = UNDERLYINGS[sym]

        self._meta.clear()
        self._prices.clear()
        self._closes.clear()

        for label, key in TAPE_KEYS.items():
            self._meta[key] = {"kind": "tape", "label": label}
        self._spot_key = spot_key
        self._meta.setdefault(spot_key, {"kind": "tape", "label": sym})

        rows = self._instruments(exchange)
        expiry = self._nearest_expiry(rows, opt_name)
        if expiry is None:
            raise UpstoxError(f"no live expiry for {opt_name} on {exchange}")
        log.info("ticker: %s expiry %s", opt_name,
                 datetime.fromtimestamp(expiry / 1000).date())

        contracts = [r for r in rows
                     if r.get("name") == opt_name
                     and r.get("instrument_type") in ("CE", "PE")
                     and r.get("expiry") == expiry
                     and r.get("strike_price")]
        if not contracts:
            raise UpstoxError(f"no {opt_name} contracts for that expiry")

        # Without a spot price yet, keep every strike in a sane band around the
        # densest part of the chain and narrow once the first tick lands.
        strikes = sorted({int(r["strike_price"]) for r in contracts})
        middle = strikes[len(strikes) // 2]
        span = (config.SHEET_ROWS // 2) * step + config.SHEET_WING + 4 * step
        for row in contracts:
            strike = int(row["strike_price"])
            if abs(strike - middle) > span * 3:
                continue
            self._meta[row["instrument_key"]] = {
                "kind": "option", "strike": strike, "right": row["instrument_type"],
            }

        count = sum(1 for m in self._meta.values() if m["kind"] == "option")
        stocks = self._resolve_universe()
        log.info("ticker: subscribing to %d instruments (%d options, %d stocks)",
                 len(self._meta), count, stocks)
        return list(self._meta)

    BSE_GROUPS = {"A", "B", "T", "X", "XT", "EQ"}   # tradable equity groups; F/G are debt

    def _resolve_universe(self) -> int:
        """Every NSE equity (and BSE equity when configured), flagged F&O when a
        futures contract exists on the company."""
        if config.UNIVERSE == "none":
            return 0
        rows = self._instruments("NSE")
        fo = {r.get("underlying_symbol") or r.get("name") for r in rows
              if r.get("segment") == "NSE_FO" and r.get("instrument_type") == "FUT"}
        fo_isin = set()
        n = 0
        for r in rows:
            if r.get("segment") != "NSE_EQ" or r.get("instrument_type") != "EQ":
                continue
            sym = r.get("trading_symbol") or ""
            key = r.get("instrument_key")
            if not sym or not key or key in self._meta:
                continue
            is_fo = sym in fo
            if is_fo and r.get("isin"):
                fo_isin.add(r["isin"])
            self._meta[key] = {"kind": "stock", "label": "NSE:" + sym, "symbol": sym,
                               "exchange": "NSE", "name": r.get("name", ""), "fo": is_fo}
            n += 1
        if "bse" in config.UNIVERSE:
            for r in self._instruments("BSE"):
                if r.get("segment") != "BSE_EQ" or r.get("instrument_type") not in self.BSE_GROUPS:
                    continue
                sym = r.get("trading_symbol") or ""
                key = r.get("instrument_key")
                if not sym or not key or key in self._meta:
                    continue
                self._meta[key] = {"kind": "stock", "label": "BSE:" + sym, "symbol": sym,
                                   "exchange": "BSE", "name": r.get("name", ""),
                                   "fo": r.get("isin") in fo_isin}
                n += 1
        # The masters are ~90 MB of parsed JSON; on a 512 MB machine that is
        # the single biggest resident. They are re-downloaded on the next
        # resolve, which only happens on reconnect.
        self._master.clear()
        self._master_day = None
        self._uni_dirty = True
        return n

    # -- socket -------------------------------------------------------------
    def _authorized_url(self) -> str:
        """Ask for the signed feed endpoint; fall back to the documented URL."""
        # Upstox sits behind Cloudflare, which answers a missing User-Agent with
        # error 1010 -- a 403 that looks exactly like a rejected token but is not.
        req = urllib.request.Request(AUTHORIZE_URL, headers={
            "Authorization": f"Bearer {config.UPSTOX_ACCESS_TOKEN}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code in (401, 403):
                raise UpstoxError(
                    f"Upstox rejected the token ({exc.code}). An Analytics Token lasts a "
                    f"year but can be revoked or regenerated. {detail}"
                ) from exc
            log.warning("authorize endpoint returned %s; using the default feed url", exc.code)
            return FEED_URL
        except (urllib.error.URLError, ValueError) as exc:
            log.warning("authorize endpoint unreachable (%s); using the default feed url", exc)
            return FEED_URL
        uri = (payload.get("data") or {}).get("authorized_redirect_uri") or (payload.get("data") or {}).get("authorizedRedirectUri")
        return uri or FEED_URL

    SOCKET_CAP = 4500   # Upstox allows 5,000 LTPC instruments per socket; keep headroom

    def _run(self) -> None:
        """Supervisor. Resolves instruments, then opens as many sockets as the
        key count needs: the first in this thread, the rest in helpers that
        follow it down so every reconnect re-resolves the whole universe."""
        backoff = 1.0
        while not self._stop.is_set():
            self._stop_extra = threading.Event()
            try:
                keys = self._resolve()
                groups = [keys[i:i + self.SOCKET_CAP] for i in range(0, len(keys), self.SOCKET_CAP)]
                log.info("%d instruments across %d socket(s)", len(keys), len(groups))
                for n, group in enumerate(groups[1:], start=2):
                    threading.Thread(target=self._socket_loop, args=(n, group),
                                     name=f"upstox-{n}", daemon=True).start()
                ws = self._open(1, groups[0])
                self._ws = ws
                backoff = 1.0
                self._read_loop(ws, 1)
            except UpstoxError as exc:
                log.error("%s", exc)
                self._publish(live=False, error=str(exc))
            except wsclient.WebSocketClosed as exc:
                log.warning("feed closed (%s)", exc)
                self._publish(live=False, error=f"stream closed: {exc}")
            except Exception as exc:
                log.exception("unexpected feed failure")
                self._publish(live=False, error=str(exc))
            finally:
                self._stop_extra.set()
                if self._ws is not None:
                    self._ws.close()
                    self._ws = None
            if self._stop.is_set():
                break
            log.info("reconnecting in %.0fs", backoff)
            self._stop.wait(backoff)
            backoff = min(self.BACKOFF_MAX, backoff * 2)

    def _socket_loop(self, n: int, keys: list[str]) -> None:
        """Reconnect loop for an additional socket; lives until the primary restarts."""
        backoff = 1.0
        stop_extra = self._stop_extra
        while not self._stop.is_set() and not stop_extra.is_set():
            ws = None
            try:
                ws = self._open(n, keys)
                backoff = 1.0
                self._read_loop(ws, n, stop_extra)
            except (UpstoxError, wsclient.WebSocketError, OSError) as exc:
                log.warning("socket %d: %s", n, exc)
            except Exception:
                log.exception("socket %d: unexpected failure", n)
            finally:
                if ws is not None:
                    ws.close()
            if self._stop.is_set() or stop_extra.is_set():
                break
            self._stop.wait(backoff)
            backoff = min(self.BACKOFF_MAX, backoff * 2)

    def _open(self, n: int, keys: list[str]) -> wsclient.WebSocket:
        url = self._authorized_url()
        log.info("socket %d: connecting (%d instruments)", n, len(keys))
        ws = wsclient.connect(url, headers={
            "Authorization": f"Bearer {config.UPSTOX_ACCESS_TOKEN}",
            "Accept": "*/*",
            "User-Agent": USER_AGENT,
        }, timeout=20.0)
        # Read timeout must exceed Upstox's quiet gaps, or an idle market tears
        # down a healthy socket.
        ws.settimeout(60.0)
        # The subscribe payload is JSON, but must go in a *binary* frame.
        # ltpc mode carries last price and close, which is all the sheet needs.
        for i in range(0, len(keys), 1000):
            ws.send_binary(json.dumps({
                "guid": f"finostat-{n}-{int(time.time())}-{i // 1000}",
                "method": "sub",
                "data": {"mode": "ltpc", "instrumentKeys": keys[i:i + 1000]},
            }).encode("utf-8"))
        log.info("socket %d: subscribed to %d instruments in ltpc mode", n, len(keys))
        return ws

    def _read_loop(self, ws: wsclient.WebSocket, n: int, stop_extra=None) -> None:
        while not self._stop.is_set() and not (stop_extra is not None and stop_extra.is_set()):
            kind, payload = ws.recv()
            if kind == "text":
                log.debug("socket %d text frame: %s", n, payload[:200])
                continue
            try:
                self._ingest(payload)
            except mp.ProtoError as exc:
                log.warning("socket %d: undecodable frame: %s", n, exc)

    @staticmethod
    def _ltp_and_close(feed: dict) -> tuple[float | None, float | None]:
        """Pull last price and close out of a Feed, whichever variant it is."""
        ltpc = mp.as_message(feed, F_LTPC)
        if ltpc is None:
            full = mp.as_message(feed, F_FULLFEED)
            if full is not None:
                inner = mp.as_message(full, F_MARKETFF) or mp.as_message(full, F_INDEXFF)
                if inner is not None:
                    ltpc = mp.as_message(inner, F_LTPC)
        if ltpc is None:
            return None, None
        return mp.as_double(ltpc, F_LTP), mp.as_double(ltpc, F_CP)

    def _ingest(self, payload: bytes) -> None:
        response = mp.decode(payload)
        feeds = mp.as_map(response, F_FEEDS)
        if not feeds:
            return
        for key, feed in feeds.items():
            meta = self._meta.get(key)
            if meta is None:
                continue
            ltp, close = self._ltp_and_close(feed)
            if ltp is not None and ltp > 0:
                self._prices[key] = ltp
                if meta["kind"] == "stock":
                    self._uni_dirty = True
            if close:
                self._closes[key] = close
        self._ticks += len(feeds)
        self._dirty.set()

    # -- publishing ---------------------------------------------------------
    def _publisher(self) -> None:
        while not self._stop.is_set():
            if not self._dirty.wait(1.0):
                continue
            self._dirty.clear()
            try:
                self._rebuild()
            except Exception:
                log.exception("rebuild failed")
            self._stop.wait(self.PUBLISH_INTERVAL)

    def _rebuild(self) -> None:
        spot = self._prices.get(self._spot_key or "")
        if not spot:
            return
        sym = config.SHEET_SYMBOL
        step = UNDERLYINGS[sym][3]

        chain = {}
        for key, meta in self._meta.items():
            if meta["kind"] != "option":
                continue
            price = self._prices.get(key)
            if price is not None:
                chain[(meta["strike"], meta["right"])] = price

        quotes = []
        for key, meta in self._meta.items():
            if meta["kind"] != "tape":
                continue
            price = self._prices.get(key)
            if price is None:
                continue
            close = self._closes.get(key)
            change = 0.0 if not close else (price - close) / close * 100.0
            quotes.append({"symbol": meta["label"], "price": round(price, 2),
                           "change": round(change, 2)})
        order = {label: i for i, (label, _spec) in enumerate(TAPE)}
        quotes.sort(key=lambda q: order.get(q["symbol"], 99))

        # A fresh dict each time something moved: readers on other threads
        # iterate the published one, so it must never be mutated after
        # publish. With ~7,000 names, rebuilding at 8 Hz when nothing changed
        # would be the single biggest CPU cost, hence the dirty flag.
        members = set(self.index_members())
        if members != self._members_seen:
            self._members_seen = members
            self._uni_dirty = True
        if self._uni_dirty:
            universe = {}
            for key, meta in self._meta.items():
                if meta["kind"] != "stock":
                    continue
                price = self._prices.get(key)
                if price is None:
                    continue
                close = self._closes.get(key)
                universe[meta["label"]] = {
                    "symbol": meta["symbol"], "exchange": meta["exchange"], "name": meta["name"],
                    "fo": meta["fo"], "n50": meta["exchange"] == "NSE" and meta["symbol"] in members,
                    "price": round(price, 2),
                    "change": round((price - close) / close * 100.0, 2) if close else 0.0,
                }
            self._universe_cache = universe
            self._uni_dirty = False
        universe = self._universe_cache

        self._publish(
            quotes=quotes,
            sheet={"rows": sheets.butterfly_rows(chain, spot, step,
                                                 config.SHEET_ROWS, config.SHEET_WING)},
            mini=sheets.mini_rows(chain, spot, step),
            straddle=sheets.straddle_price(chain, spot, step),
            symbol=sym, atm=sheets.atm_strike(spot, step),
            live=True, error=None, ticks=self._ticks, universe=universe,
        )
