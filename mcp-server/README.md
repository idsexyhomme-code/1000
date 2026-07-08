# WorkRadar MCP

**Let an AI assistant answer "will AI take my job?" — task by task, with sources, honestly.**

WorkRadar MCP exposes the [WorkRadar](https://idsexyhomme-code.github.io/1000/web/en/)
diagnosis engine as [Model Context Protocol](https://modelcontextprotocol.io) tools.
Any MCP-capable AI (Claude Desktop, Claude Code, …) can call it to give someone a
task-level AI-exposure read on their job — and route them to their next move.

Scores are **directional references, not predictions** (hand-estimated, uncalibrated),
and anchored to public AI-exposure research (AIOE, Felten/Raj/Seamans 2021) where available.

## Tools
| Tool | What it does |
|---|---|
| `assess_ai_job_risk(job, tasks?, experience_years?, uses_ai_tools?)` | Full diagnosis: AI-pressure 0–100, band, most-exposed & most-resilient tasks, suggested next move, full-report link, disclaimer |
| `search_jobs(query)` | Find matching job titles (1,300+ roles) to disambiguate |
| `compare_ai_exposure(job_a, job_b)` | Which of two jobs is more AI-exposed |

## Install (local)
**Zero dependencies.** Runs on any Python 3.8+ with no pip install:
```bash
python3 workradar_mcp.py    # runs over stdio (built-in minimal MCP server)
```
If the official `mcp` SDK happens to be installed (Python 3.10+), it's used automatically;
otherwise a built-in JSON-RPC-over-stdio server handles the protocol. Either way, same tools.

Quick manual check (no client needed):
```bash
printf '%s\n' \
 '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
 '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"assess_ai_job_risk","arguments":{"job":"nurse"}}}' \
 | python3 workradar_mcp.py
```

### Claude Desktop / Claude Code
Add to your MCP config (`claude_desktop_config.json` or `.mcp.json`):
```json
{
  "mcpServers": {
    "workradar": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp-server/workradar_mcp.py"]
    }
  }
}
```
Then ask: *"Am I at risk from AI? I'm a nurse."* → the assistant calls `assess_ai_job_risk`.

### Once published (see [PUBLISH.md](PUBLISH.md))
```bash
uvx workradar-mcp          # or: pipx run workradar-mcp
```
Config becomes `{"command": "uvx", "args": ["workradar-mcp"]}`.

## Example
```
assess_ai_job_risk(job="nurse", tasks=["charting","bedside care"], uses_ai_tools="sometimes")
→ { "job": "Nurse", "ai_pressure": 43, "band": "Cloudy",
    "most_exposed_tasks": [...], "most_resilient_tasks": [...],
    "next_move": { "path": "defend", "headline": "Stay and out-level the AI", ... },
    "full_report_url": "https://idsexyhomme-code.github.io/1000/web/en/?job=nurse",
    "external_anchor": { "source": "AIOE (Felten, Raj & Seamans 2021)", ... },
    "disclaimer": "Directional reference, not a prediction. …" }
```

## Honesty
Never presents scores as certainties. Every response carries the disclaimer; anchored
jobs are labeled with their source and confidence. This is a directional tool for
orientation — not career/financial advice, and not a verdict on any person.

---
Part of WorkRadar. Full free test + 100+ role breakdowns: https://idsexyhomme-code.github.io/1000/web/en/
