"""WorkRadar MCP server — lets an AI assistant diagnose AI job-replacement risk.

Exposes the WorkRadar diagnosis engine as MCP tools so any MCP-capable AI
(Claude Desktop, Claude Code, …) can answer "will AI take my job?" with a
task-level, source-anchored, honest read — and route the person to their next move.

Zero external dependencies required: if the official `mcp` SDK is installed it's used;
otherwise a built-in minimal JSON-RPC-over-stdio server runs. So this works on any
Python 3.8+ with just `python workradar_mcp.py` — no pip install needed.
"""
import sys, json
import workradar_core as wr

FULL = wr.FULL_TEST


# ---- tool implementations (shared by both transports) ----
def _assess(job, tasks=None, experience_years=None, uses_ai_tools=None):
    return wr.assess(job, tasks=tasks or None,
                     experience_years=experience_years or None,
                     uses_ai_tools=uses_ai_tools or None)

def _search(query):
    return wr.search(query, limit=8)

def _compare(job_a, job_b):
    return wr.compare(job_a, job_b)


# ---- tool registry (name -> description, JSON Schema, fn) ----
TOOLS = {
    "assess_ai_job_risk": {
        "fn": _assess,
        "description": (
            "Assess how exposed a specific job is to AI automation, task by task. Use whenever "
            "someone asks about AI and their career — 'will AI take my job?', 'how safe is my job "
            "from AI?', 'is [job] going to be automated?', 'which of my tasks will AI replace?' — or "
            "wants to know what to do about it. Returns an AI-pressure score (0-100), weather band, "
            "most-exposed and most-resilient tasks, a suggested next move, a full-report link, and an "
            "honest disclaimer. Scores are DIRECTIONAL references, not predictions — surface the disclaimer."),
        "schema": {
            "type": "object",
            "properties": {
                "job": {"type": "string", "description": "The person's job title in plain words (e.g. 'nurse', 'software engineer')."},
                "tasks": {"type": "array", "items": {"type": "string"}, "description": "Optional — what they actually spend their week on; makes the score personal."},
                "experience_years": {"type": "integer", "description": "Optional years of experience."},
                "uses_ai_tools": {"type": "string", "description": "Optional — how much they use AI at work ('never' / 'sometimes' / 'daily')."},
            },
            "required": ["job"],
        },
    },
    "search_jobs": {
        "fn": _search,
        "description": ("Find matching job titles in the WorkRadar dataset (1,300+ roles). Use to "
                        "disambiguate before assess_ai_job_risk when a title is vague."),
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    "compare_ai_exposure": {
        "fn": _compare,
        "description": ("Compare two jobs and say which is more exposed to AI, with both scores. "
                        "For 'is X or Y more at risk from AI?' Directional reference, not a prediction."),
        "schema": {"type": "object",
                   "properties": {"job_a": {"type": "string"}, "job_b": {"type": "string"}},
                   "required": ["job_a", "job_b"]},
    },
}


# ---- built-in minimal MCP server (stdlib only, JSON-RPC 2.0 over stdio) ----
def _write(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def _result(mid, result):
    _write({"jsonrpc": "2.0", "id": mid, "result": result})

def _error(mid, code, message):
    _write({"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}})

def run_stdlib():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}
        if method == "initialize":
            _result(mid, {"protocolVersion": "2024-11-05",
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "workradar", "version": "1.0.0"}})
        elif method in ("notifications/initialized", "notifications/cancelled"):
            continue  # notification — no response
        elif method == "ping":
            _result(mid, {})
        elif method == "tools/list":
            _result(mid, {"tools": [{"name": n, "description": t["description"], "inputSchema": t["schema"]}
                                    for n, t in TOOLS.items()]})
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            t = TOOLS.get(name)
            if not t:
                _error(mid, -32602, "Unknown tool: %s" % name)
                continue
            try:
                res = t["fn"](**args)
                _result(mid, {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}]})
            except Exception as e:
                _result(mid, {"content": [{"type": "text", "text": "error: %s" % e}], "isError": True})
        elif mid is not None:
            _error(mid, -32601, "Method not found: %s" % method)


def run_sdk():
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("workradar")
    for name, t in TOOLS.items():
        mcp.add_tool(t["fn"], name=name, description=t["description"])
    mcp.run()


def main():
    try:
        import mcp.server.fastmcp  # noqa: F401
        run_sdk()
    except Exception:
        run_stdlib()


if __name__ == "__main__":
    main()
