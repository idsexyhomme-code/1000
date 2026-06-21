# 커리어 시그널 — 배포 가이드 (R6)

의존성 0(파이썬 stdlib만). 서버 1대 + cron이면 돌아갑니다.

## 0. 구성요소
| 프로세스 | 역할 | 실행 |
|---|---|---|
| **봇 서버** | 카카오 웹훅 수신·결과리포트 서빙 | `python3 src/server.py [PORT]` (상시) |
| **배치** | 뉴스 수집→채점→변동감지→푸시 큐잉·발송 | `python3 src/batch.py --send` (cron, 1일 1~수회) |

데이터: `data/jobs/*.json`(직무 정의, 커밋됨) + `data/`(런타임 생성물, gitignore).

## 1. 환경변수
| 변수 | 용도 | 필수 |
|---|---|---|
| `GEMINI_API_KEY` | Gemini(카피/채점). AI Studio 키 | ✅ (없으면 폴백만) |
| `WEBHOOK_TOKEN` | `/webhook/kakao?token=` 인증 토큰 | 배포 시 ✅ |
| `RATE_LIMIT` | IP당 분당 요청 수(기본 60) | 선택 |
| `HOST` | 바인딩 주소(기본 127.0.0.1) | 선택 |
| `REPORT_BASE_URL` | 카카오 봇 '리포트 보기' 링크용(예: `https://api.example.com`) | 배포 시 ✅ |
| `CHANNEL_URL` | 카카오 채널 추가 링크(공유 메시지용) | 배포 시 ✅ |
| `PAYMENT_URL` | 설정 시 `/offer`가 **실결제 버튼**으로 전환(예: 토스페이먼츠 결제링크). 미설정 시 사전신청 리드 수집 | 결제 테스트 시 ✅ |
| `PAIN_PAYMENT_URL` | 설정 시 `/pain-offer`가 **특정 업무 고통 파일럿 실결제 버튼**으로 전환. 미설정 시 파일럿 사전신청 | pain 파일럿 결제 시 ✅ |
| `PAYMENT_WEBHOOK_SECRET` | PG 웹훅 HMAC-SHA256 서명검증 시크릿. **이게 없으면 `paid`(진짜 지불주체)로 절대 확정 안 함**(`/webhook/payment`→501) | 실결제 측정 시 ✅ |
| `PAYMENT_SIG_HEADER` | PG가 보내는 서명 헤더명(기본 `X-Signature`. 배포 시 실제 PG에 맞춤) | 선택 |
| `PAYMENT_EXPECTED_AMOUNT` | 결제 인정 금액(기본 99000). 서명검증돼도 이 금액과 다르면 paid로 안 셈(무료/타상품 이벤트 차단) | 선택 |
| `PAIN_PAYMENT_EXPECTED_AMOUNT` | pain 파일럿 결제 인정 금액(기본 39000). `PAIN_PAYMENT_URL`이 켜진 경우 허용 금액에 추가 | 선택 |
| `PAYMENT_ALLOWED_AMOUNTS` | 여러 상품을 동시에 결제 검증할 때 명시 목록(예: `99000,39000`). 설정 시 위 expected amount보다 우선 | 선택 |
| `PAIN_RELEASE_JOB` | pain 파일럿 실결제로 열 직업군 id(예: `video-editor`). `--mode pain-paid` 통과 조건 | pain 파일럿 결제 시 ✅ |
| `PAIN_RELEASE_PAIN` | pain 파일럿 실결제로 열 pain_id(예: `revision-chaos`). 해당 직업군에 존재해야 함 | pain 파일럿 결제 시 ✅ |
| `PAIN_RELEASE_PREVIEW` | `productize-preview`로 만든 `/pain-offer` HTML preview 경로. 오퍼 문구·법무 링크·산출물 칸 검증에 사용 | pain 파일럿 결제 시 ✅ |
| `LEGAL_*` | `/privacy`, `/terms`의 사업자/문의/위탁/이행자료 정보. 예: `LEGAL_OPERATOR_NAME`, `LEGAL_OPERATOR_ADDRESS`, `LEGAL_CONTACT_EMAIL`, `LEGAL_PRIVACY_OFFICER`, `LEGAL_BUSINESS_NUMBER`, `LEGAL_TELECOMMERCE_NUMBER`, `LEGAL_PAYMENT_PROCESSOR`, `LEGAL_HOSTING_PROVIDER`, `LEGAL_NOTIFICATION_PROVIDER`, `LEGAL_FULFILLMENT_FIELDS` | 리드/결제 전 ✅ |

```bash
export GEMINI_API_KEY="..."          # 코드에 절대 박지 말 것
export WEBHOOK_TOKEN="$(openssl rand -hex 16)"
```

## 2. 로컬 엔드투엔드 (검증용)
```bash
# 서버
GEMINI_API_KEY=REDACTED_20260608
# 다른 터미널 — 배치 1회(소량)
GEMINI_API_KEY=REDACTED_20260608
# 리포트 확인
curl "localhost:8000/report?job=video-editor" > /tmp/r.html && open /tmp/r.html
```

## 2.5 ★ 런칭 = 지불주체 스모크테스트 (가장 먼저 할 것)
> 검증 판정(POSITIONING.md): "더 만들기"가 아니라 **30일 내 지불주체 1명 증명**이 먼저.
> 카카오 연결(§5, 계정·승인 필요) 없이도 **웹 + 사전판매 오퍼만으로 즉시 런칭 가능**.

**1단계 — 리드 검증 런칭 (결제 없이, 가장 빠름):**
1. **개인정보 선행조건(필수·먼저):** 연락처(PII)를 받는 순간 개인정보처리방침 수립·공개가 **법적 의무**(PIPA). 코드에는 `/privacy`·`/terms` 초안 페이지와 신청 폼 링크가 구현되어 있습니다. 배포 전 `LEGAL_*` 값을 채우고 `python3 src/legal_preflight.py`가 통과하는지 확인하세요. 미비 시 리드 수집을 끄고 '관심만 표시'로 운영.
2. **런칭 preflight:** 리드만 받을 때는 `python3 src/launch_preflight.py --mode lead`가 통과해야 합니다. 이 모드는 `LEGAL_*`, `REPORT_BASE_URL`, `WEBHOOK_TOKEN`, `INTEREST_SALT`, PII gitignore를 확인하고, `PAYMENT_URL`/`PAIN_PAYMENT_URL`이 켜져 있으면 실패합니다.
3. **호스팅 1대** (§3) — `python3 src/server.py` + reverse proxy TLS + 도메인. `INTEREST_SALT` 설정(IP 남용탐지 해시용).
4. **근거 채우기(먼저):** `/offer`·리포트 CTA는 **직무에 결박된 근거(뉴스)가 있을 때만** 노출되고, 없으면 "준비 중"으로 게이팅됩니다(무근거 판매 금지). → **공유 전 `python3 src/batch.py --max 3`을 1회 이상 돌려 뉴스 근거를 수집**하세요. (근거 0이면 오퍼가 안 떠서 유입이 헛돕니다.)
5. **유입** — 랜딩(`/`)→리포트(`/report?job=`)→오퍼(`/offer?job=`) 연결됨. 카톡/커뮤니티에 리포트 링크 공유(바이럴).
6. **측정** (§2.6) — `python3 src/interest.py`. ※리드=관심 신호, **지불 의사 아님**.
   - 어떤 직업/업무 고통/micro-itch를 먼저 제품화할지는 `python3 src/pain_intents.py`, `python3 src/fulfillment_queue.py weekly`, `python3 src/fulfillment_queue.py productize`로 별도 확인. ※pain intent=문제 검증 신호, **지불 아님**. 각 직업군은 최소 10개의 작은 가려움 가설을 갖고, `/pain` 온보딩은 그중 앞 8개를 보여줍니다. 실제 선택 데이터가 쌓이면 `/pain`은 상위 micro-itch를 "많이 선택됨"으로 기본 체크합니다. `/pain-offer`는 `mi=`가 없을 때 ① 해당 pain의 실제 선택값 ② 저장된 운영 메모 기반 제품화 우선순위 ③ 직업군 전체 선택값 순서로 기본 micro-itch를 좁혀 보여줍니다.

**1.5단계 — 특정 업무 고통 파일럿 오퍼 (더 좁은 검증):**
- `/pain?job=video-editor&pain=revision-chaos` → `/pain-offer?job=video-editor&pain=revision-chaos` 흐름으로, 범용 커리어 패키지가 아니라 **특정 반복 업무 결과물 1개**를 파일럿으로 신청받습니다.
- 실결제를 열려면 `PAIN_PAYMENT_URL`을 설정하고, 금액 검증은 `PAIN_PAYMENT_EXPECTED_AMOUNT=39000` 또는 `PAYMENT_ALLOWED_AMOUNTS=99000,39000`처럼 명시하세요. 설정 없이는 파일럿 사전신청만 받습니다.
- pain 파일럿 실결제 전에는 `PAIN_RELEASE_JOB`, `PAIN_RELEASE_PAIN`, `PAIN_RELEASE_PREVIEW`를 특정 후보로 고정하고 `python3 src/launch_preflight.py --mode pain-paid`가 통과해야 합니다. 이 preflight는 결제 URL/금액뿐 아니라 preview HTML, 법무 링크, 전용 산출물 칸, 이행서 샘플 생성까지 확인합니다.
- 파일럿 오퍼도 컨시어지 이행입니다. 샘플 자료/상황 설명을 받아 영업일 3일 내 약속한 결과물 1개를 직접 만들어 전달할 수 있을 때만 실결제를 여세요.
- 결제 오픈 전에는 반드시 심층 pain, micro-itch, 이행서, preview를 먼저 확인하세요: `python3 src/pain_deepdive.py > web/sample-pain-atlas.md`로 직업별 구매 트리거/첫 안도감/성공지표를 갱신하고, `python3 src/pain_probe.py --out web/sample-pain-probes.md`로 온보딩 체크리스트를 갱신한 뒤, `python3 src/fulfillment.py --job video-editor --pain revision-chaos --sample`로 실제 납품 문서를 만들어 봅니다. 운영 메모가 쌓이면 `python3 src/fulfillment_queue.py productize-preview`로 결제 전 preview HTML을 만든 뒤 그 파일을 `PAIN_RELEASE_PREVIEW`로 지정합니다. `/pain-offer?job=video-editor&pain=revision-chaos&mi=1&mi=2`처럼 `mi` 인덱스를 붙이면 오퍼 페이지가 선택한 작은 가려움까지 좁혀지고, `mi`가 없으면 pain-specific 선택값 또는 `data/fulfillment_reports/YYYY-MM-DD.md` 운영 메모의 제품화 병목이 기본 추천으로 쓰입니다. "선택 때문에 달라지는 결과물" 섹션에서 필수 칸·QA 기준을 보여줍니다. 이행서에는 `micro-itch 우선순위`와 `micro-itch 산출물 조정` 블록으로 작업 초점·추가 확인 질문·필수 표 칸·QA 기준이 생성됩니다. 전용 산출물 칸은 15개 직업군 대표 micro-itch에 모두 적용되고, 아직 세부 규칙이 없는 선택값은 공통 안전 표로 fallback합니다. 심층 아틀라스는 `web/sample-pain-atlas.md`, micro-itch는 `web/sample-pain-probes.md`, 이행 샘플은 `web/sample-fulfillment-video-editor-revision-chaos.md`와 `web/sample-fulfillment-junior-developer-unknown-codebase-context.md`, 15개 직업군 대표 pain 카탈로그는 `web/sample-fulfillment-catalog.md`에 있습니다.

**2단계 — 실제 결제 검증 (지불주체 진짜 증명, 벽 높음):**
- ✅ **결제 검증 구현됨(P2):** `/webhook/payment`(PG 서버→서버, HMAC-SHA256 서명검증) + `/payment/success`(클라이언트 리다이렉트 '접수 확인' 페이지, 저장 안 함) + `payments` 저장 + `/health`의 `paid_customers`. **`paid`는 `PAYMENT_WEBHOOK_SECRET` 서명검증 + 금액일치 통과 시에만** 집계(시크릿 없으면 501, success URL 조작으로 못 부풀림). pain 파일럿 금액으로 paid가 확정되고 `PAIN_RELEASE_JOB/PAIN_RELEASE_PAIN`이 고정되어 있으면, 웹훅이 `fulfillment_jobs.jsonl`에 `pain-paid` 작업을 만들고 `data/fulfillment_reports/kickoff-ORDER_ID.md`를 자동 저장한다.
  - **오픈 전 명령:** 범용 커리어 패키지 실결제는 `python3 src/launch_preflight.py --mode paid`, pain 파일럿 실결제는 `python3 src/launch_preflight.py --mode pain-paid`가 통과해야 합니다.
  - **PG 연결 절차:** ① PG 콘솔에서 웹훅 URL을 `https://api.example.com/webhook/payment`로 등록 ② 서명 시크릿을 `PAYMENT_WEBHOOK_SECRET`에, 서명 헤더명을 `PAYMENT_SIG_HEADER`에 설정 ③ `_classify_pay_status`의 terminal-paid 값(기본 `done/paid/completed`)을 실제 PG의 '결제완료' 이벤트 값에 맞춰 조정 ④ 결제 성공 리다이렉트를 `/payment/success?job=ID`로.
  - ⚠️ 서명 스킴이 단순 HMAC(raw body)이 아닌 PG(예: 토스의 paymentKey confirm API 방식)면, 해당 PG에 맞춰 `_payment_sig_ok`/검증 로직을 교체해야 함.
- ⚠️ **국내 PG 현실:** 토스페이먼츠 등은 **사업자등록 + 홈페이지/상품·환불·해지 고지 + 카드사 심사(최대 ~14일)** 필요. 즉시 발급 아님. **Stripe는 한국 사업자 미지원**(기본 경로에서 제외).

**통과/실패 기준:** 30일 내 실제 결제(또는 강한 리드→결제 전환)가 안 나오면 B2C 유료는 접고 B2B/정부 경로로(POSITIONING.md §5.5). 코드 추가는 그 전까지 동결.

**★ 결제 후 이행(컨시어지 MVP — 자동화 아님, 사용자 직접):**
> 오퍼 상품 = **'AI 시대 커리어 재설계 패키지'(99,000원 1회성)**. 이건 **사람이 직접 이력서를 재설계해 전달하는 서비스**다. 결제 버튼을 여는 순간, **당신이 5영업일 내 결과물을 만들어 전달할 의무**가 생긴다. 결제만 받고 이행 못 하면 환불·분쟁·신뢰붕괴.
- **전달 산출물(오퍼에 약속됨):** ① 직무 AI 압력 진단 리포트 ② 사람 고유 역량 중심 이력서 재배치 가이드 ③ 직접 다듬은 이력서 요약·성과 불릿 초안 ④ 1~3년 커리어 디펜스 플랜.
- **이행 절차를 결제 오픈 전에 고정(Codex — '결제 받고 이행 못 함' 차단):**
  1. **결제자 식별·연락 수단 확보:** PG가 **이름·이메일(또는 전화)·order_id**를 반드시 수집하도록 상품/결제폼 구성. 이게 없으면 결제자에게 연락·전달 불가.
  2. **자료 수집 흐름:** 결제 후 이력서·포트폴리오 제출 경로(전용 메일 또는 폼) + 서면 인터뷰 질문 발송. **이력서/포트폴리오는 민감 자료** → 수집·보관·파기 절차와 동의 필요(아래 PII).
  3. **주 5건 하드 캡:** 문구만으론 부족 — **PG 재고 5건/주 설정 또는 수동 접수 마감**으로 실제 제한. 한계 초과면 결제 비활성화하고 사전신청만.
- **결제 후 수집 PII(연락처보다 넓음):** 이력서·포트폴리오·인터뷰 답변까지 받는다 → 개인정보처리방침에 **이 자료들의 수집항목·목적·보유기간·파기·위탁(PG 등)·정보주체 권리·보호책임자**를 포함하고 **결제 전 별도 동의**. (연락처만 다룬 리드 동의문으론 부족.)
- **결제 전 필수 고지(전자상거래법) — 위치 반복:** 상품설명·가격·환불/청약철회 조건·제공시점을 ① 오퍼 페이지 ② **결제 버튼 근처** ③ **PG 상품정보/결제 직전 화면** ④ **결제 후 계약내용 통지**에 반복 명시. 청약철회 7일·계약불일치 시 3개월(인지 후 30일)·환급 3영업일 기준 명시.

## 2.6 사전예약 리드 · 가려움 수요 측정
```bash
python3 src/interest.py          # 총 리드·직무별·가격별·최근(연락처 마스킹)
python3 src/interest.py --csv    # CSV 내보내기 (연락처 마스킹)
python3 src/interest.py --csv --raw # CSV 원본(연락처 평문 — 운영자 본인만, 외부공유 금지)

python3 src/pain_intents.py          # 어떤 직업/업무 고통/micro-itch를 먼저 제품화할지 우선순위
python3 src/pain_intents.py --csv    # pain intent CSV(연락처 마스킹, micro_itches 포함)
python3 src/pain_intents.py --csv --raw # pain intent CSV 원본(운영자 본인만)
python3 src/fulfillment.py --job video-editor --pain revision-chaos --sample # pain 파일럿 이행서 샘플
python3 src/fulfillment.py --job video-editor --pain revision-chaos --kickoff --sample # 결제 직후 자료 요청 + D0-D3 체크리스트
python3 src/pain_probe.py --out web/sample-pain-probes.md # 직업별 micro-itch 온보딩 질문 갱신
python3 src/fulfillment.py --from-intent latest # 최근 pain intent로 실제 이행서 생성(연락처 마스킹)
python3 src/fulfillment.py --from-intent latest --job marketer # 특정 직무의 최근 신청만
python3 src/fulfillment_queue.py import # pain intent를 이행 작업 큐로 가져오기
python3 src/fulfillment_queue.py list   # queued/working/delivered + due/overdue 요약
python3 src/fulfillment_queue.py report # 병목 + 다음 운영 액션 + paid pain 이행 경고
python3 src/fulfillment_queue.py memo   # data/fulfillment_reports/YYYY-MM-DD.md 운영 메모 저장(paid 경고 포함)
python3 src/fulfillment_queue.py weekly # 주간 병목 변화 + 제품화 우선순위 + paid 이행 경고
python3 src/fulfillment_queue.py productize # 주간 병목 1~3위 기준 좁은 오퍼 카피 초안 저장
python3 src/fulfillment_queue.py productize-preview # 주간 제품화 후보의 /pain-offer HTML preview 저장
python3 src/fulfillment_queue.py reconcile-paid # paid pain 주문과 큐/kickoff 누락 대조
python3 src/fulfillment_queue.py repair-paid --all # 이슈 paid pain 주문의 큐/kickoff 멱등 복구
python3 src/fulfillment_queue.py checkpoint ORDER_ID kickoff_sent --note "자료 요청 발송"
python3 src/fulfillment_queue.py checkpoint ORDER_ID materials_received --note "원본 자료 수신"
python3 src/fulfillment_queue.py checkpoint ORDER_ID draft_ready --note "초안 검수 대기"
python3 src/fulfillment_queue.py next   # due_at이 가장 빠른 queued 작업 확인
python3 src/fulfillment_queue.py render fq_xxxxxxxxxxxx # 작업 id로 이행서 출력
python3 src/fulfillment_queue.py status fq_xxxxxxxxxxxx working --note "자료 확인 중"
python3 src/legal_preflight.py                 # 방침/약관 [필수 입력] 잔여 차단
python3 src/launch_preflight.py --mode lead    # 리드 수집 런칭 전 통합 점검
python3 src/launch_preflight.py --mode paid    # 범용 패키지 실결제 전 통합 점검
python3 src/launch_preflight.py --mode pain-paid # pain 파일럿 실결제 전 통합 점검

curl localhost:8000/health       # {"presale_leads": N, "pain_intents": P, "paid_customers": M} 빠른 확인
```
- 데이터: `data/interest.jsonl`(연락처 PII → **.gitignore, 절대 커밋·외부공유 금지**). honeypot+중복제거+동의(PIPA)+IP는 솔트 HMAC(`INTEREST_SALT` 없으면 미저장) 내장. `--csv`는 마스킹 기본, 원본은 `--raw`(운영자 본인만).
- ⚠️ **라벨 정직성:** `presale_leads`는 무료 연락처 = **관심 신호**다. **지불 의사(WTP)가 아니다.**
- 데이터: `data/pain_intent.jsonl`(연락처+상황 PII → **.gitignore, 절대 커밋·외부공유 금지**). `/pain` 페이지에서 수집한 "어떤 업무 고통과 작은 가려움을 줄이고 싶은가" 신호다. `pain_intents`는 제품화 우선순위용이며 **지불/리드가 아니다**.
- 이행: `python3 src/fulfillment.py --from-intent latest`는 `data/pain_intent.jsonl`의 최근 신청을 읽어 컨시어지 납품 골격으로 바꾼다. `--kickoff`를 붙이면 결제 직후 보낼 고객 자료 요청 메시지와 D0-D3 운영 체크리스트만 따로 생성한다. 출력에도 상황 설명이 포함될 수 있으므로 외부공유·커밋 금지. 연락처는 마스킹된다.
- 이행 큐: `data/fulfillment_jobs.jsonl`(연락처+상황 PII → **.gitignore, 절대 커밋·외부공유 금지**). `fulfillment_queue.py import`가 pain intent를 `queued` 작업으로 승격하고, pain-paid 웹훅은 `order_id` 기반 `fq_pay_*` 작업을 자동 생성한다. 두 경로 모두 3영업일 기준 `due_at`과 선택된 micro-itch를 붙인다. `list/next`는 납기와 overdue, 첫 micro-itch를 보여주고, `report`는 status/job/pain/micro-itch별 병목, 병목별 산출물 위치·필수 칸·첫 확인 질문, 다음 처리 작업, paid pain 이행 경고를 요약한다. `memo`는 같은 내용을 `data/fulfillment_reports/YYYY-MM-DD.md` 운영 메모로 저장하고, `weekly`는 저장된 메모들의 open/overdue 변화, 누적 pain/micro-itch 병목, 다음 주 제품화 우선순위 3개, paid pain 누락 경고를 요약한다. `productize`는 우선순위 1~3위 micro-itch를 `data/fulfillment_reports/productization-YYYY-MM-DD.md` 좁은 랜딩/오퍼 카피 초안으로 저장한다. `productize-preview`는 같은 후보를 실제 `/pain-offer` 렌더러로 만든 HTML과 `index.md`를 `data/fulfillment_reports/productization-preview-YYYY-MM-DD/`에 저장한다. `reconcile-paid`는 `payments.jsonl`의 paid pain 주문과 큐 작업, kickoff 파일 누락·overdue·체크포인트를 한 화면에 대조하고, `repair-paid`는 이슈 주문의 큐/kickoff를 payment record 기준으로 멱등 복구한다. `checkpoint`는 `kickoff_sent` → `materials_received` → `draft_ready` → `final_delivered` 순서로 주문별 세부 이행 진행률을 남긴다. `final_delivered`는 큐 상태도 `delivered`로 바꾼다. 킥오프 파일 `data/fulfillment_reports/kickoff-*.md`는 고객 자료 요청 메시지와 D0-D3 체크리스트다. 이 메모와 초안/preview/kickoff는 신청 상황 요약을 포함할 수 있어 **.gitignore, 외부공유 금지**다. `status` 명령으로 `working/delivered/blocked/canceled` 상태를 남긴다.
- **`paid_customers`(진짜 WTP)** = 서명검증된 `/webhook/payment`로 `paid` 확정된 주문 수(reported/실패/환불 제외, 금액 일치까지 통과). 데이터: `data/payments.jsonl`(**.gitignore**). `/payment/success` 리다이렉트는 조작 가능해 **집계에서 제외**(저장 안 함). PG 대시보드와 수동 대조 권장.

## 3. 서버 호스팅 (사용자 결정)
- 아무 리눅스 VM(또는 Fly.io/Render/Railway 등). 파이썬 3.10+만 있으면 됨.
- 서버는 기본 `127.0.0.1` 바인딩 → **reverse proxy(nginx/Caddy)로 TLS 종단 + 전달**:
  ```
  # Caddy 예시 (자동 HTTPS)
  api.example.com {
      handle /static/* {        # 정적 OG 이미지 등 (앱 대신 프록시가 서빙)
          root * /srv/career-signal/web
          file_server
      }
      reverse_proxy 127.0.0.1:8000
  }
  # → web/static/og.png (1200x630) 배치 + REPORT_BASE_URL 설정 시 카톡/SNS 공유 프리뷰 이미지 자동 노출.
  ```
- 프로세스 관리: `systemd` 유닛 또는 `pm2`/`supervisor`로 server.py 상시 구동.

## 4. 배치 cron
```cron
# 매일 09:00, 13:00, 19:00 수집·채점·발송 (하루 3회 예시)
0 9,13,19 * * *  cd /srv/career-signal && GEMINI_API_KEY=... /usr/bin/python3 src/batch.py --send >> /var/log/cs-batch.log 2>&1
```
- 변동(|Δ|≥2 or 날씨변화) 직무 구독자에게만 푸시 큐잉 → `sender.flush`로 발송(재시도/throttle 내장).

## 5. 카카오 연결 (사용자 필요 — 비즈채널 계정)
1. **카카오 비즈니스 채널** 개설 + **발신프로필** 등록.
2. **알림톡 템플릿** 사전 승인(알림톡은 승인된 템플릿만 발송 가능. 친구톡은 자유롭지만 광고성 규제).
3. **카카오 i 오픈빌더** 스킬 서버 URL을 `https://api.example.com/webhook/kakao?token=<WEBHOOK_TOKEN>` 로 설정.
4. **`src/sender.py`의 `KakaoSender.send()` 구현** — 현재 `NotImplementedError` 스텁. 비즈메시지 API(알림톡/친구톡) 호출로 채우고, `batch._flush_outbox`에서 `sender.flush(sender=KakaoSender())`로 교체.

## 6. 비용 (확인 완료)
- Gemini: AI Studio **후불(pay-as-you-go)**. 빌드/소규모는 월 푼돈. 모델 분리(고가치만 3.1 Pro, 채점은 flash 강등) + `/report` 캐시로 프로덕션 비용 최적화됨.
- **Google Cloud Billing 예산 알림** 권장(후불은 자동 상한 없음). 유저 폭증 시 비용은 호출 수에 비례.

## 7. 출시 전 체크
- [ ] **(PII 게이트·먼저)** `/privacy`·`/terms` 접속 확인 + `LEGAL_*` 채움 + `python3 src/legal_preflight.py` 통과 + 삭제/문의 채널 공개 → 그 후에만 `/offer` 리드 수집 ON
- [ ] **(런칭 preflight)** 리드 모드는 `python3 src/launch_preflight.py --mode lead`, 범용 결제는 `--mode paid`, pain 결제는 `--mode pain-paid` 통과 후 공개
- [ ] **(런칭 1단계)** 호스팅 + TLS + 도메인 + `INTEREST_SALT` → `/`,`/report`,`/offer` 접속 확인 (카카오 없이 가능)
- [ ] **(가려움 검증)** `/pain?job=video-editor&pain=revision-chaos` 같은 pain intake 링크 접속 확인 → micro-itch 체크박스 선택/저장 확인 → `python3 src/pain_intents.py`로 어떤 업무 고통과 작은 가려움을 먼저 제품화할지 확인
- [ ] **(좁은 파일럿)** `/pain-offer?job=video-editor&pain=revision-chaos` 접속 확인 → 실결제 전에는 `PAIN_PAYMENT_URL` 미설정 상태로 사전신청만 운영
- [ ] **(파일럿 이행 준비)** `python3 src/fulfillment.py --job video-editor --pain revision-chaos --sample`로 실제 납품 골격 확인 → 3영업일 내 만들 수 있을 때만 실결제 오픈
- [ ] **(pain 실결제 후보 고정)** `python3 src/fulfillment_queue.py productize-preview`로 생성한 HTML을 검토 → `PAIN_RELEASE_JOB`, `PAIN_RELEASE_PAIN`, `PAIN_RELEASE_PREVIEW` 지정 → `python3 src/launch_preflight.py --mode pain-paid` 통과 전까지 `PAIN_PAYMENT_URL` 공개 금지
- [ ] **(결제 직후 킥오프)** `/webhook/payment` paid 응답의 `fulfillment_id` 확인 → `python3 src/fulfillment_queue.py reconcile-paid`로 paid pain 주문·`fq_pay_*` 작업·`kickoff-ORDER_ID.md` 누락 대조 → 이슈가 있으면 `python3 src/fulfillment_queue.py repair-paid --all`로 큐/kickoff 복구 → 자동 생성된 kickoff의 자료 요청 메시지를 고객에게 발송하고 `python3 src/fulfillment_queue.py checkpoint ORDER_ID kickoff_sent --note "자료 요청 발송"` 기록. 수동 백업은 `python3 src/fulfillment.py --job "$PAIN_RELEASE_JOB" --pain "$PAIN_RELEASE_PAIN" --kickoff --out data/fulfillment_reports/kickoff-ORDER_ID.md`
- [ ] **(신청 후 운영)** pain intent가 들어오면 `python3 src/fulfillment.py --from-intent latest`로 해당 신청의 상황을 반영한 이행서 생성 → 결과물 제작·검토·전달
- [ ] **(작업 큐 운영)** `python3 src/fulfillment_queue.py import && python3 src/fulfillment_queue.py report`로 누락 없이 큐 등록·overdue·병목 확인 → `status <id> working/delivered`로 처리상태 기록
- [ ] **(근거)** 공유 전 `python3 src/batch.py --max 3` 1회↑ 실행 → 오퍼/CTA가 "준비 중" 아닌 실제 노출되는지 확인
- [ ] **(이행 준비·결제 오픈 전 필수)** 결제가 들어오면 5영업일 내 **이력서 재설계 결과물 4종**(§2.5)을 직접 전달할 준비 — 못 지킬 처리량이면 결제 오픈 미루고 사전신청만
- [ ] **(런칭 2단계)** 사업자등록 + PG 심사(토스 ~14일) → `PAYMENT_URL`+`PAYMENT_WEBHOOK_SECRET`(+`PAYMENT_EXPECTED_AMOUNT`) 설정 → PG 웹훅을 `/webhook/payment`에 등록(서명검증 구현됨 ✅) + PG 상품정보에 환불·청약철회·제공시점 고지 → 실결제 `paid_customers` 측정
- [ ] **(법무·결제 전)** **통신판매업 신고**(또는 면제 판단) + 사이트 하단/초기화면에 **상호·대표자·주소·전화·이메일·사업자등록번호·통신판매업 신고번호·약관·개인정보처리방침** 표시 + 구매안전(에스크로) 확인증(PG가 제공)
- [ ] **(PII 확장)** 개인정보처리방침에 **이력서·포트폴리오·인터뷰 자료**의 수집항목·목적·보유·파기·위탁(PG)·권리·보호책임자 포함 + 결제 전 별도 동의 흐름
- [ ] `WEBHOOK_TOKEN` 설정 + reverse proxy TLS (※ `?token=`는 프록시 로그에 남을 수 있음 → 로그 접근제한·회전)
- [ ] **(보안 운영)** 시크릿 env 파일 `chmod 600`, `umask 077`, `data/`는 웹루트 밖, CSV/백업은 `.gitignore`(추가됨) — PII 평문 유출 방지
- [ ] 베이스라인 캘리브레이션(현재 손추정 → O*NET·워크넷 실데이터로 — 신뢰성 핵심, R7)
- [x] 시드 직업 확대 (현재 15개 직군) · 추가 확장 가능
- [ ] `KakaoSender` 실구현 + 템플릿 승인
- [x] 개인정보처리방침·이용약관 초안 라우트(`/privacy`, `/terms`) 및 폼 링크 구현
- [ ] 개인정보처리방침·이용약관 최종화(사업자 정보, 실제 위탁사, 삭제/문의 채널, 법률 검토)

## 8. CI (선택 — 사용자 수동 설정 필요)
테스트는 `python3 tests/test_core.py`로 언제든 실행 가능. GitHub Actions로 푸시마다 자동 실행하려면
아래 파일을 추가하세요. **단, 워크플로 파일 푸시는 PAT에 `workflow` 스코프가 필요**합니다
(현재 토큰은 `repo`만 보유 → 자동 푸시 불가). 둘 중 하나:
- GitHub 웹에서 `.github/workflows/ci.yml` 직접 생성(아래 내용 붙여넣기), 또는
- `github.com/settings/tokens`에서 토큰에 `workflow` 스코프 추가 후 푸시.

```yaml
# .github/workflows/ci.yml
name: tests
on:
  push:
    branches: [main]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python3 tests/test_core.py   # stdlib·오프라인, 시크릿 불필요
```
