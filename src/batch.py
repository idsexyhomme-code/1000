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
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import actionplan
import notify
import pipeline
import report
import store

MATERIAL_DELTA = 2.0  # 이 이상 변하거나 날씨 바뀌면 '알릴 만한 변동'
NOTIFY_COOLDOWN_DAYS = 3  # 같은 직무 재알림 최소 간격 — 잦은 푸시 = 불안상품화·스팸·이탈(§1.6). 날씨밴드 변화는 예외.


def _weather_changed(job_id: str) -> bool:
    h = store.score_history(job_id, 2)
    return len(h) >= 2 and h[-1].get("weather") != h[-2].get("weather")


def _in_cooldown(job_id: str, now: datetime) -> bool:
    """직전 알림이 쿨다운 이내면 True(추가 푸시 보류). notified엔 알림 당시 스냅샷 ts(ISO)가 저장됨."""
    prev = store.get_notified(job_id)
    if not prev:
        return False
    try:
        last = datetime.fromisoformat(str(prev).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    return (now - last) < timedelta(days=NOTIFY_COOLDOWN_DAYS)


def run_batch(now=None, max_per_source: int | None = None, send: bool = False) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    results = pipeline.run(now=now, max_per_source=max_per_source)
    notices = []
    for job_id, res in results.items():
        latest = store.latest_score(job_id)
        snap_ts = latest.get("ts") if latest else None
        delta = latest.get("delta") if latest else None
        weather_crossed = _weather_changed(job_id)
        material = ((isinstance(delta, (int, float)) and abs(delta) >= MATERIAL_DELTA)
                    or weather_crossed)
        # 이 스냅샷으로 이미 알림했으면 재알림 금지 — 매 배치 중복 스팸 방지 (Codex)
        new_alert = bool(material and snap_ts and store.get_notified(job_id) != snap_ts)
        # 쿨다운: 최근 알림이 NOTIFY_COOLDOWN_DAYS 이내면 푸시 보류(불안상품화·스팸 방지 §1.6).
        # 단 날씨밴드 변화(맑음→흐림 등 진짜 중대 변화)는 예외로 즉시 통과. 캐시 갱신엔 영향 없음.
        should_push = new_alert and (weather_crossed or not _in_cooldown(job_id, now))

        # 전략가타입 + 액션플랜 캐시: 없거나 새 변동일 때만 Gemini 호출 (비용 절감, /report가 캐시 사용)
        if store.get_strategist(job_id) is None or new_alert:
            try:
                store.save_strategist(job_id, report.strategist_type(res, use_gemini=True))
            except Exception as e:
                print(f"[batch] 전략가타입 캐시 실패 {job_id}: {type(e).__name__} {e}")
        if store.get_actionplan(job_id) is None or new_alert:
            try:
                store.save_actionplan(job_id, actionplan.make_action_plan(res, use_gemini=True))
            except Exception as e:
                print(f"[batch] 액션플랜 캐시 실패 {job_id}: {type(e).__name__} {e}")

        if not should_push:
            continue
        # 근거 결박된 플랜이 있으면 첫 액션을 푸시에 노출(경고→구명조끼). ungrounded면 미노출.
        plan = store.get_actionplan(job_id)
        action_title = None
        if plan and plan.get("guardrail_ok"):
            acts = plan.get("actions") or []
            if acts:
                action_title = acts[0].get("title_ko")
        snap = {"job_name_ko": res["job_name_ko"], "weather": res["weather"], "delta": delta,
                "headline_task": res.get("headline_task"), "top_drivers": res.get("top_drivers", []),
                "action_title": action_title}
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


def _flush_outbox() -> dict:
    """outbox 발송 — sent-marker/재시도/per-user throttle (현재 StubSender).
    실제 카카오 비즈메시지는 sender.KakaoSender 연결(발신프로필+템플릿 승인 후, R6)."""
    import sender
    stats = sender.flush()
    print(f"[batch] 발송: {stats}")
    return stats


if __name__ == "__main__":
    import json
    mx = None
    if "--max" in sys.argv:
        mx = int(sys.argv[sys.argv.index("--max") + 1])
    out = run_batch(max_per_source=mx, send="--send" in sys.argv)
    print(json.dumps(out, ensure_ascii=False, indent=2))
