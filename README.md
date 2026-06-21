# 커리어 시그널 (WorkRadar) 📡

> AI 직무대체 실시간 알림 서비스 — **3-AI 자율 루프**로 빌드 중.
> 모바일에서 `git pull`로 진행상황을 실시간 확인하세요.

## 🤖 작업 주체
| AI | 역할 |
|---|---|
| **Claude** | 메인 빌더 (설계·코드) |
| **Gemini 3.1 Pro** | 카피라이팅 · UI/UX (디자인·전략가타입·푸시·액션플랜) |
| **Codex** | 적대적 리뷰 (허점·법규·게이밍 검증) |

## 📍 지금 어디까지?
👉 진행상황은 [`PROJECT.md`](PROJECT.md)의 **'진행 로그'** 섹션을 보세요. 매 이터레이션마다 자동 커밋됩니다.
**백엔드+제품+발송+하드닝 전부 실작동** — 크롤링→Gemini채점→압력지수→봇서버→배치(변동감지·액션플랜·푸시)→발송(재시도/throttle).

## 🚀 실행 / 배포
- 로컬: `GEMINI_API_KEY=... python3 src/server.py 8000` (봇서버) + `python3 src/batch.py --send` (배치)
- 결과화면 미리보기: `web/sample-report.html`
- 직업별 진짜 가려움 심층 아틀라스: `web/sample-pain-atlas.md`
- 직업별 micro-itch 체크리스트: `web/sample-pain-probes.md`
- 개인정보처리방침/이용약관 샘플: `web/sample-privacy.html`, `web/sample-terms.html`
- PII 배포 전 점검: `python3 src/legal_preflight.py`
- 런칭 모드별 점검: `python3 src/launch_preflight.py --mode lead|paid|pain-paid` (`pain-paid`는 `PAIN_RELEASE_JOB/PAIN_RELEASE_PAIN/PAIN_RELEASE_PREVIEW` 필요)
- pain 파일럿 이행서 샘플: `web/sample-fulfillment-video-editor-revision-chaos.md`
- pain 결제 직후 킥오프: `python3 src/fulfillment.py --job video-editor --pain revision-chaos --kickoff --sample`
- pain-paid 웹훅: 서명검증+금액일치 후 `fq_pay_*` 이행 큐와 `kickoff-ORDER_ID.md` 자동 생성
- pain-paid 운영 대조: `python3 src/fulfillment_queue.py reconcile-paid`로 paid 주문·큐·kickoff 누락 확인, `python3 src/fulfillment_queue.py repair-paid --all`로 누락 복구. `report/memo/weekly`에도 이행 경고가 자동 포함됨
- pain-paid 체크포인트: `python3 src/fulfillment_queue.py checkpoint ORDER_ID kickoff_sent|materials_received|draft_ready|final_delivered`
- pain 파일럿 카탈로그: `web/sample-fulfillment-catalog.md`
- 배포 절차(호스팅·cron·TLS·카카오 연결): 👉 [`DEPLOY.md`](DEPLOY.md)

## 🎯 한 줄 요약
직업별 **AI 압력지수**(무료 미끼·근거 투명) → **진짜 가려운 업무 + micro-itch 선택**(pain intent) → pain 파일럿(업무 산출물 1개) → 액션플랜(무료 방향) → **결과물 패키지**(이력서 재설계, 유료 정점) → 30일 내 지불주체 검증 → 한국 검증 후 글로벌.
> 측정은 미끼, **업무 고통을 줄이는 대응(결과물)이 상품.** 공포가 아니라 근거·통제감으로 — 가짜 숫자·가짜 사회증명 금지(정직성 불가침).

## 📐 핵심 설계 원칙
- 단일 0~100 숫자 ❌ → **태스크 단위 · 근거등급 · 신뢰구간 · 기상예보식 밴드** ⭕
- 모든 변동에 출처·영향업무·방향·신뢰도·평이한 사유 동반
- 한국 규제(AI기본법 2026.1 시행 / 개인정보법 §37-2) 대응 **일부 제품 가드레일 내장**(법무 전체 준수와 별개 — 배포 시 약관·방침·통신판매 신고는 사용자 영역)

---
*이 저장소는 3-AI 자율 루프가 약 30분 간격으로 갱신합니다.*
