#!/usr/bin/env python3
"""Build the static, server-less version of the site for GitHub Pages.

Without the server there is no market feed, so the page runs its own browser-side
simulator. Numbers still move, which is exactly why the honest labelling matters:
a finance page showing invented figures under a "LIVE" badge misleads the people
most likely to act on it. This build relabels every live indicator and adds a
banner, and changes nothing else.
"""
import io, pathlib, re, shutil

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "static-site"
OUT.mkdir(exist_ok=True)

doc = io.open(ROOT / "index.html", encoding="utf-8").read()
changes = []

def sub(old, new, label, required=True):
    global doc
    n = doc.count(old)
    if n == 0 and not required:
        return
    assert n >= 1, f"not found: {label}"
    doc = doc.replace(old, new, 1)
    changes.append(label)

# 1. Banner, immediately after <body> so it is the first thing read.
sub("<body>", """<body>
<div class="preview-note" role="status">
  <strong>Preview</strong> — the sheets and tape below are a simulation, not live
  market data. The live feed launches shortly.
</div>""", "preview banner")

# 2. Style it in the site's own palette.
sub("</style>", """.preview-note{background:linear-gradient(180deg,var(--gold-2),#f2b830);color:#2a1a02;
  font-family:var(--mono);font-size:12px;letter-spacing:.04em;text-align:center;
  padding:9px 16px;position:relative;z-index:31;line-height:1.45}
.preview-note strong{font-weight:600;letter-spacing:.1em;text-transform:uppercase}
</style>""", "banner styling")

# 3. Every live indicator becomes DEMO.
sub('<span class="tag hot">LIVE</span>', '<span class="tag">DEMO</span>', "alert tag")
sub('<span class="r"><span class="live">LIVE</span></span>',
    '<span class="r"><span class="live off">DEMO</span></span>', "mini panel indicator")

# 4. Claims that only hold with the server behind them.
sub("<b>&lt;250 ms</b>sheet refresh", "<b>Preview</b>simulated data", "hero stat")
sub("<h3>Streamed by the millisecond</h3><p>WebSocket-fed sheets refresh several times a second.",
    "<h3>Streamed by the millisecond</h3><p>The live product streams over a WebSocket, refreshing several times a second.",
    "mini panel copy")

# 5. The wire cannot reach the news endpoint, so say so plainly.
doc = re.sub(r'(<a href="[^"]*"[^>]*>)?Financial headlines stream here when the Finostat server is running\.(</a>)?',
             "Live financial headlines appear here on the full version.", doc)
changes.append("wire placeholder")

io.open(OUT / "index.html", "w", encoding="utf-8").write(doc)

for name in ("og.jpg", "robots.txt", "sitemap.xml"):
    shutil.copy2(ROOT / name, OUT / name)

# GitHub Pages reads the custom domain from this file.
io.open(OUT / "CNAME", "w").write("finostat.com\n")
# Stop Jekyll touching the files.
io.open(OUT / ".nojekyll", "w").write("")

print("built static-site/")
for c in changes:
    print("  changed:", c)
print("\nfiles:")
for p in sorted(OUT.iterdir()):
    print(f"  {p.name:<14} {p.stat().st_size:>8,} bytes")
