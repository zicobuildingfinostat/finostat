"""Founder page renders with the essentials."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import founder
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1
p = founder.render().decode()
print("=== founder page ===")
check("renders", p.startswith("<!DOCTYPE html>") and "</html>" in p)
check("name, experience, desk years", all(x in p for x in ("Zico Karmakar", "10<i>+ yrs", "3<i>+ yrs", "proprietary")))
check("photo referenced", '/founder.jpg' in p and 'alt="Zico Karmakar' in p)
check("photo file ships with the site", (pathlib.Path(__file__).resolve().parents[2] / "founder.jpg").exists())
check("contact + disclaimer", "mailto:zico@finostat.com" in p and "investment advice" in p)
check("theme css included", "--gold:#f5c842" in p and ".hero{" in p)
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
