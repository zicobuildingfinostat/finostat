"""Finch renders every chapter, every internal link resolves, live widgets are wired."""
import re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import finch, builder

fails = 0
def check(label, ok, extra=""):
    global fails
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{'' if ok else '  <- ' + str(extra)}")
    if not ok: fails += 1

print("=== index ===")
idx = finch.render_index().decode()
check("index renders", "<h1>Finch</h1>" in idx)
check("index lists every chapter", all(f'/finch/{c["slug"]}' in idx for c in finch.CHAPTERS))
check("12 chapters", len(finch.CHAPTERS) == 12, len(finch.CHAPTERS))
check("slugs unique", len({c["slug"] for c in finch.CHAPTERS}) == len(finch.CHAPTERS))

print("\n=== chapters ===")
widgets = set()
for c in finch.CHAPTERS:
    page = finch.render_chapter(c["slug"])
    check(f'{c["slug"]} renders', page is not None and c["title"].replace("&", "&amp;") in page.decode())
    body = c["body"]
    check(f'{c["slug"]} is substantial', len(body.split()) > 500, len(body.split()))
    check(f'{c["slug"]} has a live example', 'data-live=' in body)
    for m in re.finditer(r'<(h2|h3|p|li|td|th|dt|dd|table|ol|ul|aside|dl)\b', body):
        pass
    for tag in ("table", "aside", "ol", "ul", "dl"):
        check(f'{c["slug"]} balanced <{tag}>', body.count(f"<{tag}") == body.count(f"</{tag}>"),
              (body.count(f"<{tag}"), body.count(f"</{tag}>")))
    widgets |= set(re.findall(r'data-live="([a-z]+)"', body))
    for p in re.findall(r'data-preset="([a-z0-9-]+)"', body):
        check(f'{c["slug"]} preset {p} exists', p in builder.PRESETS)
check("unknown chapter is None", finch.render_chapter("nope") is None)
check("all widget kinds used", widgets == {"spot", "lot", "chain", "straddle", "greeks", "smile", "strategy"}, widgets)

print("\n=== links ===")
slugs = {c["slug"] for c in finch.CHAPTERS}
for link in set(finch.internal_links()):
    check(f"{link} resolves", link[len("/finch/"):] in slugs)
for kind in ("spot", "lot", "chain", "straddle", "greeks", "smile", "strategy"):
    check(f"JS renders data-live={kind}", f"t==='{kind}'" in finch._JS)

print("\nRESULT:", "ALL PASS" if not fails else "FAILURES")
sys.exit(1 if fails else 0)
