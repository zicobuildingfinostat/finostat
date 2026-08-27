# Getting finostat.com live — free, no card, no terminal

This publishes the **preview** site: the real design and content, with the
sheets running a browser-side simulation and labelled as such. The live market
feed needs an always-on server, which needs a paid host — that part waits.

## Step 1 — Upload the files (2 min)

1. Go to <https://github.com/zicobuildingfinostat/finostat>
2. **Add file → Upload files**
3. Open the `static-site` folder on your Mac and drag **all 6 files** in:
   `index.html`, `og.jpg`, `robots.txt`, `sitemap.xml`, `CNAME`, `.nojekyll`
   - If `.nojekyll` and `CNAME` don't appear in Finder, press **⌘ + Shift + .**
     to show hidden files.
4. Scroll down, click **Commit changes**

## Step 2 — Turn on GitHub Pages (1 min)

1. In the repo: **Settings → Pages**
2. **Source:** Deploy from a branch
3. **Branch:** `main`, folder `/ (root)` → **Save**
4. Under **Custom domain** it should already read `finostat.com` (from the CNAME
   file). If not, type it and Save.
5. Tick **Enforce HTTPS** once it becomes available (can take an hour).

The repo must stay **public** for Pages to work on a free account. Yours is.

## Step 3 — Point the domain (5 min)

GoDaddy → **My Products → finostat.com → DNS → Manage DNS**

**Delete** the two existing `A` records on `@` (they point at GoDaddy's
"Launching Soon" builder).

**Add these four `A` records**, all with Name `@`:

| Type | Name | Value |
|---|---|---|
| A | `@` | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |

**Add one CNAME:**

| Type | Name | Value |
|---|---|---|
| CNAME | `www` | `zicobuildingfinostat.github.io` |

### Do not touch these
Leave every **MX** record and every **TXT** record exactly as they are. Those
run your email — `zico@finostat.com` stops working if they change.

## Step 4 — Wait, then check

DNS takes 10 minutes to an hour. Then <https://finostat.com> should show the
site. Check <https://www.whatsmydns.net/#A/finostat.com> to watch it propagate.

## Later, when you have a card

The full server is written, tested and ready. Adding a host (~$5/month) gets you
the live Upstox feed, the news wire and sub-250ms sheets. Nothing needs
rewriting — it is the same repo, just deployed somewhere that stays running.
