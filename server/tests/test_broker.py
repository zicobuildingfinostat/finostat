"""Broker connections: sealing, OAuth state, token expiry, order planning, storage, summaries."""
import sys, pathlib, tempfile, os, time, json
from datetime import datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ["FINOSTAT_SECRET_KEY"] = "unit-seal-key"; os.environ["UPSTOX_API_KEY"] = "unit-key"; os.environ["UPSTOX_API_SECRET"] = "unit-secret"
os.environ["FINOSTAT_PUBLIC_URL"] = "https://finostat.com"
import broker as B
import contracts as C
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

print("=== sealing ===")
s = B.seal("token-abc-123")
check("seal is not the plaintext and round-trips", "token-abc-123" not in s and B.unseal(s) == "token-abc-123")
check("two seals of the same text differ (nonce)", B.seal("x") != B.seal("x"))
bad = s[:-4] + ("AAAA" if s[-4:] != "AAAA" else "BBBB")
check("tampered blob -> None", B.unseal(bad) is None)
check("garbage -> None", B.unseal("not base64!!") is None)

print("\n=== oauth bits ===")
check("configured with key+secret", B.configured())
u = B.authorize_url("st4te")
check("authorize url carries client id, redirect and state", u.startswith(B.UPSTOX_AUTH) and "client_id=unit-key" in u and "state=st4te" in u and "broker%2Fupstox%2Fcallback" in u, u)
check("redirect uri", B.redirect_uri() == "https://finostat.com/broker/upstox/callback")
t = datetime(2026, 9, 10, 10, 0, tzinfo=B.IST).timestamp()
check("token expiry = next 03:30 IST (same day before 03:30, else tomorrow)", datetime.fromtimestamp(B.token_expiry(t), B.IST).strftime("%Y-%m-%d %H:%M") == "2026-09-11 03:30"
      and datetime.fromtimestamp(B.token_expiry(datetime(2026, 9, 10, 1, 0, tzinfo=B.IST).timestamp()), B.IST).strftime("%Y-%m-%d %H:%M") == "2026-09-10 03:30")

os.environ["FINOSTAT_TRADE_USERS"] = "zico@finostat.com, Gicok13films@gmail.com"
check("trade allow-list: listed emails only, case-insensitive", B.trade_allowed("gicok13films@gmail.com") and B.trade_allowed("zico@finostat.com") and not B.trade_allowed("someone@x.com") and not B.trade_allowed(""))
del os.environ["FINOSTAT_TRADE_USERS"]
check("empty allow-list -> nobody", not B.trade_allowed("zico@finostat.com"))

print("\n=== storage ===")
tmp = pathlib.Path(tempfile.mkdtemp())
st = B.Brokers(tmp / "acct.db")
state = st.new_state(7)
check("state pops once for its user", st.pop_state(state) == (7, "upstox") and st.pop_state(state) is None)
check("unknown state -> None", st.pop_state("nope") is None)
st.connect(7, "upstox", {"token": "tok-live", "uid": "UP123", "name": "Zico", "email": "z@x.com"}, time.time() + 3600)
acc = st.get(7)
check("connected account readable with unsealed token", acc and acc["token"] == "tok-live" and acc["name"] == "Zico" and not acc["expired"])
import sqlite3
raw = sqlite3.connect(tmp / "acct.db").execute("SELECT token FROM broker_accounts").fetchone()[0]
check("token sealed in the database", "tok-live" not in raw)
st.connect(7, "upstox", {"token": "tok-old", "uid": "UP123", "name": "Zico"}, time.time() - 1)
check("expired token reads as expired with no token", st.get(7)["expired"] and st.get(7)["token"] is None)
stt = st.status(7)
check("status lists brokers with availability", [b["id"] for b in stt["brokers"]] == ["upstox", "zerodha"] and stt["brokers"][0]["connected"] and stt["brokers"][0]["expired"] and not stt["brokers"][1]["available"])
check("disconnect", st.disconnect(7, "upstox") and st.get(7) is None)
oid = st.record_order(7, "upstox", [{"right": "CE", "strike": 23650, "qty": -1}], [{"leg": "SELL 1x 23650 CE", "ok": True, "order_id": "o1"}], "fino-1")
check("orders recorded and listed", st.recent_orders(7)[0]["results"][0]["order_id"] == "o1")

print("\n=== order planning ===")
ci = C.ContractIndex()
exp = 1789000000000
ci._by_name = {"NIFTY": {exp: {(23650, "CE"): ("NSE_FO|1", 65), (23650, "PE"): ("NSE_FO|2", 65), (23700, "CE"): ("NSE_FO|3", 65)}}}
check("contracts.key_for", ci.key_for("NIFTY", exp, 23650, "ce") == ("NSE_FO|1", 65) and ci.key_for("NIFTY", exp, 99999, "CE") is None)
resolve = lambda r, k: ci.key_for("NIFTY", exp, k, r)
plan = B.plan_orders([{"right": "CE", "strike": 23650, "qty": -1, "price": 150}, {"right": "CE", "strike": 23700, "qty": 1, "price": 120}], resolve, 2, "D", "LIMIT", "fino-9")
check("buys first, quantity = lots x lot size, limit prices carried", plan[0]["side"] == "BUY" and plan[0]["payload"]["quantity"] == 130 and plan[0]["payload"]["price"] == 120.0 and plan[1]["payload"]["transaction_type"] == "SELL" and plan[1]["payload"]["price"] == 150.0 and plan[1]["payload"]["instrument_token"] == "NSE_FO|1", plan)
try: B.plan_orders([{"right": "CE", "strike": 23650, "qty": 1, "price": 150}], resolve, 1, "D", "MARKET", "t"); check("market orders refused (Upstox API rule)", False)
except B.BrokerError: check("market orders refused (Upstox API rule)", True)
try: B.plan_orders([{"right": "CE", "strike": 23650, "qty": 1}], resolve, 1, "D", "LIMIT", "t"); check("limit without a price refused", False)
except B.BrokerError: check("limit without a price refused", True)
lim = B.plan_orders([{"right": "CE", "strike": 23650, "qty": 1, "price": 150.5}], resolve, 1, "I", "LIMIT", "t")
check("limit order carries the price and product", lim[0]["payload"]["price"] == 150.5 and lim[0]["payload"]["product"] == "I" and lim[0]["payload"]["order_type"] == "LIMIT")
for bad, why in [([{"right": "CE", "strike": 1, "qty": 1, "price": 1}], "unlisted strike"), ([], "no legs"), ([{"right": "XX", "strike": 23650, "qty": 1, "price": 1}], "bad right")]:
    try: B.plan_orders(bad, resolve, 1, "D", "LIMIT", "t"); check(f"rejects {why}", False)
    except B.BrokerError: check(f"rejects {why}", True)
try: B.plan_orders([{"right": "CE", "strike": 23650, "qty": 1, "price": 1}], resolve, 99, "D", "LIMIT", "t"); check("rejects 99 lots", False)
except B.BrokerError: check("rejects 99 lots", True)
class FakeClient:
    def __init__(self, fail_on=None): self.sent = []; self.fail_on = fail_on
    def place(self, payload):
        self.sent.append(payload)
        if self.fail_on is not None and len(self.sent) == self.fail_on: raise B.BrokerError("Upstox: insufficient funds")
        return {"order_id": f"o{len(self.sent)}"}
fc = FakeClient(); res = B.execute(fc, plan)
check("execute sends every leg and returns ids", [r["order_id"] for r in res] == ["o1", "o2"] and all(r["ok"] for r in res))
fc2 = FakeClient(fail_on=1); res2 = B.execute(fc2, plan)
check("execute stops at the first rejection", len(res2) == 1 and not res2[0]["ok"] and "insufficient" in res2[0]["error"] and len(fc2.sent) == 1)

print("\n=== summaries ===")
pos = B.summarize_positions([{"trading_symbol": "NIFTY 23650 CE", "exchange": "NFO", "product": "D", "quantity": -65, "average_price": 150.0, "last_price": 140.0, "pnl": 650.0, "unrealised": 650.0, "realised": 0, "instrument_token": "NSE_FO|1"},
                             {"trading_symbol": "closed", "quantity": 0, "realised": 0}])
check("positions: open ones kept, flat+zero dropped", len(pos) == 1 and pos[0]["qty"] == -65 and pos[0]["pnl"] == 650.0)
ords = B.summarize_orders([{"order_id": "a", "status": "complete", "trading_symbol": "X", "transaction_type": "BUY", "quantity": 65, "filled_quantity": 65, "average_price": 1, "order_type": "MARKET", "product": "D", "order_timestamp": "2026-09-10 10:00:00"},
                           {"order_id": "b", "status": "rejected", "trading_symbol": "Y", "status_message": "margin", "order_timestamp": "2026-09-10 11:00:00"}])
check("orders newest first with messages", [o["order_id"] for o in ords] == ["b", "a"] and ords[0]["message"] == "margin")

print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
