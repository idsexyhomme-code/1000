# WorkRadar — Custom GPT 설정 (GPT 스토어 = 수백만 접근)

MCP는 Claude 계열. 이건 **ChatGPT 쪽** 진출. GPT는 Actions로 API를 호출 → 그래서
**HTTP API 배포가 선행**이에요 (`workradar_http.py`). 아래 순서.

## 1. API 배포 (Render, 무료 티어)
`workradar_http.py`는 무의존성 → Render에서 바로 돎.
- Render → New → Web Service → 레포 `idsexyhomme-code/1000` 연결
- Root Directory: `mcp-server`
- Build Command: (없음)
- Start Command: `python3 workradar_http.py`  (Render가 $PORT 주입)
- 배포되면 URL 확보 (예: `https://workradar-api.onrender.com`)
- 확인: `curl https://…/assess?job=nurse`

## 2. Custom GPT 생성 (chatgpt.com, Plus 계정 필요)
Explore GPTs → Create → Configure:

**Name:** `WorkRadar — AI Job Risk`
**Description:**
> Will AI take your job? Get a task-level, source-anchored, honest read — not fear-bait.

**Instructions:**
```
You help people understand how exposed their job is to AI, task by task.

When a user mentions their job or asks about AI and their career, call assessAiJobRisk
with their job (and their tasks / AI usage if they mention them). Use searchJobs to
disambiguate a vague title, and compareAiExposure for "is X or Y more at risk" questions.

Always present the result faithfully AND surface the disclaimer: scores are directional
references, hand-estimated, NOT predictions or probabilities — never state them as certain.
Explain the most-exposed and most-resilient tasks, then the suggested next move. Offer the
full_report_url for the complete free test. Be honest, specific, and calm — not alarmist.
Never give guaranteed career/financial outcomes.
```

**Conversation starters:**
- `Will AI take my job? I'm a nurse.`
- `Which of my tasks will AI replace? I'm a graphic designer.`
- `Is an accountant or a plumber more at risk from AI?`
- `How do I stay relevant as AI advances in my field?`

**Actions:** Create action → paste `openapi.yaml` → set `servers.url` to your Render URL.
Authentication: None (public read API).

**Privacy policy:** point to `.../web/en/privacy.html`.

## 3. 게시
Save → Publish (Everyone). GPT 스토어 카테고리: Productivity / Education.

## 정직하게
- Actions는 API가 살아있어야 작동 (Render 무료티어는 잠들었다 깨느라 첫 호출 느릴 수 있음).
- GPT 스토어는 검색 노출 = L1(발견) 채널. MCP(Claude)와 합쳐 **양쪽 AI 생태계 커버.**
