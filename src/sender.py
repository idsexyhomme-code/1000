"""
커리어 시그널 — 발송 파이프라인 (R5-b)

outbox(큐) → Sender로 발송 → sent/failed 마킹 + 재시도 + per-user throttle.
실제 카카오 비즈메시지(알림톡/친구톡)는 KakaoSender에 연결(현재 스텁 — 발신프로필+템플릿 승인 필요).
stdlib만, 의존성 0.

실행: python3 src/sender.py   (StubSender로 큐 발송 검증)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store

MAX_RETRIES = 3
THROTTLE_PER_USER = 3   # 1회 flush에서 사용자당 최대 발송 수 (스팸 방지)


class Sender:
    name = "base"

    def send(self, user_id: str, text: str) -> bool:
        raise NotImplementedError


class StubSender(Sender):
    """발송 스텁 — 로그만, 항상 성공. 실제 API 붙기 전 파이프라인 검증용."""
    name = "stub"

    def __init__(self):
        self.sent: list[tuple] = []

    def send(self, user_id: str, text: str) -> bool:
        self.sent.append((user_id, text))
        return True


class KakaoSender(Sender):
    """카카오 비즈메시지(알림톡/친구톡) 발송 — TODO(배포): 실제 API 연결.
    필요: 발신프로필 + 사전승인 템플릿(알림톡 필수) + KAKAO_API_KEY(env).
    승인 전까지는 StubSender 사용."""
    name = "kakao"

    def send(self, user_id: str, text: str) -> bool:
        raise NotImplementedError("카카오 비즈메시지 API 미연결 — 발신프로필+템플릿 승인 후 구현")


def flush(sender: Sender | None = None, max_retries: int = MAX_RETRIES,
          throttle_per_user: int = THROTTLE_PER_USER) -> dict:
    """outbox의 queued 메시지를 발송하고 상태 마킹(sent/failed/재시도).
    per-user throttle로 한 번에 같은 사용자에게 과발송 방지. 반환: 통계."""
    sender = sender or StubSender()
    rows = store.read_outbox()
    per_user: dict[str, int] = {}
    stats = {"sent": 0, "failed": 0, "retry": 0, "throttled": 0}
    for r in rows:
        if r.get("status") != "queued":
            continue
        uid = r.get("user_id", "")
        if per_user.get(uid, 0) >= throttle_per_user:   # 다음 flush로 미룸(queued 유지)
            stats["throttled"] += 1
            continue
        try:
            ok = sender.send(uid, r.get("text", ""))
        except Exception as e:
            ok = False
            r["error"] = f"{type(e).__name__}: {e}"
        if ok:
            r["status"] = "sent"
            per_user[uid] = per_user.get(uid, 0) + 1
            stats["sent"] += 1
        else:
            r["retries"] = int(r.get("retries", 0)) + 1
            if r["retries"] >= max_retries:
                r["status"] = "failed"
                stats["failed"] += 1
            else:
                stats["retry"] += 1   # status는 queued 유지 → 다음 flush 재시도
    store.update_outbox(rows)
    return stats


if __name__ == "__main__":
    import json
    # 큐에 테스트 메시지 적재 후 StubSender로 발송 + throttle 검증
    for i in range(5):
        store.append_outbox("u1", f"테스트 메시지 {i}", "video-editor")
    store.append_outbox("u2", "다른 유저", "junior-developer")
    s = StubSender()
    stats = flush(sender=s, throttle_per_user=3)
    print("flush stats:", json.dumps(stats, ensure_ascii=False))
    print("실제 발송:", len(s.sent), "건 (u1은 throttle 3, u2는 1 → 4 기대)")
    remaining = [m for m in store.read_outbox() if m.get("status") == "queued"]
    print("남은 queued:", len(remaining), "(u1 throttle된 2건 기대)")
