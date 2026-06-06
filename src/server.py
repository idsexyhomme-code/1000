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

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import notify
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
RATE_LIMIT = int(os.environ.get("RATE_LIMIT", "60"))  # IP당 윈도우 요청 수
RATE_WINDOW = 60.0
_rl_lock = threading.Lock()
_rl: dict[str, list] = {}  # ip -> [window_start, count]


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
    job_names = [j["job_name_ko"] for j in JOBS.values()]

    jid = _match_job(utterance)
    if jid:
        if user_id:
            store.set_user_job(user_id, jid)
        return kakao_text(_summary_text(jid), quick_replies=["리포트 보기", "다른 직업"])

    # 이미 등록된 사용자면 현재 상태
    cur = store.get_user_job(user_id) if user_id else None
    if cur and ("리포트" not in utterance):
        return kakao_text(_summary_text(cur), quick_replies=["리포트 보기", "다른 직업"])

    return kakao_text(
        "당신의 직업을 알려주세요. AI 압력 시그널을 매일 보내드립니다.\n(현재 베타: 아래에서 선택)",
        quick_replies=job_names)


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

    def do_GET(self):
        if not _rate_ok(self.client_address[0]):
            return self._send(429, b"rate limited", "text/plain; charset=utf-8")
        parts = urlsplit(self.path)
        if parts.path == "/health":
            return self._json(200, {"ok": True, "jobs": list(JOBS)})
        if parts.path == "/report":
            q = parse_qs(parts.query)
            jid = (q.get("job") or [None])[0]
            if not jid and q.get("user"):
                jid = store.get_user_job(q["user"][0])
            if jid not in JOBS:
                return self._send(404, b"unknown job", "text/plain; charset=utf-8")
            res = _cached_scores().get(jid)
            # 배치가 캐시한 전략가타입 우선, 없으면 폴백 (요청마다 Gemini 호출 금지)
            strat = store.get_strategist(jid) or report.strategist_type(res, use_gemini=False)
            plan = store.get_actionplan(jid)   # 배치 캐시 premium 플랜(없으면 render가 결정적 폴백)
            html = report.render_html(res, strat, action_plan=plan)
            return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        self._send(404, b"not found", "text/plain; charset=utf-8")

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
