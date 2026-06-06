"""
커리어 시그널 — 일/주 배치 (R4d)

흐름: pipeline.run()(수집·전체히스토리 재점수·점수로그 append)
   → 직무별 '의미있는 변동'(|delta|>=2 또는 기상예보 변화) 감지
   → 그 직무를 구독한 사용자에게 푸시 메시지 큐잉(notify)
   → 전략가타입 Gemini 결과 캐시(서버 /report가 요청마다 호출하지 않게)
실제 카카오 발송은 스텁(R5/배포에서 비즈메시지 API 연동).

실행: GEMINI_API_KEY=... python3 src/batch.py [--max N] [--send]
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import notify
import pipeline
import report
import store

MATERIAL_DELTA = 2.0  # 이 이상 변하거나 날씨 바뀌면 '알릴 만한 변동'


def _weather_changed(job_id: str) -> bool:
    h = store.score_history(job_id, 2)
    return len(h) >= 2 and h[-1].get("weather") != h[-2].get("weather")


def run_batch(now=None, max_per_source: int | None = None, send: bool = False) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    results = pipeline.run(now=now, max_per_source=max_per_source)
    notices = []
    for job_id, res in results.items():
        latest = store.latest_score(job_id)
        snap_ts = latest.get("ts") if latest else None
        delta = latest.get("delta") if latest else None
        material = ((isinstance(delta, (int, float)) and abs(delta) >= MATERIAL_DELTA)
                    or _weather_changed(job_id))
        # 이 스냅샷으로 이미 알림했으면 재알림 금지 — 매 배치 중복 스팸 방지 (Codex)
        new_alert = bool(material and snap_ts and store.get_notified(job_id) != snap_ts)

        # 전략가타입 캐시: 없거나 새 변동일 때만 Gemini 호출 (비용 절감)
        if store.get_strategist(job_id) is None or new_alert:
            try:
                store.save_strategist(job_id, report.strategist_type(res, use_gemini=True))
            except Exception as e:
                print(f"[batch] 전략가타입 캐시 실패 {job_id}: {type(e).__name__} {e}")

        if not new_alert:
            continue
        snap = {"job_name_ko": res["job_name_ko"], "weather": res["weather"], "delta": delta,
                "headline_task": res.get("headline_task"), "top_drivers": res.get("top_drivers", [])}
        msg = notify.make_push(snap)["text"]
        subs = store.users_by_job(job_id)
        for uid in subs:
            store.append_outbox(uid, msg, job_id, ts=now.isoformat())
        store.set_notified(job_id, snap_ts)  # 이 스냅샷 알림 완료 기록 (중복 방지 키)
        notices.append({"job_id": job_id, "delta": delta, "subscribers": len(subs), "msg": msg})
        print(f"[batch] {res['job_name_ko']} 변동(Δ{delta}) → 구독자 {len(subs)}명 큐잉")

    if send:
        _flush_outbox()
    return notices


def _flush_outbox() -> int:
    """발송 스텁 — 실제로는 카카오 비즈메시지(알림톡/친구톡) API 호출.
    여기선 큐 길이만 로그. status 갱신/재시도/backoff는 R5."""
    pending = [m for m in store.read_outbox() if m.get("status") == "queued"]
    print(f"[batch] 발송 대기 {len(pending)}건 (카카오 비즈메시지 API 연동은 R5/배포)")
    return len(pending)


if __name__ == "__main__":
    import json
    mx = None
    if "--max" in sys.argv:
        mx = int(sys.argv[sys.argv.index("--max") + 1])
    out = run_batch(max_per_source=mx, send="--send" in sys.argv)
    print(json.dumps(out, ensure_ascii=False, indent=2))
