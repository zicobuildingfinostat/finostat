# Deploying Finostat to finostat.com

## Where the domain stands today

| | |
|---|---|
| Registrar / DNS | GoDaddy (`ns77/ns78.domaincontrol.com`) |
| Currently serving | GoDaddy Website Builder, "Launching Soon" placeholder |
| Current A records | `76.223.105.230`, `13.248.243.5` (GoDaddy, ap-south-1) |
| Email (MX) | `secureserver.net` — **leave these alone**, changing them breaks email |

## The one constraint that decides everything

The live sheets, the tape and the news wire come from a **Python server**. Static
hosting cannot run it.

Put `index.html` on a static host and the page still loads and looks right — but
it falls back to the browser's own simulator. The numbers would be **fake while
the page says "LIVE"**. Do not ship that.

So: host that runs a process. Three realistic paths.

---

### Option A — VPS (most control, ~$5/month)

Hetzner CX22, DigitalOcean, or Linode. Ubuntu 24.04.

```bash
# on the server
sudo apt update && sudo apt install -y python3 caddy git
sudo useradd --system --create-home --shell /usr/sbin/nologin finostat
sudo mkdir -p /opt/finostat && sudo chown finostat:finostat /opt/finostat

# copy the project to /opt/finostat (rsync, scp, or git clone)
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo cp deploy/finostat.service /etc/systemd/system/
sudo cp server/.env.example /opt/finostat/server/.env   # then edit it
sudo chmod 600 /opt/finostat/server/.env
sudo chown finostat:finostat /opt/finostat/server/.env

sudo systemctl daemon-reload
sudo systemctl enable --now finostat
sudo systemctl reload caddy
```

Caddy issues and renews TLS automatically. Then in **GoDaddy → Domain → DNS**:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | *your server IP* | 600 |
| A | `www` | *your server IP* | 600 |

Delete the two existing GoDaddy A records on `@` and `www`. **Do not touch MX,
TXT or any other record.**

---

### Option B — Managed platform (easiest, no server admin)

Render, Railway or Fly.io. Push the repo, point them at `deploy/Dockerfile`.

- **Render**: New → Web Service → Docker. *Avoid the free tier* — it sleeps when
  idle, and a market data site that takes 40 seconds to wake is worse than
  useless. Use Starter ($7/mo).
- **Fly.io**: `fly launch --dockerfile deploy/Dockerfile`.

Then in GoDaddy DNS, per the platform's instructions — usually:

| Type | Name | Value |
|---|---|---|
| CNAME | `www` | *the platform hostname* |
| A / ALIAS | `@` | *the platform's apex IP or ALIAS target* |

GoDaddy does not support CNAME on the apex (`@`), so use whatever apex mechanism
the platform documents.

---

### Option C — Static only (fastest, but no live data)

Cloudflare Pages or Netlify, serving `index.html`, `og.jpg`, `robots.txt`,
`sitemap.xml`. Free and instant.

Only acceptable if you first **remove the "LIVE" indicators and the
"<250 ms"/"streamed by the millisecond" claims**, because none of them would be
true. Reasonable as a launch placeholder while the real host is set up.

---

## Before you point DNS

1. **Set a real `FINOSTAT_FEED`.** Left at `simulator`, the public site shows
   invented prices. That is fine for a soft launch, but decide deliberately.
2. **`chmod 600` the `.env`.** It holds your Kite api_secret.
3. **Never commit `.env`.** `server/.gitignore` already covers it.
4. **Check `/api/status`** after deploy: `{"live":true}` means real data.
5. Give the old GoDaddy builder site a moment — DNS changes take up to an hour
   to propagate, and the placeholder may linger in caches.

## Broker and tokens

Finostat now defaults to **Upstox**, whose Analytics Token is valid for a year.
That removes the daily re-login that Kite requires. See `SETUP.md` for the token
and hosting walkthrough.

| Broker | Token life | Market data cost |
|---|---|---|
| **Upstox** (default) | **1 year** (Analytics Token) | free |
| Dhan | 24 hours | Rs 499/month |
| Zerodha Kite | expires ~07:30 IST daily | Rs 2,000/month |

The Kite adapters are still in the tree and still work; set `FINOSTAT_FEED=kite`.
