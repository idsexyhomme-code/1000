# WorkRadar MCP — 배포(발행) 체크리스트

패키징·메타데이터는 **다 준비됨** (`pyproject.toml`, `server.json`, `smithery.yaml`, `Dockerfile`, `LICENSE`).
아래는 **계정이 필요해서 당신이 직접** 하는 발행 단계 (내가 대신 못 하는 부분).

## ⚠️ 먼저 확인 (막히면 여기부터)
- [ ] **GitHub 레포 `idsexyhomme-code/1000`가 public** 이어야 함 — 레지스트리들이 GitHub로 소유권 검증/색인. private면 아무 데도 안 뜸.
- [ ] (선택·권장) MCP 서버를 **별도 레포 `workradar-mcp`**로 떼면 더 깔끔. 지금 서브폴더(`mcp-server/`)로도 PyPI 발행은 됨.
- [ ] **라이선스 MIT로 기본 설정함** — 바꾸려면 `LICENSE` 교체.

## 1. PyPI 발행 (→ `uvx workradar-mcp` / `pip install workradar-mcp` 가능해짐)
PyPI 계정 + API 토큰 필요 (pypi.org).
```bash
cd mcp-server
python3 -m pip install --upgrade build twine
python3 -m build                 # dist/*.whl, *.tar.gz 생성 (hatchling)
python3 -m twine upload dist/*   # PyPI 토큰 입력
```
> 빌드가 3.9에서 안 되면 3.11+ 파이썬으로. (hatchling은 3.8+ 지원하지만 환경따라)

## 2. 공식 MCP 레지스트리 (registry.modelcontextprotocol.io)
AI 클라이언트들이 참조하는 공식 목록. `server.json` 이미 준비됨.
```bash
# mcp-publisher CLI 설치 (Go 또는 릴리스 바이너리 — 최신법은 아래 문서 확인)
# https://github.com/modelcontextprotocol/registry 의 Publishing 가이드
mcp-publisher login github      # GitHub로 인증(소유권 = io.github.idsexyhomme-code/*)
mcp-publisher publish           # server.json 사용
```
> 이름 네임스페이스 `io.github.idsexyhomme-code/workradar`가 레포 오너와 일치해야 검증됨(맞춰둠).

## 3. Smithery (smithery.ai) — AI 도구 마켓, 발견성 큼
`smithery.yaml` + `Dockerfile` 준비됨.
- smithery.ai 로그인(GitHub) → "Add Server" → 레포 연결 → smithery.yaml 자동 인식.

## 4. 자동 색인 레지스트리 (제출만/자동)
public 레포 + 좋은 README면 대부분 자동 색인되거나 간단 제출:
- [ ] **mcp.so** — 제출 폼
- [ ] **glama.ai/mcp** — GitHub 자동 크롤
- [ ] **PulseMCP** — 제출/자동
- [ ] **Awesome MCP Servers** (github) — PR로 추가

## 5. 발행 후 (씨앗 심기 → 평판)
- [ ] README에 배지 (PyPI, Smithery)
- [ ] "There's an MCP that tells you your AI job risk" 식으로 **Show HN / Reddit r/mcp** 공유 (제품헌트 킷과 동일 원칙: 가치 먼저, 업보트 구걸 X)
- [ ] 이게 L1(AI가 추천하는 평판)의 시작점

---
정직하게: 레지스트리 등재 = *발견 가능*해지는 것이지 *즉시 다 씀*은 아님. MCP 생태계는 초기라 규모는 아직 작음. 근데 **"AI 직업위험 MCP"는 카테고리 선점 가능** — 지금 여기 있는 게 유리.
