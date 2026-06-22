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


def _legal_links() -> str:
    return '<p class="legal-links"><a href="/privacy">개인정보처리방침</a> · <a href="/terms">이용약관</a></p>'


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
.task-section,.news-section,.pain-section{margin-bottom:36px;}
.task-item{display:flex;align-items:center;margin-bottom:14px;}
.task-label{width:64px;font-size:14px;color:var(--text-secondary);letter-spacing:-.3px;}
.task-track{flex:1;height:8px;background:var(--bg-elevate);border-radius:4px;margin:0 12px;position:relative;overflow:hidden;}
.task-bar{position:absolute;top:0;left:0;bottom:0;border-radius:4px;}
.task-value{width:24px;text-align:right;font-size:14px;font-weight:600;}
.pain-note{font-size:12.5px;color:var(--text-secondary);margin:-4px 0 14px;line-height:1.55;word-break:keep-all;}
.pain-card{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:14px;padding:16px;margin-bottom:12px;}
.pain-top{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-bottom:10px;}
.pain-label{font-size:11px;font-weight:700;color:#34d399;background:rgba(52,211,153,.12);border-radius:6px;padding:3px 7px;white-space:nowrap;}
.pain-task{font-size:11.5px;color:var(--text-tertiary);text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.pain-title{font-size:15px;font-weight:700;color:var(--text-primary);letter-spacing:-.3px;line-height:1.45;margin-bottom:7px;word-break:keep-all;}
.pain-moment{font-size:13px;color:var(--text-secondary);line-height:1.55;letter-spacing:-.2px;word-break:keep-all;margin-bottom:10px;}
.pain-artifact{font-size:13px;color:var(--text-primary);line-height:1.55;background:var(--bg-elevate);border-radius:10px;padding:10px 12px;word-break:keep-all;}
.pain-artifact b{color:#fcd34d;}
.pain-link{display:block;margin-top:10px;color:#d4d4d8;background:rgba(255,255,255,.04);border:1px solid var(--bg-elevate);border-radius:10px;padding:10px 12px;text-align:center;text-decoration:none;font-size:13px;font-weight:700;letter-spacing:-.2px;}
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
.legal-links{text-align:center;font-size:12px;color:var(--text-tertiary);margin:16px 0 0;line-height:1.6;}
.legal-links a{color:var(--text-secondary);text-decoration:none;margin:0 5px;}
.ap-section{margin-bottom:32px;}
.ap-item{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:14px;padding:14px 16px;margin-bottom:10px;}
.ap-h{font-size:15px;font-weight:600;display:flex;align-items:center;gap:8px;letter-spacing:-.3px;line-height:1.4;}
.ap-tag{font-size:11px;font-weight:700;padding:2px 7px;border-radius:6px;flex-shrink:0;}
.tag-defend{background:rgba(245,158,11,.15);color:#fbbf24;}
.tag-pivot{background:rgba(59,130,246,.15);color:#60a5fa;}
.ap-step{font-size:13px;color:var(--text-secondary);margin-top:8px;line-height:1.5;word-break:keep-all;}
.ap-meta{font-size:12px;color:var(--text-tertiary);margin-top:6px;}
.ap-sub{font-size:12.5px;color:var(--text-secondary);margin:-2px 2px 14px;line-height:1.55;word-break:keep-all;}
.ap-free{font-size:10.5px;font-weight:700;color:#34d399;background:rgba(52,211,153,.12);padding:2px 7px;border-radius:6px;margin-left:auto;flex-shrink:0;}
.ap-lock{font-size:12.5px;color:var(--text-secondary);margin-top:10px;line-height:1.55;word-break:keep-all;display:flex;gap:7px;align-items:flex-start;background:var(--bg-elevate);border-radius:10px;padding:10px 12px;}
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


def _pain_map_html(job: dict) -> str:
    """직업별 '가려운 업무' — 사용자 인터뷰 전 제품 가설로만 노출.
    AI 압력지수처럼 보정된 수치가 아니므로 label/note를 같이 보여 과대표기를 막는다."""
    import painmap
    pm = painmap.build(job, limit=3)
    pains = pm.get("pains") or []
    if not pains:
        return ""
    cards = []
    jid = _e(job.get("job_id", ""))
    for p in pains:
        tasks = ", ".join(p.get("task_names_ko") or []) or "관련 업무"
        pid = _e(p.get("pain_id", ""))
        cards.append(
            '<div class="pain-card">'
            f'<div class="pain-top"><span class="pain-label">{_e(pm.get("label_ko", "제품 가설"))}</span>'
            f'<span class="pain-task">{_e(tasks)}</span></div>'
            f'<h3 class="pain-title">{_e(p.get("itch_ko", ""))}</h3>'
            f'<p class="pain-moment">{_e(p.get("moment_ko", ""))}</p>'
            f'<div class="pain-artifact"><b>만들어줄 결과물</b><br>{_e(p.get("artifact_ko", ""))}</div>'
            f'<a class="pain-link" href="/pain?job={jid}&pain={pid}">내 상황으로 좁히기 →</a>'
            '</div>'
        )
    return (
        '<div class="pain-section"><h2 class="section-title">🩹 진짜 가려운 업무</h2>'
        f'<p class="pain-note">{_e(pm.get("note_ko", ""))}</p>'
        + "".join(cards)
        + "</div>"
    )


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
    """이번 주 액션플랜 — 매주 '방향'을 무료로 제시(미끼/리텐션). 2·3번은 방향만 보이는 '맛보기'.
    유료 전환은 '텍스트 해제'가 아니라 아래 재설계 패키지(결과물=이력서 재설계)로 연결(commodity 함정
    회피, Gemini 카피 + Codex 검증). 잠긴 제목 blur 제거 = 방향은 보이고, 파는 건 '내 이력서 반영'."""
    plan = plan or {}
    actions = plan.get("actions", [])
    if not actions:
        return ""
    # 근거 미확보(guardrail_ok=False) → 잠금/판매 대신 정직한 안내 (근거 없는 조언 판매 방지)
    # fail-closed: 플래그 누락 캐시는 '무근거'로 간주(Codex — fail-open 위험 차단)
    if not plan.get("guardrail_ok", False):
        return ('<div class="ap-section"><h2 class="section-title">🧭 이번 주 액션플랜</h2>'
                '<div class="ap-item"><div class="ap-step">오늘은 당신 직무에 <b>직접 결박된 새 근거 뉴스</b>가 '
                '없어 맞춤 방향을 준비하지 못했습니다. 근거가 잡히면 바로 알려드릴게요.</div></div></div>')
    sub = ('<p class="ap-sub">매주 제안하는 커리어 방향이에요. 이 방향을 <b>실제 내 이력서 결과물</b>로 '
           '만들고 싶다면 아래 재설계 패키지를 활용하세요.</p>')
    rows = []
    for i, a in enumerate(actions):
        locked = i >= 1                       # 1번=상세 공개, 2·3번=방향만(맛보기) + 패키지로 연결
        tag = {"defend": "방어", "pivot": "전환"}.get(a.get("strategy_type"), "")
        tag_cls = "tag-defend" if a.get("strategy_type") == "defend" else "tag-pivot"
        badge = '' if locked else '<span class="ap-free">이번 주 핵심 방향</span>'
        head = (f'<div class="ap-h"><span class="ap-tag {tag_cls}">{tag}</span>'
                f'{_e(a.get("title_ko", ""))}{badge}</div>')
        if locked:
            # '텍스트 해제'가 아님 — 방향(제목)은 보이고, 파는 건 '이 방향을 내 이력서 결과물로'(텍스트 X)
            # 1인 MVP 정직: '전문가' 과장 대신 '운영자가 직접 검토'(Codex fix)
            body = ('<div class="ap-lock">🔒<div>이 방향을 <b>내 이력서 요약·성과 불릿 초안</b>으로 바꾸는 건 '
                    '재설계 패키지에서 — 운영자가 직접 검토해 반영해요(결과물).</div></div>')
        else:
            steps = a.get("action_steps", [])
            step0 = _e(steps[0]) if steps else ""
            meta = f'{_e(a.get("difficulty", ""))} · 주 {_e(a.get("time_hours", ""))}h · {_e(a.get("payoff_ko", ""))}'
            body = f'<div class="ap-step">{step0}</div><div class="ap-meta">{meta}</div>'
        rows.append(f'<div class="ap-item{" locked" if locked else ""}">{head}{body}</div>')
    return ('<div class="ap-section"><h2 class="section-title">🧭 이번 주 액션플랜</h2>'
            + sub + "".join(rows) + "</div>")


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
  {_legal_links()}
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
    anc = ab.get("anchor")
    if anc:
        anchor_html = (
            f'<div class="dd-note" style="margin-top:14px;border-top:1px solid var(--bg-elevate);padding-top:12px">'
            f'🔗 <b>외부 노출 앵커</b>: 이 직무는 AI 노출 <b>상위 {round(100 - float(anc.get("percentile", 50)))}%</b> '
            f'(백분위 {anc.get("percentile","?")}, 직무 간 상대순위) · 참고 index <b>{anc.get("anchored_index","?")}</b>'
            f'<br>출처: {_e(anc.get("source",""))} · SOC {_e(anc.get("soc",""))}/{_e(anc.get("soc_confidence",""))}'
            f'<br>※ 외부 점수는 직무 간 <b>상대 AI 노출</b>(z-score)이라 우리 압력지수와 같은 척도가 아닙니다 — '
            f'직접 대입 않고 상대순위로만 앵커링({_e(anc.get("method",""))}). '
            f'표시 점수는 여전히 손추정(calibrated:false) — 태스크-레벨 데이터 연동 전까지.</div>')
    else:
        anchor_html = '<div class="dd-note">※ 현재 손추정(미보정) — O*NET·워크넷 실데이터 연동 시 정밀 수치로 격상됩니다.</div>'
    sec_auto = (f'<div class="dd-sec"><div class="dd-h">📊 과업별 자동화율</div>'
                f'<div class="dd-src">{_e(ab["source"])}</div>{rows}{anchor_html}</div>')

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

    # 4) 채용 트렌드 / 5) 임금 타격 — 실데이터 연동 시 진짜 수치, 아니면 정직 스텁
    hr, wg = deep["hiring"], deep["wage"]
    def _dd_kv(label: str, value: str) -> str:
        return (f'<div class="dd-row"><span class="n" style="width:auto;flex:1">{_e(label)}</span>'
                f'<span class="dd-v" style="width:auto;min-width:64px">{_e(value)}</span></div>')
    if hr.get("available") and hr.get("data"):
        d = hr["data"]
        arrow = "▲" if d["trend_pct"] >= 0 else "▼"
        body_hr = (_dd_kv("공고 증감(최근 6개월)", f'{arrow} {abs(d["trend_pct"]):.1f}%')
                   + _dd_kv("'AI 활용' 우대 비율", f'{d["ai_pref_pct"]:.1f}%')
                   + f'<div class="dd-note">출처: {_e(d.get("source",""))} · 기간: {_e(d.get("period",""))}</div>')
    else:
        body_hr = f'<div class="dd-pending"><b>데이터 연동 필요</b> — {_e(hr["note"])}</div>'
    sec_hr = f'<div class="dd-sec"><div class="dd-h">📈 실시간 채용 트렌드</div>{body_hr}</div>'
    if wg.get("available") and wg.get("data"):
        d = wg["data"]
        arrow = "▲" if d["yoy_pct"] >= 0 else "▼"
        body_wg = (_dd_kv("중위 연봉", f'{d["median_krw"]:,}원')
                   + _dd_kv("전년 대비", f'{arrow} {abs(d["yoy_pct"]):.1f}%')
                   + _dd_kv("프리미엄 스킬 임금격차", f'+{d["premium_gap_pct"]:.1f}%')
                   + f'<div class="dd-note">출처: {_e(d.get("source",""))}</div>')
    else:
        body_wg = f'<div class="dd-pending"><b>데이터 연동 필요</b> — {_e(wg["note"])}</div>'
    sec_wg = f'<div class="dd-sec"><div class="dd-h">💰 임금 타격 예측</div>{body_wg}</div>'

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
  {_legal_links()}
</div></body></html>"""


def render_html(job: dict, strat: dict | None = None, action_plan: dict | None = None) -> str:
    strat = strat or strategist_type(job, use_gemini=False)
    tasks = job.get("tasks", [])
    tasks_html = "".join(_task_bar(t) for t in tasks)
    pain_html = _pain_map_html(job)
    drivers = job.get("top_drivers", [])
    drv_html = "".join(_driver(d) for d in drivers) or '<p class="news-reason">오늘은 새 근거가 없습니다.</p>'
    head_task = (job.get("headline_task") or (tasks[0] if tasks else {})).get("name_ko", "핵심 업무")
    # 외부 데이터 교차참조 신뢰 배지 — 앵커된 직무만(과대표기 없이 손추정 명시) → 신뢰+상세 클릭(리텐션)
    import deepdive
    _anchor = deepdive._load_anchor(job.get("job_id", ""))
    trust_badge = (
        f'<div style="text-align:center;font-size:12.5px;color:var(--text-secondary);'
        f'background:rgba(99,102,241,.07);border:1px solid rgba(99,102,241,.2);'
        f'border-radius:12px;padding:10px 12px;margin:0 0 12px;line-height:1.55;word-break:keep-all">'
        f'🔗 이 직무의 AI 노출은 외부 공개데이터 <b>AIOE</b>(Felten 2021)로 교차참조 — '
        f'직무 간 노출 <b>상위 {round(100 - float(_anchor.get("percentile", 50)))}%</b>. '
        f'<span style="color:var(--text-tertiary)">표시 점수는 아직 손추정(미보정) · 근거는 상세에서</span></div>'
    ) if _anchor else ''
    if action_plan is None:        # 기본은 결정적 폴백(빠름·무비용). 배치가 캐시한 Gemini 플랜은 호출측이 주입.
        import actionplan
        action_plan = actionplan.make_action_plan(job, use_gemini=False)
    ap_html = _action_plan_html(action_plan)
    # 유료 CTA는 근거 결박된(guardrail_ok) 플랜이 있을 때만 — 근거 없는 조언 판매 금지
    # 정직성: 검증 못 한 사회증명("상위 5%" 등) 금지. 가치(결과물 남는 패키지)로만 소구.
    grounded = bool((action_plan or {}).get("guardrail_ok", False) and (action_plan or {}).get("actions"))
    cta_html = (f'''<div class="cta-card"><div class="cta-icon">🛡️</div>
    <h3 class="cta-title">위 방향, 내 이력서로 만들까요?</h3>
    <p class="cta-text">제시된 방향을 데이터 근거로 <b>내 이력서에 직접 반영</b> —<br>전문가가 다듬는 손에 남는 결과물</p>
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
  {pain_html}
  <div class="news-section"><h2 class="section-title">🔎 오늘 점수를 움직인 근거</h2>{drv_html}</div>
  {ap_html}
  {cta_html}
  {trust_badge}
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
  {_legal_links()}
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
.of-depth{background:rgba(255,255,255,.035);border:1px solid var(--bg-elevate);border-radius:12px;padding:12px 13px;margin:14px 0 4px;text-align:left;}
.of-depth-title{font-size:12px;font-weight:800;color:#fcd34d;margin-bottom:8px;}
.of-depth-row{font-size:12.5px;color:var(--text-secondary);line-height:1.55;margin-top:7px;word-break:keep-all;}
.of-depth-row b{color:var(--text-primary);}
.of-micro-list{margin:7px 0 0 18px;color:var(--text-secondary);font-size:12.5px;line-height:1.55;word-break:keep-all;}
"""

# 가격은 검증 대상 가설(테스트가) — 가짜 할인 금지. 정상가는 운영된 적 없으므로 취소선 표기 안 함.
OFFER_NAME = "AI 시대 커리어 재설계 패키지"   # '대체 불가/AI-Proof'식 절대보장 표현 회피(표시광고법, Codex fix)
OFFER_PRICE = "99,000"           # 1회성 패키지(월 구독 아님) · 테스트 가격(시세 10~20만원 대비 진입가)
OFFER_DELIVERY_DAYS = 5          # 영업일 기준 납기
OFFER_WEEKLY_CAP = 5             # 사람이 직접 검토하므로 주당 실제 처리 가능 인원 = 정직한 수용한계(가짜 카운터 아님)
PRESALE_PRICE = OFFER_PRICE      # 하위호환(interest price_shown 라벨)
PAIN_OFFER_NAME = "업무 고통 제거 파일럿"
PAIN_OFFER_PRICE = os.environ.get("PAIN_OFFER_PRICE", "39,000")
PAIN_OFFER_DELIVERY_DAYS = 3


_LEGAL_CSS = """
.legal-page{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:16px;padding:18px 16px;margin-bottom:14px;}
.legal-page h2{font-size:16px;margin:20px 0 8px;letter-spacing:-.3px;}
.legal-page h2:first-child{margin-top:0;}
.legal-page p,.legal-page li{font-size:13px;color:var(--text-secondary);line-height:1.65;word-break:keep-all;margin:6px 0;}
.legal-page ul{padding-left:18px;margin:6px 0 10px;}
.legal-page table{width:100%;border-collapse:collapse;margin:10px 0 14px;font-size:12.5px;color:var(--text-secondary);}
.legal-page th,.legal-page td{border:1px solid var(--bg-elevate);padding:8px;vertical-align:top;line-height:1.5;text-align:left;}
.legal-page th{color:var(--text-primary);background:rgba(255,255,255,.03);font-weight:700;}
.legal-warn{background:rgba(245,158,11,.10);border:1px solid rgba(245,158,11,.25);border-radius:12px;padding:12px 13px;color:#fcd34d;font-size:12.5px;line-height:1.6;margin-bottom:14px;word-break:keep-all;}
.legal-ref a{color:var(--text-secondary);}
"""


def _biz(key: str, fallback: str) -> str:
    return os.environ.get(key, fallback)


def privacy_html() -> str:
    """배포 전 운영자가 사업자·연락처·위탁사를 채워야 하는 개인정보처리방침 초안."""
    service = _biz("LEGAL_SERVICE_NAME", "커리어 시그널")
    operator = _biz("LEGAL_OPERATOR_NAME", "[필수 입력] 운영자/상호")
    address = _biz("LEGAL_OPERATOR_ADDRESS", "[필수 입력] 사업장 주소")
    contact = _biz("LEGAL_CONTACT_EMAIL", "[필수 입력] privacy@example.com")
    officer = _biz("LEGAL_PRIVACY_OFFICER", "[필수 입력] 개인정보 보호책임자")
    pg = _biz("LEGAL_PAYMENT_PROCESSOR", "[필수 입력] 결제대행사/PG")
    host = _biz("LEGAL_HOSTING_PROVIDER", "[필수 입력] 호스팅/서버 제공자")
    notify_tool = _biz("LEGAL_NOTIFICATION_PROVIDER", "[필수 입력] 이메일/폼/알림 도구")
    fulfillment_fields = _biz("LEGAL_FULFILLMENT_FIELDS", "[필수 입력] 결제자 이름, 이메일/전화, 주문번호, 결제금액/상태, 이력서·포트폴리오·업무 자료·인터뷰 답변 등 실제 이행에 필요한 자료")
    today = _biz("LEGAL_EFFECTIVE_DATE", "2026-06-20")
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
{_FAVICON}<title>개인정보처리방침 · {_e(service)}</title>
<style>{_CSS}{_LEGAL_CSS}</style></head><body><div class="app-container">
  <a href="/" style="display:block;text-align:center;color:var(--text-secondary);font-size:14px;margin:4px 0 16px;text-decoration:none">← 처음으로</a>
  <div class="hero-card"><div class="hero-emoji">🔐</div>
    <h1 class="hero-title">개인정보처리방침</h1>
    <p class="hero-subtitle">{_e(service)} 개인정보 처리 기준<br><span style="font-size:12px;color:var(--text-tertiary)">시행일: {_e(today)}</span></p>
  </div>
  <div class="legal-warn">초안입니다. 배포 전 운영자는 빈 사업자 정보, 실제 수집항목, 보유기간, 위탁사, 결제/자료수집 흐름을 서비스 운영 사실에 맞게 채우고 법률 검토를 받아야 합니다.</div>
  <div class="legal-page">
    <h2>1. 개인정보처리자</h2>
    <p>{_e(operator)}은(는) {_e(service)}를 운영하며, 정보주체의 개인정보를 다음 목적과 범위에서 처리합니다.</p>
    <ul>
      <li>상호/성명: {_e(operator)}</li>
      <li>주소: {_e(address)}</li>
      <li>문의/삭제 요청: {_e(contact)}</li>
      <li>개인정보 보호책임자: {_e(officer)}</li>
    </ul>

    <h2>2. 개인정보의 처리 목적</h2>
    <table>
      <tr><th>구분</th><th>목적</th></tr>
      <tr><td>리포트/직업 선택</td><td>사용자가 선택한 직업군에 대한 AI 압력 참고 리포트 제공</td></tr>
      <tr><td>오픈 안내·사전신청</td><td>정식 오픈, 파일럿 진행 여부, 결제 또는 자료 제출 안내</td></tr>
      <tr><td>pain 파일럿</td><td>사용자가 제출한 업무 고통 상황을 바탕으로 컨시어지 산출물 초안 작성 및 전달</td></tr>
      <tr><td>결제·환불</td><td>결제 확인, 계약 이행, 환불·분쟁 대응, 법령상 보관 의무 이행</td></tr>
      <tr><td>보안·남용 방지</td><td>중복 신청, 스팸, 비정상 요청 탐지. IP는 원칙적으로 비밀키 기반 해시로만 처리합니다.</td></tr>
    </table>

    <h2>3. 처리하는 개인정보 항목</h2>
    <table>
      <tr><th>수집 경로</th><th>항목</th></tr>
      <tr><td>/offer 사전신청</td><td>연락처(이메일 또는 카카오 오픈채팅 ID), 선택 직업군, 신청 시각, IP 해시(설정 시)</td></tr>
      <tr><td>/pain, /pain-offer</td><td>연락처, 직업군, 선택한 pain, 현재 일하는 형태, 실제 상황 설명, 샘플 제공 가능 여부, 신청 시각, IP 해시(설정 시)</td></tr>
      <tr><td>실결제/이행</td><td>{_e(fulfillment_fields)}</td></tr>
    </table>

    <h2>4. 개인정보의 처리 및 보유 기간</h2>
    <ul>
      <li>사전신청/오픈 안내: 정식 오픈 후 6개월 또는 삭제 요청 시까지</li>
      <li>pain 파일럿 신청 및 이행 자료: 파일럿 종료 후 6개월 또는 삭제 요청 시까지. 다만 분쟁·정산 대응에 필요한 최소 정보는 관계 법령상 기간 동안 보관할 수 있습니다.</li>
      <li>결제·계약·환불 관련 기록: 전자상거래 등 관련 법령에서 정한 보관기간이 있는 경우 그 기간</li>
      <li>보안 로그/IP 해시: 남용 방지 목적 달성 후 지체 없이 파기하거나, 운영상 필요한 최소 기간만 보관</li>
    </ul>

    <h2>5. 제3자 제공</h2>
    <p>운영자는 원칙적으로 정보주체의 개인정보를 제3자에게 제공하지 않습니다. 다만 법령상 의무, 수사기관의 적법한 요청, 정보주체의 별도 동의가 있는 경우에는 필요한 범위에서 제공할 수 있습니다.</p>

    <h2>6. 개인정보 처리위탁</h2>
    <table>
      <tr><th>수탁자</th><th>위탁업무</th></tr>
      <tr><td>{_e(pg)}</td><td>결제 처리, 결제 확인, 환불 처리</td></tr>
      <tr><td>{_e(host)}</td><td>서버 호스팅, 데이터 저장, 보안 모니터링</td></tr>
      <tr><td>{_e(notify_tool)}</td><td>오픈 안내, 자료 수집, 결과물 전달</td></tr>
    </table>

    <h2>7. 정보주체의 권리와 행사방법</h2>
    <p>정보주체는 개인정보 열람, 정정, 삭제, 처리정지, 동의 철회를 요청할 수 있습니다. 요청은 {_e(contact)}로 접수하며, 운영자는 본인 확인 후 법령상 정당한 사유가 없는 한 지체 없이 처리합니다.</p>

    <h2>8. 파기 절차 및 방법</h2>
    <p>처리 목적이 달성되거나 보유기간이 지난 개인정보는 지체 없이 파기합니다. 전자 파일은 복구하기 어렵도록 삭제하고, 출력물이 있는 경우 분쇄 또는 이에 준하는 방식으로 파기합니다.</p>

    <h2>9. 안전성 확보 조치</h2>
    <ul>
      <li>런타임 개인정보 파일은 저장소에 커밋하지 않도록 .gitignore로 분리합니다.</li>
      <li>원시 IP는 기본 저장하지 않고, 비밀키가 설정된 경우 해시값만 저장합니다.</li>
      <li>결제 완료 집계는 서명 검증된 서버 간 웹훅만 인정합니다.</li>
      <li>이력서·포트폴리오·업무자료는 이행에 필요한 최소 범위만 수집합니다.</li>
    </ul>

    <h2>10. 자동화된 결정 및 전문 판단</h2>
    <p>AI 압력지수와 pain 추천은 참고용 제품 가설 및 리포트입니다. 개인에 대한 채용, 평가, 의료, 법률, 세무, 회계 등 전문 판단을 자동 결정하지 않으며, 유료 산출물도 운영자의 검토를 전제로 합니다.</p>

    <h2>11. 고충처리 및 문의</h2>
    <p>개인정보 관련 문의, 삭제, 동의 철회, 분쟁 접수는 {_e(contact)}로 연락해 주세요.</p>

    <h2>12. 공식 참고 출처</h2>
    <p class="legal-ref">본 초안은 개인정보보호위원회/개인정보 포털의 작성지침과 국가법령정보센터의 개인정보 보호법·시행령 공개 항목을 참고해 구성했습니다. 최신 법령·가이드 확인 후 운영 사실에 맞게 수정해야 합니다.</p>
    <ul class="legal-ref">
      <li><a href="https://www.privacy.go.kr/front/bbs/bbsView.do?bbsNo=BBSMSTR_000000000049&bbscttNo=20885" target="_blank" rel="noopener">2026 개인정보 처리방침 작성지침</a></li>
      <li><a href="https://www.law.go.kr/LSW//lsLinkCommonInfo.do?ancYnChk=&chrClsCd=010202&lsJoLnkSeq=1020398435" target="_blank" rel="noopener">개인정보 보호법 제30조</a></li>
      <li><a href="https://www.law.go.kr/LSW//lsLinkCommonInfo.do?chrClsCd=010202&lspttninfSeq=67001" target="_blank" rel="noopener">개인정보 보호법 시행령 제31조</a></li>
    </ul>
  </div>
  {_legal_links()}
</div></body></html>"""


def terms_html() -> str:
    """배포 전 운영자가 사업자 정보와 실제 상품 조건을 채워야 하는 이용약관/거래조건 초안."""
    service = _biz("LEGAL_SERVICE_NAME", "커리어 시그널")
    operator = _biz("LEGAL_OPERATOR_NAME", "[필수 입력] 운영자/상호")
    biz_no = _biz("LEGAL_BUSINESS_NUMBER", "[필수 입력] 사업자등록번호")
    mail = _biz("LEGAL_CONTACT_EMAIL", "[필수 입력] support@example.com")
    address = _biz("LEGAL_OPERATOR_ADDRESS", "[필수 입력] 사업장 주소")
    telecom = _biz("LEGAL_TELECOMMERCE_NUMBER", "[필수 입력] 통신판매업 신고번호")
    today = _biz("LEGAL_EFFECTIVE_DATE", "2026-06-20")
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
{_FAVICON}<title>이용약관 · {_e(service)}</title>
<style>{_CSS}{_LEGAL_CSS}</style></head><body><div class="app-container">
  <a href="/" style="display:block;text-align:center;color:var(--text-secondary);font-size:14px;margin:4px 0 16px;text-decoration:none">← 처음으로</a>
  <div class="hero-card"><div class="hero-emoji">📄</div>
    <h1 class="hero-title">이용약관</h1>
    <p class="hero-subtitle">{_e(service)} 서비스 및 거래조건<br><span style="font-size:12px;color:var(--text-tertiary)">시행일: {_e(today)}</span></p>
  </div>
  <div class="legal-warn">초안입니다. 사업자등록, 통신판매업 신고, PG 심사, 실제 환불·이행 프로세스에 맞춰 빈 사업자 정보를 채우고 법률 검토 후 공개해야 합니다.</div>
  <div class="legal-page">
    <h2>1. 사업자 정보</h2>
    <ul>
      <li>상호/성명: {_e(operator)}</li>
      <li>사업자등록번호: {_e(biz_no)}</li>
      <li>통신판매업 신고번호: {_e(telecom)}</li>
      <li>주소: {_e(address)}</li>
      <li>고객센터/문의: {_e(mail)}</li>
    </ul>

    <h2>2. 서비스의 성격</h2>
    <p>{_e(service)}는 공개 자료와 사용자가 제공한 정보를 바탕으로 직업별 AI 압력 참고 리포트, 업무 고통 파일럿, 커리어 재설계 패키지를 제공합니다. AI 압력지수는 참고 지표이며 특정 개인의 고용·채용·평가 결과를 결정하지 않습니다.</p>

    <h2>3. 상품 및 제공시점</h2>
    <table>
      <tr><th>상품</th><th>가격</th><th>제공시점</th><th>산출물</th></tr>
      <tr><td>업무 고통 제거 파일럿</td><td>{_e(PAIN_OFFER_PRICE)}원 / 1회</td><td>자료 수령 및 결제 확인 후 영업일 {PAIN_OFFER_DELIVERY_DAYS}일 내</td><td>선택한 pain 1개에 대한 체크리스트, 문장, 템플릿 등 컨시어지 산출물</td></tr>
      <tr><td>{_e(OFFER_NAME)}</td><td>{_e(OFFER_PRICE)}원 / 1회</td><td>자료 수령 및 결제 확인 후 영업일 {OFFER_DELIVERY_DAYS}일 내</td><td>직무 진단, 이력서 재배치 가이드, 이력서 문장 초안, 커리어 디펜스 플랜</td></tr>
    </table>
    <p>실결제 링크가 설정되지 않은 경우 신청은 결제가 아닌 사전신청이며, 오픈 안내 또는 파일럿 안내를 위한 연락처 수집에 해당합니다.</p>

    <h2>4. 이용자의 자료 제출 의무</h2>
    <p>유료 산출물은 사용자가 제출한 이력서, 포트폴리오, 업무자료, 상황 설명, 인터뷰 답변을 바탕으로 작성됩니다. 자료가 제출되지 않거나 연락이 불가능한 경우 제공시점은 자료 수령일 또는 연락 가능 시점부터 다시 산정될 수 있습니다.</p>

    <h2>5. 청약철회·취소·환불</h2>
    <ul>
      <li>전자상거래법상 청약철회권 등 소비자 권리는 보장됩니다.</li>
      <li>결제 후 작업이 시작되기 전 취소 요청 시 전액 환불을 원칙으로 합니다.</li>
      <li>맞춤형 용역이 이미 제공 개시된 경우, 법령이 허용하는 범위에서 이미 제공된 부분 또는 실제 비용을 공제할 수 있습니다. 단, 운영자는 청약철회 방해나 위약금·손해배상 청구로 소비자 권리를 제한하지 않습니다.</li>
      <li>상품 내용이 표시·광고 또는 계약 내용과 다르게 이행된 경우에는 법령상 기간 내 청약철회·해제 또는 환불을 요청할 수 있습니다.</li>
      <li>환불 접수: {_e(mail)}</li>
    </ul>

    <h2>6. 전문 판단 제외 및 성과 비보장</h2>
    <p>본 서비스는 채용 합격, 이직 성공, 매출 증가, 광고 성과, 법률·의료·세무·회계 판단 결과를 보장하지 않습니다. 의료, 법률, 세무, 회계, 노무, 채용 판단이 필요한 경우 해당 분야 전문가 또는 책임자가 최종 검토해야 합니다.</p>

    <h2>7. 금지행위</h2>
    <ul>
      <li>타인의 개인정보, 영업비밀, 저작물을 권한 없이 제출하는 행위</li>
      <li>서비스 결과물을 불법, 차별, 허위광고, 사칭 목적으로 사용하는 행위</li>
      <li>자동화된 대량 요청, 보안 우회, 서버 장애 유발 행위</li>
    </ul>

    <h2>8. 개인정보 보호</h2>
    <p>개인정보 처리에 관한 사항은 <a href="/privacy" style="color:var(--text-secondary)">개인정보처리방침</a>을 따릅니다. 이력서·포트폴리오·업무자료 등 민감할 수 있는 자료는 이행에 필요한 최소 범위로만 제출해야 합니다.</p>

    <h2>9. 분쟁 및 문의</h2>
    <p>서비스 이용, 결제, 환불, 개인정보 관련 문의는 {_e(mail)}로 접수합니다. 운영자는 접수된 문의를 확인한 뒤 합리적인 기간 내 답변합니다.</p>

    <h2>10. 공식 참고 출처</h2>
    <p class="legal-ref">거래조건 표시, 청약철회 및 계약불일치 환불 고지는 전자상거래 등에서의 소비자보호에 관한 법률 관련 조문을 기준으로 보수적으로 작성한 초안입니다.</p>
    <ul class="legal-ref">
      <li><a href="https://www.law.go.kr/lsInfoP.do?ancYnChk=0&lsId=009318" target="_blank" rel="noopener">전자상거래 등에서의 소비자보호에 관한 법률</a></li>
      <li><a href="https://www.law.go.kr/LSW/expcInfoP.do?expcSeq=340541&mode=2" target="_blank" rel="noopener">전자상거래법 제17조 관련 법령해석례</a></li>
    </ul>
  </div>
  {_legal_links()}
</div></body></html>"""


_PAIN_CSS = """
.pi-summary{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:16px;padding:18px 16px;margin-bottom:14px;}
.pi-k{font-size:11px;font-weight:700;color:#34d399;background:rgba(52,211,153,.12);border-radius:6px;padding:3px 7px;display:inline-block;margin-bottom:10px;}
.pi-title{font-size:18px;font-weight:800;line-height:1.38;letter-spacing:-.4px;margin-bottom:8px;word-break:keep-all;}
.pi-desc{font-size:13.5px;color:var(--text-secondary);line-height:1.58;word-break:keep-all;}
.pi-output{background:var(--bg-elevate);border-radius:12px;padding:12px 13px;font-size:13px;line-height:1.55;margin-top:12px;word-break:keep-all;}
.pi-output b{color:#fcd34d;}
.pi-depth{background:rgba(255,255,255,.035);border:1px solid var(--bg-elevate);border-radius:12px;padding:12px 13px;margin-top:12px;}
.pi-depth-title{font-size:12px;font-weight:800;color:#fcd34d;margin-bottom:8px;}
.pi-depth-row{font-size:12.5px;color:var(--text-secondary);line-height:1.55;margin-top:7px;word-break:keep-all;}
.pi-depth-row b{color:var(--text-primary);}
.pi-depth ul{margin:7px 0 0 18px;color:var(--text-secondary);font-size:12.5px;line-height:1.55;}
.pi-probes{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:16px;padding:15px;margin:12px 0 4px;}
.pi-probe-title{font-size:13px;font-weight:800;color:var(--text-primary);margin-bottom:8px;letter-spacing:-.2px;}
.pi-probe-note{font-size:12px;color:var(--text-tertiary);line-height:1.5;margin-bottom:10px;word-break:keep-all;}
.pi-probe-list{display:grid;grid-template-columns:1fr;gap:7px;margin:0 0 12px;}
.pi-probe{font-size:12.5px;color:var(--text-secondary);line-height:1.45;background:var(--bg-elevate);border-radius:10px;padding:9px 10px;word-break:keep-all;display:flex;gap:8px;align-items:flex-start;cursor:pointer;}
.pi-probe input{margin-top:3px;flex-shrink:0;accent-color:#34d399;}
.pi-probe span{display:block;}
.pi-rec{display:inline-block;margin-top:5px;color:#34d399;font-size:11px;font-style:normal;font-weight:800;}
.pi-probe-q{border-top:1px solid var(--bg-elevate);padding-top:10px;margin-top:4px;}
.pi-probe-q ol{margin:6px 0 0 18px;color:var(--text-secondary);font-size:12.3px;line-height:1.55;word-break:keep-all;}
.pi-grid{display:grid;grid-template-columns:1fr;gap:10px;margin:12px 0 4px;}
.pi-choice{display:flex;gap:10px;background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:13px;padding:12px;text-decoration:none;color:var(--text-primary);}
.pi-choice.active{border-color:rgba(52,211,153,.45);background:rgba(52,211,153,.06);}
.pi-choice b{font-size:13.5px;line-height:1.4;word-break:keep-all;}
.pi-choice span{font-size:12px;color:var(--text-tertiary);line-height:1.45;display:block;margin-top:4px;}
.pi-form{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:16px;padding:16px;margin-top:14px;}
.pi-label{font-size:12px;font-weight:700;color:var(--text-secondary);display:block;margin:0 0 7px;}
.pi-select,.pi-textarea,.pi-input{width:100%;box-sizing:border-box;background:var(--bg-elevate);border:1px solid transparent;border-radius:12px;color:var(--text-primary);font-size:14px;padding:13px;margin-bottom:12px;}
.pi-textarea{min-height:104px;resize:vertical;line-height:1.5;}
.pi-select:focus,.pi-textarea:focus,.pi-input:focus{outline:none;border-color:#34d399;}
.pi-submit{width:100%;background:#fafafa;color:#09090b;border:0;border-radius:14px;padding:15px;font-size:15px;font-weight:800;cursor:pointer;}
.pi-offer{display:block;width:100%;box-sizing:border-box;background:#fafafa;color:#09090b;border:0;border-radius:14px;padding:15px;font-size:15px;font-weight:800;text-align:center;text-decoration:none;margin-top:10px;}
.pi-ok{display:none;text-align:center;padding:18px;background:rgba(52,211,153,.10);border-radius:14px;font-size:14px;line-height:1.55;margin-top:12px;}
.pi-note{font-size:12px;color:var(--text-tertiary);line-height:1.6;margin-top:12px;word-break:keep-all;}
"""


def pain_intake_html(job: dict, pain_id: str | None = None, recommended_micro_itches=None) -> str:
    """직업별 가려움 온보딩 — '어떤 결과물을 원하나' 검증용.

    결제/제공 확정 페이지가 아니다. pain_intent는 정성 수요 신호이며 presale_leads와 분리한다.
    """
    import painmap
    import pain_deepdive
    import pain_probe
    jid = job.get("job_id", "")
    name = job.get("job_name_ko", "")
    pm = painmap.build(job, limit=3)
    pains = pm.get("pains") or []
    if not pains:
        return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
{_FAVICON}<title>가려운 업무 · 커리어 시그널</title><style>{_CSS}</style></head><body><div class="app-container">
<a href="/report?job={_e(jid)}" style="display:block;text-align:center;color:var(--text-secondary);font-size:14px;margin:4px 0 16px;text-decoration:none">← 내 리포트로</a>
<div class="hero-card"><div class="hero-emoji">🩹</div><h1 class="hero-title">준비 중이에요</h1>
<p class="hero-subtitle">이 직무의 가려운 업무 가설을 아직 만들지 못했습니다.</p></div></div></body></html>"""
    chosen = painmap.get(job, pain_id or "") or pains[0]
    pid = chosen.get("pain_id", "")
    deep = pain_deepdive.build(job, pid) or {}
    input_items = "".join(
        f"<li>{_e(x)}</li>" for x in deep.get("minimum_inputs_ko", [])[:4]
    )
    depth_html = (
        '<div class="pi-depth"><div class="pi-depth-title">정말 가려운 지점</div>'
        f'<div class="pi-depth-row"><b>터지는 순간</b><br>{_e(deep.get("burning_moment_ko", chosen.get("moment_ko", "")))}</div>'
        f'<div class="pi-depth-row"><b>왜 그냥 AI로 부족한가</b><br>{_e(deep.get("bad_ai_trap_ko", ""))}</div>'
        f'<div class="pi-depth-row"><b>첫 10분 안도감</b><br>{_e(deep.get("first_relief_ko", ""))}</div>'
        f'<div class="pi-depth-row"><b>필요한 최소 자료</b><ul>{input_items}</ul></div>'
        "</div>"
    )
    probe = pain_probe.build(job) or {}
    recommended = set(pain_probe.selected_micro_itches(jid, recommended_micro_itches or []))
    probe_rows = []
    for i, x in enumerate(probe.get("micro_itches_ko", [])[:8], start=1):
        checked = " checked" if x in recommended else ""
        rec = '<em class="pi-rec">많이 선택됨</em>' if x in recommended else ""
        probe_rows.append(
            f'<label class="pi-probe"><input class="pi-probe-check" type="checkbox" data-mi="{i}" value="{_e(x)}"{checked}>'
            f'<span>{_e(x)}{rec}</span></label>'
        )
    probe_items = "".join(probe_rows)
    probe_questions = "".join(
        f"<li>{_e(x)}</li>" for x in probe.get("interview_questions_ko", [])[:3]
    )
    probe_html = ""
    if probe_items:
        probe_html = (
            '<div class="pi-probes">'
            '<div class="pi-probe-title">혹시 이런 순간인가요?</div>'
            f'<p class="pi-probe-note">{_e(probe.get("note_ko", ""))}</p>'
            f'<div class="pi-probe-list">{probe_items}</div>'
        )
        if probe_questions:
            probe_html += (
                '<div class="pi-probe-q"><div class="pi-probe-title">상황을 쓸 때 답하면 좋은 질문</div>'
                f"<ol>{probe_questions}</ol></div>"
            )
        probe_html += "</div>"
    choices = []
    for p in pains:
        active = " active" if p.get("pain_id") == pid else ""
        href = f'/pain?job={_e(jid)}&pain={_e(p.get("pain_id", ""))}'
        choices.append(
            f'<a class="pi-choice{active}" href="{href}"><div>'
            f'<b>{_e(p.get("itch_ko", ""))}</b>'
            f'<span>{_e(p.get("artifact_ko", ""))}</span>'
            '</div></a>'
        )
    job_js = json.dumps(jid, ensure_ascii=False)
    pain_js = json.dumps(pid, ensure_ascii=False)
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta property="og:type" content="website"><meta property="og:site_name" content="커리어 시그널">
<meta property="og:title" content="{_e(name)}의 진짜 가려운 업무">
<meta property="og:description" content="AI 압력보다 더 구체적으로, 매주 반복되는 업무 고통을 결과물로 줄여보세요.">{_og_image_meta()}
{_FAVICON}<title>{_e(name)} 가려운 업무 · 커리어 시그널</title>
<style>{_CSS}{_PAIN_CSS}</style></head><body><div class="app-container">
  <a href="/report?job={_e(jid)}" style="display:block;text-align:center;color:var(--text-secondary);font-size:14px;margin:4px 0 16px;text-decoration:none">← 내 리포트로</a>
  <div class="hero-card"><div class="hero-emoji">🩹</div>
    <h1 class="hero-title">{_e(name)} 업무 고통 줄이기</h1>
    <p class="hero-subtitle">AI 위험보다 더 구체적으로,<br>이번 주 정말 줄이고 싶은 반복 업무를 고릅니다.</p></div>
  <div class="pi-summary">
    <span class="pi-k">선택한 가려움 · { _e(pm.get("label_ko", "제품 가설")) }</span>
    <div class="pi-title">{_e(chosen.get("itch_ko", ""))}</div>
    <div class="pi-desc">{_e(chosen.get("moment_ko", ""))}</div>
    <div class="pi-output"><b>만들어줄 결과물</b><br>{_e(chosen.get("artifact_ko", ""))}</div>
    {depth_html}
  </div>
  {probe_html}
  <div class="pi-grid">{"".join(choices)}</div>
  <form class="pi-form" id="piForm" onsubmit="return piSubmit(event)">
    <input id="piHp" type="text" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px" aria-hidden="true">
    <label class="pi-label" for="piRole">현재 일하는 형태</label>
    <select class="pi-select" id="piRole">
      <option value="employee">회사 실무자</option>
      <option value="freelancer">프리랜서/개인사업자</option>
      <option value="jobseeker">취업·이직 준비 중</option>
      <option value="lead">팀 리드/관리자</option>
    </select>
    <label class="pi-label" for="piSituation">이 문제가 실제로 터지는 상황</label>
    <textarea class="pi-textarea" id="piSituation" maxlength="600" placeholder="예: 클라이언트 수정 요청이 카톡/메일/댓글에 흩어져서 타임코드별로 다시 정리하는 데 1시간 넘게 걸려요."></textarea>
    <label class="pi-label" for="piSample">샘플 자료 제공 가능 여부</label>
    <select class="pi-select" id="piSample">
      <option value="yes">가능 — 작업물/문서/메모 일부 제공 가능</option>
      <option value="redacted">가능 — 민감정보 지우고 제공 가능</option>
      <option value="no">어렵다 — 설명만 가능</option>
    </select>
    <label class="pi-label" for="piContact">연락처</label>
    <input class="pi-input" id="piContact" type="text" maxlength="120" required placeholder="이메일 또는 카카오 오픈채팅 ID">
    <label style="display:flex;gap:8px;align-items:flex-start;font-size:12px;color:var(--text-secondary);margin:0 2px 12px;text-align:left;line-height:1.5">
      <input type="checkbox" id="piConsent" style="margin-top:2px;flex-shrink:0">
      <span>(필수) 업무 고통 검증과 오픈 안내를 위해 연락처와 작성 내용을 수집·이용하는 데 동의합니다. 보관: 정식 오픈 후 6개월 또는 삭제 요청 시까지. 동의 거부 시 신청 안내가 제공되지 않습니다. <a href="/privacy" target="_blank" rel="noopener" style="color:var(--text-secondary)">개인정보처리방침</a></span></label>
    <button class="pi-submit" type="submit">이 업무 고통 줄이기 신청</button>
    <a class="pi-offer" id="piOffer" href="/pain-offer?job={_e(jid)}&pain={_e(pid)}">파일럿 결과물 보기 →</a>
    <div class="pi-ok" id="piOk">접수했어요. 이 가려움이 가장 많이 모이면 먼저 제품화합니다.<br>정식 오픈 전 안내드릴게요.</div>
    <p class="pi-note">※ 이 페이지는 결제가 아닙니다. 선택한 업무 고통과 결과물 수요를 검증하기 위한 사전 신청입니다. 의료·법률·회계 등 전문 판단은 자동화하지 않습니다.</p>
  </form>
  {_legal_links()}
</div>
<script>
function piSubmit(e){{e.preventDefault();
  var contact=document.getElementById('piContact').value.trim();
  if(!contact){{return false;}}
  if(!document.getElementById('piConsent').checked){{alert('개인정보 수집·이용 동의가 필요합니다.');return false;}}
  var payload={{
    job:{job_js}, pain_id:{pain_js}, contact:contact,
    role_type:document.getElementById('piRole').value,
    sample_available:document.getElementById('piSample').value,
    situation:document.getElementById('piSituation').value.trim().slice(0,600),
    micro_itches:Array.prototype.slice.call(document.querySelectorAll('.pi-probe-check:checked')).map(function(x){{return x.value;}}).slice(0,6),
    consent:true, hp_url:document.getElementById('piHp').value
  }};
  fetch('/pain/intent',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}})
   .then(function(r){{if(!r.ok){{throw new Error('bad');}}
     document.getElementById('piForm').querySelector('.pi-submit').style.display='none';
     document.getElementById('piOk').style.display='block';}})
   .catch(function(){{alert('잠시 후 다시 시도해 주세요.');}});
  return false;}}
function piSelectedMi(){{return Array.prototype.slice.call(document.querySelectorAll('.pi-probe-check:checked'))
  .map(function(x){{return x.getAttribute('data-mi');}}).filter(Boolean).slice(0,6);}}
function piUpdateOfferLink(){{var link=document.getElementById('piOffer');if(!link){{return;}}
  var qs=piSelectedMi().map(function(n){{return '&mi='+encodeURIComponent(n);}}).join('');
  link.href='/pain-offer?job='+encodeURIComponent({job_js})+'&pain='+encodeURIComponent({pain_js})+qs;}}
Array.prototype.slice.call(document.querySelectorAll('.pi-probe-check')).forEach(function(x){{x.addEventListener('change',piUpdateOfferLink);}});
piUpdateOfferLink();
</script>
</body></html>"""


def pain_offer_html(job: dict, pain_id: str, payment_url: str | None = None, micro_itches=None) -> str:
    """pain별 좁은 파일럿 오퍼.

    범용 커리어 재설계 패키지와 분리한다. 여기서 파는 것은 "특정 반복 업무를 줄이는 결과물 1개"다.
    PAYMENT_URL과 별도의 PAIN_PAYMENT_URL을 연결하면 실결제로 전환할 수 있다.
    """
    import painmap
    import pain_deepdive
    import pain_probe
    jid = job.get("job_id", "")
    name = job.get("job_name_ko", "")
    pain = painmap.get(job, pain_id)
    if not pain:
        return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
{_FAVICON}<title>{PAIN_OFFER_NAME} · 커리어 시그널</title><style>{_CSS}</style></head><body><div class="app-container">
<a href="/report?job={_e(jid)}" style="display:block;text-align:center;color:var(--text-secondary);font-size:14px;margin:4px 0 16px;text-decoration:none">← 내 리포트로</a>
<div class="hero-card"><div class="hero-emoji">🩹</div><h1 class="hero-title">파일럿 준비 중</h1>
<p class="hero-subtitle">선택한 업무 고통을 찾지 못했습니다.</p></div></div></body></html>"""
    safe_payment_url = _safe_url(payment_url) if payment_url else "#"
    real = safe_payment_url != "#"
    tasks = ", ".join(pain.get("task_names_ko") or []) or "관련 업무"
    deep = pain_deepdive.build(job, pain_id) or {}
    offer_depth = (
        '<div class="of-depth"><div class="of-depth-title">왜 돈 내고 줄이는가</div>'
        f'<div class="of-depth-row"><b>구매가 터지는 순간</b><br>{_e(deep.get("paid_trigger_ko", ""))}</div>'
        f'<div class="of-depth-row"><b>첫 10분 안도감</b><br>{_e(deep.get("first_relief_ko", ""))}</div>'
        f'<div class="of-depth-row"><b>성공 기준</b><br>{_e(deep.get("success_metric_ko", ""))}</div>'
        "</div>"
    )
    selected_micro = pain_probe.selected_micro_itches(jid, micro_itches or [])[:6]
    micro_html = ""
    if selected_micro:
        micro_rows = "".join(f"<li>{_e(x)}</li>" for x in selected_micro)
        micro_html = (
            '<div class="of-depth"><div class="of-depth-title">이번 파일럿에서 먼저 줄일 작은 가려움</div>'
            f'<ul class="of-micro-list">{micro_rows}</ul>'
            "</div>"
        )
    micro_adjustment_html = ""
    adjustment = pain_probe.artifact_adjustment(jid, selected_micro)
    adjustment_rows = adjustment.get("adjustment_rows", [])
    if adjustment_rows:
        rows = []
        for row in adjustment_rows[:4]:
            rows.append(
                '<div class="of-depth-row">'
                f'<b>{_e(row.get("artifact_slot_ko", ""))}</b><br>'
                f'필수 칸: {_e(row.get("template_fields_ko", ""))}<br>'
                f'QA: {_e(row.get("qa_check_ko", ""))}'
                '</div>'
            )
        micro_adjustment_html = (
            '<div class="of-depth"><div class="of-depth-title">선택 때문에 달라지는 결과물</div>'
            f'{_e(adjustment.get("note_ko", ""))}'
            f'{"".join(rows)}'
            "</div>"
        )
    hero_promise = (
        f"'{_e(selected_micro[0])}'부터 줄이는<br><b>손에 남는 작업 산출물</b>을 만듭니다."
        if selected_micro else
        f"{_e(name)}의 반복 업무 하나를<br><b>손에 남는 작업 산출물</b>로 줄입니다."
    )
    action = (f'<a href="{_e(safe_payment_url)}" class="of-submit">'
              f'{PAIN_OFFER_PRICE}원 결제하고 파일럿 신청 →</a>' if real else
              f'''<form id="poForm" onsubmit="return poSubmit(event)">
      <input class="of-input" id="poHp" type="text" tabindex="-1" autocomplete="off"
        style="position:absolute;left:-9999px" aria-hidden="true">
      <input class="of-input" id="poContact" type="text" maxlength="120" required
        placeholder="이메일 또는 카카오 오픈채팅 ID">
      <label style="display:flex;gap:8px;align-items:flex-start;font-size:12px;color:var(--text-secondary);margin:0 2px 12px;text-align:left;line-height:1.5">
        <input type="checkbox" id="poConsent" style="margin-top:2px;flex-shrink:0">
        <span>(필수) 파일럿 안내를 위해 연락처와 선택한 업무 고통 정보를 수집·이용하는 데 동의합니다. 보관: 정식 오픈 후 6개월 또는 삭제 요청 시까지. <a href="/privacy" target="_blank" rel="noopener" style="color:var(--text-secondary)">개인정보처리방침</a> · <a href="/terms" target="_blank" rel="noopener" style="color:var(--text-secondary)">이용약관</a></span></label>
      <button class="of-submit" type="submit">파일럿 신청 — 오픈 시 우선 안내</button>
    </form>
    <div class="of-ok" id="poOk">신청 완료! 이 파일럿을 먼저 열게 되면 안내드릴게요.</div>''')
    note = (f"※ {'실결제 파일럿입니다' if real else '사전신청은 결제가 아닙니다'} — "
            f"결과물은 선택한 업무 고통 1개를 줄이는 컨시어지 산출물이며, 자동화된 전문 판단이나 성과 보장을 제공하지 않습니다. "
            f"실결제 시 법정 청약철회권 및 계약 불일치 시 환불권을 보장합니다.")
    job_js = json.dumps(jid, ensure_ascii=False)
    pain_js = json.dumps(pain.get("pain_id", ""), ensure_ascii=False)
    micro_js = json.dumps(selected_micro, ensure_ascii=False)
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta property="og:type" content="website"><meta property="og:site_name" content="커리어 시그널">
<meta property="og:title" content="{_e(name)} {PAIN_OFFER_NAME}">
<meta property="og:description" content="{_e(pain.get("artifact_ko", ""))}">{_og_image_meta()}
{_FAVICON}<title>{PAIN_OFFER_NAME} · {_e(name)}</title>
<style>{_CSS}{_OFFER_CSS}</style></head><body><div class="app-container">
  <a class="of-back" href="/pain?job={_e(jid)}&pain={_e(pain.get("pain_id", ""))}">← 가려움 선택으로</a>
  <div class="hero-card"><div class="hero-emoji">🧰</div>
    <h1 class="hero-title">{PAIN_OFFER_NAME}</h1>
    <p class="hero-subtitle">{hero_promise}</p>
  </div>
  <div class="cta-card" style="text-align:center">
    <div class="of-price"><span class="of-now">{PAIN_OFFER_PRICE}원</span><span class="of-unit">/ 파일럿 1회 · 영업일 {PAIN_OFFER_DELIVERY_DAYS}일 내</span></div>
    <div class="of-kicker">선택한 문제</div>
    <ul class="of-list">
      <li><span class="of-ic">🩹</span><div><b>{_e(pain.get("itch_ko", ""))}</b><br>{_e(pain.get("moment_ko", ""))}</div></li>
      <li><span class="of-ic">📌</span><div><b>관련 업무</b><br>{_e(tasks)}</div></li>
      <li><span class="of-ic">🧾</span><div><b>전달 결과물</b><br>{_e(pain.get("artifact_ko", ""))}</div></li>
      <li><span class="of-ic">🛠️</span><div><b>작업 방식</b><br>{_e(pain.get("service_move_ko", ""))}</div></li>
    </ul>
    {offer_depth}
    {micro_html}
    {micro_adjustment_html}
    <div class="of-kicker">파일럿 진행</div>
    <ol class="of-steps">
      <li>{'결제' if real else '신청'} 후 샘플 자료 또는 상황 설명 제출</li>
      <li>운영자가 민감정보를 제외하고 반복 패턴을 정리</li>
      <li>{_e(pain.get("artifact_ko", ""))} 형태의 초안을 전달</li>
      <li>바로 쓸 수 있는 체크리스트/문장/템플릿으로 마무리</li>
    </ol>
    <div class="of-human">🤝 <b>정직한 범위:</b> 이 파일럿은 자동 SaaS가 아니라 초기 컨시어지 검증입니다. 좋은 신호가 모인 pain만 제품화합니다.</div>
    {action}
  </div>
  <p class="of-note">{note}</p>
  {_legal_links()}
</div>
<script>
function poSubmit(e){{e.preventDefault();
  var c=document.getElementById('poContact').value.trim();
  if(!c){{return false;}}
  if(!document.getElementById('poConsent').checked){{alert('개인정보 수집·이용 동의가 필요합니다.');return false;}}
  fetch('/pain/intent',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{contact:c,job:{job_js},pain_id:{pain_js},role_type:'unknown',
      sample_available:'unknown',situation:'pain-offer pilot interest',offer_type:'pain-pack',
      micro_itches:{micro_js},
      consent:true,hp_url:document.getElementById('poHp').value}})}})
   .then(function(r){{if(!r.ok){{throw new Error('bad');}}
     document.getElementById('poForm').style.display='none';
     document.getElementById('poOk').style.display='block';}})
   .catch(function(){{alert('잠시 후 다시 시도해 주세요.');}});
  return false;}}
</script>
</body></html>"""


def offer_html(job: dict, payment_url: str | None = None, grounded: bool = True) -> str:
    """AI 시대 커리어 재설계 패키지 — 런칭=지불주체 스모크테스트. '결과물이 손에 남는' 1회성 패키지.
    위협지수(무료 미끼) → 결과물(이력서 재설계)이 유료 정점. 주간 텍스트 구독(commodity) 폐기.
    PAYMENT_URL(env) 연결 시 실결제 버튼+환불 고지, 미연결 시 사전신청(리드) 수집.
    grounded=False(직무에 결박된 근거 없음) → 결제/판매 대신 정직 안내(제품레벨 무근거 판매 금지, Codex fix)."""
    jid = _e(job.get("job_id", ""))
    name = _e(job.get("job_name_ko", ""))
    head_task = _e((job.get("headline_task") or {}).get("name_ko") or "핵심 업무")
    if not grounded:
        return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
{_FAVICON}<title>{OFFER_NAME} · {name}</title>
<style>{_CSS}</style></head><body><div class="app-container">
  <a href="/report?job={jid}" style="display:block;text-align:center;color:var(--text-secondary);font-size:14px;margin:4px 0 16px;text-decoration:none">← 내 리포트로</a>
  <div class="hero-card"><div class="hero-emoji">🧭</div>
    <h1 class="hero-title">맞춤 패키지를 준비 중이에요</h1>
    <p class="hero-subtitle">'{name}' 직무에 <b>직접 결박된 새 근거</b>가 아직 충분치 않아,<br>지금은 재설계 패키지를 안내하지 않습니다.</p>
  </div>
  <p class="footer-text">※ 근거 없는 맞춤 처방·패키지는 판매하지 않습니다(정직성 원칙). 직무에 결박된 근거가 잡히면 리포트에서 바로 안내드릴게요.</p>
  {_legal_links()}
</div></body></html>"""
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
        <span>(필수) 오픈 안내를 위해 연락처 수집·이용에 동의합니다. 수집 항목: 연락처(이메일 또는 카카오 오픈채팅 ID) / 목적: 오픈 알림 / 보관: 정식 오픈 후 6개월 또는 삭제 요청 시까지 / 삭제·문의는 회신으로 요청 가능. 동의를 거부하실 수 있으며, 거부 시 사전신청 안내가 제공되지 않을 뿐 다른 불이익은 없습니다. <a href="/privacy" target="_blank" rel="noopener" style="color:var(--text-secondary)">개인정보처리방침</a> · <a href="/terms" target="_blank" rel="noopener" style="color:var(--text-secondary)">이용약관</a></span></label>
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
      <li><span class="of-ic">📝</span><div><b>이력서 핵심 문장 초안</b> — 운영자가 직접 다듬은 요약(Summary)·성과 불릿 초안 + 적용 가이드.</div></li>
      <li><span class="of-ic">🧭</span><div><b>1~3년 커리어 디펜스 플랜</b> — 추가로 쌓으면 좋은 권장 스킬셋.</div></li>
    </ul>
    <div class="of-kicker">진행 과정</div>
    <ol class="of-steps">
      <li>{'결제' if real else '신청'} 후 기존 이력서·포트폴리오 제출</li>
      <li>WorkRadar 데이터로 직무 태스크 분석 + '안전 역량' 매핑</li>
      <li>1:1 서면 인터뷰 — 이력서에 누락된 '쉽게 대체되지 않는 경험' 발굴</li>
      <li>최종 패키지 전달 + 적용 가이드 (영업일 {OFFER_DELIVERY_DAYS}일 내)</li>
    </ol>
    <div class="of-human">🤝 <b>AI가 어디까지 하나:</b> 직무 압력 데이터 수집·1차 분류는 AI가, <b>당신의 고유 경험 발굴과 이력서 최종 문장은 운영자가 직접 검토·작성</b>합니다. 'AI가 다 써준다'가 아닙니다.</div>
    {cap_line}
    {action}
  </div>
  <p class="of-note">{note}</p>
  {_legal_links()}
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


def payment_pending_html(job_id: str = "") -> str:
    """결제 success 리다이렉트 랜딩 — 정직성: 이 페이지는 결제 '접수' 확인일 뿐,
    결제 완료를 자동 확정하지 않는다(완료는 서명검증된 웹훅으로만). 사용자 오인 방지."""
    back = f"/report?job={_e(job_id)}" if job_id else "/"
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
{_FAVICON}<title>결제 접수 · 커리어 시그널</title>
<style>{_CSS}</style></head><body><div class="app-container">
  <div class="hero-card"><div class="hero-emoji">🧾</div>
    <h1 class="hero-title">결제 요청이 접수되었어요</h1>
    <p class="hero-subtitle">결제 완료는 <b>영업일 내 확인</b> 후,<br>입력하신 연락처로 진행 안내를 드립니다.</p>
  </div>
  <p class="footer-text">※ 이 페이지는 결제 <b>접수</b> 확인이며, 결제 완료 자체를 자동 확정하지는 않습니다. 결제가 정상 처리되지 않았다면 환불·재시도 안내를 드립니다. 문의는 신청 시 연락처로 회신 가능합니다.</p>
  <a href="{back}" style="display:block;text-align:center;background:var(--bg-elevate);color:var(--text-primary);padding:13px;border-radius:14px;margin:8px 0 18px;text-decoration:none;font-weight:600">← 내 리포트로</a>
  {_legal_links()}
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
    import painmap
    import pain_probe
    pain = painmap.build(res, limit=1)["pains"][0]
    sample_micro = (pain_probe.get("video-editor") or {}).get("micro_itches_ko", [])[:2]
    pain_path = os.path.join(out_dir, "sample-pain-video-editor.html")
    with open(pain_path, "w", encoding="utf-8") as f:
        f.write(pain_intake_html(res, pain["pain_id"], recommended_micro_itches=sample_micro))
    pain_offer_path = os.path.join(out_dir, "sample-pain-offer-video-editor.html")
    with open(pain_offer_path, "w", encoding="utf-8") as f:
        f.write(pain_offer_html(res, pain["pain_id"], micro_itches=sample_micro))
    privacy_path = os.path.join(out_dir, "sample-privacy.html")
    with open(privacy_path, "w", encoding="utf-8") as f:
        f.write(privacy_html())
    terms_path = os.path.join(out_dir, "sample-terms.html")
    with open(terms_path, "w", encoding="utf-8") as f:
        f.write(terms_html())
    probe_path = os.path.join(out_dir, "sample-pain-probes.md")
    with open(probe_path, "w", encoding="utf-8") as f:
        f.write(pain_probe.markdown_catalog(eng.score([], now=datetime(2026, 6, 6, tzinfo=timezone.utc))))
    print("전략가 타입:", json.dumps(strat, ensure_ascii=False))
    print("리포트 생성:", path)
    print("가려움 온보딩 생성:", pain_path)
    print("가려움 파일럿 오퍼 생성:", pain_offer_path)
    print("개인정보처리방침 생성:", privacy_path)
    print("이용약관 생성:", terms_path)
    print("micro-itch probe 생성:", probe_path)
