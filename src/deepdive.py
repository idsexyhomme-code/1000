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
_JOBS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jobs")


def _load_anchor(job_id: str):
    """job 파일의 baseline.index_anchor(외부 AIOE 노출 앵커)를 로드. 없으면 None.
    scoring 결과는 baseline을 안 담으므로 calibrate가 적용한 앵커를 파일에서 직접 읽는다."""
    if not job_id:
        return None
    path = os.path.join(_JOBS_DIR, f"{job_id}.json")
    if not os.path.exists(path):
        return None
    try:
        import json
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("baseline", {}).get("index_anchor")
    except Exception:
        return None


def automation_breakdown(job_result: dict) -> dict:
    """과업별 자동화율 — task baseline 기반. 표시 점수는 손추정(calibrated:false), 단 직업-레벨
    외부 노출 앵커(AIOE)가 있으면 참고치로 함께 노출(정직한 외부 결박 근거)."""
    tasks = sorted(job_result.get("tasks", []), key=lambda t: -t.get("index", 0))
    return {
        "calibrated": False,
        "source": "직무-태스크 baseline (손추정) — O*NET·워크넷 연동 시 calibrated로 격상",
        "anchor": _load_anchor(job_result.get("job_id", "")),
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


# ── 외부 데이터 어댑터 — env 엔드포인트 있으면 실호출, 없거나 실패하면 정직 스텁 ──
# 원칙: 절대 숫자를 합성하지 않는다. 실데이터가 들어올 때만 진짜로 표기.
def _http_get_json(url: str, timeout: float = 8.0):
    """stdlib만으로 JSON GET. 실패 시 None (예외 삼키되 날조 안 함)."""
    import json
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "career-signal/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (env-set URL)
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _job_query(job_result: dict) -> str:
    """채용/임금 조회용 직무 식별자(이름 우선, 없으면 id)."""
    return (job_result.get("name_ko") or job_result.get("name")
            or job_result.get("job_id", ""))


def _fetch_hiring(job_result: dict):
    """HIRING_API_URL 설정 시 실호출. 응답 스키마(필수):
         {"trend_pct": <float, 최근 6개월 공고 증감률>,
          "ai_pref_pct": <float, 'AI 활용' 우대조건 비율>,
          "period": <str>, "source": <str>}
       URL의 {job}/{key}는 치환. 미설정·실패·스키마 불일치 시 None → 정직 스텁."""
    import urllib.parse
    base = os.environ.get("HIRING_API_URL")
    if not base:
        return None
    url = (base.replace("{job}", urllib.parse.quote(_job_query(job_result)))
               .replace("{key}", urllib.parse.quote(os.environ.get("HIRING_API_KEY", ""))))
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return None
    try:
        return {
            "trend_pct": float(data["trend_pct"]),
            "ai_pref_pct": float(data["ai_pref_pct"]),
            "period": str(data.get("period", "")),
            "source": str(data.get("source", "")),
        }
    except (KeyError, TypeError, ValueError):
        return None  # 스키마 불일치 → 가짜로 메우지 않음


def _fetch_wage(job_result: dict):
    """WAGE_DATA_URL 설정 시 실호출. job_id로 키된 JSON 매핑을 받아 해당 직무 추출:
         {"<job_id>": {"median_krw": <int>, "yoy_pct": <float>,
                        "premium_gap_pct": <float>, "source": <str>}}
       또는 단일 객체(이미 해당 직무). 미설정·실패·해당직무 없음 시 None → 정직 스텁."""
    url = os.environ.get("WAGE_DATA_URL")
    if not url:
        return None
    data = _http_get_json(url)
    if not isinstance(data, dict):
        return None
    jid = job_result.get("job_id", "")
    row = data.get(jid) if jid in data else data  # 매핑이면 직무 추출, 아니면 단일 객체
    if not isinstance(row, dict):
        return None
    try:
        return {
            "median_krw": int(row["median_krw"]),
            "yoy_pct": float(row["yoy_pct"]),
            "premium_gap_pct": float(row.get("premium_gap_pct", 0.0)),
            "source": str(row.get("source", "")),
        }
    except (KeyError, TypeError, ValueError):
        return None


def hiring_trend(job_result: dict) -> dict:
    """채용 수요 트렌드 — HIRING_API_URL 연동 시 실데이터, 아니면 정직 스텁(가짜 숫자 금지)."""
    data = _fetch_hiring(job_result)
    return {
        "available": data is not None,
        "data": data,
        "note": "채용 API 연동 시 — 최근 6개월 해당 직무 공고 증감률 + 'AI 활용' 우대조건 변화 표시.",
        "adapter": "env HIRING_API_URL(+HIRING_API_KEY) 설정 — {job}/{key} 치환, deepdive._fetch_hiring",
    }


def wage_impact(job_result: dict) -> dict:
    """임금 타격 — WAGE_DATA_URL 연동 시 실데이터, 아니면 정직 스텁(가짜 추정 금지)."""
    data = _fetch_wage(job_result)
    return {
        "available": data is not None,
        "data": data,
        "note": "연봉 데이터 연동 시 — AI 도입에 따른 평균 임금 하락 압력 + 프리미엄 스킬 보유 시 임금 격차.",
        "adapter": "env WAGE_DATA_URL 설정(job_id 키 JSON) — deepdive._fetch_wage",
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
