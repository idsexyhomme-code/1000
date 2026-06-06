"""
커리어 시그널 — Gemini 2.5 Pro 5요인 점수화 (R3)

뉴스 1건 + 직무 태스크 목록 → 영향(Affected) 리스트 산출.
- 키는 환경변수 GEMINI_API_KEY로만 (코드/저장소에 절대 박지 않음).
- responseMimeType=application/json 으로 JSON 강제 + 자체 검증.
- 근거 없으면 빈 배열. 직업/회사/개인을 '대체된다'고 단정 금지 (§1.6).
"""
from __future__ import annotations

import json
import os
import urllib.request

MODEL = "gemini-2.5-pro"
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

DIRECTIONS = {"automation", "wage-pressure", "tool-adoption", "regulation", "demand-growth"}
FACTOR_MAX = {"proximity": 3, "maturity": 3, "adoption": 3, "irreversibility": 3, "scale": 2}

_PROMPT = """\
너는 'AI 압력지수' 점수화 엔진이다. 아래 뉴스가 '{job_name}'의 각 업무에 미치는 AI 압력을 평가하라.
반드시 근거가 뉴스 본문에 명시될 때만 점수를 매겨라. 추측/과장 금지. 근거 없으면 affected를 빈 배열로.

[뉴스 제목] {title}
[뉴스 본문] {body}

[대상 업무 목록(task_id: 이름)]
{task_lines}

아래 JSON 스키마로만 출력(설명 텍스트 금지):
{{
  "technology": "<핵심 기술/제품명 1개, 예: Sora·Codex. 모르면 빈칸>",
  "vendor": "<해당 기술 제공 기업명, 예: OpenAI. 모르면 빈칸>",
  "affected": [
    {{
      "task_id": "<목록의 task_id 중 하나>",
      "factors": {{"proximity":0-3, "maturity":0-3, "adoption":0-3, "irreversibility":0-3, "scale":0-2}},
      "direction": "automation|wage-pressure|tool-adoption|regulation|demand-growth",
      "event_kind": "evidence|employment|regulation",
      "reason_ko": "한 문장. 뉴스의 어떤 사실 때문에 이 점수인지."
    }}
  ]
}}
※ technology/vendor는 같은 기술진척(논문→데모→GA)을 한 묶음으로 보기 위한 클러스터 키다. 일관된 표기를 써라.

채점 기준(앵커):
- proximity: 핵심업무 직접 타격 3 / 주변 1 / 무관 0
- maturity: 논문 0 / 데모 1 / 베타 2 / 정식출시(GA)+유료고객 3
- adoption: 고객사 실명·계약·고용변화 확인 3 / 일부 1 / 없음 0  (※'채용공고 감소' 단독 증거 금지)
- irreversibility: 재숙련 매우 어려움 3 / 쉬움 0
- scale: 대중 보급형 2 / 니치 0
절대 특정 직업/회사/개인이 '대체된다'고 단정하지 말 것. '관측된 자동화 압력'으로만 표현.
"""


def _key() -> str:
    k = os.environ.get("GEMINI_API_KEY")
    if not k:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 필요합니다 (코드에 키를 박지 말 것).")
    return k


def _validate(data: dict, valid_task_ids: set[str]) -> list[dict]:
    """스키마/범위 검증. 불량 항목은 드롭(조용히 점수 죽이지 않도록 호출측에서 로깅)."""
    out = []
    for a in data.get("affected", []):
        tid = a.get("task_id")
        if tid not in valid_task_ids:
            continue
        if a.get("direction") not in DIRECTIONS:
            continue
        factors = a.get("factors", {})
        clean = {k: max(0, min(int(factors.get(k, 0)), mx)) for k, mx in FACTOR_MAX.items()}
        out.append({
            "task_id": tid,
            "factors": clean,
            "direction": a["direction"],
            "event_kind": a.get("event_kind", "evidence"),
            "reason_ko": str(a.get("reason_ko", "")).strip(),
        })
    return out


def score_article(job_name: str, tasks: list[dict], title: str, body: str,
                  timeout: int = 60) -> dict:
    """뉴스 1건을 Gemini로 5요인 점수화.
    반환: {"technology", "vendor", "affected": [...]}  (meta는 dedup 클러스터 키용)."""
    valid_ids = {t["task_id"] for t in tasks}
    task_lines = "\n".join(f"- {t['task_id']}: {t['name_ko']}" for t in tasks)
    prompt = _PROMPT.format(job_name=job_name, title=title, body=body[:4000],
                            task_lines=task_lines)
    # 뉴스 채점 = routine 티어(저비용 2.5 Pro→flash, 대량 호출 대비)
    import gemini_client
    data, _model = gemini_client.generate_json(prompt, tier="routine", temperature=0.2, timeout=timeout)
    return {
        "technology": str(data.get("technology", "")).strip(),
        "vendor": str(data.get("vendor", "")).strip(),
        "affected": _validate(data, valid_ids),
    }


if __name__ == "__main__":
    # 라이브 스모크 테스트: 가상 뉴스 1건 점수화 (GEMINI_API_KEY 필요)
    tasks = [
        {"task_id": "cut-editing", "name_ko": "컷 편집"},
        {"task_id": "subtitle", "name_ko": "자막 생성"},
        {"task_id": "directing", "name_ko": "현장 디렉팅·기획"},
    ]
    res = score_article(
        "영상편집자", tasks,
        title="OpenAI, 영상편집 자동화 모델 'Sora Edit' 정식 출시…유료 고객사 확보",
        body="OpenAI가 컷 편집과 자막 생성을 자동화하는 Sora Edit를 정식 출시했다. "
             "이미 다수 미디어 기업이 유료로 도입했다고 밝혔다. 현장 촬영 디렉팅은 대상이 아니다.",
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
