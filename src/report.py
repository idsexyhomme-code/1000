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
<meta property="og:description" content="업무별 AI 압력을 근거와 함께 — 커리어 시그널">
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
    grounded = bool((action_plan or {}).get("guardrail_ok", True) and (action_plan or {}).get("actions"))
    cta_html = (f'''<div class="cta-card"><div class="cta-icon">🔒</div>
    <h3 class="cta-title">상위 5%는 이미 대응 중입니다</h3>
    <p class="cta-text">방금 확인한 '{_e(head_task)}' 압력에<br>가장 먼저 대응한 사람들의 대응법 3가지</p>
    <a href="#" class="cta-btn">대응 전략 보기</a></div>''' if grounded else '')
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
<meta property="og:title" content="{_e(og_title)}"><meta property="og:description" content="{_e(og_desc)}">
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
