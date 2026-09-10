"""Trader assessment: the first-visit questionnaire on the homepage (and /assessment).

Four steps -- who you are, how you have traded so far, a seven-question knowledge
check, and goals/risk habits. The server scores the check, assigns a profile and
a starting point in Finch, stores the submission in finostat.db (table
`assessments`) and emails the owner. The form markup is generated from the spec
below so the homepage modal and the standalone page never drift apart.
"""
from __future__ import annotations

import csv
import html
import io
import json
import logging
import pathlib
import re
import secrets
import sqlite3
import threading
import time

log = logging.getLogger("finostat.assessment")

# ---------------------------------------------------------------------------
# The questionnaire. (key, label, kind, options, required)
#   kind: text | email | phone | radio | check | quiz | consent
# ---------------------------------------------------------------------------
STEPS = [
    {"title": "About you", "hint": "So we can save your profile and send you your result.", "fields": [
        ("name", "Your name", "text", None, True),
        ("email", "Email", "email", None, True),
        ("phone", "Mobile number", "phone", None, True),
        ("city", "City", "text", None, False),
    ]},
    {"title": "Your trading so far", "hint": "There are no wrong answers here — honesty gets you a better plan.", "fields": [
        ("years", "How long have you been trading?", "radio",
         ["Never traded yet", "Less than a year", "1–3 years", "3–5 years", "More than 5 years"], True),
        ("segments", "Which segments have you traded? (pick all that apply)", "check",
         ["Equity delivery", "Intraday equity", "Index options", "Stock options", "Futures", "Commodities (MCX)", "Currency", "Crypto", "None yet"], True),
        ("style", "Your usual holding period", "radio",
         ["Intraday", "Swing (days)", "Positional (weeks or more)", "Long-term investing", "Not sure yet"], True),
        ("capital", "Capital you trade or plan to trade with", "radio",
         ["Under ₹50,000", "₹50,000 – ₹2 lakh", "₹2 – 10 lakh", "₹10 – 50 lakh", "Over ₹50 lakh"], True),
        ("fno_result", "Your F&O results so far", "radio",
         ["Net profit", "Roughly flat", "Net loss", "Never traded F&O"], True),
        ("broker", "Broker (optional)", "text", None, False),
    ]},
    {"title": "Quick knowledge check", "hint": "Seven questions. Guessing is fine — the result tells you what to read first.", "fields": [
        ("q1", "NIFTY is at 23,650. A 23,900 call with two days to expiry trades at ₹5. That premium is almost entirely…", "quiz",
         ["Intrinsic value", "Time value", "Margin", "Dividend"], True),
        ("q2", "Which of these positions has unlimited risk?", "quiz",
         ["Long call", "Long put", "Short strangle", "Bull call spread"], True),
        ("q3", "Right after a company announces results, its options' implied volatility usually…", "quiz",
         ["Rises", "Falls", "Stays the same", "Goes to zero"], True),
        ("q4", "A very large call open interest at a strike above spot is usually read as…", "quiz",
         ["Support", "Resistance", "A buy signal", "Meaningless"], True),
        ("q5", "The ATM straddle price is a good estimate of…", "quiz",
         ["Max pain", "The market's expected move to expiry", "The lot size", "The margin required"], True),
        ("q6", "An in-the-money stock option held through expiry in India is…", "quiz",
         ["Cash settled", "Physically settled — shares change hands", "Cancelled", "Rolled over automatically"], True),
        ("q7", "You risk 2% of a ₹5 lakh account per trade. The most one trade should lose is…", "quiz",
         ["₹1,000", "₹10,000", "₹50,000", "₹1 lakh"], True),
    ]},
    {"title": "Goals and risk habits", "hint": "Last step. This shapes what we recommend.", "fields": [
        ("goal", "What do you most want from trading?", "radio",
         ["Regular income from options", "Grow my capital", "Hedge my investments", "Learn properly before risking money", "Trade full-time"], True),
        ("challenge", "Your biggest challenge right now", "radio",
         ["Picking direction", "Managing risk and losses", "Understanding option pricing", "Discipline and psychology", "Finding good setups", "Not enough time"], True),
        ("risk", "How much of your capital do you risk on one trade?", "radio",
         ["Under 1%", "1–2%", "2–5%", "More than 5%", "I don't size positions"], True),
        ("journal", "Do you keep a trading journal?", "radio", ["Yes, every trade", "Sometimes", "No"], True),
        ("hours", "Hours a week you can give to markets", "radio", ["Under 2", "2–5", "5–10", "More than 10"], True),
        ("source", "How did you find Finostat?", "radio", ["Google", "YouTube", "X / Twitter", "Instagram", "A friend", "Other"], True),
        ("consent", "I agree that Finostat may store these answers and contact me about my result.", "consent", None, True),
    ]},
]

# Correct option index and the Finch chapter that teaches it.
QUIZ = {
    "q1": (1, "/finch/options-basics", "Options basics"),
    "q2": (2, "/finch/strategies", "Strategies"),
    "q3": (1, "/finch/implied-volatility", "Implied volatility"),
    "q4": (1, "/finch/reading-the-chain", "Reading the chain"),
    "q5": (1, "/finch/option-pricing", "Option pricing"),
    "q6": (1, "/finch/expiry-and-settlement", "Expiry and settlement"),
    "q7": (1, "/finch/risk-and-position-sizing", "Risk and position sizing"),
}

FIELDS = {f[0]: f for s in STEPS for f in s["fields"]}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS assessments(
  id       INTEGER PRIMARY KEY,
  ts       REAL NOT NULL,
  ip       TEXT NOT NULL DEFAULT '',
  name     TEXT NOT NULL,
  email    TEXT NOT NULL,
  phone    TEXT NOT NULL,
  answers  TEXT NOT NULL,
  score    INTEGER NOT NULL,
  profile  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS assessments_email ON assessments(email);
CREATE INDEX IF NOT EXISTS assessments_ip_ts ON assessments(ip, ts);
"""


# ---------------------------------------------------------------------------
# Validation and scoring (pure; tested directly)
# ---------------------------------------------------------------------------
def clean_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", str(raw or ""))
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits if len(digits) == 10 and digits[0] in "6789" else None


def validate(payload: dict) -> tuple[dict | None, str | None]:
    """Return (clean answers, None) or (None, error message)."""
    if not isinstance(payload, dict):
        return None, "expected an object"
    out: dict = {}
    for key, label, kind, options, required in FIELDS.values():
        v = payload.get(key)
        if kind in ("text", "email", "phone"):
            v = str(v or "").strip()
            if required and not v:
                return None, f"{label} is required"
            if len(v) > 120:
                return None, f"{label} is too long"
            if kind == "email" and v and not _EMAIL.match(v):
                return None, "That email address doesn't look right"
            if kind == "phone" and v:
                v = clean_phone(v)
                if v is None:
                    return None, "Enter a 10-digit Indian mobile number"
            out[key] = v.lower() if kind == "email" else v
        elif kind in ("radio", "quiz"):
            try:
                idx = int(v)
            except (TypeError, ValueError):
                idx = -1
            if not 0 <= idx < len(options):
                if required:
                    return None, f"Please answer: {label}"
                idx = None
            out[key] = idx
        elif kind == "check":
            if not isinstance(v, list):
                v = []
            picks = set()
            for x in v:
                try:
                    j = int(x)
                except (TypeError, ValueError):
                    continue
                if 0 <= j < len(options):
                    picks.add(j)
            picks = sorted(picks)
            if required and not picks:
                return None, f"Please answer: {label}"
            out[key] = picks
        elif kind == "consent":
            if required and v is not True:
                return None, "Please tick the consent box to continue"
            out[key] = bool(v)
    return out, None


def score(answers: dict) -> dict:
    """Knowledge score, profile, and a concrete starting point."""
    wrong = []
    for q, (correct, path, title) in QUIZ.items():
        if answers.get(q) != correct:
            wrong.append({"q": q, "question": FIELDS[q][1], "your": FIELDS[q][3][answers[q]] if answers.get(q) is not None else "—",
                          "correct": FIELDS[q][3][correct], "read": path, "chapter": title})
    right = len(QUIZ) - len(wrong)
    years = answers.get("years", 0)                     # 0 never .. 4 five-plus
    never = years == 0 or answers.get("fno_result") == 3
    if never and right < 4:
        profile = "Newcomer"
    elif right < 4:
        profile = "Learner"
    elif right >= 6 and years >= 3:
        profile = "Advanced"
    elif right >= 4 and years >= 1:
        profile = "Practitioner"
    else:
        profile = "Learner"

    flags = []
    if answers.get("risk") in (3, 4):
        flags.append("You risk more than 5% a trade or don't size at all — that is the single most common reason accounts don't survive. Read risk and position sizing before anything else.")
    if answers.get("fno_result") == 2 and answers.get("goal") == 0:
        flags.append("You want regular income from options but have been net negative so far. Income strategies are short-gamma: the losses come from the tail, not the average week. Start with defined-risk structures.")
    if answers.get("journal") == 2:
        flags.append("No journal yet. Start one today — the seven-question checklist in Finch is a journal template.")
    if answers.get("years") == 0 and answers.get("capital", 0) >= 3:
        flags.append("Large capital, no trading history: size your first months as if you had ₹1 lakh. The market will still be there.")

    if profile == "Newcomer":
        start = {"path": "/finch/start-here", "title": "Start here — what F&O is", "why": "Begin at chapter 1 and read Finch in order; it is written for exactly where you are."}
    elif wrong:
        w = wrong[0]
        start = {"path": w["read"], "title": w["chapter"], "why": "The first question you missed is taught in this chapter."}
    else:
        start = {"path": "/dashboard#p-builder", "title": "The strategy builder", "why": "Full marks — go straight to live chains, greeks and payoffs in the terminal."}
    plan = {"Newcomer": "starter", "Learner": "starter", "Practitioner": "desk", "Advanced": "pro"}[profile]
    blurb = {
        "Newcomer": "You are at the start, which is the best place to be honest about it. Finch was written for you: twelve chapters on the live market, free.",
        "Learner": "You have some background, with gaps in the mechanics that cost money. A few chapters of Finch will close them.",
        "Practitioner": "You know how options work and have traded them. The terminal's live chains, greeks and builder are where the edge is now.",
        "Advanced": "Strong fundamentals and real experience. You will get the most out of the builder on stock options and the recorded history.",
    }[profile]
    return {"score": right, "total": len(QUIZ), "profile": profile, "blurb": blurb, "wrong": wrong,
            "start": start, "plan": plan, "flags": flags, "pitch": PITCH[plan]}


# Why the paid plans are worth it, in the result card. One per suggested plan;
# the copy mirrors the homepage plan cards so nobody is promised something else.
PITCH = {
    "starter": {
        "plan": "desk", "name": "Desk", "price": "₹2,199 / month · ₹21,990 a year",
        "head": "When you start trading real money, trade it with the desk's tools",
        "why": "Starter is free and is all you need while you learn. The moment you put capital at risk, the difference between guessing and knowing is the live feed: real-time sheets, the builder priced on every F&O stock, and alerts that email you when your level trades — so you are not glued to a screen or, worse, finding out after the move.",
        "points": ["All sheets live, under 250 ms — Starter is 15-minute delayed", "Strategy builder on every F&O stock, not just the index", "Alert engine: up to 25 rules, evaluated on the server and emailed", "IV percentile, bell curves and the volatility surface, live"],
    },
    "desk": {
        "plan": "desk", "name": "Desk", "price": "₹2,199 / month · ₹21,990 a year",
        "head": "You already trade. Stop trading on delayed numbers.",
        "why": "You know what a straddle is telling you — Desk makes sure you see it before the market moves on. Your knowledge score says the concepts are in place; what usually separates a practitioner from a consistent one is tooling: exact breakevens and max loss before entry, stock-option chains on demand, alerts that watch the level so you don't have to. One avoided oversized trade pays for a year of it.",
        "points": ["Real-time sheets and straddle on NIFTY, BANKNIFTY, SENSEX, FINNIFTY", "Builder on 200+ F&O stocks with live greeks and exact breakevens", "25 server-side alert rules, emailed the second they trigger", "Gamma exposure, skew heatmap, IV percentile — the context behind the price"],
    },
    "pro": {
        "plan": "pro", "name": "Pro desk", "price": "₹5,599 / month · ₹55,990 a year",
        "head": "Your edge now is history and unlimited alerts",
        "why": "At your level the questions are quantitative: how did this structure behave across the last four years of expiries, where did the pin actually land, what did the straddle do into events. Pro adds the recorded tick history and backtesting, unlimited alert rules, the MCX arbitrage scanner and data export, plus a live session with the desk each quarter.",
        "points": ["Tick-by-tick replay and four years of expiry history", "Backtest any structure across past expiries", "Unlimited alert rules; data export and API access", "One live session with the desk every quarter"],
    },
}


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
class Assessments:
    def __init__(self, path: pathlib.Path, per_ip_hour: int = 5):
        self.path = pathlib.Path(path)
        self.per_ip_hour = per_ip_hour
        self._lock = threading.Lock()
        from auth import open_or_quarantine
        open_or_quarantine(self.path, _SCHEMA)
        self._migrate()

    def _migrate(self) -> None:
        """Columns added after the table first shipped."""
        with self._conn() as c:
            cols = {r[1] for r in c.execute("PRAGMA table_info(assessments)")}
            for col, ddl in (("token", "TEXT NOT NULL DEFAULT ''"), ("quote", "TEXT NOT NULL DEFAULT ''"),
                             ("quote_ok", "INTEGER NOT NULL DEFAULT 0")):
                if col not in cols:
                    c.execute(f"ALTER TABLE assessments ADD COLUMN {col} {ddl}")

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def submit(self, payload: dict, ip: str = "") -> tuple[dict | None, str | None, int]:
        """Validate, score, store. Returns (result, error, http status)."""
        answers, err = validate(payload)
        if err:
            return None, err, 400
        with self._lock, self._conn() as c:
            recent = c.execute("SELECT COUNT(*) FROM assessments WHERE ip=? AND ts>?",
                               (ip, time.time() - 3600)).fetchone()[0]
            if ip and recent >= self.per_ip_hour:
                return None, "Too many submissions from this connection; try again later", 429
            result = score(answers)
            token = secrets.token_urlsafe(16)          # lets the result page attach a quote later, nobody else
            cur = c.execute("INSERT INTO assessments(ts,ip,name,email,phone,answers,score,profile,token) VALUES(?,?,?,?,?,?,?,?,?)",
                            (time.time(), ip, answers["name"], answers["email"], answers["phone"],
                             json.dumps(answers, separators=(",", ":")), result["score"], result["profile"], token))
            result["id"] = cur.lastrowid
            result["token"] = token
            result["first"] = answers["name"].split()[0]
            result["city"] = answers.get("city") or ""
        return result, None, 200

    def add_quote(self, aid, token: str, quote: str, allow: bool) -> tuple[dict | None, str | None]:
        """Attach the optional 'may we quote you' line. Needs the submission's token."""
        quote = " ".join(str(quote or "").split())[:280]
        if not quote:
            return None, "Write a line first"
        with self._lock, self._conn() as c:
            row = c.execute("SELECT id,name,email,token,quote FROM assessments WHERE id=?", (aid,)).fetchone()
            if row is None or not token or not secrets.compare_digest(row["token"], str(token)):
                return None, "Not found"
            if row["quote"]:
                return None, "Already sent — thank you"
            c.execute("UPDATE assessments SET quote=?, quote_ok=? WHERE id=?", (quote, 1 if allow else 0, aid))
        return {"name": row["name"], "email": row["email"], "quote": quote, "allow": bool(allow)}, None

    def quotes(self) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id,ts,name,email,answers,quote,quote_ok FROM assessments WHERE quote!='' ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]

    def recent(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT id,ts,name,email,phone,score,profile,answers FROM assessments ORDER BY id DESC LIMIT ?",
                             (limit,)).fetchall()
        return [dict(r) for r in rows]

    def delete(self, aid: int) -> bool:
        with self._lock, self._conn() as c:
            return c.execute("DELETE FROM assessments WHERE id=?", (aid,)).rowcount == 1

    def count(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM assessments").fetchone()[0]

    def export_csv(self) -> str:
        """Every submission, answers expanded to their labels."""
        keys = [f[0] for s in STEPS for f in s["fields"] if f[2] != "consent"]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "submitted", "score", "profile"] + keys)
        with self._conn() as c:
            rows = c.execute("SELECT * FROM assessments ORDER BY id").fetchall()
        for r in rows:
            a = json.loads(r["answers"])
            w.writerow([r["id"], time.strftime("%Y-%m-%d %H:%M", time.localtime(r["ts"])), r["score"], r["profile"]]
                       + [describe(k, a.get(k)) for k in keys])
        return buf.getvalue()


def describe(key: str, value) -> str:
    """Human label for a stored answer."""
    _, _, kind, options, _ = FIELDS[key]
    if kind in ("radio", "quiz"):
        return options[value] if isinstance(value, int) and 0 <= value < len(options) else ""
    if kind == "check":
        return "; ".join(options[i] for i in (value or []) if 0 <= i < len(options))
    return "" if value is None else str(value)


def owner_lines(answers: dict, result: dict) -> list[str]:
    lines = [f"{answers['name']} <{answers['email']}> {answers['phone']}" + (f" · {answers['city']}" if answers.get("city") else ""),
             f"Profile: {result['profile']} — knowledge {result['score']}/{result['total']} — suggested plan: {result['plan']}", ""]
    for s in STEPS[1:]:
        for key, label, kind, _, _ in s["fields"]:
            if kind == "consent":
                continue
            lines.append(f"{label}: {describe(key, answers.get(key))}" + (" ✓" if kind == "quiz" and answers.get(key) == QUIZ[key][0] else (" ✗" if kind == "quiz" else "")))
    lines += ["", "List them all:  fly ssh console --app finostat -C \"python3 /app/server/admin.py assessments\""]
    return lines


# ---------------------------------------------------------------------------
# Markup
# ---------------------------------------------------------------------------
def _esc(s) -> str:
    return html.escape(str(s), quote=True)


def form_html() -> str:
    steps = []
    for i, s in enumerate(STEPS):
        fields = []
        for key, label, kind, options, required in s["fields"]:
            req = ' data-req="1"' if required else ""
            if kind in ("text", "email", "phone"):
                typ = {"text": "text", "email": "email", "phone": "tel"}[kind]
                ac = {"name": "name", "email": "email", "phone": "tel", "city": "address-level2"}.get(key, "off")
                fields.append(f'<label class="fa-f"{req} data-key="{key}"><span>{_esc(label)}{"" if required else " <small>optional</small>"}</span>'
                              f'<input type="{typ}" name="{key}" autocomplete="{ac}" maxlength="120"{" inputmode=numeric placeholder=10-digit mobile" if kind == "phone" else ""}></label>')
            elif kind in ("radio", "quiz", "check"):
                typ = "checkbox" if kind == "check" else "radio"
                opts = "".join(f'<label class="fa-o"><input type="{typ}" name="{key}" value="{j}"><i></i>{_esc(o)}</label>'
                               for j, o in enumerate(options))
                cls = "fa-f fa-q" if kind == "quiz" else "fa-f"
                fields.append(f'<div class="{cls}"{req} data-key="{key}"><span>{_esc(label)}</span><div class="fa-opts">{opts}</div></div>')
            elif kind == "consent":
                fields.append(f'<label class="fa-f fa-consent"{req} data-key="{key}"><input type="checkbox" name="{key}" value="1"><i></i><span>{_esc(label)}</span></label>')
        steps.append(f'<section class="fa-step" data-step="{i}"{"" if i == 0 else " hidden"}><h3><em>{i + 1}/{len(STEPS)}</em>{_esc(s["title"])}</h3><p class="fa-hint">{_esc(s["hint"])}</p>{"".join(fields)}</section>')
    return (f'<form class="fa-form" novalidate autocomplete="on"><div class="fa-bar"><i style="width:{100 // len(STEPS)}%"></i></div>'
            + "".join(steps)
            + '<div class="fa-err" hidden></div>'
            '<div class="fa-nav"><button type="button" class="fa-btn ghost" data-act="back" hidden>← Back</button>'
            '<button type="button" class="fa-btn ghost" data-act="skip">Skip for now</button>'
            '<button type="button" class="fa-btn primary" data-act="next">Continue →</button></div></form>'
            '<div class="fa-result" hidden></div>')


CSS = """
.fa-modal{position:fixed;inset:0;z-index:1000;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(6,3,20,.78);backdrop-filter:blur(6px)}
.fa-modal[hidden]{display:none}
.fa-card{position:relative;width:100%;max-width:640px;max-height:calc(100vh - 32px);overflow:auto;background:var(--panel,#120a33);border:1px solid var(--line-strong,#4a34a0);box-shadow:0 30px 80px rgba(0,0,0,.6);font-family:var(--body,"IBM Plex Sans",system-ui,sans-serif);color:var(--text,#f1edff)}
.fa-hd{display:flex;align-items:center;gap:12px;padding:9px 14px;background:var(--panel-hd,#1c1052);border-bottom:1px solid var(--line-strong,#4a34a0);font-family:var(--mono,ui-monospace,monospace);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;position:sticky;top:0;z-index:2}
.fa-hd .k{color:var(--gold,#f5c842);font-weight:600}.fa-hd .s{color:var(--cyan,#7fe0f0)}.fa-hd .x{margin-left:auto;background:none;border:0;color:var(--muted,#a89ccf);font-size:18px;cursor:pointer;line-height:1}
.fa-body{padding:18px 20px 22px}
.fa-intro h2{font-family:var(--display,"Barlow Condensed",Impact,sans-serif);font-size:30px;line-height:1;letter-spacing:.01em;text-transform:uppercase;margin:0 0 8px}
.fa-intro p{color:var(--muted,#a89ccf);font-size:14.5px;line-height:1.6;margin:0 0 10px}
.fa-bar{height:3px;background:var(--line,#2c1c66);margin:0 0 18px}.fa-bar i{display:block;height:100%;background:linear-gradient(90deg,var(--gold,#f5c842),var(--cyan,#7fe0f0));transition:width .3s}
.fa-step h3{font-family:var(--display,"Barlow Condensed",Impact,sans-serif);font-size:24px;text-transform:uppercase;letter-spacing:.02em;margin:0 0 4px}.fa-step h3 em{font-style:normal;color:var(--gold,#f5c842);margin-right:10px;font-family:var(--mono,monospace);font-size:13px}
.fa-hint{color:var(--muted,#a89ccf);font-size:13px;margin:0 0 16px}
.fa-f{display:block;margin:0 0 16px}.fa-f>span{display:block;font-size:14px;font-weight:500;margin-bottom:8px;line-height:1.45}.fa-f>span small{color:var(--faint,#6d609e);font-weight:400;font-family:var(--mono,monospace);font-size:11px}
.fa-f input[type=text],.fa-f input[type=email],.fa-f input[type=tel]{width:100%;background:var(--bg,#0c0626);border:1px solid var(--line-strong,#4a34a0);color:var(--text,#f1edff);padding:10px 12px;font:inherit;font-size:15px;outline:0}
.fa-f input:focus{border-color:var(--gold,#f5c842)}
.fa-opts{display:grid;grid-template-columns:1fr 1fr;gap:6px}.fa-q .fa-opts{grid-template-columns:1fr}
.fa-o{display:flex;align-items:center;gap:9px;padding:9px 11px;border:1px solid var(--line,#2c1c66);background:rgba(12,6,38,.5);cursor:pointer;font-size:13.5px;line-height:1.35;transition:.12s}
.fa-o:hover{border-color:var(--line-strong,#4a34a0)}.fa-o input{position:absolute;opacity:0;width:0;height:0}.fa-o i{flex:none;width:14px;height:14px;border:1px solid var(--faint,#6d609e);border-radius:50%}
.fa-o input[type=checkbox]+i{border-radius:2px}.fa-o input:checked+i{background:var(--gold,#f5c842);border-color:var(--gold,#f5c842);box-shadow:inset 0 0 0 3px var(--panel,#120a33)}
.fa-o:has(input:checked){border-color:var(--gold,#f5c842);background:rgba(245,200,66,.08)}
.fa-consent{display:flex;gap:10px;align-items:flex-start;font-size:13px;color:var(--muted,#a89ccf);cursor:pointer;margin-top:6px}.fa-consent input{position:absolute;opacity:0;width:0;height:0}.fa-consent i{flex:none;width:16px;height:16px;border:1px solid var(--faint,#6d609e);margin-top:2px}.fa-consent input:checked+i{background:var(--gold,#f5c842);border-color:var(--gold,#f5c842);box-shadow:inset 0 0 0 3px var(--panel,#120a33)}.fa-consent a{color:var(--cyan,#7fe0f0)}
.fa-f.bad>span,.fa-f.bad>input{color:var(--down,#ff5c6c);border-color:var(--down,#ff5c6c)}
.fa-err{color:var(--down,#ff5c6c);font-family:var(--mono,monospace);font-size:12px;margin:0 0 12px}
.fa-nav{display:flex;gap:8px;align-items:center;margin-top:8px;flex-wrap:wrap}.fa-nav [data-act=next]{margin-left:auto}
.fa-btn{display:inline-flex;align-items:center;gap:8px;font-family:var(--mono,monospace);font-size:12px;letter-spacing:.08em;text-transform:uppercase;padding:10px 16px;border:1px solid var(--line-strong,#4a34a0);background:none;color:var(--text,#f1edff);cursor:pointer;transition:.15s;text-decoration:none}
.fa-btn:hover{border-color:var(--gold,#f5c842);color:var(--gold,#f5c842)}.fa-btn.ghost{color:var(--muted,#a89ccf)}
.fa-btn.primary{background:linear-gradient(180deg,var(--gold-2,#ffe27a),#f2b830);color:#2a1a02;border-color:var(--gold,#f5c842);font-weight:600}.fa-btn.primary:hover{filter:brightness(1.08);color:#000}.fa-btn[disabled]{opacity:.5;cursor:wait}
.fa-result .prof{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:0 0 16px}.fa-result .prof div{padding:12px 14px;background:var(--bg,#0c0626);border:1px solid var(--line,#2c1c66)}.fa-result .prof small{display:block;font-family:var(--mono,monospace);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint,#6d609e);margin-bottom:6px}.fa-result .prof b{font-family:var(--display,"Barlow Condensed",Impact,sans-serif);font-size:30px;line-height:1;color:var(--gold,#f5c842);text-transform:uppercase}
.fa-result p{font-size:14.5px;line-height:1.6;color:var(--muted,#a89ccf);margin:0 0 12px}.fa-result h4{font-family:var(--mono,monospace);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--cyan,#7fe0f0);margin:16px 0 8px}
.fa-result .start{display:block;padding:14px 16px;border:1px solid var(--gold,#f5c842);background:rgba(245,200,66,.07);color:var(--text,#f1edff);text-decoration:none;margin:0 0 6px}.fa-result .start b{display:block;font-family:var(--display,"Barlow Condensed",Impact,sans-serif);font-size:22px;text-transform:uppercase;color:var(--gold,#f5c842)}.fa-result .start span{font-size:13px;color:var(--muted,#a89ccf)}
.fa-result ul{list-style:none;padding:0;margin:0}.fa-result li{padding:9px 0;border-top:1px solid var(--line,#2c1c66);font-size:13.5px;line-height:1.5}.fa-result li em{font-style:normal;color:var(--down,#ff5c6c)}.fa-result li b{color:var(--up,#3dd68c);font-weight:500}.fa-result li a{color:var(--cyan,#7fe0f0);font-family:var(--mono,monospace);font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;text-decoration:none;white-space:nowrap}
.fa-result .flag{padding:10px 12px;border-left:3px solid var(--down,#ff5c6c);background:rgba(255,92,108,.07);font-size:13.5px;line-height:1.5;margin:0 0 8px}
.fa-result .pitch{margin:4px 0 14px;padding:16px 18px;border:1px solid var(--line-strong,#4a34a0);background:linear-gradient(180deg,rgba(106,53,240,.18),rgba(12,6,38,.6))}.fa-result .pitch small{display:block;font-family:var(--mono,monospace);font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--cyan,#7fe0f0);margin-bottom:6px}.fa-result .pitch b{display:block;font-family:var(--display,"Barlow Condensed",Impact,sans-serif);font-size:24px;line-height:1.05;text-transform:uppercase;color:var(--gold,#f5c842);margin-bottom:8px}.fa-result .pitch ul{margin:0 0 12px}.fa-result .pitch li{border:0;padding:4px 0 4px 18px;position:relative;color:var(--text,#f1edff)}.fa-result .pitch li::before{content:"▸";position:absolute;left:0;color:var(--gold,#f5c842)}.fa-result .pitch em{display:block;font-style:normal;font-size:12px;color:var(--faint,#6d609e);margin-top:10px}
.fa-result .quote{margin:8px 0 14px;padding:14px 16px;border:1px dashed var(--line-strong,#4a34a0)}.fa-result .quote h4{margin-top:0}.fa-result .quote textarea{width:100%;background:var(--bg,#0c0626);border:1px solid var(--line-strong,#4a34a0);color:var(--text,#f1edff);padding:10px 12px;font:inherit;font-size:14px;outline:0;resize:vertical;margin:0 0 10px}.fa-result .quote textarea:focus{border-color:var(--gold,#f5c842)}.fa-result .quote .fa-nav{margin-top:10px}
@media(max-width:560px){.fa-opts{grid-template-columns:1fr}.fa-result .prof{grid-template-columns:1fr}.fa-body{padding:14px 14px 18px}.fa-intro h2{font-size:26px}}
"""

JS = r"""
(function(){
"use strict";
var root=document.getElementById('fa-root'); if(!root) return;
var mode=root.getAttribute('data-mode'), modal=root.querySelector('.fa-modal');
var KEY='fino_assess';
function stored(){ try{ return JSON.parse(localStorage.getItem(KEY)||'null'); }catch(e){ return null; } }
function store(v){ try{ localStorage.setItem(KEY, JSON.stringify(v)); }catch(e){} }
function esc(s){ return String(s).replace(/[&<>"]/g,function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
function open_(){ if(modal){ modal.hidden=false; document.body.style.overflow='hidden'; } }
function close_(){ if(modal){ modal.hidden=true; document.body.style.overflow=''; } }
function wire(card){
  var form=card.querySelector('.fa-form'), steps=card.querySelectorAll('.fa-step'), bar=card.querySelector('.fa-bar i'), err=card.querySelector('.fa-err'), res=card.querySelector('.fa-result'), intro=card.querySelector('.fa-intro');
  var back=card.querySelector('[data-act=back]'), skip=card.querySelector('[data-act=skip]'), next=card.querySelector('[data-act=next]'); var cur=0;
  function show(i){ cur=i; Array.prototype.forEach.call(steps,function(s,j){ s.hidden=j!==i; }); bar.style.width=Math.round((i+1)/steps.length*100)+'%'; back.hidden=i===0; next.textContent=i===steps.length-1?'See my result →':'Continue →'; err.hidden=true; card.scrollTop=0; if(intro) intro.hidden=i>0; }
  function value(f){ var k=f.getAttribute('data-key'), els=f.querySelectorAll('[name="'+k+'"]'), e0=els[0]; if(!e0) return null;
    if(e0.type==='checkbox'&&els.length===1&&f.classList.contains('fa-consent')) return e0.checked;
    if(e0.type==='checkbox'){ var out=[]; Array.prototype.forEach.call(els,function(e){ if(e.checked) out.push(+e.value); }); return out; }
    if(e0.type==='radio'){ var v=null; Array.prototype.forEach.call(els,function(e){ if(e.checked) v=+e.value; }); return v; }
    return e0.value.trim(); }
  function validStep(i){ var ok=true, first=null; Array.prototype.forEach.call(steps[i].querySelectorAll('.fa-f'),function(f){ var v=value(f), req=f.getAttribute('data-req')==='1', bad=false;
      if(req){ if(v===null||v===''||v===false||(Array.isArray(v)&&!v.length)) bad=true; }
      var inp=f.querySelector('input[type=email],input[type=tel]');
      if(!bad&&inp&&inp.type==='email'&&v&&!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(v)) bad=true;
      if(!bad&&inp&&inp.type==='tel'&&v){ var d=v.replace(/\D/g,''); if(d.length===12&&d.slice(0,2)==='91') d=d.slice(2); if(d.length===11&&d[0]==='0') d=d.slice(1); if(!(d.length===10&&/[6-9]/.test(d[0]))) bad=true; }
      f.classList.toggle('bad',bad); if(bad){ ok=false; first=first||f; } });
    if(!ok){ err.textContent=i===0?'Please fill in your name, a valid email and a 10-digit mobile number.':'Please answer every question on this step.'; err.hidden=false; if(first) first.scrollIntoView({block:'center',behavior:'smooth'}); }
    return ok; }
  function collect(){ var o={}; Array.prototype.forEach.call(card.querySelectorAll('.fa-f'),function(f){ o[f.getAttribute('data-key')]=value(f); }); return o; }
  function render(r){ form.hidden=true; if(intro) intro.hidden=true; res.hidden=false;
    var h='<div class="prof"><div><small>Your profile</small><b>'+esc(r.profile)+'</b></div><div><small>Knowledge check</small><b>'+r.score+' / '+r.total+'</b></div></div><p>'+esc(r.blurb)+'</p>';
    (r.flags||[]).forEach(function(f){ h+='<div class="flag">'+esc(f)+'</div>'; });
    h+='<h4>Start here</h4><a class="start" href="'+esc(r.start.path)+'"><b>'+esc(r.start.title)+'</b><span>'+esc(r.start.why)+'</span></a>';
    if(r.wrong&&r.wrong.length){ h+='<h4>What you missed</h4><ul>'+r.wrong.map(function(w){ return '<li>'+esc(w.question)+'<br><em>You said: '+esc(w.your)+'</em> · <b>'+esc(w.correct)+'</b> · <a href="'+esc(w.read)+'">Read: '+esc(w.chapter)+' →</a></li>'; }).join('')+'</ul>'; }
    h+='<h4>Suggested plan</h4><p>'+(r.plan==='starter'?'Starter (free) is enough for now: Finch, the delayed sheets and the index builder. Learn on it; it costs nothing.':r.plan==='desk'?'Desk — the full live terminal for the active expiry trader.':'Pro desk — everything live, plus four years of expiry history.')+'</p>';
    if(r.pitch){ var pp=r.pitch; h+='<div class="pitch"><small>'+esc(pp.name)+' · '+esc(pp.price)+'</small><b>'+esc(pp.head)+'</b><p>'+esc(pp.why)+'</p><ul>'+pp.points.map(function(x){ return '<li>'+esc(x)+'</li>'; }).join('')+'</ul><div class="fa-nav"><a class="fa-btn primary" href="/login">Start with '+esc(pp.name)+' →</a><a class="fa-btn ghost" href="/#plans">Compare plans</a></div><em>No card needed to sign in. Request the upgrade from the terminal and we switch it on the same day; cancel any time.</em></div>'; }
    h+='<div class="fa-nav"><a class="fa-btn primary" href="'+esc(r.start.path)+'">Go →</a><a class="fa-btn ghost" href="/finch">All Finch chapters</a>'+(mode==='modal'?'<button type="button" class="fa-btn ghost" data-act="close">Close</button>':'')+'</div>';
    h+='<div class="quote" id="fa-quote"><h4>One more thing</h4><p>What would make Finostat worth your time? One honest line — good or bad. If you tick the box we may show it on the homepage as “'+esc((r.first||'you'))+', '+esc(r.city||'India')+'”.</p><textarea maxlength="280" rows="3" placeholder="e.g. I want alerts that email me when my level trades, and a course that uses today\'s chain."></textarea><label class="fa-consent"><input type="checkbox"><i></i><span>You may quote me on finostat.com (first name and city only)</span></label><div class="fa-nav"><button type="button" class="fa-btn ghost" data-act="quote">Send →</button><span class="fa-err" hidden></span></div></div>';
    res.innerHTML=h; var c=res.querySelector('[data-act=close]'); if(c) c.addEventListener('click',close_);
    var qb=res.querySelector('#fa-quote'); if(qb){ var qbtn=qb.querySelector('[data-act=quote]'), qerr=qb.querySelector('.fa-err'); qbtn.addEventListener('click',function(){ var text=qb.querySelector('textarea').value.trim(); if(!text){ qerr.textContent='Write a line first.'; qerr.hidden=false; return; } qbtn.disabled=true;
      fetch('/api/assessment/quote',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify({id:r.id,token:r.token,quote:text,allow:qb.querySelector('input').checked})}).then(function(x){ return x.json().then(function(d){ return {ok:x.ok,d:d}; }); }).then(function(x){ if(!x.ok){ qbtn.disabled=false; qerr.textContent=x.d.error||'Try again'; qerr.hidden=false; return; } qb.innerHTML='<h4>Thank you</h4><p>Got it. If you said we may quote you, we will ask before we do.</p>'; }).catch(function(){ qbtn.disabled=false; qerr.textContent='Network error'; qerr.hidden=false; }); }); } }
  back.addEventListener('click',function(){ if(cur>0) show(cur-1); });
  skip.addEventListener('click',function(){ store({skipped:Date.now()}); if(mode==='modal') close_(); else location.href='/'; });
  next.addEventListener('click',function(){ if(!validStep(cur)) return; if(cur<steps.length-1){ show(cur+1); return; }
    next.disabled=true; err.hidden=true;
    fetch('/api/assessment',{method:'POST',headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},body:JSON.stringify(collect())}).then(function(r){ return r.json().then(function(d){ return {ok:r.ok,d:d}; }); }).then(function(x){ next.disabled=false;
      if(!x.ok){ err.textContent=x.d&&x.d.error?x.d.error:'Something went wrong; please try again.'; err.hidden=false; return; }
      store({done:Date.now(),profile:x.d.profile,score:x.d.score,start:x.d.start&&x.d.start.path}); render(x.d); }).catch(function(){ next.disabled=false; err.textContent='Network error; please try again.'; err.hidden=false; }); });
  form.addEventListener('keydown',function(e){ if(e.key==='Enter'&&e.target&&e.target.tagName==='INPUT'&&e.target.type!=='checkbox'&&e.target.type!=='radio'){ e.preventDefault(); next.click(); } });
  show(0);
}
wire(root.querySelector('.fa-card'));
if(mode==='modal'){
  var s=stored(), fresh=!s||(s.skipped&&Date.now()-s.skipped>7*864e5);
  var x=root.querySelector('.fa-hd .x'); if(x) x.addEventListener('click',function(){ store({skipped:Date.now()}); close_(); });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape'&&modal&&!modal.hidden){ store({skipped:Date.now()}); close_(); } });
  modal.addEventListener('click',function(e){ if(e.target===modal){ store({skipped:Date.now()}); close_(); } });
  if(fresh&&location.pathname==='/'&&!location.hash) setTimeout(open_,1400);
  var link=document.getElementById('fa-open'); if(link){ if(s&&s.done) link.textContent=s.profile?'Profile: '+s.profile:'My profile'; link.addEventListener('click',function(e){ e.preventDefault(); if(s&&s.done&&s.start){ location.href=s.start; } else open_(); }); }
}
})();
"""

_INTRO = ('<div class="fa-intro"><h2>Two minutes, then a plan</h2>'
          '<p>Tell us where you are as a trader and answer seven quick questions. You get a profile, the exact Finch chapter to start with, '
          'and the plan that fits — nothing is sold to you on the way.</p></div>')


def widget_html() -> str:
    """The homepage modal: injected before </body> on /."""
    return (f'<div id="fa-root" data-mode="modal"><style>{CSS}</style><div class="fa-modal" hidden role="dialog" aria-modal="true" aria-label="Trader assessment">'
            f'<div class="fa-card"><div class="fa-hd"><span class="k">ASSESS</span><span class="s">TRADER ASSESSMENT</span><span>FREE · 2 MIN</span><button class="x" type="button" aria-label="Close">×</button></div>'
            f'<div class="fa-body">{_INTRO}{form_html()}</div></div></div><script>{JS}</script></div>')


def render_page() -> bytes:
    """Standalone /assessment page (same form, inline)."""
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Trader assessment — Finostat</title><meta name="description" content="A two-minute trader assessment: your experience, a seven-question options knowledge check, and a personal starting point in Finch."><meta name="theme-color" content="#0c0626">
<link rel="icon" href="/og.jpg"><link rel="canonical" href="https://finostat.com/assessment">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>:root{{--bg:#0c0626;--panel:#120a33;--panel-hd:#1c1052;--line:#2c1c66;--line-strong:#4a34a0;--gold:#f5c842;--gold-2:#ffe27a;--cyan:#7fe0f0;--up:#3dd68c;--down:#ff5c6c;--text:#f1edff;--muted:#a89ccf;--faint:#6d609e;--display:"Barlow Condensed",Impact,sans-serif;--body:"IBM Plex Sans",system-ui,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}}
*{{box-sizing:border-box;margin:0;padding:0}}html{{background:var(--bg)}}body{{font-family:var(--body);color:var(--text);background:radial-gradient(ellipse 70% 45% at 50% 0%,rgba(122,60,245,.5),transparent 70%),var(--bg);min-height:100vh}}
.top{{display:flex;align-items:center;justify-content:space-between;padding:12px 18px;border-bottom:1px solid var(--line);font-family:var(--mono);font-size:12px;letter-spacing:.1em;text-transform:uppercase}}.top a{{color:var(--muted);text-decoration:none;margin-left:16px}}.top .logo{{color:var(--gold);font-family:var(--display);font-size:20px;letter-spacing:.06em;margin:0}}
.wrap{{max-width:680px;margin:32px auto;padding:0 16px}}{CSS}
.fa-card{{max-height:none}}</style></head><body>
<header class="top"><a class="logo" href="/">FINOSTAT</a><div><a href="/finch">Finch</a><a href="/dashboard">Terminal</a></div></header>
<main class="wrap"><div id="fa-root" data-mode="page"><div class="fa-card"><div class="fa-hd"><span class="k">ASSESS</span><span class="s">TRADER ASSESSMENT</span><span>FREE · 2 MIN</span></div><div class="fa-body">{_INTRO}{form_html()}</div></div></div></main>
<script>{JS}</script></body></html>"""
    return doc.encode("utf-8")
