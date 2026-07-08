# WorkRadar MCP — 런치/씨앗뿌리기 킷 (발행 후)

개발자·AI 커뮤니티 대상 (소비자용 Product Hunt 킷과 별개).
원칙: **가치 먼저, 업보트 구걸 X.** 이 판은 정직·무의존성 같은 *엔지니어가 좋아하는 디테일*이 먹힘.

**핵심 훅 3개:**
- 🪶 **무의존성** — stdlib만으로 MCP 프로토콜 구현, `python3 workradar_mcp.py` 하나면 됨 (pip install 0)
- 🔍 **task 단위 + 출처 앵커(AIOE)** — 직업이 아니라 task별 노출도, 1,300+ 역할
- 🧭 **정직** — 점수를 예측이 아니라 *방향성 참조*로 라벨. fear-bait 반대

---

## Show HN (news.ycombinator.com/submit)
**제목:**
```
Show HN: An MCP server that tells you your AI job-replacement risk (zero deps)
```
**본문(첫 코멘트):**
```
I kept seeing "AI will kill X jobs" headlines that never show their work, and
noticed assistants hand-wave when you ask "will AI take MY job?". So I made it a
tool the assistant can actually call.

WorkRadar MCP exposes a task-level diagnosis: give it a job (+ optional tasks),
it returns an AI-pressure score, the most-exposed and most-resilient tasks, a
suggested next move, and — honestly — a disclaimer that scores are directional
references, not predictions. Anchored to public AI-exposure research (AIOE,
Felten/Raj/Seamans 2021) where available. 1,300+ roles.

Design notes that might interest folks here:
- Zero dependencies. It uses the official `mcp` SDK if present, else a built-in
  ~100-line stdlib JSON-RPC-over-stdio server. Runs on any Python 3.8+, no install.
- The scoring is deliberately labeled uncalibrated/hand-estimated — I'd rather ship
  a transparent, arguable frame than a fake-precise number.

Feedback on the method (and the honesty framing) very welcome.
```

## r/mcp (+ r/ClaudeAI, r/LocalLLaMA)
**제목:** `WorkRadar MCP: ask your assistant "will AI take my job?" and get a task-level answer`
**본문:** 위 훅 3개 + 설치 한 줄(`python3 workradar_mcp.py`) + Claude Desktop 설정 스니펫 + "피드백 환영". 각 서브 **자기홍보 규칙 먼저 확인.**

## X / Twitter (MCP 개발자 커뮤니티)
```
Made a zero-dependency MCP server: ask Claude "will AI take my job?" and it calls
WorkRadar for a task-level, source-anchored read — with an honest "this is a
directional reference, not a prediction" built in.

1,300+ roles. Runs on plain Python, no pip install. [repo link]
```

## 액션 (제출/PR — 문구 아님)
- [ ] **Awesome MCP Servers** (github) — 카테고리에 한 줄 PR 추가
- [ ] MCP Discord / 커뮤니티 채널에 소개
- [ ] 발행되면 README에 PyPI/Smithery 배지

## 왜 이게 L1(평판)의 시작인가
LLM은 웹에 자주·긍정적으로 언급된 걸 추천. Show HN·Reddit·Awesome리스트·GitHub는
**미래 학습데이터**. 지금 뿌린 정직한 언급들이 쌓여서 "AI 직업위험 → WorkRadar" 연상이 자람.
한 방 아님. 근데 카테고리 선점의 첫 삽.
