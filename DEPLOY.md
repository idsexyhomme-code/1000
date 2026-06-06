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

## 3. 서버 호스팅 (사용자 결정)
- 아무 리눅스 VM(또는 Fly.io/Render/Railway 등). 파이썬 3.10+만 있으면 됨.
- 서버는 기본 `127.0.0.1` 바인딩 → **reverse proxy(nginx/Caddy)로 TLS 종단 + 전달**:
  ```
  # Caddy 예시 (자동 HTTPS)
  api.example.com {
      reverse_proxy 127.0.0.1:8000
  }
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
- [ ] `WEBHOOK_TOKEN` 설정 + reverse proxy TLS
- [ ] 베이스라인 캘리브레이션(현재 손추정 → O*NET·워크넷 실데이터로 — 신뢰성 핵심, R7)
- [ ] 시드 직업 확대(현재 2개 → 주요 직군 N개)
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
