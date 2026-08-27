# Finostat

Desk-grade options analytics for Indian derivatives traders — live butterfly,
ratio and straddle sheets for Nifty, BankNifty, Sensex and FinNifty.

<https://finostat.com>

## Running it

```bash
cd server
cp .env.example .env     # then add your Upstox token
./run.sh
```

Open <http://127.0.0.1:8000>. With no credentials configured it runs a
self-consistent simulator, so the site works immediately.

## What's here

| Path | |
|---|---|
| `index.html` | The whole front end — one file, no build step |
| `server/` | Market data server. Python 3 standard library only, no dependencies |
| `server/tests/` | Protocol tests. No network or credentials needed |
| `deploy/` | Dockerfile, Caddy and systemd units, deployment guides |

## Market data

| Broker | Token life | Data cost | Setting |
|---|---|---|---|
| **Upstox** (default) | **1 year** | free | `FINOSTAT_FEED=upstox` |
| Zerodha Kite | expires daily | ₹2,000/mo | `FINOSTAT_FEED=kite` |
| — simulator | n/a | free | `FINOSTAT_FEED=simulator` |

Upstox is the default because its Analytics Token lasts a year; Kite's expires
every morning and has no non-interactive login, which means a deployed site goes
dark daily.

Both feeds stream over a WebSocket and fall back gracefully: a bad token drops to
the simulator rather than serving a broken page.

## Architecture

One upstream connection, many browsers. The server holds a single socket to the
broker, derives the sheets, and pushes snapshots to browsers over server-sent
events at `/api/sheet/stream`. A hundred open tabs still cost the broker one
connection.

There are no third-party packages. The WebSocket client (`wsclient.py`), the Kite
binary tick decoder (`kiteticker.py`) and the protobuf reader (`miniproto.py`)
are all implemented against their published specs and tested.

```bash
server/tests/run.sh
```

## Deploying

See [deploy/SETUP.md](deploy/SETUP.md) for tokens and hosting, and
[deploy/DEPLOY.md](deploy/DEPLOY.md) for DNS.

Note: **Vercel cannot host this.** The feed needs a process that stays alive for
the whole market session; serverless functions time out and hold no shared state.

## Disclaimer

Data is indicative, may be delayed, and is not investment advice. Derivatives
trading involves substantial risk of loss. Not affiliated with NSE, BSE, MCX or
SEBI.
