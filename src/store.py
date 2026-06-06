"""
커리어 시그널 — 영속화 계층 (이벤트 스토어 + 점수로그 time series)

stdlib만 사용(의존성 0). 이벤트는 JSON 파일, 점수 스냅샷은 JSONL append.
점수로그가 곧 mean-reversion(이전 점수→baseline 회귀)과 '주식 호가창' 시계열의 기반 (R2.5).
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

_USERS_LOCK = threading.Lock()

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
EVENTS_DIR = os.path.join(_DATA, "events")
SCORES_DIR = os.path.join(_DATA, "scores")


def _ensure() -> None:
    os.makedirs(EVENTS_DIR, exist_ok=True)
    os.makedirs(SCORES_DIR, exist_ok=True)


# ── 이벤트 스토어 ─────────────────────────────────────────────────────
def save_event(ev: dict) -> str:
    """점수화 완료된 이벤트(dict)를 저장. event_id로 멱등."""
    _ensure()
    path = os.path.join(EVENTS_DIR, f"{ev['event_id']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    return path


AUDIT_LOG = os.path.join(_DATA, "overrides_audit.jsonl")


def save_override(ev: dict, operator: str, reason: str) -> str:
    """운영자 수동보정 이벤트 — 일반 Event와 구조적으로 분리(override=True) + 별도 감사로그(R2.5 ⑤).
    점수엔 반영되되 드라이버에 editorial_override 라벨로 노출돼 사후 감사 가능."""
    _ensure()
    ev = {**ev, "override": True, "status": "complete",
          "audit": {"operator": operator, "reason": reason}}
    path = save_event(ev)
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "event_id": ev["event_id"],
           "operator": operator, "reason": reason}
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def load_events() -> list[dict]:
    _ensure()
    out = []
    for fn in sorted(os.listdir(EVENTS_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(EVENTS_DIR, fn), encoding="utf-8") as f:
                out.append(json.load(f))
    return out


def event_exists(event_id: str) -> bool:
    return os.path.exists(os.path.join(EVENTS_DIR, f"{event_id}.json"))


def event_status(event_id: str) -> str | None:
    """저장된 이벤트의 status 반환(없으면 None).
    원자적 저장(Codex 리뷰 최우선): 'failed'는 재시도 대상, 'complete'/'irrelevant'는 처리완료."""
    path = os.path.join(EVENTS_DIR, f"{event_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("status")
    except Exception:
        return None


# ── 점수로그 (time series) ───────────────────────────────────────────
def append_score(job_id: str, snapshot: dict, ts: str | None = None) -> None:
    """직무별 점수 스냅샷을 시계열로 append. ts 미지정 시 현재 UTC."""
    _ensure()
    rec = {"ts": ts or datetime.now(timezone.utc).isoformat(), **snapshot}
    with open(os.path.join(SCORES_DIR, f"{job_id}.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def score_history(job_id: str, limit: int | None = None) -> list[dict]:
    path = os.path.join(SCORES_DIR, f"{job_id}.jsonl")
    if not os.path.exists(path):
        return []
    rows = [json.loads(ln) for ln in open(path, encoding="utf-8") if ln.strip()]
    return rows[-limit:] if limit else rows


def latest_score(job_id: str) -> dict | None:
    h = score_history(job_id, limit=1)
    return h[0] if h else None


def delta_since_prev(job_id: str, current_index: float) -> float | None:
    """직전 스냅샷 대비 변화량 — 푸시 알림 '+N' 표기용."""
    prev = latest_score(job_id)
    if not prev or "index" not in prev:
        return None
    return round(current_index - prev["index"], 1)


# ── 사용자-직업 매핑 (봇 서버용) ──────────────────────────────────────
USERS_FILE = os.path.join(_DATA, "users.json")  # 런타임/개인정보 → .gitignore


def _load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def set_user_job(user_id: str, job_id: str) -> None:
    """동시쓰기 안전(락 + temp→os.replace 원자적 저장), user_id 길이 제한."""
    _ensure()
    user_id = str(user_id)[:128]
    with _USERS_LOCK:
        users = _load_users()
        users[user_id] = {"job_id": job_id}
        tmp = USERS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        os.replace(tmp, USERS_FILE)  # 원자적 교체 — 읽는 중 파일 날아감 방지


def get_user_job(user_id: str) -> str | None:
    return _load_users().get(user_id, {}).get("job_id")
