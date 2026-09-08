"""Trader assessment: validation, scoring, storage, rate limit, CSV, markup."""
import sys, pathlib, tempfile, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import assessment as A

fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

GOOD = {"name": "Asha Rao", "email": "Asha@Example.com", "phone": "+91 98765 43210", "city": "Pune",
        "years": 2, "segments": [2, 3], "style": 1, "capital": 2, "fno_result": 2, "broker": "Zerodha",
        "q1": 1, "q2": 2, "q3": 1, "q4": 1, "q5": 1, "q6": 1, "q7": 1,
        "goal": 0, "challenge": 1, "risk": 1, "journal": 1, "hours": 1, "source": 0, "consent": True}

print("=== validation ===")
a, err = A.validate(GOOD)
check("good payload accepted", err is None, err)
check("email lower-cased", a["email"] == "asha@example.com")
check("phone normalised", a["phone"] == "9876543210", a["phone"])
for bad, why in [({"phone": "12345"}, "short phone"), ({"phone": "5123456789"}, "phone not 6-9"), ({"email": "nope"}, "bad email"),
                 ({"name": ""}, "missing name"), ({"consent": False}, "no consent"), ({"years": 9}, "radio out of range"),
                 ({"q3": None}, "quiz unanswered"), ({"segments": []}, "no segments"), ({"name": "x" * 200}, "too long")]:
    p = dict(GOOD); p.update(bad); _, e = A.validate(p)
    check(f"rejects {why}", e is not None, "accepted")
p = dict(GOOD); p["segments"] = ["2", 99, "x"]; a2, e = A.validate(p)
check("check list coerced and filtered", e is None and a2["segments"] == [2])
p = dict(GOOD); p["phone"] = "09876543210"; a3, e = A.validate(p)
check("leading-zero phone accepted", e is None and a3["phone"] == "9876543210")
check("non-dict rejected", A.validate([1])[1])

print("\n=== scoring ===")
r = A.score(A.validate(GOOD)[0])
check("all correct = 7/7", r["score"] == 7 and not r["wrong"], r)
check("1-3y + 7/7 -> Practitioner", r["profile"] == "Practitioner", r["profile"])
check("perfect score starts at the builder", r["start"]["path"].startswith("/dashboard"))
check("income goal + net loss flagged", any("income" in f for f in r["flags"]), r["flags"])
p = dict(GOOD); p.update({"years": 0, "fno_result": 3, "q1": 0, "q2": 0, "q3": 0, "q4": 0, "segments": [8], "risk": 4})
r = A.score(A.validate(p)[0])
check("never traded + 3/7 -> Newcomer", r["profile"] == "Newcomer", r["profile"])
check("newcomer starts at chapter 1", r["start"]["path"] == "/finch/start-here")
check("no-sizing flagged", any("5%" in f for f in r["flags"]))
check("wrong answers list the chapter", r["wrong"][0]["read"] == "/finch/options-basics" and r["wrong"][0]["correct"] == "Time value")
p = dict(GOOD); p.update({"years": 4, "q7": 0})
r = A.score(A.validate(p)[0])
check("5y+ and 6/7 -> Advanced, pro suggested", r["profile"] == "Advanced" and r["plan"] == "pro", (r["profile"], r["plan"]))
check("first miss drives the start chapter", r["start"]["path"] == "/finch/risk-and-position-sizing")
p = dict(GOOD); p.update({"years": 1, "q1": 0, "q2": 0, "q3": 0, "q4": 0})
check("<1y and 3/7 -> Learner", A.score(A.validate(p)[0])["profile"] == "Learner")

print("\n=== storage ===")
tmp = pathlib.Path(tempfile.mkdtemp())
st = A.Assessments(tmp / "acct.db", per_ip_hour=2)
res, err, code = st.submit(GOOD, ip="1.2.3.4")
check("submit ok", err is None and code == 200 and res["id"] == 1, (err, code))
check("stored", st.count() == 1 and st.recent()[0]["email"] == "asha@example.com")
_, err, code = st.submit({"name": "x"}, ip="1.2.3.4")
check("invalid -> 400 with message", code == 400 and err)
st.submit(GOOD, ip="1.2.3.4")
_, err, code = st.submit(GOOD, ip="1.2.3.4")
check("per-ip rate limit -> 429", code == 429, code)
_, err, code = st.submit(GOOD, ip="5.5.5.5")
check("other ip fine", code == 200)
check("delete removes one row", st.delete(2) and st.count() == 2 and not st.delete(2))
csv_ = st.export_csv()
check("csv has header + rows with labels", csv_.splitlines()[0].startswith("id,submitted,score,profile,name") and "Index options; Stock options" in csv_ and "Net loss" in csv_, csv_[:200])
lines = A.owner_lines(A.validate(GOOD)[0], res)
check("owner note has contact + profile", "asha@example.com" in lines[0] and "9876543210" in lines[0] and "Practitioner" in lines[1])
import auth as AU
au = AU.Auth(tmp / "acct.db"); au.redeem_link(au.create_link("u@x.com", ip="1.1.1.1"))
check("shares finostat.db with auth without clobbering", au.list_users()[0]["email"] == "u@x.com" and st.count() == 2)

print("\n=== markup ===")
w = A.widget_html()
check("widget has modal, form, every field", '<div class="fa-modal" hidden' in w and all(f'data-key="{k}"' in w for k in A.FIELDS))
check("four steps, first visible", w.count('class="fa-step"') == 4 and 'data-step="0">' in w and 'data-step="1" hidden' in w)
check("posts with the CSRF header", "'X-Requested-With':'fetch'" in w)
check("no unescaped rupee/quotes break", "₹50,000 – ₹2 lakh" in w)
pg = A.render_page().decode()
check("standalone page renders inline", 'data-mode="page"' in pg and "<title>Trader assessment" in pg and '<div class="fa-modal"' not in pg)
check("every suggested plan has a pitch", all(A.score(A.validate(GOOD)[0])["pitch"]) and set(A.PITCH) == {"starter", "desk", "pro"})
check("newcomer pitch sells Desk without pretending Starter isn't enough", "Starter is free" in A.PITCH["starter"]["why"])

print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
