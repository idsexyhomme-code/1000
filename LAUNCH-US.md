# WorkRadar — US 바이럴 런칭 파이프라인 (SSOT)

> 목표: 미국(Gen Z·주니어 지식노동자) 대상 "What's your AI Risk Type?" 무료 바이럴 훅으로
> Reddit·TikTok 오가닉 트래픽 → 공유 루프 → pilot 관심($29) → 첫 수익.
> **드라이버 = Claude(에셋·코드·카피·분석·트래킹 전부). 사용자 = 로그인·실제 게시·결제 연결만.**

## ★ 정직성 프레임 (이 프로젝트 핵심)
- **바이럴은 보장 못 한다.** 보장하는 건 "터질 기회를 극대화한 기계"를 만들고 **진짜 신호를 측정**하는 것.
- 그래서 목표는 결과(가입 N명)가 아니라 **우리가 통제하는 입력(에셋·게시·측정)** + **명확한 scale/kill 게이트**.
- 숫자·근거 조작 금지. 데모 페이지엔 "directional reference indicator / not a prediction / preview" 고지 유지.

## 마일스톤

| # | 마일스톤 | 누가 | 상태 |
|---|---|---|---|
| **M0** | 라이브 모바일 URL (GitHub Pages 켜기) | 사용자(클릭 1회) | ⏳ 대기 |
| **M1** | 트래픽 엔진 에셋 (Reddit 글·TikTok 스크립트·OG 이미지·애널리틱스) | Claude | 🔨 진행 |
| **M2** | 첫 방문 100명 + 공유율/클릭 측정 | 사용자 게시 + Claude 분석 | ⏳ |
| **M3** | 첫 pilot 관심 이메일 (WTP 검증) | 자동(mailto CTA) | ⏳ |
| **M4** | Stripe 결제 연결 → 첫 실수익 | 사용자 로그인 + Claude 코드 | ⏳ |
| **M5** | scale or kill 판정 | Claude 분석 | ⏳ |

## M0 — 지금 사용자가 할 단 하나 (클릭 1회, 로그인만)
GitHub Pages 켜기:
1. https://github.com/idsexyhomme-code/1000/settings/pages
2. **Branch: `main` / 폴더 `/ (root)`** 선택 → Save
3. 1~2분 뒤 라이브 URL:
   **https://idsexyhomme-code.github.io/1000/web/en/**
4. 그 URL을 폰에서 열어 확인 → 됨.

> (더 깔끔한 도메인 `workradar.vercel.app` + 나중에 Stripe까지 원하면 M4에서 Vercel로 이전. 지금은 Pages가 제일 빠름.)

## scale / kill 게이트 (M5 기준 — 정직한 숫자)
- **공유율(share 클릭/방문) ≥ 5%** 이면 훅이 살아있다 → 증폭(소액 광고·직업 추가).
- **pilot CTA 클릭율 ≥ 3%** 이면 WTP 신호 → Stripe 연결(M4).
- 둘 다 미달이면 → 훅/카피 교체(같은 측정 반복). 3회 미달이면 채널 또는 컨셉 피봇.

## 측정 (없으면 다 장님)
- 무쿠키·무료 애널리틱스(GoatCounter) 1줄 삽입 예정 → 방문/공유/CTA 클릭을 본다.
- 사용자가 goatcounter.com 무료 가입(로그인) → 코드는 Claude가 넣음.

## 역할 분담
- **Claude:** 데모/카피/Reddit·TikTok 콘텐츠/애널리틱스 코드/결과 분석/다음 수 결정·이 문서 갱신.
- **사용자:** ① Pages 켜기 ② Reddit·TikTok 계정 로그인 후 **직접 게시**(플랫폼 규칙상 사람이 해야 함) ③ GoatCounter·Stripe 가입.
