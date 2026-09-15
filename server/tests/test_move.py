"""MOVE maths and the extra alert families (book / OI / PCR / gamma flip / XAU) through providers."""
import os, sys, tempfile, pathlib, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import move, alerts, pages

fails = 0
def check(label, ok, extra=""):
    global fails
    print(("ok   " if ok else "FAIL ") + label + (("  " + str(extra)) if extra and not ok else ""))
    if not ok: fails += 1

e = move.expected(23400.0, 14.0, 180.0, 2 / 365)
check("expected: day/week/expiry from IV, straddle terms", abs(e["em_day"] - 23400 * 0.14 * (1 / 252) ** 0.5) < 0.2 and e["em_week"] > e["em_day"] and e["em_expiry_straddle"] == 180.0 and abs(e["sigma_expiry_straddle"] - 225.0) < 0.1)
check("expected: no IV -> None", move.expected(100.0, None, None, None)["em_day"] is None)
day = "2026-09-15"
cands = [[f"{day}T09:15:00+05:30", 23350, 23380, 23340, 23370, 100], [f"{day}T09:20:00+05:30", 23370, 23470, 23360, 23460, 100], [f"{day}T09:25:00+05:30", 23460, 23465, 23400, 23410, 100],
         ["2026-09-14T15:25:00+05:30", 23000, 23010, 22990, 23000, 100]]
r = move.realised(move.today_only(cands, move.datetime(2026, 9, 15, 10, 0, tzinfo=move.IST)), 23400.0)
check("realised: today's bars only, ohlc, move, gap", r["bars"] == 3 and r["high"] == 23470 and r["low"] == 23340 and r["range"] == 130 and r["move"] == 10 and r["gap"] == -50 and r["max_up"] == 70)
c = move.compare(e, r)
check("compare: range vs 2σ, sigmas, touched", c["range_vs_expected_pct"] == round(100 * 130 / (2 * e["em_day"])) and abs(c["move_sigmas"] - 10 / e["em_day"]) < 0.01 and c["touched_lower"] is False and c["touched_upper"] is False and c["verdict"])
b = move.build("NIFTY 50", 23400.0, 14.0, 180.0, 2 / 365, 23400.0, cands, expiry="2026-09-16", now=move.datetime(2026, 9, 15, 10, 0, tzinfo=move.IST))
check("build: shape", b["u"] == "NIFTY 50" and b["expected"]["em_day"] and b["realised"]["bars"] == 3 and "verdict" in b["compare"] and len(b["realised"]["path"]) == 3)

# ---- alerts: parsing, validation, labels
check("parse_extra ok", alerts.parse_extra("book:delta") == ("book", ["delta"]) and alerts.parse_extra("oi:NIFTY 50:CE") == ("oi", ["NIFTY 50", "CE"]) and alerts.parse_extra("xau:4h") == ("xau", ["4h"]) and alerts.parse_extra("gexflip:BANKNIFTY"))
check("parse_extra rejects", alerts.parse_extra("book:x") is None and alerts.parse_extra("oi:NIFTY 50:XX") is None and alerts.parse_extra("xau:2h") is None and alerts.parse_extra("spot:NIFTY 50") is None)
ok, err = alerts.validate({"metric": "book:delta", "cmp": ">=", "value": 20000})
check("validate book metric", ok and ok["metric"] == "book:delta" and ok["strike"] is None, err)
ok2, err2 = alerts.validate({"metric": "oi:NIFTY 50:CE", "cmp": ">=", "value": 5000000})
check("validate oi needs strike", ok2 is None and "strike" in err2)
ok3, _ = alerts.validate({"metric": "oichg:NIFTY 50:PE", "strike": 23300, "cmp": ">=", "value": 50000})
check("validate oichg with strike", ok3 and ok3["strike"] == 23300)
check("labels", alerts.metric_label("book:daypnl", None) == "Book day P&L" and alerts.metric_label("oichg:NIFTY 50:PE", 23300) == "NIFTY 50 23300 PE ΔOI 15m" and alerts.metric_label("xau:1d", None).startswith("XAU Sovereign"))

# ---- engine fires through a provider
db = pathlib.Path(tempfile.mkdtemp()) / "auth.db"
sent = []
E = alerts.AlertEngine(db, send_email=lambda to, subj, lines: sent.append((to, subj, lines)), user_email=lambda uid: "u@x.y")
vals = {"book:delta": -30000.0, "xau:1d": 0.31, "oi:NIFTY 50:CE": 4200000.0}
E.providers.update({"book": lambda m, k, u: vals.get(m), "xau": lambda m, k, u: vals.get(m), "oi": lambda m, k, u: vals.get(m) if k == 23500 else None})
E.create(7, alerts.validate({"metric": "book:delta", "cmp": "<=", "value": -25000})[0])
E.create(7, alerts.validate({"metric": "xau:1d", "cmp": ">=", "value": 0.25})[0])
E.create(7, alerts.validate({"metric": "oi:NIFTY 50:CE", "strike": 23500, "cmp": ">=", "value": 4000000})[0])
E.create(7, alerts.validate({"metric": "oi:NIFTY 50:CE", "strike": 23600, "cmp": ">=", "value": 1})[0])          # provider has no value -> stays armed
E.create(7, alerts.validate({"metric": "pcr:NIFTY 50", "cmp": ">=", "value": 1.0})[0])                            # no provider registered -> stays armed
fired = E.evaluate({"live": True, "quotes": []})
msgs = sorted(f["message"] for f in fired)
check("providers fire book / xau / oi rules", len(fired) == 3 and any("Book net" in m for m in msgs) and any("XAU Sovereign" in m for m in msgs) and any("23500 CE OI" in m for m in msgs), msgs)
check("one email per user with all three", len(sent) == 1 and len(sent[0][2]) == 3)
check("unknown-value and unregistered kinds stay armed", sum(1 for a in E.list_for(7) if a["state"] == "armed") == 2)

# ---- dashboard carries MOVE + new alert options
doc = pages.render_dashboard({}).decode()
for m in ('id="p-move"', "/api/move?u=", "['move','Expected move']", "MOVE:'move'", "id:'book:delta'", "id:'xau:1d'", "id:'gexflip:NIFTY 50'"):
    check("dashboard has " + m, m in doc)
print("fails:", fails)
sys.exit(1 if fails else 0)
