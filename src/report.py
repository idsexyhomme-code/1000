"""
커리어 시그널 — 미니웹 결과리포트 렌더러 (R4b → 디자인 고도화 by Gemini 3.1 Pro)

scoring.ScoringEngine.score() 의 직무 결과 dict → 모바일 우선 정적 HTML.
표현층은 Gemini 3.1 Pro가 레퍼런스(Spotify Wrapped/16Personalities/Toss/Apple Health 링/
Apple Weather 밴드/Linear)를 종합해 재설계. 콘텐츠 구조·데이터·가드레일 문구는 불변.

원칙: 모바일퍼스트(≤460px) · 공유캡처 최적화 · 불안상품화 금지(공포색 남발 금지) ·
      투명성 시각화(±·티어배지·'참고지표' 톤) · 숫자 단독강조 금지 · 한글 시스템폰트 · WCAG AA.
카피(전략가타입)는 Gemini(키 env) → 실패 시 결정적 폴백. 의존성 0, 인라인 CSS.
실행: GEMINI_API_KEY=... python3 src/report.py  → web/sample-report.html 생성
"""
from __future__ import annotations

import html
import json
import os
from urllib.parse import urlsplit

# 기상밴드: (이모지, solid색, 그라디언트 시작색). 태풍은 공포 떡칠 대신 절제된 로즈.
WEATHER_STYLE = {
    "맑음": ("☀️", "#3b82f6", "#1d4ed8"),
    "구름조금": ("⛅", "#8b5cf6", "#5b21b6"),
    "흐림": ("🌥️", "#f59e0b", "#b45309"),
    "태풍경보": ("🌀", "#fb7185", "#9f1239"),  # 공유캡처 빨강 떡칠 방지: 절제된 로즈로 완화
}


# ── 전략가 타입 (Gemini + 폴백) ───────────────────────────────────────
_TYPE_PROMPT = """\
'{job}'의 AI 압력 프로필로 'MBTI식 전략가 타입'을 지어라.
규칙: 위협과 기회를 함께 제시해 공유하기 부끄럽지 않게. '위험 85%' 같은 낙인/단정 금지.
고압력(자동화 압력 높음) 업무: {high}
저압력(방어 가능, 사람 강점) 업무: {low}
아래 JSON으로만 출력:
{{"type_name":"~형 (예: AI 파도 서퍼)","emoji":"1개","tagline":"한 줄 캐치프레이즈",
  "threat":"한 문장 위협","opportunity":"한 문장 기회(방어/전환 전략)"}}
"""


def strategist_type(job: dict, use_gemini: bool = True) -> dict:
    tasks = job.get("tasks", [])
    high = ", ".join(t["name_ko"] for t in tasks[:2]) or "-"
    low = ", ".join(t["name_ko"] for t in tasks[-2:]) or "-"
    if use_gemini and os.environ.get("GEMINI_API_KEY"):
        try:
            return _gemini_type(job["job_name_ko"], high, low)
        except Exception as e:
            print(f"[report] Gemini 타입 실패→폴백: {type(e).__name__} {e}")
    return {
        "type_name": "균형 전략가형", "emoji": "🧭",
        "tagline": f"{high} 자동화 파도를 읽고 {low}로 중심을 잡는 타입",
        "threat": f"{high} 업무에 AI 자동화 압력이 관측됩니다.",
        "opportunity": f"{low} 등 사람 강점 영역으로 무게를 옮기면 방어력이 높아집니다.",
    }


def _gemini_type(job: str, high: str, low: str) -> dict:
    # 카피/UX = premium 티어(3.1 Pro 최대한 → 죽으면 2.5-pro/flash 자동강등 + 429 backoff)
    import gemini_client
    d, _model = gemini_client.generate_json(
        _TYPE_PROMPT.format(job=job, high=high, low=low), tier="premium", temperature=0.9)
    return {k: str(d.get(k, "")).strip() for k in
            ("type_name", "emoji", "tagline", "threat", "opportunity")}


# ── 보안/이스케이프 헬퍼 ──────────────────────────────────────────────
def _e(s) -> str:
    return html.escape(str(s))


def _safe_url(u: str) -> str:
    """http/https만 허용 (javascript:/data: 등 scheme XSS 차단)."""
    try:
        if urlsplit(str(u)).scheme.lower() in ("http", "https"):
            return str(u)
    except Exception:
        pass
    return "#"


# ── 표현층 (Gemini 3.1 Pro 디자인) ────────────────────────────────────
_FAVICON = ("<link rel=\"icon\" href=\"data:image/svg+xml,"
            "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E"
            "%3Ctext y='.9em' font-size='88'%3E%F0%9F%93%A1%3C/text%3E%3C/svg%3E\">")


def _og_image_meta() -> str:
    """og:image는 절대 URL 필요 → REPORT_BASE_URL 설정 시에만 출력(정적파일은 reverse proxy가 /static/ 서빙)."""
    base = os.environ.get("REPORT_BASE_URL", "")
    return f'<meta property="og:image" content="{_e(base)}/static/og.png">' if base else ""

_CSS = """
:root{--bg-base:#09090b;--bg-surface:#18181b;--bg-elevate:#27272a;--border-color:#3f3f46;
--text-primary:#fafafa;--text-secondary:#a1a1aa;--text-tertiary:#8b8b94;
--color-clear:#3b82f6;--color-pcloudy:#8b5cf6;--color-cloudy:#f59e0b;--color-typhoon:#e11d48;}
*{box-sizing:border-box;margin:0;padding:0;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;}
body{background:#000;color:var(--text-primary);font-family:"Pretendard Variable",Pretendard,-apple-system,BlinkMacSystemFont,system-ui,Roboto,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",sans-serif;display:flex;justify-content:center;line-height:1.5;}
.app-container{width:100%;max-width:460px;background:var(--bg-base);min-height:100vh;padding:24px 20px 48px;}
.hero-card{background:linear-gradient(145deg,#18181b,#131316);border:1px solid var(--bg-elevate);border-radius:24px;padding:32px 20px 24px;text-align:center;margin-bottom:24px;box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 8px 24px rgba(0,0,0,.4);}
.hero-emoji{font-size:48px;margin-bottom:16px;line-height:1;}
.hero-title{font-size:24px;font-weight:700;margin-bottom:8px;letter-spacing:-.5px;}
.hero-subtitle{font-size:15px;color:var(--text-secondary);margin-bottom:32px;letter-spacing:-.3px;word-break:keep-all;}
.gauge-wrapper{position:relative;width:100%;max-width:280px;margin:0 auto;}
.gauge-svg{width:100%;height:auto;overflow:visible;}
.insight-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:32px;}
.insight-card{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:16px;padding:16px;}
.insight-header{display:flex;align-items:center;font-size:13px;font-weight:600;margin-bottom:8px;}
.insight-header.threat{color:#fca5a5;}
.insight-header.opp{color:#6ee7b7;}
.insight-icon{margin-right:6px;font-size:14px;}
.insight-desc{font-size:14px;color:var(--text-primary);line-height:1.4;word-break:keep-all;letter-spacing:-.3px;}
.section-title{font-size:18px;font-weight:700;margin-bottom:16px;letter-spacing:-.4px;}
.task-section,.news-section{margin-bottom:36px;}
.task-item{display:flex;align-items:center;margin-bottom:14px;}
.task-label{width:64px;font-size:14px;color:var(--text-secondary);letter-spacing:-.3px;}
.task-track{flex:1;height:8px;background:var(--bg-elevate);border-radius:4px;margin:0 12px;position:relative;overflow:hidden;}
.task-bar{position:absolute;top:0;left:0;bottom:0;border-radius:4px;}
.task-value{width:24px;text-align:right;font-size:14px;font-weight:600;}
.news-card{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:14px;padding:16px;margin-bottom:12px;text-decoration:none;display:block;}
.news-meta{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;}
.news-badge{padding:4px 8px;border-radius:6px;font-size:11px;font-weight:600;letter-spacing:-.2px;}
.badge-official{background:rgba(59,130,246,.15);color:#60a5fa;}
.badge-vendor{background:rgba(139,92,246,.15);color:#a78bfa;}
.news-link-text{font-size:12px;color:var(--text-tertiary);}
.news-title{font-size:15px;font-weight:600;color:var(--text-primary);margin-bottom:6px;letter-spacing:-.3px;line-height:1.4;}
.news-reason{font-size:13px;color:var(--text-secondary);letter-spacing:-.2px;}
.cta-card{background:linear-gradient(145deg,rgba(245,158,11,.08),rgba(225,29,72,.03));border:1px solid rgba(245,158,11,.2);border-radius:20px;padding:28px 20px;text-align:center;margin-bottom:36px;}
.cta-icon{font-size:28px;margin-bottom:12px;}
.cta-title{font-size:16px;font-weight:700;margin-bottom:8px;letter-spacing:-.3px;}
.cta-text{font-size:15px;font-weight:500;color:var(--text-secondary);line-height:1.5;margin-bottom:20px;word-break:keep-all;letter-spacing:-.3px;}
.cta-highlight{color:#fcd34d;}
.cta-btn{display:inline-block;background:var(--text-primary);color:var(--bg-base);padding:14px 28px;border-radius:30px;font-size:15px;font-weight:700;text-decoration:none;letter-spacing:-.3px;}
.share-btn{width:100%;background:var(--bg-elevate);color:var(--text-primary);border:1px solid var(--border-color);padding:16px;border-radius:16px;font-size:16px;font-weight:600;margin-bottom:24px;cursor:pointer;letter-spacing:-.3px;}
.footer-text{font-size:12px;color:var(--text-tertiary);line-height:1.6;text-align:justify;word-break:keep-all;letter-spacing:-.2px;}
.ap-section{margin-bottom:32px;}
.ap-item{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:14px;padding:14px 16px;margin-bottom:10px;}
.ap-h{font-size:15px;font-weight:600;display:flex;align-items:center;gap:8px;letter-spacing:-.3px;line-height:1.4;}
.ap-tag{font-size:11px;font-weight:700;padding:2px 7px;border-radius:6px;flex-shrink:0;}
.tag-defend{background:rgba(245,158,11,.15);color:#fbbf24;}
.tag-pivot{background:rgba(59,130,246,.15);color:#60a5fa;}
.ap-step{font-size:13px;color:var(--text-secondary);margin-top:8px;line-height:1.5;word-break:keep-all;}
.ap-meta{font-size:12px;color:var(--text-tertiary);margin-top:6px;}
.ap-item.locked .ap-h{filter:blur(5px);user-select:none;pointer-events:none;}
.ap-lock{font-size:13px;color:var(--text-tertiary);margin-top:10px;text-align:center;}
"""


def _gauge_svg(index: float, ci) -> str:
    # 반원(180°) arc. 인디케이터 각도 = 값/100 * 180° (좌단 0% → 우단 100%).
    try:
        idx = max(0.0, min(100.0, float(index)))   # index 비정상이어도 리포트 안 죽게 방어
    except (TypeError, ValueError):
        idx = 0.0
    angle = idx / 100 * 180
    band = ('<path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="{c}" '
            'stroke-width="12" stroke-dasharray="62.83 502.65" stroke-dashoffset="{o}"/>')
    bands = (band.format(c="var(--color-clear)", o=0) + band.format(c="var(--color-pcloudy)", o=-62.83)
             + band.format(c="var(--color-cloudy)", o=-125.66) + band.format(c="var(--color-typhoon)", o=-188.49))
    return (f'<svg class="gauge-svg" viewBox="0 0 200 110" role="img" '
            f'aria-label="AI 영향 참고지표 {_e(index)}, 신뢰구간 플러스마이너스 {_e(ci)}">'
            '<path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#27272a" stroke-width="12" stroke-linecap="round"/>'
            f'{bands}'
            f'<g transform="rotate({angle:.1f}, 100, 100)"><circle cx="20" cy="100" r="6" fill="#fff" stroke="#18181b" stroke-width="2.5"/></g>'
            '<g transform="translate(0,-8)">'
            '<text x="100" y="55" font-size="11" font-weight="500" text-anchor="middle" fill="var(--text-secondary)">AI 영향 참고지표</text>'
            f'<text x="100" y="92" font-size="42" font-weight="800" text-anchor="middle" fill="#fff" letter-spacing="-1">{_e(index)}</text>'
            f'<text x="100" y="110" font-size="11" font-weight="500" text-anchor="middle" fill="var(--text-tertiary)">신뢰구간 ±{_e(ci)}</text>'
            '</g></svg>')


def _task_bar(t: dict) -> str:
    _emoji, solid, grad = WEATHER_STYLE.get(t.get("weather"), ("", "#71717a", "#52525b"))
    pct = max(2, min(100, t["index"]))
    return (f'<div class="task-item"><div class="task-label">{_e(t["name_ko"])}</div>'
            f'<div class="task-track"><div class="task-bar" style="width:{pct}%;'
            f'background:linear-gradient(90deg,{grad},{solid})"></div></div>'
            f'<div class="task-value">{_e(t["index"])}</div></div>')


def _badge(tier: int) -> tuple[str, str]:
    if tier == 3:
        return ("badge-vendor", "벤더PR")
    if tier == 2:
        return ("badge-official", "언론")
    return ("badge-official", "공식")


def _driver(d: dict) -> str:
    cls, label = _badge(d.get("source_tier", 3))
    url = _e(_safe_url(d.get("url", "#")))
    return (f'<a href="{url}" target="_blank" rel="noopener" class="news-card">'
            f'<div class="news-meta"><span class="news-badge {cls}">{label}</span>'
            '<span class="news-link-text">원문보기 ↗</span></div>'
            f'<h3 class="news-title">{_e(d.get("title", ""))[:80]}</h3>'
            f'<p class="news-reason">{_e(d.get("reason_ko", ""))}</p></a>')


def _action_plan_html(plan: dict) -> str:
    """이번 주 생존 액션플랜 — 첫 1개 무료 티저, 나머지 잠금(유료 전환점). 해자를 유료CTA에 결박."""
    plan = plan or {}
    actions = plan.get("actions", [])
    if not actions:
        return ""
    # 근거 미확보(guardrail_ok=False) → 유료 잠금 대신 정직한 안내 (근거 없는 조언 판매 방지)
    if not plan.get("guardrail_ok", True):
        return ('<div class="ap-section"><h2 class="section-title">🧭 이번 주 생존 액션플랜</h2>'
                '<div class="ap-item"><div class="ap-step">오늘은 당신 직무에 <b>직접 결박된 새 근거 뉴스</b>가 '
                '없어 맞춤 대응법을 준비하지 못했습니다. 근거가 잡히면 바로 알려드릴게요.</div></div></div>')
    rows = []
    for i, a in enumerate(actions):
        locked = i >= 1                       # 첫 1개만 공개, 2·3번 잠금
        tag = {"defend": "방어", "pivot": "전환"}.get(a.get("strategy_type"), "")
        tag_cls = "tag-defend" if a.get("strategy_type") == "defend" else "tag-pivot"
        head = (f'<div class="ap-h"><span class="ap-tag {tag_cls}">{tag}</span>'
                f'{_e(a.get("title_ko", ""))}</div>')
        if locked:
            body = '<div class="ap-lock">🔒 잠금 — 대응법 보기</div>'
        else:
            steps = a.get("action_steps", [])
            step0 = _e(steps[0]) if steps else ""
            meta = f'{_e(a.get("difficulty", ""))} · 주 {_e(a.get("time_hours", ""))}h · {_e(a.get("payoff_ko", ""))}'
            body = f'<div class="ap-step">{step0}</div><div class="ap-meta">{meta}</div>'
        rows.append(f'<div class="ap-item{" locked" if locked else ""}">{head}{body}</div>')
    return ('<div class="ap-section"><h2 class="section-title">🧭 이번 주 생존 액션플랜</h2>'
            + "".join(rows) + "</div>")


_LANDING_CSS = """
.lj-lead{font-size:14px;color:var(--text-secondary);text-align:center;margin:0 0 20px;word-break:keep-all;}
.lj-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.lj-card{display:block;background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:14px;
padding:16px 14px;text-align:center;text-decoration:none;color:var(--text-primary);font-weight:600;font-size:15px;letter-spacing:-.3px;}
"""


def landing_html(jobs: dict) -> str:
    """웹 진입점 — 직업 그리드(고압력순) → /report?job=. 공유받은 친구의 '내 직업 확인' 루프 완성."""
    items = sorted(jobs.values(), key=lambda j: -j.get("baseline", {}).get("index", 0))
    cards = "".join(f'<a class="lj-card" href="/report?job={_e(j["job_id"])}">{_e(j["job_name_ko"])}</a>'
                    for j in items)
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta property="og:type" content="website"><meta property="og:site_name" content="커리어 시그널">
<meta property="og:title" content="내 직업, AI에 얼마나 영향받을까?">
<meta property="og:description" content="업무별 AI 압력을 근거와 함께 — 커리어 시그널">{_og_image_meta()}
{_FAVICON}<title>커리어 시그널 — 내 직업, AI에 얼마나?</title>
<style>{_CSS}{_LANDING_CSS}</style></head><body><div class="app-container">
  <div class="hero-card"><div class="hero-emoji">📡</div>
    <h1 class="hero-title">커리어 시그널</h1>
    <p class="hero-subtitle">내 직업이 AI에 얼마나 영향받을까?<br>업무별 압력을 근거와 함께, 매일.</p>
  </div>
  <p class="lj-lead">직업을 선택하면 업무별 AI 압력 리포트를 보여드려요.</p>
  <div class="lj-grid">{cards}</div>
  <p class="footer-text">※ 본 지수는 공개된 AI 뉴스를 정해진 원칙으로 계량화한 <b>참고 지표</b>입니다. 특정 개인·기업의 대체를 단정하지 않으며, 모든 변동의 근거를 공개합니다.</p>
</div></body></html>"""


_DETAIL_CSS = """
.dd-sec{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:16px;padding:18px 16px;margin-bottom:14px;}
.dd-h{font-size:16px;font-weight:700;margin-bottom:4px;letter-spacing:-.3px;}
.dd-src{font-size:11px;color:var(--text-tertiary);margin-bottom:12px;}
.dd-row{display:flex;align-items:center;margin-bottom:10px;font-size:14px;}
.dd-row .n{width:104px;color:var(--text-secondary);flex-shrink:0;letter-spacing:-.3px;}
.dd-track{flex:1;height:7px;background:var(--bg-elevate);border-radius:4px;margin:0 10px;overflow:hidden;}
.dd-track i{display:block;height:100%;border-radius:4px;}
.dd-v{width:30px;text-align:right;font-weight:600;}
.dd-tl .it{border-left:2px solid var(--bg-elevate);padding:0 0 12px 14px;margin-left:4px;}
.dd-stage{font-size:11px;font-weight:700;color:#fbbf24;}.dd-date{font-size:11px;color:var(--text-tertiary);margin-left:6px;}
.dd-tl a{color:var(--text-primary);text-decoration:none;font-size:13px;font-weight:600;display:block;margin-top:3px;line-height:1.4;}
.dd-pending{background:rgba(245,158,11,.07);border:1px dashed rgba(245,158,11,.3);border-radius:12px;padding:14px;font-size:13px;color:var(--text-secondary);line-height:1.5;}
.dd-pending b{color:#fbbf24;}
.dd-chip{display:inline-block;background:var(--bg-elevate);border-radius:8px;padding:7px 12px;margin:4px 5px 0 0;font-size:13px;}
.dd-back{display:block;text-align:center;color:var(--text-secondary);font-size:14px;margin:6px 0 18px;text-decoration:none;}
.dd-note{font-size:12px;color:var(--text-tertiary);margin-top:10px;line-height:1.5;}
"""


def detail_html(job_result: dict, deep: dict | None = None) -> str:
    """상세 분석(drill-down) — 5섹션. 실데이터로 받칠 수 있는 것만 채우고 나머지는 정직한 '연동 필요'."""
    import deepdive
    deep = deep or deepdive.build(job_result)
    jid = _e(job_result.get("job_id", ""))
    name = _e(job_result.get("job_name_ko", ""))

    # 1) 과업별 자동화율
    ab = deep["automation"]
    rows = ""
    for t in ab["tasks"]:
        _e2, solid, grad = WEATHER_STYLE.get(t["weather"], ("", "#71717a", "#52525b"))
        pct = max(2, min(100, t["automation_pct"]))
        rows += (f'<div class="dd-row"><span class="n">{_e(t["name_ko"])}</span>'
                 f'<span class="dd-track"><i style="width:{pct}%;background:linear-gradient(90deg,{grad},{solid})"></i></span>'
                 f'<span class="dd-v">{_e(t["automation_pct"])}</span></div>')
    sec_auto = (f'<div class="dd-sec"><div class="dd-h">📊 과업별 자동화율</div>'
                f'<div class="dd-src">{_e(ab["source"])}</div>{rows}'
                f'<div class="dd-note">※ 현재 손추정(미보정) — O*NET·워크넷 실데이터 연동 시 정밀 수치로 격상됩니다.</div></div>')

    # 2) 기술 상용화 타임라인
    tl = deep["timeline"]
    if tl["items"]:
        its = "".join(f'<div class="it"><span class="dd-stage">{_e(i["stage"])}</span>'
                      f'<span class="dd-date">{_e(i["date"])} · T{i["source_tier"]}</span>'
                      f'<a href="{_e(_safe_url(i["url"]))}" target="_blank" rel="noopener">{_e(i["title"])[:70]}</a></div>'
                      for i in tl["items"])
        body_tl = f'<div class="dd-tl">{its}</div>'
    else:
        body_tl = f'<div class="dd-pending">{_e(tl["note"])}</div>'
    sec_tl = (f'<div class="dd-sec"><div class="dd-h">🗓️ 기술 상용화 타임라인</div>'
              f'<div class="dd-src">{_e(tl["source"])}</div>{body_tl}</div>')

    # 3) 전이경로
    pv = deep["pivot"]
    chips = "".join(f'<span class="dd-chip">🛡️ {_e(t["name_ko"])} ({_e(t["automation_pct"])})</span>'
                    for t in pv["within_job"])
    sec_pv = (f'<div class="dd-sec"><div class="dd-h">🧭 전이경로 — 어디로 무게를 옮길까</div>'
              f'<div class="dd-src">{_e(pv["source"])}</div>'
              f'<div>{chips}</div>'
              f'<div class="dd-note">{_e(pv["cross_job_note"])}</div></div>')

    # 4) 채용 트렌드 (스텁) / 5) 임금 타격 (스텁)
    hr, wg = deep["hiring"], deep["wage"]
    sec_hr = (f'<div class="dd-sec"><div class="dd-h">📈 실시간 채용 트렌드</div>'
              f'<div class="dd-pending"><b>데이터 연동 필요</b> — {_e(hr["note"])}</div></div>')
    sec_wg = (f'<div class="dd-sec"><div class="dd-h">💰 임금 타격 예측</div>'
              f'<div class="dd-pending"><b>데이터 연동 필요</b> — {_e(wg["note"])}</div></div>')

    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
{_FAVICON}<title>{name} 상세 분석 · 커리어 시그널</title>
<style>{_CSS}{_DETAIL_CSS}</style></head><body><div class="app-container">
  <a class="dd-back" href="/report?job={jid}">← 요약으로 돌아가기</a>
  <div class="hero-card"><div class="hero-emoji">🔬</div>
    <h1 class="hero-title">{name} 상세 분석</h1>
    <p class="hero-subtitle">업무별 근거를 깊게 — 분량이 아니라 근거로.</p></div>
  {sec_auto}{sec_tl}{sec_pv}{sec_hr}{sec_wg}
  <div class="dd-sec"><div class="dd-h">🧪 방법론 & 한계 (투명 공개)</div>
    <div class="dd-note">· 압력지수는 공개 AI뉴스를 정해진 5요인 루브릭으로 계량화한 <b>참고 지표</b>입니다(예측 아님).<br>
    · 현재 baseline은 <b>손추정(calibrated: false)</b> — O*NET·채용·임금 데이터 연동으로 보정 예정.<br>
    · 모든 변동은 출처·신뢰도를 동반하며, 근거 없는 처방은 생성하지 않습니다(개인 자동판정 아님, 개인정보보호법 §37-2).</div></div>
  <p class="footer-text">※ 본 지수는 공개된 AI 뉴스를 정해진 원칙으로 계량화한 <b>참고 지표</b>입니다. 특정 개인·기업의 대체를 단정하지 않으며, 모든 변동의 근거를 공개합니다.</p>
</div></body></html>"""


def render_html(job: dict, strat: dict | None = None, action_plan: dict | None = None) -> str:
    strat = strat or strategist_type(job, use_gemini=False)
    tasks = job.get("tasks", [])
    tasks_html = "".join(_task_bar(t) for t in tasks)
    drivers = job.get("top_drivers", [])
    drv_html = "".join(_driver(d) for d in drivers) or '<p class="news-reason">오늘은 새 근거가 없습니다.</p>'
    head_task = (job.get("headline_task") or (tasks[0] if tasks else {})).get("name_ko", "핵심 업무")
    if action_plan is None:        # 기본은 결정적 폴백(빠름·무비용). 배치가 캐시한 Gemini 플랜은 호출측이 주입.
        import actionplan
        action_plan = actionplan.make_action_plan(job, use_gemini=False)
    ap_html = _action_plan_html(action_plan)
    # 유료 CTA는 근거 결박된(guardrail_ok) 플랜이 있을 때만 — 근거 없는 조언 판매 금지
    # 정직성: 검증 못 한 사회증명("상위 5%" 등) 금지. 가치(결과물 남는 패키지)로만 소구.
    grounded = bool((action_plan or {}).get("guardrail_ok", True) and (action_plan or {}).get("actions"))
    cta_html = (f'''<div class="cta-card"><div class="cta-icon">🛡️</div>
    <h3 class="cta-title">'{_e(head_task)}' 압력, 이력서부터 점검하세요</h3>
    <p class="cta-text">데이터로 본 '덜 대체되는 역량' 중심으로<br>이력서를 재설계 — 손에 남는 결과물</p>
    <a href="/offer?job={_e(job.get('job_id',''))}" class="cta-btn">{OFFER_NAME} 보기 →</a></div>''' if grounded else '')
    # 공유 페이로드(바이럴 #1 레버). json.dumps→유효 JS 객체. </script 브레이크아웃 방어로 <\/ 치환.
    _share = json.dumps({
        "title": "커리어 시그널",
        "text": f"[{strat.get('type_name','전략가형')} {strat.get('emoji','🧭')}] "
                f"{strat.get('tagline','')}\n{job.get('job_name_ko','')} AI 압력지수 "
                f"{job.get('index','-')}({job.get('weather','')}) — 내 직무는?",
    }, ensure_ascii=False).replace("</", "<\\/")
    # OG 메타(공유 링크 프리뷰 = 바이럴 레버). 카톡/SNS에서 매력적으로 보이게.
    og_title = (f"{strat.get('type_name','전략가형')} · {job.get('job_name_ko','')} "
                f"AI 압력 {job.get('index','-')}")
    og_desc = (strat.get('tagline', '') or strat.get('threat', '')
               or "내 직무가 AI에 얼마나 영향받는지 업무별로 확인하세요")
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta property="og:type" content="website"><meta property="og:site_name" content="커리어 시그널">
<meta property="og:title" content="{_e(og_title)}"><meta property="og:description" content="{_e(og_desc)}">{_og_image_meta()}
{_FAVICON}<title>커리어 시그널 · {_e(job.get('job_name_ko',''))}</title>
<style>{_CSS}</style></head><body><div class="app-container">
  <div class="hero-card">
    <div class="hero-emoji" role="img" aria-label="전략가 타입">{_e(strat.get('emoji','🧭'))}</div>
    <h1 class="hero-title">{_e(strat.get('type_name','전략가형'))}</h1>
    <p class="hero-subtitle">"{_e(strat.get('tagline',''))}"</p>
    <div class="gauge-wrapper">{_gauge_svg(job.get('index','-'), job.get('ci',12))}</div>
  </div>
  <div class="insight-grid">
    <div class="insight-card"><div class="insight-header threat"><span class="insight-icon">⚡️</span> 위협</div>
      <div class="insight-desc">{_e(strat.get('threat',''))}</div></div>
    <div class="insight-card"><div class="insight-header opp"><span class="insight-icon">🎯</span> 기회</div>
      <div class="insight-desc">{_e(strat.get('opportunity',''))}</div></div>
  </div>
  <div class="task-section"><h2 class="section-title">📊 내 업무별 AI 압력 (높을수록 자동화 신호 ↑)</h2>{tasks_html}</div>
  <div class="news-section"><h2 class="section-title">🔎 오늘 점수를 움직인 근거</h2>{drv_html}</div>
  {ap_html}
  {cta_html}
  <a href="/detail?job={_e(job.get('job_id',''))}" style="display:block;text-align:center;background:var(--bg-elevate);color:var(--text-primary);padding:13px;border-radius:14px;margin:0 0 12px;text-decoration:none;font-size:14px;font-weight:600;letter-spacing:-.3px">🔬 더 깊은 상세 분석 보기 →</a>
  <button class="share-btn" onclick="csShare()">📲 내 전략가 타입 공유하기</button>
  <script>
  function csShare(){{var d={_share};d.url=location.href;
    if(navigator.share){{navigator.share(d).catch(function(){{}});}}
    else if(navigator.clipboard){{navigator.clipboard.writeText(d.text+" "+d.url);alert("공유 링크를 복사했어요!");}}
    else {{window.prompt("공유 링크",d.url);}}}}
  </script>
  <a href="/" style="display:block;text-align:center;color:var(--text-secondary);font-size:13px;margin:2px 0 18px;text-decoration:none">🔎 내 직업도 확인하기 →</a>
  <p class="footer-text">※ 본 지수는 공개된 AI 뉴스를 정해진 원칙으로 계량화한 <b>참고 지표</b>입니다. 특정 개인·기업의 대체를 단정하지 않으며, 모든 변동의 근거를 공개합니다.</p>
</div></body></html>"""


_OFFER_CSS = """
.of-price{display:flex;align-items:baseline;gap:9px;justify-content:center;margin:8px 0 2px;}
.of-now{font-size:30px;font-weight:800;letter-spacing:-1px;}
.of-unit{font-size:13px;color:var(--text-secondary);}
.of-list{list-style:none;padding:0;margin:16px 0 6px;}
.of-list li{display:flex;gap:11px;padding:12px 0;border-bottom:1px solid var(--bg-elevate);font-size:14px;line-height:1.45;word-break:keep-all;}
.of-list li:last-child{border-bottom:0;}
.of-ic{flex-shrink:0;}
.of-soon{color:var(--text-tertiary);}
.of-input{width:100%;box-sizing:border-box;background:var(--bg-elevate);border:1px solid transparent;border-radius:12px;
padding:14px;font-size:15px;color:var(--text-primary);margin-bottom:10px;-webkit-appearance:none;}
.of-input:focus{outline:none;border-color:#6366f1;}
.of-submit{width:100%;background:#fafafa;color:#09090b;border:0;border-radius:14px;padding:15px;font-size:15px;font-weight:700;cursor:pointer;text-decoration:none;display:block;text-align:center;box-sizing:border-box;}
.of-ok{display:none;text-align:center;padding:20px;background:rgba(99,102,241,.1);border-radius:14px;font-size:14px;line-height:1.55;}
.of-note{font-size:12px;color:var(--text-tertiary);margin-top:14px;line-height:1.6;}
.of-back{display:block;text-align:center;color:var(--text-secondary);font-size:14px;margin:4px 0 16px;text-decoration:none;}
.of-kicker{font-size:12px;font-weight:700;color:var(--text-tertiary);letter-spacing:.4px;margin:18px 2px 2px;text-transform:uppercase;}
.of-steps{list-style:none;counter-reset:s;padding:0;margin:8px 0 4px;}
.of-steps li{counter-increment:s;display:flex;gap:11px;padding:8px 0;font-size:13.5px;line-height:1.5;color:var(--text-secondary);word-break:keep-all;}
.of-steps li::before{content:counter(s);flex-shrink:0;width:22px;height:22px;border-radius:50%;background:var(--bg-elevate);color:var(--text-primary);font-size:12px;font-weight:700;display:flex;align-items:center;justify-content:center;}
.of-human{font-size:12.5px;color:var(--text-secondary);background:var(--bg-elevate);border-radius:12px;padding:12px 13px;margin:14px 0 4px;line-height:1.55;word-break:keep-all;}
.of-cap{font-size:13px;color:var(--text-primary);font-weight:600;text-align:center;margin:16px 0 12px;line-height:1.5;}
"""

# 가격은 검증 대상 가설(테스트가) — 가짜 할인 금지. 정상가는 운영된 적 없으므로 취소선 표기 안 함.
OFFER_NAME = "AI 시대 커리어 재설계 패키지"   # '대체 불가/AI-Proof'식 절대보장 표현 회피(표시광고법, Codex fix)
OFFER_PRICE = "99,000"           # 1회성 패키지(월 구독 아님) · 테스트 가격(시세 10~20만원 대비 진입가)
OFFER_DELIVERY_DAYS = 5          # 영업일 기준 납기
OFFER_WEEKLY_CAP = 5             # 사람이 직접 검토하므로 주당 실제 처리 가능 인원 = 정직한 수용한계(가짜 카운터 아님)
PRESALE_PRICE = OFFER_PRICE      # 하위호환(interest price_shown 라벨)


def offer_html(job: dict, payment_url: str | None = None) -> str:
    """AI-Proof 커리어 재설계 패키지 — 런칭=지불주체 스모크테스트. '결과물이 손에 남는' 1회성 패키지.
    위협지수(무료 미끼) → 결과물(이력서 재설계)이 유료 정점. 주간 텍스트 구독(commodity) 폐기.
    PAYMENT_URL(env) 연결 시 실결제 버튼+환불 고지, 미연결 시 사전신청(리드) 수집."""
    jid = _e(job.get("job_id", ""))
    name = _e(job.get("job_name_ko", ""))
    head_task = _e((job.get("headline_task") or {}).get("name_ko") or "핵심 업무")
    safe_payment_url = _safe_url(payment_url) if payment_url else "#"
    real = safe_payment_url != "#"     # 잘못된 URL(javascript: 등)이면 실결제 모드로 오인 금지(Codex fix)
    cap_line = (f'<div class="of-cap">🪑 사람이 직접 검토·작성하므로 <b>초기에는 주 최대 {OFFER_WEEKLY_CAP}명까지 수동 검토</b>합니다.'
                f'<br><span class="of-unit">실제 처리 한계 — 가짜 카운트다운 아님</span></div>')
    if real:                           # 실결제 모드 — 환불·제공시점 고지(운영 시 약관 페이지 링크 권장)
        price_label = f'<span class="of-unit">/ 1회 · 영업일 {OFFER_DELIVERY_DAYS}일 내 전달</span>'
        action = (f'<a href="{_e(safe_payment_url)}" class="of-submit">'
                  f'지금 신청하기 — {OFFER_PRICE}원 결제 →</a>')
        note = (f'※ <b>{OFFER_PRICE}원이 1회 결제</b>됩니다(구독 아님). 결제는 외부 결제 페이지에서 진행되며, '
                f'현재 결제 완료는 자동 확인되지 않아 영업일 내 수동 확인 후 작업을 시작합니다. '
                f'<b>법정 청약철회권 및 계약 불일치 시 환불권은 보장</b>되며(결제 후 작업 미개시분은 전액 환불), '
                f'이미 제공 개시된 맞춤 용역 부분은 관련 법령(전자상거래법) 범위 내에서만 공제될 수 있습니다(영업일 {OFFER_DELIVERY_DAYS}일 내 전달). '
                f'이력서 재설계는 <b>당신 직무에 결박된 근거가 있을 때만</b> 수행하며, 근거 없는 조언은 팔지 않습니다. '
                f'AI 압력지수는 참고용 통계 지표이며 개인에 대한 자동 판정이 아닙니다.')
    else:                              # 사전신청(비결제) 모드 — 리드 수집(결제 아님)
        price_label = f'<span class="of-unit">/ 1회 (테스트 가격 · 정식가는 오픈 전 확정)</span>'
        action = (f'''<form id="ofForm" onsubmit="return ofSubmit(event)">
      <input class="of-input" id="ofHp" name="hp_url" type="text" tabindex="-1" autocomplete="off"
        style="position:absolute;left:-9999px" aria-hidden="true">
      <input class="of-input" id="ofContact" type="text" maxlength="120" required
        placeholder="이메일 또는 카카오 오픈채팅 ID" autocomplete="email">
      <label style="display:flex;gap:8px;align-items:flex-start;font-size:12px;color:var(--text-secondary);margin:0 2px 12px;text-align:left;line-height:1.5">
        <input type="checkbox" id="ofConsent" style="margin-top:2px;flex-shrink:0">
        <span>(필수) 오픈 안내를 위해 연락처 수집·이용에 동의합니다. 수집 항목: 연락처(이메일 또는 카카오 오픈채팅 ID) / 목적: 오픈 알림 / 보관: 정식 오픈 후 6개월 또는 삭제 요청 시까지 / 삭제·문의는 회신으로 요청 가능. 동의를 거부하실 수 있으며, 거부 시 사전신청 안내가 제공되지 않을 뿐 다른 불이익은 없습니다.</span></label>
      <button class="of-submit" type="submit">사전신청 — 오픈 시 우선 안내</button>
    </form>
    <div class="of-ok" id="ofOk">신청 완료! 정식 오픈하면 가장 먼저 알려드릴게요.<br>관심 가져주셔서 고맙습니다. 🙏</div>''')
        note = ('※ <b>사전신청은 결제가 아닙니다</b> — 정식 오픈 시 우선 안내드립니다. '
                '이력서 재설계는 <b>당신 직무에 결박된 근거가 있을 때만</b> 수행하며, 근거 없는 조언은 팔지 않습니다. '
                'AI 압력지수는 참고용 통계 지표이며 개인에 대한 자동 판정이 아닙니다.')
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
{_FAVICON}<title>{OFFER_NAME} · {name}</title>
<style>{_CSS}{_OFFER_CSS}</style></head><body><div class="app-container">
  <a class="of-back" href="/report?job={jid}">← 내 리포트로</a>
  <div class="hero-card"><div class="hero-emoji">🛡️</div>
    <h1 class="hero-title">{OFFER_NAME}</h1>
    <p class="hero-subtitle">'{head_task}' 압력 데이터를 근거로,<br><b>AI가 상대적으로 덜 대체하는 사람 고유 역량</b> 중심으로 이력서를 재설계합니다.</p>
  </div>
  <div class="cta-card" style="text-align:center">
    <div class="of-price"><span class="of-now">{OFFER_PRICE}원</span>{price_label}</div>
    <div class="of-kicker">손에 남는 결과물</div>
    <ul class="of-list">
      <li><span class="of-ic">📊</span><div><b>데이터 기반 직무 진단</b> — 실제 AI 뉴스·근거에 기반해 내 직무의 '위험 업무/안전 업무'를 분류한 리포트.</div></li>
      <li><span class="of-ic">✨</span><div><b>사람 고유 역량 발굴</b> — AI가 잘하는 단순반복은 줄이고, 문제해결·기획·도메인 강점을 강조하도록 이력서 재배치 가이드(절대적 방어 보장이 아니라 상대적 강조점 재배치).</div></li>
      <li><span class="of-ic">📝</span><div><b>이력서 핵심 문장 초안</b> — 커리어 디렉터가 직접 다듬은 요약(Summary)·성과 불릿 초안 + 적용 가이드.</div></li>
      <li><span class="of-ic">🧭</span><div><b>1~3년 커리어 디펜스 플랜</b> — 추가로 쌓으면 좋은 권장 스킬셋.</div></li>
    </ul>
    <div class="of-kicker">진행 과정</div>
    <ol class="of-steps">
      <li>{'결제' if real else '신청'} 후 기존 이력서·포트폴리오 제출</li>
      <li>WorkRadar 데이터로 직무 태스크 분석 + '안전 역량' 매핑</li>
      <li>1:1 서면 인터뷰 — 이력서에 누락된 '쉽게 대체되지 않는 경험' 발굴</li>
      <li>최종 패키지 전달 + 적용 가이드 (영업일 {OFFER_DELIVERY_DAYS}일 내)</li>
    </ol>
    <div class="of-human">🤝 <b>AI가 어디까지 하나:</b> 직무 압력 데이터 수집·1차 분류는 AI가, <b>당신의 고유 경험 발굴과 이력서 최종 문장은 커리어 디렉터가 직접 검토·작성</b>합니다. 'AI가 다 써준다'가 아닙니다.</div>
    {cap_line}
    {action}
  </div>
  <p class="of-note">{note}</p>
</div>
<script>
function ofSubmit(e){{e.preventDefault();
  var c=document.getElementById('ofContact').value.trim();
  var hp=document.getElementById('ofHp').value;
  if(!c){{return false;}}
  if(!document.getElementById('ofConsent').checked){{alert('개인정보 수집·이용 동의가 필요합니다.');return false;}}
  fetch('/offer/interest',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{contact:c,job:'{jid}',price_shown:'{PRESALE_PRICE}',consent:true,hp_url:hp}})}})
   .then(function(r){{if(!r.ok){{throw new Error('bad');}}
     document.getElementById('ofForm').style.display='none';
     document.getElementById('ofOk').style.display='block';}})
   .catch(function(){{alert('잠시 후 다시 시도해 주세요.');}});
  return false;}}
</script>
</body></html>"""


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from datetime import datetime, timezone
    from scoring import Affected, Event, ScoringEngine
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    eng = ScoringEngine(os.path.join(here, "data", "jobs"))
    ev = [Event("d1", "OpenAI, 영상 자동편집 모델 정식 출시 + 유료 고객사 확보",
                "https://example.com/n1", 1, "2026-06-05T00:00:00Z",
                [Affected("video-editor", "cut-editing",
                          {"proximity": 3, "maturity": 3, "adoption": 2, "irreversibility": 2, "scale": 2},
                          "automation", "컷편집 자동화 정식기능 + 유료고객으로 도입신호 상승")],
                dedup_key="sora+openai")]
    res = eng.score(ev, now=datetime(2026, 6, 6, tzinfo=timezone.utc))["video-editor"]
    strat = strategist_type(res, use_gemini=True)
    out_dir = os.path.join(here, "web")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "sample-report.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_html(res, strat))
    print("전략가 타입:", json.dumps(strat, ensure_ascii=False))
    print("리포트 생성:", path)
