"""
커리어 시그널 — 뉴스 수집 → 이벤트 변환 파이프라인 (골격)

흐름: (1) 소스 수집 → (2) 직무 관련성 필터 → (3) LLM으로 5요인 점수화 →
      (4) dedup_key 생성 → (5) Event로 저장 → scoring.ScoringEngine에 투입.

※ R2에서는 인터페이스/골격만. 실제 LLM 점수화 프롬프트와 소스 어댑터는 R3에서 구현.
"""
from __future__ import annotations

import hashlib
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

# 소스 티어링 (§1.3) — 도메인 → tier 매핑 (확장 예정)
SOURCE_TIER_MAP = {
    # Tier1: 중립·공식 통계/공시 (정부·통계·검증된 고용지표). ★벤더 자기홍보는 제외.
    "kostat.go.kr": 1, "work.go.kr": 1, "bls.gov": 1, "oecd.org": 1,
    # Tier2: 주요 독립 언론
    "techcrunch.com": 2, "theverge.com": 2, "arstechnica.com": 2,
    "yna.co.kr": 2, "zdnet.co.kr": 2,
    # Tier3: 벤더 자기홍보 블로그 + 커뮤니티 (단독 max +2).
    #   벤더는 자사툴 '능력(maturity)'엔 권위 있으나 '도입/규모(adoption/scale)' 주장은 PR →
    #   펌핑 방지 위해 보수 처리 (Codex 리뷰 #2 반영).
    "openai.com": 3, "blog.google": 3, "anthropic.com": 3, "ai.meta.com": 3,
    "deepmind.google": 3, "medium.com": 3, "reddit.com": 3, "news.ycombinator.com": 3,
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


def _text(elem, *tags) -> str:
    for t in tags:
        node = elem.find(t)
        if node is not None and node.text:
            return node.text.strip()
    return ""


class RSSSource(NewsSource):
    """RSS/Atom 피드 어댑터 (stdlib만). RSS<item>·Atom<entry> 모두 처리."""

    def __init__(self, name: str, url: str, limit: int = 15):
        self.name = name
        self.url = url
        self.limit = limit

    def fetch(self) -> list[RawArticle]:
        req = urllib.request.Request(self.url, headers={"User-Agent": "career-signal/0.1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            root = ET.fromstring(r.read())
        # 네임스페이스 무시: 태그 localname으로 매칭
        items = [e for e in root.iter() if e.tag.split("}")[-1] in ("item", "entry")]
        out: list[RawArticle] = []
        for it in items[: self.limit]:
            title = _text(it, "title", "{http://www.w3.org/2005/Atom}title")
            link = _text(it, "link", "guid")
            if not link:  # Atom: link는 href 속성
                ln = it.find("{http://www.w3.org/2005/Atom}link")
                link = ln.get("href") if ln is not None else ""
            pub = _text(it, "pubDate", "{http://www.w3.org/2005/Atom}updated",
                        "{http://purl.org/dc/elements/1.1/}date")
            body = _text(it, "description", "summary",
                         "{http://www.w3.org/2005/Atom}summary")
            if title:
                out.append(RawArticle(title=title, url=link, published_at=pub, body=body))
        return out


# 기본 소스 레지스트리 (티어는 crawler.tier_of(url)로 자동 판정)
DEFAULT_SOURCES = [
    RSSSource("OpenAI Blog", "https://openai.com/blog/rss.xml"),
    RSSSource("Google AI Blog", "https://blog.google/technology/ai/rss/"),
    RSSSource("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
]


# R3b TODO (다음 이터레이션):
#  - pipeline 배선: fetch → 직무 관련성 필터 → gemini_scorer.score_article → Event → store
#  - R2.5: CI propagation / Tier3 누적캡 / mean-reversion 상태모델 / task-first 응답계약 / override 분리
#  - 카카오 채널봇 푸시 연동 (카피는 Gemini 검수, R4)
