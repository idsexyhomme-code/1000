# 백엔드 배포 가이드 (라이브 EN 사이트 측정·구독·referral 살리기)

> 라이브 EN 사이트(GitHub Pages, 정적)는 측정/구독/referral을 백엔드 `/api/*`에 의존.
> 이 백엔드(src/server.py, 의존성 0)를 Render에 1-클릭 배포 → 그 URL을 사이트 `API_BASE`에 꽂으면 전부 살아남.
> ⚠️ **브라우저 단계라 사용자(당신)가 직접** — 아래 순서대로 5분.

## 1) Render 배포 (Blueprint)
1. https://render.com 가입(무료) → GitHub 연결
2. **New → Blueprint** → repo `idsexyhomme-code/1000` 선택 → Render가 `render.yaml` 자동 감지 → **Apply**
3. 빌드 없음(stdlib만) → 1~2분 후 라이브. URL 예: `https://career-signal.onrender.com`
   - `INTEREST_SALT`는 Render가 자동 생성(수신거부 토큰·IP HMAC용). `WR_ALLOW_ORIGIN`은 이미 GitHub Pages로 설정됨.
   - (선택) `GEMINI_API_KEY` 넣으면 라이브 카피/채점, 없으면 폴백.

## 2) 헬스 체크
```
curl https://<your-app>.onrender.com/api/wr/health   # → 200 + JSON
```

## 3) 라이브 사이트에 백엔드 연결 (한 줄 + 푸시)
`web/en/index.html`의 `var API_BASE="";` →
```js
var API_BASE="https://<your-app>.onrender.com";
```
커밋·푸시 → GitHub Pages 재빌드(1~2분) → **퀴즈 완료·이메일 구독·referral 실추적·페이지뷰가 전부 백엔드에 기록**됨.
> 이 한 줄은 배포 URL 확정 후 알려주시면 제가 바꿔서 커밋해 드릴게요.

## 4) 켜지는 것들 (API_BASE 연결 즉시)
- **측정**: 퀴즈 완료/방문 → `/api/wr/health`에서 집계 확인
- **구독**: 이메일이 실제 저장(현재는 mailto 폴백) + **기능적 수신거부**(`/api/unsubscribe?email=&t=토큰`, 주간메일 링크에 자동 포함)
- **referral**: "친구 3명 초대 → 5경로 언락" 실추적(honor 폴백 대체)

## ⚠️ 무료 플랜 정직 주의
- 무료 web service는 **비활성 시 슬립**(첫 요청 콜드스타트 수십초) + **재배포/슬립마다 디스크 초기화** → 구독자/펀널 로그 휘발.
- **검증 단계(트래픽 보기 전)엔 무료로 충분.** 실제 구독자 영구 보존하려면 → render.yaml의 `disk:` 블록 주석 해제 + `plan: starter` + `store DATA_DIR` 분리(현재 repo 상대경로).

## 5) (선택) 한국 카카오봇
같은 백엔드가 `/webhook/kakao`도 서빙 → 카카오 i오픈빌더 스킬 URL에 `?token=<WEBHOOK_TOKEN>` 박고 `WEBHOOK_TOKEN` env 설정. (별도 비즈채널 승인 필요 = 브라우저 단계)
