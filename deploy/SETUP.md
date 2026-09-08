# Setup: token, hosting, database

## 1. Get your Upstox Analytics Token

1. Sign in at <https://account.upstox.com/developer/apps>
2. Create an app if you have not already.
3. Generate an **Analytics Token** — *not* a regular access token.
   - Analytics Token → valid **1 year**, no daily login.
   - Regular access token → expires at **3:30 AM every day**.
   - Getting this wrong is the difference between a site that runs itself and
     one you have to nurse every morning.
4. Copy it. It is read-only and cannot place orders, but treat it like a password.

## 2. Put it in `server/.env`

From the project folder:

```bash
cd "/Users/gicokarmakar/Desktop/Finostat Website/server"
cp .env.example .env
open -e .env
```

In the file that opens, change these two lines:

```
FINOSTAT_FEED=upstox
UPSTOX_ACCESS_TOKEN=paste_your_token_here
```

Rules that actually bite:
- **No quotes** around the token. `UPSTOX_ACCESS_TOKEN=eyJ0eXAi...` — not `"eyJ0eXAi..."`.
- **No spaces** around the `=`.
- **No trailing spaces** after the token.
- The token is one long line. Do not let the editor wrap it into two.

Then lock the file down:

```bash
chmod 600 .env
```

Confirm it never gets committed — this should print `.env`:

```bash
cat .gitignore
```

## 3. Test locally before deploying

```bash
cd "/Users/gicokarmakar/Desktop/Finostat Website/server"
./run.sh
```

In another terminal:

```bash
curl -s localhost:8000/api/status
```

- `"live":true` → real Upstox data is flowing.
- `"live":false` with an `"error"` → read the error; it says exactly what is wrong.
- `"feed":"simulator"` → the token was not picked up. Check step 2.

Outside market hours (09:15–15:30 IST, Mon–Fri) prices will be static because
the exchange is closed. That is normal, not a bug.

---

## 4. Hosting: Vercel will not work for this

**Vercel cannot host the Finostat server.** This is not a preference, it is an
architectural mismatch:

- Vercel runs **serverless functions**. Your feed needs a **process that stays
  alive** holding one WebSocket open to Upstox from 09:15 to 15:30 — six hours.
- Vercel's WebSocket support (public beta, June 2026) is capped at **5 minutes**
  by default, **30 minutes** on Pro. The market day is twelve times that.
- The server keeps prices **in memory** and fans them out to browsers. Serverless
  invocations are isolated and ephemeral, so there is no shared memory to fan out
  from.

Vercel is excellent at what it does — static sites and short request/response
functions. This is neither.

### Use Railway instead (recommended)

One service, one always-on process, roughly $5/month.

1. Put the project in a GitHub repo. **Check `server/.env` is not in it.**
2. <https://railway.app> → New Project → Deploy from GitHub repo.
3. Settings → Build → set **Dockerfile Path** to `deploy/Dockerfile`.
4. Variables → add:

   | Variable | Value |
   |---|---|
   | `FINOSTAT_FEED` | `upstox` |
   | `UPSTOX_ACCESS_TOKEN` | *your token* |
   | `FINOSTAT_HOST` | `0.0.0.0` |

   Set the token **here**, in Railway's variables — not in a committed file.
   This is the same value as your local `.env`, stored in the platform's secret
   store instead.
5. Settings → Networking → Generate Domain, confirm the site loads.
6. Settings → Custom Domain → add `finostat.com`. Railway shows you the DNS
   record it wants.

Fly.io works the same way (`fly launch --dockerfile deploy/Dockerfile`,
`fly secrets set UPSTOX_ACCESS_TOKEN=...`). Render also works — but **not its
free tier**, which sleeps when idle.

### Then point GoDaddy at it

GoDaddy → My Products → finostat.com → DNS → Manage DNS.

Delete the two existing `A` records on `@` and `www` (they point at GoDaddy's
builder), and add what your host told you — usually:

| Type | Name | Value |
|---|---|---|
| A | `@` | *the IP your host gave you* |
| CNAME | `www` | *the hostname your host gave you* |

**Do not touch the MX or TXT records.** Those are your email; changing them
breaks it. Propagation takes minutes to an hour.

### If you truly want Vercel in the picture

The only workable split is: static page on Vercel, feed server on Railway at
`api.finostat.com`, and the page calls across to it. That costs you CORS
configuration, a second deploy target, and an extra DNS record — for no benefit
over just putting everything on Railway. I would not.

---

## 5. Postgres: not yet, and here is why

**Nothing currently built stores anything.** The server holds live prices in
memory and derives sheets on the fly; the news wire keeps 120 headlines in RAM.
Adding Postgres today gives you an empty database and a connection string to
manage.

Postgres becomes necessary the moment you build any of these — all of which the
marketing page already advertises:

| Feature | What the table holds |
|---|---|
| Sign-ups, the `/signup` and `/login` routes | users, password hashes, sessions |
| Alert rules ("alerts that never sleep") | rule per user, per instrument, thresholds |
| Saved sheets and layouts | user preferences |
| Plans and billing | subscription state, payment references |

There is **one** argument for starting sooner: the site promises *"4 yrs expiry
history"*, *historical sheets* and *backtesting*. You cannot backfill tick data
you never recorded. If those features matter, a small writer that banks every
tick from launch day starts accumulating something you cannot buy back later.
For that specific job **TimescaleDB** (Postgres with a time-series extension)
fits far better than plain Postgres.

My recommendation: **launch without a database.** Add Postgres when you build
sign-ups, because that is the first feature that genuinely cannot work without
one. If you want tick history banked from day one, say so and I will write the
recorder as a separate, self-contained piece.

Railway, Render and Fly all provision Postgres in a couple of clicks when the
time comes, and inject `DATABASE_URL` automatically.

---

## 6. Sign-in emails (magic links)

Accounts are passwordless: `/login` emails a one-time link that signs the user
in and creates the account on first use. Sending needs SMTP credentials; until
they're set, the server **logs** links instead of sending them and the login
page says so.

Use the GoDaddy mailbox you already have:

1. `open -e server/.env` and fill in:
   ```
   SMTP_HOST=smtpout.secureserver.net
   SMTP_PORT=465
   SMTP_USER=zico@finostat.com
   SMTP_PASS=<that mailbox's password>
   SMTP_FROM=zico@finostat.com
   ```
   Save, close the editor.
2. Say "SMTP is in .env" — Claude reads the values from the file and pushes them
   to Fly as secrets (`flyctl secrets set ...`). They never appear in chat.
3. Confirm with `curl -s https://finostat.com/api/status` →
   `"auth":{"smtp_configured":true}`, then request a link at
   [finostat.com/login](https://finostat.com/login) and check the inbox.

Security properties, for the record: tokens and session ids are random 256-bit
values stored only as SHA-256 hashes; links expire in 15 minutes and burn on
first use; sessions are `HttpOnly; Secure; SameSite=Lax`, 30 days; link
requests are rate-limited (5 per address, 20 per IP, per 15 min); emailed links
always use `FINOSTAT_PUBLIC_URL`, never the request's Host header.

What an account unlocks today: the terminal's **watchlist** and **layout**
(which panels are shown) sync to the account across devices. Signed-out users
keep the same features in browser storage only.
