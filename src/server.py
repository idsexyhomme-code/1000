"""
커리어 시그널 — 봇 서버 골격 (R4c)

stdlib http.server 기반(의존성 0). 정적 모듈(scoring/notify/report/store)을 동작 서비스로 묶음.
라우트:
  POST /webhook/kakao  카카오 채널 스킬 웹훅 — 발화로 직업 선택→저장, 현재 압력 요약 응답
  GET  /report?job=ID  결과리포트 HTML (report.render_html)
  GET  /report?user=ID 사용자의 직업 리포트
  GET  /health         헬스체크

실행: GEMINI_API_KEY=... python3 src/server.py [PORT]
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import notify
import fulfillment_queue
import pain_intents
import painmap
import pain_probe
import pipeline
import report
import store
from scoring import ScoringEngine

JOBS_DIR = pipeline.JOBS_DIR
_ENG = ScoringEngine(JOBS_DIR)
JOBS = _ENG.jobs  # {job_id: {job_name_ko, tasks, ...}}

MAX_BODY = 64 * 1024          # 웹훅 본문 최대 64KB (DoS 방지)
_CACHE_TTL = 60.0             # 점수 계산 캐시 TTL(초) — /report·요약 반복요청 DoS/비용 완화
_score_cache = {"ts": -1e9, "data": None}


def _cached_scores() -> dict:
    now = time.monotonic()
    if _score_cache["data"] is None or now - _score_cache["ts"] > _CACHE_TTL:
        _score_cache["data"] = pipeline.current_scores()
        _score_cache["ts"] = now
    return _score_cache["data"]


# ── 배포 보안: 웹훅 토큰 인증 + IP rate limit (R5) ────────────────────
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN", "")  # 설정 시 /webhook은 ?token= 일치 요구
REPORT_BASE_URL = os.environ.get("REPORT_BASE_URL", "")  # 예: https://api.example.com (리포트 링크용)
CHANNEL_URL = os.environ.get("CHANNEL_URL", "")          # 카카오 채널 추가 링크(공유 바이럴용)
PAYMENT_URL = os.environ.get("PAYMENT_URL", "")          # 설정 시 /offer가 실결제 버튼, 미설정 시 사전예약 수집
PAIN_PAYMENT_URL = os.environ.get("PAIN_PAYMENT_URL", "")  # 설정 시 /pain-offer가 실결제 버튼으로 전환
PAIN_RELEASE_JOB = os.environ.get("PAIN_RELEASE_JOB", "")
PAIN_RELEASE_PAIN = os.environ.get("PAIN_RELEASE_PAIN", "")
# 결제 웹훅 서명검증 — 이 시크릿 없으면 'paid'(진짜 지불주체)로 절대 확정하지 않음(정직성 불가침).
PAYMENT_WEBHOOK_SECRET = os.environ.get("PAYMENT_WEBHOOK_SECRET", "")
PAYMENT_SIG_HEADER = os.environ.get("PAYMENT_SIG_HEADER", "X-Signature")  # PG가 보내는 HMAC 서명 헤더명(배포 시 PG에 맞춤)
INTEREST_SALT = os.environ.get("INTEREST_SALT", "") or WEBHOOK_TOKEN  # 리드 IP HMAC 솔트(없으면 IP 미저장)
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "60"))  # IP당 윈도우 요청 수
RATE_WINDOW = 60.0
_rl_lock = threading.Lock()
_rl: dict[str, list] = {}  # ip -> [window_start, count]


def _valid_contact(c: str) -> bool:
    """이메일 또는 카카오 오픈채팅 ID로 보이는지 최소 검증(쓰레기/인젝션 거부)."""
    if not c or len(c) < 3 or len(c) > 120:
        return False
    if any(ch in c for ch in "<>\"'\\\n\r\t ") or "  " in c:
        return False
    if "@" in c:                      # 이메일류: a@b.c 꼴
        local, _, dom = c.partition("@")
        return bool(local) and "." in dom and not dom.startswith(".")
    return len(c) >= 3                # 카카오 오픈채팅 ID류


def _ip_hmac(ip: str) -> str:
    """IP 평문 저장 금지. 비밀 솔트 없으면 빈 문자열."""
    return (hmac.new(INTEREST_SALT.encode(), str(ip).encode(),
                     hashlib.sha256).hexdigest()[:12] if INTEREST_SALT else "")


def _valid_micro_itches(job_id: str, raw) -> list[str]:
    """클라이언트가 보낸 micro-itch는 직업군 atlas에 있는 문장만 저장한다."""
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    allowed = set((pain_probe.get(job_id) or {}).get("micro_itches_ko", []))
    out: list[str] = []
    for item in raw[:12]:
        s = str(item or "").strip()[:180]
        if s and s in allowed and s not in out:
            out.append(s)
        if len(out) >= 6:
            break
    return out


def _micro_itches_from_indexes(job_id: str, raw_indexes) -> list[str]:
    """URL query의 mi=1&mi=2 값을 atlas 문장으로 복원한다."""
    atlas = (pain_probe.get(job_id) or {}).get("micro_itches_ko", [])
    out: list[str] = []
    if isinstance(raw_indexes, str):
        raw_indexes = [raw_indexes]
    if not isinstance(raw_indexes, list):
        return out
    for raw in raw_indexes[:12]:
        try:
            idx = int(str(raw).strip())
        except Exception:
            continue
        if 1 <= idx <= len(atlas):
            item = atlas[idx - 1]
            if item not in out:
                out.append(item)
        if len(out) >= 6:
            break
    return out


def _recommended_micro_itches(job_id: str, pain_id: str = "", limit: int = 2) -> list[str]:
    """저장된 aggregate 기준 추천 micro-itch. PII 원문은 반환하지 않는다."""
    try:
        pain_specific = pain_intents.recommended_micro_itches(
            job_id, pain_id, limit=limit, fallback_to_job=False,
        )
        if pain_specific:
            return pain_specific
    except Exception:
        pass
    try:
        productized = fulfillment_queue.productized_micro_itches(job_id, limit=limit)
        if productized:
            return productized
    except Exception:
        pass
    try:
        return pain_intents.recommended_micro_itches(job_id, pain_id, limit=limit)
    except Exception:
        return []


def handle_pain_intent(body: dict, ip: str = "") -> tuple[int, dict]:
    """직업별 가려움 온보딩 제출 검증/저장.

    기존 /offer/interest와 다른 지표다. 여기서는 '어떤 고통을 제품화할지'를 검증한다.
    """
    if not isinstance(body, dict):
        return 400, {"ok": False}
    if str(body.get("hp_url", "")).strip():      # honeypot: 봇은 저장하지 않고 조용히 성공
        return 200, {"ok": True}
    if not body.get("consent"):
        return 400, {"ok": False, "error": "consent required"}
    contact = str(body.get("contact", "")).strip()[:120]
    if not _valid_contact(contact):
        return 400, {"ok": False, "error": "invalid contact"}
    job = str(body.get("job", ""))[:60]
    if job not in JOBS:
        return 400, {"ok": False, "error": "invalid job"}
    res = _cached_scores().get(job)
    pain_id = str(body.get("pain_id", ""))[:80]
    if not painmap.get(res, pain_id):
        return 400, {"ok": False, "error": "invalid pain"}
    role = str(body.get("role_type", ""))[:40]
    if role not in {"employee", "freelancer", "jobseeker", "lead"}:
        role = "unknown"
    sample = str(body.get("sample_available", ""))[:40]
    if sample not in {"yes", "redacted", "no"}:
        sample = "unknown"
    offer_type = str(body.get("offer_type", "pain-intake"))[:40]
    if offer_type not in {"pain-intake", "pain-pack"}:
        offer_type = "pain-intake"
    situation = str(body.get("situation", "")).strip()[:600]
    micro_itches = _valid_micro_itches(job, body.get("micro_itches", []))
    store.append_pain_intent({
        "contact": contact,
        "job": job,
        "pain_id": pain_id,
        "role_type": role,
        "sample_available": sample,
        "situation": situation,
        "micro_itches": micro_itches,
        "offer_type": offer_type,
        "iph": _ip_hmac(ip),
    })
    return 200, {"ok": True}


# 결제 상태 매핑 — terminal-paid 이벤트만 좁게 인정(Codex fix: approved/authorized=승인≠캡처 제외).
# 배포 시 실제 PG의 '결제완료' 이벤트 값에 맞춰 조정(토스=DONE). 모르는 값=failed(보수적).
_PAY_SUCCESS = {"done", "paid", "completed"}
_PAY_REFUND = {"canceled", "cancelled", "refunded", "partial_canceled", "aborted", "chargeback"}
# 서명검증을 통과해도 이 금액과 다르면 paid로 인정하지 않음(무료/테스트/타상품 이벤트 차단).
PAYMENT_EXPECTED_AMOUNT = int(os.environ.get("PAYMENT_EXPECTED_AMOUNT", "99000") or 0)
PAIN_PAYMENT_EXPECTED_AMOUNT = int(os.environ.get("PAIN_PAYMENT_EXPECTED_AMOUNT", "39000") or 0)
PAYMENT_ALLOWED_AMOUNTS = os.environ.get("PAYMENT_ALLOWED_AMOUNTS", "")


def _payment_allowed_amounts() -> set[int]:
    """paid로 인정할 결제 금액 목록.

    기본은 범용 커리어 패키지 99,000원만. pain 파일럿 결제 링크를 켠 경우에만
    pain 금액을 추가한다. 여러 상품을 동시에 열 때는 PAYMENT_ALLOWED_AMOUNTS="99000,39000"처럼 명시.
    """
    if PAYMENT_ALLOWED_AMOUNTS.strip():
        vals = set()
        for part in PAYMENT_ALLOWED_AMOUNTS.split(","):
            try:
                n = int(part.strip())
            except ValueError:
                continue
            if n > 0:
                vals.add(n)
        return vals
    vals = set()
    if PAYMENT_EXPECTED_AMOUNT > 0:
        vals.add(int(PAYMENT_EXPECTED_AMOUNT))
    if PAIN_PAYMENT_URL and PAIN_PAYMENT_EXPECTED_AMOUNT > 0:
        vals.add(int(PAIN_PAYMENT_EXPECTED_AMOUNT))
    return vals


def _classify_pay_status(s: str) -> str:
    s = (s or "").strip().lower()
    if s in _PAY_REFUND:
        return "refunded"
    if s in _PAY_SUCCESS:
        return "paid"
    return "failed"


def _finalize_pay_status(status: str, amount) -> str:
    """서명검증 후 최종 상태 — 'paid'는 금액 검증까지 통과해야 인정(0/음수/기대불일치=failed).
    서명된 이벤트라도 금액이 우리 상품가와 다르면 진짜 지불주체로 세지 않는다(정직성)."""
    if status != "paid":
        return status
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        return "failed"
    allowed = _payment_allowed_amounts()
    if allowed and int(amount) not in allowed:
        return "failed"
    return "paid"


def _payment_contact(body: dict) -> str:
    for key in ("contact", "customerEmail", "customer_email", "email", "buyerEmail", "buyer_email"):
        val = str(body.get(key, "")).strip()[:120]
        if _valid_contact(val):
            return val
    return ""


def _paid_pain_fulfillment_meta(order_id: str, amount, body: dict, status: str) -> dict:
    if status != "paid":
        return {}
    if not PAIN_RELEASE_JOB or not PAIN_RELEASE_PAIN:
        return {}
    if not PAIN_PAYMENT_EXPECTED_AMOUNT or amount != PAIN_PAYMENT_EXPECTED_AMOUNT:
        return {}
    try:
        micro_itches = _recommended_micro_itches(PAIN_RELEASE_JOB, PAIN_RELEASE_PAIN)
        contact = _payment_contact(body)
        job = fulfillment_queue.enqueue_paid_release(
            order_id=order_id,
            job_id=PAIN_RELEASE_JOB,
            pain_id=PAIN_RELEASE_PAIN,
            amount=amount,
            contact=contact,
            micro_itches=micro_itches,
        )
        kickoff_path = fulfillment_queue.save_paid_release_kickoff(
            order_id=order_id,
            job_id=PAIN_RELEASE_JOB,
            pain_id=PAIN_RELEASE_PAIN,
            contact=contact,
            micro_itches=micro_itches,
        )
        return {
            "pain_release_job": PAIN_RELEASE_JOB,
            "pain_release_pain": PAIN_RELEASE_PAIN,
            "fulfillment_id": job.get("fulfillment_id", ""),
            "kickoff_path": kickoff_path,
        }
    except Exception as e:
        return {"fulfillment_error": str(e)[:160]}


def _payment_sig_ok(raw: bytes, sig: str) -> bool:
    """PG 웹훅 HMAC-SHA256 서명검증. 시크릿 미설정 or 서명 불일치면 False(=paid 확정 불가).
    상수시간 비교로 타이밍 공격 방지. 'paid'는 오직 이게 True일 때만."""
    if not PAYMENT_WEBHOOK_SECRET or not sig:
        return False
    sig = sig.strip().lower()
    if not sig or any(c not in "0123456789abcdef" for c in sig):   # 비-hex 헤더 → 예외 없이 거부
        return False
    expected = hmac.new(PAYMENT_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


def _rate_ok(ip: str) -> bool:
    now = time.monotonic()
    with _rl_lock:
        w = _rl.get(ip)
        if not w or now - w[0] > RATE_WINDOW:
            _rl[ip] = [now, 1]
            return True
        w[1] += 1
        return w[1] <= RATE_LIMIT


def _match_job(utterance: str) -> str | None:
    """발화에서 직업 식별 (이름 부분일치 or job_id)."""
    u = (utterance or "").strip().lower()
    for jid, job in JOBS.items():
        if jid in u or job["job_name_ko"] in utterance:
            return jid
    return None


def _summary_text(job_id: str) -> str:
    """현재 점수 요약 1~2줄 (task-first, 단정 없이)."""
    res = _cached_scores().get(job_id)
    if not res:
        return "아직 데이터가 준비 중입니다."
    snap = {"job_name_ko": res["job_name_ko"], "weather": res["weather"],
            "delta": store.delta_since_prev(job_id, res["index"]),
            "headline_task": res.get("headline_task"), "top_drivers": res.get("top_drivers", [])}
    push = notify.make_push(snap)["text"]
    head = res.get("headline_task") or {}
    return (f"[{res['weather']}] {res['job_name_ko']} · AI 압력 {res['index']}(보조지표)\n"
            f"가장 압력 높은 업무: {head.get('name_ko','-')} {head.get('index','')}\n\n{push}")


def _share_text(job_id: str) -> str:
    """친구에게 전달할 공유 메시지(바이럴 #1 레버). 전략가타입 캐시 있으면 활용."""
    res = _cached_scores().get(job_id) or {}
    strat = store.get_strategist(job_id) or {}
    name = res.get("job_name_ko", "")
    head = f"{strat['type_name']} {strat.get('emoji', '🧭')}\n" if strat.get("type_name") else ""
    link = CHANNEL_URL or "(채널 링크는 배포 후 제공)"
    return (f"📡 내 직무 AI 압력 리포트\n{head}{name} 압력지수 {res.get('index', '-')}({res.get('weather', '')})\n"
            f"내 직무는 AI에 얼마나 영향받을까? 업무별로 확인 👉 {link}")


def kakao_text(text: str, quick_replies: list[str] | None = None) -> dict:
    out = {"version": "2.0", "template": {"outputs": [{"simpleText": {"text": text}}]}}
    if quick_replies:
        out["template"]["quickReplies"] = [
            {"label": q, "action": "message", "messageText": q} for q in quick_replies]
    return out


def handle_kakao(body: dict) -> dict:
    if not isinstance(body, dict):
        return kakao_text("요청을 이해하지 못했습니다.")
    ureq = body.get("userRequest")
    ureq = ureq if isinstance(ureq, dict) else {}
    user = ureq.get("user")
    user = user if isinstance(user, dict) else {}
    user_id = user.get("id") if isinstance(user.get("id"), str) else ""
    utterance = ureq.get("utterance") if isinstance(ureq.get("utterance"), str) else ""
    # 고압력(가장 궁금해할) 직업 우선 노출 — quick reply 10개 한계 안에서 인게이지먼트 최대화
    job_names = [j["job_name_ko"] for j in
                 sorted(JOBS.values(), key=lambda x: -x.get("baseline", {}).get("index", 0))]
    cur = store.get_user_job(user_id) if user_id else None

    # 1) 리포트 보기 — 상세 결과화면 링크 (이전엔 데드엔드였음)
    if "리포트" in utterance:
        if cur:
            link = (f"{REPORT_BASE_URL}/report?user={user_id}" if REPORT_BASE_URL
                    else "(리포트 링크는 배포 후 제공됩니다)")
            return kakao_text(f"📄 '{JOBS[cur]['job_name_ko']}' 상세 리포트 — 업무별 압력·근거·이번 주 액션\n{link}",
                              quick_replies=["다른 직업"])
        return kakao_text("먼저 직업을 알려주세요 🙂", quick_replies=job_names[:10])

    # 2) 공유 — 친구에게 전달할 메시지 (바이럴)
    if "공유" in utterance:
        if cur:
            return kakao_text(_share_text(cur) + "\n\n☝️ 이 메시지를 친구에게 전달해보세요.",
                              quick_replies=["다른 직업"])
        return kakao_text("먼저 직업을 알려주세요 🙂", quick_replies=job_names[:10])

    # 3) 직업 변경/탐색
    if "다른 직업" in utterance or "변경" in utterance:
        return kakao_text("어떤 직업의 AI 압력을 볼까요?\n(목록에 없으면 직업명을 직접 입력하세요)",
                          quick_replies=job_names[:10])

    # 4) 직업 매칭 → 등록 + 요약
    jid = _match_job(utterance)
    if jid:
        if user_id:
            store.set_user_job(user_id, jid)
        return kakao_text(_summary_text(jid), quick_replies=["리포트 보기", "공유하기", "다른 직업"])

    # 5) 이미 등록된 사용자 → 현재 상태
    if cur:
        return kakao_text(_summary_text(cur), quick_replies=["리포트 보기", "공유하기", "다른 직업"])

    # 6) 첫 접점 — 온보딩(따뜻하게, 1탭 선택)
    return kakao_text(
        "👋 커리어 시그널이에요.\n내 직업이 AI에 얼마나 영향받는지 — 업무별로, 매일 알려드려요.\n\n직업을 선택하거나 직접 입력해보세요.",
        quick_replies=job_names[:10])


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _not_found(self):
        html = ('<!doctype html><meta charset="utf-8"><title>커리어 시그널</title>'
                '<body style="background:#09090b;color:#fafafa;font-family:-apple-system,sans-serif;'
                'text-align:center;padding:64px 20px"><div style="font-size:44px">📡</div>'
                '<h1 style="font-size:20px">페이지를 찾을 수 없어요</h1>'
                '<p style="color:#a1a1aa;font-size:14px">내 직업의 AI 압력을 확인해보세요.</p>'
                '<a href="/" style="display:inline-block;margin-top:18px;background:#fafafa;color:#09090b;'
                'padding:13px 26px;border-radius:26px;text-decoration:none;font-weight:700">시작하기 →</a></body>')
        self._send(404, html.encode("utf-8"), "text/html; charset=utf-8")

    def do_GET(self):
        if not _rate_ok(self.client_address[0]):
            return self._send(429, b"rate limited", "text/plain; charset=utf-8")
        parts = urlsplit(self.path)
        if parts.path in ("/", ""):     # 웹 진입점 — 직업 그리드(공유 바이럴 루프 완성)
            return self._send(200, report.landing_html(JOBS).encode("utf-8"),
                              "text/html; charset=utf-8")
        if parts.path == "/privacy":
            return self._send(200, report.privacy_html().encode("utf-8"),
                              "text/html; charset=utf-8")
        if parts.path == "/terms":
            return self._send(200, report.terms_html().encode("utf-8"),
                              "text/html; charset=utf-8")
        if parts.path == "/health":
            # presale_leads = 사전예약 리드 수(무료 연락처, 중복제거). ★리드≠지불.
            # pain_intents = 어떤 업무 고통을 해결하고 싶은지 남긴 수요 신호. ★지불 아님.
            # paid_customers = 서명검증된 웹훅으로 'paid' 확정된 주문 수(=진짜 WTP). reported는 제외.
            return self._json(200, {"ok": True, "jobs": list(JOBS),
                                    "presale_leads": store.interest_count(),
                                    "pain_intents": store.pain_intent_count(),
                                    "paid_customers": store.paid_count()})
        if parts.path == "/report":
            q = parse_qs(parts.query)
            jid = (q.get("job") or [None])[0]
            if not jid and q.get("user"):
                jid = store.get_user_job(q["user"][0])
            if jid not in JOBS:
                return self._not_found()
            res = _cached_scores().get(jid)
            # 배치가 캐시한 전략가타입 우선, 없으면 폴백 (요청마다 Gemini 호출 금지)
            strat = store.get_strategist(jid) or report.strategist_type(res, use_gemini=False)
            plan = store.get_actionplan(jid)   # 배치 캐시 premium 플랜(없으면 render가 결정적 폴백)
            html = report.render_html(res, strat, action_plan=plan)
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        if parts.path == "/detail":     # 상세 분석(drill-down) — 점진적 공개
            q = parse_qs(parts.query)
            jid = (q.get("job") or [None])[0]
            if not jid and q.get("user"):
                jid = store.get_user_job(q["user"][0])
            if jid not in JOBS:
                return self._not_found()
            res = _cached_scores().get(jid)
            return self._send(200, report.detail_html(res).encode("utf-8"),
                              "text/html; charset=utf-8")
        if parts.path == "/pain":       # 가려움 기반 온보딩 — 어떤 결과물을 원하는지 검증
            q = parse_qs(parts.query)
            jid = (q.get("job") or [None])[0]
            if not jid and q.get("user"):
                jid = store.get_user_job(q["user"][0])
            if jid not in JOBS:
                return self._not_found()
            pain_id = (q.get("pain") or [""])[0][:80]
            res = _cached_scores().get(jid)
            recommended = _recommended_micro_itches(jid, pain_id)
            return self._send(200, report.pain_intake_html(
                res, pain_id, recommended_micro_itches=recommended,
            ).encode("utf-8"),
                              "text/html; charset=utf-8")
        if parts.path == "/pain-offer":  # 특정 업무 고통 1개를 줄이는 좁은 파일럿 오퍼
            q = parse_qs(parts.query)
            jid = (q.get("job") or [None])[0]
            if not jid and q.get("user"):
                jid = store.get_user_job(q["user"][0])
            if jid not in JOBS:
                return self._not_found()
            pain_id = (q.get("pain") or [""])[0][:80]
            res = _cached_scores().get(jid)
            micro_itches = _micro_itches_from_indexes(jid, q.get("mi", []))
            if not micro_itches:
                micro_itches = _recommended_micro_itches(jid, pain_id)
            return self._send(200, report.pain_offer_html(res, pain_id, PAIN_PAYMENT_URL or None,
                                                          micro_itches=micro_itches).encode("utf-8"),
                              "text/html; charset=utf-8")
        if parts.path == "/offer":      # AI 대응 스프린트 사전판매(런칭=지불주체 테스트)
            q = parse_qs(parts.query)
            jid = (q.get("job") or [None])[0]
            if not jid and q.get("user"):
                jid = store.get_user_job(q["user"][0])
            if jid not in JOBS:
                return self._not_found()
            res = _cached_scores().get(jid)
            # 무근거 판매 금지(제품레벨) — 리포트 CTA와 동일 기준으로 grounded 판정(Codex fix).
            plan = store.get_actionplan(jid)
            if plan is None:
                import actionplan
                plan = actionplan.make_action_plan(res, use_gemini=False)
            grounded = bool(plan.get("guardrail_ok") and plan.get("actions"))
            return self._send(200, report.offer_html(res, PAYMENT_URL or None, grounded=grounded).encode("utf-8"),
                              "text/html; charset=utf-8")
        if parts.path == "/payment/success":
            # PG 결제 후 클라이언트 리다이렉트. 쿼리는 누구나 조작 가능 → 아무것도 저장하지 않는다
            # (Codex fix: 공개 append-only DoS 차단 + 조작 가능한 'reported'는 신뢰 불가 노이즈).
            # 진짜 'paid'는 오직 서명검증된 /webhook/payment 로만. 페이지는 '접수 확인'으로 정직 표현.
            q = parse_qs(parts.query)
            job = (q.get("job") or [""])[0][:60]
            return self._send(200, report.payment_pending_html(job if job in JOBS else "").encode("utf-8"),
                              "text/html; charset=utf-8")
        self._not_found()

    def do_POST(self):
        if not _rate_ok(self.client_address[0]):
            return self._json(429, kakao_text("요청이 많아 잠시 후 다시 시도해 주세요."))
        parts = urlsplit(self.path)
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            return self._json(400, kakao_text("잘못된 요청입니다."))
        if length < 0 or length > MAX_BODY:
            return self._json(413, kakao_text("요청이 너무 큽니다."))
        raw = self.rfile.read(length) if length else b"{}"
        if parts.path == "/webhook/kakao":
            # 토큰 설정 시 일치 요구 (카카오 i오픈빌더 스킬 URL에 ?token= 박아 호출)
            if WEBHOOK_TOKEN and parse_qs(parts.query).get("token", [""])[0] != WEBHOOK_TOKEN:
                return self._json(401, kakao_text("인증에 실패했습니다."))
            try:
                body = json.loads(raw or b"{}")
            except Exception:
                return self._json(400, kakao_text("요청을 이해하지 못했습니다."))
            return self._json(200, handle_kakao(body))
        if parts.path == "/offer/interest":   # 사전예약 리드 수집 (지불주체 스모크테스트)
            try:
                body = json.loads(raw or b"{}")
            except Exception:
                return self._json(400, {"ok": False})
            if not isinstance(body, dict):
                return self._json(400, {"ok": False})
            # 봇 트랩(honeypot): 사람은 비워두는 숨김필드가 채워지면 = 봇 → 조용히 통과(저장 안 함)
            if str(body.get("hp_url", "")).strip():
                return self._json(200, {"ok": True})
            # 개인정보 수집 동의 필수 (PIPA — 화면 동의 체크와 결박)
            if not body.get("consent"):
                return self._json(400, {"ok": False, "error": "consent required"})
            contact = str(body.get("contact", "")).strip()[:120]
            if not _valid_contact(contact):
                return self._json(400, {"ok": False, "error": "invalid contact"})
            job = str(body.get("job", ""))[:60]
            # IP 평문 저장 금지. 비밀 솔트(INTEREST_SALT/없으면 WEBHOOK_TOKEN)로 HMAC →
            # 솔트 없으면 아예 저장 안 함(무염 SHA256은 IP 사전대입으로 역추적 가능하므로).
            store.append_interest({                # 중복(contact+job)이면 내부에서 skip
                "contact": contact,
                "job": job if job in JOBS else "",
                "price_shown": str(body.get("price_shown", ""))[:20],
                "iph": _ip_hmac(self.client_address[0]),
            })
            return self._json(200, {"ok": True})
        if parts.path == "/pain/intent":  # 가려움별 수요 신호 수집(사전신청, 결제 아님)
            try:
                body = json.loads(raw or b"{}")
            except Exception:
                return self._json(400, {"ok": False})
            code, obj = handle_pain_intent(body, self.client_address[0])
            return self._json(code, obj)
        if parts.path == "/webhook/payment":
            # PG 서버→서버 웹훅. 'paid' 확정은 오직 여기서, 서명검증 통과 시에만(정직성 불가침).
            if not PAYMENT_WEBHOOK_SECRET:
                # 시크릿 미설정 → 결제 완료를 확정할 방법이 없음 → 501(절대 paid로 안 셈).
                return self._json(501, {"ok": False, "error": "payment webhook not configured"})
            sig = self.headers.get(PAYMENT_SIG_HEADER, "")
            if not _payment_sig_ok(raw, sig):
                return self._json(401, {"ok": False, "error": "bad signature"})
            try:
                body = json.loads(raw or b"{}")
            except Exception:
                return self._json(400, {"ok": False})
            if not isinstance(body, dict):
                return self._json(400, {"ok": False})
            order_id = str(body.get("orderId") or body.get("order_id") or "")[:80]
            if not order_id:
                return self._json(400, {"ok": False, "error": "no order_id"})
            amount = body.get("amount")
            if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                amount = None
            # 금액 검증까지 통과해야 paid(서명O라도 금액 0/음수/기대불일치면 failed로 강등 — 정직성).
            status = _finalize_pay_status(_classify_pay_status(str(body.get("status", ""))), amount)
            job = str(body.get("job") or body.get("orderName") or "")[:60]
            fulfillment_meta = _paid_pain_fulfillment_meta(order_id, amount, body, status)
            payment_job = fulfillment_meta.get("pain_release_job") or (job if job in JOBS else "")
            # 멱등: append-only + _reduce_payments가 order_id별 상태랭크로 축약 → 웹훅 재전송 안전.
            extra = {"src": "webhook"}
            extra.update(fulfillment_meta)
            store.save_payment(order_id, payment_job, amount, status, extra=extra)
            res = {"ok": True, "status": status}
            if fulfillment_meta.get("fulfillment_id"):
                res["fulfillment_id"] = fulfillment_meta["fulfillment_id"]
            return self._json(200, res)
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def log_message(self, *a):  # 조용히
        pass


def serve(port: int = 8000, host: str = "127.0.0.1"):
    # 기본 로컬 바인딩. 배포 시 reverse proxy(TLS/auth/rate limit) 뒤에 두고 host 지정.
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"커리어 시그널 봇 서버 {host}:{port}  (직업 {len(JOBS)}개)")
    srv.serve_forever()


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8000,
          host=os.environ.get("HOST", "127.0.0.1"))
