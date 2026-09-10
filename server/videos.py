"""Latest videos from the Finostat YouTube channel, for the homepage.

YouTube publishes a public Atom feed per channel (no API key). It is fetched
every few hours, cached on disk so a restart never shows an empty section,
and rendered server-side into the homepage. Thumbnails come from ytimg and
nothing from YouTube loads until a visitor clicks play (youtube-nocookie).
"""
from __future__ import annotations

import html
import json
import logging
import pathlib
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

log = logging.getLogger("finostat.videos")

CHANNEL_ID = "UC_CumweKPdzeM5RzVPIqm8A"
CHANNEL_URL = "https://www.youtube.com/@finostat"
INSTAGRAM_URL = "https://www.instagram.com/chase.alpha_/"
REELS_FILE = pathlib.Path(__file__).resolve().parent / "reels.json"      # curated: Instagram has no public feed
_REEL_RE = None
FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
_NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}


def parse_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall("a:entry", _NS):
        vid = e.findtext("yt:videoId", namespaces=_NS)
        if not vid:
            continue
        m = e.find("media:group", _NS)
        th = m.find("media:thumbnail", _NS) if m is not None else None
        st = m.find("media:community/media:statistics", _NS) if m is not None else None
        desc = (m.findtext("media:description", default="", namespaces=_NS) if m is not None else "") or ""
        out.append({"id": vid, "title": (e.findtext("a:title", namespaces=_NS) or "").strip(),
                    "published": (e.findtext("a:published", namespaces=_NS) or "")[:10],
                    "thumb": th.get("url") if th is not None else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "views": int(st.get("views")) if st is not None and (st.get("views") or "").isdigit() else None,
                    "short": "#shorts" in desc.lower() or "#shorts" in (e.findtext("a:title", namespaces=_NS) or "").lower()})
    return out


class YouTubeFeed:
    def __init__(self, channel_id: str = CHANNEL_ID, cache: pathlib.Path | None = None, interval: float = 6 * 3600):
        self.channel_id, self.cache, self.interval = channel_id, cache, interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.videos: list[dict] = []
        self.fetched: float | None = None
        self.error: str | None = None
        if cache and cache.exists():
            try:
                data = json.loads(cache.read_text())
                self.videos, self.fetched = data.get("videos", []), data.get("fetched")
            except (ValueError, OSError):
                pass

    def start(self) -> None:
        threading.Thread(target=self._run, name="videos", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def refresh(self) -> bool:
        try:
            req = urllib.request.Request(FEED_URL.format(cid=self.channel_id), headers={"User-Agent": "finostat/1.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                vids = parse_feed(r.read().decode("utf-8"))
        except Exception as exc:
            self.error = str(exc)[:200]
            log.warning("youtube feed: %s", exc)
            return False
        with self._lock:
            self.videos, self.fetched, self.error = vids, time.time(), None
        if self.cache:
            try:
                self.cache.write_text(json.dumps({"videos": vids, "fetched": self.fetched}))
            except OSError:
                pass
        log.info("youtube feed: %d videos", len(vids))
        return True

    def _run(self) -> None:
        self.refresh()
        while not self._stop.wait(self.interval):
            self.refresh()

    def latest(self, n: int = 6) -> list[dict]:
        with self._lock:
            return list(self.videos[:n])

    def status(self) -> dict:
        return {"count": len(self.videos), "fetched": self.fetched, "error": self.error}


def load_reels(path: pathlib.Path = REELS_FILE) -> list[str]:
    """Reel URLs, newest first, from reels.json. Only instagram.com/reel|p links count."""
    import re
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    out = []
    for u in raw if isinstance(raw, list) else raw.get("reels", []):
        m = re.match(r"^https?://(?:www\.)?instagram\.com/(?:reel|reels|p)/([A-Za-z0-9_-]{5,})/?", str(u).strip())
        if m:
            out.append(f"https://www.instagram.com/reel/{m.group(1)}/")
    return out[:12]


def render_reels(urls: list[str]) -> str:
    """Instagram's official embed markup; embed.js is only loaded when scrolled to."""
    if not urls:
        return ""
    cards = "".join(
        f'<blockquote class="instagram-media" data-instgrm-permalink="{html.escape(u)}" data-instgrm-version="14" style="margin:0;min-width:0;width:100%"></blockquote>'
        for u in urls)
    return f'<h3 class="reels-h rv">Reels</h3><div class="reels" id="reels">{cards}</div>'


def _views(v) -> str:
    if v is None:
        return ""
    return f"{v / 1000:.1f}k views" if v >= 1000 else f"{v} views"


def _when(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return iso


def render_section(videos: list[dict], reels: list[str] | None = None) -> str:
    """The homepage block. Empty string if there is nothing to show yet."""
    if not videos and not reels:
        return ""
    cards = "".join(
        f'<div class="vid rv" data-id="{html.escape(v["id"])}" role="button" tabindex="0" aria-label="Play: {html.escape(v["title"])}">'
        f'<div class="thumb"><img src="{html.escape(v["thumb"])}" alt="" loading="lazy" width="480" height="360"><span class="play">▶</span></div>'
        f'<div class="meta"><h3>{html.escape(v["title"])}</h3><small>{_when(v["published"])}{" · " + _views(v["views"]) if v["views"] is not None else ""}</small></div></div>'
        for v in videos)
    return f"""<section id="watch">
  <div class="wrap">
    <div class="sec-head rv"><div><span class="eyebrow">VID · youtube</span><h2>Watch the desk</h2></div><p>Expiry analysis, market structure and the occasional rant, straight from the founder's channel. Latest uploads, updated automatically.</p></div>
    <div class="vids">{cards}</div>
    {render_reels(reels or [])}
    <p class="vids-more rv"><a class="btn" href="{CHANNEL_URL}" target="_blank" rel="noopener">Subscribe on YouTube →</a> <a class="btn" href="{INSTAGRAM_URL}" target="_blank" rel="noopener">Follow @chase.alpha_ on Instagram →</a></p>
  </div>
</section>"""


CSS = """
/* ---------- videos ---------- */
.vids{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.vid{background:var(--panel);border:1px solid var(--line-strong);cursor:pointer;overflow:hidden;box-shadow:0 18px 50px rgba(0,0,0,.35);transition:border-color .15s}
.vid:hover,.vid:focus-visible{border-color:var(--gold);outline:0}
.vid .thumb{position:relative;aspect-ratio:16/9;background:#06031a;overflow:hidden}
.vid .thumb img{width:100%;height:100%;object-fit:cover;display:block;filter:saturate(.9)}
.vid .thumb iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.vid .play{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:56px;height:56px;border-radius:50%;background:rgba(12,6,38,.78);border:1px solid var(--gold);color:var(--gold);display:flex;align-items:center;justify-content:center;font-size:20px;padding-left:4px;box-shadow:0 0 30px rgba(245,200,66,.25)}
.vid:hover .play{background:var(--gold);color:#2a1a02}
.vid .meta{padding:12px 14px 14px}
.vid h3{font-family:var(--body);font-size:14px;font-weight:600;line-height:1.35;margin:0 0 6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.vid small{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint)}
.vids-more{margin-top:22px}
.reels-h{font-family:var(--mono);font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--cyan);margin:26px 0 12px}
.reels{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;align-items:start}
.reels .instagram-media{background:var(--panel)!important;border:1px solid var(--line-strong)!important;border-radius:0!important;box-shadow:0 18px 50px rgba(0,0,0,.35)!important;max-width:100%!important;min-width:0!important}
.vids-more .btn{margin:0 8px 8px 0}
@media (max-width:980px){.vids{grid-template-columns:repeat(2,1fr)}.reels{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:620px){.vids{grid-template-columns:1fr}.reels{grid-template-columns:1fr}}
"""

JS = """
(function(){
  var wrap=document.querySelector('.vids'); if(!wrap) return;
  function play(card){
    var id=card.getAttribute('data-id'), th=card.querySelector('.thumb'); if(!id||th.querySelector('iframe')) return;
    var f=document.createElement('iframe'); f.src='https://www.youtube-nocookie.com/embed/'+encodeURIComponent(id)+'?autoplay=1&rel=0'; f.title=card.getAttribute('aria-label')||'video';
    f.setAttribute('allow','accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share'); f.setAttribute('allowfullscreen','');
    th.appendChild(f); card.style.cursor='default';
  }
  wrap.addEventListener('click',function(e){ var c=e.target.closest('.vid'); if(c) play(c); });
  wrap.addEventListener('keydown',function(e){ var c=e.target.closest('.vid'); if(c&&(e.key==='Enter'||e.key===' ')){ e.preventDefault(); play(c); } });
  var reels=document.getElementById('reels');
  if(reels){
    var loaded=false;
    function loadIG(){ if(loaded) return; loaded=true; var s=document.createElement('script'); s.src='https://www.instagram.com/embed.js'; s.async=true; s.onload=function(){ if(window.instgrm&&window.instgrm.Embeds) window.instgrm.Embeds.process(); }; document.body.appendChild(s); }
    if('IntersectionObserver' in window){ var io=new IntersectionObserver(function(es){ if(es.some(function(x){ return x.isIntersecting; })){ loadIG(); io.disconnect(); } },{rootMargin:'400px'}); io.observe(reels); } else loadIG();
  }
})();
"""
