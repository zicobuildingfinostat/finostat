"""The news wire: poll a few public RSS feeds, fan new items out over SSE."""
from __future__ import annotations

import html
import logging
import queue
import re
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import config

log = logging.getLogger("finostat.news")

_HOT = re.compile(
    r"\b(rbi|sebi|fed|rate cut|rate hike|inflation|gdp|war|strike|sanction|"
    r"crash|plunge|surge|circuit|halt|emergency|budget)\b",
    re.I,
)


def _text(node, tag: str) -> str:
    child = node.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def _timestamp(node) -> float:
    for tag in ("pubDate", "{http://purl.org/dc/elements/1.1/}date"):
        raw = _text(node, tag)
        if not raw:
            continue
        try:
            return parsedate_to_datetime(raw).timestamp()
        except (TypeError, ValueError):
            continue
    return time.time()


class NewsHub:
    """Holds recent headlines and pushes fresh ones to connected browsers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[dict] = []
        self._seen: set[str] = set()
        self._subscribers: list[queue.Queue] = []
        self._stop = threading.Event()

    # -- subscribers --------------------------------------------------------
    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=64)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def _broadcast(self, items: list[dict]) -> None:
        with self._lock:
            targets = list(self._subscribers)
        for q in targets:
            try:
                q.put_nowait(items)
            except queue.Full:
                pass  # a stalled browser is dropped rather than blocking the poller

    # -- data ---------------------------------------------------------------
    def latest(self, limit: int = 30) -> list[dict]:
        with self._lock:
            return self._items[:limit]

    def _ingest(self, items: list[dict]) -> list[dict]:
        fresh = []
        with self._lock:
            for item in items:
                if item["url"] in self._seen:
                    continue
                self._seen.add(item["url"])
                self._items.append(item)
                fresh.append(item)
            self._items.sort(key=lambda i: i["ts"], reverse=True)
            if len(self._items) > config.NEWS_MAX:
                for dropped in self._items[config.NEWS_MAX:]:
                    self._seen.discard(dropped["url"])
                del self._items[config.NEWS_MAX:]
        return fresh

    # -- polling ------------------------------------------------------------
    def _fetch(self, category: str, handle: str, url: str) -> list[dict]:
        req = urllib.request.Request(url, headers={"User-Agent": "Finostat/1.0 (+https://finostat.com)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
        root = ET.fromstring(body)
        out = []
        for item in root.iter("item"):
            title = html.unescape(_text(item, "title"))
            link = _text(item, "link")
            if not title or not link:
                continue
            out.append({
                "ts": _timestamp(item),
                "text": title,
                "url": link,
                "category": category,
                "handle": handle,
                "hot": bool(_HOT.search(title)),
            })
        return out

    def poll_once(self) -> int:
        collected = []
        for category, handle, url in config.NEWS_FEEDS:
            try:
                collected.extend(self._fetch(category, handle, url))
            except (urllib.error.URLError, ET.ParseError, OSError) as exc:
                log.warning("news feed %s failed: %s", handle, exc)
        fresh = self._ingest(collected)
        if fresh:
            self._broadcast(fresh)
        return len(fresh)

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                count = self.poll_once()
                if count:
                    log.info("wire: %d new headlines", count)
            except Exception:
                log.exception("news poll failed")
            self._stop.wait(config.NEWS_REFRESH)

    def start(self) -> None:
        threading.Thread(target=self._loop, name="news", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
