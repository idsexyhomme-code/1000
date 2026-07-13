# YouTube MCP

**Let an AI agent research & monitor YouTube — search, stats, comments, uploads, trending — in one call.**

YouTube MCP exposes the official **YouTube Data API v3** as [Model Context Protocol](https://modelcontextprotocol.io)
tools. Any MCP-capable AI (Claude Desktop, Claude Code, …) can call it to pull real
YouTube data on demand — no scraping, no proxies, no bans, fully within YouTube's Terms.

## Tools
| Tool | What it does | Quota |
|---|---|---|
| `youtube_search(query, max_results?, order?, published_after?, region?)` | Search videos by keyword | 100 |
| `youtube_video_stats(video_ids)` | Views, likes, comments, duration, tags | 1 |
| `youtube_channel_stats(channel)` | Subscribers, video count, total views | 1 |
| `youtube_channel_videos(channel, max_results?)` | A channel's most recent uploads | ~2 |
| `youtube_comments(video_id, max_results?, order?)` | Top-level comments on a video | 1 |
| `youtube_trending(region?, category_id?, max_results?)` | Most popular videos in a country | 1 |

`channel` accepts a channel ID (`UC…`) or a `@handle`. YouTube gives **10,000 free quota units/day** —
enough for thousands of list/stat calls (search is the only expensive one at 100 units each).

## Get a free API key (2 min)
1. Go to <https://console.cloud.google.com> → create/select a project.
2. **APIs & Services → Library → search "YouTube Data API v3" → Enable.**
3. **APIs & Services → Credentials → Create credentials → API key.**
4. Export it:
   ```bash
   export YOUTUBE_API_KEY=your_key_here
   ```
The key is read **from the environment only** — never hard-code or commit it.

## Install (local)
**Zero dependencies.** Runs on any Python 3.8+ with no pip install:
```bash
export YOUTUBE_API_KEY=your_key_here
python3 youtube_mcp.py          # runs over stdio (built-in minimal MCP server)
```
If the official `mcp` SDK happens to be installed (Python 3.10+), it's used automatically;
otherwise a built-in JSON-RPC-over-stdio server handles the protocol. Same tools either way.

Quick manual check (no client needed):
```bash
export YOUTUBE_API_KEY=your_key_here
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"youtube_search","arguments":{"query":"ai coding agents","max_results":3}}}' \
 | python3 youtube_mcp.py
```

### Claude Desktop / Claude Code
Add to your MCP config (`claude_desktop_config.json` or `.mcp.json`):
```json
{
  "mcpServers": {
    "youtube": {
      "command": "python3",
      "args": ["/absolute/path/to/youtube-mcp/youtube_mcp.py"],
      "env": { "YOUTUBE_API_KEY": "your_key_here" }
    }
  }
}
```
Then ask: *"What are the top trending videos on YouTube in the US right now?"* → the assistant calls `youtube_trending`.

## Example
```
youtube_search(query="ai job automation", order="viewCount", max_results=3)
→ { "query": "ai job automation", "count": 3,
    "results": [ { "video_id": "…", "title": "…", "channel": "…",
                   "published_at": "…", "url": "https://www.youtube.com/watch?v=…" }, … ] }
```

## Honesty / scope
Uses only the **official YouTube Data API v3** (public data, within Terms). It does not
scrape, does not bypass rate limits, and returns exactly what the API returns. Quota and
availability are Google's; comment/stat access follows each video's/channel's settings.
Not affiliated with YouTube or Google.
