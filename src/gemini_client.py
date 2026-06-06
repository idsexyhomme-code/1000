"""
커리어 시그널 — Gemini 호출 중앙 클라이언트 (모델 폴백 + backoff + 역할/비용 정책)

왜 필요한가:
- 프리뷰 모델은 죽는다(우리가 gemini-3-pro-preview deprecate로 이미 당함). 한 모델명에 박히면 그날 전부 멈춤.
- 레이트리밋(429)/일시오류(5xx)에 안 죽고 재시도해야 무한 루프가 안 끊김.
- 역할 분담(사용자 지시): 디자인·UI/UX·카피 = premium(Gemini 3.x 최대한), 루틴 채점 = routine(저비용).

정책: tier별 모델 체인을 앞에서부터 시도 → 모델이 죽거나(404/400) 막히면 다음으로 자동 강등,
      일시오류는 지수 backoff 재시도. 전 체인 실패 시에만 예외 → 호출측 결정적 폴백.
키는 env GEMINI_API_KEY로만(코드/저장소에 절대 박지 않음).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

# 역할별 모델 폴백 체인 (앞→뒤로 강등). 프리뷰가 죽어도 정식 모델로 떨어지게 끝에 안정 모델 배치.
CHAINS = {
    "premium": ["gemini-3.1-pro-preview", "gemini-2.5-pro", "gemini-2.5-flash"],  # 디자인/카피/액션플랜
    "routine": ["gemini-2.5-pro", "gemini-2.5-flash"],                            # 뉴스 채점 등
    "cheap":   ["gemini-2.5-flash", "gemini-flash-latest"],
}
MAX_RETRIES = 2        # 일시오류(429/5xx) 모델당 재시도 횟수 (과한 대기 방지)
BACKOFF_BASE = 1.6     # 지수 backoff 기준(초): 1, 1.6...
_RETRYABLE = {429, 500, 502, 503, 504}
_DROP_MODEL = {400, 403, 404}   # 모델 deprecated/없음/권한 → 재시도 말고 다음 모델로 강등


class _SoftFail(Exception):
    """HTTP 200이지만 사용 불가(빈 응답/MAX_TOKENS 절단/no candidates) → 다음 모델로 강등."""


def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY")
    if not k:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 필요합니다 (코드에 키 금지).")
    return k


def _post(model: str, payload: dict, timeout: int) -> str:
    req = urllib.request.Request(
        _ENDPOINT.format(model=model, key=_key()),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.load(r)
    cands = resp.get("candidates") or []
    if not cands:                                   # 안전필터 등으로 후보 없음
        raise _SoftFail(f"{model}: no candidates")
    cand = cands[0]
    fr = cand.get("finishReason")
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", [])).strip()
    if not text:                                    # 200이어도 빈 응답(3.x thinking이 토큰 소진 등)
        raise _SoftFail(f"{model}: empty text (finishReason={fr})")
    if fr == "MAX_TOKENS":                          # 절단된 출력 → 신뢰 불가
        raise _SoftFail(f"{model}: truncated MAX_TOKENS")
    return text


def generate(prompt: str, *, tier: str = "routine", json_mode: bool = False,
             temperature: float = 0.7, timeout: int = 60,
             max_output_tokens: int | None = None) -> tuple[str, str]:
    """모델 폴백 + backoff로 1회 생성. 반환: (text, used_model). 전 체인 실패 시 예외."""
    _key()  # 키 없으면 즉시 실패 (재시도/강등 무의미)
    chain = CHAINS.get(tier, CHAINS["routine"])
    cfg: dict = {"temperature": temperature}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    if max_output_tokens:
        cfg["maxOutputTokens"] = max_output_tokens
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg}

    last: Exception | None = None
    for model in chain:
        for attempt in range(MAX_RETRIES):
            try:
                return _post(model, payload, timeout), model
            except _SoftFail as e:             # 빈/절단 응답 → 재시도 무의미, 다음 모델로 강등
                last = e
                break
            except urllib.error.HTTPError as e:
                last = e
                if e.code in _DROP_MODEL:
                    break                      # 모델 가망 없음 → 다음 모델로 강등
                if e.code in _RETRYABLE:
                    if attempt < MAX_RETRIES - 1:   # 마지막 시도 뒤엔 안 잠
                        time.sleep(BACKOFF_BASE ** attempt)
                    continue
                break                          # 기타 4xx → 다음 모델 시도
            except Exception as e:             # 네트워크/타임아웃/파싱 → backoff 재시도
                last = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(BACKOFF_BASE ** attempt)
    raise RuntimeError(f"Gemini 전 체인 실패(tier={tier}, chain={chain}): "
                       f"{type(last).__name__} {last}")


def generate_json(prompt: str, *, tier: str = "routine", temperature: float = 0.4,
                  timeout: int = 60) -> tuple[dict, str]:
    """JSON 강제 생성 → 파싱된 dict + used_model 반환."""
    text, model = generate(prompt, tier=tier, json_mode=True, temperature=temperature, timeout=timeout)
    return json.loads(text), model


if __name__ == "__main__":
    # 라이브: premium 정상 + 폴백(죽은 프리뷰로 시작하는 체인) 검증
    print("=== premium 정상 호출 ===")
    txt, used = generate("한 문장으로 인사해줘", tier="premium", temperature=0.3)
    print(f"used={used} | text={txt[:40]}")
    assert txt, "빈 응답이면 안 됨"

    print("=== 폴백 검증: 죽은 모델로 시작 → 강등 ===")
    CHAINS["_test"] = ["gemini-3-pro-preview", "gemini-2.5-flash"]  # 앞은 deprecated(404)
    txt2, used2 = generate("한 문장으로 인사해줘", tier="_test")
    print(f"used={used2} (gemini-2.5-flash로 강등 기대) | text={txt2[:40]}")
    assert used2 == "gemini-2.5-flash", "폴백 실패"
    assert txt2, "폴백도 빈 응답이면 안 됨"
    print("[OK] 모델 폴백 + 빈응답 강등 동작")
