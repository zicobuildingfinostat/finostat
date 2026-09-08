"""Open interest: decoding full-mode / option_greeks-mode feeds, the day-open baseline,
and the chain-level summary (PCR, max pain, walls)."""
import sys, pathlib, struct, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import upstoxfeed as U
import chains as C

fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

# --- an encoder independent of miniproto (same helpers as test_miniproto)
def vi(n):
    out = bytearray()
    while True:
        b = n & 0x7F; n >>= 7
        if n: out.append(b | 0x80)
        else: out.append(b); return bytes(out)
def f_double(f, v): return vi((f << 3) | 1) + struct.pack("<d", v)
def f_varint(f, v): return vi((f << 3) | 0) + vi(v)
def f_bytes(f, raw): return vi((f << 3) | 2) + vi(len(raw)) + raw
def f_str(f, s): return f_bytes(f, s.encode())
def map_entry(f, key, msg): return f_bytes(f, f_str(1, key) + f_bytes(2, msg))

ltpc = f_double(1, 153.05) + f_varint(2, 1788000000000) + f_varint(3, 65) + f_double(4, 160.0)
quote = f_varint(1, 650) + f_double(2, 153.0) + f_varint(3, 1300) + f_double(4, 153.1)
market_ff = (f_bytes(1, ltpc) + f_bytes(2, f_bytes(1, quote) + f_bytes(1, quote)) + f_bytes(3, f_double(1, 0.52))
             + f_double(5, 152.2) + f_varint(6, 4_512_000) + f_double(7, 3_215_400.0) + f_double(8, 0.1141) + f_double(9, 12000.0) + f_double(10, 9000.0))
feed_full = f_bytes(2, f_bytes(1, market_ff)) + f_varint(4, 2)
feed_ltpc = f_bytes(1, ltpc) + f_varint(4, 1)
first_level = f_bytes(1, ltpc) + f_bytes(2, quote) + f_bytes(3, f_double(1, 0.52)) + f_varint(4, 777_000) + f_double(5, 98_765.0) + f_double(6, 0.12)
feed_greeks = f_bytes(3, first_level) + f_varint(4, 3)

print("=== decoding ===")
import miniproto as mp
st = U.UpstoxFeed._extract_stats(mp.decode(feed_full))
check("full mode: oi, volume, iv, top of book", st == {"oi": 3215400, "vol": 4512000, "iv_feed": 0.1141, "bid": 153.0, "bid_q": 650, "ask": 153.1, "ask_q": 1300}, st)
st2 = U.UpstoxFeed._extract_stats(mp.decode(feed_greeks))
check("option_greeks mode: oi, volume, first depth", st2 == {"oi": 98765, "vol": 777000, "bid": 153.0, "bid_q": 650, "ask": 153.1, "ask_q": 1300}, st2)
check("ltpc-only feed carries no stats", U.UpstoxFeed._extract_stats(mp.decode(feed_ltpc)) is None)
ltp, close = U.UpstoxFeed._ltp_and_close(mp.decode(feed_full))
check("full mode still yields ltp/close", (ltp, close) == (153.05, 160.0), (ltp, close))

print("\n=== ingest keeps OI and a day-open baseline ===")
feed = U.UpstoxFeed.__new__(U.UpstoxFeed)
feed._meta = {"NSE_FO|1": {"kind": "option", "label": "x"}, "NSE_FO|2": {"kind": "option", "label": "y"}}
feed._prices, feed._closes, feed._stats, feed._oi_open = {}, {}, {}, {}
feed._uni_dirty, feed._ticks, feed._logged_fields = False, 0, True
import threading; feed._dirty = threading.Event()
msg = f_varint(1, 2) + map_entry(2, "NSE_FO|1", feed_full) + map_entry(2, "NSE_FO|2", feed_ltpc)
feed._ingest(msg)
check("price stored for both, stats only for the full-mode key", feed._prices == {"NSE_FO|1": 153.05, "NSE_FO|2": 153.05} and set(feed._stats) == {"NSE_FO|1"})
s1 = feed.stats_of("NSE_FO|1")
check("stats_of: oi with baseline = first oi today, change 0", s1["oi"] == 3215400 and s1["oi_open"] == 3215400 and s1["oi_chg"] == 0, s1)
later = f_bytes(1, ltpc) + f_double(7, 3_300_000.0)
feed._ingest(f_varint(1, 2) + map_entry(2, "NSE_FO|1", f_bytes(2, f_bytes(1, later))))
s1 = feed.stats_of("NSE_FO|1")
check("change in OI vs the day-open baseline", s1["oi"] == 3300000 and s1["oi_chg"] == 84600 and s1["vol"] == 4512000, s1)
check("stats_of for an ltpc-only key is empty", feed.stats_of("NSE_FO|2") == {})
check("dynamic socket subscribes in full mode", U.DYN_MODE == "full")

print("\n=== chain-level summary ===")
rows = []
for k, ce_oi, pe_oi in [(23500, 100, 900), (23550, 200, 700), (23600, 300, 1200), (23650, 400, 400), (23700, 1500, 300), (23750, 800, 100), (23800, 600, 50)]:
    rows.append({"strike": k, "atm": k == 23650, "ce": {"ltp": 1, "oi": ce_oi}, "pe": {"ltp": 1, "oi": pe_oi}})
o = C.oi_summary(rows, 23640.0)
check("PCR = put OI / call OI", abs(o["pcr"] - round(3650 / 3900, 2)) < 1e-9, o)
check("call wall = biggest call OI at/above spot (23700)", o["call_wall"] == 23700, o)
check("put wall = biggest put OI at/below spot (23600)", o["put_wall"] == 23600, o)
check("max pain lies between the walls", 23600 <= o["max_pain"] <= 23700, o["max_pain"])
check("totals + max_oi", o["tot_ce"] == 3900 and o["tot_pe"] == 3650 and o["max_oi"] == 1500)
check("no OI -> None", C.oi_summary([{"strike": 1, "atm": True, "ce": {"ltp": 1}, "pe": {"ltp": 1}}], 1.0) is None)
# max pain by hand: payout(S) = sum ce_oi*max(S-k,0) + sum pe_oi*max(k-S,0)
def payout(S): return sum(r["ce"]["oi"] * max(S - r["strike"], 0) + r["pe"]["oi"] * max(r["strike"] - S, 0) for r in rows)
check("max pain is the argmin of total payout", o["max_pain"] == min((r["strike"] for r in rows), key=payout))


print("\n=== chain-socket fallback routing (feed refuses a 3rd connection) ===")
class FakeWS:
    def __init__(self): self.sent = []
    def send_binary(self, b): self.sent.append(__import__("json").loads(b))
f = U.UpstoxFeed.__new__(U.UpstoxFeed)
f._dyn_lock = threading.Lock(); f._dyn_keys = set(); f._meta = {}; f._prices = {}; f._closes = {}; f._stats = {}
f._dyn_ws = None; f._dyn_started = True; f._dyn_wake = threading.Event(); f._helpers = {}; f._ws = FakeWS(); f._dyn_refused = 0; f._dyn_fallback = False
f.subscribe_dynamic({"NSE_FO|A": {"kind": "option"}})
check("no dedicated socket, no fallback -> nothing sent (the dyn loop will subscribe)", f._ws.sent == [])
f._dyn_fallback = True; h2 = FakeWS(); f._helpers = {2: h2}
f.subscribe_dynamic({"NSE_FO|B": {"kind": "option"}})
check("fallback on -> new keys ride the emptiest universe socket in ltpc", h2.sent and h2.sent[-1]["method"] == "sub" and h2.sent[-1]["data"]["mode"] == "ltpc" and h2.sent[-1]["data"]["instrumentKeys"] == ["NSE_FO|B"], h2.sent)
h3 = FakeWS(); f._helpers = {2: h2, 3: h3}
f._route_dyn_via(f._fallback_ws())
check("_route_dyn_via pushes every chain key to the highest-numbered helper", h3.sent and sorted(h3.sent[-1]["data"]["instrumentKeys"]) == ["NSE_FO|A", "NSE_FO|B"] and h3.sent[-1]["data"]["mode"] == "ltpc", h3.sent)
f.unsubscribe_dynamic(["NSE_FO|A"])
check("unsubscribe goes to the same fallback socket", h3.sent[-1]["method"] == "unsub" and h3.sent[-1]["data"]["instrumentKeys"] == ["NSE_FO|A"], h3.sent[-1])
d = FakeWS(); f._dyn_ws = d; f._dyn_fallback = False
f.subscribe_dynamic({"NSE_FO|C": {"kind": "option"}})
check("dedicated socket back -> subscribes there in full mode", d.sent and d.sent[-1]["data"]["mode"] == "full" and d.sent[-1]["data"]["instrumentKeys"] == ["NSE_FO|C"], d.sent)

print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
