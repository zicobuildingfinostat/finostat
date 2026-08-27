# Finostat server

Serves `index.html` with live numbers baked in and backs the four endpoints the
page already polls. **Python 3 standard library only** — no pip install, no
build step, no `node_modules`.

```bash
./run.sh          # or: python3 app.py
```

Then open http://127.0.0.1:8000.

Out of the box it runs the **simulator** feed, which needs no credentials and no
network. Everything works immediately; the prices just are not real.

---

## Going live with Zerodha Kite

Kite Connect is a paid product (about ₹2,000/month) and needs a Zerodha account.

1. Create an app at <https://developers.kite.trade/apps>. Set the redirect URL to
   anything you control — `http://127.0.0.1:8000/` is fine for local work.
2. `cp .env.example .env` and fill in `KITE_API_KEY` and `KITE_API_SECRET`.
3. Mint an access token:

   ```bash
   python3 login.py                 # prints the sign-in URL
   python3 login.py <request_token> # exchanges it, prints KITE_ACCESS_TOKEN=...
   ```

4. Paste that line into `.env`, set `FINOSTAT_FEED=kite`, and restart.

`FINOSTAT_FEED` picks how prices arrive:

| Value | Transport | Refresh |
|---|---|---|
| `simulator` | none | ~200 ms (default) |
| `kite` | WebSocket ticker | **sub-250 ms** — recommended |
| `kite-rest` | REST polling | ~1 s |

`kite` holds one socket open to `wss://ws.kite.trade` and the exchange pushes
every tick. REST is still used twice: once at startup to turn symbols into
instrument tokens and record yesterday's closes, and again when the expiry
rolls. `kite-rest` is kept as a fallback for a network that will not pass
WebSocket traffic.

Check it took:

```bash
curl -s localhost:8000/api/status
# {"feed":"kite","live":true,"error":null,...}
```

If `live` is `false`, `error` says why. The server **falls back to the simulator
rather than serving a broken page**, so a bad token degrades instead of breaking.

> **Access tokens expire every morning.** Step 3 is a daily ritual. For an
> always-on deployment you will want to automate it or hold a session open —
> Kite has no non-interactive login, which is a genuine operational constraint,
> not an oversight here.

### Switching brokers

Everything Kite-specific lives in `KiteFeed` in `feeds.py`. To use Upstox, Dhan
or Angel One instead, write a class with the same `refresh()` that calls
`self._publish(...)`, and add it to `build_feed()`. `sheets.py` and the HTTP
layer do not change — they never learn where the prices came from.

---

## Endpoints

| Route | Returns |
|---|---|
| `GET /` | `index.html` with `window.FINO` seeded and the news wire pre-rendered |
| `GET /api/quotes` | Ticker tape: `[{symbol, price, change}]`, `change` in percent |
| `GET /api/sheet` | `{rows: [[strike, CE, PE, BFLY, NET]], symbol, atm, straddle, live}` |
| `GET /api/mini` | The small BUY/SELL panel: `[[strike, buy, sell]]` |
| `GET /api/news` | `?limit=N` recent headlines |
| `GET /api/sheet/stream` | Server-sent events, `event: sheet` — the live sheet and tape |
| `GET /api/news/stream` | Server-sent events, `event: news` |
| `GET /api/status` | Feed health — use this for monitoring |

Unbuilt routes the marketing page links to (`/dashboard`, `/login`,
`/strategies/*`, …) return an on-brand 404 rather than a stack trace.

## How the numbers are built

`sheets.py` holds the maths, independent of any broker.

- **BFLY** — the 1:2:1 call butterfly at each strike: `C(K−W) − 2·C(K) + C(K+W)`.
- **NET** — that minus the equivalent put butterfly. Under put/call parity the
  two are equal, so NET sits at zero on a clean chain. **A NET far from zero is
  the dislocation the scanner exists to find.**

Missing legs produce a skipped row, never a wrong number.

## Architecture note

One connection to the broker, many browsers. The feed owns a single upstream
link and publishes snapshots; browsers subscribe to `/api/sheet/stream` and are
pushed updates. A hundred open tabs still cost the broker exactly one
connection — which matters, because Kite's `/quote` limit is about **one request
per second in total, not per client**, and it permits **three** concurrent
WebSocket connections per api_key.

The page prefers the push stream and falls back to polling `/api/sheet` if
EventSource is unavailable or the stream will not open within three seconds. If
the server disappears entirely, the page keeps animating from its own
client-side simulator rather than freezing.

Snapshot rebuilds are throttled to 120 ms. Ticks can arrive hundreds of times a
second; re-deriving the whole sheet on each one is work nobody can perceive.

## Deploying

`ThreadingHTTPServer` is fine for a small desk. For public traffic put nginx or
Caddy in front to terminate TLS and serve static files, and proxy `/api/` here.
SSE needs buffering off — the server already sends `X-Accel-Buffering: no`.

Set `FINOSTAT_HOST=0.0.0.0` to accept external connections. Keep `.env` out of
version control (`.gitignore` already covers it).

## Testing

`wsclient.py` and `kiteticker.py` are pure protocol code with no I/O, and were
built against a loopback WebSocket server and synthetic Kite packets:

- WebSocket: handshake and `Sec-WebSocket-Accept` verification, client-side
  masking, ping/pong, fragmented messages, 70 KB frames, clean close.
- Tick decoding: envelope framing, all five packet lengths, segment-dependent
  price divisors (100 / 10,000 / 10,000,000), the index vs tradable OHLC field
  order, heartbeats, and truncated envelopes.

## Known limitations

- **The Kite feed has not been exercised against a live account.** The transport
  is proven — `wsclient` completes a TLS handshake against the real
  `wss://ws.kite.trade` and gets back Kite's own *"Invalid `access_token` or
  `api_key`"* — and the decoder is tested against synthetic packets built from
  the published spec. But no real tick has ever flowed through it. Treat the
  first run with live credentials as a shakedown, during market hours.
- The **mini BUY/SELL panel** and the **straddle sparkline** still animate
  client-side. The stream already carries `mini`, so wiring them up is small.
- Kite allows **three** concurrent WebSocket connections per api_key. Running
  more than three server processes on one key will start getting refused.
- GIFT NIFTY is not available on Kite, so it drops off the tape on the live feed.
