# Zero-dependency MCP server — no pip install needed.
# Provide YOUTUBE_API_KEY at runtime: docker run -e YOUTUBE_API_KEY=... <image>
FROM python:3.12-slim
WORKDIR /app
COPY youtube_mcp.py youtube_core.py ./
ENTRYPOINT ["python", "youtube_mcp.py"]
