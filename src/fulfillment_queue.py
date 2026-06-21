"""
커리어 시그널 — pain 파일럿 이행 작업 큐.

pain intent는 "문제 신호"이고, fulfillment job은 "운영자가 납품해야 할 일감"이다.
이 모듈은 저장된 pain intent를 작업 큐로 가져오고 상태를 추적한다.

사용:
    python3 src/fulfillment_queue.py import
    python3 src/fulfillment_queue.py list
    python3 src/fulfillment_queue.py next
    python3 src/fulfillment_queue.py memo
    python3 src/fulfillment_queue.py weekly
    python3 src/fulfillment_queue.py productize
    python3 src/fulfillment_queue.py productize-preview
    python3 src/fulfillment_queue.py reconcile-paid
    python3 src/fulfillment_queue.py repair-paid ORDER_ID
    python3 src/fulfillment_queue.py checkpoint ORDER_ID kickoff_sent
    python3 src/fulfillment_queue.py render fq_ab12cd34ef56
    python3 src/fulfillment_queue.py status fq_ab12cd34ef56 working --note "자료 확인 중"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, time, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fulfillment  # noqa: E402
import painmap  # noqa: E402
import pain_probe  # noqa: E402
import report  # noqa: E402
import store  # noqa: E402
from scoring import ScoringEngine  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JOBS_DIR = os.path.join(_ROOT, "data", "jobs")

STATUSES = {"queued", "working", "delivered", "blocked", "canceled"}
DELIVERY_SLA_BUSINESS_DAYS = 3
OPEN_STATUSES = {"queued", "working", "blocked"}
CHECKPOINTS = ("kickoff_sent", "materials_received", "draft_ready", "final_delivered")
CHECKPOINT_LABELS = {
    "kickoff_sent": "kickoff 발송",
    "materials_received": "자료 수신",
    "draft_ready": "초안 준비",
    "final_delivered": "최종 전달",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def add_business_days(ts: str, days: int = DELIVERY_SLA_BUSINESS_DAYS) -> str:
    """UTC 기준 영업일 SLA due_at 생성. 주말만 제외하고 공휴일은 수동 운영에서 보정한다."""
    start = _parse_ts(ts) or datetime.now(timezone.utc)
    cur = datetime.combine(start.date(), time(18, 0), tzinfo=timezone.utc)
    added = 0
    while added < max(0, int(days)):
        cur = cur + timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur.isoformat()


def is_overdue(row: dict, *, now: str | None = None) -> bool:
    if row.get("status") not in OPEN_STATUSES:
        return False
    due = _parse_ts(row.get("due_at", ""))
    ref = _parse_ts(now or _now())
    return bool(due and ref and due < ref)


def _norm_contact(contact: str) -> str:
    return (contact or "").strip().lower()


def _mask_contact(contact: str) -> str:
    c = (contact or "").strip()
    if not c:
        return "미기재"
    if "@" in c:
        local, _, dom = c.partition("@")
        return f"{local[:2]}***@{dom}" if local else f"***@{dom}"
    return f"{c[:2]}***" if len(c) > 2 else "***"


def _micro_itches(row: dict) -> list[str]:
    raw = row.get("micro_itches", row.get("micro_itches_ko", []))
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        s = str(item or "").replace("\r", " ").replace("\n", " ").strip()
        if s and s not in out:
            out.append(s)
    return out[:6]


def _micro_summary(row: dict) -> str:
    itches = _micro_itches(row)
    if not itches:
        return "-"
    first = itches[0]
    return first[:34] + ("..." if len(first) > 34 else "")


def _micro_key(row: dict, itch: str) -> str:
    job = row.get("job", "") or "(unknown)"
    return f"{job}::{itch}"


def _checkpoint_data(row: dict | None) -> dict:
    if not row:
        return {}
    raw = row.get("checkpoints", {})
    return raw if isinstance(raw, dict) else {}


def checkpoint_status(row: dict | None) -> dict:
    """paid pain 이행 체크포인트 진행률을 반환한다."""
    if not row:
        return {
            "done": [],
            "done_count": 0,
            "total": len(CHECKPOINTS),
            "next_checkpoint": "missing_queue",
            "next_label": "큐 없음",
            "summary": f"0/{len(CHECKPOINTS)} 큐 없음",
        }
    data = _checkpoint_data(row)
    done = []
    for key in CHECKPOINTS:
        item = data.get(key)
        if isinstance(item, dict) and item.get("ts"):
            done.append(key)
    next_checkpoint = next((key for key in CHECKPOINTS if key not in done), "")
    next_label = CHECKPOINT_LABELS.get(next_checkpoint, "완료")
    return {
        "done": done,
        "done_count": len(done),
        "total": len(CHECKPOINTS),
        "next_checkpoint": next_checkpoint,
        "next_label": next_label,
        "summary": f"{len(done)}/{len(CHECKPOINTS)} {next_label}",
    }


def _micro_action_rows(rows: list[dict], limit: int = 5) -> list[dict]:
    counts: Counter[tuple[str, str]] = Counter()
    for row in rows:
        job = str(row.get("job", "") or "")
        for itch in _micro_itches(row):
            counts[(job, itch)] += 1
    out = []
    for (job, itch), count in counts.most_common(max(0, int(limit))):
        adjustment = pain_probe.artifact_adjustment(job, [itch])
        adj_rows = adjustment.get("adjustment_rows", [])
        hint = adj_rows[0] if adj_rows else {}
        focus = pain_probe.fulfillment_focus(job, [itch])
        questions = focus.get("followup_questions_ko", [])
        out.append({
            "job": job,
            "micro_itch_ko": itch,
            "count": count,
            "artifact_slot_ko": hint.get("artifact_slot_ko", ""),
            "template_fields_ko": hint.get("template_fields_ko", ""),
            "qa_check_ko": hint.get("qa_check_ko", ""),
            "first_question_ko": questions[0] if questions else "",
        })
    return out


def fulfillment_id(row: dict) -> str:
    """intent row에서 안정적인 queue id 생성.

    큐 파일 자체가 PII 파일이라 .gitignore로 보호된다. id는 운영 편의를 위한 축약값이며,
    원본 연락처를 출력하지 않는다.
    """
    raw = "|".join([
        _norm_contact(str(row.get("contact", ""))),
        str(row.get("job", "")),
        str(row.get("pain_id", "")),
    ])
    return "fq_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def paid_release_id(order_id: str) -> str:
    raw = str(order_id or "").strip()
    if not raw:
        raise ValueError("order_id required")
    return "fq_pay_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def read_jobs(path: str | None = None) -> list[dict]:
    path = path or store.FULFILLMENT_FILE
    if not os.path.exists(path):
        return []
    out = []
    for ln in open(path, encoding="utf-8"):
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def _write_jobs(rows: list[dict], path: str | None = None) -> None:
    path = path or store.FULFILLMENT_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _job_from_intent(row: dict) -> dict:
    # build_from_intent로 job/pain 유효성을 먼저 검증한다.
    fulfillment.build_from_intent(row)
    now = _now()
    due_at = add_business_days(now)
    return {
        "fulfillment_id": fulfillment_id(row),
        "created_at": now,
        "due_at": due_at,
        "sla_business_days": DELIVERY_SLA_BUSINESS_DAYS,
        "status": "queued",
        "status_ts": now,
        "intent_ts": row.get("ts", ""),
        "contact": row.get("contact", ""),
        "job": row.get("job", ""),
        "pain_id": row.get("pain_id", ""),
        "role_type": row.get("role_type", ""),
        "sample_available": row.get("sample_available", ""),
        "situation": row.get("situation", ""),
        "micro_itches": _micro_itches(row),
        "offer_type": row.get("offer_type", "pain-intake"),
        "notes": "",
        "history": [{"ts": now, "status": "queued", "note": "imported from pain intent"}],
    }


def enqueue_paid_release(
    *,
    order_id: str,
    job_id: str,
    pain_id: str,
    amount=None,
    contact: str = "",
    micro_itches=None,
    queue_path: str | None = None,
) -> dict:
    """서명검증된 pain-paid 주문을 이행 큐에 연결한다.

    id는 order_id 기반이라 PG 웹훅 재전송에도 중복 생성되지 않는다.
    """
    fulfillment.build_from_ids(
        job_id,
        pain_id,
        contact=contact,
        role_type="paid-release",
        sample_available="unknown",
        situation=f"paid pain release order {order_id}",
        micro_itches=micro_itches or [],
    )
    fid = paid_release_id(order_id)
    existing = read_jobs(queue_path)
    for row in existing:
        if row.get("fulfillment_id") == fid or row.get("payment_order_id") == order_id:
            return row
    now = _now()
    job = {
        "fulfillment_id": fid,
        "created_at": now,
        "due_at": add_business_days(now),
        "sla_business_days": DELIVERY_SLA_BUSINESS_DAYS,
        "status": "queued",
        "status_ts": now,
        "intent_ts": "",
        "payment_order_id": str(order_id)[:80],
        "payment_amount": amount,
        "contact": contact,
        "job": job_id,
        "pain_id": pain_id,
        "role_type": "paid-release",
        "sample_available": "unknown",
        "situation": f"paid pain release order {order_id}",
        "micro_itches": _micro_itches({"micro_itches": micro_itches or []}),
        "offer_type": "pain-paid",
        "notes": "created from signed payment webhook",
        "history": [{"ts": now, "status": "queued", "note": "created from signed payment webhook"}],
    }
    _write_jobs(existing + [job], queue_path)
    return job


def save_paid_release_kickoff(
    *,
    order_id: str,
    job_id: str,
    pain_id: str,
    contact: str = "",
    micro_itches=None,
    report_dir: str | None = None,
    out_path: str | None = None,
) -> str:
    directory = report_dir or store.FULFILLMENT_REPORT_DIR
    filename = f"kickoff-{_slug(order_id)}.md"
    path = out_path or os.path.join(directory, filename)
    os.makedirs(os.path.dirname(path) or directory, exist_ok=True)
    text = fulfillment.kickoff_from_ids(
        job_id,
        pain_id,
        contact=contact,
        role_type="paid-release",
        sample_available="unknown",
        situation=f"paid pain release order {order_id}",
        micro_itches=micro_itches or [],
    )
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")
    os.replace(tmp, path)
    return path


def _is_paid_pain_payment(row: dict) -> bool:
    return row.get("status") == "paid" and (
        row.get("pain_release_job")
        or row.get("pain_release_pain")
        or str(row.get("fulfillment_id", "")).startswith("fq_pay_")
        or row.get("offer_type") == "pain-paid"
    )


def _paid_pain_payments() -> list[dict]:
    return [row for row in store.payment_records() if _is_paid_pain_payment(row)]


def paid_reconciliation(*, queue_path: str | None = None, now: str | None = None) -> dict:
    """서명검증 paid pain 주문과 fulfillment queue/kickoff 파일을 대조한다."""
    payments = _paid_pain_payments()
    jobs = read_jobs(queue_path)
    by_order = {str(row.get("payment_order_id", "")): row for row in jobs if row.get("payment_order_id")}
    by_id = {str(row.get("fulfillment_id", "")): row for row in jobs if row.get("fulfillment_id")}
    rows = []
    for pay in payments:
        order_id = str(pay.get("order_id", ""))
        pay_fid = str(pay.get("fulfillment_id", ""))
        job = by_order.get(order_id) or by_id.get(pay_fid)
        issues = []
        if not job:
            issues.append("missing_queue")
        else:
            if pay_fid and job.get("fulfillment_id") != pay_fid:
                issues.append("fulfillment_id_mismatch")
            if job.get("payment_order_id") and job.get("payment_order_id") != order_id:
                issues.append("order_id_mismatch")
            if is_overdue(job, now=now):
                issues.append("overdue")
        kickoff_path = str(pay.get("kickoff_path", ""))
        if not kickoff_path and order_id:
            kickoff_path = os.path.join(store.FULFILLMENT_REPORT_DIR, f"kickoff-{_slug(order_id)}.md")
        kickoff_exists = bool(kickoff_path and os.path.exists(kickoff_path))
        if not kickoff_exists:
            issues.append("missing_kickoff")
        checkpoint = checkpoint_status(job)
        rows.append({
            "order_id": order_id,
            "amount": pay.get("amount"),
            "payment_job": pay.get("job", ""),
            "pain_release_job": pay.get("pain_release_job", ""),
            "pain_release_pain": pay.get("pain_release_pain", ""),
            "payment_fulfillment_id": pay_fid,
            "queue_fulfillment_id": job.get("fulfillment_id", "") if job else "",
            "queue_status": job.get("status", "") if job else "",
            "queue_due_at": job.get("due_at", "") if job else "",
            "kickoff_path": kickoff_path,
            "kickoff_exists": kickoff_exists,
            "checkpoint_summary": checkpoint["summary"],
            "checkpoint_done_count": checkpoint["done_count"],
            "checkpoint_total": checkpoint["total"],
            "next_checkpoint": checkpoint["next_checkpoint"],
            "next_checkpoint_label": checkpoint["next_label"],
            "issues": issues,
        })
    issue_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    for row in rows:
        issue_counts.update(row["issues"])
        status_counts[row.get("queue_status") or "missing"] += 1
    return {
        "paid_pain_orders": len(rows),
        "ok": sum(1 for row in rows if not row["issues"]),
        "issue_counts": dict(issue_counts),
        "queue_status_counts": dict(status_counts),
        "rows": rows,
    }


def paid_reconciliation_markdown(*, queue_path: str | None = None, now: str | None = None) -> str:
    rep = paid_reconciliation(queue_path=queue_path, now=now)
    parts = [
        "# paid pain 주문 이행 대조",
        "",
        f"- paid pain orders: {rep['paid_pain_orders']}",
        f"- ok: {rep['ok']}",
        "",
    ]
    if rep["issue_counts"]:
        parts.extend(["## 이슈", ""])
        parts.extend(f"- {k}: {v}" for k, v in rep["issue_counts"].items())
        parts.append("")
    if rep["queue_status_counts"]:
        parts.extend(["## 큐 상태", ""])
        parts.extend(f"- {k}: {v}" for k, v in rep["queue_status_counts"].items())
        parts.append("")
    parts.extend([
        "## 주문별 대조",
        "",
        "| order_id | amount | release | queue | due | kickoff | checkpoint | issues |",
        "|---|---:|---|---|---|---|---|---|",
    ])
    if not rep["rows"]:
        parts.append("| - | 0 | - | - | - | - | - | paid pain 주문 없음 |")
    for row in rep["rows"]:
        release = f"{row.get('pain_release_job') or row.get('payment_job')}/{row.get('pain_release_pain') or '-'}"
        queue = f"{row.get('queue_fulfillment_id') or '-'} {row.get('queue_status') or 'missing'}"
        due = str(row.get("queue_due_at", ""))[:10] or "-"
        kickoff = "ok" if row.get("kickoff_exists") else "missing"
        issues = ", ".join(row.get("issues") or []) or "ok"
        parts.append(
            f"| {_md(row.get('order_id', ''))} | {row.get('amount') or 0} | {_md(release)} | {_md(queue)} | {_md(due)} | {kickoff} | {_md(row.get('checkpoint_summary', ''))} | {_md(issues)} |"
        )
    return "\n".join(parts).rstrip() + "\n"


def print_paid_reconciliation(*, queue_path: str | None = None, now: str | None = None) -> None:
    print(paid_reconciliation_markdown(queue_path=queue_path, now=now).rstrip())


def _paid_reconciliation_row(order_id: str, *, queue_path: str | None = None, now: str | None = None) -> dict:
    for row in paid_reconciliation(queue_path=queue_path, now=now).get("rows", []):
        if row.get("order_id") == order_id:
            return row
    return {}


def repair_paid_release_order(
    order_id: str,
    *,
    queue_path: str | None = None,
    dry_run: bool = False,
    now: str | None = None,
) -> dict:
    """paid pain 주문의 큐 작업/kickoff를 payment record 기준으로 멱등 복구한다."""
    oid = str(order_id or "").strip()
    if not oid:
        raise ValueError("order_id required")
    pay = next((row for row in _paid_pain_payments() if row.get("order_id") == oid), None)
    if not pay:
        raise ValueError(f"paid pain order not found: {oid}")
    job_id = str(pay.get("pain_release_job") or pay.get("job") or "").strip()
    pain_id = str(pay.get("pain_release_pain") or "").strip()
    if not job_id or not pain_id:
        raise ValueError(f"paid pain release metadata missing: {oid}")
    before = _paid_reconciliation_row(oid, queue_path=queue_path, now=now)
    before_issues = list(before.get("issues") or [])
    micro_itches = _micro_itches(pay) or productized_micro_itches(job_id, limit=2)
    kickoff_path = str(pay.get("kickoff_path", "")).strip()
    if not kickoff_path:
        kickoff_path = os.path.join(store.FULFILLMENT_REPORT_DIR, f"kickoff-{_slug(oid)}.md")
    fid = paid_release_id(oid)
    if not dry_run:
        job = enqueue_paid_release(
            order_id=oid,
            job_id=job_id,
            pain_id=pain_id,
            amount=pay.get("amount"),
            contact=str(pay.get("contact", "")),
            micro_itches=micro_itches,
            queue_path=queue_path,
        )
        kickoff_path = save_paid_release_kickoff(
            order_id=oid,
            job_id=job_id,
            pain_id=pain_id,
            contact=str(pay.get("contact", "")),
            micro_itches=micro_itches,
            out_path=kickoff_path,
        )
        fid = job.get("fulfillment_id") or fid
        store.save_payment(oid, job_id, pay.get("amount"), "paid", extra={
            "src": "repair-paid",
            "pain_release_job": job_id,
            "pain_release_pain": pain_id,
            "fulfillment_id": fid,
            "kickoff_path": kickoff_path,
        })
    after = _paid_reconciliation_row(oid, queue_path=queue_path, now=now)
    return {
        "order_id": oid,
        "dry_run": dry_run,
        "job": job_id,
        "pain_id": pain_id,
        "fulfillment_id": fid,
        "kickoff_path": kickoff_path,
        "before_issues": before_issues,
        "after_issues": list(after.get("issues") or []),
    }


def repair_paid_releases(
    order_ids: list[str] | None = None,
    *,
    all_issues: bool = False,
    queue_path: str | None = None,
    dry_run: bool = False,
    now: str | None = None,
) -> list[dict]:
    ids = [str(x or "").strip() for x in (order_ids or []) if str(x or "").strip()]
    if all_issues:
        ids.extend(
            str(row.get("order_id", ""))
            for row in paid_reconciliation(queue_path=queue_path, now=now).get("rows", [])
            if row.get("issues")
        )
    seen = set()
    unique_ids = []
    for oid in ids:
        if oid and oid not in seen:
            unique_ids.append(oid)
            seen.add(oid)
    if not unique_ids:
        raise ValueError("order_id required or use --all")
    return [
        repair_paid_release_order(oid, queue_path=queue_path, dry_run=dry_run, now=now)
        for oid in unique_ids
    ]


def import_intents(
    *,
    intent_path: str | None = None,
    queue_path: str | None = None,
    limit: int = 0,
) -> list[dict]:
    """pain intent를 fulfillment queue에 가져온다. 기존 id는 중복 생성하지 않는다."""
    existing = read_jobs(queue_path)
    seen = {r.get("fulfillment_id") for r in existing}
    new_jobs = []
    for row in fulfillment.intent_rows(intent_path):
        if limit and len(new_jobs) >= limit:
            break
        try:
            job = _job_from_intent(row)
        except ValueError:
            continue
        if job["fulfillment_id"] in seen:
            continue
        new_jobs.append(job)
        seen.add(job["fulfillment_id"])
    if new_jobs:
        _write_jobs(existing + new_jobs, queue_path)
    return new_jobs


def set_status(
    fulfillment_id_: str,
    status: str,
    *,
    note: str = "",
    queue_path: str | None = None,
) -> dict:
    status = str(status or "").strip()
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status}")
    rows = read_jobs(queue_path)
    for row in rows:
        if row.get("fulfillment_id") == fulfillment_id_:
            row["status"] = status
            row["status_ts"] = _now()
            row.setdefault("history", []).append({"ts": row["status_ts"], "status": status, "note": note})
            if note:
                row["notes"] = note
            _write_jobs(rows, queue_path)
            return row
    raise ValueError(f"unknown fulfillment_id: {fulfillment_id_}")


def set_checkpoint(
    identifier: str,
    checkpoint: str,
    *,
    note: str = "",
    ts: str | None = None,
    queue_path: str | None = None,
) -> dict:
    """fulfillment_id 또는 payment order_id로 이행 체크포인트를 기록한다."""
    ident = str(identifier or "").strip()
    checkpoint = str(checkpoint or "").strip()
    if not ident:
        raise ValueError("fulfillment_id or order_id required")
    if checkpoint not in CHECKPOINTS:
        raise ValueError(f"invalid checkpoint: {checkpoint}")
    ref = ts or _now()
    if not _parse_ts(ref):
        raise ValueError(f"invalid timestamp: {ref}")
    rows = read_jobs(queue_path)
    for row in rows:
        if row.get("fulfillment_id") == ident or row.get("payment_order_id") == ident:
            item = {"ts": ref, "note": str(note or "")[:200]}
            if not isinstance(row.get("checkpoints"), dict):
                row["checkpoints"] = {}
            row["checkpoints"][checkpoint] = item
            if checkpoint == "final_delivered":
                row["status"] = "delivered"
                row["status_ts"] = ref
            row.setdefault("history", []).append({
                "ts": ref,
                "status": row.get("status", ""),
                "checkpoint": checkpoint,
                "note": note,
            })
            _write_jobs(rows, queue_path)
            return row
    raise ValueError(f"unknown fulfillment_id or order_id: {ident}")


def next_job(*, queue_path: str | None = None) -> dict | None:
    queued = [row for row in read_jobs(queue_path) if row.get("status") == "queued"]
    if not queued:
        return None
    return sorted(queued, key=lambda r: (_due_sort_key(r), r.get("created_at", "")))[0]


def render_job(fulfillment_id_: str, *, queue_path: str | None = None) -> str:
    for row in read_jobs(queue_path):
        if row.get("fulfillment_id") == fulfillment_id_:
            return fulfillment.build_from_intent(row)
    raise ValueError(f"unknown fulfillment_id: {fulfillment_id_}")


def _due_sort_key(row: dict) -> str:
    return str(row.get("due_at", "")) or "9999-12-31T23:59:59+00:00"


def _md(value: str) -> str:
    return str(value or "").replace("|", "/").replace("\r", " ").replace("\n", " ").strip()


def _summary_rows(rows: list[dict]) -> list[str]:
    lines = []
    for row in rows:
        situation = str(row.get("situation", "")).replace("\n", " ")[:48]
        due = str(row.get("due_at", ""))[:10] or "-"
        flag = "OVERDUE" if is_overdue(row) else ""
        lines.append(
            f"{row.get('fulfillment_id',''):<15} {row.get('status',''):<9} {due:<10} {flag:<7} "
            f"{row.get('job',''):<18} {row.get('pain_id',''):<24} "
            f"{_mask_contact(row.get('contact','')):<18} {_micro_summary(row):<37} {situation}"
        )
    return lines


def _default_report_path(ref: datetime) -> str:
    return os.path.join(store.FULFILLMENT_REPORT_DIR, f"{ref.date().isoformat()}.md")


def _default_productization_path(ref: datetime) -> str:
    return os.path.join(store.FULFILLMENT_REPORT_DIR, f"productization-{ref.date().isoformat()}.md")


def _default_preview_dir(ref: datetime) -> str:
    return os.path.join(store.FULFILLMENT_REPORT_DIR, f"productization-preview-{ref.date().isoformat()}")


def operational_report(*, queue_path: str | None = None, now: str | None = None, limit: int = 5) -> dict:
    rows = read_jobs(queue_path)
    ref = _parse_ts(now or _now()) or datetime.now(timezone.utc)
    open_rows = [r for r in rows if r.get("status") in OPEN_STATUSES]
    overdue_rows = [r for r in open_rows if is_overdue(r, now=ref.isoformat())]
    due_today = []
    for row in open_rows:
        due = _parse_ts(row.get("due_at", ""))
        if due and due.date() == ref.date() and not is_overdue(row, now=ref.isoformat()):
            due_today.append(row)
    by_job = Counter(r.get("job", "") or "(unknown)" for r in open_rows)
    by_pain = Counter(f"{r.get('job','')}/{r.get('pain_id','')}" for r in open_rows)
    by_micro_itch: Counter[str] = Counter()
    for row in open_rows:
        for itch in _micro_itches(row):
            by_micro_itch[_micro_key(row, itch)] += 1
    next_rows = sorted(open_rows, key=lambda r: (is_overdue(r, now=ref.isoformat()) is False, _due_sort_key(r), r.get("created_at", "")))
    return {
        "total": len(rows),
        "open": len(open_rows),
        "overdue": len(overdue_rows),
        "due_today": len(due_today),
        "status_counts": dict(sorted(Counter(r.get("status", "?") for r in rows).items())),
        "by_job": dict(by_job.most_common(10)),
        "by_pain": dict(by_pain.most_common(10)),
        "by_micro_itch": dict(by_micro_itch.most_common(10)),
        "micro_actions": _micro_action_rows(open_rows, limit=5),
        "next": next_rows[:max(0, int(limit))],
        "paid_reconciliation": paid_reconciliation(queue_path=queue_path, now=ref.isoformat()),
    }


def report_markdown(*, queue_path: str | None = None, now: str | None = None, limit: int = 5) -> str:
    ref = _parse_ts(now or _now()) or datetime.now(timezone.utc)
    rep = operational_report(queue_path=queue_path, now=ref.isoformat(), limit=limit)
    paid = rep.get("paid_reconciliation") or {}
    paid_issues = sum((paid.get("issue_counts") or {}).values())
    parts = [
        f"# pain 파일럿 운영 메모 - {ref.date().isoformat()}",
        "",
        f"- 생성시각: {ref.isoformat()}",
        f"- total/open/overdue/due_today: {rep['total']} / {rep['open']} / {rep['overdue']} / {rep['due_today']}",
        f"- paid pain orders/ok/issues: {paid.get('paid_pain_orders', 0)} / {paid.get('ok', 0)} / {paid_issues}",
        "- 주의: 이 파일은 큐 상황과 신청 상황 요약을 포함할 수 있는 운영 메모입니다. 외부공유·커밋 금지.",
        "",
    ]
    if rep["status_counts"]:
        parts.extend(["## 상태", ""])
        parts.extend(f"- {k}: {v}" for k, v in rep["status_counts"].items())
        parts.append("")
    if rep["by_job"]:
        parts.extend(["## 직무별 open", ""])
        parts.extend(f"- {job}: {n}" for job, n in rep["by_job"].items())
        parts.append("")
    if rep["by_pain"]:
        parts.extend(["## pain별 open", ""])
        parts.extend(f"- {pain}: {n}" for pain, n in rep["by_pain"].items())
        parts.append("")
    if rep["by_micro_itch"]:
        parts.extend(["## micro-itch별 open", ""])
        parts.extend(f"- {itch}: {n}" for itch, n in rep["by_micro_itch"].items())
        parts.append("")
    if rep["micro_actions"]:
        parts.extend([
            "## 다음 운영 액션",
            "",
            "| count | job | micro-itch | 산출물 위치 | 필수 칸 | 첫 확인 질문 |",
            "|---:|---|---|---|---|---|",
        ])
        for row in rep["micro_actions"]:
            parts.append(
                "| {count} | {job} | {itch} | {slot} | {fields} | {question} |".format(
                    count=row.get("count", 0),
                    job=_md(row.get("job", "")),
                    itch=_md(row.get("micro_itch_ko", "")),
                    slot=_md(row.get("artifact_slot_ko", "")),
                    fields=_md(row.get("template_fields_ko", "")),
                    question=_md(row.get("first_question_ko", "")),
                )
            )
        parts.append("")
    if paid.get("paid_pain_orders"):
        parts.extend([
            "## paid pain 이행 대조",
            "",
            "| order_id | release | queue | due | kickoff | checkpoint | issues |",
            "|---|---|---|---|---|---|---|",
        ])
        for row in paid.get("rows", []):
            release = f"{row.get('pain_release_job') or row.get('payment_job')}/{row.get('pain_release_pain') or '-'}"
            queue = f"{row.get('queue_fulfillment_id') or '-'} {row.get('queue_status') or 'missing'}"
            due = str(row.get("queue_due_at", ""))[:10] or "-"
            kickoff = "ok" if row.get("kickoff_exists") else "missing"
            issues = ", ".join(row.get("issues") or []) or "ok"
            parts.append(
                "| {order} | {release} | {queue} | {due} | {kickoff} | {checkpoint} | {issues} |".format(
                    order=_md(row.get("order_id", "")),
                    release=_md(release),
                    queue=_md(queue),
                    due=_md(due),
                    kickoff=kickoff,
                    checkpoint=_md(row.get("checkpoint_summary", "")),
                    issues=_md(issues),
                )
            )
        parts.append("")
    if paid.get("issue_counts"):
        parts.extend(["## paid pain 이행 이슈", ""])
        parts.extend(f"- {k}: {v}" for k, v in paid["issue_counts"].items())
        parts.append("")
    parts.extend(["## 다음 처리", ""])
    if rep["next"]:
        parts.append("```text")
        parts.extend(_summary_rows(rep["next"]))
        parts.append("```")
    else:
        parts.append("- open 작업 없음")
    parts.append("")
    return "\n".join(parts)


def save_report_memo(
    *,
    queue_path: str | None = None,
    out_path: str | None = None,
    now: str | None = None,
    limit: int = 5,
) -> str:
    ref = _parse_ts(now or _now()) or datetime.now(timezone.utc)
    path = out_path or _default_report_path(ref)
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(report_markdown(queue_path=queue_path, now=ref.isoformat(), limit=limit))
    os.replace(tmp, path)
    return path


def _parse_memo_snapshot(text: str, path: str = "") -> dict:
    out = {
        "path": path,
        "date": "",
        "total": 0,
        "open": 0,
        "overdue": 0,
        "due_today": 0,
        "paid_orders": 0,
        "paid_ok": 0,
        "paid_issues": 0,
        "pain_counts": {},
        "micro_counts": {},
        "paid_issue_counts": {},
    }
    section = ""
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if line.startswith("# pain 파일럿 운영 메모 - "):
            out["date"] = line.rsplit(" - ", 1)[-1].strip()
            continue
        m = re.search(r"total/open/overdue/due_today:\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", line)
        if m:
            out["total"], out["open"], out["overdue"], out["due_today"] = [int(x) for x in m.groups()]
            continue
        m = re.search(r"paid pain orders/ok/issues:\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", line)
        if m:
            out["paid_orders"], out["paid_ok"], out["paid_issues"] = [int(x) for x in m.groups()]
            continue
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if section == "micro-itch별 open" and line.startswith("- ") and ":" in line:
            key, _, val = line[2:].rpartition(":")
            try:
                n = int(val.strip())
            except ValueError:
                continue
            if key.strip():
                out["micro_counts"][key.strip()] = n
        if section == "pain별 open" and line.startswith("- ") and ":" in line:
            key, _, val = line[2:].rpartition(":")
            try:
                n = int(val.strip())
            except ValueError:
                continue
            if key.strip():
                out["pain_counts"][key.strip()] = n
        if section == "paid pain 이행 이슈" and line.startswith("- ") and ":" in line:
            key, _, val = line[2:].rpartition(":")
            try:
                n = int(val.strip())
            except ValueError:
                continue
            if key.strip():
                out["paid_issue_counts"][key.strip()] = n
    if not out["date"] and path:
        out["date"] = os.path.splitext(os.path.basename(path))[0]
    return out


def memo_snapshots(*, report_dir: str | None = None, days: int = 7) -> list[dict]:
    directory = report_dir or store.FULFILLMENT_REPORT_DIR
    if not os.path.isdir(directory):
        return []
    rows = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        if "# pain 파일럿 운영 메모 - " not in text:
            continue
        snap = _parse_memo_snapshot(text, path)
        if snap.get("date"):
            rows.append(snap)
    rows = sorted(rows, key=lambda r: (str(r.get("date", "")), str(r.get("path", ""))))
    return rows[-max(0, int(days)):] if days else rows


def weekly_summary(*, report_dir: str | None = None, days: int = 7) -> dict:
    snaps = memo_snapshots(report_dir=report_dir, days=days)
    if not snaps:
        return {
            "snapshots": 0,
            "first_date": "",
            "last_date": "",
            "open_delta": 0,
            "overdue_delta": 0,
            "latest": {},
            "top_pains": {},
            "top_micro_itches": {},
            "paid_latest": {},
            "paid_issue_counts": {},
            "paid_issue_delta": 0,
            "productization_priorities": [],
        }
    micro_total: Counter[str] = Counter()
    pain_total: Counter[str] = Counter()
    paid_issue_total: Counter[str] = Counter()
    for snap in snaps:
        micro_total.update(snap.get("micro_counts", {}))
        pain_total.update(snap.get("pain_counts", {}))
        paid_issue_total.update(snap.get("paid_issue_counts", {}))
    first, last = snaps[0], snaps[-1]
    top_micro = dict(micro_total.most_common(10))
    top_pains = dict(pain_total.most_common(10))
    return {
        "snapshots": len(snaps),
        "first_date": first.get("date", ""),
        "last_date": last.get("date", ""),
        "open_delta": int(last.get("open", 0)) - int(first.get("open", 0)),
        "overdue_delta": int(last.get("overdue", 0)) - int(first.get("overdue", 0)),
        "latest": {
            "total": last.get("total", 0),
            "open": last.get("open", 0),
            "overdue": last.get("overdue", 0),
            "due_today": last.get("due_today", 0),
        },
        "top_pains": top_pains,
        "top_micro_itches": top_micro,
        "paid_latest": {
            "orders": last.get("paid_orders", 0),
            "ok": last.get("paid_ok", 0),
            "issues": last.get("paid_issues", 0),
            "issue_counts": last.get("paid_issue_counts", {}),
        },
        "paid_issue_counts": dict(paid_issue_total.most_common(10)),
        "paid_issue_delta": int(last.get("paid_issues", 0)) - int(first.get("paid_issues", 0)),
        "productization_priorities": productization_priorities(top_micro, limit=3, pain_counts=top_pains),
    }


def _job_results() -> dict:
    return ScoringEngine(_JOBS_DIR).score([])


def _representative_pain_id(job_id: str, pain_counts: dict[str, int] | Counter | None = None) -> str:
    pain_counts = pain_counts or {}
    candidates = []
    for key, count in pain_counts.items():
        job, sep, pain_id = str(key).partition("/")
        if sep and job == job_id and pain_id:
            candidates.append((int(count), pain_id))
    if candidates:
        return sorted(candidates, key=lambda x: (-x[0], x[1]))[0][1]
    job = _job_results().get(job_id)
    pains = painmap.build(job, limit=1).get("pains", []) if job else []
    return pains[0].get("pain_id", "") if pains else ""


def productization_priorities(
    top_micro_itches: dict[str, int] | Counter,
    limit: int = 3,
    *,
    pain_counts: dict[str, int] | Counter | None = None,
) -> list[dict]:
    """주간 병목에서 다음 주 제품화 후보를 만든다.

    입력은 weekly_summary의 job::micro-itch 누적 카운트다. 연락처/상황 원문 없이 aggregate만 사용한다.
    """
    items = top_micro_itches.items() if hasattr(top_micro_itches, "items") else []
    ranked = sorted(items, key=lambda kv: (-int(kv[1]), str(kv[0])))
    out = []
    for key, count in ranked:
        job, sep, itch = str(key).partition("::")
        if not sep or not job or not itch:
            continue
        adjustment = pain_probe.artifact_adjustment(job, [itch])
        rows = adjustment.get("adjustment_rows", [])
        hint = rows[0] if rows else {}
        focus = pain_probe.fulfillment_focus(job, [itch])
        questions = focus.get("followup_questions_ko", [])
        out.append({
            "rank": len(out) + 1,
            "job": job,
            "pain_id": _representative_pain_id(job, pain_counts),
            "micro_itch_ko": itch,
            "demand_count": int(count),
            "artifact_slot_ko": hint.get("artifact_slot_ko", ""),
            "template_fields_ko": hint.get("template_fields_ko", ""),
            "first_question_ko": questions[0] if questions else "",
            "next_product_move_ko": "전용 pain-offer 문구, 샘플 이행서, 납품 표 첫 섹션을 이 micro-itch 중심으로 고정한다.",
        })
        if len(out) >= max(0, int(limit)):
            break
    return out


def productized_micro_itches(
    job_id: str,
    *,
    report_dir: str | None = None,
    days: int = 7,
    limit: int = 2,
) -> list[str]:
    """저장된 운영 메모 기준으로 특정 직업군의 제품화 추천 micro-itch를 반환한다.

    연락처/상황 원문 없이 `job::micro-itch` aggregate만 읽는다. `/pain-offer` 기본값처럼
    사용자에게 노출될 수 있으므로 atlas에 있는 문장만 통과시킨다.
    """
    allowed = set((pain_probe.get(job_id) or {}).get("micro_itches_ko", []))
    if not allowed:
        return []
    summary = weekly_summary(report_dir=report_dir, days=days)
    out = []
    for key in (summary.get("top_micro_itches") or {}).keys():
        job, sep, itch = str(key).partition("::")
        if not sep or job != job_id or itch not in allowed or itch in out:
            continue
        out.append(itch)
        if len(out) >= max(0, int(limit)):
            break
    return out


def weekly_summary_markdown(*, report_dir: str | None = None, days: int = 7) -> str:
    summary = weekly_summary(report_dir=report_dir, days=days)
    parts = [
        "# pain 파일럿 주간 운영 요약",
        "",
        f"- 메모 수: {summary['snapshots']}",
        f"- 기간: {summary['first_date'] or '-'} → {summary['last_date'] or '-'}",
        f"- open 변화: {summary['open_delta']:+d}",
        f"- overdue 변화: {summary['overdue_delta']:+d}",
    ]
    latest = summary.get("latest") or {}
    paid_latest = summary.get("paid_latest") or {}
    if latest:
        parts.extend([
            f"- 최신 total/open/overdue/due_today: {latest.get('total', 0)} / {latest.get('open', 0)} / {latest.get('overdue', 0)} / {latest.get('due_today', 0)}",
            "",
        ])
    else:
        parts.append("")
    if summary["top_micro_itches"]:
        parts.extend(["## 누적 micro-itch 병목", ""])
        parts.extend(f"- {k}: {v}" for k, v in summary["top_micro_itches"].items())
    else:
        parts.extend(["## 누적 micro-itch 병목", "", "- 기록 없음"])
    if summary.get("top_pains"):
        parts.extend(["", "## 누적 pain 병목", ""])
        parts.extend(f"- {k}: {v}" for k, v in summary["top_pains"].items())
    if paid_latest and (paid_latest.get("orders") or paid_latest.get("issues") or summary.get("paid_issue_counts")):
        parts.extend(["", "## paid pain 이행 경고", ""])
        parts.append(
            "- 최신 paid pain orders/ok/issues: {orders} / {ok} / {issues}".format(
                orders=paid_latest.get("orders", 0),
                ok=paid_latest.get("ok", 0),
                issues=paid_latest.get("issues", 0),
            )
        )
        parts.append(f"- 이슈 변화: {summary.get('paid_issue_delta', 0):+d}")
        if paid_latest.get("issue_counts"):
            parts.extend(f"- {k}: {v}" for k, v in paid_latest["issue_counts"].items())
        else:
            parts.append("- 현재 이슈 없음")
        parts.append("- 조치: `python3 src/fulfillment_queue.py reconcile-paid`로 주문별 누락을 확인하고 즉시 큐/kickoff를 복구한다.")
    priorities = summary.get("productization_priorities") or []
    parts.extend(["", "## 다음 주 제품화 우선순위", ""])
    if priorities:
        for row in priorities:
            parts.extend([
                f"### {row['rank']}. {row['job']}",
                f"- 연결 pain: {row.get('pain_id') or '-'}",
                f"- 누적 수요: {row['demand_count']}",
                f"- 작은 가려움: {row['micro_itch_ko']}",
                f"- 산출물 위치: {row['artifact_slot_ko'] or '-'}",
                f"- 필수 칸: {row['template_fields_ko'] or '-'}",
                f"- 첫 확인 질문: {row['first_question_ko'] or '-'}",
                f"- 다음 제품화 행동: {row['next_product_move_ko']}",
                "",
            ])
    else:
        parts.append("- 기록 없음")
    return "\n".join(parts).rstrip() + "\n"


def productization_draft_markdown(*, report_dir: str | None = None, days: int = 7, limit: int = 3) -> str:
    summary = weekly_summary(report_dir=report_dir, days=days)
    priorities = (summary.get("productization_priorities") or [])[:max(0, int(limit))]
    parts = [
        "# 다음 주 micro-itch 제품화 초안",
        "",
        f"- 기준 기간: {summary.get('first_date') or '-'} → {summary.get('last_date') or '-'}",
        f"- 근거 메모 수: {summary.get('snapshots', 0)}",
        "- 주의: 운영 메모 기반 가설입니다. 결제 오픈 전 실제 납품 가능성과 법무/PII 조건을 다시 확인하세요.",
        "",
    ]
    if not priorities:
        parts.append("제품화 후보가 없습니다. 먼저 `fulfillment_queue.py memo`로 운영 메모를 쌓으세요.")
        return "\n".join(parts).rstrip() + "\n"

    for row in priorities:
        headline = f"{row['job']}의 '{row['micro_itch_ko']}'를 3영업일 안에 정리합니다"
        parts.extend([
            f"## {row['rank']}. {row['job']} narrow pain-offer",
            "",
            f"- Offer URL: `/pain-offer?job={row['job']}&pain={row.get('pain_id') or ''}`",
            f"- 누적 수요 신호: {row['demand_count']}",
            f"- Hero headline: {headline}",
            f"- Promise: 선택한 작은 가려움을 `{row['artifact_slot_ko'] or '핵심 산출물'}`로 바꾸고, 바로 쓸 수 있는 표/문장/질문을 전달합니다.",
            f"- Deliverable fields: `{row['template_fields_ko'] or 'input / pain_signal / artifact_move / priority / qa_check'}`",
            f"- First intake question: {row['first_question_ko'] or '마지막으로 이 문제가 터진 실제 상황과 원문 자료는 무엇인가요?'}",
            "- CTA draft: 이 반복 업무 줄이기 파일럿 신청",
            "- Scope guard: 자동화된 전문 판단, 성과 보장, 법률·의료·세무·채용 판단은 제공하지 않습니다. 운영자가 자료를 보고 컨시어지 초안을 만듭니다.",
            "",
        ])
    return "\n".join(parts).rstrip() + "\n"


def save_productization_draft(
    *,
    report_dir: str | None = None,
    out_path: str | None = None,
    now: str | None = None,
    days: int = 7,
    limit: int = 3,
) -> str:
    ref = _parse_ts(now or _now()) or datetime.now(timezone.utc)
    path = out_path or _default_productization_path(ref)
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(productization_draft_markdown(report_dir=report_dir, days=days, limit=limit))
    os.replace(tmp, path)
    return path


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip("-").lower()
    return slug or "preview"


def _productization_preview_rows(*, report_dir: str | None = None, days: int = 7, limit: int = 3) -> list[dict]:
    summary = weekly_summary(report_dir=report_dir, days=days)
    priorities = (summary.get("productization_priorities") or [])[:max(0, int(limit))]
    scores = _job_results()
    rows = []
    for row in priorities:
        job_id = row.get("job", "")
        pain_id = row.get("pain_id") or _representative_pain_id(job_id, summary.get("top_pains"))
        job = scores.get(job_id)
        if not job or not painmap.get(job, pain_id):
            continue
        filename = f"{int(row.get('rank', len(rows) + 1)):02d}-{_slug(job_id)}-{_slug(pain_id)}.html"
        rows.append({
            **row,
            "pain_id": pain_id,
            "filename": filename,
            "job_result": job,
        })
    return rows


def save_productization_previews(
    *,
    report_dir: str | None = None,
    out_dir: str | None = None,
    now: str | None = None,
    days: int = 7,
    limit: int = 3,
) -> list[str]:
    ref = _parse_ts(now or _now()) or datetime.now(timezone.utc)
    directory = out_dir or _default_preview_dir(ref)
    os.makedirs(directory, exist_ok=True)
    rows = _productization_preview_rows(report_dir=report_dir, days=days, limit=limit)
    paths = []
    index_lines = [
        f"# productization preview - {ref.date().isoformat()}",
        "",
        "- 주의: 운영 메모 기반 오퍼 미리보기입니다. 결제 오픈 전 납품 가능성, 법무/PII, 가격을 다시 확인하세요.",
        "",
    ]
    if not rows:
        index_lines.append("- preview 후보 없음")
    for row in rows:
        path = os.path.join(directory, row["filename"])
        html = report.pain_offer_html(
            row["job_result"],
            row["pain_id"],
            micro_itches=[row.get("micro_itch_ko", "")],
        )
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(html)
        os.replace(tmp, path)
        paths.append(path)
        index_lines.extend([
            f"## {row.get('rank')}. {row.get('job')} / {row.get('pain_id')}",
            "",
            f"- 파일: `{row['filename']}`",
            f"- 누적 수요: {row.get('demand_count', 0)}",
            f"- 작은 가려움: {row.get('micro_itch_ko', '')}",
            f"- 산출물 위치: {row.get('artifact_slot_ko') or '-'}",
            f"- 필수 칸: {row.get('template_fields_ko') or '-'}",
            "",
        ])
    index_path = os.path.join(directory, "index.md")
    tmp = index_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines).rstrip() + "\n")
    os.replace(tmp, index_path)
    paths.append(index_path)
    return paths


def print_report(*, queue_path: str | None = None, now: str | None = None, limit: int = 5) -> None:
    rep = operational_report(queue_path=queue_path, now=now, limit=limit)
    print("── pain 파일럿 운영 리포트 ──")
    print(f"total={rep['total']} open={rep['open']} overdue={rep['overdue']} due_today={rep['due_today']}")
    if rep["status_counts"]:
        print("상태:", ", ".join(f"{k}={v}" for k, v in rep["status_counts"].items()))
    if rep["by_job"]:
        print("\n직무별 open:")
        for job, n in rep["by_job"].items():
            print(f"  {n:>3}  {job}")
    if rep["by_pain"]:
        print("\npain별 open:")
        for pain, n in rep["by_pain"].items():
            print(f"  {n:>3}  {pain}")
    if rep["by_micro_itch"]:
        print("\nmicro-itch별 open:")
        for itch, n in rep["by_micro_itch"].items():
            print(f"  {n:>3}  {itch}")
    if rep["micro_actions"]:
        print("\n다음 운영 액션:")
        for row in rep["micro_actions"]:
            print(f"  {row['count']:>3}  {row['job']} · {row['artifact_slot_ko']}")
            print(f"       fields: {row['template_fields_ko']}")
            if row.get("first_question_ko"):
                print(f"       ask: {row['first_question_ko']}")
    paid = rep.get("paid_reconciliation") or {}
    if paid.get("paid_pain_orders"):
        issues = sum((paid.get("issue_counts") or {}).values())
        print("\npaid pain 이행 대조:")
        print(f"  orders={paid.get('paid_pain_orders', 0)} ok={paid.get('ok', 0)} issues={issues}")
        for row in (paid.get("rows") or [])[:5]:
            print(
                f"  {row.get('order_id', '-')}: {row.get('checkpoint_summary', '-')} "
                f"queue={row.get('queue_status') or 'missing'}"
            )
        for issue, n in (paid.get("issue_counts") or {}).items():
            print(f"  {issue}: {n}")
        if issues:
            print("  action: python3 src/fulfillment_queue.py reconcile-paid")
    print("\n다음 처리:")
    if not rep["next"]:
        print("  open 작업 없음")
    else:
        for line in _summary_rows(rep["next"]):
            print(line)


def print_list(*, queue_path: str | None = None) -> None:
    rows = read_jobs(queue_path)
    print("── pain 파일럿 이행 큐 ──")
    print(f"총 작업: {len(rows)}")
    if not rows:
        print("아직 없음. `python3 src/fulfillment_queue.py import`로 pain intent를 가져오세요.")
        return
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.get("status", "?")] = counts.get(row.get("status", "?"), 0) + 1
    print("상태:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    overdue = [row for row in rows if is_overdue(row)]
    if overdue:
        print(f"overdue: {len(overdue)}건")
    print("\nfulfillment_id  status    due        flag    job                pain_id                  contact            micro-itch                            situation")
    ordered = sorted(rows, key=lambda r: (r.get("status") != "queued", _due_sort_key(r), r.get("created_at", "")))
    for line in _summary_rows(ordered[-20:]):
        print(line)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="pain 파일럿 이행 작업 큐를 관리합니다.")
    ap.add_argument("--queue-file", default="", help="테스트/운영용 큐 jsonl 경로 override")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_import = sub.add_parser("import", help="pain intent를 이행 작업 큐로 가져옵니다.")
    p_import.add_argument("--intent-file", default="", help="pain intent jsonl 경로 override")
    p_import.add_argument("--limit", type=int, default=0, help="가져올 최대 건수")

    sub.add_parser("list", help="큐를 요약합니다.")
    p_report = sub.add_parser("report", help="운영 리포트를 출력합니다.")
    p_report.add_argument("--limit", type=int, default=5, help="다음 처리 작업 표시 개수")
    p_memo = sub.add_parser("memo", help="운영 리포트를 Markdown 메모로 저장합니다.")
    p_memo.add_argument("--limit", type=int, default=5, help="다음 처리 작업 표시 개수")
    p_memo.add_argument("--out", default="", help="저장할 Markdown 경로. 기본은 data/fulfillment_reports/YYYY-MM-DD.md")
    p_memo.add_argument("--now", default="", help="테스트/백필용 기준 시각 ISO 문자열")
    p_weekly = sub.add_parser("weekly", help="저장된 운영 메모를 주간 요약으로 출력합니다.")
    p_weekly.add_argument("--dir", default="", help="운영 메모 디렉터리. 기본은 data/fulfillment_reports")
    p_weekly.add_argument("--days", type=int, default=7, help="최근 메모 파일 개수")
    p_productize = sub.add_parser("productize", help="주간 병목 기반 제품화/오퍼 카피 초안을 저장합니다.")
    p_productize.add_argument("--dir", default="", help="운영 메모 디렉터리. 기본은 data/fulfillment_reports")
    p_productize.add_argument("--days", type=int, default=7, help="최근 메모 파일 개수")
    p_productize.add_argument("--limit", type=int, default=3, help="제품화 후보 개수")
    p_productize.add_argument("--out", default="", help="저장할 Markdown 경로. 기본은 data/fulfillment_reports/productization-YYYY-MM-DD.md")
    p_productize.add_argument("--now", default="", help="테스트/백필용 기준 시각 ISO 문자열")
    p_preview = sub.add_parser("productize-preview", help="주간 제품화 후보의 /pain-offer HTML 미리보기를 저장합니다.")
    p_preview.add_argument("--dir", default="", help="운영 메모 디렉터리. 기본은 data/fulfillment_reports")
    p_preview.add_argument("--days", type=int, default=7, help="최근 메모 파일 개수")
    p_preview.add_argument("--limit", type=int, default=3, help="제품화 후보 개수")
    p_preview.add_argument("--out-dir", default="", help="저장할 디렉터리. 기본은 data/fulfillment_reports/productization-preview-YYYY-MM-DD")
    p_preview.add_argument("--now", default="", help="테스트/백필용 기준 시각 ISO 문자열")
    p_reconcile = sub.add_parser("reconcile-paid", help="paid pain 주문과 이행 큐/kickoff 상태를 대조합니다.")
    p_reconcile.add_argument("--now", default="", help="테스트/백필용 기준 시각 ISO 문자열")
    p_repair = sub.add_parser("repair-paid", help="paid pain 주문의 큐/kickoff 누락을 복구합니다.")
    p_repair.add_argument("order_id", nargs="*", help="복구할 order_id. --all 사용 시 생략 가능")
    p_repair.add_argument("--all", action="store_true", help="현재 reconcile 이슈가 있는 paid pain 주문 전체 복구")
    p_repair.add_argument("--dry-run", action="store_true", help="복구하지 않고 대상과 예상 경로만 출력")
    p_repair.add_argument("--now", default="", help="테스트/백필용 기준 시각 ISO 문자열")
    p_checkpoint = sub.add_parser("checkpoint", help="paid pain 주문/작업의 이행 체크포인트를 기록합니다.")
    p_checkpoint.add_argument("identifier", help="fulfillment_id 또는 payment order_id")
    p_checkpoint.add_argument("checkpoint", choices=CHECKPOINTS)
    p_checkpoint.add_argument("--note", default="", help="운영 메모")
    p_checkpoint.add_argument("--ts", default="", help="테스트/백필용 체크포인트 시각 ISO 문자열")
    sub.add_parser("next", help="다음 queued 작업 1건을 출력합니다.")

    p_render = sub.add_parser("render", help="작업 id로 이행서를 출력합니다.")
    p_render.add_argument("fulfillment_id")

    p_status = sub.add_parser("status", help="작업 상태를 변경합니다.")
    p_status.add_argument("fulfillment_id")
    p_status.add_argument("status", choices=sorted(STATUSES))
    p_status.add_argument("--note", default="")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    queue_path = args.queue_file or None
    try:
        if args.cmd == "import":
            new_jobs = import_intents(
                intent_path=args.intent_file or None,
                queue_path=queue_path,
                limit=max(0, args.limit),
            )
            print(f"imported: {len(new_jobs)}")
            for line in _summary_rows(new_jobs):
                print(line)
            return 0
        if args.cmd == "list":
            print_list(queue_path=queue_path)
            return 0
        if args.cmd == "report":
            print_report(queue_path=queue_path, limit=max(0, args.limit))
            return 0
        if args.cmd == "memo":
            path = save_report_memo(
                queue_path=queue_path,
                out_path=args.out or None,
                now=args.now or None,
                limit=max(0, args.limit),
            )
            print(f"saved: {path}")
            return 0
        if args.cmd == "weekly":
            print(weekly_summary_markdown(report_dir=args.dir or None, days=max(0, args.days)))
            return 0
        if args.cmd == "productize":
            path = save_productization_draft(
                report_dir=args.dir or None,
                out_path=args.out or None,
                now=args.now or None,
                days=max(0, args.days),
                limit=max(0, args.limit),
            )
            print(f"saved: {path}")
            return 0
        if args.cmd == "productize-preview":
            paths = save_productization_previews(
                report_dir=args.dir or None,
                out_dir=args.out_dir or None,
                now=args.now or None,
                days=max(0, args.days),
                limit=max(0, args.limit),
            )
            for path in paths:
                print(f"saved: {path}")
            return 0
        if args.cmd == "reconcile-paid":
            print_paid_reconciliation(queue_path=queue_path, now=args.now or None)
            return 0
        if args.cmd == "repair-paid":
            repaired = repair_paid_releases(
                args.order_id,
                all_issues=bool(args.all),
                queue_path=queue_path,
                dry_run=bool(args.dry_run),
                now=args.now or None,
            )
            for row in repaired:
                mode = "dry-run" if row.get("dry_run") else "repaired"
                before = ", ".join(row.get("before_issues") or []) or "ok"
                after = ", ".join(row.get("after_issues") or []) or "ok"
                print(
                    f"{mode}: {row['order_id']} {row['job']}/{row['pain_id']} "
                    f"{row['fulfillment_id']} before={before} after={after} kickoff={row['kickoff_path']}"
                )
            return 0
        if args.cmd == "checkpoint":
            row = set_checkpoint(
                args.identifier,
                args.checkpoint,
                note=args.note,
                ts=args.ts or None,
                queue_path=queue_path,
            )
            checkpoint = checkpoint_status(row)
            print(
                f"checkpoint: {row['fulfillment_id']} {args.checkpoint} "
                f"{checkpoint['summary']} status={row.get('status', '')}"
            )
            return 0
        if args.cmd == "next":
            row = next_job(queue_path=queue_path)
            if not row:
                print("queued 작업 없음")
                return 1
            for line in _summary_rows([row]):
                print(line)
            return 0
        if args.cmd == "render":
            print(render_job(args.fulfillment_id, queue_path=queue_path))
            return 0
        if args.cmd == "status":
            row = set_status(args.fulfillment_id, args.status, note=args.note, queue_path=queue_path)
            print(f"updated: {row['fulfillment_id']} {row['status']}")
            return 0
        raise ValueError("unknown command")
    except ValueError as e:
        sys.stderr.write(str(e) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
