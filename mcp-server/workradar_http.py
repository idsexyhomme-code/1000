"""WorkRadar HTTP API — zero-dependency stdlib server exposing the same diagnosis
engine over HTTP/JSON. Powers the Custom GPT (via Actions) and can back the web app.

Endpoints (GET query-string or POST JSON, both work):
    GET  /                       -> health + info
    POST /assess  {job, tasks?, experience_years?, uses_ai_tools?}
    GET  /assess?job=nurse&uses_ai_tools=sometimes
    POST /search  {query}   |  GET /search?q=nurse
    POST /compare {job_a, job_b}  |  GET /compare?job_a=..&job_b=..

Run:  python3 workradar_http.py            (PORT env or 8000)
Deploy: any host that runs `python3 workradar_http.py` and sets $PORT (e.g. Render).
"""
import os, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import workradar_core as wr


def _dispatch(path, params):
    if path == "/assess":
        job = params.get("job")
        if not job:
            return 400, {"error": "missing 'job'"}
        tasks = params.get("tasks")
        if isinstance(tasks, str):
            tasks = [t.strip() for t in tasks.split(",") if t.strip()]
        exp = params.get("experience_years")
        try:
            exp = int(exp) if exp not in (None, "") else None
        except (TypeError, ValueError):
            exp = None
        return 200, wr.assess(job, tasks=tasks or None, experience_years=exp,
                              uses_ai_tools=params.get("uses_ai_tools") or None)
    if path == "/search":
        q = params.get("query") or params.get("q") or ""
        return 200, {"results": wr.search(q, limit=8)}
    if path == "/compare":
        a, b = params.get("job_a"), params.get("job_b")
        if not a or not b:
            return 400, {"error": "missing 'job_a' or 'job_b'"}
        return 200, wr.compare(a, b)
    return 404, {"error": "not found", "endpoints": ["/assess", "/search", "/compare"]}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", ""):
            return self._send(200, {"service": "WorkRadar API", "version": "0.1.0",
                                    "endpoints": ["/assess", "/search", "/compare"],
                                    "docs": wr.FULL_TEST})
        params = {k: v[0] for k, v in parse_qs(u.query).items()}
        code, out = _dispatch(u.path, params)
        self._send(code, out)

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            params = json.loads(self.rfile.read(n) or b"{}") if n else {}
            if not isinstance(params, dict):
                raise ValueError
        except Exception:
            return self._send(400, {"error": "invalid JSON body"})
        code, out = _dispatch(urlparse(self.path).path, params)
        self._send(code, out)

    def log_message(self, *a):  # quiet
        pass


def main():
    port = int(os.environ.get("PORT", "8000"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("WorkRadar API on :%d" % port)
    srv.serve_forever()


if __name__ == "__main__":
    main()
