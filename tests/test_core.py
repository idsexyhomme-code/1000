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
import deepdive
import fulfillment
import fulfillment_queue
import gemini_client
import launch_preflight
import legal_preflight
import notify
import pain_deepdive
import painmap
import pain_probe
import pain_intents
import pipeline
import report
import scoring
import sender
import server
import store
import workradar
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


def test_all_job_files_schema_valid():
    import json
    for fn in os.listdir(JOBS):
        if not fn.endswith(".json"):
            continue
        j = json.load(open(os.path.join(JOBS, fn), encoding="utf-8"))
        assert j.get("job_id") and j.get("job_name_ko"), fn
        b = j.get("baseline", {})
        assert isinstance(b.get("index"), (int, float)) and isinstance(b.get("ci"), (int, float)), fn
        assert "calibrated" in b, f"{fn}: calibrated 플래그 누락"
        assert "캘리브레이션" in b.get("note", "") or "손추정" in b.get("note", ""), f"{fn}: 정직 note 누락"
        tasks = j.get("tasks", [])
        assert len(tasks) >= 4, fn
        ws = round(sum(t.get("weight", 0) for t in tasks), 3)
        assert 0.95 <= ws <= 1.05, f"{fn}: weight 합 {ws}"
        for t in tasks:
            assert t.get("task_id") and t.get("name_ko"), fn
            assert 0 <= t.get("baseline", -1) <= 100, fn


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


def test_report_landing_lists_jobs():
    h = report.landing_html(server.JOBS)
    assert h.rstrip().endswith("</html>")
    assert h.count('class="lj-card"') >= 10                              # 직업 카드 그리드
    assert "참고 지표" in h                                              # 가드레일 푸터
    assert "/privacy" in h and "/terms" in h                              # PII 수집 전 공개 표면


def test_legal_pages_are_public_templates_with_required_items():
    privacy = report.privacy_html()
    terms = report.terms_html()
    assert privacy.rstrip().endswith("</html>")
    assert terms.rstrip().endswith("</html>")
    assert "[필수 입력]" in privacy and "[필수 입력]" in terms             # 사업자 정보 채우기 전제
    for marker in [
        "개인정보의 처리 목적",
        "개인정보의 처리 및 보유 기간",
        "제3자 제공",
        "개인정보 처리위탁",
        "정보주체의 권리",
        "파기 절차",
        "자동화된 결정",
        "2026 개인정보 처리방침 작성지침",
    ]:
        assert marker in privacy
    for marker in [
        "사업자 정보",
        "상품 및 제공시점",
        "청약철회",
        "환불",
        "전문 판단 제외",
        "개인정보처리방침",
        "전자상거래",
    ]:
        assert marker in terms


def test_legal_preflight_blocks_placeholders_until_env_is_filled():
    old = {k: os.environ.get(k) for k in legal_preflight.REQUIRED_ENV}
    try:
        for key in legal_preflight.REQUIRED_ENV:
            os.environ.pop(key, None)
        ok, issues = legal_preflight.check()
        assert ok is False
        assert any("missing env" in issue for issue in issues)
        assert any("[필수 입력]" in issue for issue in issues)
    finally:
        for key, val in old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def test_legal_preflight_passes_when_legal_env_is_filled():
    old = {k: os.environ.get(k) for k in legal_preflight.REQUIRED_ENV + ["LEGAL_SERVICE_NAME"]}
    vals = {
        "LEGAL_SERVICE_NAME": "커리어 시그널",
        "LEGAL_OPERATOR_NAME": "테스트상호",
        "LEGAL_OPERATOR_ADDRESS": "서울특별시 테스트로 1",
        "LEGAL_CONTACT_EMAIL": "legal@example.com",
        "LEGAL_PRIVACY_OFFICER": "개인정보책임자",
        "LEGAL_BUSINESS_NUMBER": "123-45-67890",
        "LEGAL_TELECOMMERCE_NUMBER": "제2026-서울테스트-0001호",
        "LEGAL_PAYMENT_PROCESSOR": "테스트PG",
        "LEGAL_HOSTING_PROVIDER": "테스트호스팅",
        "LEGAL_NOTIFICATION_PROVIDER": "테스트메일도구",
        "LEGAL_FULFILLMENT_FIELDS": "결제자 이름, 이메일, 주문번호, 이력서, 포트폴리오",
    }
    try:
        os.environ.update(vals)
        ok, issues = legal_preflight.check()
        assert ok is True, issues
        assert "[필수 입력]" not in report.privacy_html()
        assert "[필수 입력]" not in report.terms_html()
    finally:
        for key, val in old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def _with_env(vals, fn, clear=None):
    keys = set(vals) | set(clear or [])
    old = {k: os.environ.get(k) for k in keys}
    try:
        for key in clear or []:
            os.environ.pop(key, None)
        os.environ.update(vals)
        fn()
    finally:
        for key, val in old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val


def _ready_launch_env(extra=None):
    vals = {
        "GEMINI_API_KEY": "test-gemini-key",
        "REPORT_BASE_URL": "https://career.example.com",
        "WEBHOOK_TOKEN": "webhook-token-123456",
        "INTEREST_SALT": "interest-salt-123456",
        "LEGAL_SERVICE_NAME": "커리어 시그널",
        "LEGAL_OPERATOR_NAME": "테스트상호",
        "LEGAL_OPERATOR_ADDRESS": "서울특별시 테스트로 1",
        "LEGAL_CONTACT_EMAIL": "legal@example.com",
        "LEGAL_PRIVACY_OFFICER": "개인정보책임자",
        "LEGAL_BUSINESS_NUMBER": "123-45-67890",
        "LEGAL_TELECOMMERCE_NUMBER": "제2026-서울테스트-0001호",
        "LEGAL_PAYMENT_PROCESSOR": "테스트PG",
        "LEGAL_HOSTING_PROVIDER": "테스트호스팅",
        "LEGAL_NOTIFICATION_PROVIDER": "테스트메일도구",
        "LEGAL_FULFILLMENT_FIELDS": "결제자 이름, 이메일, 주문번호, 이력서, 포트폴리오",
    }
    vals.update(extra or {})
    return vals


def test_launch_preflight_lead_mode_blocks_unready_env():
    def body():
        ok, issues = launch_preflight.check("lead")
        assert ok is False
        assert any("legal:" in issue for issue in issues)
        assert any("GEMINI_API_KEY" in issue for issue in issues)
    _with_env({}, body, clear=launch_preflight.COMMON_REQUIRED + legal_preflight.REQUIRED_ENV)


def test_launch_preflight_lead_mode_passes_and_rejects_payment_urls():
    clear = ["PAYMENT_URL", "PAIN_PAYMENT_URL", "PAYMENT_ALLOWED_AMOUNTS",
             "PAYMENT_WEBHOOK_SECRET", "PAYMENT_EXPECTED_AMOUNT", "PAIN_PAYMENT_EXPECTED_AMOUNT"]

    def ok_body():
        ok, issues = launch_preflight.check("lead")
        assert ok is True, issues

    _with_env(_ready_launch_env(), ok_body, clear=clear)

    def bad_body():
        ok, issues = launch_preflight.check("lead")
        assert ok is False
        assert "lead mode must not set PAYMENT_URL" in issues

    _with_env(_ready_launch_env({"PAYMENT_URL": "https://pay.example/checkout"}), bad_body,
              clear=["PAIN_PAYMENT_URL", "PAYMENT_ALLOWED_AMOUNTS"])


def test_launch_preflight_paid_modes_require_payment_guards():
    def bad_body():
        ok, issues = launch_preflight.check("paid")
        assert ok is False
        assert any("PAYMENT_URL" in issue for issue in issues)
        assert any("PAYMENT_WEBHOOK_SECRET" in issue for issue in issues)

    _with_env(_ready_launch_env(), bad_body, clear=["PAYMENT_URL", "PAYMENT_WEBHOOK_SECRET"])

    paid_env = _ready_launch_env({
        "PAYMENT_URL": "https://pay.example/career",
        "PAYMENT_WEBHOOK_SECRET": "payment-secret-123456",
        "PAYMENT_EXPECTED_AMOUNT": "99000",
        "PAYMENT_ALLOWED_AMOUNTS": "99000,39000",
    })

    def paid_body():
        ok, issues = launch_preflight.check("paid")
        assert ok is True, issues

    _with_env(paid_env, paid_body)

    pain_env = _ready_launch_env({
        "PAIN_PAYMENT_URL": "https://pay.example/pain",
        "PAYMENT_WEBHOOK_SECRET": "payment-secret-123456",
        "PAIN_PAYMENT_EXPECTED_AMOUNT": "39000",
        "PAYMENT_ALLOWED_AMOUNTS": "99000,39000",
    })

    def pain_without_release_body():
        ok, issues = launch_preflight.check("pain-paid")
        assert ok is False
        assert any("PAIN_RELEASE_JOB" in issue for issue in issues)
        assert any("PAIN_RELEASE_PAIN" in issue for issue in issues)
        assert any("PAIN_RELEASE_PREVIEW" in issue for issue in issues)

    _with_env(pain_env, pain_without_release_body,
              clear=["PAIN_RELEASE_JOB", "PAIN_RELEASE_PAIN", "PAIN_RELEASE_PREVIEW"])

    import tempfile
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    pain_id = "revision-chaos"
    micro = pain_probe.get("video-editor")["micro_itches_ko"][0]
    preview = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    preview.close()
    with open(preview.name, "w", encoding="utf-8") as f:
        f.write(report.pain_offer_html(job, pain_id, micro_itches=[micro]))
    pain_release_env = {**pain_env, "PAIN_RELEASE_JOB": "video-editor",
                        "PAIN_RELEASE_PAIN": pain_id, "PAIN_RELEASE_PREVIEW": preview.name}

    def pain_body():
        ok, issues = launch_preflight.check("pain-paid")
        assert ok is True, issues

    try:
        _with_env(pain_release_env, pain_body)
    finally:
        os.unlink(preview.name)


def test_deepdive_and_detail_honest():
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    deep = deepdive.build(job)
    assert deep["automation"]["calibrated"] is False                     # 손추정 정직 표기
    assert deep["hiring"]["available"] is False                          # 데이터 없음 → 스텁(가짜숫자 금지)
    assert len(deep["automation"]["tasks"]) == len(job["tasks"])         # 전 과업 자동화율
    assert deep["pivot"]["within_job"]                                   # 전이경로(저압력 업무)
    h = report.detail_html(job, deep)
    assert h.rstrip().endswith("</html>")
    assert "과업별 자동화율" in h and "방법론" in h                       # 5섹션 + 방법론
    assert "데이터 연동 필요" in h                                       # 스텁 정직 노출(패딩 아님)


def test_painmap_schema_and_job_task_links():
    errors = painmap.validate_against_jobs(server.JOBS)
    assert errors == []
    assert set(painmap.PAIN_MAP) == set(server.JOBS)


def test_painmap_build_is_labeled_hypothesis():
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    pm = painmap.build(job, limit=2)
    assert pm["label_ko"] == "제품 가설"
    assert "유료 판단 근거" in pm["note_ko"]                              # 과대표기 방지
    assert len(pm["pains"]) == 2
    assert painmap.get(job, pm["pains"][0]["pain_id"])["pain_id"] == pm["pains"][0]["pain_id"]
    for p in pm["pains"]:
        assert p["task_names_ko"] and p["artifact_ko"]                    # 업무 맥락 + 결과물
        assert p["priority_score"] > 0


def test_pain_deepdive_covers_representative_job_pains():
    errors = pain_deepdive.validate_against_jobs(server.JOBS)
    assert errors == []
    assert len(pain_deepdive.DEEP_ATLAS) == len(server.JOBS)
    rows = pain_deepdive.catalog(ScoringEngine(JOBS).score([], now=NOW))
    assert len(rows) == len(server.JOBS)
    for row in rows:
        assert row["burning_moment_ko"]
        assert row["bad_ai_trap_ko"]
        assert row["minimum_inputs_ko"]
        assert row["paid_trigger_ko"]
        assert row["success_metric_ko"]
    md = pain_deepdive.markdown_catalog(ScoringEngine(JOBS).score([], now=NOW))
    assert "직업별 진짜 가려운 업무 심층 아틀라스" in md
    assert "구매 트리거" in md


def test_pain_probe_atlas_deepens_every_job():
    errors = pain_probe.validate_against_jobs(server.JOBS)
    assert errors == []
    rows = pain_probe.catalog(ScoringEngine(JOBS).score([], now=NOW))
    assert len(rows) == len(server.JOBS)
    for row in rows:
        assert row["label_ko"] == "micro-itch 가설"
        assert len(row["micro_itches_ko"]) >= 10
        assert len(row["interview_questions_ko"]) >= 4
        assert row["money_moment_ko"]
        assert row["wedge_ko"]
        assert row["avoid_ko"]
    md = pain_probe.markdown_catalog(ScoringEngine(JOBS).score([], now=NOW))
    assert "직업별 micro-itch probe atlas" in md
    assert "검증 질문" in md
    micro = pain_probe.get("video-editor")["micro_itches_ko"][1]
    focus = pain_probe.fulfillment_focus("video-editor", [micro, "임의 문장"])
    assert focus["selected_micro_itches_ko"] == [micro]
    assert "이번 납품" in focus["priority_focus_ko"]
    assert any("마지막으로 터진 실제 상황" in q for q in focus["followup_questions_ko"])
    assert "임의 문장" not in " ".join(focus["followup_questions_ko"])
    adj = pain_probe.artifact_adjustment("video-editor", [micro, "임의 문장"])
    assert len(adj["adjustment_rows"]) == 1
    assert adj["adjustment_rows"][0]["template_fields_ko"] == "conflict_group / request_a / request_b / decision_needed / proposed_reply"

    dev_micro = pain_probe.get("junior-developer")["micro_itches_ko"][0]
    dev_adj = pain_probe.artifact_adjustment("junior-developer", [dev_micro])
    assert dev_adj["adjustment_rows"][0]["template_fields_ko"] == "entrypoint / likely_file / reason / unknown / first_probe_command"

    sales_micro = pain_probe.get("sales-rep")["micro_itches_ko"][0]
    sales_adj = pain_probe.artifact_adjustment("sales-rep", [sales_micro])
    assert sales_adj["adjustment_rows"][0]["template_fields_ko"] == "account_signal / stakeholder / likely_pain / proof_point / opening_question"

    data_micro = pain_probe.get("data-analyst")["micro_itches_ko"][0]
    data_adj = pain_probe.artifact_adjustment("data-analyst", [data_micro])
    assert data_adj["adjustment_rows"][0]["template_fields_ko"] == "metric / numerator / denominator / comparison_window / first_check_sql"

    acct_micro = pain_probe.get("accountant")["micro_itches_ko"][0]
    acct_adj = pain_probe.artifact_adjustment("accountant", [acct_micro])
    assert acct_adj["adjustment_rows"][0]["template_fields_ko"] == "client / missing_doc / period / deadline / request_sentence / received_status"

    more_expected = {
        "office-admin": "request / department / owner / deadline / blocker / reminder_text",
        "call-center-agent": "call_reason / customer_emotion / confirmed_fact / promised_action / after_call_task",
        "teacher": "level / learning_goal / activity / scaffold / check_question",
        "nurse": "observation / intervention / patient_response / report_status / missing_check",
        "translator": "segment_id / source_text / mt_output / risk_type / fix_priority / reviewer_note",
        "graphic-designer": "brief_word / possible_meaning / clarifying_question / decision_needed / design_risk",
        "hr-manager": "candidate / jd_requirement / resume_evidence / concern / interview_question",
        "journalist": "release_title / news_value / affected_party / fact_to_check / reporting_next_step",
        "paralegal": "date / actor / event / evidence_file / issue_tag / attorney_question",
    }
    for job_id, fields in more_expected.items():
        row_micro = pain_probe.get(job_id)["micro_itches_ko"][0]
        row_adj = pain_probe.artifact_adjustment(job_id, [row_micro])
        assert row_adj["adjustment_rows"][0]["template_fields_ko"] == fields


def test_report_surfaces_pain_map_without_paywall_language():
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    h = report.render_html(job, {"type_name": "t", "emoji": "🧭", "tagline": "", "threat": "", "opportunity": ""})
    assert "진짜 가려운 업무" in h
    assert "제품 가설" in h
    assert "만들어줄 결과물" in h
    assert "/pain?job=video-editor" in h                                  # 가려움 온보딩으로 연결


def test_pain_intake_page_is_non_payment_onboarding():
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    p = painmap.build(job, limit=1)["pains"][0]
    micro = pain_probe.get("video-editor")["micro_itches_ko"][1]
    h = report.pain_intake_html(job, p["pain_id"], recommended_micro_itches=[micro, "임의 조작 문장"])
    assert h.rstrip().endswith("</html>")
    assert p["itch_ko"] in h
    assert "정말 가려운 지점" in h
    assert "왜 그냥 AI로 부족한가" in h
    assert "첫 10분 안도감" in h
    assert "혹시 이런 순간인가요?" in h
    assert "클라이언트 요청끼리 서로 충돌" in h
    assert "pi-probe-check" in h
    assert 'data-mi="2"' in h
    assert "많이 선택됨" in h
    assert f'value="{micro}" checked' in h
    assert "임의 조작 문장" not in h
    assert "piUpdateOfferLink" in h
    assert "이 페이지는 결제가 아닙니다" in h                              # 결제 오인 방지
    assert "fetch('/pain/intent'" in h                                    # 별도 수요 신호 저장
    assert "/pain-offer?job=video-editor" in h                            # 좁은 파일럿 오퍼로 연결
    assert "/privacy" in h


def test_pain_offer_page_scoped_and_honest():
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    p = painmap.build(job, limit=1)["pains"][0]
    micro = pain_probe.get("video-editor")["micro_itches_ko"][1]
    h = report.pain_offer_html(job, p["pain_id"], micro_itches=[micro])
    assert h.rstrip().endswith("</html>")
    assert report.PAIN_OFFER_NAME in h
    assert p["artifact_ko"] in h
    assert "이번 파일럿에서 먼저 줄일 작은 가려움" in h
    assert micro in h
    assert "선택 때문에 달라지는 결과물" in h
    assert "conflict_group / request_a / request_b / decision_needed / proposed_reply" in h
    assert "micro_itches:" in h
    assert "왜 돈 내고 줄이는가" in h
    assert "구매가 터지는 순간" in h
    assert "성공 기준" in h
    assert "사전신청은 결제가 아닙니다" in h
    assert "자동화된 전문 판단이나 성과 보장" in h
    assert "/privacy" in h and "/terms" in h
    bad = report.pain_offer_html(job, p["pain_id"], micro_itches=["임의 조작 문장"])
    assert "임의 조작 문장" not in bad
    assert "선택 때문에 달라지는 결과물" not in bad


def test_offer_page_links_legal_pages():
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    h = report.offer_html(job, grounded=True)
    assert h.rstrip().endswith("</html>")
    assert report.OFFER_NAME in h
    assert "/privacy" in h and "/terms" in h
    assert "사전신청은 결제가 아닙니다" in h


def test_fulfillment_video_editor_revision_pack_is_operational():
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    md = fulfillment.generate(job, "revision-chaos", sample=True)
    assert md.startswith("# 영상편집자 pain 파일럿 이행서")
    assert "타임코드별 수정 체크리스트" in md
    assert "클라이언트 회신문 초안" in md
    assert "버전 관리 규칙" in md
    assert "micro-itch 우선순위" in md
    assert "작업 초점" in md
    assert "추가 확인 질문" in md
    assert "micro-itch 산출물 조정" in md
    assert "source / timecode_or_scene / original_request / normalized_request / status" in md
    assert "conflict_group / request_a / request_b / decision_needed / proposed_reply" in md
    assert "전문 판단이나 성과 보장" in md
    assert "sample@example.com" not in md                               # 연락처 마스킹


def test_fulfillment_kickoff_request_and_three_day_checklist():
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    md = fulfillment.kickoff_plan(job, "revision-chaos", sample=True)
    assert md.startswith("# 영상편집자 pain 파일럿 킥오프")
    assert "## 고객에게 보낼 자료 요청 메시지" in md
    assert "현재 최신 영상본 링크 또는 파일명" in md
    assert "수정 요청 원문 전체" in md
    assert "자료를 받은 뒤 영업일 3일 안에 1차 초안을 전달" in md
    assert "## D0-D3 운영 체크리스트" in md
    assert "### D0 결제/신청 직후" in md
    assert "### D1 자료 검수와 질문" in md
    assert "### D2 산출물 초안 작성" in md
    assert "### D3 QA와 전달" in md
    assert "source / timecode_or_scene / original_request / normalized_request / status" in md
    assert "자동화된 전문 판단이나 성과 보장" in md
    assert "sample@example.com" not in md
    assert fulfillment.materials_for("video-editor", "revision-chaos")[0] == "현재 최신 영상본 링크 또는 파일명"


def test_fulfillment_target_job_playbooks_are_specific():
    scores = ScoringEngine(JOBS).score([], now=NOW)
    cases = [
        ("accountant", "missing-client-docs", ["누락자료 체크리스트", "고객 안내문"]),
        ("call-center-agent", "after-call-work", ["상담 요약", "이관 메모", "후속조치 등록 문장"]),
        ("data-analyst", "why-did-it-drop", ["원인 후보 트리", "SQL 초안", "이해관계자 설명문"]),
        ("graphic-designer", "revision-boundary", ["수정 범위표", "정중한 추가비 안내문"]),
        ("hr-manager", "resume-screening-rationale", ["후보자 요약표", "면접 확인 질문"]),
        ("journalist", "press-release-triage", ["보도자료 선별표", "추가취재 질문"]),
        ("junior-developer", "unknown-codebase-context", ["수정 영향도 맵", "PR 설명문 초안"]),
        ("marketer", "weekly-report-story", ["주간 성과 해석표", "다음 실험 3개", "보고서 문장"]),
        ("nurse", "charting-fatigue", ["차팅 문장 초안", "누락 확인 리스트"]),
        ("office-admin", "request-chasing", ["요청 추적 보드", "리마인드 메시지"]),
        ("paralegal", "case-timeline", ["사건 타임라인", "증거목록", "변호사 검토 질문"]),
        ("sales-rep", "pre-call-brief", ["3분 미팅 브리프", "발견 질문 7개"]),
        ("teacher", "differentiated-materials", ["수준별 활동지", "채점 루브릭"]),
        ("translator", "mtpe-quality-trap", ["번역 QA 리포트", "수정 우선순위"]),
        ("video-editor", "revision-chaos", ["타임코드별 수정 체크리스트", "클라이언트 회신문"]),
    ]
    for job_id, pain_id, markers in cases:
        md = fulfillment.generate(scores[job_id], pain_id, sample=True)
        for marker in markers:
            assert marker in md, (job_id, marker)
        assert "sample@example.com" not in md                            # 전용 샘플도 연락처 마스킹
        assert "결과물 초안 작성" not in md                               # 공통 샘플 테이블로 퇴행 금지
    dev_md = fulfillment.generate(scores["junior-developer"], "unknown-codebase-context", sample=True)
    assert "micro-itch 산출물 조정" in dev_md
    assert "entrypoint / likely_file / reason / unknown / first_probe_command" in dev_md
    assert "change_summary / why / risk / test_command / rollback_note" in dev_md


def test_fulfillment_templates_cover_all_top_job_pains():
    scores = ScoringEngine(JOBS).score([], now=NOW)
    for job in scores.values():
        pain = painmap.build(job, limit=1)["pains"][0]
        md = fulfillment.generate(job, pain["pain_id"])
        assert job["job_name_ko"] in md
        assert pain["artifact_ko"] in md
        assert "금지/가드레일" in md
        assert "자동화된 전문 판단" in md


def test_fulfillment_builds_from_stored_pain_intent():
    import tempfile
    old = store.PAIN_INTENT_FILE
    tf = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tf.close()
    store.PAIN_INTENT_FILE = tf.name
    try:
        store.append_pain_intent({
            "contact": "realuser@example.com",
            "job": "marketer",
            "pain_id": "weekly-report-story",
            "role_type": "employee",
            "sample_available": "redacted",
            "situation": "주간 리포트에서 원인 설명과 다음 실험을 한 장으로 정리해야 합니다.",
            "micro_itches": ["보고서는 많이 쓰지만 다음 주 실험으로 연결되지 않는다."],
        })
        row = fulfillment.select_intent("latest", job_id="marketer")
        md = fulfillment.build_from_intent(row)
        assert "마케터 pain 파일럿 이행서" in md
        assert "주간 리포트에서 원인 설명" in md
        assert "보고서는 많이 쓰지만 다음 주 실험으로 연결되지 않는다." in md
        assert "micro-itch 우선순위" in md
        assert "이번 납품은 '보고서는 많이 쓰지만 다음 주 실험으로 연결되지 않는다.'" in md
        assert "micro-itch 산출물 조정" in md
        assert "hypothesis / action / owner / success_metric / stop_rule" in md
        assert "주간 성과 해석표" in md
        assert "re***@example.com" in md
        assert "realuser@example.com" not in md
        assert "자동화된 전문 판단" in md
    finally:
        store.PAIN_INTENT_FILE = old
        os.unlink(tf.name)


def test_fulfillment_intent_selection_is_safe():
    import tempfile
    old = store.PAIN_INTENT_FILE
    tf = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tf.close()
    store.PAIN_INTENT_FILE = tf.name
    try:
        store.append_pain_intent({
            "contact": "a@example.com", "job": "video-editor", "pain_id": "revision-chaos",
            "role_type": "freelancer", "sample_available": "yes", "situation": "첫 요청",
        })
        store.append_pain_intent({
            "contact": "b@example.com", "job": "video-editor", "pain_id": "revision-chaos",
            "role_type": "freelancer", "sample_available": "yes", "situation": "둘째 요청",
        })
        assert fulfillment.select_intent("1")["situation"] == "첫 요청"
        assert fulfillment.select_intent("-1")["situation"] == "둘째 요청"
        for bad in ["0", "999", "nope"]:
            raised = False
            try:
                fulfillment.select_intent(bad)
            except ValueError:
                raised = True
            assert raised, bad
        raised = False
        try:
            fulfillment.select_intent("latest", job_id="marketer")
        except ValueError:
            raised = True
        assert raised
    finally:
        store.PAIN_INTENT_FILE = old
        os.unlink(tf.name)


def test_fulfillment_queue_import_status_and_render():
    import tempfile
    old_intent = store.PAIN_INTENT_FILE
    old_queue = store.FULFILLMENT_FILE
    intent = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    queue = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    intent.close()
    queue.close()
    os.unlink(queue.name)
    store.PAIN_INTENT_FILE = intent.name
    store.FULFILLMENT_FILE = queue.name
    try:
        micro = pain_probe.get("video-editor")["micro_itches_ko"][0]
        store.append_pain_intent({
            "contact": "queueuser@example.com",
            "job": "video-editor",
            "pain_id": "revision-chaos",
            "role_type": "freelancer",
            "sample_available": "redacted",
            "situation": "수정 요청이 흩어져 버전 관리가 어렵습니다.",
            "micro_itches": [micro],
        })
        new_jobs = fulfillment_queue.import_intents()
        assert len(new_jobs) == 1
        assert new_jobs[0]["micro_itches"] == [micro]
        assert fulfillment_queue.import_intents() == []                 # 중복 import 방지
        job = fulfillment_queue.next_job()
        assert job["status"] == "queued"
        assert job["due_at"] and job["sla_business_days"] == 3
        assert job["fulfillment_id"].startswith("fq_")
        md = fulfillment_queue.render_job(job["fulfillment_id"])
        assert "수정 요청이 흩어져 버전 관리" in md
        assert "micro-itch 산출물 조정" in md
        assert "qu***@example.com" in md
        assert "queueuser@example.com" not in md
        updated = fulfillment_queue.set_status(job["fulfillment_id"], "working", note="자료 확인 중")
        assert updated["status"] == "working"
        assert updated["notes"] == "자료 확인 중"
        assert fulfillment_queue.next_job() is None
        updated = fulfillment_queue.set_status(job["fulfillment_id"], "delivered")
        assert updated["history"][-1]["status"] == "delivered"
    finally:
        store.PAIN_INTENT_FILE = old_intent
        store.FULFILLMENT_FILE = old_queue
        for path in (intent.name, queue.name):
            if os.path.exists(path):
                os.unlink(path)


def test_fulfillment_queue_sla_due_date_and_overdue():
    friday = "2026-06-19T09:00:00+00:00"  # Friday
    assert fulfillment_queue.add_business_days(friday, 3).startswith("2026-06-24")  # next Wednesday
    open_row = {"status": "working", "due_at": "2026-06-20T00:00:00+00:00"}
    done_row = {"status": "delivered", "due_at": "2026-06-20T00:00:00+00:00"}
    assert fulfillment_queue.is_overdue(open_row, now="2026-06-21T00:00:00+00:00")
    assert not fulfillment_queue.is_overdue(done_row, now="2026-06-21T00:00:00+00:00")


def test_fulfillment_queue_next_prioritizes_earliest_due():
    import tempfile
    old_queue = store.FULFILLMENT_FILE
    queue = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    queue.close()
    rows = [
        {"fulfillment_id": "fq_late", "status": "queued", "due_at": "2026-06-25T18:00:00+00:00",
         "created_at": "2026-06-20T00:00:00+00:00"},
        {"fulfillment_id": "fq_early", "status": "queued", "due_at": "2026-06-22T18:00:00+00:00",
         "created_at": "2026-06-21T00:00:00+00:00"},
        {"fulfillment_id": "fq_working", "status": "working", "due_at": "2026-06-01T18:00:00+00:00",
         "created_at": "2026-06-01T00:00:00+00:00"},
    ]
    with open(queue.name, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(__import__("json").dumps(row, ensure_ascii=False) + "\n")
    store.FULFILLMENT_FILE = queue.name
    try:
        assert fulfillment_queue.next_job()["fulfillment_id"] == "fq_early"
    finally:
        store.FULFILLMENT_FILE = old_queue
        os.unlink(queue.name)


def test_fulfillment_queue_operational_report_counts_bottlenecks():
    import tempfile
    old_payments = store.PAYMENTS_FILE
    old_queue = store.FULFILLMENT_FILE
    payments = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    payments.close()
    queue = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    queue.close()
    memo_path = queue.name + ".md"
    memo_dir = queue.name + "_reports"
    video_micro = pain_probe.get("video-editor")["micro_itches_ko"][0]
    marketer_micro = pain_probe.get("marketer")["micro_itches_ko"][0]
    rows = [
        {"fulfillment_id": "fq_overdue", "status": "working", "due_at": "2026-06-18T18:00:00+00:00",
         "created_at": "2026-06-15T00:00:00+00:00", "job": "video-editor", "pain_id": "revision-chaos",
         "micro_itches": [video_micro]},
        {"fulfillment_id": "fq_today", "status": "queued", "due_at": "2026-06-20T18:00:00+00:00",
         "created_at": "2026-06-18T00:00:00+00:00", "job": "video-editor", "pain_id": "revision-chaos",
         "micro_itches": [video_micro]},
        {"fulfillment_id": "fq_later", "status": "queued", "due_at": "2026-06-24T18:00:00+00:00",
         "created_at": "2026-06-19T00:00:00+00:00", "job": "marketer", "pain_id": "weekly-report-story",
         "micro_itches": [marketer_micro]},
        {"fulfillment_id": "fq_done", "status": "delivered", "due_at": "2026-06-01T18:00:00+00:00",
         "created_at": "2026-05-29T00:00:00+00:00", "job": "sales-rep", "pain_id": "pre-call-brief",
         "micro_itches": [video_micro]},
    ]
    with open(queue.name, "w", encoding="utf-8") as f:
        import json
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    store.PAYMENTS_FILE = payments.name
    store.FULFILLMENT_FILE = queue.name
    try:
        store.save_payment("order-missing", "video-editor", 39000, "paid", extra={
            "src": "webhook",
            "pain_release_job": "video-editor",
            "pain_release_pain": "revision-chaos",
            "fulfillment_id": "fq_pay_missing",
            "kickoff_path": os.path.join(memo_dir, "missing.md"),
        })
        rep = fulfillment_queue.operational_report(now="2026-06-20T09:00:00+00:00", limit=2)
        assert rep["total"] == 4
        assert rep["open"] == 3
        assert rep["overdue"] == 1
        assert rep["due_today"] == 1
        assert rep["status_counts"]["delivered"] == 1
        assert rep["by_job"]["video-editor"] == 2
        assert rep["by_pain"]["video-editor/revision-chaos"] == 2
        assert rep["by_micro_itch"][f"video-editor::{video_micro}"] == 2
        assert rep["by_micro_itch"][f"marketer::{marketer_micro}"] == 1
        assert rep["micro_actions"][0]["job"] == "video-editor"
        assert rep["micro_actions"][0]["count"] == 2
        assert rep["micro_actions"][0]["artifact_slot_ko"] == "수정 체크리스트 상단"
        assert rep["micro_actions"][0]["template_fields_ko"] == "source / timecode_or_scene / original_request / normalized_request / status"
        assert video_micro in rep["micro_actions"][0]["first_question_ko"]
        assert "마지막으로 터진 실제 상황" in rep["micro_actions"][0]["first_question_ko"]
        assert rep["micro_actions"][1]["job"] == "marketer"
        assert rep["micro_actions"][1]["template_fields_ko"] == "metric / change / segment / cause_candidate / confidence / next_check"
        assert [r["fulfillment_id"] for r in rep["next"]] == ["fq_overdue", "fq_today"]
        assert rep["paid_reconciliation"]["paid_pain_orders"] == 1
        assert rep["paid_reconciliation"]["ok"] == 0
        assert rep["paid_reconciliation"]["issue_counts"]["missing_queue"] == 1
        assert rep["paid_reconciliation"]["issue_counts"]["missing_kickoff"] == 1
        md = fulfillment_queue.report_markdown(now="2026-06-20T09:00:00+00:00", limit=2)
        assert "# pain 파일럿 운영 메모 - 2026-06-20" in md
        assert "paid pain orders/ok/issues: 1 / 0 / 2" in md
        assert "## paid pain 이행 이슈" in md
        assert "missing_queue" in md and "missing_kickoff" in md
        assert "## 다음 운영 액션" in md
        assert "source / timecode_or_scene / original_request / normalized_request / status" in md
        assert "마지막으로 터진 실제 상황" in md
        saved = fulfillment_queue.save_report_memo(
            out_path=memo_path,
            now="2026-06-20T09:00:00+00:00",
            limit=2,
        )
        assert saved == memo_path
        with open(memo_path, encoding="utf-8") as f:
            saved_md = f.read()
        assert saved_md == md
        os.makedirs(memo_dir, exist_ok=True)
        older_path = os.path.join(memo_dir, "2026-06-19.md")
        with open(older_path, "w", encoding="utf-8") as f:
            f.write(
                "# pain 파일럿 운영 메모 - 2026-06-19\n\n"
                "- total/open/overdue/due_today: 2 / 1 / 0 / 0\n\n"
                "## micro-itch별 open\n\n"
                f"- video-editor::{video_micro}: 1\n"
            )
        latest_path = os.path.join(memo_dir, "2026-06-20.md")
        fulfillment_queue.save_report_memo(
            out_path=latest_path,
            now="2026-06-20T09:00:00+00:00",
            limit=2,
        )
        weekly = fulfillment_queue.weekly_summary(report_dir=memo_dir, days=7)
        assert weekly["snapshots"] == 2
        assert weekly["open_delta"] == 2
        assert weekly["overdue_delta"] == 1
        assert weekly["top_pains"]["video-editor/revision-chaos"] == 2
        assert weekly["top_micro_itches"][f"video-editor::{video_micro}"] == 3
        assert weekly["paid_latest"]["orders"] == 1
        assert weekly["paid_latest"]["issues"] == 2
        assert weekly["paid_issue_counts"]["missing_queue"] == 1
        assert weekly["paid_issue_counts"]["missing_kickoff"] == 1
        assert weekly["paid_issue_delta"] == 2
        assert weekly["productization_priorities"][0]["job"] == "video-editor"
        assert weekly["productization_priorities"][0]["pain_id"] == "revision-chaos"
        assert weekly["productization_priorities"][0]["demand_count"] == 3
        assert weekly["productization_priorities"][0]["artifact_slot_ko"] == "수정 체크리스트 상단"
        assert weekly["productization_priorities"][0]["template_fields_ko"] == "source / timecode_or_scene / original_request / normalized_request / status"
        assert "pain-offer" in weekly["productization_priorities"][0]["next_product_move_ko"]
        weekly_md = fulfillment_queue.weekly_summary_markdown(report_dir=memo_dir, days=7)
        assert "pain 파일럿 주간 운영 요약" in weekly_md
        assert "open 변화: +2" in weekly_md
        assert "paid pain 이행 경고" in weekly_md
        assert "최신 paid pain orders/ok/issues: 1 / 0 / 2" in weekly_md
        assert "reconcile-paid" in weekly_md
        assert "다음 주 제품화 우선순위" in weekly_md
        assert "수정 체크리스트 상단" in weekly_md
        draft = fulfillment_queue.productization_draft_markdown(report_dir=memo_dir, days=7, limit=1)
        assert "# 다음 주 micro-itch 제품화 초안" in draft
        assert "video-editor narrow pain-offer" in draft
        assert "/pain-offer?job=video-editor&pain=revision-chaos" in draft
        assert "Hero headline:" in draft
        assert video_micro in draft
        assert "수정 체크리스트 상단" in draft
        assert "source / timecode_or_scene / original_request / normalized_request / status" in draft
        assert "이 반복 업무 줄이기 파일럿 신청" in draft
        product_path = os.path.join(memo_dir, "productization-2026-06-20.md")
        saved_product = fulfillment_queue.save_productization_draft(
            report_dir=memo_dir,
            out_path=product_path,
            now="2026-06-20T09:00:00+00:00",
            days=7,
            limit=1,
        )
        assert saved_product == product_path
        with open(product_path, encoding="utf-8") as f:
            assert f.read() == draft
        assert len(fulfillment_queue.memo_snapshots(report_dir=memo_dir, days=7)) == 2
        preview_dir = os.path.join(memo_dir, "preview")
        preview_paths = fulfillment_queue.save_productization_previews(
            report_dir=memo_dir,
            out_dir=preview_dir,
            now="2026-06-20T09:00:00+00:00",
            days=7,
            limit=1,
        )
        assert os.path.join(preview_dir, "01-video-editor-revision-chaos.html") in preview_paths
        assert os.path.join(preview_dir, "index.md") in preview_paths
        with open(os.path.join(preview_dir, "01-video-editor-revision-chaos.html"), encoding="utf-8") as f:
            preview_html = f.read()
        assert report.PAIN_OFFER_NAME in preview_html
        assert video_micro in preview_html
        assert "수정 체크리스트 상단" in preview_html
        with open(os.path.join(preview_dir, "index.md"), encoding="utf-8") as f:
            preview_index = f.read()
        assert "video-editor / revision-chaos" in preview_index
        assert "01-video-editor-revision-chaos.html" in preview_index
    finally:
        store.PAYMENTS_FILE = old_payments
        store.FULFILLMENT_FILE = old_queue
        for path in (payments.name, queue.name, memo_path):
            if os.path.exists(path):
                os.unlink(path)
        if os.path.isdir(memo_dir):
            for name in os.listdir(memo_dir):
                path = os.path.join(memo_dir, name)
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.unlink(path)
            os.rmdir(memo_dir)


def test_server_offer_recommendation_uses_productized_micro_itch():
    import tempfile
    old_report_dir = store.FULFILLMENT_REPORT_DIR
    old_intent = store.PAIN_INTENT_FILE
    memo_dir = tempfile.mkdtemp()
    intent_file = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    intent_file.close()
    video_micro = pain_probe.get("video-editor")["micro_itches_ko"][0]
    intent_micro = pain_probe.get("video-editor")["micro_itches_ko"][1]
    try:
        store.FULFILLMENT_REPORT_DIR = memo_dir
        store.PAIN_INTENT_FILE = intent_file.name
        with open(os.path.join(memo_dir, "2026-06-20.md"), "w", encoding="utf-8") as f:
            f.write(
                "# pain 파일럿 운영 메모 - 2026-06-20\n\n"
                "- total/open/overdue/due_today: 4 / 4 / 0 / 0\n\n"
                "## micro-itch별 open\n\n"
                f"- video-editor::{video_micro}: 4\n"
            )
        assert fulfillment_queue.productized_micro_itches("video-editor", limit=1) == [video_micro]
        assert server._recommended_micro_itches("video-editor", "revision-chaos", limit=1) == [video_micro]
        job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
        pain = painmap.build(job, limit=1)["pains"][0]
        h = report.pain_offer_html(job, pain["pain_id"], micro_itches=[video_micro])
        assert video_micro in h
        assert "수정 체크리스트 상단" in h
        store.append_pain_intent({
            "ts": "2026-06-20T10:00:00Z",
            "contact": "specific@example.com",
            "job": "video-editor",
            "pain_id": "revision-chaos",
            "role_type": "freelancer",
            "sample_available": "yes",
            "situation": "충돌하는 수정 요청을 정리해야 합니다.",
            "micro_itches": [intent_micro],
        })
        assert server._recommended_micro_itches("video-editor", "revision-chaos", limit=1) == [intent_micro]
    finally:
        store.FULFILLMENT_REPORT_DIR = old_report_dir
        store.PAIN_INTENT_FILE = old_intent
        if os.path.exists(intent_file.name):
            os.unlink(intent_file.name)
        if os.path.isdir(memo_dir):
            shutil.rmtree(memo_dir)


def test_fulfillment_queue_rejects_bad_status_and_unknown_id():
    import tempfile
    old_queue = store.FULFILLMENT_FILE
    queue = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    queue.close()
    store.FULFILLMENT_FILE = queue.name
    try:
        for args in [("missing", "working"), ("missing", "bad")]:
            raised = False
            try:
                fulfillment_queue.set_status(args[0], args[1])
            except ValueError:
                raised = True
            assert raised, args
    finally:
        store.FULFILLMENT_FILE = old_queue
        if os.path.exists(queue.name):
            os.unlink(queue.name)


def test_fulfillment_rejects_unknown_pain():
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    raised = False
    try:
        fulfillment.generate(job, "not-a-pain")
    except ValueError:
        raised = True
    assert raised


# ── server ────────────────────────────────────────────────────────────
def test_server_match_job():
    assert server._match_job("영상편집자") == "video-editor"
    assert server._match_job("관련없는말") is None


def test_server_kakao_malformed_no_crash():
    for bad in [[], None, {}, {"userRequest": None},
                {"userRequest": {"user": "x", "utterance": 5}}]:
        out = server.handle_kakao(bad)
        assert "version" in out and out["template"]["outputs"]      # 항상 유효 카카오 응답


def test_server_kakao_job_selection_stores_mapping():
    _clear_users()
    old = os.environ.pop("GEMINI_API_KEY", None)                    # 오프라인 강제(요약은 폴백)
    try:
        out = server.handle_kakao({"userRequest": {"utterance": "주니어 개발자",
                                                   "user": {"id": "tu1"}}})
        txt = out["template"]["outputs"][0]["simpleText"]["text"]
        assert "주니어 개발자" in txt
        assert store.get_user_job("tu1") == "junior-developer"
    finally:
        if old:
            os.environ["GEMINI_API_KEY"] = old
        _clear_users()


def test_server_rate_limit():
    server._rl.clear()
    flags = [server._rate_ok("9.9.9.9") for _ in range(server.RATE_LIMIT + 2)]
    assert flags[0] is True and flags[-1] is False                  # 초과 시 차단
    server._rl.clear()


def test_server_report_quick_reply_not_deadend():
    _clear_users()
    old = os.environ.pop("GEMINI_API_KEY", None)
    saved = server.REPORT_BASE_URL
    server.REPORT_BASE_URL = "https://x.test"
    try:
        server.handle_kakao({"userRequest": {"utterance": "주니어 개발자", "user": {"id": "ru1"}}})
        out = server.handle_kakao({"userRequest": {"utterance": "리포트 보기", "user": {"id": "ru1"}}})
        txt = out["template"]["outputs"][0]["simpleText"]["text"]
        assert "리포트" in txt and "report?user=ru1" in txt          # 데드엔드 아님 + 링크 포함
    finally:
        server.REPORT_BASE_URL = saved
        if old:
            os.environ["GEMINI_API_KEY"] = old
        _clear_users()


def _with_temp_pain_intents(fn):
    import tempfile
    old = store.PAIN_INTENT_FILE
    tf = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tf.close()
    store.PAIN_INTENT_FILE = tf.name
    try:
        fn()
    finally:
        store.PAIN_INTENT_FILE = old
        os.unlink(tf.name)


def test_server_pain_intent_validates_and_stores_once():
    def body():
        job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
        pid = painmap.build(job, limit=1)["pains"][0]["pain_id"]
        valid_micro = pain_probe.get("video-editor")["micro_itches_ko"][1]
        assert server._micro_itches_from_indexes("video-editor", ["2", "999", "bad"]) == [valid_micro]
        payload = {"contact": "a@example.com", "job": "video-editor", "pain_id": pid,
                   "role_type": "freelancer", "sample_available": "redacted",
                   "situation": "수정 요청이 흩어집니다", "offer_type": "pain-pack",
                   "micro_itches": [valid_micro, "임의 조작 문장"], "consent": True}
        code, obj = server.handle_pain_intent(payload, "1.2.3.4")
        assert code == 200 and obj["ok"] is True
        assert store.pain_intent_count() == 1
        assert pain_intents.rows()[0]["offer_type"] == "pain-pack"
        assert pain_intents.rows()[0]["micro_itches"] == [valid_micro]   # atlas 밖 문장 저장 금지
        assert server._recommended_micro_itches("video-editor", pid) == [valid_micro]
        code, obj = server.handle_pain_intent(payload, "1.2.3.4")
        assert code == 200 and obj["ok"] is True
        assert store.pain_intent_count() == 1                       # contact+job+pain 중복 제거
    _with_temp_pain_intents(body)


def test_server_pain_intent_rejects_bad_inputs():
    def body():
        good = {"contact": "a@example.com", "job": "video-editor", "pain_id": "nope",
                "role_type": "employee", "sample_available": "yes", "consent": True}
        assert server.handle_pain_intent({**good, "consent": False}, "1.1.1.1")[0] == 400
        assert server.handle_pain_intent({**good, "contact": "bad contact"}, "1.1.1.1")[0] == 400
        assert server.handle_pain_intent({**good, "job": "no-job"}, "1.1.1.1")[0] == 400
        assert server.handle_pain_intent(good, "1.1.1.1")[0] == 400       # pain_id 검증
        assert server.handle_pain_intent({**good, "hp_url": "bot"}, "1.1.1.1")[0] == 200
        assert store.pain_intent_count() == 0                             # honeypot은 저장 안 함
    _with_temp_pain_intents(body)


def test_pain_intents_rank_and_masking():
    def body():
        rows = [
            {"ts": "2026-06-06T00:00:00Z", "contact": "alpha@example.com",
             "job": "video-editor", "pain_id": "revision-chaos",
             "role_type": "freelancer", "sample_available": "redacted",
             "situation": "수정요청이 흩어집니다",
             "micro_itches": ["수정 요청이 카톡, 메일, 댓글, 캡처 이미지에 흩어져 타임라인에 다시 꽂아야 한다."]},
            {"ts": "2026-06-06T00:01:00Z", "contact": "beta@example.com",
             "job": "video-editor", "pain_id": "revision-chaos",
             "role_type": "employee", "sample_available": "yes",
             "situation": "타임코드 정리가 어렵습니다",
             "micro_itches": ["수정 요청이 카톡, 메일, 댓글, 캡처 이미지에 흩어져 타임라인에 다시 꽂아야 한다.",
                              "타임코드 없이 '여기 좀 빠르게' 같은 피드백이 와서 영상을 다시 훑어야 한다."]},
            {"ts": "2026-06-06T00:02:00Z", "contact": "gamma@example.com",
             "job": "marketer", "pain_id": "weekly-report-story",
             "role_type": "employee", "sample_available": "no",
             "situation": ""},
        ]
        for r in rows:
            store.append_pain_intent(r)
        ranked = pain_intents.ranked_pains(pain_intents.rows())
        assert ranked[0]["job"] == "video-editor"
        assert ranked[0]["pain_id"] == "revision-chaos"
        assert ranked[0]["count"] == 2 and ranked[0]["unique_contacts"] == 2
        micro = pain_intents.ranked_micro_itches(pain_intents.rows())
        assert micro[0]["job"] == "video-editor"
        assert micro[0]["count"] == 2 and micro[0]["unique_contacts"] == 2
        rec = pain_intents.recommended_micro_itches("video-editor", "revision-chaos")
        assert rec[0] == "수정 요청이 카톡, 메일, 댓글, 캡처 이미지에 흩어져 타임라인에 다시 꽂아야 한다."
        assert len(rec) == 2
        assert pain_intents.recommended_micro_itches("video-editor", "other-pain", fallback_to_job=False) == []
        assert pain_intents.recommended_micro_itches("video-editor", "other-pain") == rec
        assert pain_intents.recommended_micro_itches("no-job") == []
        assert pain_intents._mask("alpha@example.com") == "al***@example.com"
        assert pain_intents._csv_safe("=cmd") == "'=cmd"                 # CSV 수식 인젝션 방어
    _with_temp_pain_intents(body)


def test_pain_intents_summary_empty(capture=None):
    import io
    old = sys.stdout
    def body():
        sys.stdout = io.StringIO()
        try:
            pain_intents.summary()
            out = sys.stdout.getvalue()
        finally:
            sys.stdout = old
        assert "총 pain intents: 0" in out
        assert "결제 아님" in out
    _with_temp_pain_intents(body)


# ── store ─────────────────────────────────────────────────────────────
def _clear_users():
    if os.path.exists(store.USERS_FILE):
        os.remove(store.USERS_FILE)


def test_store_user_mapping():
    _clear_users()
    store.set_user_job("a", "video-editor")
    store.set_user_job("b", "video-editor")
    assert store.get_user_job("a") == "video-editor"
    assert set(store.users_by_job("video-editor")) == {"a", "b"}
    _clear_users()


def test_store_caches_roundtrip():
    files = (store.STRATEGIST_FILE, store.ACTIONPLAN_FILE, store.NOTIFIED_FILE)
    for f in files:
        if os.path.exists(f):
            os.remove(f)
    store.save_strategist("j", {"type_name": "T"})
    store.save_actionplan("j", {"source": "gemini"})
    store.set_notified("j", "ts1")
    assert store.get_strategist("j") == {"type_name": "T"}
    assert store.get_actionplan("j") == {"source": "gemini"}
    assert store.get_notified("j") == "ts1"
    assert store.get_strategist("none") is None                     # 미존재 → None
    for f in files:
        if os.path.exists(f):
            os.remove(f)


def test_store_score_history_and_delta():
    f = os.path.join(DATA, "scores", "tj.jsonl")
    if os.path.exists(f):
        os.remove(f)
    store.append_score("tj", {"index": 50.0}, ts="2026-06-05T00:00:00Z")
    store.append_score("tj", {"index": 55.0}, ts="2026-06-06T00:00:00Z")
    assert store.latest_score("tj")["index"] == 55.0
    assert store.delta_since_prev("tj", 60.0) == 5.0                 # 60 - 55
    assert len(store.score_history("tj")) == 2
    if os.path.exists(f):
        os.remove(f)


# ── gemini_client ─────────────────────────────────────────────────────
def test_gemini_chain_config():
    assert gemini_client.CHAINS["premium"][0].startswith("gemini-3")   # 최신 우선
    assert gemini_client.CHAINS["premium"][-1] == "gemini-2.5-flash"    # 안정 fallback 종단
    assert gemini_client.CHAINS["routine"][-1] == "gemini-2.5-flash"


def test_gemini_key_required_fast_fail():
    import time
    old = os.environ.pop("GEMINI_API_KEY", None)
    try:
        t = time.time()
        raised = False
        try:
            gemini_client.generate("hi", tier="premium")
        except RuntimeError:
            raised = True
        assert raised and (time.time() - t) < 2                      # 즉시 실패(네트워크 루프 없음)
    finally:
        if old:
            os.environ["GEMINI_API_KEY"] = old


# ── 결제 검증 (Phase 5 — 진짜 지불주체는 서명검증 웹훅으로만) ──────────────
def _with_temp_payments(fn):
    """store.PAYMENTS_FILE을 임시 경로로 격리하고 실행(실데이터 오염 방지)."""
    import tempfile
    old = store.PAYMENTS_FILE
    tf = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    tf.close()
    store.PAYMENTS_FILE = tf.name
    try:
        fn()
    finally:
        store.PAYMENTS_FILE = old
        os.unlink(tf.name)


def test_payment_reported_never_counts_as_paid():
    def body():
        store.save_payment("o1", "video-editor", 99000, "reported", extra={"src": "redirect"})
        assert store.paid_count() == 0                       # 클라이언트 리다이렉트(reported)=지불주체 아님
        store.save_payment("o2", "video-editor", 99000, "paid", extra={"src": "webhook"})
        assert store.paid_count() == 1                       # 서명검증 webhook(paid)만 카운트
    _with_temp_payments(body)


def test_payment_refund_overrides_paid():
    def body():
        store.save_payment("o1", "x", 99000, "paid")
        assert store.paid_count() == 1
        store.save_payment("o1", "x", 99000, "refunded")     # 같은 주문 환불 → 최종 refunded
        assert store.paid_count() == 0                       # 환불은 지불주체에서 제외
        assert store.payment_status_counts().get("refunded") == 1
    _with_temp_payments(body)


def test_payment_signature_gate():
    import hashlib
    import hmac
    raw = b'{"orderId":"o1","status":"DONE","amount":99000}'
    old = server.PAYMENT_WEBHOOK_SECRET
    try:
        server.PAYMENT_WEBHOOK_SECRET = ""                   # 시크릿 없으면 절대 통과 금지
        assert server._payment_sig_ok(raw, "anything") is False
        server.PAYMENT_WEBHOOK_SECRET = "s3cr3t"
        good = hmac.new(b"s3cr3t", raw, hashlib.sha256).hexdigest()
        assert server._payment_sig_ok(raw, good) is True     # 올바른 HMAC만 통과
        assert server._payment_sig_ok(raw, good[:-1] + "0") is False  # 위조 서명 거부
        assert server._payment_sig_ok(raw + b"x", good) is False      # 본문 변조 거부
    finally:
        server.PAYMENT_WEBHOOK_SECRET = old


def test_payment_status_classify():
    assert server._classify_pay_status("DONE") == "paid"
    assert server._classify_pay_status("PAID") == "paid"
    assert server._classify_pay_status("CANCELED") == "refunded"
    assert server._classify_pay_status("APPROVED") == "failed"   # 승인≠캡처 → paid 아님(좁힘)
    assert server._classify_pay_status("foobar") == "failed"     # 모르는 값=보수적 failed
    assert server._classify_pay_status("") == "failed"


def test_payment_amount_validation():
    old = server.PAYMENT_EXPECTED_AMOUNT
    old_pain_url = server.PAIN_PAYMENT_URL
    old_pain_amount = server.PAIN_PAYMENT_EXPECTED_AMOUNT
    old_allowed = server.PAYMENT_ALLOWED_AMOUNTS
    try:
        server.PAIN_PAYMENT_URL = ""
        server.PAYMENT_ALLOWED_AMOUNTS = ""
        server.PAYMENT_EXPECTED_AMOUNT = 99000
        assert server._finalize_pay_status("paid", 99000) == "paid"
        assert server._finalize_pay_status("paid", 0) == "failed"      # 0원
        assert server._finalize_pay_status("paid", -5) == "failed"     # 음수
        assert server._finalize_pay_status("paid", None) == "failed"   # 누락
        assert server._finalize_pay_status("paid", True) == "failed"   # bool 차단
        assert server._finalize_pay_status("paid", 50000) == "failed"  # 기대금액 불일치
        assert server._finalize_pay_status("refunded", 99000) == "refunded"  # paid 외엔 그대로
        server.PAIN_PAYMENT_URL = "https://pay.example/pain"
        server.PAIN_PAYMENT_EXPECTED_AMOUNT = 39000
        assert server._finalize_pay_status("paid", 39000) == "paid"    # pain 파일럿 링크 켠 경우만 허용
        server.PAYMENT_ALLOWED_AMOUNTS = "99000,29000"
        assert server._finalize_pay_status("paid", 29000) == "paid"    # 명시 목록 우선
        assert server._finalize_pay_status("paid", 39000) == "failed"
        server.PAYMENT_EXPECTED_AMOUNT = 0
        server.PAYMENT_ALLOWED_AMOUNTS = ""
        server.PAIN_PAYMENT_URL = ""
        assert server._finalize_pay_status("paid", 12345) == "paid"    # 기대금액 미설정+양수→통과
    finally:
        server.PAYMENT_EXPECTED_AMOUNT = old
        server.PAIN_PAYMENT_URL = old_pain_url
        server.PAIN_PAYMENT_EXPECTED_AMOUNT = old_pain_amount
        server.PAYMENT_ALLOWED_AMOUNTS = old_allowed


def test_payment_paid_pain_creates_fulfillment_job_and_kickoff():
    import tempfile
    old_payments = store.PAYMENTS_FILE
    old_queue = store.FULFILLMENT_FILE
    old_report_dir = store.FULFILLMENT_REPORT_DIR
    old_release_job = server.PAIN_RELEASE_JOB
    old_release_pain = server.PAIN_RELEASE_PAIN
    old_pain_amount = server.PAIN_PAYMENT_EXPECTED_AMOUNT
    payments = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    payments.close()
    queue = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
    queue.close()
    report_dir = tempfile.mkdtemp()
    try:
        store.PAYMENTS_FILE = payments.name
        store.FULFILLMENT_FILE = queue.name
        store.FULFILLMENT_REPORT_DIR = report_dir
        server.PAIN_RELEASE_JOB = "video-editor"
        server.PAIN_RELEASE_PAIN = "revision-chaos"
        server.PAIN_PAYMENT_EXPECTED_AMOUNT = 39000
        meta = server._paid_pain_fulfillment_meta(
            "order-pain-1",
            39000,
            {"customerEmail": "paid@example.com"},
            "paid",
        )
        assert meta["pain_release_job"] == "video-editor"
        assert meta["pain_release_pain"] == "revision-chaos"
        assert meta["fulfillment_id"].startswith("fq_pay_")
        assert os.path.exists(meta["kickoff_path"])
        jobs = fulfillment_queue.read_jobs()
        assert len(jobs) == 1
        assert jobs[0]["payment_order_id"] == "order-pain-1"
        assert jobs[0]["payment_amount"] == 39000
        assert jobs[0]["offer_type"] == "pain-paid"
        assert jobs[0]["status"] == "queued"
        with open(meta["kickoff_path"], encoding="utf-8") as f:
            kickoff = f.read()
        assert "고객에게 보낼 자료 요청 메시지" in kickoff
        assert "paid@example.com" not in kickoff
        assert "pa***@example.com" in kickoff
        store.save_payment("order-pain-1", "video-editor", 39000, "paid", extra={
            "src": "webhook",
            "pain_release_job": "video-editor",
            "pain_release_pain": "revision-chaos",
            "fulfillment_id": meta["fulfillment_id"],
            "kickoff_path": meta["kickoff_path"],
        })
        rec = fulfillment_queue.paid_reconciliation(now="2026-06-20T09:00:00+00:00")
        assert rec["paid_pain_orders"] == 1
        assert rec["ok"] == 1
        assert rec["rows"][0]["order_id"] == "order-pain-1"
        assert rec["rows"][0]["queue_status"] == "queued"
        assert rec["rows"][0]["kickoff_exists"] is True
        assert rec["rows"][0]["checkpoint_done_count"] == 0
        assert rec["rows"][0]["next_checkpoint"] == "kickoff_sent"
        assert rec["rows"][0]["issues"] == []
        rec_md = fulfillment_queue.paid_reconciliation_markdown(now="2026-06-20T09:00:00+00:00")
        assert "paid pain 주문 이행 대조" in rec_md
        assert "order-pain-1" in rec_md
        assert "fq_pay_" in rec_md
        assert "0/4 kickoff 발송" in rec_md
        cp1 = fulfillment_queue.set_checkpoint(
            "order-pain-1",
            "kickoff_sent",
            note="자료 요청 메일 발송",
            ts="2026-06-20T10:00:00+00:00",
        )
        assert cp1["checkpoints"]["kickoff_sent"]["note"] == "자료 요청 메일 발송"
        assert cp1["status"] == "queued"
        cp2 = fulfillment_queue.set_checkpoint(
            meta["fulfillment_id"],
            "materials_received",
            ts="2026-06-21T10:00:00+00:00",
        )
        assert cp2["checkpoints"]["materials_received"]["ts"] == "2026-06-21T10:00:00+00:00"
        rec_cp = fulfillment_queue.paid_reconciliation(now="2026-06-21T11:00:00+00:00")
        first_row = [r for r in rec_cp["rows"] if r["order_id"] == "order-pain-1"][0]
        assert first_row["checkpoint_done_count"] == 2
        assert first_row["next_checkpoint"] == "draft_ready"
        assert first_row["checkpoint_summary"] == "2/4 초안 준비"
        cp_done = fulfillment_queue.set_checkpoint(
            "order-pain-1",
            "final_delivered",
            ts="2026-06-22T10:00:00+00:00",
        )
        assert cp_done["status"] == "delivered"
        store.save_payment("order-missing", "video-editor", 39000, "paid", extra={
            "src": "webhook",
            "pain_release_job": "video-editor",
            "pain_release_pain": "revision-chaos",
            "fulfillment_id": "fq_pay_missing",
            "kickoff_path": os.path.join(report_dir, "missing.md"),
        })
        rec2 = fulfillment_queue.paid_reconciliation(now="2026-06-20T09:00:00+00:00")
        assert rec2["paid_pain_orders"] == 2
        assert rec2["ok"] == 1
        assert rec2["issue_counts"]["missing_queue"] == 1
        assert rec2["issue_counts"]["missing_kickoff"] == 1
        repairs = fulfillment_queue.repair_paid_releases(["order-missing"], now="2026-06-20T09:00:00+00:00")
        assert len(repairs) == 1
        assert repairs[0]["order_id"] == "order-missing"
        assert repairs[0]["fulfillment_id"].startswith("fq_pay_")
        assert "missing_queue" in repairs[0]["before_issues"]
        assert "missing_kickoff" in repairs[0]["before_issues"]
        assert repairs[0]["after_issues"] == []
        assert os.path.exists(repairs[0]["kickoff_path"])
        rec3 = fulfillment_queue.paid_reconciliation(now="2026-06-20T09:00:00+00:00")
        assert rec3["paid_pain_orders"] == 2
        assert rec3["ok"] == 2
        assert rec3["issue_counts"] == {}
        assert len(fulfillment_queue.read_jobs()) == 2
        repeat = fulfillment_queue.repair_paid_releases(["order-missing"], now="2026-06-20T09:00:00+00:00")
        assert repeat[0]["after_issues"] == []
        assert len(fulfillment_queue.read_jobs()) == 2
        meta2 = server._paid_pain_fulfillment_meta(
            "order-pain-1",
            39000,
            {"customerEmail": "paid@example.com"},
            "paid",
        )
        assert meta2["fulfillment_id"] == meta["fulfillment_id"]
        assert len(fulfillment_queue.read_jobs()) == 2
        assert server._paid_pain_fulfillment_meta("career-order", 99000, {}, "paid") == {}
        assert server._paid_pain_fulfillment_meta("failed-order", 39000, {}, "failed") == {}
    finally:
        store.PAYMENTS_FILE = old_payments
        store.FULFILLMENT_FILE = old_queue
        store.FULFILLMENT_REPORT_DIR = old_report_dir
        server.PAIN_RELEASE_JOB = old_release_job
        server.PAIN_RELEASE_PAIN = old_release_pain
        server.PAIN_PAYMENT_EXPECTED_AMOUNT = old_pain_amount
        if os.path.exists(payments.name):
            os.unlink(payments.name)
        if os.path.exists(queue.name):
            os.unlink(queue.name)
        if os.path.isdir(report_dir):
            shutil.rmtree(report_dir)


# ── 캘리브레이션 어댑터 (R7 — 손추정→실데이터, 정직성 불가침) ──────────────
def test_calibrate_norm_soc():
    import calibrate
    assert calibrate._norm_soc("27-4032.00") == "27-4032"
    assert calibrate._norm_soc("274032") == "27-4032"
    assert calibrate._norm_soc(" 15-1252.00 ") == "15-1252"


def test_calibrate_percentile_monotonic():
    import calibrate
    vals = [0.0, 1.0, 2.0, 3.0]
    assert calibrate._percentile(3.0, vals) > calibrate._percentile(0.0, vals)
    assert 0 <= calibrate._percentile(1.0, vals) <= 100


def test_calibrate_anchor_only_with_data_and_no_overclaim():
    import calibrate
    job = {"job_id": "x", "baseline": {"index": 50, "ci": 10, "calibrated": False, "note": "손추정"},
           "tasks": [{"task_id": "t", "name_ko": "t", "weight": 1.0, "baseline": 40, "ci": 10}]}
    exposure = {"27-4032": 2.0, "10-0000": 0.0}
    assert calibrate.calibrate_job(job, "99-9999", exposure) is None      # SOC 없음 → 앵커 안 함
    out = calibrate.calibrate_job(job, "27-4032", exposure, confidence="high", citation="테스트")
    assert isinstance(out, dict)
    b = out["baseline"]
    assert b["calibrated"] is False                                       # ★과대표기 금지: 표시점수 미반영→false 유지
    a = b["index_anchor"]
    assert a["soc"] == "27-4032" and "percentile" in a
    assert "raw_exposure" not in a and "raw" not in a                     # 라이선스: 외부 raw 점수 미저장
    assert out["tasks"][0]["baseline"] == 40                              # 태스크 baseline 불변(손추정)
    assert "calibration" not in job["baseline"] and "index_anchor" not in job["baseline"]  # 원본 비파괴


def test_calibrate_medium_default_holds():
    import calibrate
    job = {"job_id": "x", "baseline": {"index": 50, "ci": 8, "calibrated": False, "note": "손추정"}, "tasks": []}
    exp = {"11-1111": 1.0, "22-2222": 0.0}
    assert calibrate.calibrate_job(job, "11-1111", exp, confidence="medium") == "skip_medium"   # 기본 보류
    ok = calibrate.calibrate_job(job, "11-1111", exp, confidence="medium", apply_medium=True)
    assert isinstance(ok, dict) and ok["baseline"]["index_anchor"]["soc_confidence"] == "medium"


def test_calibrate_load_exposure_autodetect(tmp_csv=None):
    import calibrate, tempfile, os as _os
    p = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8")
    p.write("SOC,AIOE\n27-4032.00,1.85\n15-1252.00,1.2\n"); p.close()
    try:
        tab = calibrate.load_exposure(p.name)
        assert tab["27-4032"] == 1.85 and tab["15-1252"] == 1.2          # SOC/점수 컬럼 자동탐지+정규화
        assert calibrate.load_exposure("/no/such/file.csv") == {}        # 없는 파일 → {}(정직 no-op)
    finally:
        _os.unlink(p.name)


# ── WorkRadar US (5갈래 코파일럿) ───────────────────────────────────────
def test_wr_branch_logic():
    # feel<=1 → 같은 분야(defend/pivot), feel==2 → 떠남(reskill/independent/founder)
    assert workradar.decide_branch(0, 0, 0) == "defend"     # 반복 적음 + 분야 좋음
    assert workradar.decide_branch(2, 1, 0) == "pivot"      # 반복 많음 + 분야 ok
    assert workradar.decide_branch(1, 2, 0) == "reskill"    # 떠남 + 더 깊이
    assert workradar.decide_branch(1, 2, 1) == "independent" # 떠남 + 내 일
    assert workradar.decide_branch(1, 2, 2) == "founder"    # 떠남 + 창업


def test_wr_compute_result():
    r = workradar.compute_result("junior-developer", 2, 2, 2)
    assert r["branch_id"] == "founder" and r["type_name"] == "The Founder"
    assert r["score"] == 68 and r["band"] == "Cloudy"       # 64 + (2-1)*4
    assert len(r["tasks"]) == 5
    for bad in [("nope", 0, 0, 0), ("junior-developer", 5, 0, 0),
                ("junior-developer", True, 0, 0), ("junior-developer", 0, 0, None)]:
        try:
            workradar.compute_result(*bad)
            assert False, bad
        except ValueError:
            pass


def test_wr_valid_email():
    assert workradar.valid_email("a@b.co")
    for bad in ["", "x", "a@b", "a b@c.com", "a@@b.com", "a@b."]:
        assert not workradar.valid_email(bad), bad


def test_wr_subscriber_dedup(tmp_path=None):
    import tempfile
    orig = workradar.SUBS_FILE
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(p)
    workradar.SUBS_FILE = p
    try:
        assert workradar.append_subscriber({"email": "X@Y.com", "job": "junior-developer"})
        assert not workradar.append_subscriber({"email": "x@y.com", "job": "junior-developer"})  # 중복(대소문자)
        assert not workradar.append_subscriber({"email": "bad-email", "job": ""})                # 무효 이메일
        assert workradar.subscriber_count() == 1
    finally:
        if os.path.exists(p):
            os.unlink(p)
        workradar.SUBS_FILE = orig


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
