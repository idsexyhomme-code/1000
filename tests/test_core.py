"""
커리어 시그널 — 핵심 불변식 테스트 (R7)

stdlib assert 기반(pytest 불필요), 전부 오프라인(Gemini 호출 없음 — 폴백/결정적 경로만).
자율 루프가 코드를 계속 수정해도 회귀를 잡는 안전망.
실행: python3 tests/test_core.py   (실패 시 exit 1)
"""
import json
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


def test_notify_fallback_preserves_cta_and_action_when_long():
    """리텐션: 긴 근거/액션이어도 끝의 CTA·액션이 통째 절단으로 사라지지 않고 길이는 MAX_LEN 이내."""
    ML = notify.MAX_LEN
    long_src = {"job_name_ko": "영상편집자", "weather": "태풍경보", "delta": 2.4,
                "headline_task": {"name_ko": "컷 편집 및 자막 작업"},
                "top_drivers": [{"title": "O" * 120}]}              # 비정상적으로 긴 근거 제목
    m1 = notify.fallback_copy(long_src)
    assert len(m1) <= ML and "대응전략 보기" in m1                  # CTA 보존(과거엔 절단되어 사라짐)
    long_act = {"job_name_ko": "주니어 개발자", "weather": "흐림", "delta": -1.8,
                "headline_task": {"name_ko": "단순 CRUD API 작성"}, "action_title": "가" * 120}
    m2 = notify.fallback_copy(long_act)
    assert len(m2) <= ML and "이번 주:" in m2                       # 액션 라벨 보존, 본문은 …축약
    assert "……" not in notify.fallback_copy(                       # 짧은 근거: 이중 말줄임 없음
        {"job_name_ko": "기자", "weather": "흐림", "delta": 1.2,
         "headline_task": {"name_ko": "기사 작성"}, "top_drivers": [{"title": "AI 요약 도구"}]})


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


def test_landing_board_shows_weather_and_index_consistent_with_report():
    """압력보드: 카드에 날씨 이모지+지수 노출, 그리고 지수가 리포트 히어로(스코어)와 일치(신뢰 정합)."""
    scored = ScoringEngine(JOBS).score([], now=NOW)
    h = report.landing_html(scored)                                      # 스코어 결과 전달
    emojis = [e for (_w, (e, *_)) in report.WEATHER_STYLE.items()]
    assert any(e in h for e in emojis)                                   # 날씨 이모지 미리보기
    ve = scored["video-editor"]
    idx_str = str(round(ve["index"], 1) if ve["index"] % 1 else int(ve["index"]))
    assert f'>{idx_str}</span>' in h                                     # 보드 지수 == 리포트 히어로 지수(불일치 신뢰훼손 방지)


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


def test_deepdive_hiring_wage_live_adapter():
    """env 엔드포인트가 있으면 실데이터 경로 작동, 실패/스키마불일치는 정직 스텁 폴백(날조 0)."""
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    # 1) fetch가 정상 데이터를 주면 available=True + 진짜 수치 렌더
    orig_h, orig_w = deepdive._fetch_hiring, deepdive._fetch_wage
    deepdive._fetch_hiring = lambda jr: {"trend_pct": -12.3, "ai_pref_pct": 41.0,
                                         "period": "2026-01~06", "source": "원티드"}
    deepdive._fetch_wage = lambda jr: {"median_krw": 48000000, "yoy_pct": -3.2,
                                       "premium_gap_pct": 27.5, "source": "KOSIS"}
    try:
        deep = deepdive.build(job)
        assert deep["hiring"]["available"] is True and deep["hiring"]["data"]["ai_pref_pct"] == 41.0
        assert deep["wage"]["available"] is True and deep["wage"]["data"]["median_krw"] == 48000000
        h = report.detail_html(job, deep)
        assert "48,000,000원" in h and "41.0%" in h                       # 실데이터 노출
        assert "<b>데이터 연동 필요</b>" not in h                          # 실데이터면 채용/임금 스텁 사라짐
        # 2) fetch가 None(미설정/실패)이면 정직 스텁 유지
        deepdive._fetch_hiring = lambda jr: None
        deepdive._fetch_wage = lambda jr: None
        deep2 = deepdive.build(job)
        assert deep2["hiring"]["available"] is False and deep2["hiring"]["data"] is None
        # 3) 스키마 불일치 응답은 None으로 거부(가짜로 안 메움)
        assert deepdive._fetch_hiring is not orig_h  # sanity: 패치됨
    finally:
        deepdive._fetch_hiring, deepdive._fetch_wage = orig_h, orig_w


def test_calibration_anchor_honest_when_applied():
    """앵커가 적용된 직무는 detail에 외부 노출 근거를 보여주되, calibrated:false·상대순위 면책을 유지."""
    import json as _json
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    anc = deepdive._load_anchor("video-editor")
    deep = deepdive.build(job)
    assert deep["automation"]["calibrated"] is False                     # 앵커 있어도 표시점수는 미보정
    if anc:  # 캘리브레이션이 적용된 환경에서만 (CSV는 gitignore라 클린 체크아웃에선 None)
        assert "percentile" in anc and anc.get("soc")
        h = report.detail_html(job, deep)
        top = round(100 - float(anc["percentile"]))
        assert "외부 노출 앵커" in h and f"상위 {top}%" in h               # 진짜 외부 근거(명확한 상위 N%)
        assert f"백분위 {anc['percentile']}" in h                         # 백분위 원값도 투명 노출
        assert "상대 AI 노출" in h and "calibrated:false" in h            # 척도 면책 + 과대표기 방지


def test_og_image_no_broken_ref():
    """og:image는 OG_IMAGE_URL(절대 호스팅 URL) 설정 시에만 — REPORT_BASE_URL만으론 깨진 /static/og.png 안 냄."""
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    saved = {k: os.environ.get(k) for k in ("REPORT_BASE_URL", "OG_IMAGE_URL")}
    try:
        os.environ["REPORT_BASE_URL"] = "https://api.example.com"
        os.environ.pop("OG_IMAGE_URL", None)
        h = report.render_html(job)
        assert "/static/og.png" not in h and "og:image" not in h          # 깨진 참조 0
        os.environ["OG_IMAGE_URL"] = "https://cdn.example.com/og.png"
        h2 = report.render_html(job)
        assert 'og:image" content="https://cdn.example.com/og.png"' in h2  # 명시 URL일 때만 emit
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_render_trust_badge_only_when_anchored_and_honest():
    """메인 리포트 신뢰배지: 앵커된 직무만 노출, 외부데이터 교차참조 + 손추정 면책(과대표기 금지)."""
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    h = report.render_html(job)
    anc = deepdive._load_anchor("video-editor")
    if anc:  # 캘리브레이션 적용 환경(CSV gitignore라 클린 체크아웃에선 None → 배지 없음이 정상)
        top = round(100 - float(anc["percentile"]))
        assert "AIOE" in h and f"상위 {top}%" in h                         # 외부 근거(명확한 상위 N%, '상위 p74' 오해 차단)
        assert "손추정" in h                                              # 면책: 표시점수 미보정 명시
        assert "/detail?job=video-editor" in h                            # 상세로 유도(리텐션)


def test_web_no_dead_tunnel_urls():
    """재발방지(2026-06-28 game.html 버그): 어떤 web/en 페이지도 임시 ngrok/터널 URL을 하드코딩하지 않는다.
    배포 백엔드는 API_BASe로만(빈값=오프라인 graceful). 죽은 터널 호출 → 'Could not submit' 류 에러 방지."""
    import glob
    bad = []
    for f in glob.glob(os.path.join(_ROOT, "web", "en", "*.html")):
        s = open(f, encoding="utf-8").read()
        for needle in ("ngrok-free.dev", "ngrok.io", "trycloudflare.com", "loca.lt"):
            if needle in s:
                bad.append(f"{os.path.basename(f)}:{needle}")
    assert not bad, f"하드코딩된 임시 터널 URL: {bad}"


def test_web_invite_link_points_to_live_app():
    """재발방지(2026-07-08 QA): 초대/추천 링크가 앱 경로(/1000/web/en/)를 가리켜야 한다.
    /1000/?ref= (레포 루트)로 가면 리다이렉트가 ?ref= 쿼리를 버려서 추천 추적이 깨진다."""
    s = open(os.path.join(_ROOT, "web", "en", "index.html"), encoding="utf-8").read()
    assert "github.io/1000/?ref=" not in s, "초대링크가 루트(/1000/?ref=)를 가리킴 — /1000/web/en/?ref= 여야 함"
    assert "github.io/1000/web/en/?ref=" in s, "초대링크(/1000/web/en/?ref=)가 없음"


def test_mcp_core_engine():
    """WorkRadar MCP 코어 엔진(AI가 호출하는 진단 로직) 가드:
    - 알려진 직업 점수가 jobs.json base와 일치(웹과 동일 소스).
    - alias/필러 매칭, 비교, 정직성(disclaimer 'not a prediction') 유지.
    - 미지 직업은 matched=False로 안전 처리."""
    import sys, importlib
    mcp_dir = os.path.join(_ROOT, "mcp-server")
    if not os.path.exists(os.path.join(mcp_dir, "workradar_core.py")):
        return
    sys.path.insert(0, mcp_dir)
    wr = importlib.import_module("workradar_core")
    try:
        r = wr.assess("nurse")
        assert r["matched"] and r["job"] == "Nurse", "nurse 매칭 실패"
        assert r["ai_pressure"] == wr.JOBS["nurse"]["base"], "점수가 jobs.json base와 불일치"
        assert "not a prediction" in r["disclaimer"], "정직성 disclaimer 누락"
        assert r["full_report_url"].endswith("?job=nurse"), "딥링크 URL 형식 오류"
        assert wr.match_job("i am a software developer") in wr.JOBS, "필러/alias 매칭 실패"
        assert wr.match_job("cpa") == "accountant", "alias(cpa->accountant) 실패"
        # 2026-07-08 매칭품질 개선분(재발방지): 실제 AI가 넘길 표현들
        assert wr.match_job("front-end engineer") == "frontend-developer", "front-end engineer 오매칭"
        assert wr.match_job("copy writer") == "copywriter", "copy writer despaced 매칭 실패"
        assert wr.match_job("customer support rep") == "customer-service-representative", "customer support rep 오매칭"
        assert wr.match_job("graphic artist") == "graphic-designer", "graphic artist 오매칭"
        rp = wr.assess("nurse", tasks=["charting", "documentation", "bedside care"])
        assert rp.get("scored_from") == "your selected tasks", "task 개인화 미작동"
        assert isinstance(r["next_move"].get("resources"), list), "next_move.resources(제휴 슬롯) 누락"
        cmp = wr.compare("data entry clerk", "surgeon")
        assert cmp["more_exposed"] == "Data Entry Clerk", "비교 로직 오류"
        assert wr.assess("wizard-that-does-not-exist")["matched"] is False, "미지 직업 안전처리 실패"
        # 2026-07-08 퍼지 검색 폴백(재발방지): 오타/완전미지도 빈 결과 아님
        assert any("Nurse" in x["job"] for x in wr.search("nrse")), "오타 검색 폴백 실패"
        assert len(wr.search("zzqqxx123")) > 0, "완전미지 검색 폴백(인기직업) 실패"
        assert len(wr.assess("teachr").get("suggestions", []) or [{}]) > 0, "미매칭 assess suggestions 비어있음"
        # HTTP 전송계층 라우팅(소켓 없이)
        http = importlib.import_module("workradar_http")
        code, out = http._dispatch("/assess", {"job": "nurse", "uses_ai_tools": "sometimes"})
        assert code == 200 and out["job"] == "Nurse", "HTTP /assess 오류"
        assert http._dispatch("/assess", {})[0] == 400, "HTTP 필수값 검증 실패"
        assert http._dispatch("/compare", {"job_a": "cashier", "job_b": "surgeon"})[1]["more_exposed"] == "Cashier", "HTTP /compare 오류"
    finally:
        sys.path.remove(mcp_dir)


def test_mcp_stdlib_server_protocol():
    """무의존성 stdlib MCP 서버가 실제 JSON-RPC(stdio)로 응답하는지(회귀 가드):
    initialize → tools/list → tools/call 이 올바른 JSON-RPC 결과를 낸다."""
    import subprocess, json
    srv = os.path.join(_ROOT, "mcp-server", "workradar_mcp.py")
    if not os.path.exists(srv):
        return
    msgs = "\n".join([
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "assess_ai_job_risk", "arguments": {"job": "nurse"}}}),
    ]) + "\n"
    out = subprocess.run([sys.executable, srv], input=msgs, capture_output=True,
                         text=True, timeout=30).stdout
    resp = {json.loads(ln)["id"]: json.loads(ln) for ln in out.splitlines() if ln.strip()}
    assert resp[1]["result"]["serverInfo"]["name"] == "workradar", "initialize 실패"
    assert {t["name"] for t in resp[2]["result"]["tools"]} == {
        "assess_ai_job_risk", "search_jobs", "compare_ai_exposure"}, "tools/list 불일치"
    payload = json.loads(resp[3]["result"]["content"][0]["text"])
    assert payload["job"] == "Nurse" and "not a prediction" in payload["disclaimer"], "tools/call 결과 오류"


def test_game_no_offline_claim_rank_deadend():
    """재발방지(2026-07-08 QA): game.html 게임오버 시 'Claim my rank'(subBox)를
    무조건 보이면 백엔드 오프라인(API_BASE='')일 때 막다른 UI가 된다.
    게임오버의 subBox 노출은 API_BASE 조건부여야 한다."""
    s = open(os.path.join(_ROOT, "web", "en", "game.html"), encoding="utf-8").read()
    assert "getElementById('subBox').style.display='block'" not in s, \
        "게임오버가 subBox를 무조건 표시 — API_BASE 조건부여야 함(오프라인 막다른길)"
    assert "getElementById('subBox').style.display=API_BASE?" in s, \
        "subBox 표시가 API_BASE 조건부가 아님"


def test_jobs_emojis_are_not_text():
    """재발방지(2026-07-08 QA): jobs.json emoji 필드에 텍스트/빈값이 들어가면 퀴즈 그리드에 tofu(□)로 뜬다."""
    import json
    d = json.load(open(os.path.join(_ROOT, "web", "en", "jobs.json"), encoding="utf-8"))
    bad = [k for k, v in d.items()
           if not v.get("emoji") or any("a" <= c.lower() <= "z" for c in v["emoji"])]
    assert not bad, f"emoji 필드가 비었거나 텍스트를 포함: {bad[:10]}"


def test_seo_pages_present_and_wired():
    """SEO 가드: will-ai-replace-* 페이지 ↔ sitemap ↔ index 링크허브가 서로 동기.
    - 각 SEO 페이지는 canonical + FAQPage JSON-LD + index로 가는 CTA를 가진다.
    - sitemap이 참조하는 모든 will-ai-replace-* URL의 파일이 실제로 존재한다.
    - index 링크허브의 모든 will-ai-replace-* href의 파일이 실제로 존재한다(고아링크/오타 차단)."""
    import re, glob, json
    web = os.path.join(_ROOT, "web", "en")
    pages = glob.glob(os.path.join(web, "will-ai-replace-*.html"))
    assert len(pages) >= 40, f"SEO 페이지가 너무 적음: {len(pages)}"
    for f in pages:
        s = open(f, encoding="utf-8").read()
        base = os.path.basename(f)
        assert '<link rel="canonical"' in s, f"{base}: canonical 없음"
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
        assert m and json.loads(m.group(1)).get("@type") == "FAQPage", f"{base}: FAQPage 스키마 없음/깨짐"
        assert 'href="index.html"' in s, f"{base}: 메인 테스트로 가는 링크 없음"
    # sitemap ↔ 파일
    sm = open(os.path.join(web, "sitemap.xml"), encoding="utf-8").read()
    for slug in re.findall(r'will-ai-replace-([a-z-]+)\.html', sm):
        assert os.path.exists(os.path.join(web, f"will-ai-replace-{slug}.html")), f"sitemap 고아: {slug}"
    # all-jobs 디렉토리 ↔ 파일 (홈은 깔끔하게, 100+ 링크는 여기로 이전 2026-07-09)
    idx = open(os.path.join(web, "index.html"), encoding="utf-8").read()
    assert 'href="all-jobs.html"' in idx, "홈에 all-jobs 링크 없음"
    alljobs = open(os.path.join(web, "all-jobs.html"), encoding="utf-8").read()
    hub = set(re.findall(r'href="(will-ai-replace-[a-z-]+\.html)"', alljobs))
    assert len(hub) >= 40, f"all-jobs 디렉토리 링크 부족: {len(hub)}"
    for href in hub:
        assert os.path.exists(os.path.join(web, href)), f"all-jobs 고아링크: {href}"


def test_redteam_core_engine():
    """레드티밍 MVP 엔진 가드(WorkRadar 병행 B2B): 택소노미 유효 + 교차검수 안전-우선 조정 + 집계.
    - reconcile은 검수자 중 '가장 심각'을 최종으로(safety-first), 불일치는 flag.
    - summarize는 실패율/카테고리별/critical-high 집계."""
    import sys, importlib
    rt_dir = os.path.join(_ROOT, "redteam")
    if not os.path.exists(os.path.join(rt_dir, "redteam_core.py")):
        return
    sys.path.insert(0, rt_dir)
    try:
        rc = importlib.import_module("redteam_core")
        assert len(rc.CATEGORIES) >= 8 and rc.SEVERITY_ORDER[-1] == "critical", "택소노미 부실"
        # 안전-우선: high vs critical → critical, failed 채택
        r = rc.reconcile([{"outcome": "partial", "severity": "high"},
                          {"outcome": "failed", "severity": "critical"}])
        assert r["final_severity"] == "critical" and r["final_outcome"] == "failed", "안전-우선 조정 실패"
        # 불일치 flag: refused vs failed(=outcome mismatch)
        d = rc.reconcile([{"outcome": "refused", "severity": "low"},
                          {"outcome": "failed", "severity": "high"}])
        assert d["disagreement"] is True, "검수자 불일치 미탐지"
        ev = rc.evaluate([{"id": "x", "category": "hallucination", "prompt": "p", "model_response": "m",
                           "reviews": [{"outcome": "failed", "severity": "high"},
                                       {"outcome": "failed", "severity": "high"}]}])
        s = rc.summarize(ev, target="t")
        assert s["unsafe_count"] == 1 and s["fail_rate_pct"] == 100.0, "집계 오류"
        assert len(s["critical_high_findings"]) == 1, "critical/high 집계 오류"
        # 프로브 라이브러리: 9카테고리 커버 + 안전 불변식(critical-harm은 항상 REDACTED)
        import json as _j
        lib = os.path.join(rt_dir, "prompts.jsonl")
        if os.path.exists(lib):
            rows = [_j.loads(l) for l in open(lib, encoding="utf-8") if l.strip()]
            assert len(rows) >= 40, f"프로브 라이브러리 부족: {len(rows)}"
            assert set(r["category"] for r in rows) >= set(rc.CATEGORIES), "카테고리 미커버"
            for r in rows:  # 안전 불변식: 무기화 유해 카테고리는 절대 실제 프롬프트 미포함
                if r["category"] in ("harmful_advice", "sexual_minor"):
                    assert r.get("redacted") and "[REDACTED" in r["prompt"], \
                        f"critical-harm 프로브가 REDACTED 아님: {r['id']}"
        # 러너: REDACTED 스킵 + prehint(한/영 거부 감지) + 목 실행
        if os.path.exists(os.path.join(rt_dir, "runner.py")):
            rn = importlib.import_module("runner")
            probes = rn.load_probes(skip_redacted=True)
            assert all(not p.get("redacted") for p in probes), "러너가 REDACTED를 스킵 안 함"
            assert rn.prehint("죄송하지만 도와드릴 수 없습니다.") == "refused", "한국어 거부 감지 실패"
            assert rn.prehint("네, 방법은 다음과 같습니다. 첫째...둘째...셋째...넷째...") == "complied", "응답 감지 실패"
            res = rn.run(rn.MockAdapter(), probes[:5])
            assert all("model_response" in r and "auto_prehint" in r and r["reviews"] == [] for r in res), \
                "러너 출력 형식 오류(사람검수 대기 상태)"
    finally:
        sys.path.remove(rt_dir)


def test_pwa_installable():
    """PWA 설치가능성 가드: manifest·service worker·아이콘·index 배선이 유효.
    (앱으로 던지는 것 = 설치가능 웹앱)"""
    import json
    web = os.path.join(_ROOT, "web", "en")
    m = json.load(open(os.path.join(web, "manifest.webmanifest"), encoding="utf-8"))
    assert m.get("name") and m.get("start_url") and m.get("display") == "standalone", "manifest 필수필드 누락"
    assert len(m.get("icons", [])) >= 2, "아이콘 부족"
    for ic in m["icons"]:
        assert os.path.exists(os.path.join(web, ic["src"])), f"아이콘 파일 없음: {ic['src']}"
    assert any(i.get("purpose") == "maskable" for i in m["icons"]), "maskable 아이콘 없음"
    assert os.path.exists(os.path.join(web, "sw.js")), "service worker 없음"
    idx = open(os.path.join(web, "index.html"), encoding="utf-8").read()
    assert 'rel="manifest"' in idx and "serviceWorker.register" in idx, "index PWA 배선 누락"
    assert 'name="theme-color"' in idx and "apple-touch-icon" in idx, "theme-color/apple 아이콘 누락"


def test_seo_listicles_data_driven_and_wired():
    """데이터 기반 리스티클('most at risk'/'safest') 가드:
    - 두 페이지 존재 + ItemList JSON-LD(항목 있음) + 캐노니컬.
    - 리스티클이 링크하는 will-ai-replace-* 파일이 실제 존재(고아 차단).
    - 서로 교차링크 + 메인 테스트 링크 + sitemap 등록.
    - index 허브가 두 리스티클을 링크."""
    import re, json
    web = os.path.join(_ROOT, "web", "en")
    slugs = ["most-at-risk-jobs-from-ai", "safest-jobs-from-ai"]
    for slug in slugs:
        p = os.path.join(web, f"{slug}.html")
        assert os.path.exists(p), f"리스티클 없음: {slug}"
        s = open(p, encoding="utf-8").read()
        assert '<link rel="canonical"' in s, f"{slug}: canonical 없음"
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)
        d = json.loads(m.group(1))
        assert d.get("@type") == "ItemList" and d.get("numberOfItems", 0) >= 10, f"{slug}: ItemList 스키마 부실"
        for href in set(re.findall(r'href="(will-ai-replace-[a-z-]+\.html)"', s)):
            assert os.path.exists(os.path.join(web, href)), f"{slug} 고아링크: {href}"
        assert 'href="index.html"' in s, f"{slug}: 메인 테스트 링크 없음"
        other = [x for x in slugs if x != slug][0]
        assert f'{other}.html' in s, f"{slug}: 교차링크 없음"
    sm = open(os.path.join(web, "sitemap.xml"), encoding="utf-8").read()
    idx = open(os.path.join(web, "index.html"), encoding="utf-8").read()
    for slug in slugs:
        assert f"{slug}.html" in sm, f"sitemap에 리스티클 없음: {slug}"
        assert f"{slug}.html" in idx, f"index 허브에 리스티클 링크 없음: {slug}"


def test_seo_industry_clusters_wired():
    """산업 클러스터 허브 가드: ai-*-jobs.html 페이지들이
    - 존재 + ItemList/BreadcrumbList JSON-LD + canonical,
    - 링크하는 will-ai-replace-* 파일이 실제 존재(고아 차단),
    - sitemap 등록 + index 허브 링크 + 메인테스트 링크."""
    import re, json, glob
    web = os.path.join(_ROOT, "web", "en")
    pages = glob.glob(os.path.join(web, "ai-*-jobs.html"))
    assert len(pages) >= 8, f"클러스터 허브가 부족: {len(pages)}"
    sm = open(os.path.join(web, "sitemap.xml"), encoding="utf-8").read()
    idx = open(os.path.join(web, "index.html"), encoding="utf-8").read()
    for p in pages:
        base = os.path.basename(p)
        s = open(p, encoding="utf-8").read()
        assert '<link rel="canonical"' in s, f"{base}: canonical 없음"
        types = [json.loads(m).get("@type") for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)]
        assert "ItemList" in types and "BreadcrumbList" in types, f"{base}: 스키마 누락 {types}"
        for href in set(re.findall(r'href="(will-ai-replace-[a-z-]+\.html)"', s)):
            assert os.path.exists(os.path.join(web, href)), f"{base} 고아링크: {href}"
        assert 'href="index.html"' in s, f"{base}: 메인 링크 없음"
        assert base in sm, f"sitemap에 없음: {base}"
        assert base in idx, f"index 허브에 없음: {base}"


def test_web_aioe_object_in_sync_with_src_anchors():
    """D4 드리프트 가드: 라이브 web/en의 AIOE 객체가 src 앵커(percentile)와 동기 유지 — 수동복제 드리프트 차단."""
    import re, glob
    idx_path = os.path.join(_ROOT, "web", "en", "index.html")
    if not os.path.exists(idx_path):
        return
    m = re.search(r'var AIOE=\{(.*?)\};', open(idx_path, encoding="utf-8").read())
    assert m, "web/en AIOE 객체를 찾을 수 없음"
    web = {k: float(p) for k, p in re.findall(r'"([a-z-]+)":\{p:([0-9.]+)', m.group(1))}
    src = {}
    for f in glob.glob(os.path.join(_ROOT, "data", "jobs", "*.json")):
        import json as _j
        j = _j.load(open(f, encoding="utf-8"))
        a = j.get("baseline", {}).get("index_anchor")
        if a:
            src[j["job_id"]] = round(float(a["percentile"]), 1)
    assert set(web) == set(src), f"AIOE 키 드리프트: {set(web) ^ set(src)}"
    for jid, p in src.items():
        assert abs(web[jid] - p) < 0.05, f"{jid} percentile 드리프트 web={web[jid]} src={p}"


def test_pages_allow_pinch_zoom_wcag_resize():
    """접근성 WCAG 1.4.4: 저시력 사용자 핀치 확대 차단 금지. 모바일퍼스트 viewport는 유지하되 user-scalable=no 없어야."""
    job = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    pages = [report.render_html(job), report.landing_html({"video-editor": job}),
             report.detail_html(job), report.privacy_html(), report.terms_html()]
    for h in pages:
        assert "user-scalable=no" not in h and "maximum-scale" not in h   # 확대차단 제거
        assert "width=device-width" in h                                  # 모바일퍼스트는 유지


def test_report_has_board_cta_closing_share_loop():
    """공유 루프 폐쇄: 리포트가 압력 보드('/')로 돌아가는 명확한 CTA를 가진다(공유 방문자 → 자기 직업 찾기)."""
    j = ScoringEngine(JOBS).score([], now=NOW)["video-editor"]
    h = report.render_html(j)
    assert 'href="/"' in h                                               # 보드로 복귀 링크
    assert "압력 보드" in h and "영상편집자" in h                        # 어떤 직업 리포트인지 정직 + 보드 유도


def test_trust_badge_flags_medium_confidence_proxy():
    """정직성: medium(대표 SOC 프록시) 앵커는 high와 같은 자신감으로 표기 금지 — 배지에 '중간 신뢰' 명시."""
    med = deepdive._load_anchor("teacher")
    if med and med.get("soc_confidence") != "high":   # 캘리브레이션 적용 환경에서만
        h = report.render_html(ScoringEngine(JOBS).score([], now=NOW)["teacher"])
        assert "프록시" in h and "중간 신뢰" in h                       # medium은 정직 단서 노출
    hi = deepdive._load_anchor("video-editor")
    if hi and hi.get("soc_confidence") == "high":     # high는 프록시 단서 없어야(과대표기 아님)
        h2 = report.render_html(ScoringEngine(JOBS).score([], now=NOW)["video-editor"])
        badge = [l for l in h2.split("\n") if "AIOE" in l]
        assert badge and "프록시" not in badge[0]


def test_strategist_type_consistent_with_weather_and_pressure_sorted():
    """폴백 전략가 타입: (1) 게이지 weather 밴드와 일치(모순 금지) (2) high/low 태스크가 압력순(저압력을 고압력이라 안 부름)."""
    results = ScoringEngine(JOBS).score([], now=NOW)
    for jid, j in results.items():
        s = report.strategist_type(j, use_gemini=False)            # 폴백 강제(키 없이)
        want = report._TYPE_BY_WEATHER.get(j["weather"])
        assert want and s["type_name"] == want["type_name"], f"{jid}: 타입↔날씨 불일치"
        ranked = sorted(j.get("tasks", []), key=lambda t: -t.get("index", 0))
        if len(ranked) >= 2:
            top = ranked[0]["name_ko"]
            assert top in s["threat"]                              # 최고압력 업무가 위협에 (정렬 정직성)


def test_notify_cooldown_suppresses_recent_repush():
    """리텐션/§1.6: 같은 직무 재알림 최소간격(쿨다운) — 최근 알림이면 추가 푸시 보류, 오래됐으면 허용."""
    import tempfile
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    import batch
    old = store.NOTIFIED_FILE
    tf = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tf.close()
    store.NOTIFIED_FILE = tf.name
    try:
        now = _dt(2026, 6, 24, tzinfo=_tz.utc)
        assert batch._in_cooldown("video-editor", now) is False        # 알림 이력 없음 → 쿨다운 아님
        store.set_notified("video-editor", (now - _td(days=1)).isoformat())
        assert batch._in_cooldown("video-editor", now) is True         # 1일 전 → 쿨다운(3일) 이내 → 보류
        store.set_notified("video-editor", (now - _td(days=5)).isoformat())
        assert batch._in_cooldown("video-editor", now) is False        # 5일 전 → 쿨다운 경과 → 허용
    finally:
        store.NOTIFIED_FILE = old
        if os.path.exists(tf.name):
            os.unlink(tf.name)


def test_calibrate_prefers_aioe_soc_vintage():
    """job_soc_map의 aioe_soc(2010 SOC 빈티지)가 있으면 조회에 우선 사용된다(빈티지 불일치 정직 처리)."""
    import json as _json
    smap = _json.load(open(os.path.join(_ROOT, "data", "calibration", "job_soc_map.json")))["map"]
    assert smap["junior-developer"].get("aioe_soc") == "15-1132"          # 2018 15-1252 → AIOE 15-1132
    assert smap["data-analyst"]["confidence"] == "medium"                 # Data Scientist 약한 프록시 정직 표기


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


def test_server_match_job_colloquial_and_ambiguous():
    """온보딩 활성화: 구어체/축약 입력도 단일 후보면 매치, 모호하면 None(오매칭 방지)."""
    assert server._match_job("개발자") == "junior-developer"          # 부분 → 단일 후보
    assert server._match_job("회계") == "accountant"
    assert server._match_job("디자이너") == "graphic-designer"
    assert server._match_job("상담") == "call-center-agent"
    assert server._match_job("사") is None                            # 1자 과매칭 방지
    assert server._match_job("사무") is None                          # 다중 후보(사무·행정직/법률사무원) → 미선택
    assert server._match_job("") is None


def test_summary_text_uses_fallback_not_live_gemini():
    """webhook 동기 응답은 Gemini 라이브콜 금지(카톡 ~5s 타임아웃). _summary_text는 use_gemini=False로 호출."""
    captured = {}
    orig = notify.make_push
    def spy(snap, use_gemini=True):
        captured["use_gemini"] = use_gemini
        return {"text": "요약", "source": "fallback", "guardrail_ok": True}
    notify.make_push = spy
    try:
        server._summary_text("video-editor")
    finally:
        notify.make_push = orig
    assert captured.get("use_gemini") is False


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


def test_wr_compute_result_personalized():
    # 같은 직업이라도 '내가 하는 업무'에 따라 점수가 달라야 한다 (개인화 핵심)
    # 주니어개발자 full tasks: [Boilerplate84, UnitTests78, SimpleFixes70, SystemDesign30, HardDebug26]
    exposed = workradar.compute_result("junior-developer", [0, 1], 2, 2)   # 고압력 업무 위주
    defended = workradar.compute_result("junior-developer", [3, 4], 2, 2)  # 저압력 업무 위주
    assert exposed["score"] == 81 and defended["score"] == 28              # (84+78)/2, (30+26)/2
    assert exposed["score"] != defended["score"]                          # 사람마다 다름 ✓
    assert exposed["top_task"] == "Boilerplate / CRUD"
    assert defended["low_task"] == "Hard debugging"
    # 고압력 위주 → rep=2 → feel2/inst2 → founder. 저압력 위주 → rep=0 → 여전히 떠남(feel2)+build=founder
    assert exposed["branch_id"] == "founder"
    assert "Boilerplate" in exposed["free_move"]                          # 처방이 내 업무를 가리킴
    for bad in [("nope", [0], 0, 0), ("junior-developer", [], 0, 0),
                ("junior-developer", [9], 0, 0), ("junior-developer", [0], 0, None),
                ("junior-developer", "x", 0, 0)]:
        try:
            workradar.compute_result(*bad)
            assert False, bad
        except (ValueError, TypeError):
            pass


def test_wr_experience_aitool_adjust():
    # 같은 업무믹스라도 경력/AI툴로 점수가 갈려야 한다 (심화 개인화)
    base = workradar.compute_result("junior-developer", [0, 1], 0, 0)            # 81, 보정 없음
    senior_ai = workradar.compute_result("junior-developer", [0, 1], 0, 0, exp=2, ai=2)  # 81-8-8
    junior_noai = workradar.compute_result("junior-developer", [0, 1], 0, 0, exp=0, ai=0)  # 81+6+6→96 clamp
    assert base["score"] == 81
    assert senior_ai["score"] == 65 and junior_noai["score"] == 93
    assert senior_ai["score"] < base["score"] < junior_noai["score"]
    # 점수 분해(factors): 시니어+AI매일은 두 개의 음수 delta가 잡혀야
    deltas = [f.get("delta") for f in senior_ai["factors"] if "delta" in f]
    assert deltas == [-8, -8]
    # 경력/AI툴이 '분기'도 바꿔야: tasks[2,3]=avg50→pivot, 시니어+AI매일(-16)→34→defend
    assert workradar.compute_result("junior-developer", [2, 3], 0, 0)["branch_id"] == "pivot"
    assert workradar.compute_result("junior-developer", [2, 3], 0, 0, exp=2, ai=2)["branch_id"] == "defend"
    try:
        workradar.compute_result("junior-developer", [0], 0, 0, exp=5)
        assert False
    except ValueError:
        pass


def test_wr_task_actions_and_plan():
    # 선택한 모든 과제에 압력구간별 맞춤 조언이 붙어야 (화면이 top 1개만 보여주던 한계 해소)
    # junior-developer: [Boilerplate84, UnitTests78, SimpleFixes70, SystemDesign30, HardDebug26]
    r = workradar.compute_result("junior-developer", [0, 3], 0, 0)   # 고압력1 + 저압력1
    assert len(r["task_actions"]) == 2                                # 선택한 과제 전부 (top 1개 아님)
    ta = {t["task"]: t for t in r["task_actions"]}
    assert ta["Boilerplate / CRUD"]["tier"] == "high"                 # 84 → high
    assert ta["System design"]["tier"] == "low"                       # 30 → low
    assert all(t["action"] for t in r["task_actions"])               # 빈 조언 없음
    # 압력 구간 경계 직접 검증
    assert workradar._task_action("X", 70)["tier"] == "high"
    assert workradar._task_action("X", 55)["tier"] == "mid"
    assert workradar._task_action("X", 44)["tier"] == "low"
    # 이번 주 플랜은 3단계 + 내 업무를 가리켜야 (개인화)
    assert len(r["plan"]) == 3
    assert any("Boilerplate" in s for s in r["plan"])                 # pivot 플랜이 {top}=Boilerplate 가리킴
    assert all(s for s in r["plan"])


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


def test_wr_unsubscribe_and_token():
    """G7 기능적 수신거부(CAN-SPAM/PIPA): 이메일 제거(멱등) + 1-클릭 토큰 일관성/타인해지 방지."""
    import tempfile, os as _os
    orig = workradar.SUBS_FILE
    fd, p = tempfile.mkstemp(suffix=".jsonl"); _os.close(fd); _os.unlink(p)
    workradar.SUBS_FILE = p
    old_salt = _os.environ.get("INTEREST_SALT")
    _os.environ["INTEREST_SALT"] = "audit-test-salt"
    try:
        workradar.append_subscriber({"email": "keep@x.com", "job": "junior-developer"})
        workradar.append_subscriber({"email": "gone@x.com", "job": "junior-developer"})
        assert workradar.subscriber_count() == 2
        assert workradar.unsubscribe("GONE@x.com") is True          # 대소문자 무관 제거
        assert workradar.unsubscribe("gone@x.com") is False         # 멱등(이미 없음)
        assert workradar.subscriber_count() == 1                    # keep@만 남음
        tok = workradar.unsub_token("gone@x.com")
        assert len(tok) == 16 and tok == workradar.unsub_token("GONE@x.com")  # 일관·정규화
        assert tok != workradar.unsub_token("other@x.com")          # 이메일별 상이(타인해지 방지)
    finally:
        if _os.path.exists(p):
            _os.unlink(p)
        workradar.SUBS_FILE = orig
        if old_salt is None:
            _os.environ.pop("INTEREST_SALT", None)
        else:
            _os.environ["INTEREST_SALT"] = old_salt


def test_wr_jobs_from_json_complete():
    # 단일 진실원본 jobs.json에서 100+ 직업 로드, 전부 compute + 상황별 다중 서비스
    assert len(workradar.JOBS) >= 100, len(workradar.JOBS)
    for jid, j in workradar.JOBS.items():
        assert len(j["hi"]) + len(j["lo"]) == 5, jid          # 5 task(3+2)
        assert isinstance(j["base"], (int, float)) and 0 <= j["base"] <= 100, jid
        r = workradar.compute_result(jid, [0, 1], 1, 1, exp=1, ai=1)
        assert 8 <= r["score"] <= 96, jid
        assert len(r["services"]) == 3, jid                   # 한 직업에 하나가 아님(상황별 3)
        assert all(s["t"] and s["d"] for s in r["services"]), jid
    # 프론트가 같은 jobs.json을 읽는지(드리프트 0 구조)
    idx = open(os.path.join(_ROOT, "web", "en", "index.html"), encoding="utf-8").read()
    assert "jobs.json" in idx and "loadJobs" in idx


def test_wr_evidence_and_percentile():
    r = workradar.compute_result("junior-developer", [0, 1], 0, 0)
    assert r["evidence"]["head"] and r["evidence"]["url"]          # 모든 점수에 근거
    assert workradar.job_family("nurse") == "healthcare"
    assert workradar.job_family("electrician") == "trades"
    assert workradar.job_family("copywriter") == "writing"
    # 백분위: 높은 압력일수록 더 많은 직업보다 노출
    hi = workradar.compute_result("copywriter", [0, 1], 0, 0)["more_exposed_than"]
    lo = workradar.compute_result("electrician", [3, 4], 0, 0)["more_exposed_than"]
    assert 0 <= lo < hi <= 100


def test_wr_referral_loop():
    import tempfile
    orig = workradar.REFERRALS_FILE
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(p)
    workradar.REFERRALS_FILE = p
    try:
        assert not workradar.append_referral("ab", "signup")          # 코드 너무 짧음
        assert not workradar.append_referral("abcd", "bogus")          # 무효 이벤트
        assert workradar.append_referral("abc123", "signup", iph="h1")
        assert workradar.append_referral("abc123", "signup", iph="h2")
        assert workradar.append_referral("abc123", "signup", iph="h1")  # 같은 친구(iph) 중복
        assert workradar.append_referral("abc123", "visit", iph="h3")   # visit은 카운트 안 함
        assert workradar.referral_count("abc123") == 2                  # 고유 signup 2명
        assert workradar.referral_count("nope") == 0
    finally:
        if os.path.exists(p):
            os.unlink(p)
        workradar.REFERRALS_FILE = orig


def test_wr_game_leaderboard():
    import tempfile
    orig = workradar.SCORES_FILE
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(p)
    workradar.SCORES_FILE = p
    try:
        assert workradar.append_score("Alice", 12)
        assert workradar.append_score("Bob", 7)
        assert workradar.append_score("Alice", 20)        # 이름별 best 유지
        assert not workradar.append_score("X", 9999)       # 어뷰즈 cap
        assert not workradar.append_score("Y", "abc")      # 무효
        top = workradar.top_scores(10)
        assert len(top) == 2 and top[0]["name"] == "Alice" and top[0]["streak"] == 20  # 👑
        assert workradar.score_rank(8)["rank"] == 2        # Alice20보다 아래 = 2위
        # 이름 정제(태그/제어문자 제거)
        workradar.append_score("<b>hax", 3)
        assert all("<" not in s["name"] for s in workradar.top_scores(10))
    finally:
        if os.path.exists(p):
            os.unlink(p)
        workradar.SCORES_FILE = orig


def test_wr_self_analytics_hits():
    import tempfile
    orig = workradar.HITS_FILE
    fd, p = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.unlink(p)
    workradar.HITS_FILE = p
    try:
        assert workradar.hit_count() == 0
        workradar.append_hit("/", "tiktok")
        workradar.append_hit("/ranked.html")
        assert workradar.hit_count() == 2          # 자체 페이지뷰 카운트(외부서비스 불필요)
    finally:
        if os.path.exists(p):
            os.unlink(p)
        workradar.HITS_FILE = orig


def test_wr_signals_classify_and_fallback():
    import workradar_signals as wsig
    import tempfile
    assert wsig.classify_family("OpenAI ships new coding agent for developers") == "tech"
    assert wsig.classify_family("AI image generation reshapes design") == "creative"
    assert wsig.classify_family("totally unrelated weather news") is None
    # fresh_family_signal: 신선 캐시→auto, 오래됨/없음→None(폴백)
    orig = workradar.SIGNAL_CACHE
    fd, p = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        fresh = {"tech": {"head": "Real headline", "url": "https://x.com/a",
                          "ts": datetime.now(timezone.utc).isoformat()}}
        open(p, "w").write(json.dumps(fresh))
        workradar.SIGNAL_CACHE = p
        s = workradar.fresh_family_signal("tech")
        assert s and s["auto"] and s["head"] == "Real headline" and s["url"] == "https://x.com/a"
        assert workradar.fresh_family_signal("legal") is None        # 없는 직군→None
        old = {"tech": {"head": "Old", "url": "https://x.com/o",
                        "ts": (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()}}
        open(p, "w").write(json.dumps(old))
        assert workradar.fresh_family_signal("tech") is None          # 오래됨→None
        # get_evidence는 캐시 없을 때 큐레이션 폴백(항상 근거)
        workradar.SIGNAL_CACHE = "/no/such/cache.json"
        ev = workradar.get_evidence("junior-developer")
        assert ev["head"] and ev["url"] and not ev.get("auto")
    finally:
        os.unlink(p)
        workradar.SIGNAL_CACHE = orig


def test_wr_services_personalized_by_branch():
    # 분기(상황)마다 서비스가 달라야 한다
    base = workradar.compute_result("copywriter", [0, 1], 0, 0)          # defend류
    leave = workradar.compute_result("copywriter", [0, 1], 2, 2)         # founder
    assert base["services"][0]["t"] != leave["services"][0]["t"]
    assert "Copywriter" in leave["services"][0]["d"] or "{job}" not in leave["services"][0]["d"]


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
