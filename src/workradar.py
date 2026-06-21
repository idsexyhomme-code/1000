"""WorkRadar US 백엔드 엔진 — "AI Risk Type 5갈래 코파일럿" (stdlib only, 의존성 0).

서버측 진실원본(source of truth): 프론트 퀴즈(web/en/index.html)의 분기 로직을 여기서 재현해
결과 계산 + 완료 로깅 + 주간리포트 구독(이메일 캡처)을 담당한다.

정직성(불가침):
- 점수는 calibrated:false 손추정 baseline → "directional reference indicator", 예측 아님.
- 이메일/연락처는 PII → data/*.jsonl 은 .gitignore. 동의(consent) 필수.
- "대체된다" 단정 금지 → 관측된 자동화 '압력/신호'.
"""
from __future__ import annotations
import json
import os
import re
import threading
from datetime import datetime, timezone

# ── 직업별 task 프로필 (프론트 JOBS와 일치 유지) ──────────────────────────────
# base = 직업 단위 AI 압력 참고지표(손추정). hi/lo = task별 [라벨, 점수].
JOBS: dict[str, dict] = {
    "junior-developer": {"name": "Junior Developer", "emoji": "💻", "base": 64,
        "hi": [["Boilerplate / CRUD", 84], ["Unit tests", 78], ["Simple bug fixes", 70]],
        "lo": [["System design", 30], ["Hard debugging", 26]]},
    "video-editor": {"name": "Video Editor", "emoji": "🎬", "base": 59,
        "hi": [["Auto-captioning", 82], ["Rough cuts", 77], ["Thumbnails", 74]],
        "lo": [["Sound & mixing", 48], ["On-set direction", 22]]},
    "data-analyst": {"name": "Data Analyst", "emoji": "📊", "base": 57,
        "hi": [["Dashboards", 80], ["SQL pulls", 75], ["Report formatting", 72]],
        "lo": [["Causal analysis", 38], ["Stakeholder framing", 28]]},
    "designer": {"name": "Designer", "emoji": "🎨", "base": 55,
        "hi": [["Production mockups", 78], ["Resizing/variants", 76], ["Stock-style art", 70]],
        "lo": [["Brand strategy", 34], ["Art direction", 26]]},
    "marketer": {"name": "Marketer", "emoji": "📣", "base": 58,
        "hi": [["Copy variants", 81], ["Scheduling", 74], ["Basic reporting", 71]],
        "lo": [["Positioning", 36], ["Partnerships", 27]]},
    "support-agent": {"name": "Support Agent", "emoji": "📞", "base": 70,
        "hi": [["FAQ replies", 86], ["Ticket triage", 79], ["Macros", 77]],
        "lo": [["Escalation judgment", 40], ["Retention saves", 30]]},
}

# ── 5갈래 = AI Risk Type = 커리어 의사결정 분기 ───────────────────────────────
BRANCHES: dict[str, dict] = {
    "defend": {"em": "🛡️", "name": "The Defender",
        "line": "You stay — and out-level the AI in your own role.",
        "move": "This week, take ONE repetitive task and let AI do the first pass — you own the final judgment call."},
    "pivot": {"em": "🔄", "name": "The Pivoter",
        "line": "Same field, but you slide to the work AI can't touch.",
        "move": "Pick your lowest-pressure task. Starting now, spend 20% more of your week there."},
    "reskill": {"em": "🧗", "name": "The Reskiller",
        "line": "You jump to an adjacent role with more runway.",
        "move": "List 3 roles that use ~50% of your current skills but face less AI pressure. That's your map."},
    "independent": {"em": "🦅", "name": "The Independent",
        "line": "You sell your strongest tasks directly, on your terms.",
        "move": "Name the ONE task people already come to you for. That's your first offer."},
    "founder": {"em": "🚀", "name": "The Founder",
        "line": "The thing that annoys you at work IS the business.",
        "move": "Write down the workflow that wastes the most time in your field. That friction is your seed."},
}

# 분기별 '이번 주 다음 수' — {top}=내가 가장 많이 하는 고압력 업무, {low}=가장 안전한 업무.
# 개인의 실제 업무 선택을 끼워넣어 사람마다 다른 처방을 만든다(가짜 아님, 입력 기반).
MOVE_TMPL: dict[str, str] = {
    "defend": "This week, take your most exposed task — {top} — and let AI do the first pass. You own the final call.",
    "pivot": "Your safest ground is {low}. Spend 20% more of your week there, and less on {top}.",
    "reskill": "You spend your week on {top}, which AI is coming for. List 3 adjacent roles that lean on {low}-style judgment instead.",
    "independent": "People already trust your {low}. Package that as your first solo offer.",
    "founder": "The {top} grind you repeat every week? That friction is a product — write it down.",
}

REP_RANGE = FEEL_RANGE = INST_RANGE = (0, 1, 2)


def _derive_rep(avg_selected: float) -> int:
    """선택한 업무들의 평균 압력 → 반복도(0~2) 추론. 고압력 업무 위주 = 반복많음."""
    return 2 if avg_selected >= 65 else 1 if avg_selected >= 45 else 0


def decide_branch(rep: int, feel: int, inst: int) -> str:
    """답변 3개 → 5갈래 결정 (프론트 decideBranch와 동일)."""
    if feel <= 1:
        return "pivot" if rep >= 1 else "defend"
    if inst == 2:
        return "founder"
    if inst == 1:
        return "independent"
    return "reskill"


def band(score: float) -> list:
    if score <= 25:
        return ["Clear", "#3b82f6"]
    if score <= 50:
        return ["Partly cloudy", "#8b5cf6"]
    if score <= 75:
        return ["Cloudy", "#f59e0b"]
    return ["Storm", "#e11d48"]


def _valid_answer(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v in (0, 1, 2)


def compute_result(job_id: str, tasks, feel: int, inst: int) -> dict:
    """개인화 결과 계산. tasks = 사용자가 '내 주를 차지하는 업무'로 고른 인덱스 리스트(1~3).
    점수 = 그 사람이 실제로 하는 업무들의 평균 압력 → 같은 직업이라도 사람마다 다름. 검증 실패 시 ValueError."""
    if job_id not in JOBS:
        raise ValueError("unknown job")
    if not all(_valid_answer(x) for x in (feel, inst)):
        raise ValueError("invalid answer")
    job = JOBS[job_id]
    full = job["hi"] + job["lo"]            # [[label, score], ...] (5개)
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("no tasks")
    idx: list[int] = []
    for t in tasks:
        if isinstance(t, bool) or not isinstance(t, int) or t < 0 or t >= len(full):
            raise ValueError("bad task")
        if t not in idx:
            idx.append(t)
    idx = idx[:3]
    sel = [full[i] for i in idx]
    avg_sel = sum(s[1] for s in sel) / len(sel)
    score = max(8, min(96, round(avg_sel)))
    rep = _derive_rep(avg_sel)
    branch_id = decide_branch(rep, feel, inst)
    br = BRANCHES[branch_id]
    top = max(sel, key=lambda s: s[1])[0]          # 본인이 고른 것 중 최고압력 = 가장 노출된 업무
    low = min(full, key=lambda s: s[1])[0]         # 직업 전체 최저압력 = 가장 안전한 레버
    move = MOVE_TMPL[branch_id].format(top=top, low=low)
    bd = band(score)
    return {
        "job_id": job_id, "job_name": job["name"], "emoji": job["emoji"],
        "branch_id": branch_id, "type_name": br["name"], "type_emoji": br["em"],
        "type_line": br["line"], "free_move": move,
        "score": score, "band": bd[0], "band_color": bd[1],
        "rep": rep, "top_task": top, "low_task": low,
        "selected": [[s[0], s[1]] for s in sel],
        "tasks": full, "selected_idx": idx,
    }


EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def valid_email(e: str) -> bool:
    e = (e or "").strip()
    return bool(e) and len(e) <= 254 and bool(EMAIL_RE.match(e))


# ── 저장 (파일 기반, store.py 패턴: 원자적 append + 중복제거) ─────────────────
_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
QUIZ_FILE = os.path.join(_DATA, "wr_quiz.jsonl")          # 완료 로그(분석용, PII 없음)
SUBS_FILE = os.path.join(_DATA, "wr_subscribers.jsonl")   # 이메일 구독 → PII, .gitignore 필수
_QUIZ_LOCK = threading.Lock()
_SUBS_LOCK = threading.Lock()


def _ensure() -> None:
    os.makedirs(_DATA, exist_ok=True)


def append_quiz_result(res: dict, iph: str = "") -> None:
    """완료 1건 적재 — 분석용. PII 없음(직업/분기/점수/답변만)."""
    _ensure()
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "job": res.get("job_id", ""), "branch": res.get("branch_id", ""),
        "score": res.get("score"), "iph": iph,
    }
    with _QUIZ_LOCK:
        with open(QUIZ_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _norm_email(e: str) -> str:
    return (e or "").strip().lower()


def append_subscriber(rec: dict) -> bool:
    """주간리포트 구독 1건 적재 (원자적 + 이메일 중복제거). 반환: 신규 여부.
    rec에 이메일(PII) 포함 → 절대 커밋 금지(.gitignore)."""
    _ensure()
    rec = dict(rec)
    rec.setdefault("ts", datetime.now(timezone.utc).isoformat())
    key = _norm_email(rec.get("email", ""))
    if not valid_email(key):
        return False
    with _SUBS_LOCK:
        if os.path.exists(SUBS_FILE):
            for ln in open(SUBS_FILE, encoding="utf-8"):
                if not ln.strip():
                    continue
                try:
                    p = json.loads(ln)
                except Exception:
                    continue
                if _norm_email(p.get("email", "")) == key:
                    return False
        with open(SUBS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True


def _count(path: str, lock: threading.Lock) -> int:
    if not os.path.exists(path):
        return 0
    n = 0
    with lock:
        for ln in open(path, encoding="utf-8"):
            if ln.strip():
                try:
                    json.loads(ln)
                    n += 1
                except Exception:
                    pass
    return n


def quiz_count() -> int:
    return _count(QUIZ_FILE, _QUIZ_LOCK)


def subscriber_count() -> int:
    return _count(SUBS_FILE, _SUBS_LOCK)


def quiz_stats() -> dict:
    """분기/직업별 완료 분포 — 어떤 후크·직업이 도는지 운영 지표."""
    by_branch: dict[str, int] = {}
    by_job: dict[str, int] = {}
    total = 0
    if os.path.exists(QUIZ_FILE):
        with _QUIZ_LOCK:
            for ln in open(QUIZ_FILE, encoding="utf-8"):
                if not ln.strip():
                    continue
                try:
                    p = json.loads(ln)
                except Exception:
                    continue
                total += 1
                by_branch[p.get("branch", "")] = by_branch.get(p.get("branch", ""), 0) + 1
                by_job[p.get("job", "")] = by_job.get(p.get("job", ""), 0) + 1
    return {"total": total, "by_branch": by_branch, "by_job": by_job}


def subscribers() -> list:
    """주간 엔진용 — 구독자 전체(이메일 포함). 호출측이 PII 취급 주의."""
    out = []
    if os.path.exists(SUBS_FILE):
        with _SUBS_LOCK:
            for ln in open(SUBS_FILE, encoding="utf-8"):
                if not ln.strip():
                    continue
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
    return out


if __name__ == "__main__":
    # 빠른 점검
    r = compute_result("junior-developer", 2, 0, 0)
    print(r["type_name"], r["score"], r["band"])
    print("quiz:", quiz_count(), "subs:", subscriber_count())
