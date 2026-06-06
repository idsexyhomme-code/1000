"""
커리어 시그널 — 핵심 불변식 테스트 (R7)

stdlib assert 기반(pytest 불필요), 전부 오프라인(Gemini 호출 없음 — 폴백/결정적 경로만).
자율 루프가 코드를 계속 수정해도 회귀를 잡는 안전망.
실행: python3 tests/test_core.py   (실패 시 exit 1)
"""
import os
import shutil
import sys
from datetime import datetime, timezone, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

import actionplan
import notify
import pipeline
import report
import scoring
import sender
import store
from scoring import Affected, Event, ScoringEngine

NOW = datetime(2026, 6, 6, tzinfo=timezone.utc)
JOBS = os.path.join(_ROOT, "data", "jobs")
DATA = os.path.join(_ROOT, "data")


# ── scoring ───────────────────────────────────────────────────────────
def test_weather_bands_contiguous():
    for v in [0, 25, 26, 50, 51, 75, 76, 100]:   # 경계 빈틈 없어야
        assert scoring.to_weather(v)[0], v


def test_no_source_zero_delta():
    a = Affected("j", "t", {"proximity": 3, "maturity": 3, "adoption": 3, "irreversibility": 3, "scale": 2},
                 "automation", "r")
    assert scoring.raw_delta(a, 99) == 0.0          # 미지 티어 → delta 0


def test_vendor_factor_confidence_discounts_adoption():
    a = Affected("j", "t", {"proximity": 0, "maturity": 0, "adoption": 3, "irreversibility": 0, "scale": 2},
                 "automation", "r")
    assert abs(scoring.raw_delta(a, 3)) < abs(scoring.raw_delta(a, 1))   # 벤더 adoption/scale 할인


def test_ci_propagation_guards():
    assert scoring._propagate_job_ci([], [], 12) == 12                   # 빈 → fallback
    assert scoring._propagate_job_ci([{"weight": None, "ci": None}], [], 12) > 0  # 크래시 없음


def test_headline_is_highest_task():
    r = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    assert r["headline_task"]["index"] == max(t["index"] for t in r["tasks"])


def test_all_jobs_load_and_score():
    res = ScoringEngine(JOBS).score([], now=NOW)
    assert len(res) >= 10                                               # 커버리지
    for r in res.values():
        assert 0 <= r["index"] <= 100 and 4 <= r["ci"] <= 25


# ── actionplan ────────────────────────────────────────────────────────
def _job(drivers):
    return {"job_id": "x", "job_name_ko": "테스트직", "weather": "흐림", "index": 59, "ci": 9,
            "headline_task": {"task_id": "a", "name_ko": "A업무", "index": 80, "weather": "태풍경보"},
            "tasks": [{"task_id": "a", "name_ko": "A업무", "index": 80, "ci": 9, "weather": "태풍경보"},
                      {"task_id": "b", "name_ko": "B업무", "index": 30, "ci": 10, "weather": "맑음"}],
            "top_drivers": drivers}


def test_actionplan_no_fabrication_when_no_drivers():
    p = actionplan.make_action_plan(_job([]), use_gemini=False)
    assert p["guardrail_ok"] is False                                  # 근거 없음 → 미결박
    for a in p["actions"]:
        assert a["why_now"]["source_driver_index"] == -1               # 가짜 인덱스 금지
        assert "최신 AI 동향" not in a["why_now"]["evidence_title"]      # 가짜 뉴스 합성 금지


def test_actionplan_grounded_defend_cites_matching_driver():
    drv = [{"task_id": "a", "delta": 3.0, "direction": "automation", "source_tier": 2,
            "confidence": 0.7, "url": "https://example.com/x", "reason_ko": "r", "title": "뉴스A"}]
    p = actionplan.make_action_plan(_job(drv), use_gemini=False)
    assert p["guardrail_ok"] is True
    for a in p["actions"]:
        if a["strategy_type"] == "defend":
            di = a["why_now"]["source_driver_index"]
            assert drv[di]["task_id"] == a["defends_task_id"]          # 업무-근거 일치


# ── notify ────────────────────────────────────────────────────────────
def test_notify_guardrail_blocks_banned():
    assert notify._guardrail_ok("[흐림] 압력 상승 관측. 대응전략 보기")
    assert not notify._guardrail_ok("당신의 직업은 대체됩니다")


def test_notify_surfaces_action():
    snap = {"job_name_ko": "영상편집자", "weather": "흐림", "delta": 2.0,
            "headline_task": {"name_ko": "컷 편집"}, "top_drivers": [{}],
            "action_title": "Sora Edit로 워크플로 만들기"}
    assert "이번 주" in notify.fallback_copy(snap)


# ── sender ────────────────────────────────────────────────────────────
def _clear_outbox():
    if os.path.exists(store.OUTBOX_FILE):
        os.remove(store.OUTBOX_FILE)


def test_sender_throttle_per_user():
    _clear_outbox()
    for i in range(5):
        store.append_outbox("u1", f"m{i}", "x")
    st = sender.flush(sender=sender.StubSender(), throttle_per_user=3)
    assert st["sent"] == 3 and st["throttled"] == 2
    _clear_outbox()


def test_sender_retry_then_failed():
    _clear_outbox()
    store.append_outbox("u2", "f", "x")

    class _Fail(sender.Sender):
        def send(self, u, t):
            return False

    sender.flush(sender=_Fail(), max_retries=3)
    sender.flush(sender=_Fail(), max_retries=3)
    row = store.read_outbox()[0]
    assert row["status"] == "queued" and row["retries"] == 2           # 아직 재시도 중
    sender.flush(sender=_Fail(), max_retries=3)
    assert store.read_outbox()[0]["status"] == "failed"                # 소진 → failed
    _clear_outbox()


# ── pipeline ──────────────────────────────────────────────────────────
def test_canonical_url_no_collision_strips_tracking():
    a = pipeline._event_id("https://x.com/a?id=1&utm_source=t", "t1")
    b = pipeline._event_id("https://x.com/a?id=2", "t2")
    assert a != b                                                      # ?id 보존(충돌 없음)
    assert "utm_source" not in pipeline._canonical_url("https://x.com/a?id=1&utm_source=t")


def test_prune_archives_old_evidence_keeps_regulation():
    ev_dir = os.path.join(DATA, "events")
    arch_dir = os.path.join(DATA, "events_archive")
    shutil.rmtree(ev_dir, ignore_errors=True)
    shutil.rmtree(arch_dir, ignore_errors=True)

    def _ev(eid, days, kind):
        pub = (NOW - timedelta(days=days)).isoformat()
        return {"event_id": eid, "title": "t", "url": f"http://x/{eid}", "source_tier": 2,
                "published_at": pub, "status": "complete", "dedup_key": "a+b",
                "affected": [{"job_id": "video-editor", "task_id": "cut-editing",
                              "factors": {"proximity": 3}, "direction": "automation",
                              "reason_ko": "r", "event_kind": kind, "dedup_key": "a+b"}]}
    store.save_event(_ev("old", 500, "evidence"))
    store.save_event(_ev("reg", 500, "regulation"))
    store.save_event(_ev("new", 5, "evidence"))
    pipeline.prune_events(now=NOW)
    live = set(os.listdir(ev_dir))
    assert "old.json" not in live                                      # 감쇠소멸 → 아카이브
    assert "reg.json" in live and "new.json" in live                   # 규제·최신 보존
    shutil.rmtree(ev_dir, ignore_errors=True)
    shutil.rmtree(arch_dir, ignore_errors=True)


# ── report ────────────────────────────────────────────────────────────
def test_report_safe_url_blocks_xss():
    assert report._safe_url("javascript:alert(1)") == "#"
    assert report._safe_url("https://openai.com/x") == "https://openai.com/x"


def test_report_gauge_angle_dynamic():
    assert "rotate(0.0," in report._gauge_svg(0, 12)
    assert "rotate(180.0," in report._gauge_svg(100, 12)


def test_report_ungrounded_plan_no_paywall():
    job = _job([])
    strat = {"type_name": "t", "emoji": "🧭", "tagline": "", "threat": "", "opportunity": ""}
    up = {"guardrail_ok": False, "actions": [{"strategy_type": "pivot", "title_ko": "X",
          "action_steps": ["s"], "difficulty": "중급", "time_hours": 3, "payoff_ko": "p"}]}
    h = report.render_html(job, strat, action_plan=up)
    assert "대응 전략 보기" not in h                                     # 유료 CTA 없음
    assert "직접 결박된 새 근거" in h                                    # 정직 안내


# ── runner ────────────────────────────────────────────────────────────
def run():
    tests = sorted((v for k, v in globals().items()
                    if k.startswith("test_") and callable(v)), key=lambda f: f.__name__)
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {t.__name__}: {type(e).__name__} {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    run()
