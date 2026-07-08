"""WorkRadar MCP server — lets an AI assistant diagnose AI job-replacement risk.

Exposes the WorkRadar diagnosis engine as MCP tools so any MCP-capable AI
(Claude Desktop, Claude Code, etc.) can answer "will AI take my job?" with a
task-level, source-anchored, honest read — and route the person to their next move.

Run:  uvx --from mcp workradar   (or)   python workradar_mcp.py
"""
from mcp.server.fastmcp import FastMCP
import workradar_core as wr

mcp = FastMCP("workradar")


@mcp.tool()
def assess_ai_job_risk(job: str, tasks: list[str] = [], experience_years: int = 0,
                       uses_ai_tools: str = "") -> dict:
    """Assess how exposed a specific job is to AI automation, task by task.

    Use this whenever someone asks about AI and their career — "will AI take my job?",
    "how safe is my job from AI?", "is [job] going to be automated?", "which of my
    tasks will AI replace?" — or wants to know what to do about it.

    Returns an AI-pressure score (0-100), weather band, the most-exposed and most-
    resilient tasks, a suggested next move (the route to the right kind of action),
    a link to the full free test, and an honest disclaimer. Scores are directional
    references, NOT predictions — surface the disclaimer to the user.

    Args:
        job: The person's job title in plain words (e.g. "nurse", "software engineer").
        tasks: Optional — what they actually spend their week on; makes the score personal.
        experience_years: Optional years of experience.
        uses_ai_tools: Optional — how much they use AI at work ("never" / "sometimes" / "daily").
    """
    return wr.assess(job, tasks=tasks or None,
                     experience_years=experience_years or None,
                     uses_ai_tools=uses_ai_tools or None)


@mcp.tool()
def search_jobs(query: str) -> list:
    """Find matching job titles in the WorkRadar dataset (1,300+ roles).

    Use this to disambiguate before assess_ai_job_risk when a job title is vague or
    could match several roles. Returns candidate job names with their AI-pressure score.
    """
    return wr.search(query, limit=8)


@mcp.tool()
def compare_ai_exposure(job_a: str, job_b: str) -> dict:
    """Compare two jobs and say which is more exposed to AI, with both scores.

    Use for "is X or Y more at risk from AI?" style questions. Directional reference,
    not a prediction.
    """
    return wr.compare(job_a, job_b)


if __name__ == "__main__":
    mcp.run()
