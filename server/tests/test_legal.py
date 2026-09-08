"""Privacy, terms and contact pages render and say the things they must."""
import sys, pathlib, re
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import legal

fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

print("=== legal pages ===")
for path in ("/privacy", "/terms", "/contact"):
    p = legal.render(path).decode()
    check(f"{path} renders", p.startswith("<!DOCTYPE html>") and f'href="https://finostat.com{path}"' in p)
    check(f"{path} names the owner and email", "Zico Karmakar" in p and "zico@finostat.com" in p)
    check(f"{path} has an updated date", legal.UPDATED in p)
check("unknown path -> None", legal.render("/nope") is None)

priv = legal.render("/privacy").decode()
for must in ("fino_session", "assessment", "mobile number", "Fly.io", "Singapore", "Google Fonts", "Digital Personal Data Protection", "delete", "seven days", "Upstox"):
    check(f"privacy mentions '{must}'", must in priv)
check("privacy: no analytics claimed", "no third-party analytics" in priv or "do not run advertising trackers" in priv)

terms = legal.render("/terms").decode()
for must in ("not registered with SEBI", "indicative", "lose more than", "Starter", "Desk", "Pro", "GST", "laws of India", "/privacy"):
    check(f"terms mentions '{must}'", must in terms)

contact = legal.render("/contact").decode()
check("contact has mailto + founder link", 'href="mailto:zico@finostat.com"' in contact and 'href="/founders"' in contact)

# Homepage and sitemap must not advertise routes that don't exist.
root = pathlib.Path(__file__).resolve().parents[2]
index = (root / "index.html").read_text(encoding="utf-8")
sitemap = (root / "sitemap.xml").read_text(encoding="utf-8")
check("homepage has no /tools, /blog, /live-session, /analysis, /about links",
      not re.findall(r'href="/(?:tools/|blog|live-session|analysis|about)', index))
check("sitemap lists no retired urls", not re.findall(r'finostat\.com/(?:tools/|blog|live-session|about)', sitemap))
check("sitemap lists the legal pages", all(f"finostat.com/{p}</loc>" in sitemap for p in ("privacy", "terms", "contact")))

print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
