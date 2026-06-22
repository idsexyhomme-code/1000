# 백엔드 클라우드 배포 가이드 (Mac+ngrok 탈피)

> 목표: 백엔드를 내 Mac/ngrok에 묶지 않고 항상 떠있게.
> ⚠️ **핵심 함정:** 우리 백엔드는 데이터를 **파일**(`data/*.jsonl` — 펀널·점수·추천·구독)에 저장해.
> 무료 컨테이너는 재시작마다 파일이 **싹 지워져.** 그래서 "그냥 무료 배포"는 데이터가 날아가. 아래는 그걸 감안한 정직한 옵션.

## 옵션 A — 제일 싸고 빠름: Mac 유지 + 안정화 (오늘 추천)
데이터가 Mac 로컬에 남아 durable. 약점(ngrok URL 변경·Mac 꺼짐)만 잡으면 됨.
1. **ngrok 무료 고정 도메인** (대시보드 → Domains → 무료 1개) → 재시작해도 주소 안 바뀜
   `~/bin/ngrok http 8000 --url=https://<고정>.ngrok-free.app`
2. **Mac 안 자게**: `caffeinate -dis` (창 열어둠) 또는 시스템설정 잠자기 끔
3. 그 고정 URL을 Claude가 `API_BASE`에 영구로 박음
→ 비용 0, 데이터 안전. **트래픽 검증 단계엔 이게 정답.**

## 옵션 B — 완전 클라우드 (Mac 불필요): Render
**🆕 원클릭:** repo에 `render.yaml` Blueprint가 있음 → render.com → New → **Blueprint** → repo 선택하면
아래 1~4단계가 자동 적용됨(start command·health check·env 자리 포함). 디스크만 수동(아래 5번).
**단, 데이터 보존하려면 Persistent Disk(유료 ~월 $1~)가 필수.** 없으면 재시작 때 펀널·점수 리셋.
1. render.com → New → **Web Service** → repo `idsexyhomme-code/1000` 연결
2. Runtime: **Python 3** / Build Command: (비움 — stdlib라 설치 없음)
3. **Start Command:** `HOST=0.0.0.0 python3 src/server.py $PORT`  (server.py가 HOST env + argv 포트 지원함)
4. **Environment** 추가:
   - `INTEREST_SALT` = (긴 랜덤)
   - `WR_ALLOW_ORIGIN` = `https://idsexyhomme-code.github.io`
5. **Disks** → Persistent Disk 추가, **Mount Path** = 프로젝트의 `data/` 경로 (예: `/opt/render/project/src/data`) ← 이걸 빼면 데이터 휘발
6. 배포 후 나온 `https://<app>.onrender.com` 을 `API_BASE`에 박고 push → **Mac·ngrok 끔**

## 옵션 C — Fly.io (무료 볼륨 있음)
1. 간단 `Dockerfile`: `FROM python:3.12-slim` / `COPY . /app` / `WORKDIR /app` / `CMD HOST=0.0.0.0 python3 src/server.py 8080`
2. `fly launch` → `fly volumes create data` → `fly.toml`에 `[mounts] source="data" destination="/app/data"`
3. env(INTEREST_SALT, WR_ALLOW_ORIGIN) 설정 → `fly deploy`
4. `https://<app>.fly.dev` 을 API_BASE에 박음

## 결정 가이드 (정직)
- **지금(검증 전):** 옵션 A. 돈 0, 5분. 데이터 Mac에 안전.
- **steady 트래픽 생기면:** 옵션 B(Render+디스크 ~월 $1) 또는 C(Fly 무료볼륨)로 이전 → Mac 졸업.
- **"존나 사기" 금지:** 무료/월 몇천 원으로 충분. 스케일은 유저 늘 때.

## 이전 시 잊지 말 것
- `API_BASE`(web/en/*.html) → 새 클라우드 URL로 교체 후 push
- 클라우드는 ngrok 인터스티셜 없으니 `ngrok-skip-browser-warning` 헤더는 둬도 무해(무시됨)
- 0.0.0.0 바인딩 필수(HOST env). 리버스프록시가 TLS 처리.
