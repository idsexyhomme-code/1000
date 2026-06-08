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
| `PAYMENT_WEBHOOK_SECRET` | PG 웹훅 HMAC-SHA256 서명검증 시크릿. **이게 없으면 `paid`(진짜 지불주체)로 절대 확정 안 함**(`/webhook/payment`→501) | 실결제 측정 시 ✅ |
| `PAYMENT_SIG_HEADER` | PG가 보내는 서명 헤더명(기본 `X-Signature`. 배포 시 실제 PG에 맞춤) | 선택 |
| `PAYMENT_EXPECTED_AMOUNT` | 결제 인정 금액(기본 99000). 서명검증돼도 이 금액과 다르면 paid로 안 셈(무료/타상품 이벤트 차단) | 선택 |

```bash
export GEMINI_API_KEY="..."          # 코드에 절대 박지 말 것
export WEBHOOK_TOKEN="$(openssl rand -hex 16)"
```

## 2. 로컬 엔드투엔드 (검증용)
```bash
# 서버
GEMINI_API_KEY=... WEBHOOK_TOKEN=secret python3 src/server.py 8000
# 다른 터미널 — 배치 1회(소량)
GEMINI_API_KEY=... python3 src/batch.py --max 2 --send
# 리포트 확인
curl "localhost:8000/report?job=video-editor" > /tmp/r.html && open /tmp/r.html
```

## 2.5 ★ 런칭 = 지불주체 스모크테스트 (가장 먼저 할 것)
> 검증 판정(POSITIONING.md): "더 만들기"가 아니라 **30일 내 지불주체 1명 증명**이 먼저.
> 카카오 연결(§5, 계정·승인 필요) 없이도 **웹 + 사전판매 오퍼만으로 즉시 런칭 가능**.

**1단계 — 리드 검증 런칭 (결제 없이, 가장 빠름):**
1. **개인정보 선행조건(필수·먼저):** 연락처(PII)를 받는 순간 개인정보처리방침 수립·공개가 **법적 의무**(PIPA). `/offer`의 인라인 동의문구만으론 부족 → **개인정보처리방침·문의/삭제 채널을 먼저 갖춘 뒤** 수집 시작. (방침 페이지는 사업자/연락처 정보 필요 = 사용자 작성. 미비 시 리드 수집 끄고 '관심만 표시'로 운영.)
2. **호스팅 1대** (§3) — `python3 src/server.py` + reverse proxy TLS + 도메인. `INTEREST_SALT` 설정(IP 남용탐지 해시용).
3. **근거 채우기(먼저):** `/offer`·리포트 CTA는 **직무에 결박된 근거(뉴스)가 있을 때만** 노출되고, 없으면 "준비 중"으로 게이팅됩니다(무근거 판매 금지). → **공유 전 `python3 src/batch.py --max 3`을 1회 이상 돌려 뉴스 근거를 수집**하세요. (근거 0이면 오퍼가 안 떠서 유입이 헛돕니다.)
4. **유입** — 랜딩(`/`)→리포트(`/report?job=`)→오퍼(`/offer?job=`) 연결됨. 카톡/커뮤니티에 리포트 링크 공유(바이럴).
5. **측정** (§2.6) — `python3 src/interest.py`. ※리드=관심 신호, **지불 의사 아님**.

**2단계 — 실제 결제 검증 (지불주체 진짜 증명, 벽 높음):**
- ✅ **결제 검증 구현됨(P2):** `/webhook/payment`(PG 서버→서버, HMAC-SHA256 서명검증) + `/payment/success`(클라이언트 리다이렉트 '접수 확인' 페이지, 저장 안 함) + `payments` 저장 + `/health`의 `paid_customers`. **`paid`는 `PAYMENT_WEBHOOK_SECRET` 서명검증 + 금액일치 통과 시에만** 집계(시크릿 없으면 501, success URL 조작으로 못 부풀림).
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

## 2.6 사전예약 리드 측정
```bash
python3 src/interest.py          # 총 리드·직무별·가격별·최근(연락처 마스킹)
python3 src/interest.py --csv    # CSV 내보내기 (연락처 평문 — 운영자 본인만, 외부공유 금지)
curl localhost:8000/health       # {"presale_leads": N, "paid_customers": M} 빠른 확인
```
- 데이터: `data/interest.jsonl`(연락처 PII → **.gitignore, 절대 커밋·외부공유 금지**). honeypot+중복제거+동의(PIPA)+IP는 솔트 HMAC(`INTEREST_SALT` 없으면 미저장) 내장. `--csv`는 마스킹 기본, 원본은 `--raw`(운영자 본인만).
- ⚠️ **라벨 정직성:** `presale_leads`는 무료 연락처 = **관심 신호**다. **지불 의사(WTP)가 아니다.**
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
- [ ] **(PII 게이트·먼저)** 개인정보처리방침·이용약관·삭제/문의 채널 공개 → 그 후에만 `/offer` 리드 수집 ON
- [ ] **(런칭 1단계)** 호스팅 + TLS + 도메인 + `INTEREST_SALT` → `/`,`/report`,`/offer` 접속 확인 (카카오 없이 가능)
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
- [ ] 개인정보처리방침·이용약관(개인정보보호법 §37-2, AI기본법 대응 — 가드레일은 코드에 내장됨)

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
