"""
커리어 시그널 — 생존 액션플랜 엔진 (유료 '상위 5% 대응법' 실체) (R4b)

한 직무 score 결과(scoring.ScoringEngine.score()[job_id]) → '이번 주에 실제로 할 일'
정확히 3가지를 처방한다. 경고에서 끝내지 않고 불안→건설적 행동으로 전환하는 게 목적.

설계(notify.make_push와 동일 패턴):
  Gemini 3.1 Pro 실호출(responseMimeType=application/json)
   → 자체검증(스키마/근거결박/업무실재/금칙어/3개강제)
   → 실패·검증탈락 시 결정적 폴백(입력 score만으로 동일 스키마 생성).

가드레일(필수, §1.5/§1.6 + 개인정보보호법 §37-2):
  - '대체된다/사라진다/실직/해고/퇴출' 등 단정·공포 표현 금지(금칙어 백스톱).
  - 모든 액션은 입력 tasks[]의 실재 고압력 업무 + top_drivers 근거뉴스에 1:1 결박.
  - 일반론('강의 들으세요') 금지 — defends_task 업무 맥락에 특정.
  - disclaimer_ko 고정 노출(개인 자동판정 아님·참고지표·예측 아님).

키 보안: GEMINI_API_KEY는 env로만 (코드/저장소에 절대 박지 않음).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import urllib.request

MODEL = "gemini-3.1-pro-preview"
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

# ── enum / 상수 ────────────────────────────────────────────────────────────
_WEATHER = ("맑음", "구름조금", "흐림", "태풍경보")
_HIGH_PRESSURE = ("흐림", "태풍경보")          # 고압력 판정 기준
_STRATEGY = ("defend", "pivot")
_DIFFICULTY = ("입문", "중급", "고급")
_KIND = ("ai_tool", "skill", "task_shift")

_DISCLAIMER = ("본 처방은 관측된 업무별 자동화 압력에 대한 일반 참고 가이드이며 "
               "특정 개인에 대한 자동 판정·진단이 아닙니다.")

# 단정·공포조작 금칙어 (notify._BANNED 재사용·확장 — §1.6 가드레일 백스톱)
_BANNED = ["대체됩니다", "대체된다", "대체될", "대체 확률", "사라집니다", "사라진다",
           "사라질", "끝났습니다", "끝났다", "끝난다", "실직", "해고", "퇴출",
           "지금 안 하면", "위험 급등", "도태"]

# 폴백/검증에서 쓰는 안전한 enum 정규화 기본값
_DEFAULT_DIFFICULTY = "중급"


# ── 공통 유틸 ──────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def _scrub(text: str) -> bool:
    """금칙어 백스톱: 단정·공포 표현이 하나라도 있으면 False."""
    return isinstance(text, str) and not any(b in text for b in _BANNED)


def _all_text(action: dict) -> list[str]:
    """한 액션의 사람이 읽는 모든 텍스트(금칙어 스캔 대상) 수집."""
    out = [action.get("title_ko", ""), action.get("payoff_ko", ""),
           action.get("defends_task_name_ko", "")]
    out.extend(str(s) for s in action.get("action_steps", []) or [])
    lt = action.get("learn_target") or {}
    out.append(str(lt.get("name", "")))
    wn = action.get("why_now") or {}
    out.append(str(wn.get("evidence_reason_ko", "")))
    return out


def _num(x, default: float) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _drivers(job_result: dict) -> list[dict]:
    return job_result.get("top_drivers") or []


def _tasks(job_result: dict) -> list[dict]:
    return job_result.get("tasks") or []


def _high_pressure_tasks(job_result: dict) -> list[dict]:
    """weather가 흐림/태풍경보인 업무를 index 내림차순으로. 없으면 index 상위로 보충."""
    tasks = _tasks(job_result)
    hi = [t for t in tasks if t.get("weather") in _HIGH_PRESSURE]
    hi.sort(key=lambda t: -_num(t.get("index"), 0))
    return hi


def _driver_for_task(job_result: dict, task_id: str) -> int:
    """해당 task_id를 '직접' 가리키는 top_drivers 인덱스. 없으면 -1.
    ★무매칭 시 0(엉뚱한 뉴스)로 폴백하지 않는다 — 업무B 처방에 업무A 근거 박는 교차오염 차단."""
    for i, d in enumerate(_drivers(job_result)):
        if d.get("task_id") == task_id:
            return i
    return -1


def _strongest_driver(job_result: dict) -> int:
    """직무 전반 압력을 대표하는 최강 근거(|delta| 최대) 인덱스. pivot 동기 결박용. 없으면 -1."""
    drivers = _drivers(job_result)
    if not drivers:
        return -1
    return max(range(len(drivers)), key=lambda i: abs(_num(drivers[i].get("delta"), 0)))


# ── Gemini 프롬프트 ────────────────────────────────────────────────────────
_SCHEMA_SNIPPET = """\
{
  "job_id": "<입력 job_id>",
  "job_name_ko": "<입력 직업명>",
  "as_of": "<ISO8601 호출시각>",
  "headline_weather": "맑음|구름조금|흐림|태풍경보",
  "actions": [
    {
      "defends_task_id": "<입력 고압력 업무 task_id 중 하나>",
      "defends_task_name_ko": "<그 업무의 name_ko 그대로>",
      "task_weather": "맑음|구름조금|흐림|태풍경보",
      "strategy_type": "defend|pivot",
      "title_ko": "<40자 이내, '~하기' 동사형>",
      "action_steps": ["<이번 주 실제 단계, 특정 툴·특정 산출물>", "..."],
      "learn_target": {"kind": "ai_tool|skill|task_shift", "name": "<구체 명칭>"},
      "why_now": {
        "source_driver_index": <근거뉴스 인덱스 0부터>,
        "evidence_title": "<top_drivers[i].title 인용>",
        "evidence_reason_ko": "<top_drivers[i].reason_ko 인용/파생>",
        "source_tier": <1|2|3>,
        "evidence_url": "<top_drivers[i].url>"
      },
      "difficulty": "입문|중급|고급",
      "time_hours": <0.5~10 수치>,
      "payoff_ko": "<80자 이내, '상쇄/흡수/비중 전환' 같은 비단정 표현>"
    }
  ],
  "disclaimer_ko": "<고정 문구>"
}"""

_PROMPT = """\
너는 '커리어 시그널'의 생존 액션플랜 엔진이다. 한 직무의 AI 압력 스냅샷(고압력 업무 + 근거뉴스)을 받아,
사용자가 '이번 주에 실제로 할 일' 정확히 3가지를 처방한다. 이것은 유료 '상위 5% 대응법'의 실체이므로,
남들이 모를 만큼 구체적이어야 한다.

[절대 규칙 — 위반 시 출력 전체 무효]
1) 모든 처방은 아래 [고압력 업무]와 [근거뉴스] 안에 실재하는 것에만 결박하라. 입력에 없는 업무·없는 근거·없는 툴 효과를 지어내지 마라.
2) 각 액션의 defends_task_id 는 반드시 [고압력 업무] 목록의 task_id 중 하나여야 한다(weather가 흐림/태풍경보인 것 우선).
3) 각 액션의 why_now.source_driver_index 는 [근거뉴스] 목록의 인덱스(0부터)여야 하고, evidence_title/evidence_reason_ko 는 그 뉴스를 인용·결박하라. 근거가 없으면 그 액션을 만들지 마라.
4) '대체된다/사라진다/실직/해고/퇴출/끝났다' 같은 단정·공포 표현 절대 금지. '관측된 자동화 압력'으로만 말하라. 특정 회사·개인 비난 금지.
5) 일반론 금지. '온라인 강의 들으세요/트렌드 파악하세요' 같은 만능 조언 금지. 반드시 defends_task의 업무 맥락에 특정한 실행을 써라.

[처방 설계 원칙]
- 고압력 업무가 3개 이상이면: 그 업무들을 strategy_type='defend'(그 업무 안에서 [근거뉴스]에 나온 AI를 '내 도구'로 흡수해 생산성/단가를 방어)로 다뤄라.
- 고압력 업무가 3개 미만이면: 부족분은 strategy_type='pivot'(AI 압력이 낮고 사람 가치가 높은 인접 업무 — 예: 기획·디렉팅·클라이언트 커뮤니케이션·품질검수 — 로 시간 비중을 옮기기)으로 채워라.
- 각 액션은 '이번 주' 단위로 끝나는 실행이어야 한다: action_steps 2~4개, 각 단계는 특정 도구로 특정 산출물 1개를 만드는 식의 구체 단위. action_steps 중 최소 1개는 '이번 주에 만들어낼 구체 산출물 1개'를 포함하라.
- time_hours 는 0.5~10 사이 현실값, difficulty 는 입문/중급/고급. 난이도와 시간이 행동과 어긋나지 않게 하라.
- learn_target.name 은 가능하면 [근거뉴스]에 등장한 기술/제품명과 연결하라.
- payoff_ko 는 '이걸 하면 무엇이 방어/전환되는지' 1문장, 단정·보장 금지('상쇄/흡수/비중 전환'처럼).
- 3개 액션이 같은 task_id+같은 strategy_type 으로 몰리지 말 것(서로 다른 업무 또는 defend/pivot 혼합으로 분산).

[입력]
직업: {job_name_ko} ({job_id}), 직무 날씨: {headline_weather}
고압력 업무(index 내림차순):
{high_pressure_tasks}
근거뉴스(top_drivers, 인덱스 0부터):
{top_drivers}

아래 JSON 스키마로만 출력(설명 텍스트 금지, responseMimeType=application/json):
{schema_snippet}

※ disclaimer_ko 에는 다음 문구를 그대로 넣어라: '{disclaimer}' (개인정보보호법 §37-2 준수)
※ as_of 는 호출 시각(ISO8601)을 넣어라. source/guardrail_ok 는 호출측이 채우므로 비워도 된다.
"""


def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY")
    if not k:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 필요합니다 (코드에 키를 박지 말 것).")
    return k


def _fmt_tasks_for_prompt(job_result: dict) -> str:
    hi = _high_pressure_tasks(job_result)
    if not hi:  # 고압력 0개면 전 태스크 index 상위 제공(pivot 매칭용)
        hi = sorted(_tasks(job_result), key=lambda t: -_num(t.get("index"), 0))[:5]
    lines = [f"{t.get('task_id')} | {t.get('name_ko')} | "
             f"{_num(t.get('index'), 0):.1f} | {t.get('weather', '')}" for t in hi]
    return "\n".join(lines) or "(고압력 업무 없음)"


def _fmt_drivers_for_prompt(job_result: dict) -> str:
    lines = []
    for i, d in enumerate(_drivers(job_result)):
        lines.append(f"[{i}] (T{d.get('source_tier', 3)}) {d.get('title', '')} — "
                     f"{d.get('reason_ko', '')} ({d.get('url', '')})")
    return "\n".join(lines) or "(근거뉴스 없음)"


def _gemini_plan(job_result: dict, timeout: int = 60) -> dict:
    prompt = _PROMPT.format(
        job_name_ko=job_result.get("job_name_ko", ""),
        job_id=job_result.get("job_id", ""),
        headline_weather=job_result.get("weather", "흐림"),
        high_pressure_tasks=_fmt_tasks_for_prompt(job_result),
        top_drivers=_fmt_drivers_for_prompt(job_result),
        schema_snippet=_SCHEMA_SNIPPET,
        disclaimer=_DISCLAIMER,
    )
    # 액션플랜(해자 카피) = premium 티어(3.1 Pro → 자동강등 + backoff)
    import gemini_client
    plan, _model = gemini_client.generate_json(prompt, tier="premium", temperature=0.6, timeout=timeout)
    return plan


# ── 검증 (gemini_scorer._validate와 동일한 'drop invalid' 패턴) ──────────────
def _validate_action(action: dict, job_result: dict) -> dict | None:
    """한 액션을 스키마·근거결박·업무실재·금칙어로 검증. 통과 시 정규화된 액션, 실패 시 None."""
    if not isinstance(action, dict):
        return None

    tasks = {t.get("task_id"): t for t in _tasks(job_result)}
    drivers = _drivers(job_result)

    # 1) 업무 실재 검증 — defends_task_id 가 입력 tasks[]에 실제 존재
    tid = action.get("defends_task_id")
    if tid not in tasks:
        return None
    task = tasks[tid]

    # 2) strategy_type 먼저 (근거 결박 규칙이 전략에 따라 다름)
    strategy = action.get("strategy_type")
    if strategy not in _STRATEGY:
        return None

    # 3) 근거 결박 — index 유효 + (defend면) driver가 이 업무를 '직접' 가리킬 것
    why = action.get("why_now") or {}
    try:
        di = int(why.get("source_driver_index"))
    except (TypeError, ValueError):
        return None
    if not (0 <= di < len(drivers)):
        return None
    drv = drivers[di]
    if strategy == "defend" and drv.get("task_id") != tid:
        # 모델이 엉뚱한 driver를 인덱싱한 환각 근거 → 이 업무 직결 driver로 재바인딩, 없으면 드롭
        mi = _driver_for_task(job_result, tid)
        if mi < 0:
            return None
        di, drv = mi, drivers[mi]
    difficulty = action.get("difficulty")
    if difficulty not in _DIFFICULTY:
        difficulty = _DEFAULT_DIFFICULTY
    lt = action.get("learn_target") or {}
    kind = lt.get("kind")
    if kind not in _KIND:
        return None

    # 4) action_steps 2~4개
    steps = [str(s).strip() for s in (action.get("action_steps") or []) if str(s).strip()]
    if not (2 <= len(steps) <= 4):
        return None
    steps = steps[:4]

    # 5) time_hours 0.5~10 수치
    th = _num(action.get("time_hours"), 0)
    if not (0.5 <= th <= 10):
        return None

    # 6) 근거 일치 — title/reason 을 입력 driver 값으로 결박(지어내기 차단)
    norm = {
        "defends_task_id": tid,
        "defends_task_name_ko": task.get("name_ko", ""),   # tasks[].name_ko 그대로 결박
        "task_weather": task.get("weather", "") if task.get("weather") in _WEATHER else "흐림",
        "strategy_type": strategy,
        "title_ko": str(action.get("title_ko", "")).strip()[:40],
        "action_steps": [s[:90] for s in steps],
        "learn_target": {"kind": kind, "name": str(lt.get("name", "")).strip()},
        "why_now": {
            "source_driver_index": di,
            "evidence_title": drv.get("title", ""),         # driver 값으로 강제 결박
            "evidence_reason_ko": (str(why.get("evidence_reason_ko", "")).strip()
                                   or drv.get("reason_ko", "")),
            "source_tier": int(drv.get("source_tier", 3)) if drv.get("source_tier") in (1, 2, 3) else 3,
            "evidence_url": drv.get("url", ""),
        },
        "difficulty": difficulty,
        "time_hours": round(th, 1),
        "payoff_ko": str(action.get("payoff_ko", "")).strip()[:80],
    }

    # 7) 금칙어 백스톱 — 어떤 텍스트에도 단정·공포 표현 없을 것
    if not all(_scrub(t) for t in _all_text(norm)):
        return None
    if not norm["title_ko"]:
        return None
    return norm


def _validate_plan(plan: dict, job_result: dict) -> list[dict]:
    """plan.actions 검증 → 통과 액션만, 중복(task_id+strategy) 제거하여 최대 3개."""
    out: list[dict] = []
    seen: set = set()
    for a in (plan.get("actions") or []):
        v = _validate_action(a, job_result)
        if v is None:
            continue
        key = (v["defends_task_id"], v["strategy_type"])
        if key in seen:               # 같은 업무+같은 전략 중복 회피(일반론화 방지)
            continue
        seen.add(key)
        out.append(v)
        if len(out) == 3:
            break
    return out


# ── 결정적 폴백 (입력 score만으로 동일 스키마 생성) ───────────────────────────
def _pivot_task(job_result: dict) -> dict:
    """전환 대상: AI 압력 낮고 가치 높은 인접 업무(weather 맑음/구름조금, index 하위)."""
    low = [t for t in _tasks(job_result) if t.get("weather") not in _HIGH_PRESSURE]
    low.sort(key=lambda t: _num(t.get("index"), 0))
    if low:
        return low[0]
    # 저압력 업무가 없으면 가장 압력 낮은 업무를 전환 앵커로
    tasks = sorted(_tasks(job_result), key=lambda t: _num(t.get("index"), 0))
    return tasks[0] if tasks else {"task_id": "core", "name_ko": "핵심 업무", "weather": "흐림"}


def _fallback_action(task: dict, strategy: str, job_result: dict) -> dict:
    """근거에 정직하게 결박된 결정적 1개 액션. defend=업무 직결 driver, pivot=직무 전반 최강 driver.
    근거가 전혀 없으면 가짜 뉴스를 합성하지 않고 '근거 미확보'로 정직 표기(source_driver_index=-1)."""
    drivers = _drivers(job_result)
    di = (_driver_for_task(job_result, task.get("task_id")) if strategy == "defend"
          else _strongest_driver(job_result))   # pivot은 직무 전반 압력이 전환 동기
    drv = drivers[di] if di >= 0 else {}
    tname = task.get("name_ko", "핵심 업무")
    tech = drv.get("title", "").split("…")[0].split(",")[0].strip() if drv else ""

    if strategy == "defend":
        tool = f"'{tech}'" if tech else "근거뉴스의 AI 도구"
        title = f"{tool} 흡수해 '{tname}' 초벌 워크플로 1개 만들기"[:40]
        steps = [
            f"{tool}를 '{tname}'의 초벌 단계에 적용해 이번 주 1건 처리해본다",
            f"'{tname}' 샘플 산출물 1개를 AI 초벌+사람 검수 방식으로 완성한다",
            f"AI가 맡을 단계와 사람이 끝까지 쥘 단계를 가른 체크리스트 1장을 만든다",
        ]
        learn = ({"kind": "ai_tool", "name": tech} if tech
                 else {"kind": "skill", "name": f"{tname} AI 검수·오케스트레이션"})
        payoff = f"'{tname}'의 자동화 압력을 도구 흡수로 상쇄해 생산성 단가를 방어"[:80]
        difficulty, hours = "중급", 4.0
    else:  # pivot
        title = f"'{tname}' 비중 늘려 고가치 업무로 시간 전환하기"[:40]
        steps = [
            f"이번 주 업무 시간 일부를 압력 낮은 '{tname}'로 의도적으로 옮긴다",
            f"'{tname}' 산출물(기획안·디렉팅 노트·QC 리포트) 샘플 1개를 만든다",
            f"AI 산출물을 사람이 검수·디렉팅하는 워크플로에서 내 역할 1개를 정의한다",
        ]
        learn = {"kind": "task_shift", "name": f"{tname} 중심 역할로 비중 이동"}
        payoff = f"자동화 압력 낮은 '{tname}'로 시간 비중을 전환해 사람 가치 영역을 키움"[:80]
        difficulty, hours = "중급", 3.0

    if drv:   # 실제 근거 결박
        why = {
            "source_driver_index": di,
            "evidence_title": drv.get("title", ""),
            "evidence_reason_ko": drv.get("reason_ko", ""),
            "source_tier": int(drv.get("source_tier", 3)) if drv.get("source_tier") in (1, 2, 3) else 3,
            "evidence_url": drv.get("url", ""),
        }
    else:     # ★근거 전무 → 가짜 합성 금지, 정직하게 미확보 표기
        why = {
            "source_driver_index": -1,
            "evidence_title": "근거뉴스 없음 — 직무 전반 압력 참고",
            "evidence_reason_ko": "이번 주 이 업무에 직접 결박된 근거뉴스가 없어 일반 가이드로 제공",
            "source_tier": 3,
            "evidence_url": "",
        }

    return {
        "defends_task_id": task.get("task_id", "core"),
        "defends_task_name_ko": tname,
        "task_weather": task.get("weather", "흐림") if task.get("weather") in _WEATHER else "흐림",
        "strategy_type": strategy,
        "title_ko": title,
        "action_steps": [s[:90] for s in steps],
        "learn_target": learn,
        "why_now": why,
        "difficulty": difficulty,
        "time_hours": hours,
        "payoff_ko": payoff,
    }


def fallback_plan(job_result: dict) -> dict:
    """Gemini 없이도 동작하는 결정적 폴백 — 동일 스키마, 항상 guardrail_ok=True.
    고압력 업무를 defend로, 3개 미달이면 pivot으로 보충(일반론화 방지)."""
    hi = _high_pressure_tasks(job_result)
    actions: list[dict] = []
    seen: set = set()

    # 1) 고압력 업무 → defend (그 업무에 '직접' 결박된 근거가 있을 때만 — 교차오염 방지)
    for t in hi:
        if len(actions) == 3:
            break
        if _driver_for_task(job_result, t.get("task_id")) < 0:
            continue   # 근거 없는 defend는 만들지 않음(pivot이 보충)
        key = (t.get("task_id"), "defend")
        if key in seen:
            continue
        seen.add(key)
        actions.append(_fallback_action(t, "defend", job_result))

    # 2) 부족분 → pivot(저압력 고가치 업무로 전환)
    if len(actions) < 3:
        pv = _pivot_task(job_result)
        # pivot 앵커가 defend로 이미 쓰였으면 다른 저압력 업무 시도
        low_pool = [t for t in _tasks(job_result) if t.get("weather") not in _HIGH_PRESSURE]
        low_pool.sort(key=lambda t: _num(t.get("index"), 0))
        pool = low_pool or [pv]
        pi = 0
        while len(actions) < 3:
            t = pool[pi % len(pool)]
            key = (t.get("task_id"), "pivot")
            pi += 1
            if key in seen:
                if pi > len(pool) * 2:   # 안전 탈출: 같은 업무라도 채움
                    actions.append(_fallback_action(t, "pivot", job_result))
                continue
            seen.add(key)
            actions.append(_fallback_action(t, "pivot", job_result))

    # 3) 그래도 부족하면(태스크/근거가 거의 없는 극단 입력) headline 기반으로 채움
    while len(actions) < 3:
        ht = job_result.get("headline_task") or {"task_id": "core", "name_ko": "핵심 업무",
                                                  "weather": "흐림"}
        actions.append(_fallback_action(ht, "defend" if len(actions) % 2 == 0 else "pivot",
                                        job_result))

    # 모든 액션이 실제 근거(>=0)에 결박됐을 때만 guardrail_ok — 미확보(-1) 있으면 False로 정직 표기
    grounded = all(a["why_now"]["source_driver_index"] >= 0 for a in actions[:3])
    return _assemble(job_result, actions[:3], source="fallback", guardrail_ok=grounded)


# ── 조립 ──────────────────────────────────────────────────────────────────
def _assemble(job_result: dict, actions: list[dict], source: str, guardrail_ok: bool) -> dict:
    weather = job_result.get("weather", "흐림")
    return {
        "job_id": job_result.get("job_id", ""),
        "job_name_ko": job_result.get("job_name_ko", ""),
        "as_of": _now_iso(),
        "headline_weather": weather if weather in _WEATHER else "흐림",
        "actions": actions,
        "disclaimer_ko": _DISCLAIMER,
        "source": source,
        "guardrail_ok": guardrail_ok,
    }


# ── 공개 API ──────────────────────────────────────────────────────────────
def make_action_plan(job_result: dict, use_gemini: bool = True) -> dict:
    """한 직무 score 결과 → 이번 주 생존 액션 3가지 (SurvivalActionPlan).

    notify.make_push와 동일: Gemini 성공+가드레일통과=gemini, 아니면 결정적 폴백.
    반환 스키마: job_id, job_name_ko, as_of, headline_weather, actions[3],
                disclaimer_ko, source('gemini'|'fallback'), guardrail_ok.
    """
    if not isinstance(job_result, dict):
        raise TypeError("job_result must be a dict (score()[job_id] 한 직무 스냅샷)")

    if use_gemini and os.environ.get("GEMINI_API_KEY"):
        try:
            raw = _gemini_plan(job_result)
            valid = _validate_plan(raw, job_result)
            if len(valid) == 3:
                return _assemble(job_result, valid, source="gemini", guardrail_ok=True)
            print(f"[actionplan] Gemini 검증 후 유효 액션 {len(valid)}/3 → 폴백 보충")
        except Exception as e:  # 네트워크/JSON/스키마 실패 → 결정적 폴백
            print(f"[actionplan] Gemini 실패→폴백: {type(e).__name__} {e}")

    return fallback_plan(job_result)


# ── 스모크 테스트 ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    demo = {
        "job_id": "video-editor",
        "job_name_ko": "영상편집자",
        "index": 71.0, "ci": 9.0, "weather": "태풍경보",
        "headline_task": {"task_id": "cut-editing", "name_ko": "컷 편집",
                          "index": 82.0, "weather": "태풍경보"},
        "tasks": [
            {"task_id": "cut-editing", "name_ko": "컷 편집", "index": 82.0, "ci": 8, "weather": "태풍경보"},
            {"task_id": "subtitle", "name_ko": "자막 생성", "index": 74.0, "ci": 9, "weather": "흐림"},
            {"task_id": "color", "name_ko": "색 보정", "index": 58.0, "ci": 11, "weather": "흐림"},
            {"task_id": "directing", "name_ko": "현장 디렉팅·기획", "index": 31.0, "ci": 12, "weather": "맑음"},
            {"task_id": "client", "name_ko": "클라이언트 커뮤니케이션", "index": 22.0, "ci": 12, "weather": "맑음"},
        ],
        "top_drivers": [
            {"task_id": "cut-editing", "delta": 3.1, "direction": "automation",
             "source_tier": 3, "confidence": 0.62,
             "url": "https://example.com/sora-edit",
             "reason_ko": "컷 편집 자동화 정식기능(GA) 출시로 해당 업무 자동화 신호 상승",
             "title": "OpenAI, 영상 자동편집 모델 'Sora Edit' 정식 출시…유료 고객사 확보"},
            {"task_id": "subtitle", "delta": 2.0, "direction": "tool-adoption",
             "source_tier": 2, "confidence": 0.71,
             "url": "https://example.com/auto-caption",
             "reason_ko": "자막 자동생성 도구의 미디어사 도입 확대 보도",
             "title": "주요 미디어, 자막 자동생성 도입 확대"},
            {"task_id": "color", "delta": 1.4, "direction": "tool-adoption",
             "source_tier": 2, "confidence": 0.66,
             "url": "https://example.com/auto-color",
             "reason_ko": "색 보정 AI 프리셋의 실무 채택 사례 증가",
             "title": "AI 색보정 프리셋, 편집 스튜디오 채택 증가"},
        ],
    }

    print("=== Fallback (use_gemini=False) ===")
    fb = make_action_plan(demo, use_gemini=False)
    print(json.dumps(fb, ensure_ascii=False, indent=2))

    # 폴백 자체검증: 스키마/개수/금칙어/근거결박
    assert fb["source"] == "fallback" and fb["guardrail_ok"] is True
    assert len(fb["actions"]) == 3, "actions 정확히 3개여야 함"
    assert fb["disclaimer_ko"] == _DISCLAIMER
    valid_ids = {t["task_id"] for t in demo["tasks"]}
    for a in fb["actions"]:
        assert a["defends_task_id"] in valid_ids, "defends_task_id 실재 검증"
        assert a["strategy_type"] in _STRATEGY
        assert a["difficulty"] in _DIFFICULTY
        assert a["learn_target"]["kind"] in _KIND
        assert 2 <= len(a["action_steps"]) <= 4
        assert 0.5 <= a["time_hours"] <= 10
        _sdi = a["why_now"]["source_driver_index"]
        assert _sdi == -1 or 0 <= _sdi < len(demo["top_drivers"])  # -1 = 정직한 근거 미확보
        for t in _all_text(a):
            assert _scrub(t), f"금칙어 발견: {t!r}"
    print("\n[OK] 폴백 스모크 검증 통과 (3개 액션·근거결박·업무실재·금칙어 클린)")

    if os.environ.get("GEMINI_API_KEY"):
        print("\n=== Gemini live (GEMINI_API_KEY 감지) ===")
        gp = make_action_plan(demo, use_gemini=True)
        print("source:", gp["source"], "| guardrail_ok:", gp["guardrail_ok"],
              "| actions:", len(gp["actions"]))
        print(json.dumps(gp, ensure_ascii=False, indent=2))
    else:
        print("\n[skip] GEMINI_API_KEY 없음 → 라이브 호출 생략 (폴백만 검증)")
