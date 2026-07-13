"""YouTube MCP server — lets an AI agent research & monitor YouTube.

Exposes the official YouTube Data API v3 as MCP tools so any MCP-capable AI
(Claude Desktop, Claude Code, …) can search videos, pull stats, read comments,
list a channel's uploads, and see what's trending — in one call.

Zero external dependencies required: if the official `mcp` SDK is installed it's
used; otherwise a built-in minimal JSON-RPC-over-stdio server runs. So this works
on any Python 3.8+ with just `python3 youtube_mcp.py` — no pip install needed.

Requires a free YouTube Data API key in the environment: YOUTUBE_API_KEY (see README).
"""
import sys
import json
import youtube_core as yt


# ---- tool registry (name -> description, JSON Schema, fn) ----
TOOLS = {
    "youtube_search": {
        "fn": yt.search,
        "description": (
            "Search YouTube videos by keyword. Use to find videos on a topic, scout a niche, "
            "or research what's being published. Returns video id, title, channel, publish date, "
            "description and URL. Quota cost: 100 units. order = relevance|date|viewCount|rating|title; "
            "published_after is ISO8601 UTC (e.g. '2026-01-01T00:00:00Z') to only get newer videos."),
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords."},
                "max_results": {"type": "integer", "description": "1-50 (default 10)."},
                "order": {"type": "string", "description": "relevance|date|viewCount|rating|title."},
                "published_after": {"type": "string", "description": "ISO8601 UTC; only videos newer than this."},
                "region": {"type": "string", "description": "ISO 3166-1 alpha-2 country code, e.g. 'US', 'KR'."},
            },
            "required": ["query"],
        },
    },
    "youtube_video_stats": {
        "fn": yt.video_stats,
        "description": (
            "Get stats for one or more videos: views, likes, comment count, duration, tags, channel. "
            "Use to compare performance or enrich search results. Quota cost: 1 unit. Up to 50 IDs."),
        "schema": {
            "type": "object",
            "properties": {
                "video_ids": {"type": "array", "items": {"type": "string"},
                              "description": "Video IDs, up to 50."},
            },
            "required": ["video_ids"],
        },
    },
    "youtube_channel_stats": {
        "fn": yt.channel_stats,
        "description": (
            "Get a channel's subscriber count, total video count and total views. Use to size up a "
            "creator or competitor. Quota cost: 1 unit. channel = a channel ID (starts 'UC…') or a @handle."),
        "schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel ID ('UC…') or @handle."},
            },
            "required": ["channel"],
        },
    },
    "youtube_channel_videos": {
        "fn": yt.channel_videos,
        "description": (
            "List a channel's most recent uploads (newest first). Use to monitor a creator/competitor "
            "over time. Quota cost: ~2 units. channel = a channel ID ('UC…') or a @handle."),
        "schema": {
            "type": "object",
            "properties": {
                "channel": {"type": "string", "description": "Channel ID ('UC…') or @handle."},
                "max_results": {"type": "integer", "description": "1-50 (default 10)."},
            },
            "required": ["channel"],
        },
    },
    "youtube_comments": {
        "fn": yt.comments,
        "description": (
            "Read top-level comments on a video (audience reaction, questions, sentiment). "
            "Quota cost: 1 unit. order = relevance|time. Fails if comments are disabled on the video."),
        "schema": {
            "type": "object",
            "properties": {
                "video_id": {"type": "string", "description": "The video ID."},
                "max_results": {"type": "integer", "description": "1-100 (default 20)."},
                "order": {"type": "string", "description": "relevance|time."},
            },
            "required": ["video_id"],
        },
    },
    "youtube_trending": {
        "fn": yt.trending,
        "description": (
            "Get the most popular (trending) videos in a country right now. Use for trend/hook research. "
            "Quota cost: 1 unit. region = ISO 3166-1 alpha-2 (e.g. 'US', 'KR'). category_id optional."),
        "schema": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "ISO 3166-1 alpha-2 country code, e.g. 'US', 'KR'."},
                "category_id": {"type": "string", "description": "Optional YouTube category ID to narrow the chart."},
                "max_results": {"type": "integer", "description": "1-50 (default 10)."},
            },
            "required": [],
        },
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
                          "serverInfo": {"name": "youtube", "version": "1.0.0"}})
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
    mcp = FastMCP("youtube")
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
