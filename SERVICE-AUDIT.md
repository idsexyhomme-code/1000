# 서비스 전체 감사 — 100 체크포인트 (분할 리뷰)

## ★★ 종합 보고 (6배치 완료, 2026-06-27) ★★
> 12도메인 100체크 이중렌즈 점검 완료. ⚠️Codex MCP 오프라인이라 Claude가 양렌즈 수행.
> **총평: 핵심 엔진(점수·보안·리텐션)은 견고. 심각결함 2건은 즉시 수정 완료. 미해결은 대부분 "백엔드/이메일 배포를 실제 띄울 때" 필요한 것들.**

### 도메인별 상태
| | A정직 | B법무 | C엔진 | D데이터 | E결과창 | F공유 | G리텐션 | H온보딩 | I수익화 | J보안 | K접근성 | L배포 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
|상태| ✅ | ⚠️ | ✅ | ✅ | ✅ | ⚠️ | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ |

### 🔧 즉시 수정 완료 (이번 감사, 미푸시 5커밋)
1. **B5 'AI-proof' 절대표현** → "hardest-to-automate" (표시광고법, src와 정합)
2. **F4 죽은 ngrok API_BASE**(HTTP404) → `""` (referral·측정 죽은URL 호출 제거)
3. **D4 AIOE 드리프트 가드** 테스트 추가(web↔src 동기 회귀잠금)

### 📋 미해결 ⚠️ — 분류 + 실행순서
**① 지금 즉시 (이미 한 작업 라이브화 — 최우선)**
- **L1: `git push origin main`** (미푸시 5커밋) → 위 AI-proof·API_BASE fix를 **실유저에 반영**. 안 하면 고친 게 라이브에 없음.

**② 즉시 가능한 quick-win (코드, 짧음)** — ✅ **완료(2026-06-27)**
- ~~F2: OG 이미지 6페이지 누락~~ → **해결: 6페이지(ranked·daily·game·reels·result×2)에 페이지별 og:title/desc/url + 공유 og.png 삽입. 7/7 페이지 og:image 커버. 구조무결성·JS파싱 검증.**

**③ 이메일 발송 게이트 (메일 보내기 전 필수 3종 묶음)**
- **B3** 개인정보처리방침/약관 페이지+링크 · **B3** 동의문에 수집항목·목적·거부권 명시 · **G7** 기능적 unsubscribe 엔드포인트(현재 링크가 퀴즈페이지로만 감).

**④ 백엔드 배포 게이트 (render.yaml 띄우면 해결)**
- ~~subscribe 과대표기~~ → ✅ **정직성 부분해결(2026-06-27)**: mailto 폴백 시 "You're in" 대신 "Almost there — send the email draft to confirm" 표시(거짓 성공 제거). *실제 캡처*는 여전히 백엔드 필요.
- **referral 언락**(백엔드 없이 영영 안 풀림) · **quiz/방문 측정**. → 백엔드 배포 후 API_BASE 실주소 설정 시 살아남.

**⑤ 비즈니스/전략 결정 (코드 아님, 사용자)**
- **I2 가격**: web EN "$29 pilot" vs src KO "₩99,000" 통일/의도 확인 · **L4 두 코드베이스 정체성**(KO 카톡봇 vs EN 라이브, 어느 쪽 메인).

**추천 순서:** ①푸시(지금) → ②OG 6페이지(다음 짧은틱) → ⑤정체성·가격 결정 → ④백엔드 배포 → ③이메일 3종 → 이메일 런치.

---


> 목적: 커리어 시그널/WorkRadar **서비스 전체**를 아주 디테일하게 분할 점검.
> 방식: 각 항목을 **이중 렌즈**로 — 🟦 Claude(빌더: 의도/일관성) + 🟥 적대 리뷰어(Codex식: 깨지는 경로/거짓신뢰/엣지). ⚠️Codex MCP 끊긴 세션에선 Claude가 양쪽 수행(과거 확립 방식); 재연결 시 도메인별로 Codex 재실행 가능.
> 상태: ⬜미점검 / 🔄진행 / ✅정상 / ⚠️개선필요 / 🟥결함.
> 그라운딩: src/ 26모듈, web/en 7페이지+jobs.json(1345), 99테스트, data/jobs(17).

## A. 정직성·반(反)가짜신뢰 [핵심 불가침]
- A1 ⬜ 표시 점수 어디서도 calibrated인 척 안 함(손추정 면책 노출) — src report·web result 양쪽
- A2 ⬜ AIOE 앵커: 앵커 직업만 배지, medium=proxy 표기, "상대노출≠확률·직접대입 안 함"
- A3 ⬜ 채용/임금 스텁: 데이터 없을 때 가짜숫자 0(정직 스텁 유지) — deepdive
- A4 ⬜ 액션플랜: 근거(driver) 없으면 guardrail_ok=False, 가짜 근거 합성 안 함 — actionplan
- A5 ⬜ 사회증명("상위 5%"·후기) 검증 안 된 것 노출 0
- A6 ⬜ 공유카드/OG: 점수·top% 표기가 본문과 일치, 과대표기 없음
- A7 ⬜ "preview/illustrative" 표기가 미검증 수치에 동반(web footer)
- A8 ⬜ 두 코드베이스(src KO·web EN) 간 점수/문구 정직성 기준 동일

## B. 법무·규제 (한국 실재)
- B1 ⬜ 명예훼손: "대체된다" 단정 없음 → "관측된 자동화 압력/which tasks"
- B2 ⬜ AI기본법: 모델카드/방법론 공개·오류정정 경로 존재
- B3 ⬜ PIPA §15: 이메일 수집 전 동의 체크박스+수집항목·거부권 고지
- B4 ⬜ PIPA §37-2: 개인 자동결정 사용 금지 명시·human review
- B5 ⬜ 표시광고법: "AI-proof/보장" 절대표현 없음("no guaranteed outcomes" 유지)
- B6 ⬜ 전자상거래법: 환불/청약철회권 문구(99k 패키지) 적법
- B7 ⬜ 특정 회사/학교/개인 겨냥 표현 0
- B8 ⬜ 가격·결제 표기: "접수/대기"와 "결제완료" 정직 구분(가짜 paid 없음)
- B9 ⬜ 쿠키/트래커(goatcounter 등) 고지 필요성 점검

## C. 점수 엔진 (scoring.py)
- C1 ⬜ 5요인 앵커 정의대로 가중·범위, round 정보손실 없음(float 유지)
- C2 ⬜ 이벤트 dedup(기술+벤더+태스크+주장) — 중복가산 방지
- C3 ⬜ 출처 티어링: 벤더단독 max +2, Tier3 누적 상한
- C4 ⬜ 신뢰구간(CI) 전파: 보수적 floor, 인위 축소 없음
- C5 ⬜ 감쇠/회귀: half-life 공개·고정, 규제이벤트 보존
- C6 ⬜ 일일 캡(up/down 버킷), EPSILON은 표시 프루닝만
- C7 ⬜ 태스크→직업 롤업 가중평균 정확
- C8 ⬜ 기상밴드 경계 연속(빈틈 없음) src·web 동일 기준
- C9 ⬜ web/en finalScore(exp/ai 보정) 합산·표시 분해 일관

## D. 캘리브레이션·데이터 무결성
- D1 ⬜ AIOE 앵커 percentile만 저장(raw z-score 미저장, 라이선스)
- D2 ⬜ job_soc_map confidence high/medium 정확, aioe_soc 빈티지 매핑
- D3 ⬜ calibrate.py 멱등·medium 경고·skip 로직
- D4 ⬜ web AIOE 객체(17) ↔ src 앵커 동기화(드리프트 0)
- D5 ⬜ web jobs.json(1345) 스키마 일관, base 분포 정직
- D6 ⬜ src data/jobs(17) 태스크 weight 합·CI 타당
- D7 ⬜ .gitignore: CSV/xlsx/PII 파생물 커밋 차단
- D8 ⬜ 17 src job_id ↔ web key 슬러그 매칭 정확

## E. 결과창 UX (web/en + src report)
- E1 ⬜ 게이지 SVG 각도·밴드색 정확, 접근성 aria
- E2 ⬜ 위협/기회 카드: 실제 top/low 업무 기반
- E3 ⬜ 신뢰배지 details: 출처·SOC·면책 완비
- E4 ⬜ "why this score" 분해 투명(블랙박스 아님)
- E5 ⬜ 태스크 바·색 임계 일관
- E6 ⬜ 액션플랜/패스: 분기별 상이·개인화
- E7 ⬜ CTA(deep consult·서비스·로드맵) 링크 유효
- E8 ⬜ 모바일 폭(≤460) 레이아웃 깨짐 없음
- E9 ⬜ src detail_html 5섹션 정직 스텁/실데이터 분기

## F. 공유·바이럴 루프
- F1 ⬜ navigator.share 페이로드·breakout 방어(</)
- F2 ⬜ OG/twitter 메타: 절대URL·이미지·canonical(전 페이지)
- F3 ⬜ og.png 실제 서빙(404 아님)·1200×630
- F4 ⬜ 추천(referral) 코드·unlock·진척바 로직
- F5 ⬜ downloadCard canvas: 텍스트 잘림·신뢰줄 정확
- F6 ⬜ 공유→랜딩→내직업 루프 폐쇄(보드 CTA)
- F7 ⬜ 공유 문구 정직(과장·낙인 없음)
- F8 ⬜ 친구 도착 시 ref 파라미터 처리

## G. 리텐션·알림
- G1 ⬜ notify 금칙어 가드·MAX_LEN·CTA 보존(트렁케이션)
- G2 ⬜ batch 변동감지(MATERIAL_DELTA·weather) 정확
- G3 ⬜ 쿨다운(3일)·날씨밴드 예외·중복 snap_ts 차단
- G4 ⬜ 캐시(strategist/actionplan) 갱신 게이팅
- G5 ⬜ outbox fan-out·set_notified 멱등
- G6 ⬜ sender throttle·retry·sent-marker
- G7 ⬜ weekly signal(workradar_weekly) 정직·구독해지
- G8 ⬜ 푸시 공포프레이밍 금지(§1.6)

## H. 온보딩·활성화
- H1 ⬜ kakao webhook: 토큰인증·rate limit·malformed 무크래시
- H2 ⬜ _match_job 구어체·모호회피(오매칭 0)
- H3 ⬜ 첫진입 온보딩·quick reply 10개 한계
- H4 ⬜ web 퀴즈 6단계 흐름·진행점·뒤로
- H5 ⬜ 요약 응답: 라이브 Gemini콜 없음(타임아웃 방지)
- H6 ⬜ 직업 미선택·없는직업 폴백 친절
- H7 ⬜ 재방문(등록유저) 상태 표시

## I. 수익화·오퍼
- I1 ⬜ 무료 티저 1 + 잠금 2(액션플랜) 정합
- I2 ⬜ $29 pilot / 99k 패키지 오퍼 일관(가격·결과물)
- I3 ⬜ ungrounded 플랜은 유료잠금 대신 "근거없음" 톤
- I4 ⬜ waitlist vs 실결제 정직 구분
- I5 ⬜ _safe_url 결제URL 검증(javascript: 차단)
- I6 ⬜ 결제 웹훅 서명검증(HMAC)·중복방지
- I7 ⬜ 환불/사람검토 정직 표기
- I8 ⬜ 2-티어(디지털 구독 + 패키지) 서사 정합

## J. 보안
- J1 ⬜ WEBHOOK_TOKEN 인증·미설정 시 동작
- J2 ⬜ IP rate limit 윈도우·한계
- J3 ⬜ XSS: _e 이스케이프·_safe_url(http/https only)
- J4 ⬜ 시크릿: 코드/메모리/커밋 0(스캔 통과)
- J5 ⬜ 구독 honeypot(subHp)·동의 게이트
- J6 ⬜ CORS: WR_ALLOW_ORIGIN·쿠키 미사용
- J7 ⬜ 결제 웹훅 비-hex 서명 거부
- J8 ⬜ 파일/정적 서빙 경로 traversal 방어
- J9 ⬜ Gemini 키 env-only·로그 노출 0

## K. 성능·접근성
- K1 ⬜ 핀치 확대 허용(WCAG 1.4.4) 전 페이지
- K2 ⬜ 렌더 바이트·gzip 합리(리포트 ~5KB gzip)
- K3 ⬜ 색 대비(WCAG AA) 텍스트/배경
- K4 ⬜ aria-label·role(게이지·버튼·이모지)
- K5 ⬜ 키보드 포커스·details 접근
- K6 ⬜ 폰트·이미지 로딩(외부 의존 0, 인라인)
- K7 ⬜ i18n: KO/EN 분리·인코딩
- K8 ⬜ JS 에러 시 graceful(폴백)

## L. 배포·운영·정합
- L1 ⬜ GitHub Pages 빌드·서빙 정상(라이브=최신)
- L2 ⬜ 루트 redirect·canonical 정확
- L3 ⬜ render.yaml/Procfile 백엔드 배포 가능(측정용)
- L4 ⬜ 두 코드베이스(src/web) 드리프트·정체성 정렬 계획
- L5 ⬜ 테스트 99 커버리지·핵심 회귀잠금
- L6 ⬜ sitemap.xml·robots 색인
- L7 ⬜ 모니터링/분석(goatcounter·quiz POST) 측정 가능
- L8 ⬜ 시드 데이터 vs 1345 직업 운영 일관
- L9 ⬜ 문서(PROJECT/README/DEPLOY) 최신·정확

---
## 리뷰 로그 (Batch별 findings)

### Batch 1 — 도메인 A(정직성) + B(법무) [2026-06-27, Codex MCP 오프라인→Claude 이중렌즈]
**정상(✅):** A1 면책 양쪽 노출(web footer "Preview/directional reference" + src 손추정) · A2 AIOE proxy/medium·"상대노출≠확률" 면책(Step2) · A4 액션플랜 guardrail_ok·무근거 미합성 · A7 "Preview: figures illustrate the method" footer · B1 "대체된다" 단정 회피("which tasks AI takes") · B7 특정개인/회사 겨냥 0 · B8 "Waitlist — not charged yet" 정직 구분 · I7/B5 "no guaranteed outcomes".

**🟥 결함→즉시수정(✅ fixed):**
- **B5/A8 'AI-proof' 절대표현** (index.html:242 서비스템플릿 "the AI-proof part of {job}"). 🟥적대렌즈: 표시광고법상 절대보장 표현, 게다가 src/는 이미 'AI 시대/상대적으로 덜 대체'로 완화했는데 **web/en만 안 됨=두 코드베이스 정직성 정합 깨짐**. → **"the hardest-to-automate part of {job}"로 수정 완료.**

**⚠️ 개선필요(다음 배치 조치, 미수정):**
- **B3 (High) 개인정보처리방침/약관 링크 부재** — web/en이 이메일을 수집(subscribe)하는데 방침·약관 링크가 **0**("terms"는 'on your terms' 관용구뿐). 동의문("I agree to receive weekly emails…")이 PIPA §15 요구(수집항목·목적·보유기간·거부권+불이익없음) 미충족. 🟦빌더: src/에는 /privacy·/terms 있으나 web/en(정적)엔 미연결. → **조치: web/en에 최소 privacy/terms 정적 페이지 + subscribe 근처 링크.**
- **A/B (Med) subscribe() 과대표기** — API_BASE 미설정(백엔드 미배포) 시 mailto 폴백 후 `done()`을 **무조건** 호출 → 메일 미발송·클라이언트 없음에도 "✓ You're in. First signal lands within a week" 표시. 🟥적대: (1)가입 미포착인데 성공 표기 (2)EN에 위클리 발송기제 미배포면 "within a week" 못 지킬 약속. → **조치: no-backend 경로 메시지 톤다운("check your email app to confirm") + 발송 배포 전엔 "within a week" 보류.**
- **B9 (Low) goatcounter 트래커** — 쿠키리스·PII無라 저위험. 단 방침 링크 부재와 합쳐 고지 권장(B3 해결 시 함께).

**도메인 상태:** A 대체로 ✅(정합 1건 fixed) · B ⚠️(B3 High 미해결, B5 fixed, 나머지 ✅).

### Batch 2 — 도메인 C(점수엔진) + D(데이터무결성) [2026-06-27]
**정상(✅) — 엔진 견고, 결함 0:** C1 내부 float 유지·표시만 round·요인 0..max 클램프(부호뒤집힘 방지) · C2 dedup(기술+벤더+태스크+방향 base_key) · C3 TIER_DELTA_CAP(벤더 max+2)+TIER3_JOB_CAP 게이트(PR펌핑 차단) · C4 _propagate_job_ci 보수적 하한(w_avg·0.75)+저신뢰 시 inflate+클램프4~25(과신 금지) · C5 decay 공개half-life(evidence90/employment365/regulation∞) · C6 daily cap up/down 버킷·부분클램프, EPSILON은 드라이버 표시만(누적엔 전 비-0 반영) · C7 직업지수=태스크 가중평균 · C8 기상밴드 src(0-26-51-76-101)↔web band()(≤25/≤50/≤75/else) 경계 일치 검증 · D5 web jobs.json 1345직업 스키마0결함·base분포 정직(min12~max90,median52,극단값0) · D6 src17 태스크weight합 전부1.0 · D7 .gitignore PII/CSV차단 · D8 src job_id↔web key 17/17.
**🟦 설계상 분리(결함 아님):** C9 web finalScore(task평균+경력/AI보정)는 src 뉴스기반 엔진과 **다른 시스템**(퀴즈 vs 신호) — 의도된 분리, web는 'why this score' 분해로 투명.
**⚠️→fix(✅):** D4 web AIOE객체(17)↔src앵커 현재 percentile 동기됐으나 **수동 하드코딩 복제=단일소스 없음→드리프트 위험**. 🟥적대: src 재캘리 시 web 안 따라감. → **드리프트 가드 테스트 추가**(web AIOE키·percentile == src앵커 회귀잠금, 100테스트).
**다음 배치:** E(결과창) + F(공유).

### Batch 3 — 도메인 E(결과창) + F(공유) [2026-06-27]
**정상(✅):** E1 게이지 SVG 밴드·aria · E2 위협/기회 실제top/low(Step3) · E3 신뢰배지 details 출처·SOC·면책(Step2) · E4 "why this score" 분해 투명 · E7 deep-consult CTA(upsight-blue.vercel.app)=**HTTP 200 생존** · E8 모바일퍼스트(≤460) · F1 share breakout(src `<\/` 가드, web _share는 런타임 JS문자열 저위험) · F3 og.png=**HTTP 200**(48KB,1200×630) · F6 루프폐쇄(src 보드CTA)·F7 공유문구 정직.
**🟥 결함→즉시수정(✅ fixed):**
- **F4/J/L (High) API_BASE가 죽은 ngrok 터널** — `API_BASE="https://unsavory-paralysis-jokingly.ngrok-free.dev"` = **HTTP 404**(ngrok-free 임시터널 소멸). 🟥적대: (1)**referral 언락 영구 미작동**(checkRefProgress→죽은URL→catch→"0/3"에서 영원, "친구3명 초대 언락" 못 지킬 약속) (2)quiz/hit 측정 죽음 (3)subscribe는 mailto degrade. → **API_BASE="" 수정**(코드가 `if(API_BASE)` 전부 가드 → 죽은URL 호출 0, graceful degrade). web script 파싱 OK.
**⚠️ 개선필요(미수정):**
- **F2 (Med) OG 이미지 6페이지 누락** — index.html만 og:image. daily/game/ranked/reels/result-video-editor/result-junior-developer는 og:image=0 → 그 URL 공유 시 미리보기 밋밋. 특히 result-*·ranked는 공유 표면. → 조치: 6페이지에 og:image 메타 추가(다음 패스).
- **F4 잔여 (Med) referral 언락 = 백엔드 필요** — API_BASE 비웠지만 언락 자체는 backend 없이 불가. 🟥적대: "invite 3 to unlock"이 영영 안 풀리면 약속 위반. → 조치: 백엔드 배포(render.yaml) 또는 언락 문구를 "coming soon/honor"로 정직화 = **사용자 결정**.
**다음 배치:** G(리텐션) + H(온보딩).

### Batch 4 — 도메인 G(리텐션) + H(온보딩) [2026-06-27]
**정상(✅):** G1/G8 _BANNED(대체/사라진다/실직/해고/퇴출) 금칙어+_guardrail_ok, 공포프레이밍 금지 · G2/G3 batch 변동감지(MATERIAL_DELTA·weather)+쿨다운3일·날씨밴드예외(기존) · G4 캐시 갱신 게이팅 · G5 outbox fan-out·set_notified · G6 sender flush retry·per-user throttle(과발송 시 queued 유지)·sent-marker · G7 weekly 매메일 면책+"directional reference, not prediction"+calibrated:false · H1 webhook 토큰인증(?token=)+rate limit+IP는 HMAC(평문 미저장) · H1 malformed 무크래시(테스트) · H2 _match_job 구어체/모호회피(기존fix,테스트) · H5 요약 라이브 Gemini콜 없음(기존fix,테스트) · H3 quick reply 10한계.
**⚠️ 개선필요(미수정, 이메일 배포 게이트):**
- **G7 (Med) 기능적 unsubscribe 엔드포인트 부재** — weekly 다이제스트의 "Manage/unsubscribe" 링크가 LANDING(퀴즈)으로만 감(실제 수신거부 처리 0), "Reply STOP"만 수동. 🟥적대: 실제 메일 발송 시작하면 CAN-SPAM/PIPA의 1-클릭 수신거부 의무 위반. 🟦빌더: 현재 weekly는 미배선(발송 안 함)이라 잠복. → **조치: 발송 배포 전 /unsubscribe?token= 엔드포인트 + store opt-out.** B3(방침링크)와 함께 "이메일 발송 전 필수 3종(방침·동의문·수신거부)"으로 묶음 = 사용자 배포 결정.
**도메인 상태:** G ✅(엔진 견고) · H ✅(보안·매칭 견고). 결함 0, ⚠️1(이메일 배포 전 조건).
**다음 배치:** I(수익화) + J(보안).

### Batch 5 — 도메인 I(수익화) + J(보안) [2026-06-27]
**정상(✅) — 보안 견고, 결함 0:** J1 WEBHOOK_TOKEN(?token= 일치) · J2 IP rate limit 윈도우 · J3 _safe_url(http/https only, javascript:/data: 차단)+_e 이스케이프 · **J3 web ?ref= 파라미터 `.replace(/[^a-zA-Z0-9]/g,'')` 영숫자화→fetch body로만(innerHTML 미반영)=반영XSS 안전** · J4 시크릿 코드/커밋 0(매배치 스캔) · J5 구독 honeypot(subHp)+동의 게이트 · J7 결제 비-hex 서명 예외없이 거부+hmac.compare_digest(상수시간) · J8 **정적 파일서빙 핸들러 없음=경로traversal 표면0** · J9 Gemini키 env-only(없으면 raise, 로그/저장 0) · I1 무료티저1+잠금2 · I3 ungrounded=유료잠금 대신 "근거없음" 톤 · I4 waitlist "not charged yet" vs 실결제 정직구분 · I5 결제URL _safe_url→`real = !="#"`(javascript: 실결제 오인 차단, Codex fix) · I6 결제웹훅 HMAC-SHA256 서명검증 · I7 "no guaranteed outcomes"+사람검토 정직.
**⚠️ 개선필요/플래그(미수정):**
- **I2 (Low) 오퍼 가격 두 코드베이스 불일치** — web EN "**$29 pilot**" vs src KO "**₩99,000**". 🟥적대: $29≈₩40k≠₩99k. pilot(초기 할인) vs 풀패키지 or 시장차이로 *의도*일 수 있으나, AI-proof·API_BASE처럼 두 코드베이스 드리프트 전력 있음. → **조치: 의도된 가격전략인지 사용자 확인**(코드 결함 아닌 비즈니스 결정).
- **J6 (Low) CORS `*`** — 쿠키/인증정보 미사용 공개 퀴즈 API라 정당화됨(주석 명시). 백엔드 배포 시 WR_ALLOW_ORIGIN으로 좁히기 권장.
**도메인 상태:** I ✅(정직·정합, ⚠️가격 플래그) · J ✅(보안 견고, 결함0).
**다음 배치:** K(접근성·성능) + L(배포·정합) — 마지막.

### Batch 6 — 도메인 K(접근성·성능) + L(배포·정합) [2026-06-27] ★마지막
**정상(✅):** K1 핀치확대 잔존0 전페이지(WCAG 1.4.4) · K2 렌더 합리(리포트~5KB gzip) · K4 게이지 role=img+aria · K6 외부의존 **1개만**(goatcounter gc.zgo.at, 쿠키리스·privacy-friendly), 나머지 인라인=의존0원칙 거의 충족 · L5 100테스트 · L6 sitemap.xml 라이브 HTTP200 · L9 문서 06-27까지 최신.
**⚠️ 개선필요:**
- **L1 (High·운영) 라이브 ≠ 최신** — 감사 fix **5커밋 미푸시**(b7e443f AI-proof·c625165 API_BASE 등 web/en/index.html 2건 포함) → **표시광고법 fix·죽은 ngrok fix가 아직 실유저 미반영**. 🟥적대: 고친 줄 알지만 라이브엔 그대로. → **조치: `git push origin main`(사용자) = 즉시 라이브화.**
- **L4/L8 (전략) 두 코드베이스 정체성** — src KO(17직업, 카톡봇+미니웹) vs web EN(1345직업, 정적 라이브). §0-A 로드맵에 "합치/우선=사용자 결정" 기록됨. 드리프트 전력(AI-proof·API_BASE·가격) → 단일 정체성 결정 필요.
- **K3 (Low) 색대비** — #71717a 디밍 푸터텍스트가 AA 경계(소형). 본문 아님, 허용범위.
**도메인 상태:** K ✅ · L ⚠️(L1 푸시 필요, L4 전략결정).
