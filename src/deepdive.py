"""
커리어 시그널 — 상세 분석(drill-down) 데이터 (5섹션)

3-AI 만장일치 원칙: '50페이지 패딩' 금지. 깊이는 분량이 아니라 '근거 밀도'.
→ 실제 데이터로 받칠 수 있는 것만 채우고, 외부 데이터 필요한 것은 '가짜 숫자' 대신
  정직한 '연동 필요' 자리 + 어댑터 인터페이스로 둔다(데이터 꽂으면 바로 진짜가 됨).

섹션:
  1) automation_breakdown  과업별 자동화율 — 현 baseline(손추정). O*NET 연동 시 calibrated.
  2) tech_timeline         기술 상용화 타임라인 — 크롤링 뉴스의 성숙도/날짜(실제 근거).
  3) pivot_paths           전이경로 — 직무 내 저압력 업무(현 데이터). 인접 직무는 링크드인 데이터 필요.
  4) hiring_trend          채용 트렌드 — 채용 API 연동 필요(스텁).
  5) wage_impact           임금 타격 — 연봉 데이터 연동 필요(스텁).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store

_MATURITY_STAGE = {0: "논문", 1: "데모", 2: "베타", 3: "정식출시(GA)"}


def automation_breakdown(job_result: dict) -> dict:
    """과업별 자동화율 — task baseline 기반. 현재 손추정(calibrated:false)임을 정직 표기."""
    tasks = sorted(job_result.get("tasks", []), key=lambda t: -t.get("index", 0))
    return {
        "calibrated": False,
        "source": "직무-태스크 baseline (손추정) — O*NET·워크넷 연동 시 calibrated로 격상",
        "tasks": [{"name_ko": t.get("name_ko", ""), "automation_pct": t.get("index", 0),
                   "ci": t.get("ci", 10), "weather": t.get("weather", "")} for t in tasks],
    }


def tech_timeline(job_id: str) -> dict:
    """기술 상용화 타임라인 — 이 직무에 결박된 크롤링 뉴스를 성숙도·날짜로 정렬(실제 근거)."""
    items = []
    for e in store.load_events():
        if e.get("status") != "complete":
            continue
        affs = [a for a in (e.get("affected") or []) if a.get("job_id") == job_id]
        if not affs:
            continue
        maturity = max(int(a.get("factors", {}).get("maturity", 0)) for a in affs)
        items.append({
            "date": e.get("published_at", "")[:10],
            "stage": _MATURITY_STAGE.get(maturity, "논문"),
            "title": e.get("title", ""), "url": e.get("url", ""),
            "source_tier": e.get("source_tier", 3),
        })
    items.sort(key=lambda x: x["date"])
    return {"source": "크롤링 뉴스 근거(성숙도·날짜)",
            "items": items,
            "note": "" if items else "아직 이 직무에 결박된 근거 뉴스가 없습니다(배치 누적 시 채워짐)."}


def pivot_paths(job_result: dict) -> dict:
    """전이경로 — 직무 내 저압력(방어적) 업무로 비중 이동(현 데이터). 인접 직무는 외부 데이터 필요."""
    tasks = sorted(job_result.get("tasks", []), key=lambda t: t.get("index", 0))
    low = [t for t in tasks if t.get("weather") in ("맑음", "구름조금")][:3]
    if not low:
        low = tasks[:2]
    return {
        "source": "직무 내 저압력 업무 (현 baseline)",
        "within_job": [{"name_ko": t.get("name_ko", ""), "automation_pct": t.get("index", 0)} for t in low],
        "cross_job": None,
        "cross_job_note": "인접 직무 전이경로(어디로 옮기면 안전한가)는 링크드인 커리어 이동 데이터 연동 필요",
    }


# ── 외부 데이터 필요 — 정직한 스텁 (가짜 숫자 금지) ──────────────────────
def hiring_trend(job_result: dict) -> dict:
    """채용 수요 트렌드 — 채용 API(원티드/잡코리아 등) 연동 필요. 어댑터: HIRING_API_KEY + fetch 구현."""
    return {
        "available": bool(os.environ.get("HIRING_API_KEY")),
        "note": "채용 API 연동 시 — 최근 6개월 해당 직무 공고 증감률 + 'AI 활용' 우대조건 변화 표시.",
        "adapter": "env HIRING_API_KEY 설정 + deepdive._fetch_hiring 구현",
    }


def wage_impact(job_result: dict) -> dict:
    """임금 타격 — 연봉 데이터(KOSIS/플랫폼) 연동 필요. 가짜 추정 금지."""
    return {
        "available": bool(os.environ.get("WAGE_DATA_URL")),
        "note": "연봉 데이터 연동 시 — AI 도입에 따른 평균 임금 하락 압력 + 프리미엄 스킬 보유 시 임금 격차.",
        "adapter": "env WAGE_DATA_URL 설정 + deepdive._fetch_wage 구현",
    }


def build(job_result: dict) -> dict:
    """상세 분석 5섹션 묶음."""
    jid = job_result.get("job_id", "")
    return {
        "automation": automation_breakdown(job_result),
        "timeline": tech_timeline(jid),
        "pivot": pivot_paths(job_result),
        "hiring": hiring_trend(job_result),
        "wage": wage_impact(job_result),
    }


if __name__ == "__main__":
    import json
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from datetime import datetime, timezone
    from scoring import ScoringEngine
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    res = ScoringEngine(os.path.join(here, "data", "jobs")).score(
        [], now=datetime(2026, 6, 6, tzinfo=timezone.utc))["video-editor"]
    print(json.dumps(build(res), ensure_ascii=False, indent=2)[:900])
