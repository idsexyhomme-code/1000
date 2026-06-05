"""
커리어 시그널 — 엔드투엔드 파이프라인 (R3b)

fetch → 직무 관련성 필터 → Gemini 5요인 점수화 → Event 저장 →
전체 이벤트 히스토리(감쇠 적용)로 ScoringEngine 재계산 → 점수로그 append.

★ mean-reversion(R2.5 ③): 매 실행마다 '전체 누적 이벤트'를 현재 시점 기준 감쇠와 함께
   재점수한다. 오래된 이벤트는 half-life로 자연 소멸 → 지수가 baseline으로 회귀.
   별도 상태 누적이 아니라 'baseline + 현재 살아있는 감쇠 이벤트합'으로 항상 재계산 → 운영자 임의조정 불가.

실행: GEMINI_API_KEY=... python3 src/pipeline.py [--max N]
"""
from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gemini_scorer
import store
from crawler import DEFAULT_SOURCES, tier_of
from scoring import Affected, Event, ScoringEngine

JOBS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jobs")

# AI 관련성 1차 필터 (저렴한 키워드 게이트 — 정밀 매칭은 Gemini가 affected 빈배열로 거름)
_AI_KEYWORDS = ("ai", "gpt", "llm", "model", "automat", "agent", "generative", "openai",
                "anthropic", "gemini", "인공지능", "자동화", "에이전트", "생성형", "모델")


def _event_id(url: str, title: str) -> str:
    return hashlib.sha1((url or title).encode("utf-8")).hexdigest()[:16]


def _norm_date(s: str, now: datetime) -> str:
    if not s:
        return now.isoformat()
    try:  # RSS RFC822
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        try:  # Atom ISO8601
            return datetime.fromisoformat(s.replace("Z", "+00:00")).isoformat()
        except Exception:
            return now.isoformat()


def _is_relevant(title: str, body: str) -> bool:
    text = (title + " " + body).lower()
    return any(k in text for k in _AI_KEYWORDS)


def _to_event(e: dict) -> Event:
    affs = [Affected(job_id=a["job_id"], task_id=a["task_id"], factors=a["factors"],
                     direction=a["direction"], reason_ko=a.get("reason_ko", ""),
                     event_kind=a.get("event_kind", "evidence")) for a in e["affected"]]
    return Event(event_id=e["event_id"], title=e["title"], url=e["url"],
                 source_tier=e["source_tier"], published_at=e["published_at"],
                 affected=affs, dedup_key=e.get("dedup_key", ""))


def ingest(sources=None, now=None, max_per_source: int | None = None) -> int:
    """소스 수집 → 신규 기사 점수화 → Event 저장. 반환: 신규 점수화 건수."""
    eng = ScoringEngine(JOBS_DIR)
    sources = sources or DEFAULT_SOURCES
    now = now or datetime.now(timezone.utc)
    scored = 0
    for src in sources:
        try:
            articles = src.fetch()
        except Exception as e:  # 소스 1개 실패가 전체를 막지 않음
            print(f"[소스 실패] {src.name}: {type(e).__name__} {e}")
            continue
        if max_per_source:
            articles = articles[:max_per_source]
        for art in articles:
            eid = _event_id(art.url, art.title)
            if store.event_exists(eid):
                continue  # 멱등: 이미 처리한 기사
            published = _norm_date(art.published_at, now)
            tier = tier_of(art.url)
            if not _is_relevant(art.title, art.body):
                store.save_event({"event_id": eid, "title": art.title, "url": art.url,
                                  "source_tier": tier, "published_at": published,
                                  "affected": [], "dedup_key": ""})
                continue
            affected_all = []
            for job_id, job in eng.jobs.items():
                try:
                    affs = gemini_scorer.score_article(
                        job["job_name_ko"], job["tasks"], art.title, art.body)
                except Exception as e:
                    print(f"[점수화 실패] {art.title[:40]}: {type(e).__name__} {e}")
                    continue
                for a in affs:
                    affected_all.append({**a, "job_id": job_id})
            store.save_event({"event_id": eid, "title": art.title, "url": art.url,
                              "source_tier": tier, "published_at": published,
                              "affected": affected_all, "dedup_key": ""})
            if affected_all:
                scored += 1
    return scored


def recompute(now=None) -> dict:
    """전체 이벤트 히스토리(감쇠)로 현재 지수 재계산 + 점수로그 append (mean-reversion)."""
    now = now or datetime.now(timezone.utc)
    eng = ScoringEngine(JOBS_DIR)
    events = [_to_event(e) for e in store.load_events() if e.get("affected")]
    result = eng.score(events, now=now)
    for job_id, r in result.items():
        delta = store.delta_since_prev(job_id, r["index"])
        store.append_score(job_id, {
            "index": r["index"], "weather": r["weather"], "delta": delta,
            "top_drivers": r["top_drivers"],
        }, ts=now.isoformat())
    return result


def run(now=None, max_per_source: int | None = None) -> dict:
    new = ingest(now=now, max_per_source=max_per_source)
    print(f"[ingest] 신규 점수화 {new}건")
    result = recompute(now=now)
    for job_id, r in result.items():
        d = next(iter(store.score_history(job_id, 1)), {}).get("delta")
        d_str = f" ({d:+})" if isinstance(d, (int, float)) else ""
        print(f"  {r['job_name_ko']}: {r['index']} [{r['weather']}]{d_str}")
    return result


if __name__ == "__main__":
    n = None
    if "--max" in sys.argv:
        n = int(sys.argv[sys.argv.index("--max") + 1])
    run(max_per_source=n)
