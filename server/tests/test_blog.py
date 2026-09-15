"""Blog content engine: generators from fake sources, store, scheduler due-logic, pages, feed, sitemap."""
import os, sys, tempfile, pathlib
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from datetime import date, datetime
import blog, blog_content

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + label + (("  " + str(extra)) if extra and not ok else ""))
    if not ok: fails += 1

SRC = {
    "quotes": lambda: [{"symbol": "NIFTY 50", "price": 23118.6, "change": -1.19}, {"symbol": "BANKNIFTY", "price": 55794.8, "change": -1.43}, {"symbol": "INDIA VIX", "price": 13.4, "change": 9.3}],
    "chain": lambda slug: {"expiry": "16-Sep-2026", "stats": {"pcr": 1.06, "max_pain": 23200, "call_wall": 23500, "put_wall": 23000, "atm": 23100}} if slug == "nifty" else None,
    "oiscan": lambda u: {"read": {"text": "bearish lean — call writing at 23,300 / 23,500 (supply)"}, "ce_d": 120000, "pe_d": -45000, "pcr": 1.06, "pcr_then": 1.21} if u == "NIFTY 50" else {},
    "move": lambda u: {"expected": {"em_day": 180, "em_expiry_straddle": 150, "iv": 13.8}, "realised": {"range": 310}, "compare": {"range_vs_expected_pct": 86, "verdict": "in line with expected"}} if u == "NIFTY 50" else {},
    "ivp": lambda u: {"pct_percentile": 72, "cycles": 20, "read": "rich — straddle above most cycles at this time"} if u == "NIFTY 50" else None,
    "gold": lambda: {"spot": 4350.2, "inr_10g": 123400, "signals": {"1d": "NEUTRAL", "4h": "SELL"}},
    "flows": lambda: {"cash_date": "2026-09-15", "fii_net": -2143.5, "dii_net": 3011.2, "fii_fut": -98000},
    "flows_week": lambda: {"fii_net": -8100, "dii_net": 9400, "days": 5},
    "events": lambda days: [{"title": "FOMC decision", "country": "USD", "date": "2026-09-16", "when": "23:30"}, {"title": "India WPI", "country": "INR", "date": "2026-09-16", "when": "12:00"}],
    "expiries": lambda: [{"date": "2026-09-16", "label": "NIFTY", "kind": "weekly", "note": ""}, {"date": "2026-09-18", "label": "SENSEX", "kind": "weekly", "note": ""}],
    "week_change": lambda: {"NIFTY 50": {"close": 23118.6, "pct": -1.8, "high": 23600, "low": 23050}},
}
db = pathlib.Path(tempfile.mkdtemp()) / "auth.db"
B = blog.Blog(db, SRC, holidays=None, clock=lambda: datetime(2026, 9, 15, 18, 35, tzinfo=blog.IST))

d = blog.daily_read(SRC, date(2026, 9, 15))
check("daily: title/slug/body", d["slug"] == "desk-read-2026-09-15" and "23,119" in d["title"] and "PCR" in d["body"] and "23,500" in d["body"] and "bearish lean" in d["body"] and "±180" in d["body"] and "72th" in d["body"] and "XAU Sovereign" in d["body"] and "FOMC" in d["body"] and "₹-2,144" in d["body"].replace("−", "-"))
check("daily: missing sources just drop paragraphs", "BANKNIFTY option chain" not in d["body"] and "NIFTY option chain" in d["body"])
check("daily: no quotes -> None", blog.daily_read({"quotes": lambda: []}, date(2026, 9, 15)) is None)
w = blog.week_ahead(SRC, date(2026, 9, 13))
check("week ahead: next monday slug, events, expiries, flows", w["slug"] == "week-ahead-2026-09-14" and "FOMC" in w["body"] and "SENSEX" in w["body"] and "-8,100" in w["body"].replace("−", "-"))
wr = blog.weekly_wrap(SRC, date(2026, 9, 18))
check("weekly wrap", wr["slug"] == "weekly-wrap-2026-09-18" and "-1.80%" in wr["body"] and "max pain" in wr["body"])

# store + due + run
check("due at 18:35 on a Tuesday = daily only", B.due() == ["daily"])
p = B.run("daily")
check("run daily stores the post", p and B.has("desk-read-2026-09-15") and B.due() == [] and B.get("desk-read-2026-09-15")["kind"] == "daily")
B2 = blog.Blog(db, SRC, clock=lambda: datetime(2026, 9, 18, 17, 40, tzinfo=blog.IST))
check("friday 17:40 -> wrap due (daily waits for 18:30)", B2.due() == ["wrap"])
B3 = blog.Blog(db, SRC, clock=lambda: datetime(2026, 9, 20, 18, 5, tzinfo=blog.IST))
check("sunday 18:05 -> week ahead due only", B3.due() == ["ahead"])
B3.run("ahead"); B2.run("wrap")
check("recent lists newest first with kinds", [x["kind"] for x in B.recent()][:1] == ["weekly"] and len(B.recent()) == 3 and len(B.recent(kind="daily")) == 1)
B.put(p)
check("put is idempotent", len(B.recent()) == 3)
class Hol:
    def dates(self): return {"2026-09-15"}
B4 = blog.Blog(db, SRC, holidays=Hol(), clock=lambda: datetime(2026, 9, 15, 19, 0, tzinfo=blog.IST))
check("holiday -> no daily due", "daily" not in B4.due())

# pages
idx = blog.render_index(B).decode()
check("index: guides + posts + CTA + schema", all(g["slug"] in idx for g in blog_content.GUIDES) and "desk-read-2026-09-15" in idx and "/vip-indicator" in idx and '"@type":"Blog"' in idx and "feed.xml" in idx)
post = blog.render_post(B, "desk-read-2026-09-15").decode()
check("post: article schema, CTA twice, breadcrumbs, disclaimer", '"@type":"Article"' in post and post.count('class="cta-grid"') == 2 and "BreadcrumbList" in post and "investment advice" in post and "Keep reading" in post)
g = blog.render_post(B, "how-to-read-an-option-chain").decode()
check("guide renders with VIP link", g and "/vip-indicator" in g and "max pain" in g.lower())
check("unknown slug -> None", blog.render_post(B, "nope") is None)
check("guides each link a product and are substantial", all(("/vip-indicator" in x["body"] or "/xau-sovereign" in x["body"]) and len(x["body"]) > 1200 for x in blog_content.GUIDES) and len(blog_content.GUIDES) >= 10)
feed = blog.render_feed(B).decode()
check("rss: posts + guides", feed.startswith('<?xml') and feed.count("<item>") == 3 + len(blog_content.GUIDES) and "pubDate" in feed)
sm = blog.sitemap_entries(B)
check("sitemap: index + guides + posts", sm.count("<loc>") == 1 + len(blog_content.GUIDES) + 3 and "/blog/desk-read-2026-09-15" in sm)
print("fails:", fails)
sys.exit(1 if fails else 0)
