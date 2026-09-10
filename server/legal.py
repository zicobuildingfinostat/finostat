"""/privacy, /terms, /contact -- written for what this site actually does."""
from __future__ import annotations

from finch import _CSS as _BASE_CSS

UPDATED = "8 September 2026"
OWNER = "Zico Karmakar"
EMAIL = "zico@finostat.com"

_CSS = _BASE_CSS + r"""
.legal{max-width:76ch}
.legal h2{font-size:24px;margin-top:34px}
.legal p,.legal li{color:var(--muted)}
.legal strong{color:var(--text)}
.legal table{max-width:100%}
.meta{font-family:var(--mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);margin:0 0 22px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin:18px 0 26px;max-width:820px}
.cards div{border:1px solid var(--line-strong);background:var(--panel);padding:16px 18px}
.cards b{display:block;font-family:var(--mono);font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--cyan);margin-bottom:6px}
.cards p{font-size:14px;color:var(--muted);margin:0 0 8px}
.cards a.big{font-family:var(--display);font-size:22px;text-transform:uppercase;color:var(--gold)}
"""

_HEAD = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Finostat</title><meta name="description" content="__DESC__"><meta name="theme-color" content="#0c0626">
<link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" type="image/png" sizes="96x96" href="/favicon-96.png"><link rel="icon" type="image/png" sizes="192x192" href="/favicon-192.png"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="canonical" href="https://finostat.com__PATH__"><meta name="robots" content="index, follow">
<meta property="og:type" content="website"><meta property="og:site_name" content="Finostat"><meta property="og:title" content="__TITLE__ — Finostat"><meta property="og:description" content="__DESC__"><meta property="og:image" content="https://finostat.com/og.jpg"><meta property="og:url" content="https://finostat.com__PATH__">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>__CSS__</style></head><body>
<header class="top"><a class="logo" href="/">FINO<b>STAT</b></a><div class="r"><a href="/finch">FINCH</a><a href="/dashboard">TERMINAL</a><a href="/founders">FOUNDER</a><a href="/contact">CONTACT</a></div><a class="home-ic" href="/" aria-label="Finostat home" title="Finostat — home"><img src="/favicon-96.png" alt="Finostat" width="34" height="34"></a></header>
<main class="wrap"><nav class="crumb"><a href="/">FINO</a> · __CRUMB__</nav>
<h1>__TITLE__</h1><p class="meta">Last updated __UPDATED__ · Finostat, India · __EMAIL__</p>
<article class="legal">"""

_FOOT = """</article>
<p class="disc">Finostat is an analytics and education product, not a broker, adviser or research analyst. Nothing on this site is investment advice. Derivatives can lose more than you put in. Finostat is not affiliated with NSE, BSE, MCX, SEBI or Upstox.</p>
</main></body></html>"""

_PRIVACY = f"""
<p class="lede">This policy says exactly what finostat.com collects, why, where it lives and how to get it deleted. It is written to be read, not skimmed past.</p>

<h2>Who is responsible</h2>
<p>Finostat is operated by <strong>{OWNER}</strong> from India. For anything about your data — questions, corrections, deletion — write to <a href="mailto:{EMAIL}">{EMAIL}</a>. {OWNER} is also the grievance officer for the purposes of India's Digital Personal Data Protection Act, 2023.</p>

<h2>What we collect, and why</h2>
<table><thead><tr><th>Data</th><th>When</th><th>Why</th></tr></thead><tbody>
<tr><td>Email address</td><td>You sign in or sign up</td><td>Passwordless sign-in links; alert emails you ask for; upgrade requests. It is your account identifier.</td></tr>
<tr><td>Name, email, mobile number, city, your answers</td><td>You complete the trader assessment</td><td>To score the assessment, show your result, and — only if you ticked the consent box — to contact you about it. Answers are stored so you can be shown the same result again and so we can improve the questions.</td></tr>
<tr><td>Watchlist and layout preferences</td><td>You use the terminal signed in</td><td>So they follow your account between devices. Signed out, the same data stays in your browser only.</td></tr>
<tr><td>Alert rules and the events they fire</td><td>You create alerts signed in</td><td>To evaluate them on the server and email you when they trigger.</td></tr>
<tr><td>A feedback line and whether we may quote it</td><td>You choose to write one after the assessment</td><td>Product feedback. We publish a quote on the site only if you ticked “you may quote me”, and only as first name and city.</td></tr>
<tr><td>IP address</td><td>Every request, briefly</td><td>Rate-limiting sign-in links and assessment submissions to stop abuse. Kept with sign-in links (15 minutes) and assessment rows; not used for tracking.</td></tr>
</tbody></table>
<p>Payments for Desk and Pro are taken by <strong>Razorpay</strong> or <strong>Cashfree</strong> on their own checkout pages: your card, UPI or bank details go to the payment gateway and never to Finostat. Cashfree requires a mobile number on every order, which we keep on your account for that purpose only. We keep the order id, payment id, plan, period and amount, which is what a receipt and a refund need. We do not run advertising trackers or third-party analytics, and we never sell or rent personal data.</p>

<h2>Cookies and browser storage</h2>
<ul>
<li><strong>fino_session</strong> — one cookie, set only when you sign in. It holds a random session id (not your email), is HttpOnly and Secure, and expires after 30 days or when you sign out. It is strictly necessary for sign-in; there is no consent banner because there is nothing else to consent to.</li>
<li><strong>Local storage</strong> — signed-out watchlist, layout, browser-side alert rules, and a flag noting whether you have seen the assessment. This never leaves your browser and can be cleared from your browser settings.</li>
</ul>

<h2>Emails we send</h2>
<p>Only the ones you trigger: sign-in links, alert notifications for rules you created, and a reply if you write to us. No newsletters or marketing emails unless you opt in explicitly later; if we ever add them, every one will have an unsubscribe link. Email is sent through our own mailbox; delivery providers see the address and the message in transit, as any email provider does.</p>

<h2>Market data and third parties</h2>
<ul>
<li><strong>Market data</strong> comes from Upstox's market feed under our own subscription. Nothing about you is sent to Upstox.</li>
<li><strong>Hosting</strong>: the server and database run on Fly.io in Singapore, with encrypted storage. Your personal data is therefore stored outside India; the categories are those listed above and no more.</li>
<li><strong>Fonts</strong> load from Google Fonts, which sees your IP address and browser details when the page loads, as with any web font. No other third-party scripts run on the site.</li>
<li><strong>Search engines</strong>: public pages are indexable; your account data is never public.</li>
</ul>

<h2>How long we keep it</h2>
<ul>
<li>Sign-in links: 15 minutes. Sessions: 30 days of inactivity.</li>
<li>Account, preferences and alerts: for as long as the account exists. Ask and we delete the account and everything attached to it.</li>
<li>Assessment submissions: until you ask us to delete them.</li>
<li>Backups: daily copies of the database are kept for seven days, then overwritten. A deletion request removes you from the live database at once and from backups within seven days.</li>
</ul>

<h2>Your rights</h2>
<p>Under the DPDP Act and as a matter of plain decency you can ask for a copy of what we hold about you, correct it, withdraw consent, or have it deleted. Email <a href="mailto:{EMAIL}">{EMAIL}</a> from the address on the account; we respond within seven days and delete within thirty. If you are unhappy with the response you may approach the Data Protection Board of India.</p>

<h2>Security</h2>
<p>Sign-in tokens and session ids are stored only as SHA-256 hashes; links are single-use; all traffic is HTTPS; the database lives on an encrypted volume and is backed up daily. No system is perfect — if we discover a breach affecting your data we will tell you by email without undue delay.</p>

<h2>Children</h2>
<p>The site is for adults. We do not knowingly collect data from anyone under 18; if you believe we have, tell us and it will be deleted.</p>

<h2>Changes</h2>
<p>If this policy changes materially we update the date at the top and, for signed-in users, say so by email. The current version always lives at <a href="/privacy">finostat.com/privacy</a>.</p>
"""

_TERMS = f"""
<p class="lede">The short, honest version of the deal between you and Finostat. Using the site means you accept it.</p>

<h2>What Finostat is — and is not</h2>
<p>Finostat is an <strong>analytics and education</strong> product: live market data, option-chain mathematics, a strategy builder, alerts and the Finch course. It is <strong>not</strong> a broker, an exchange, a portfolio manager, or a research or advisory service. {OWNER} and Finostat are not registered with SEBI as investment advisers or research analysts. Nothing on the site — no number, alert, strategy preset, example, chapter, assessment result or reply to an email — is a recommendation to buy, sell or hold anything. Every trading decision is yours alone.</p>

<h2>Data is indicative</h2>
<p>Prices, implied volatilities, Greeks, payoffs and breakevens are computed from a live feed and standard models. They can be delayed, missing or wrong: feeds drop, exchanges halt, models assume things markets ignore. Confirm anything you intend to act on with your broker's terminal. Historical or recorded data is provided as-is.</p>

<h2>Risk</h2>
<p>Derivatives trading can lose more than the money you put in, quickly. You confirm that you understand this, that you are trading with money you can afford to lose, and that you will not hold Finostat responsible for trading outcomes. Please read the <a href="/finch/risk-and-position-sizing">risk chapter of Finch</a>; it is free and it is the part that matters most.</p>

<h2>Accounts</h2>
<p>Accounts are created with an email address and passwordless links. Keep your mailbox secure; anyone who can read your email can sign in as you. One account per person; do not share sessions or scrape the site. We may suspend accounts that abuse the service (automated hammering, resale of data, attempts to access other users' data) and will tell you why.</p>

<h2>Plans and payment</h2>
<ul>
<li><strong>Starter</strong> is free, without a card.</li>
<li><strong>Desk</strong> and <strong>Pro</strong> are paid plans at the prices shown on the <a href="/#plans">plans section</a>, in Indian rupees; any GST due is itemised at checkout. You pay for 30 days or 365 days at a time through Razorpay or Cashfree from your <a href="/account">account page</a>, and the plan is active the moment the payment is confirmed; a receipt is emailed.</li>
<li>Plans do <strong>not</strong> renew automatically. We email you three days before a period ends; paying again extends the plan from its current end date. Cancel simply by not renewing — access continues to the end of the paid period. Refunds: within seven days of a first payment if you have not been able to use the service, otherwise pro rata at our discretion; refunds go back to the original payment method via the gateway you paid through.</li>
<li>We may change prices with 30 days' notice; changes apply from your next billing period.</li>
</ul>

<h2>Broker connections and orders</h2>
<p>You may connect a broker account (for example Upstox) to Finostat through the broker's own login. Finostat then reads your positions and funds and, only when you press the confirm button on an order ticket, transmits the orders you composed to your broker. <strong>Finostat is not a broker and does not execute trades</strong>: the broker executes, the broker's terms, margins and charges apply, and every order is placed under your own account and your own responsibility. Finostat shows you what it will send before it sends it; check it. Connections can be removed from the terminal at any time, and the broker's access token expires daily on its own. Finostat is not liable for orders rejected, delayed or executed by the broker, for feed or connectivity failures, or for the outcome of any trade.</p>

<h2>Availability</h2>
<p>We aim to keep the terminal up during Indian market hours but promise no particular uptime. Feeds, hosting and exchanges fail from time to time; we do not owe compensation for downtime, though we may extend paid periods when it is significant.</p>

<h2>Content and intellectual property</h2>
<p>The site, its code, sheets, Finch text and design are Finostat's. You may use them for your own trading and study, quote short passages with attribution, and share links freely. You may not republish, resell or redistribute the data or the course, or use the site to build a competing feed. Market data is licensed from its providers and is for your personal display only.</p>

<h2>Feedback and quotes</h2>
<p>If you send feedback we may use it to improve the product. We publish a quote from you on the site only with the consent you give at the time (first name and city only), and we remove it if you ask.</p>

<h2>Liability</h2>
<p>To the fullest extent Indian law allows, Finostat's total liability to you for anything arising from the service is limited to the amount you paid us in the twelve months before the claim, and we are not liable for trading losses, lost profits or indirect losses of any kind. Nothing here limits liability that cannot lawfully be limited.</p>

<h2>Governing law</h2>
<p>These terms are governed by the laws of India. Disputes go first to a conversation by email, and if that fails, to the courts in India.</p>

<h2>Changes</h2>
<p>We may update these terms; the date at the top changes when we do, and signed-in users are told by email about material changes. Continued use after that is acceptance. Privacy is covered separately in the <a href="/privacy">privacy policy</a>.</p>
"""

_CONTACT = f"""
<p class="lede">One person answers this mailbox — the founder. Product questions, data problems, upgrade requests, a trade whose pricing you want a second opinion on, or anything about your data.</p>
<div class="cards">
<div><b>Email</b><p>Replies within one working day, usually faster during market hours.</p><a class="big" href="mailto:{EMAIL}">{EMAIL}</a></div>
<div><b>Plans and upgrades</b><p>Request Desk or Pro from the terminal's builder panel, or email with the address on your account.</p><a class="big" href="/#plans">See plans →</a></div>
<div><b>Your data</b><p>Copy, correction or deletion of anything we hold about you — see the privacy policy for what that is.</p><a class="big" href="/privacy">Privacy →</a></div>
<div><b>Who you're writing to</b><p>{OWNER}, founder — ten-plus years in derivatives, three on prop and arbitrage desks.</p><a class="big" href="/founders">About the founder →</a></div>
</div>
<h2>Before you write</h2>
<ul>
<li><strong>Sign-in link not arriving?</strong> Check spam, then request a new one — links expire after 15 minutes and are single-use. Five links per address every 15 minutes is the limit.</li>
<li><strong>A price looks wrong?</strong> Tell us the symbol, the time (IST) and what your broker showed. That is enough to trace the tick.</li>
<li><strong>Want a feature?</strong> Say what decision it would help you make; that is how the roadmap is ordered.</li>
<li><strong>Press or partnerships:</strong> same address, subject line “Press” or “Partnership”.</li>
</ul>
<p>Finostat has no phone line and no office walk-ins; email is the fastest route and it reaches the person who built the product.</p>
"""

PAGES = {
    "/privacy": ("Privacy policy", "What finostat.com collects, why, where it is stored, how long it is kept and how to have it deleted. Plain language.", "PRIVACY", _PRIVACY),
    "/terms": ("Terms of service", "Finostat is analytics and education, not advice. Data is indicative, derivatives are risky, plans and payment, liability, Indian law.", "TERMS", _TERMS),
    "/contact": ("Contact", "Write to the founder of Finostat directly: product questions, data requests, upgrades, press.", "CONTACT", _CONTACT),
}


def render(path: str) -> bytes | None:
    page = PAGES.get(path)
    if page is None:
        return None
    title, desc, crumb, body = page
    doc = (_HEAD.replace("__TITLE__", title).replace("__DESC__", desc).replace("__PATH__", path).replace("__CRUMB__", crumb)
           .replace("__UPDATED__", UPDATED).replace("__EMAIL__", EMAIL).replace("__CSS__", _CSS))
    return (doc + body + _FOOT).encode("utf-8")
