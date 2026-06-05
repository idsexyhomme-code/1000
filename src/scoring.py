"""
커리어 시그널(WorkRadar) — AI 압력지수 점수 엔진 (루브릭 v2 구현)

PROJECT.md §1 루브릭 v2를 그대로 코드화.
핵심 원칙: 단일 0~100 숫자 격하 → 태스크 단위 · 근거등급 · 신뢰구간 · 기상예보 밴드.
모든 변동은 (출처/영향업무/방향/신뢰도/평이한 사유)를 동반해야 함.

실행: python3 src/scoring.py   (시드 직업 데모 출력)
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ── 출처 티어 → 신뢰도/델타캡 (§1.3 펌핑 방어) ──────────────────────────
# Tier1 공시·정부통계·고객사 직접발표 / Tier2 주요 언론 / Tier3 벤더·블로그
SOURCE_TIER = {
    1: {"confidence": 1.0, "delta_cap": 8.0},
    2: {"confidence": 0.7, "delta_cap": 5.0},
    3: {"confidence": 0.4, "delta_cap": 2.0},  # 벤더 단독 출처 max +2
}

# ── 델타 5요인 (§1.2). 각 요인의 최대값 → 합 14 → 0~8로 매핑 ──────────
FACTOR_MAX = {"proximity": 3, "maturity": 3, "adoption": 3, "irreversibility": 3, "scale": 2}
FACTOR_SUM_MAX = sum(FACTOR_MAX.values())  # 14
DELTA_SPAN = 8.0  # 1건당 ±0~8

# ── 감쇠 half-life (일). 공개·고정 함수 (§1.4) ────────────────────────
HALF_LIFE_DAYS = {"evidence": 90, "employment": 365, "regulation": None}  # None=만료 전 유지

DAILY_JOB_CAP = 12.0  # 직업당 1일 누적 Δ 상한 (폭주 방지)

# ── 기상예보 밴드 (§1.5) ──────────────────────────────────────────────
WEATHER_BANDS = [  # 경계 연속 (lo<=x<hi). 빈틈 없어야 함
    (0, 26, "맑음", "안정"),
    (26, 51, "구름조금", "변화 관측"),
    (51, 76, "흐림", "직접 영향권"),
    (76, 101, "태풍경보", "급격한 변화"),
]


def to_weather(index: float) -> tuple[str, str]:
    for lo, hi, label, desc in WEATHER_BANDS:
        if lo <= index < hi:
            return label, desc
    return ("태풍경보", "급격한 변화")


# ── 데이터 모델 ───────────────────────────────────────────────────────
@dataclass
class Affected:
    """한 이벤트가 특정 직무-태스크에 미치는 영향."""
    job_id: str
    task_id: str
    factors: dict          # {proximity, maturity, adoption, irreversibility, scale}
    direction: str         # automation | wage-pressure | tool-adoption | regulation | demand-growth
    reason_ko: str
    event_kind: str = "evidence"  # evidence | employment | regulation

    def sign(self) -> int:
        # demand-growth만 압력을 낮춤(-), 나머지는 +
        return -1 if self.direction == "demand-growth" else 1


@dataclass
class Event:
    event_id: str
    title: str
    url: str
    source_tier: int       # 1 | 2 | 3
    published_at: str      # ISO8601
    affected: list[Affected]
    # 같은 (기술+벤더+영향태스크+주장유형)은 1건으로 dedup (§1.2 이벤트 클러스터링)
    dedup_key: str = ""

    def published_dt(self) -> datetime:
        return datetime.fromisoformat(self.published_at.replace("Z", "+00:00"))


# ── 핵심: 1개 영향에 대한 원시 델타 산출 ──────────────────────────────
def raw_delta(aff: Affected, source_tier: int) -> float:
    """
    Δ = (요인합 / 14) * 8 * 방향부호, 그 뒤 신뢰도 가중 + 티어 캡.
    내부는 float 유지(반올림 정보손실 금지) — 표시층에서만 밴드/소수1자리.

    가드레일(Codex 리뷰 반영):
    - 출처 불명/미지 티어 → delta=0 (§1.4 '근거 없으면 변동 금지').
    - 요인은 0..max로 강제 클램프 (음수 주입으로 부호 뒤집힘 방지).
    """
    if source_tier not in SOURCE_TIER:
        return 0.0  # no source → delta=0
    s = sum(max(0, min(int(aff.factors.get(k, 0)), mx)) for k, mx in FACTOR_MAX.items())
    base = (s / FACTOR_SUM_MAX) * DELTA_SPAN          # 0~8
    tier = SOURCE_TIER[source_tier]
    val = base * tier["confidence"] * aff.sign()
    cap = tier["delta_cap"]                            # 벤더 단독 출처 max +2 등
    return max(-cap, min(cap, val))


def decay_factor(event_kind: str, age_days: float) -> float:
    """경과일에 따른 감쇠 계수(0~1). 규제 이벤트는 감쇠 없음."""
    hl = HALF_LIFE_DAYS.get(event_kind, 90)
    if hl is None:
        return 1.0
    return 0.5 ** (age_days / hl)


# ── 점수 엔진 ─────────────────────────────────────────────────────────
class ScoringEngine:
    def __init__(self, jobs_dir: str):
        self.jobs = {}
        for fn in sorted(os.listdir(jobs_dir)):
            if fn.endswith(".json"):
                with open(os.path.join(jobs_dir, fn), encoding="utf-8") as f:
                    j = json.load(f)
                    self.jobs[j["job_id"]] = j

    def _task(self, job_id: str, task_id: str) -> dict | None:
        for t in self.jobs.get(job_id, {}).get("tasks", []):
            if t["task_id"] == task_id:
                return t
        return None

    def score(self, events: list[Event], now: datetime | None = None) -> dict:
        """
        이벤트들을 적용해 각 직무의 현재 압력지수 산출.
        반환: { job_id: {index, ci, weather, tasks:[...], drivers:[...]} }
        dedup_key로 중복 이벤트 클러스터링, daily cap 적용.
        """
        now = now or datetime.now(timezone.utc)

        # ── 1) Evidence Normalization: 구조화 dedup (기술+벤더+job+task+방향) ──
        # 멀티태스크 이벤트가 서로 죽이지 않도록 key에 job_id/task_id/direction 포함.
        chosen: dict[tuple, tuple] = {}
        for ev in events:
            for aff in ev.affected:
                base_key = ev.dedup_key or ev.event_id
                key = (base_key, aff.job_id, aff.task_id, aff.direction)
                age = max(0.0, (now - ev.published_dt()).total_seconds() / 86400)
                d = raw_delta(aff, ev.source_tier) * decay_factor(aff.event_kind, age)
                prev = chosen.get(key)
                if prev is None or abs(d) > abs(prev[2]):
                    chosen[key] = (ev, aff, d)

        # ── 2) 결정적 순서: Tier 우선(1>2>3) → |delta| 큰 순 (cap 공정성) ──
        ordered = sorted(chosen.values(), key=lambda x: (x[0].source_tier, -abs(x[2])))

        # ── 3) 날짜별·직업별 cap: 상승/하락 버킷 분리 + 잔여분 부분 클램프 ──
        task_delta: dict[tuple, float] = {}
        used: dict[tuple, float] = {}   # (job_id, date, 'up'|'down') -> 누적 |Δ|
        drivers: dict[str, list] = {}
        for ev, aff, d in ordered:
            if d == 0:
                continue
            day = ev.published_dt().date().isoformat()
            bucket = "up" if d > 0 else "down"
            ukey = (aff.job_id, day, bucket)
            remaining = DAILY_JOB_CAP - used.get(ukey, 0.0)
            if remaining <= 0:
                continue
            d_eff = math.copysign(min(abs(d), remaining), d)   # 폭주 방지: 잔여만큼만
            used[ukey] = used.get(ukey, 0.0) + abs(d_eff)
            task_delta[(aff.job_id, aff.task_id)] = (
                task_delta.get((aff.job_id, aff.task_id), 0.0) + d_eff)
            tier = SOURCE_TIER[ev.source_tier]
            drivers.setdefault(aff.job_id, []).append({
                "task_id": aff.task_id, "delta": round(d_eff, 1), "direction": aff.direction,
                "source_tier": ev.source_tier, "confidence": tier["confidence"],
                "url": ev.url, "reason_ko": aff.reason_ko, "title": ev.title,
                "audit_label": "editorial_override" if getattr(ev, "override", False) else "auto",
            })

        # 직업별 집계: 직업지수 = 태스크지수 가중평균
        out = {}
        for job_id, job in self.jobs.items():
            tasks_out = []
            wsum = 0.0
            widx = 0.0
            for t in job["tasks"]:
                cur = t["baseline"] + task_delta.get((job_id, t["task_id"]), 0.0)
                cur = max(0.0, min(100.0, cur))
                w = t.get("weight", 1.0 / len(job["tasks"]))
                wsum += w
                widx += cur * w
                lbl, _ = to_weather(cur)
                tasks_out.append({
                    "task_id": t["task_id"], "name_ko": t["name_ko"],
                    "index": round(cur, 1), "ci": t.get("ci", 10),
                    "weather": lbl, "weight": w,
                })
            job_index = widx / wsum if wsum else job["baseline"]["index"]
            lbl, desc = to_weather(job_index)
            ds = sorted(drivers.get(job_id, []), key=lambda x: -abs(x["delta"]))
            out[job_id] = {
                "job_name_ko": job["job_name_ko"],
                "index": round(job_index, 1),
                "ci": job["baseline"].get("ci", 12),
                "weather": lbl, "weather_desc": desc,
                "tasks": sorted(tasks_out, key=lambda x: -x["index"]),
                "top_drivers": ds[:3],   # 점수를 민 핵심 근거 — 유료 트리거에 사용
            }
        return out


# ── 데모 ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    eng = ScoringEngine(os.path.join(here, "data", "jobs"))

    # 샘플 이벤트: 가상의 영상생성 AI 정식출시 (Tier1)
    sample = [
        Event(
            event_id="evt-demo-1",
            title="[데모] Adobe, Firefly에 '자동 컷편집' 정식기능 출시 + 유료고객 확보",
            url="https://example.com/news/1",
            source_tier=1,
            published_at="2026-06-05T00:00:00Z",
            dedup_key="firefly+adobe+cut-editing+GA",
            affected=[Affected(
                job_id="video-editor", task_id="cut-editing",
                factors={"proximity": 3, "maturity": 3, "adoption": 2, "irreversibility": 2, "scale": 2},
                direction="automation",
                reason_ko="컷편집 핵심업무를 직접 자동화하는 정식기능 + 실제 유료고객 확보로 도입신호 확인",
                event_kind="evidence",
            )],
        ),
        Event(
            event_id="evt-demo-2",
            title="[데모] 'Devin' 류 코딩에이전트, 주니어 반복코딩 자동화 데모 공개",
            url="https://example.com/news/2",
            source_tier=2,
            published_at="2026-06-04T00:00:00Z",
            dedup_key="devin+cognition+boilerplate+demo",
            affected=[Affected(
                job_id="junior-developer", task_id="boilerplate-coding",
                factors={"proximity": 3, "maturity": 1, "adoption": 1, "irreversibility": 1, "scale": 1},
                direction="automation",
                reason_ko="반복 코드작성 업무를 겨냥했으나 아직 데모 단계 + 도입신호 약함 → 압력 소폭",
                event_kind="evidence",
            )],
        ),
    ]

    result = eng.score(sample, now=datetime(2026, 6, 6, tzinfo=timezone.utc))
    for job_id, r in result.items():
        print(f"\n=== {r['job_name_ko']} | AI 압력지수 {r['index']} ±{r['ci']} "
              f"[{r['weather']} · {r['weather_desc']}] ===")
        for t in r["tasks"]:
            print(f"  - {t['name_ko']:<14} {t['index']:>5} [{t['weather']}]")
        if r["top_drivers"]:
            print("  ▶ 이번 변동 핵심 근거:")
            for d in r["top_drivers"]:
                print(f"     [{d['delta']:+}] {d['title']}  (T{d['source_tier']})")
                print(f"        ↳ {d['reason_ko']}")
