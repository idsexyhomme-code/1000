"""
커리어 시그널 — 카카오 채널봇 푸시 카피 생성 (R4a)

점수 스냅샷 → 푸시 메시지 1줄.
원칙(§1.5/§1.6): 공포 훅 유지하되 '대체된다' 단정 금지, 근거(뉴스)+영향업무+다음행동 동반,
기상예보 메타포, 직업/회사/개인 비난 금지. 단일 숫자만 푸시하지 않음.

카피는 Gemini 2.5 Pro 실호출(키 env GEMINI_API_KEY) → 가드레일 후처리 → 실패 시 폴백 템플릿.
"""
from __future__ import annotations

import json
import os

MAX_LEN = 90

# 단정·공포조작 금칙어 (§1.6 법적/윤리 가드레일)
_BANNED = ["대체됩니다", "대체된다", "대체될", "대체 확률", "사라집니다", "사라진다", "사라질",
           "끝났습니다", "끝난다", "실직", "해고", "퇴출"]


def _guardrail_ok(text: str) -> bool:
    return bool(text) and len(text) <= MAX_LEN + 20 and not any(b in text for b in _BANNED)


def _delta_phrase(delta) -> str:
    if not isinstance(delta, (int, float)) or abs(delta) < 0.1:
        return "압력 변화 관측"
    return f"압력 {'상승' if delta > 0 else '완화'} ({delta:+.1f})"


def _ellip(s: str, n: int) -> str:
    """n자에 맞춰 자르되 잘렸으면 '…' 표기(맹목 절단 방지). n<=0이면 빈 문자열."""
    if n <= 0:
        return ""
    return s if len(s) <= n else s[:max(1, n - 1)] + "…"


def fallback_copy(snap: dict) -> str:
    """Gemini 없이도 동작하는 결정적 템플릿. action_title 있으면 이번 주 할 일 노출.
    ★변동부(액션/근거)만 예산에 맞춰 자른다 — 끝의 CTA/액션이 통째 절단으로 사라지지 않게(리텐션 보호)."""
    job = snap.get("job_name_ko", "내 직무")
    task = (snap.get("headline_task") or {}).get("name_ko", "핵심 업무")
    weather = snap.get("weather", "흐림")
    drv = (snap.get("top_drivers") or [{}])[0]
    src = drv.get("title", "최신 AI 동향")
    action = snap.get("action_title")
    if action:   # 경고→구명조끼: 이번 주 구체 행동 1개. 액션이 핵심이라 prefix 보존 후 액션만 축약.
        prefix = f"[{weather}] '{task}' 업무 {_delta_phrase(snap.get('delta'))}. 이번 주: "
        msg = prefix + _ellip(action, MAX_LEN - len(prefix))
    else:        # 근거 뒤 CTA '대응전략 보기'는 고정 보존, 근거(src)만 남는 예산에 맞춰 축약.
        prefix = f"[{weather}] '{job}'의 '{task}' 업무 {_delta_phrase(snap.get('delta'))}. 근거: "
        suffix = "… 대응전략 보기"
        msg = prefix + _ellip(src, MAX_LEN - len(prefix) - len(suffix)).rstrip("…") + suffix
    return msg[:MAX_LEN]


_PROMPT = """\
너는 '커리어 시그널' 카카오 푸시 카피라이터다. 아래 스냅샷으로 푸시 메시지 1개를 써라.
규칙(필수):
- {maxlen}자 이내, 한 줄, 메시지만 출력(따옴표/설명 금지).
- 공포 훅은 허용하되 '대체된다/사라진다/실직' 같은 단정 절대 금지. '관측된 자동화 압력'처럼 표현.
- 반드시 포함: (1) 어떤 업무가 (2) 어떤 근거(뉴스)로 (3) 압력이 어떻게 변했는지 + 행동 유도(대응전략/리스킬링).
- 기상예보 메타포 활용 가능. 직업/회사/개인을 비난하지 말 것. 단일 숫자만 강조하지 말 것.

[스냅샷]
직업: {job}
대표 영향업무: {task} (날씨: {task_weather})
직무 날씨: {weather}
변화: {delta}
핵심 근거 뉴스: {drv_title}
근거 요약: {drv_reason}
출처 등급: T{drv_tier} (T1 공식 > T2 언론 > T3 벤더PR)
{action_line}
"""


def _gemini_copy(snap: dict, timeout: int = 40) -> str:
    drv = (snap.get("top_drivers") or [{}])[0]
    action = snap.get("action_title")
    prompt = _PROMPT.format(
        maxlen=MAX_LEN,
        job=snap.get("job_name_ko", ""),
        task=(snap.get("headline_task") or {}).get("name_ko", ""),
        task_weather=(snap.get("headline_task") or {}).get("weather", ""),
        weather=snap.get("weather", ""),
        delta=_delta_phrase(snap.get("delta")),
        drv_title=drv.get("title", ""),
        drv_reason=drv.get("reason_ko", ""),
        drv_tier=drv.get("source_tier", 3),
        action_line=(f"이번 주 추천 행동(메시지 끝에 '이번 주: ~' 한 구절로 간결히 녹여라): {action}"
                     if action else ""),
    )
    # 카피 = premium 티어(3.1 Pro → 자동강등 + backoff). 결과 빈 문자열이면 호출측이 폴백 처리.
    import gemini_client
    text, _model = gemini_client.generate(prompt, tier="premium", temperature=0.8, timeout=timeout)
    return text.strip().strip('"')


def make_push(snap: dict, use_gemini: bool = True) -> dict:
    """푸시 메시지 생성. 반환: {text, source('gemini'|'fallback'), guardrail_ok}."""
    if use_gemini and os.environ.get("GEMINI_API_KEY"):
        try:
            text = _gemini_copy(snap)
            if _guardrail_ok(text):
                return {"text": text, "source": "gemini", "guardrail_ok": True}
        except Exception as e:
            print(f"[notify] Gemini 실패→폴백: {type(e).__name__} {e}")
    return {"text": fallback_copy(snap), "source": "fallback", "guardrail_ok": True}


if __name__ == "__main__":
    demo = {
        "job_name_ko": "영상편집자", "weather": "흐림", "delta": 2.4,
        "headline_task": {"name_ko": "컷 편집", "weather": "태풍경보"},
        "top_drivers": [{
            "title": "OpenAI, 영상 자동편집 모델 정식 출시 + 유료 고객사 확보",
            "reason_ko": "컷 편집 자동화 정식기능 출시로 해당 업무 자동화 신호 상승",
            "source_tier": 3, "url": "https://example.com",
        }],
    }
    print("Gemini:", make_push(demo, use_gemini=True))
    print("Fallback:", make_push(demo, use_gemini=False))
