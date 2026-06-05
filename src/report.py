"""
커리어 시그널 — 미니웹 결과리포트 렌더러 (R4b)

scoring.ScoringEngine.score() 의 직무 결과 dict → 모바일 우선 정적 HTML.
구성: 전략가 타입(MBTI식, 위협+기회 동시 → 공유 부끄럽지 않게, Gemini 카피) +
      기상예보 시각화 + 태스크별 압력(task-first) + 근거뉴스(출처 투명) + 유료트리거.

카피는 Gemini 2.5 Pro(키 env) → 실패 시 결정적 폴백.
실행: GEMINI_API_KEY=... python3 src/report.py  → web/sample-report.html 생성
"""
from __future__ import annotations

import html
import json
import os
import urllib.request
from urllib.parse import urlsplit

MODEL = "gemini-2.5-pro"
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

WEATHER_STYLE = {
    "맑음": ("☀️", "#3da35d"), "구름조금": ("⛅", "#c8a415"),
    "흐림": ("🌫️", "#d2772b"), "태풍경보": ("🌀", "#d23b3b"),
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
    key = os.environ["GEMINI_API_KEY"]
    payload = {"contents": [{"parts": [{"text": _TYPE_PROMPT.format(job=job, high=high, low=low)}]}],
               "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"}}
    req = urllib.request.Request(_ENDPOINT.format(model=MODEL, key=key),
                                 data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        resp = json.load(r)
    d = json.loads(resp["candidates"][0]["content"]["parts"][0]["text"])
    return {k: str(d.get(k, "")).strip() for k in
            ("type_name", "emoji", "tagline", "threat", "opportunity")}


# ── HTML 렌더 ─────────────────────────────────────────────────────────
def _e(s) -> str:
    return html.escape(str(s))


def _safe_url(u: str) -> str:
    """http/https만 허용 (javascript:/data: 등 scheme XSS 차단 — Codex 리뷰)."""
    try:
        if urlsplit(str(u)).scheme.lower() in ("http", "https"):
            return str(u)
    except Exception:
        pass
    return "#"


def _task_bar(t: dict) -> str:
    emoji, color = WEATHER_STYLE.get(t["weather"], ("", "#888"))
    pct = max(2, min(100, t["index"]))
    return f"""
      <div class="task">
        <div class="task-h"><span>{emoji} {_e(t['name_ko'])}</span><b>{t['index']}</b></div>
        <div class="bar"><i style="width:{pct}%;background:{color}"></i></div>
      </div>"""


def _driver(d: dict) -> str:
    tier = {1: "공식", 2: "언론", 3: "벤더PR"}.get(d.get("source_tier", 3), "기타")
    url = _e(_safe_url(d.get("url", "#")))
    return f"""
      <a class="drv" href="{url}" target="_blank" rel="noopener">
        <span class="badge t{d.get('source_tier',3)}">{tier}</span>
        <span class="drv-t">{_e(d.get('title',''))[:70]}</span>
        <span class="drv-r">{_e(d.get('reason_ko',''))}</span>
      </a>"""


def render_html(job: dict, strat: dict | None = None) -> str:
    strat = strat or strategist_type(job, use_gemini=False)
    emoji, color = WEATHER_STYLE.get(job.get("weather", "흐림"), ("🌫️", "#d2772b"))
    tasks_html = "".join(_task_bar(t) for t in job.get("tasks", []))
    drivers = job.get("top_drivers", [])
    drv_html = "".join(_driver(d) for d in drivers) or '<p class="muted">오늘은 새 근거가 없습니다.</p>'
    return f"""<!doctype html><html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>커리어 시그널 · {_e(job.get('job_name_ko',''))}</title>
<style>
:root{{--bg:#0f1115;--card:#181b22;--mut:#8a92a6;--line:#272b34}}
*{{box-sizing:border-box}}body{{margin:0;font-family:-apple-system,'Apple SD Gothic Neo',sans-serif;
background:var(--bg);color:#eef1f6;padding:18px;max-width:480px;margin:auto}}
.type{{text-align:center;padding:22px 14px;background:linear-gradient(160deg,{color}22,transparent);
border:1px solid var(--line);border-radius:18px}}
.type .em{{font-size:46px}}.type h1{{margin:8px 0 4px;font-size:22px}}
.type .tag{{color:var(--mut);font-size:14px;margin:0}}
.hero{{display:flex;align-items:center;gap:14px;margin:16px 0;padding:16px;
background:var(--card);border-radius:16px;border:1px solid var(--line)}}
.hero .w{{font-size:42px}}.hero .lab{{font-size:13px;color:var(--mut)}}
.hero .v{{font-size:30px;font-weight:800;color:{color}}}
.sec{{margin:18px 0 8px;font-size:13px;color:var(--mut);font-weight:700}}
.task{{margin:10px 0}}.task-h{{display:flex;justify-content:space-between;font-size:14px;margin-bottom:5px}}
.bar{{height:9px;background:#23262f;border-radius:6px;overflow:hidden}}.bar i{{display:block;height:100%}}
.to{{display:flex;gap:10px;margin:14px 0;padding:12px;background:#1d2129;border-radius:12px;font-size:13px}}
.to .k{{color:var(--mut)}}.to b{{color:#ff8e64}}
.drv{{display:block;padding:11px;margin:8px 0;background:var(--card);border:1px solid var(--line);
border-radius:12px;text-decoration:none;color:inherit}}
.badge{{font-size:11px;padding:2px 7px;border-radius:20px;margin-right:6px}}
.t1{{background:#1d4d2b;color:#7bd99a}}.t2{{background:#3a3a1d;color:#d9d27b}}.t3{{background:#4d2b1d;color:#d9a17b}}
.drv-t{{font-weight:600}}.drv-r{{display:block;color:var(--mut);font-size:12px;margin-top:3px}}
.pay{{margin:20px 0;padding:18px;border-radius:16px;border:1px dashed {color};
background:linear-gradient(160deg,{color}18,transparent);text-align:center}}
.pay h3{{margin:0 0 6px;font-size:16px}}.pay p{{color:var(--mut);font-size:13px;margin:6px 0 12px}}
.btn{{display:inline-block;background:{color};color:#0f1115;font-weight:800;padding:12px 22px;
border-radius:30px;text-decoration:none}}
.share{{width:100%;margin-top:14px;padding:13px;border:1px solid var(--line);background:transparent;
color:#eef1f6;border-radius:30px;font-size:15px;font-weight:700}}
.foot{{color:var(--mut);font-size:11px;text-align:center;margin-top:18px;line-height:1.6}}
.muted{{color:var(--mut);font-size:13px}}
</style></head><body>
  <div class="type">
    <div class="em">{_e(strat.get('emoji','🧭'))}</div>
    <h1>{_e(strat.get('type_name','전략가형'))}</h1>
    <p class="tag">{_e(strat.get('tagline',''))}</p>
  </div>
  <div class="hero">
    <div class="w">{emoji}</div>
    <div><div class="lab">{_e(job.get('job_name_ko',''))} · AI 압력 (보조지표)</div>
      <div class="v">{job.get('index','-')} <span style="font-size:14px;color:var(--mut)">±{job.get('ci',12)} · {_e(job.get('weather',''))}</span></div></div>
  </div>
  <div class="to"><div><span class="k">위협</span><br>{_e(strat.get('threat',''))}</div></div>
  <div class="to"><div><span class="k">기회</span> <b>↗</b><br>{_e(strat.get('opportunity',''))}</div></div>
  <div class="sec">📊 내 업무별 AI 압력 (높을수록 자동화 신호 ↑)</div>
  {tasks_html}
  <div class="sec">🔎 오늘 점수를 움직인 근거</div>
  {drv_html}
  <div class="pay">
    <h3>🔒 상위 5%는 이미 대응 중입니다</h3>
    <p>방금 확인한 '{_e((job.get('tasks') or [{}])[0].get('name_ko','내 업무'))}' 압력에<br>가장 먼저 대응한 사람들의 대응법 3가지</p>
    <a class="btn" href="#">대응 전략 보기</a>
  </div>
  <button class="share">📲 내 전략가 타입 공유하기</button>
  <p class="foot">※ 본 지수는 공개된 AI 뉴스를 정해진 원칙으로 계량화한 <b>참고 지표</b>입니다.<br>
  특정 개인·기업의 대체를 단정하지 않으며, 모든 변동의 근거를 공개합니다.</p>
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
