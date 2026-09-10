"""The live terminal is Desk-only: locked rendering, entitlement, API gating list."""
import sys, pathlib, os, tempfile
os.environ["FINOSTAT_FEED"]="simulator"; os.environ["FINOSTAT_UNIVERSE"]="none"; os.environ["FINOSTAT_DATA_DIR"]=tempfile.mkdtemp()
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import auth as A, pages
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1
print("=== entitlement ===")
check("terminal needs desk", not A.entitled("starter", "terminal") and A.entitled("desk", "terminal") and A.entitled("pro", "terminal"))
check("finch's index builder stays free", A.entitled("starter", "builder_index"))
snap = {"sheet": {"rows": [[24500, 316.2, 28.7, 52.8, -13.9]]}, "quotes": [{"symbol": "NIFTY 50", "price": 23650.0, "change": 0.1}], "mini": [], "atm": 24500, "straddle": 200.0, "live": True, "symbol": "NIFTY"}
print("\n=== rendering ===")
open_ = pages.render_dashboard(snap).decode()
check("paid render has no paywall and no lock guard", "class=\"paywall\"" not in open_ and "window.FINO_LOCKED=true" not in open_)
check("chart panel present, TradingView loaded lazily, symbol map covers indices", 'id="p-chart"' in open_ and "s3.tradingview.com/tv.js" in open_ and "'NIFTY 50':'NSE:NIFTY'" in open_ and "'SENSEX':'BSE:SENSEX'" in open_ and "['chart','Chart']" in open_)
check("locked page never loads TradingView", "window.FINO_LOCKED||chPanel.hidden" in open_)
anon = pages.render_dashboard(snap, locked=True, signed_in=False).decode()
check("anonymous lock: card, sign-in CTA, blur css, network guard", all(x in anon for x in ('class="paywall"', "Sign in &amp; get Desk", "filter:blur(7px)", "window.FINO_LOCKED=true", 'window.fetch=function(){return Promise.reject', "window.EventSource=function()")))
check("guard runs before the app scripts", anon.index("window.FINO_LOCKED=true") < anon.index("window.SEED="))
check("seed still present so the blurred panels have content", "24500" in anon)
starter = pages.render_dashboard(snap, locked=True, signed_in=True, plan="starter").decode()
check("signed-in starter lock: account CTA", "Your account is on Starter" in starter and 'href="/account?plan=desk"' in starter)
lapsed = pages.render_dashboard(snap, locked=True, signed_in=True, plan="starter").decode()
check("prices on the card", "₹2,199" in starter and "₹21,990" in starter and "₹5,599" in starter)
import app
check("terminal API gate list covers the streams and search", {"/api/sheet/stream", "/api/news/stream", "/api/symbols", "/api/quote", "/api/alerts"} <= app.TERMINAL_APIS)
check("finch's endpoints are not gated", not ({"/api/quotes", "/api/chain", "/api/strategy"} & app.TERMINAL_APIS))
check("_paid: anonymous no, desk yes, expired no", not app._paid(None) and app._paid({"plan": "desk"}) and not app._paid({"plan": "starter"}))
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
