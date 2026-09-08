"""Market data feeds.

Every feed produces the same `snapshot()` payload, so the HTTP layer never
knows or cares whether the numbers came from a broker or from the simulator.

A feed refreshes on its own background thread. Browsers poll the cached
snapshot, which means a hundred open tabs still cost the broker exactly one
request per interval -- important, because Kite's /quote endpoint allows
roughly one request per second in total, not per client.
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import math
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from socket import timeout as socket_timeout

import config
import kiteticker
import sheets
import wsclient

log = logging.getLogger("finostat.feeds")

# Tape rows. A spec is either a literal Kite instrument ("NSE:NIFTY 50") or a
# ("<EXCHANGE>", "<NAME>", "FUT") triple resolved to the nearest-expiry future.
TAPE = [
    ("NIFTY 50", "NSE:NIFTY 50"),
    ("BANKNIFTY", "NSE:NIFTY BANK"),
    ("SENSEX", "BSE:SENSEX"),
    ("FINNIFTY", "NSE:NIFTY FIN SERVICE"),
    ("INDIA VIX", "NSE:INDIA VIX"),
    ("GOLD", ("MCX", "GOLD", "FUT")),
    ("CRUDE", ("MCX", "CRUDEOIL", "FUT")),
    ("USDINR", ("CDS", "USDINR", "FUT")),
]

# Index spot instrument and option-root exchange, per underlying.
UNDERLYING = {
    "NIFTY":     {"spot": "NSE:NIFTY 50",          "opt_exchange": "NFO", "step": 50},
    "BANKNIFTY": {"spot": "NSE:NIFTY BANK",        "opt_exchange": "NFO", "step": 100},
    "FINNIFTY":  {"spot": "NSE:NIFTY FIN SERVICE", "opt_exchange": "NFO", "step": 50},
    "SENSEX":    {"spot": "BSE:SENSEX",            "opt_exchange": "BFO", "step": 100},
}


class Feed:
    """Interface every feed implements."""

    name = "base"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot: dict = {"quotes": [], "sheet": {"rows": []}, "mini": [],
                                "symbol": config.SHEET_SYMBOL, "atm": None,
                                "straddle": None, "live": False, "error": None,
                                "universe": {}}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._listeners: list = []
        # Set by the app to a callable returning the current Nifty 50 symbols,
        # so universe entries can carry an n50 flag that follows NSE's list.
        self.index_members = lambda: set()

    def add_listener(self, fn) -> None:
        """Called with each new snapshot -- used to push updates to browsers."""
        self._listeners.append(fn)

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        self.refresh()
        self._thread = threading.Thread(target=self._loop, name=f"feed-{self.name}", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    @property
    def interval(self) -> float:
        return config.POLL_INTERVAL

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.refresh()
            except Exception:
                log.exception("feed refresh failed")

    # -- data ---------------------------------------------------------------
    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._snapshot)

    def _publish(self, **fields) -> None:
        with self._lock:
            self._snapshot.update(fields)
            snap = dict(self._snapshot)
        for fn in list(self._listeners):   # outside the lock: listeners may block
            try:
                fn(snap)
            except Exception:
                log.exception("snapshot listener failed")

    def refresh(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    # -- hooks for on-demand option chains (chains.ChainManager) ------------
    def spot_of(self, key: str):
        """Last price for an index label or a universe key, from the snapshot."""
        snap = self.snapshot()
        for q in snap.get("quotes") or []:
            if q.get("symbol") == key:
                return q.get("price")
        e = (snap.get("universe") or {}).get(key)
        return e.get("price") if e else None

    def price_of(self, key: str):
        """(ltp, close) for a subscribed contract key; feeds that stream override."""
        return (None, None)

    def subscribe_dynamic(self, metas: dict) -> None:
        """Start streaming extra contract keys (meta per key). Overridden by live feeds."""

    def unsubscribe_dynamic(self, keys) -> None:
        pass


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------

def _bs(spot: float, strike: float, years: float, vol: float, right: str) -> float:
    """Black-Scholes with zero rates -- enough to keep a demo chain arbitrage free."""
    if years <= 0 or vol <= 0:
        intrinsic = spot - strike if right == "CE" else strike - spot
        return max(0.05, intrinsic)
    sd = vol * math.sqrt(years)
    d1 = (math.log(spot / strike) + 0.5 * sd * sd) / sd
    d2 = d1 - sd
    ncdf = lambda x: 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
    call = spot * ncdf(d1) - strike * ncdf(d2)
    value = call if right == "CE" else call - spot + strike
    return max(0.05, value)


class SimulatorFeed(Feed):
    """Self-consistent fake market. No credentials, no network, always available.

    Prices come from a Black-Scholes surface over a random-walking spot, so the
    butterflies behave the way real ones do instead of each cell jittering on
    its own.
    """

    name = "simulator"

    @property
    def interval(self) -> float:
        return config.SIM_INTERVAL

    # A handful of F&O names so the watchlist and stock alerts work offline.
    STOCKS = {"RELIANCE": ("RELIANCE INDUSTRIES LTD", 2905.4), "TCS": ("TATA CONSULTANCY SERV LT", 3512.7),
              "HDFCBANK": ("HDFC BANK LTD", 1687.2), "INFY": ("INFOSYS LIMITED", 1498.9),
              "ICICIBANK": ("ICICI BANK LTD.", 1182.6), "SBIN": ("STATE BANK OF INDIA", 789.3),
              "TATAMOTORS": ("TATA MOTORS LIMITED", 974.1), "BAJFINANCE": ("BAJAJ FINANCE LIMITED", 6840.5)}

    LEVELS = {
        "NIFTY 50": 24816.47, "BANKNIFTY": 54180.02, "SENSEX": 81418.97,
        "FINNIFTY": 26016.09, "INDIA VIX": 12.84, "GIFT NIFTY": 24859.96,
        "GOLD": 102469.38, "CRUDE": 6844.54, "USDINR": 87.41,
    }

    def __init__(self) -> None:
        super().__init__()
        self._spot = dict(self.LEVELS)
        self._open = dict(self.LEVELS)
        for sym, (_name, px) in self.STOCKS.items():
            self._spot["NSE:" + sym] = px
            self._open["NSE:" + sym] = px
        self._rng = random.Random(20260827)

    # per-tick volatility by instrument
    VOL = {"INDIA VIX": 0.005, "USDINR": 0.0004, "GOLD": 0.0008, "CRUDE": 0.0015}

    def _walk(self) -> None:
        for key, value in self._spot.items():
            anchor = self._open[key]
            vol = self.VOL.get(key, 0.0012)
            # Mean reverting, not a free random walk: left unanchored the spot
            # wanders arbitrarily far from a plausible level over a long session,
            # and the sheet starts quoting strikes that do not exist.
            pull = 0.02 * (anchor - value) / anchor
            self._spot[key] = max(0.01, value * (1.0 + pull + self._rng.gauss(0.0, vol)))

    def _chain(self, symbol: str, spot: float, step: int) -> dict:
        vol = max(0.06, self._spot["INDIA VIX"] / 100.0)
        years = max(1.0 / 365.0, 4.0 / 365.0)
        atm = sheets.atm_strike(spot, step)
        chain = {}
        for i in range(-14, 15):
            strike = atm + i * step
            if strike <= 0:
                continue
            # a mild smile: wings trade richer than the at-the-money
            skew = 1.0 + 0.35 * (abs(strike - spot) / max(spot, 1.0)) * 12.0
            for right in ("CE", "PE"):
                chain[(strike, right)] = round(_bs(spot, strike, years, vol * skew, right), 1)
        return chain

    def refresh(self) -> None:
        self._walk()
        quotes = []
        for label, _spec in TAPE:
            if label not in self._spot:
                continue
            price = self._spot[label]
            base = self._open[label]
            quotes.append({"symbol": label, "price": round(price, 2),
                           "change": round((price - base) / base * 100.0, 2)})

        sym = config.SHEET_SYMBOL
        spot_key = {"NIFTY": "NIFTY 50"}.get(sym, sym)
        spot = self._spot.get(spot_key, self._spot["NIFTY 50"])
        step = UNDERLYING.get(sym, {}).get("step", config.SHEET_STEP)
        chain = self._chain(sym, spot, step)

        mini_sym = config.MINI_SYMBOL
        mini_spot = self._spot.get({"NIFTY": "NIFTY 50"}.get(mini_sym, mini_sym), spot)
        mini_step = UNDERLYING.get(mini_sym, {}).get("step", config.MINI_STEP)
        mini_chain = self._chain(mini_sym, mini_spot, mini_step)

        universe = {}
        members = set(self.index_members())
        for s, (name, _px) in self.STOCKS.items():
            key = "NSE:" + s
            price, base = self._spot[key], self._open[key]
            universe[key] = {"symbol": s, "exchange": "NSE", "name": name, "fo": True, "n50": s in members,
                             "price": round(price, 2), "change": round((price - base) / base * 100.0, 2)}
        self._publish(
            quotes=quotes,
            sheet={"rows": sheets.butterfly_rows(chain, spot, step, config.SHEET_ROWS, config.SHEET_WING)},
            mini=sheets.mini_rows(mini_chain, mini_spot, mini_step),
            straddle=sheets.straddle_price(chain, spot, step),
            symbol=sym, atm=sheets.atm_strike(spot, step),
            live=False, error=None, universe=universe,
        )


# ---------------------------------------------------------------------------
# Zerodha Kite Connect
# ---------------------------------------------------------------------------

class KiteError(RuntimeError):
    pass


class KiteFeed(Feed):
    """Live data over Kite Connect's REST quote endpoint.

    Credentials come from the environment and never leave this process -- the
    browser only ever sees derived prices, never the api_key or access_token.
    """

    name = "kite"

    def __init__(self) -> None:
        super().__init__()
        if not config.KITE_API_KEY or not config.KITE_ACCESS_TOKEN:
            raise KiteError(
                "KITE_API_KEY and KITE_ACCESS_TOKEN must be set. "
                "Run `python3 login.py <request_token>` to mint an access token."
            )
        self._instruments: dict[str, list[dict]] = {}
        self._instruments_day: date | None = None
        self._resolved_tape: list[tuple[str, str]] = []
        self._opt_cache: dict[tuple[str, str], list[str]] = {}

    # -- HTTP ---------------------------------------------------------------
    def _request(self, path: str, params=None, raw: bool = False):
        url = config.KITE_BASE + path
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        req = urllib.request.Request(url, headers={
            "X-Kite-Version": "3",
            "Authorization": f"token {config.KITE_API_KEY}:{config.KITE_ACCESS_TOKEN}",
            "Accept-Encoding": "gzip",
        })
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
        except urllib.error.HTTPError as exc:
            # We ask for gzip, so error bodies arrive compressed too. Without this
            # the log fills with binary noise instead of Kite's actual message.
            detail_raw = exc.read()
            if exc.headers.get("Content-Encoding") == "gzip":
                try:
                    detail_raw = gzip.decompress(detail_raw)
                except (OSError, EOFError):
                    pass
            detail = detail_raw.decode("utf-8", "replace")[:400]
            try:
                detail = json.loads(detail).get("message", detail)
            except (ValueError, AttributeError):
                pass
            if exc.code in (401, 403):
                raise KiteError(
                    f"Kite rejected the credentials ({exc.code}). Access tokens expire "
                    f"every morning -- mint a fresh one with login.py. {detail}"
                ) from exc
            raise KiteError(f"Kite HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise KiteError(f"Cannot reach Kite: {exc.reason}") from exc
        if raw:
            return body
        payload = json.loads(body.decode("utf-8"))
        if payload.get("status") != "success":
            raise KiteError(f"Kite error: {payload.get('message')}")
        return payload["data"]

    # -- instruments --------------------------------------------------------
    def _load_instruments(self, exchange: str) -> list[dict]:
        today = date.today()
        if self._instruments_day != today:
            self._instruments.clear()
            self._opt_cache.clear()
            self._resolved_tape = []
            self._instruments_day = today
        if exchange in self._instruments:
            return self._instruments[exchange]
        log.info("downloading %s instrument dump", exchange)
        body = self._request(f"/instruments/{exchange}", raw=True)
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8", "replace"))))
        self._instruments[exchange] = rows
        log.info("%s: %d instruments", exchange, len(rows))
        return rows

    @staticmethod
    def _expiry(row: dict):
        try:
            return datetime.strptime(row["expiry"], "%Y-%m-%d").date()
        except (ValueError, KeyError):
            return None

    def _nearest_future(self, exchange: str, name: str) -> str | None:
        today = date.today()
        best, best_exp = None, None
        for row in self._load_instruments(exchange):
            if row.get("name") != name or row.get("instrument_type") != "FUT":
                continue
            exp = self._expiry(row)
            if exp is None or exp < today:
                continue
            if best_exp is None or exp < best_exp:
                best, best_exp = row, exp
        return f"{exchange}:{best['tradingsymbol']}" if best else None

    def _nearest_expiry(self, exchange: str, name: str):
        today = date.today()
        expiries = {self._expiry(r) for r in self._load_instruments(exchange)
                    if r.get("name") == name and r.get("instrument_type") in ("CE", "PE")}
        future = sorted(e for e in expiries if e and e >= today)
        return future[0] if future else None

    def _option_symbols(self, symbol: str, spot: float) -> tuple[list[str], dict]:
        """Tradingsymbols for the strikes around spot, plus strike/right lookup."""
        meta = UNDERLYING.get(symbol)
        if not meta:
            raise KiteError(f"No option mapping configured for {symbol}")
        exchange = meta["opt_exchange"]
        expiry = self._nearest_expiry(exchange, symbol)
        if expiry is None:
            raise KiteError(f"No live expiry found for {symbol} on {exchange}")
        step = meta["step"]
        atm = sheets.atm_strike(spot, step)
        span = (config.SHEET_ROWS // 2) * step + config.SHEET_WING
        lo, hi = atm - span, atm + span

        symbols, lookup = [], {}
        for row in self._load_instruments(exchange):
            if row.get("name") != symbol or row.get("instrument_type") not in ("CE", "PE"):
                continue
            if self._expiry(row) != expiry:
                continue
            try:
                strike = int(float(row["strike"]))
            except (ValueError, KeyError):
                continue
            if not (lo <= strike <= hi):
                continue
            key = f"{exchange}:{row['tradingsymbol']}"
            symbols.append(key)
            lookup[key] = (strike, row["instrument_type"])
        if not symbols:
            raise KiteError(f"No {symbol} strikes found near {atm} for expiry {expiry}")
        return symbols, lookup

    # -- refresh ------------------------------------------------------------
    def _tape_instruments(self) -> list[tuple[str, str]]:
        if self._resolved_tape:
            return self._resolved_tape
        resolved = []
        for label, spec in TAPE:
            if isinstance(spec, str):
                resolved.append((label, spec))
                continue
            exchange, name, _kind = spec
            try:
                found = self._nearest_future(exchange, name)
            except KiteError:
                found = None
            if found:
                resolved.append((label, found))
            else:
                log.warning("tape: could not resolve %s on %s", name, exchange)
        self._resolved_tape = resolved
        return resolved

    def refresh(self) -> None:
        try:
            self._refresh()
        except KiteError as exc:
            log.error("%s", exc)
            self._publish(live=False, error=str(exc))

    def _refresh(self) -> None:
        tape = self._tape_instruments()
        sym = config.SHEET_SYMBOL
        meta = UNDERLYING.get(sym, {})
        spot_key = meta.get("spot", "NSE:NIFTY 50")

        # One request for the tape and the index spots.
        want = [inst for _label, inst in tape]
        if spot_key not in want:
            want.append(spot_key)
        first = self._request("/quote", {"i": want})

        quotes = []
        for label, inst in tape:
            row = first.get(inst)
            if not row:
                continue
            last = row.get("last_price")
            close = (row.get("ohlc") or {}).get("close")
            if last is None:
                continue
            change = 0.0 if not close else (last - close) / close * 100.0
            quotes.append({"symbol": label, "price": round(last, 2), "change": round(change, 2)})

        spot_row = first.get(spot_key)
        if not spot_row or spot_row.get("last_price") is None:
            raise KiteError(f"No spot price for {spot_key}")
        spot = float(spot_row["last_price"])

        # A second request for the option strikes around the money.
        symbols, lookup = self._option_symbols(sym, spot)
        chain = {}
        for batch in (symbols[i:i + 500] for i in range(0, len(symbols), 500)):
            data = self._request("/quote", {"i": batch})
            for key, row in data.items():
                price = row.get("last_price")
                if price is None:
                    continue
                ident = lookup.get(key) or lookup.get(key.split(":", 1)[-1])
                if ident:
                    chain[ident] = float(price)

        step = meta.get("step", config.SHEET_STEP)
        self._publish(
            quotes=quotes,
            sheet={"rows": sheets.butterfly_rows(chain, spot, step, config.SHEET_ROWS, config.SHEET_WING)},
            mini=sheets.mini_rows(chain, spot, step),
            straddle=sheets.straddle_price(chain, spot, step),
            symbol=sym, atm=sheets.atm_strike(spot, step),
            live=True, error=None,
        )


def build_feed() -> Feed:
    """Pick a feed from config, falling back to the simulator if it cannot start."""
    if config.FEED == "upstox":
        try:
            from upstoxfeed import UpstoxFeed   # imported here: upstoxfeed imports us
            feed = UpstoxFeed()
            log.info("using live Upstox market data feed")
            return feed
        except Exception as exc:
            log.error("Upstox feed unavailable (%s) -- falling back to the simulator", exc)
    elif config.FEED in ("kite", "kite-rest"):
        cls = KiteFeed if config.FEED == "kite-rest" else KiteTickerFeed
        try:
            feed = cls()
            log.info("using live Kite Connect feed (%s)", feed.name)
            return feed
        except KiteError as exc:
            log.error("Kite feed unavailable (%s) -- falling back to the simulator", exc)
    elif config.FEED != "simulator":
        log.warning("unknown FINOSTAT_FEED=%r -- using the simulator", config.FEED)
    log.info("using the simulator feed")
    return SimulatorFeed()


class KiteTickerFeed(KiteFeed):
    """Live data over Kite's streaming WebSocket.

    Instrument resolution and REST calls are inherited; the difference is how
    prices arrive. Instead of asking once a second, we hold one socket open and
    the exchange pushes every tick, which is what makes sub-250ms refresh real.

    REST is still used, exactly twice a day's worth: once to resolve
    instrument tokens and opening closes, and again when the expiry rolls.
    """

    name = "kite-ticker"

    # Rebuild the published snapshot at most this often. Ticks can arrive
    # hundreds of times a second; re-deriving the whole sheet on each one is
    # wasted work nobody can see.
    PUBLISH_INTERVAL = 0.12
    BACKOFF_MAX = 30.0

    @property
    def interval(self) -> float:
        """Pushed, not polled -- report how often snapshots are republished."""
        return self.PUBLISH_INTERVAL

    def __init__(self) -> None:
        super().__init__()
        self._ws: wsclient.WebSocket | None = None
        self._prices: dict[int, float] = {}      # token -> last price
        self._closes: dict[int, float] = {}      # token -> previous close
        self._meta: dict[int, dict] = {}         # token -> what the token is
        self._spot_token: int | None = None
        self._resolved_for: date | None = None
        self._dirty = threading.Event()
        self._ticks = 0

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="kite-ticker", daemon=True)
        self._thread.start()
        threading.Thread(target=self._publisher, name="kite-publish", daemon=True).start()

    def stop(self) -> None:
        super().stop()
        self._dirty.set()
        ws = self._ws
        if ws is not None:
            ws.close()

    def refresh(self) -> None:
        """The socket pushes; there is nothing to poll."""

    # -- token resolution ---------------------------------------------------
    def _resolve(self) -> list[int]:
        """One REST pass to turn symbols into tokens and record yesterday's closes."""
        tape = self._tape_instruments()
        sym = config.SHEET_SYMBOL
        meta = UNDERLYING.get(sym, {})
        spot_key = meta.get("spot", "NSE:NIFTY 50")

        want = [inst for _label, inst in tape]
        if spot_key not in want:
            want.append(spot_key)
        first = self._request("/quote", {"i": want})

        self._meta.clear()
        self._closes.clear()
        self._prices.clear()

        for label, inst in tape:
            row = first.get(inst)
            if not row or row.get("instrument_token") is None:
                log.warning("ticker: no token for %s", inst)
                continue
            token = int(row["instrument_token"])
            self._meta[token] = {"kind": "tape", "label": label}
            self._seed(token, row)

        spot_row = first.get(spot_key)
        if not spot_row or spot_row.get("instrument_token") is None:
            raise KiteError(f"No instrument token for {spot_key}")
        self._spot_token = int(spot_row["instrument_token"])
        self._meta.setdefault(self._spot_token, {"kind": "spot", "label": sym})
        self._meta[self._spot_token]["kind"] = self._meta[self._spot_token].get("kind", "spot")
        self._seed(self._spot_token, spot_row)

        spot = float(spot_row.get("last_price") or 0.0)
        if spot <= 0:
            raise KiteError(f"No spot price for {spot_key}")

        symbols, lookup = self._option_symbols(sym, spot)
        for batch in (symbols[i:i + 500] for i in range(0, len(symbols), 500)):
            data = self._request("/quote", {"i": batch})
            for key, row in data.items():
                ident = lookup.get(key) or lookup.get(key.split(":", 1)[-1])
                if not ident or row.get("instrument_token") is None:
                    continue
                token = int(row["instrument_token"])
                self._meta[token] = {"kind": "option", "strike": ident[0], "right": ident[1]}
                self._seed(token, row)

        if not any(m["kind"] == "option" for m in self._meta.values()):
            raise KiteError(f"Resolved no {sym} option tokens")

        self._resolved_for = date.today()
        log.info("ticker: resolved %d instruments (%d options)", len(self._meta),
                 sum(1 for m in self._meta.values() if m["kind"] == "option"))
        return list(self._meta)

    def _seed(self, token: int, row: dict) -> None:
        """Prime prices from REST so the first snapshot is complete before ticks land."""
        price = row.get("last_price")
        if price is not None:
            self._prices[token] = float(price)
        close = (row.get("ohlc") or {}).get("close")
        if close:
            self._closes[token] = float(close)

    # -- socket -------------------------------------------------------------
    def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                tokens = self._resolve()
                self._connect(tokens)
                backoff = 1.0
                self._read_forever()
            except KiteError as exc:
                log.error("ticker: %s", exc)
                self._publish(live=False, error=str(exc))
            except wsclient.WebSocketClosed as exc:
                log.warning("ticker: socket closed (%s)", exc)
                self._publish(live=False, error=f"stream closed: {exc}")
            except Exception as exc:
                log.exception("ticker: unexpected failure")
                self._publish(live=False, error=str(exc))
            finally:
                if self._ws is not None:
                    self._ws.close()
                    self._ws = None
            if self._stop.is_set():
                break
            log.info("ticker: reconnecting in %.0fs", backoff)
            self._stop.wait(backoff)
            backoff = min(self.BACKOFF_MAX, backoff * 2)

    def _connect(self, tokens: list[int]) -> None:
        url = (f"wss://ws.kite.trade?api_key={urllib.parse.quote(config.KITE_API_KEY)}"
               f"&access_token={urllib.parse.quote(config.KITE_ACCESS_TOKEN)}")
        log.info("ticker: connecting to ws.kite.trade")
        ws = wsclient.WebSocket(url, timeout=20.0)
        # Read timeout must exceed Kite's heartbeat gap or we would tear down a
        # perfectly healthy socket during a quiet market.
        ws.settimeout(60.0)
        ws.send_text(kiteticker.subscribe_message(tokens))
        ws.send_text(kiteticker.mode_message(kiteticker.QUOTE, tokens))
        self._ws = ws
        log.info("ticker: subscribed to %d instruments in quote mode", len(tokens))
        self._rebuild()

    def _read_forever(self) -> None:
        assert self._ws is not None
        while not self._stop.is_set():
            try:
                kind, payload = self._ws.recv()
            except socket_timeout:
                raise wsclient.WebSocketClosed("no data for 60s")
            if kind == "text":
                self._on_text(payload)
                continue
            ticks = kiteticker.parse_binary(payload)
            if not ticks:
                continue  # heartbeat
            for tick in ticks:
                token = tick["instrument_token"]
                if token not in self._meta:
                    continue
                self._prices[token] = tick["last_price"]
                close = (tick.get("ohlc") or {}).get("close")
                if close:
                    self._closes[token] = close
            self._ticks += len(ticks)
            self._dirty.set()

    def _on_text(self, payload: bytes) -> None:
        try:
            message = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return
        if message.get("type") == "error":
            log.error("ticker: kite said %s", message.get("data"))
            self._publish(error=str(message.get("data")))

    # -- publishing ---------------------------------------------------------
    def _publisher(self) -> None:
        while not self._stop.is_set():
            if not self._dirty.wait(1.0):
                continue
            self._dirty.clear()
            try:
                self._rebuild()
            except Exception:
                log.exception("ticker: rebuild failed")
            self._stop.wait(self.PUBLISH_INTERVAL)

    def _rebuild(self) -> None:
        spot = self._prices.get(self._spot_token or -1)
        if not spot:
            return
        sym = config.SHEET_SYMBOL
        step = UNDERLYING.get(sym, {}).get("step", config.SHEET_STEP)

        chain = {}
        for token, meta in self._meta.items():
            if meta["kind"] != "option":
                continue
            price = self._prices.get(token)
            if price is not None:
                chain[(meta["strike"], meta["right"])] = price

        quotes = []
        for token, meta in self._meta.items():
            if meta["kind"] != "tape":
                continue
            price = self._prices.get(token)
            if price is None:
                continue
            close = self._closes.get(token)
            change = 0.0 if not close else (price - close) / close * 100.0
            quotes.append({"symbol": meta["label"], "price": round(price, 2),
                           "change": round(change, 2)})
        order = {label: i for i, (label, _spec) in enumerate(TAPE)}
        quotes.sort(key=lambda q: order.get(q["symbol"], 99))

        self._publish(
            quotes=quotes,
            sheet={"rows": sheets.butterfly_rows(chain, spot, step,
                                                 config.SHEET_ROWS, config.SHEET_WING)},
            mini=sheets.mini_rows(chain, spot, step),
            straddle=sheets.straddle_price(chain, spot, step),
            symbol=sym, atm=sheets.atm_strike(spot, step),
            live=True, error=None, ticks=self._ticks,
        )
