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
_STATE_LOCK = threading.Lock()  # strategist/notified 등 소형 상태파일용 (users와 분리)

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


ARCHIVE_DIR = os.path.join(_DATA, "events_archive")


def archive_event(event_id: str) -> bool:
    """감쇠 소멸 이벤트를 아카이브로 이동(점수 재계산 입력에서 제외, 기록은 보존)."""
    src = os.path.join(EVENTS_DIR, f"{event_id}.json")
    if not os.path.exists(src):
        return False
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.replace(src, os.path.join(ARCHIVE_DIR, f"{event_id}.json"))
    return True


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


def users_by_job(job_id: str) -> list[str]:
    """해당 직무를 구독한 사용자 ID 목록 (배치 푸시 대상)."""
    return [uid for uid, v in _load_users().items() if v.get("job_id") == job_id]


# ── 발송 큐 (카카오 API 발송 전 단계) + 전략가타입 캐시 ────────────────
OUTBOX_FILE = os.path.join(_DATA, "outbox.jsonl")        # 런타임 → .gitignore
STRATEGIST_FILE = os.path.join(_DATA, "strategist_cache.json")
ACTIONPLAN_FILE = os.path.join(_DATA, "actionplan_cache.json")


def append_outbox(user_id: str, text: str, job_id: str, ts: str | None = None) -> None:
    _ensure()
    rec = {"ts": ts or datetime.now(timezone.utc).isoformat(), "user_id": user_id,
           "job_id": job_id, "text": text, "status": "queued"}
    with open(OUTBOX_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_outbox() -> list[dict]:
    if not os.path.exists(OUTBOX_FILE):
        return []
    return [json.loads(ln) for ln in open(OUTBOX_FILE, encoding="utf-8") if ln.strip()]


def update_outbox(rows: list[dict]) -> None:
    """outbox 전체를 갱신된 상태로 원자적 재기록 (sent-marker/재시도 후)."""
    _ensure()
    with _STATE_LOCK:
        tmp = OUTBOX_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, OUTBOX_FILE)


# ── 사전예약/결제의사 수집 (지불주체 검증 = 30일 스모크 테스트) ────────
INTEREST_FILE = os.path.join(_DATA, "interest.jsonl")   # 연락처 포함 → .gitignore 필수
_INTEREST_LOCK = threading.Lock()


def _norm_contact(c: str) -> str:
    return (c or "").strip().lower()


def append_interest(rec: dict) -> bool:
    """사전예약 리드 1건 적재 (원자적 append + (contact,job) 중복제거).
    rec엔 PII(연락처) 포함 → 절대 커밋 금지(.gitignore). 반환: 신규 적재 여부(중복이면 False)."""
    _ensure()
    rec = dict(rec)
    rec.setdefault("ts", datetime.now(timezone.utc).isoformat())
    key = (_norm_contact(rec.get("contact", "")), rec.get("job", ""))
    with _INTEREST_LOCK:
        if os.path.exists(INTEREST_FILE):
            for ln in open(INTEREST_FILE, encoding="utf-8"):
                if not ln.strip():
                    continue
                try:
                    p = json.loads(ln)
                except Exception:
                    continue
                if (_norm_contact(p.get("contact", "")), p.get("job", "")) == key:
                    return False        # 같은 연락처+직무 중복 → 지표 오염 방지
        with open(INTEREST_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True


def interest_count() -> int:
    """수집된 사전예약 건수 (30일 지불주체 테스트 측정 지표)."""
    if not os.path.exists(INTEREST_FILE):
        return 0
    with _INTEREST_LOCK:
        return sum(1 for ln in open(INTEREST_FILE, encoding="utf-8") if ln.strip())


NOTIFIED_FILE = os.path.join(_DATA, "notified.json")  # 직무별 마지막 알림 스냅샷 ts (중복 알림 방지)


def _save_state(path: str, key: str, val) -> None:
    _ensure()
    with _STATE_LOCK:
        data = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[key] = val
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def _get_state(path: str, key: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get(key)
    except Exception:
        return None


def save_strategist(job_id: str, obj: dict) -> None:
    """전략가타입 캐시 — /report가 요청마다 Gemini 호출하지 않도록 배치에서 미리 저장."""
    _save_state(STRATEGIST_FILE, job_id, obj)


def get_strategist(job_id: str) -> dict | None:
    return _get_state(STRATEGIST_FILE, job_id)


def save_actionplan(job_id: str, plan: dict) -> None:
    """배치가 생성한 Gemini 액션플랜 캐시 — /report가 요청마다 호출 없이 premium 플랜 사용."""
    _save_state(ACTIONPLAN_FILE, job_id, plan)


def get_actionplan(job_id: str) -> dict | None:
    return _get_state(ACTIONPLAN_FILE, job_id)


def get_notified(job_id: str):
    """이 직무로 마지막에 알림 보낸 스냅샷 ts. 같은 ts면 재알림 금지(중복 스팸 방지)."""
    return _get_state(NOTIFIED_FILE, job_id)


def set_notified(job_id: str, snap_ts) -> None:
    _save_state(NOTIFIED_FILE, job_id, snap_ts)
