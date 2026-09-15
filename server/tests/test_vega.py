"""Vega chat: message cleaning, prompt grounding, API transport handling, rate limit, widget injection."""
import os, sys, tempfile, pathlib, json, urllib.error, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import vega, vega_widget

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + label + (("  " + str(extra)) if extra and not ok else ""))
    if not ok: fails += 1

m = vega.clean_messages([{"role": "assistant", "content": "hi"}, {"role": "user", "content": "a"}, {"role": "user", "content": "b"}, {"role": "assistant", "content": "c"}, {"role": "user", "content": " q "}])
check("clean: drops leading assistant, merges same-role, ends with user", m == [{"role": "user", "content": "a\nb"}, {"role": "assistant", "content": "c"}, {"role": "user", "content": "q"}], m)
check("clean: empty / trailing assistant -> []", vega.clean_messages([]) == [] and vega.clean_messages([{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]) == [])
check("clean: caps history and length", len(vega.clean_messages([{"role": "user" if i % 2 == 0 else "assistant", "content": "x" * 5000} for i in range(40)])) <= vega.MAX_TURNS and all(len(x["content"]) <= vega.MAX_CHARS * 2 for x in vega.clean_messages([{"role": "user", "content": "x" * 5000}])))

ctx = {"india": {"quotes": {"NIFTY 50": {"price": 23456.7}}}, "gold": {"xau_sovereign": {"1d": {"signal": "SELL"}}}}
sp = vega.system_prompt(ctx)
check("prompt carries knowledge + live json", "Vega" in sp and "23456.7" in sp and "XAU Sovereign" in sp and "not a SEBI" in sp)

seen = {}
def fake(payload, timeout):
    seen.update(payload); return {"content": [{"type": "text", "text": "NIFTY is at 23,456.7 — see /dashboard."}]}
r = vega.ask([{"role": "user", "content": "nifty?"}], ctx, transport=fake)
check("ask: payload shape + reply text", seen["model"] and seen["max_tokens"] == vega.MAX_TOKENS and "23456.7" in seen["system"] and seen["messages"][0]["role"] == "user" and r.startswith("NIFTY"))
os.environ.pop("ANTHROPIC_API_KEY", None)
check("no key -> offline message, no network", vega.ask([{"role": "user", "content": "x"}], ctx) == vega.OFFLINE)
def boom(payload, timeout):
    raise urllib.error.HTTPError("u", 429, "rate", {}, io.BytesIO(b"{}"))
check("429 -> busy message", "busy" in vega.ask([{"role": "user", "content": "x"}], ctx, transport=boom))
def boom401(payload, timeout):
    raise urllib.error.HTTPError("u", 401, "auth", {}, io.BytesIO(b"{}"))
check("401 -> key rejected message", "rejected" in vega.ask([{"role": "user", "content": "x"}], ctx, transport=boom401))

db = pathlib.Path(tempfile.mkdtemp()) / "auth.db"
V = vega.Vega(db, per_ip=3, window=600)
out = V.chat([{"role": "user", "content": "what is max pain?"}], ctx, ip="1.2.3.4", user_id=None, page="/", transport=fake)
check("chat: reply + logged", out.get("reply") and out["name"] == "Vega" and V.recent(1)[0]["question"] == "what is max pain?" and V.recent(1)[0]["page"] == "/")
V.chat([{"role": "user", "content": "2"}], ctx, ip="1.2.3.4", transport=fake); V.chat([{"role": "user", "content": "3"}], ctx, ip="1.2.3.4", transport=fake)
check("rate limit per ip", "breather" in V.chat([{"role": "user", "content": "4"}], ctx, ip="1.2.3.4", transport=fake).get("error", "") and "reply" in V.chat([{"role": "user", "content": "4"}], ctx, ip="9.9.9.9", transport=fake))
check("chat: empty -> error", "error" in V.chat([], ctx, ip="5.5.5.5", transport=fake))

doc = b"<html><body><p>x</p></body></html>"
inj = vega_widget.inject(doc)
check("widget injected once, before </body>", inj.count(b'id="vega-btn"') == 1 and inj.endswith(b"</body></html>") and vega_widget.inject(inj) == inj)
check("widget has no self-moving effects", b"animation" not in vega_widget.SNIPPET.encode() and b"setInterval" not in vega_widget.SNIPPET.encode())
check("widget posts to /api/vega with the fetch header", "/api/vega" in vega_widget.SNIPPET and "X-Requested-With" in vega_widget.SNIPPET)
print("fails:", fails)
sys.exit(1 if fails else 0)
