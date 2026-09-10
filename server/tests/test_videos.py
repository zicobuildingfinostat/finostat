"""YouTube feed parsing, caching and the homepage section."""
import sys, pathlib, tempfile, json
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import videos as V
fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1
XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015" xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
<title>Finostat</title>
<entry><id>yt:video:abc123XYZ_-</id><yt:videoId>abc123XYZ_-</yt:videoId><title>NIFTY EXPIRY ANALYSIS &amp; more</title><published>2026-09-07T10:00:00+00:00</published>
<media:group><media:title>t</media:title><media:thumbnail url="https://i1.ytimg.com/vi/abc123XYZ_-/hqdefault.jpg" width="480" height="360"/><media:description>weekly #shorts</media:description>
<media:community><media:statistics views="956"/></media:community></media:group></entry>
<entry><id>yt:video:def456</id><yt:videoId>def456</yt:videoId><title>Markets pe charcha</title><published>2026-09-06T10:00:00+00:00</published>
<media:group><media:thumbnail url="https://i2.ytimg.com/vi/def456/hqdefault.jpg"/><media:description>long form</media:description><media:community><media:statistics views="12345"/></media:community></media:group></entry>
</feed>"""
print("=== parse ===")
vs = V.parse_feed(XML)
check("two entries, newest first as published by YouTube", [v["id"] for v in vs] == ["abc123XYZ_-", "def456"])
check("title unescaped, date trimmed, views int, shorts flagged", vs[0]["title"] == "NIFTY EXPIRY ANALYSIS & more" and vs[0]["published"] == "2026-09-07" and vs[0]["views"] == 956 and vs[0]["short"] and not vs[1]["short"], vs[0])
print("\n=== cache ===")
tmp = pathlib.Path(tempfile.mkdtemp()) / "videos.json"
tmp.write_text(json.dumps({"videos": vs, "fetched": 123.0}))
f = V.YouTubeFeed(cache=tmp)
check("cache loaded at start (no network)", len(f.latest()) == 2 and f.fetched == 123.0)
check("status", f.status() == {"count": 2, "fetched": 123.0, "error": None})
print("\n=== section ===")
h = V.render_section(vs)
check("section with two cards, escaped title, play overlay, subscribe link", h.count('class="vid rv"') == 2 and "NIFTY EXPIRY ANALYSIS &amp; more" in h and 'class="play"' in h and V.CHANNEL_URL in h)
check("thumbnails lazy, ids as data attributes", 'loading="lazy"' in h and 'data-id="abc123XYZ_-"' in h)
check("views formatted", "956 views" in h and "12.3k views" in h)
check("empty feed renders nothing", V.render_section([]) == "")
check("JS embeds via youtube-nocookie only on click", "youtube-nocookie.com/embed/" in V.JS and "addEventListener('click'" in V.JS)
root = pathlib.Path(__file__).resolve().parents[2]
idx = (root / "index.html").read_text(encoding="utf-8")
check("homepage carries the placeholders and nav link", "<!--VIDEOS-->" in idx and "/*VIDEOS_CSS*/" in idx and 'href="#watch"' in idx and '"sameAs":["https://www.youtube.com/@finostat"]' in idx)
print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
