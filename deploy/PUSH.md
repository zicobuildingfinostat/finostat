# Push to GitHub, then deploy to Railway

The local repo is already committed and clean. `server/.env` is **not** in it —
verified by scanning the staged contents, not just the filenames.

## 1. Create the GitHub repo

`gh` is not installed on this machine, so use the web UI:

1. <https://github.com/new>
2. **Repository name:** `finostat`
3. **Private.** This is a commercial product with a paid data feed. You can
   always flip it public later; you cannot un-publish git history.
4. **Do not** tick "Add a README", ".gitignore" or "license" — this repo already
   has all three, and initialising would create a conflicting first commit.
5. Create repository.

## 2. Push

Replace `YOUR_USERNAME`:

```bash
cd "/Users/gicokarmakar/Desktop/Finostat Website"
git remote add origin https://github.com/YOUR_USERNAME/finostat.git
git push -u origin main
```

**When it asks for a password, your GitHub account password will not work.**
GitHub removed password auth for git. Use a Personal Access Token:

1. <https://github.com/settings/tokens> → Generate new token (classic)
2. Tick the **`repo`** scope, generate, copy it
3. Paste it as the *password* at the prompt (username is your GitHub username)

Then confirm the secret really did not go up:

```bash
git ls-files | grep -c "\.env$"      # must print 0
```

## 3. Deploy on Railway

1. <https://railway.app> → sign in **with GitHub**.
2. **New Project → Deploy from GitHub repo →** pick `finostat`. Authorise
   Railway to read the repo when prompted.
3. **Settings → Build → Dockerfile Path:** `deploy/Dockerfile`
4. **Variables → New Variable**, add these three:

   | Variable | Value |
   |---|---|
   | `FINOSTAT_FEED` | `upstox` |
   | `UPSTOX_ACCESS_TOKEN` | *your Analytics Token* |
   | `FINOSTAT_HOST` | `0.0.0.0` |

   **Do not set `FINOSTAT_PORT`.** Railway injects its own `$PORT` and routes to
   it; overriding it gives you a deploy that reports healthy while the site is
   unreachable.

5. **Settings → Networking → Generate Domain.**
6. Check it before touching DNS:

   ```
   https://YOUR-APP.up.railway.app/api/status
   ```

   You want `"feed":"upstox"` and `"live":true`. If it says
   `"feed":"simulator"`, the token variable did not land — check step 4.

## 4. Point finostat.com at it

1. Railway → **Settings → Custom Domain →** add `finostat.com`. Railway shows
   you the exact DNS record it wants.
2. GoDaddy → My Products → finostat.com → **DNS → Manage DNS**.
3. **Delete** the two existing `A` records on `@` and `www` — they point at the
   GoDaddy "Launching Soon" builder.
4. **Add** the record Railway gave you.
5. **Do not touch the MX or TXT records.** Those are your email; changing them
   breaks it.

Propagation is usually minutes, occasionally an hour.

## 5. After it is live

- **Regenerate your Upstox token.** The one currently in `server/.env` was
  visible in a chat transcript. Generate a fresh Analytics Token at
  <https://account.upstox.com/developer/apps> and set it in Railway's Variables
  only — it never needs to touch a file again.
- Watch `/api/status` on the first trading morning (09:15 IST). `ticks` should
  climb steadily.
