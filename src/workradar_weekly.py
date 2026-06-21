"""WorkRadar US 주간 리포트 엔진 — 구독 리텐션의 심장 (stdlib only).

구독자별로 "내 직업 AI 압력 + 이번 주 신호 + 내 분기 다음 행동"을 담은 주간 다이제스트를
생성해 발송 대기열(data/wr_outbox.jsonl)에 적재한다. 실제 발송은 sender(Resend/SMTP)가 처리.

정직성:
- 점수는 calibrated:false 손추정 → "directional reference". 예측 단정 금지.
- '이번 주 신호'는 큐레이션(editorial) 라벨 + 실제 출처 링크. 가짜 뉴스/가짜 수치 금지.
- 매 메일에 수신거부(unsubscribe) 안내 (CAN-SPAM/이메일 기본 예의).
"""
from __future__ import annotations
import argparse
import html as _html
import json
import os
import threading
from datetime import datetime, timezone

import workradar

# 직업별 '이번 주 신호' 큐레이션 슬롯 — 실제 출처 링크. (라이브 뉴스 파이프라인 연결 전 editorial)
# 운영자가 매주 갱신하거나, 추후 crawler/scoring으로 자동 주입.
SIGNALS: dict[str, dict] = {
    "junior-developer": {"head": "Coding agents keep expanding into multi-file PRs",
        "why": "Pressure stays high on boilerplate & simple fixes — your judgment layer is the hedge.",
        "url": "https://www.anthropic.com/claude-code"},
    "video-editor": {"head": "Generative video tools add longer edit-ready clips",
        "why": "Rough-cut & b-roll pressure rises; sound design & direction stay your moat.",
        "url": "https://openai.com/sora"},
    "data-analyst": {"head": "BI copilots auto-generate dashboards & SQL",
        "why": "Reporting pressure up; causal framing for stakeholders stays human.",
        "url": "https://www.anthropic.com/claude"},
    "designer": {"head": "Image models ship faster production variants",
        "why": "Mockup/resizing pressure up; brand & art direction stay yours.",
        "url": "https://www.adobe.com/products/firefly.html"},
    "marketer": {"head": "AI ad-copy & scheduling tools go mainstream",
        "why": "Copy-variant pressure up; positioning & partnerships stay human.",
        "url": "https://www.anthropic.com/claude"},
    "support-agent": {"head": "AI agents resolve more tier-1 tickets end to end",
        "why": "FAQ/triage pressure high; escalation judgment & retention saves stay yours.",
        "url": "https://www.anthropic.com/claude"},
}

LANDING = "https://idsexyhomme-code.github.io/1000/web/en/"
PILOT_MAILTO = "mailto:idsexyhomme@gmail.com?subject=WorkRadar%20pilot"

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUTBOX_FILE = os.path.join(_DATA, "wr_outbox.jsonl")   # 발송 대기열 (이메일 PII) → .gitignore
_OUTBOX_LOCK = threading.Lock()


def _e(s) -> str:
    return _html.escape(str(s), quote=True)


def build_digest(sub: dict, now: datetime | None = None) -> dict | None:
    """구독자 1명의 주간 다이제스트 → {to, subject, html, text}. 직업 미상이면 None."""
    now = now or datetime.now(timezone.utc)
    job_id = sub.get("job", "")
    if job_id not in workradar.JOBS:
        return None
    email = sub.get("email", "")
    job = workradar.JOBS[job_id]
    branch_id = sub.get("branch", "")
    br = workradar.BRANCHES.get(branch_id)
    sig = SIGNALS.get(job_id, {})
    bd = workradar.band(job["base"])
    wk = now.strftime("%b %d")

    top_tasks = ", ".join(t[0] for t in job["hi"][:2])
    move = br["move"] if br else "Pick your lowest-pressure task and grow your time there this week."
    type_line = (br["em"] + " " + br["name"]) if br else "your path"

    subject = f"WorkRadar · {job['name']} AI pressure {job['base']} ({bd[0]}) — {wk}"
    html = (
        '<div style="max-width:480px;margin:0 auto;font-family:-apple-system,Segoe UI,Roboto,sans-serif;'
        'background:#0b0b0d;color:#fafafa;padding:24px;border-radius:16px">'
        f'<div style="font-size:13px;color:#a1a1aa">WorkRadar · weekly signal · {_e(wk)}</div>'
        f'<h1 style="font-size:22px;margin:10px 0 4px">{_e(job["name"])} · AI pressure '
        f'<span style="color:{bd[1]}">{job["base"]} ({_e(bd[0])})</span></h1>'
        f'<p style="font-size:14px;color:#a1a1aa;margin:0 0 18px">Highest pressure this week: '
        f'<b style="color:#fafafa">{_e(top_tasks)}</b></p>'
        '<div style="background:#18181b;border:1px solid #27272a;border-radius:12px;padding:16px;margin-bottom:14px">'
        f'<div style="font-size:11px;font-weight:700;color:#f59e0b;text-transform:uppercase;letter-spacing:.5px">This week\'s signal · curated</div>'
        f'<div style="font-size:15px;font-weight:700;margin:8px 0 4px">{_e(sig.get("head","Steady — no major new signal this week."))}</div>'
        f'<div style="font-size:13px;color:#a1a1aa">{_e(sig.get("why",""))}</div>'
        + (f'<a href="{_e(sig.get("url"))}" style="font-size:12px;color:#60a5fa">source &#8599;</a>' if sig.get("url") else "")
        + '</div>'
        '<div style="background:#18181b;border:1px solid #27272a;border-radius:12px;padding:16px;margin-bottom:14px">'
        f'<div style="font-size:11px;font-weight:700;color:#34d399;text-transform:uppercase">Your path · {_e(type_line)}</div>'
        f'<div style="font-size:14px;margin-top:8px">{_e(move)}</div></div>'
        f'<a href="{_e(PILOT_MAILTO)}" style="display:inline-block;background:#fafafa;color:#000;padding:12px 22px;'
        'border-radius:24px;text-decoration:none;font-weight:700;font-size:14px">Get my full roadmap · $29 pilot →</a>'
        '<p style="font-size:11px;color:#71717a;line-height:1.5;margin-top:20px">'
        'WorkRadar is a directional reference indicator from public AI news — not a prediction, not a verdict on any person or company. '
        f'<br>You get this because you asked for weekly updates. <a href="{_e(LANDING)}" style="color:#71717a">Manage / unsubscribe</a>.</p>'
        '</div>')
    text = (f"WorkRadar weekly · {wk}\n{job['name']} AI pressure {job['base']} ({bd[0]})\n"
            f"Highest pressure: {top_tasks}\n\nThis week's signal (curated): {sig.get('head','Steady this week.')}\n"
            f"{sig.get('why','')}\n{sig.get('url','')}\n\nYour path: {type_line}\n{move}\n\n"
            f"Full roadmap ($29 pilot): {PILOT_MAILTO}\n\n"
            "Directional reference, not a prediction. Reply STOP to unsubscribe.")
    return {"to": email, "subject": subject, "html": html, "text": text}


def run(now: datetime | None = None) -> dict:
    """전체 구독자 다이제스트 생성 → 발송 대기열 적재. 반환 요약."""
    os.makedirs(_DATA, exist_ok=True)
    subs = workradar.subscribers()
    queued = skipped = 0
    with _OUTBOX_LOCK:
        with open(OUTBOX_FILE, "a", encoding="utf-8") as f:
            for s in subs:
                d = build_digest(s, now=now)
                if not d or not d["to"]:
                    skipped += 1
                    continue
                rec = {"ts": (now or datetime.now(timezone.utc)).isoformat(),
                       "channel": "email", **d}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                queued += 1
    return {"subscribers": len(subs), "queued": queued, "skipped": skipped}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="WorkRadar 주간 다이제스트 생성")
    ap.add_argument("--sample", metavar="JOB", help="구독자 없이 직업 샘플 미리보기")
    args = ap.parse_args()
    if args.sample:
        d = build_digest({"email": "you@example.com", "job": args.sample, "branch": "pivot"})
        print(d["text"] if d else f"unknown job: {args.sample}")
    else:
        print(run())
