# WorkRadar — 24h Mac 백엔드 구동 가이드 (셀프호스트, Supabase 없음)

> 구조: **정적 퀴즈(GitHub Pages)** → POST → **Mac의 Python 백엔드(stdlib, 의존성 0)** → 파일저장.
> Mac을 24h 켜두고, 터널로 인터넷에 노출해 Pages 퀴즈가 호출하게 한다.

## 1. 서버 띄우기 (수동 테스트)
```
cd "/Users/seohyeongmin/Desktop/실시간 ai 직업 대체 알림 서비스 앱"
python3 src/server.py 8000
```
확인: `curl localhost:8000/api/wr/health` → `{"ok": true, ...}`

## 2. 24시간 자동 유지 (launchd — 꺼져도 자동 재시작, 로그인 시 자동 실행)
`~/Library/LaunchAgents/com.workradar.backend.plist` 생성:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.workradar.backend</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/Users/seohyeongmin/Desktop/실시간 ai 직업 대체 알림 서비스 앱/src/server.py</string>
    <string>8000</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/seohyeongmin/Desktop/실시간 ai 직업 대체 알림 서비스 앱</string>
  <key>EnvironmentVariables</key><dict>
    <key>HOST</key><string>127.0.0.1</string>
    <key>INTEREST_SALT</key><string>__여기에_긴_랜덤문자열__</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/tmp/workradar.out.log</string>
  <key>StandardErrorPath</key><string>/tmp/workradar.err.log</string>
</dict></plist>
```
등록:
```
launchctl unload ~/Library/LaunchAgents/com.workradar.backend.plist 2>/dev/null
launchctl load  ~/Library/LaunchAgents/com.workradar.backend.plist
```
+ Mac 잠자기 방지(전원연결 시): 시스템설정 → 배터리 → "디스플레이 꺼져도 자동 잠자기 방지" 켜기. (또는 `caffeinate -s`)

## 3. 인터넷 노출 (터널) — **안정 URL이 핵심** (재시작해도 안 바뀌어야)

### 권장 A: ngrok 무료 고정 도메인 (제일 간단)
```
! brew install ngrok
! ngrok config add-authtoken <대시보드의_토큰>     # ngrok.com 무료가입 후
# 무료 고정 도메인 1개 발급(대시보드 → Domains) 후:
ngrok http 8000 --domain=<your-free-static>.ngrok-free.app
```
→ 공개 URL: `https://<your-free-static>.ngrok-free.app`

### 대안 B: Tailscale Funnel (무료·안정, 도메인 불필요)
```
! brew install tailscale && tailscale up
! tailscale funnel 8000
```
→ 공개 URL: `https://<machine>.<tailnet>.ts.net`

### 즉석 테스트용 C: Cloudflare quick tunnel (URL 매번 바뀜 — 24h용 아님)
```
! brew install cloudflared
cloudflared tunnel --url http://localhost:8000
```

## 4. 퀴즈를 백엔드에 연결
`web/en/index.html` 상단의:
```js
var API_BASE="";
```
→ 3번에서 받은 공개 URL로 교체 (끝 슬래시 없이), 예:
```js
var API_BASE="https://workradar.ngrok-free.app";
```
그 다음 commit + push → Pages 반영. 이제 퀴즈 결과가 Mac에 로깅되고, 이메일 구독이 들어옴.
(보안 강화: launchd plist에 `WR_ALLOW_ORIGIN=https://idsexyhomme-code.github.io` 추가하면 CORS를 그 오리진으로 좁힘.)

## 5. 동작 확인
```
curl https://<공개URL>/api/wr/health
curl -X POST https://<공개URL>/api/quiz -d '{"job":"junior-developer","rep":2,"feel":2,"inst":2}'
```

## 6. 주간 리포트 (구독 리텐션 엔진)
미리보기: `python3 src/workradar_weekly.py --sample video-editor`
전체 생성(구독자 → 발송대기열 data/wr_outbox.jsonl): `python3 src/workradar_weekly.py`
매주 자동 실행은 별도 launchd(StartCalendarInterval) 또는 cron으로. 실제 발송은 이메일 provider(Resend/SMTP) 연결 후. (다음 단계)

## 운영 지표 한눈에
```
curl localhost:8000/api/wr/health    # 퀴즈 완료수 · 구독자수 · 분기/직업 분포
```
