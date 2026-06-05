"""
커리어 시그널 — 뉴스 수집 → 이벤트 변환 파이프라인 (골격)

흐름: (1) 소스 수집 → (2) 직무 관련성 필터 → (3) LLM으로 5요인 점수화 →
      (4) dedup_key 생성 → (5) Event로 저장 → scoring.ScoringEngine에 투입.

※ R2에서는 인터페이스/골격만. 실제 LLM 점수화 프롬프트와 소스 어댑터는 R3에서 구현.
"""
from __future__ import annotations

from dataclasses import dataclass

# 소스 티어링 (§1.3) — 도메인 → tier 매핑 (확장 예정)
SOURCE_TIER_MAP = {
    # Tier1: 공식/공시/정부
    "openai.com": 1, "blog.google": 1, "anthropic.com": 1, "kostat.go.kr": 1, "work.go.kr": 1,
    # Tier2: 주요 언론
    "techcrunch.com": 2, "theverge.com": 2, "yna.co.kr": 2, "zdnet.co.kr": 2,
    # Tier3: 벤더 PR/블로그/커뮤니티 (단독 max +2)
    "medium.com": 3, "reddit.com": 3, "news.ycombinator.com": 3,
}


def tier_of(url: str) -> int:
    for dom, t in SOURCE_TIER_MAP.items():
        if dom in url:
            return t
    return 3  # 미지 출처는 보수적으로 Tier3


@dataclass
class RawArticle:
    title: str
    url: str
    published_at: str
    body: str


class NewsSource:
    """소스 어댑터 인터페이스. RSS/API/스크래퍼가 이걸 구현."""
    name: str = "base"

    def fetch(self) -> list[RawArticle]:
        raise NotImplementedError


# --- LLM 점수화 인터페이스 (R3에서 Gemini/Claude로 구현) -----------------
SCORING_PROMPT_TEMPLATE = """\
다음 뉴스가 '{job_name}'의 각 업무에 미치는 AI 압력을 평가하라.
반드시 근거가 뉴스 본문에 있을 때만 점수를 매기고, 추측 금지.

[뉴스] {title}
{body}

[대상 업무 목록] {tasks}

각 영향 업무마다 JSON으로:
- task_id
- factors: proximity(핵심업무 타격 0-3), maturity(논문0<데모1<베타2<GA+유료고객3),
  adoption(고객사 실명·고용변화 확인 0-3, '채용감소' 단독 금지), irreversibility(재숙련난이도 0-3), scale(니치0~대중2)
- direction: automation|wage-pressure|tool-adoption|regulation|demand-growth
- reason_ko: 한 문장, 점수 근거 (뉴스의 어떤 사실 때문인지)
근거 없으면 빈 배열 반환. 절대 직업/회사/개인을 '대체된다'고 단정하지 말 것 (§1.6 법적 가드레일).
"""


def build_dedup_key(technology: str, vendor: str, task_id: str, claim_type: str) -> str:
    """같은 기술진척(논문→데모→베타→GA)이 중복 가산되지 않게 (§1.2)."""
    return f"{technology}+{vendor}+{task_id}+{claim_type}".lower()


# R3 TODO:
#  - RSS/API 소스 어댑터 2~3개 (OpenAI/Google 블로그, 테크 언론, GitHub Trending)
#  - LLM 점수화 호출 (Gemini 2.5 Pro) + JSON 파싱/검증
#  - 일/주 단위 배치 + 점수로그(time series) 영속화
#  - 카카오 채널봇 푸시 연동 (카피는 Gemini 검수)
