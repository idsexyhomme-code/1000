# Zero-dependency MCP server — no pip install needed.
FROM python:3.12-slim
WORKDIR /app
COPY workradar_mcp.py workradar_core.py jobs.json ./
ENTRYPOINT ["python", "workradar_mcp.py"]
