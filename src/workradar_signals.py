"""WorkRadar 라이브 신호 자동수집 (stdlib only) — 직군별 '이번 압력의 근거'를 신선하게 유지.

실제 공개 RSS(구글 뉴스 검색 피드)에서 AI 관련 헤드라인을 가져와 직군으로 분류하고,
직군별 최신 1건을 data/wr_signals.json 캐시에 저장한다. workradar.fresh_family_signal()이 읽음.

정직성(불가침):
- 저장하는 head/url은 **실제 가져온 헤드라인과 실제 출처 링크**. 합성/가짜 금지.
- 제목이 직군 키워드에 명확히 매칭될 때만 분류(애매하면 버림 → 큐레이션 폴백 유지).
- 네트워크 실패해도 안전(기존 캐시/폴백 유지). Mac 24h에서 cron으로 주기 실행.

실행: python3 src/workradar_signals.py        (수집 → 캐시 갱신)
      python3 src/workradar_signals.py --dry   (네트워크 호출만, 저장 안 함)
"""
from __future__ import annotations
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CACHE = os.path.join(_DATA, "wr_signals.json")

# 구글 뉴스 RSS 검색(공개·무키). 직군 다양성 확보용 쿼리.
FEEDS = [
    "https://news.google.com/rss/search?q=AI%20coding%20tools%20developers&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI%20generative%20image%20video%20design&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI%20writing%20content%20copywriting&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI%20customer%20service%20automation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI%20healthcare%20medical%20jobs&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI%20finance%20accounting%20legal%20jobs&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=AI%20jobs%20automation%20workforce&hl=en-US&gl=US&ceid=US:en",
]

# 헤드라인 → 직군 분류 키워드(워크라다 직군과 정렬). 명확 매칭만, 애매하면 None.
_CLASS = [
    ("tech", ("coding", "developer", "programmer", "software", "github", "copilot", "devops", "code ")),
    ("creative", ("image generat", "video generat", "design", "photo", "illustrat", "art ", "midjourney", "sora", "firefly")),
    ("writing", ("writing", "writer", "content", "copywrit", "journalis", "translat", "language model")),
    ("marketing", ("marketing", "advertis", "ad copy", "seo")),
    ("finance", ("finance", "accounting", "accountant", "banking", "trading", "fintech", "bookkeep")),
    ("legal", ("legal", "lawyer", "law firm", "contract review", "paralegal")),
    ("support", ("customer service", "call center", "support agent", "chatbot")),
    ("healthcare", ("health", "medical", "clinical", "radiolog", "nursing", "doctor", "diagnos")),
    ("education", ("education", "teacher", "teaching", "classroom", "student", "tutor")),
    ("science", ("research", "scientist", "scientific", "laborator")),
    ("business", ("office job", "white-collar", "productivity", "enterprise", "workplace", "consultant")),
]


def classify_family(title: str) -> str | None:
    t = (title or "").lower()
    for fam, kws in _CLASS:
        if any(k in t for k in kws):
            return fam
    return None


def _fetch(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (WorkRadar signal bot)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _parse_items(xml: str) -> list[dict]:
    out = []
    try:
        root = ET.fromstring(xml)
    except Exception:
        return out
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        if title and link.startswith("http"):
            out.append({"title": title, "link": link, "pub": pub})
    return out


def collect(dry: bool = False) -> dict:
    """피드 수집 → 직군별 최신 1건. dry=True면 저장 안 함."""
    best: dict[str, dict] = {}
    seen = 0
    for url in FEEDS:
        try:
            items = _parse_items(_fetch(url))
        except Exception:
            continue
        for it in items:
            seen += 1
            fam = classify_family(it["title"])
            if not fam or fam in best:        # 직군별 첫(최신) 1건만
                continue
            best[fam] = {"head": re.sub(r"\s+", " ", it["title"])[:140],
                         "url": it["link"],
                         "ts": datetime.now(timezone.utc).isoformat()}
    result = {"feeds": len(FEEDS), "items_seen": seen, "families": sorted(best)}
    if not dry and best:
        os.makedirs(_DATA, exist_ok=True)
        # 기존 캐시와 병합(이번에 못 받은 직군은 유지)
        prev = {}
        try:
            with open(CACHE, encoding="utf-8") as f:
                prev = json.load(f)
        except Exception:
            pass
        prev.update(best)
        tmp = CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(prev, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CACHE)
        result["written"] = len(best)
    return result


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    print(json.dumps(collect(dry=dry), ensure_ascii=False))
