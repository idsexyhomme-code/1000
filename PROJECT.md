# 커리어 시그널 (WorkRadar) — 프로젝트 캐노니컬 문서

> AI 직무대체 실시간 알림 서비스. 3-AI 자율 루프(Gemini 2.5 Pro = 카피/UX, Codex = 비판적 리뷰, Claude = 메인 빌더)로 진행.
> 이 문서가 단일 진실 소스(SSOT). 매 루프 이터레이션마다 갱신.

## 운영 원칙 (자율 루프) ★최우선
- **절대 멈추지 않는다.** 결정이 필요하면 셋(Gemini/Codex/Claude)이 판단해 **즉시 진행**. 사용자에게 질문해 블로킹하지 않음.
- 모든 자율 결정은 진행 로그에 `[자율결정] 무엇을/왜` 형식으로 기록 → 사용자가 **나중에 거부권(veto)·수정 가능**.
- 사용자가 1분 내 답 없으면 = 위임으로 간주하고 진행 (사용자 명시 원칙). 사용자가 끼어들면 그 즉시 반영.
- **Git:** 매 이터레이션 끝에 의미 있는 단위로 `git add -A && git commit` → 원격(origin)이 있으면 `git push`. 사용자가 모바일에서 `git pull`로 진행 확인. 원격 없으면 로컬 커밋만(나중에 일괄 푸시). **API 키/시크릿 절대 커밋 금지**(.gitignore로 보호). 커밋 전 정밀 스캔(오탐 방지): `git grep -InE "AIzaSy[0-9A-Za-z_-]{30,}|ghp_[A-Za-z0-9]{30,}"` — 매치 있으면 **실제 중단**하고 제거 후 진행.

## 전략 재정렬 (3-AI 만장일치, max-gear 조준) ★
- **"로직 물량 최대 = 앱스토어 1위"는 틀림** (Gemini 3.1 Pro·Codex·Claude 만장일치). 양으로 신뢰는 안 생기고 내부 자기만족·복잡도부채·가짜신뢰성 위험.
- **1위의 진짜 레버 = 공유(바이럴) 루프 × 신뢰성 × 리텐션.** 로직은 이 루프를 받치는 근거여야지 제품의 자랑거리가 아님.
- **Max 화력은 "더미"가 아니라 고레버리지 3곳에 조준:**
  1. **신뢰성/캘리브레이션** — 베이스라인을 O*NET·워크넷 실데이터로, 출처검증·태스크매핑 정확도, 사용자 피드백 캘리브레이션 루프(가짜 아닌 진짜).
  2. **초개인화 생존 액션플랜(해자) ✅** — `src/actionplan.py`(멀티에이전트 워크플로우 설계→구현→3렌즈 적대검증). 직무 score→이번주 실행 3가지(defend/pivot, 근거뉴스 결박, 실툴명, 난이도/시간). **3렌즈(근거성·일반성·안전) 만장일치 fix-first → 가짜 근거 합성 차단**: driver-task 일치검증, 무매칭 시 -1 정직표기+guardrail_ok=False, 교차오염 제거. Gemini 라이브+폴백 통과. **report 결과화면에 연결 ✅** — '이번 주 생존 액션플랜' 1개 무료 티저+2개 잠금(🔒)→유료CTA가 해제. 해자=수익화 지점 결박. **배치 Gemini 플랜 캐시 ✅** — 변동 시 make_action_plan(use_gemini=True) 캐시, /report가 주입(없으면 폴백). 라이브 확인: 드라이버 있는 직무=source=gemini, 드라이버 0=정직한 폴백(guardrail_ok=False, anti-fake-credibility 작동). **다음: ① ungrounded(guardrail_ok=False) 플랜은 유료잠금 대신 '이번 주 새 근거 없음' 톤으로(근거없는 조언 판매 방지) ② notify 푸시에 액션 1개 노출.**
  3. **공유·리텐션** — MBTI식 결과 시각화(공유 강제), 푸시 훅, 온보딩 3탭 이내.
- **함정 회피:** 근거 없는 처방/지표 30개/에이전트 토론/예측문장 자동생성 = 바쁜일. 출시 지연·API비용 폭증·피봇 마비.

## 0. 락(lock)된 방향성
- **컨셉:** 직업별 'AI 압력지수' — 공포 훅 유지하되 모든 변동에 근거 뉴스 링크 + 영향 업무 + 신뢰도 표시. ❌'대체확률 48%'식 단정 절대 금지.
- **공유 장치:** MBTI식 '전략가 타입' 결과 리포트 (위협+기회 동시 제시 → 부끄럼 없이 공유).
- **유료 트리거:** 무료로 "내 지수 +7, 원인=OO업무" 확인한 직후 → "상위 5%의 대응법 3가지(유료)".
- **시장:** 한국 우선(카카오톡 채널봇 + 미니웹) → 글로벌(영어, 텔레그램/앱).
- **시드 직업:** 영상편집자, 주니어 개발자.
- **네이밍(잠정):** 커리어 시그널 / WorkRadar / 잽(JAB). 루프에서 재검토.

## 1. 제품의 심장 — AI 압력지수 산출 루브릭 v2 (Gemini+Codex 교차검증 반영)

> **v1→v2 핵심 피벗 (Gemini·Codex 독립 수렴):** "직업별 0~100 단일 숫자"를 메인에서 **격하**한다.
> 단일 숫자는 (a) 너무 확정적으로 보여 churn/소송 포인트가 되고 (b) 주관 점수+뉴스편향+불명확 baseline의 합성물이라 방어 불가.
> **메인 = 태스크(업무) 단위 · 근거등급 · 신뢰구간 · 기상예보식 밴드.** 숫자는 보조 지표로.

### 1.1 구조 (태스크 우선)
- 직업이 아니라 **`직무-태스크 매트릭스`** 가 기본 단위. (예: 영상편집자 = 컷편집/자막/색보정/디렉팅… 각각 별도 점수)
- 직업 점수 = **태스크 점수의 가중 평균**으로만 산출. 사용자에겐 "어떤 업무가 점수를 밀었는지"를 먼저 노출.
- 베이스라인은 임의값 금지 → O*NET/워크넷/채용공고/업무시간 비중 등 **관측 데이터**로 산식 공개, **신뢰구간 표기** (예: `62 ± 12`).

### 1.2 델타 산출 5요인 + 앵커 정의 (재현성 확보)
| 요인 | 범위 | 앵커 예시 (주관성 제거) |
|---|---|---|
| 근접도 | 0~3 | 핵심 업무 직접 타격=3, 주변=1, 무관=0 |
| 성숙도 | 0~3 | 3=상용 GA + 유료고객 + 반복 사용사례 3건↑ / 2=베타 / 1=데모 / 0=논문 |
| 도입신호 | 0~3 | 고객사 실명·계약·고용변화 확인=3. **'채용공고 감소' 단독 증거 금지** (계절조정+인접직군 대비+4~8주 추세 필요) |
| 비가역성 | 0~3 | 재숙련 매우 어려움=3 |
| 규모 | 0~2 | 대중 보급형=2, 니치=0 |

- **내부 점수는 실수(float)로 유지**, round() 정보손실 금지. 사용자 표시는 밴드/소수1자리 (`+2.4`, `상승 압력: 중간`).
- **이벤트 클러스터링:** 같은 `기술+벤더+영향태스크+주장유형`은 1건으로 dedup·합산 (논문→데모→베타→GA 중복가산 방지).
- 방향 태그: `automation`/`wage-pressure`/`tool-adoption`/`regulation`/`demand-growth`.

### 1.3 출처 티어링 (펌핑 방어)
- **Tier 1** 공시·정부통계·고객사 직접발표 / **Tier 2** 주요 언론 / **Tier 3** 벤더 보도자료·블로그·유튜브.
- **벤더 단독 출처 max +2.** Tier 3 누적 가중치 상한. 고객사 실명/계약/반복사용 확인 시만 상향.

### 1.4 감쇠/회귀 (운영자 임의조정 차단)
- **공개·고정 함수:** 증거 이벤트 half-life 90일 / 실고용지표 365일 / 규제 이벤트는 만료 전까지 유지.
- 회귀 기준 명시(baseline). 운영자 수동 보정은 반드시 `editorial override` 라벨 + 독립 감사 로그.

### 1.5 표현층 — 기상예보 메타포 (Gemini) + 다음행동 (Gemini)
- 0~100 대신 **AI 기상예보**: 맑음(0~25)/구름조금(26~50)/흐림(51~75)/태풍경보(76~100). 공유 쉬움, 압박 완화.
- 점수 옆 **타임라인 로그** `[+3] 5/12 Adobe Firefly 영상생성 기능 발표 (사유: 핵심업무 자동화 ↑)` → 근거 투명.
- ★**무력감 차단:** 고압력 사용자에겐 반드시 '다음 행동'(리스킬링/트렌드/대응법) 연결. 불안 → 건설적 에너지로 전환.
- 공식(`가중합/14*8`) 노출 금지. "정해진 5원칙으로 계량화한 **참고 지표**, 모든 변동 출처 100% 공개, 인위 보정 불가" 원칙만 소통.

### 1.6 법적/윤리 가드레일 ★한국 규제 실재 (today=2026-06-06)
- **AI 기본법 시행됨 (2026-01-22):** 고용·생계 영향 → '고영향 AI' 해석 여지. 모델카드/데이터출처/평가절차/오류정정 절차를 **초기부터** 구비.
- **개인정보보호법 §37-2 (자동화 결정):** 이 지표를 **개인에 대한 자동결정에 사용 금지** 명시. 설명·이의제기·정정·human review 프로세스.
- **명예훼손(한국은 사실적시도 위험):** 특정 개인/회사/학교/자격군 겨냥 표현 금지. "대체된다"❌ → "관측된 자동화 압력"⭕. 예측 아닌 지표임 명시.
- **불안상품화 방지:** 푸시 카피 공포 프레이밍 금지(`위험 급등`❌ → `관련 업무 자동화 신호 증가`⭕). 단일 숫자만 푸시 금지 — 근거·불확실성·방어역량 동반.

## 2. 진행 로그
- **R1 (설계+검증):** 루브릭 v1 작성 → Gemini(카피/UX)+Codex(적대 리뷰) 실호출 검증 → **v2 피벗 완료**(태스크 단위·근거등급·신뢰구간·기상예보·다음행동·한국규제 가드레일). 셋 다 "단일 숫자 격하"에 수렴.
- **R2 (코드+검증) ✅:** v2 루브릭을 코드화. `src/scoring.py`(점수엔진, 실행됨)·`src/crawler.py`(수집 골격)·`data/jobs/{video-editor,junior-developer}.json`(시드 직무-태스크 매트릭스). Codex 적대 리뷰로 치명버그 다수 수정: 밴드 경계 빈틈, 요인 음수 부호뒤집힘, 출처불명→Δ=0, 멀티태스크 dedup 충돌(키에 job/task/direction 포함), daily cap 미작동·폭주(날짜별·상승/하락 버킷·부분 클램프), 비결정적 순서(Tier·|Δ| 정렬). 데모: 영상편집자 59[흐림]/주니어개발자 50.5[구름조금].
  - **[자율결정]** R2는 백엔드라 Codex 중심 검증, Gemini(카피/UX)는 R4(카카오봇 카피·UI)에서 투입.
- **R3a (구현+라이브검증) ✅:** `src/store.py`(이벤트 스토어 + 점수로그 time series, 직전대비 델타) · `src/gemini_scorer.py`(Gemini 2.5 Pro 5요인 점수화, 키는 env GEMINI_API_KEY, responseMimeType=json + 자체검증) · `src/crawler.py` RSSSource(stdlib urllib+xml, RSS/Atom). **라이브 테스트 통과:** store 시계열·델타 / TechCrunch 실수집 3건 / Gemini가 영향없는 업무 정확히 제외하고 5요인 JSON 반환. 런타임 생성물(data/events, data/scores)은 .gitignore.
  - **[자율결정]** R3 분량 커서 R3a(모듈+검증)/R3b(배선+통계)로 분할.
- **R3b-1 (파이프라인 배선+라이브검증) ✅:** `src/pipeline.py` — fetch→관련성게이트→Gemini 점수화→Event저장→**전체 히스토리 감쇠 재점수(=mean-reversion ③)**→점수로그 append. 라이브 통과(OpenAI 블로그 'Endava' 기사 실채점, 멱등성 OK). **[자율결정+라이브 결함수정]** 벤더 자기홍보 블로그(openai/google/anthropic)를 tier1→**tier3(PR, max+2)** 강등 — 실데이터에서 벤더PR이 adoption/scale 펌핑하는 것 포착, 주니어지수 정정.
- **R3b-2-a (수집/저장 정합성) ✅:** ①원자적 Event 저장(`status` complete/irrelevant/failed, 부분실패는 재시도, recompute는 complete만 반영) ②구조화 dedup_key(Gemini가 technology/vendor 반환→affected별 키, 논문→데모→GA 클러스터) ③_event_id 강건화(추적파라미터만 제거하는 canonical URL — Codex가 ?id 충돌 지적해 정밀화) ④조건부 스냅샷 append(index≥0.1·날씨 변화 시만). 라이브+Codex 교차검증 통과(Codex fix-first 2건 반영: URL충돌·affected별 키).
- **R3b-2-b (점수엔진 정확도) ✅:** ①**factor별 신뢰도 분리**(FACTOR_CONF[tier][factor] — 벤더 maturity 0.9 신뢰/adoption·scale 0.3 보수, 전역 신뢰도 1개를 factor별로 대체) ②**Tier3 누적 캡**(TIER3_JOB_CAP=6/직업, 대량 PR 펌핑 차단) ③**드라이버 표시 프루닝**(점수 누적엔 전부 반영 — Codex가 '작은신호 다수 소멸' 지적해 표시용으로만 제한). 라이브+단위테스트+Codex fix-first 통과(작은신호5건→컷편집 70→72.3 누적 확인).
- **R3b-2-c (task-first + override) ✅:** ④`headline_task`로 태스크 우선 노출, 직업 index는 secondary 명시(소비자 무손상). ⑤Event.override 필드 + `store.save_override()`(override=True + 별도 감사로그 `overrides_audit.jsonl`)로 운영자 보정 구조 분리. 회귀 통과.
- **R4a (카카오 푸시 카피 생성기) ✅:** `src/notify.py` — 점수 스냅샷→푸시 1줄. Gemini 2.5 Pro 카피 + 가드레일 후처리(금칙어 '대체된다' 등 차단) + Gemini 없이도 동작하는 폴백 템플릿. 라이브 통과(업무우선+근거+단정없음+행동유도). 한계: 금칙어 리스트는 백스톱일 뿐 의미적 조작 전부는 못 잡음.
- **R4b (미니웹 결과리포트) ✅:** `src/report.py` — scoring 결과→모바일 우선 정적 HTML. 전략가 타입(Gemini, 위협+기회 동시 → 공유 가능, 예: "AI 편집 설계자형🧠") + 기상예보 시각화 + 태스크별 압력바 + 근거뉴스(출처 배지+링크) + 유료트리거. 라이브+Codex fix-first 통과(XSS scheme 차단 _safe_url). 샘플: `web/sample-report.html`(모바일에서 열어보면 실제 UI).
- **R4c (봇 서버 골격) ✅:** `src/server.py`(stdlib http.server, 의존성0) — POST /webhook/kakao(발화→직업선택→매핑저장→task-first 요약+푸시카피), GET /report(결과리포트 서빙), /health. store에 사용자-직업 매핑(락+원자적쓰기). 라이브 통과(엔드투엔드 사용자여정). Codex 보안 fix-first 5종: Content-Length 제한(64KB·413), body 타입검증(배열/null 크래시 방지), users.json 락+os.replace, /report 점수 TTL캐시+Gemini호출 제거(0.0007s), 127.0.0.1 기본 바인딩.
  - **배포 전 필수(R5):** 웹훅 인증/서명 검증, rate limit, reverse proxy TLS.
- **R4d (일/주 배치) ✅:** `src/batch.py` — pipeline.run()(수집·재점수) → 의미있는 변동(|Δ|≥2 or 날씨변화) 직무의 구독자에게 notify 푸시 큐잉(outbox) + 전략가타입 캐시. 카카오 발송은 스텁. 라이브 통과(영상편집자 Δ+17.3→u1 큐잉). Codex fix-first: **스냅샷 ts 기반 중복 알림 방지**(set_notified/get_notified — 매 배치 같은 알림 재큐잉 스팸 차단, 2회차 재큐잉 0 확인) + 전략가 Gemini는 변동 시에만 호출. server /report는 캐시된 전략가타입 사용.
  - **★ MVP 백엔드 완성:** 크롤링→Gemini채점→지수→시계열→봇서버(웹훅·리포트)→배치알림 전 과정 실작동. 카카오 채널 연결 + 발송 API만 붙이면 런칭 가능.
- **D1 (결과리포트 디자인 고도화, Gemini 3.1 Pro 주도) ✅:** 표현층만 프리미엄 교체(콘텐츠·데이터·가드레일 문구 불변). `src/report.py` 재설계.
  - **[자율결정]** 사용자 "Antigravity로 시도" 요청 → Antigravity는 별도 IDE라 호출 불가하나, 그 기반 모델 **gemini-3.1-pro-preview**가 API로 살아있어 디자인 생성에 사용(2.5 Pro 대비 우월). ※이전에 "Gemini 3.x 없음"이라 한 건 모델목록 출력을 [:12]로 잘라본 내 오류였음 — 3.1-pro/3.5-flash 등 실재.
  - **레퍼런스(각 적용점):** Spotify Wrapped(데이터→공유 스토리, 타입을 '페르소나'로) · 16Personalities(명확한 타입 정체성) · Toss(카드 위계·여백) · Apple Health 링(수치를 위험 아닌 '상태'로, 숫자 보조화) · Apple Weather 밴드(색으로 직관) · Linear(절제된 프리미엄 다크).
  - **구현:** 히어로 카드 안에 반원 SVG 게이지(각도=index/100×180° 동적) + 4단계 기상밴드 + 신뢰구간± / 위협·기회 양면 / task-first 업무바 / 티어배지(공식·언론·벤더PR)+근거 / 유료CTA / 가드레일 푸터. Pretendard 폰트스택·word-break:keep-all 한글 최적화.
  - **Codex fix-first:** 카피 불변 위반(가드레일/섹션/CTA 문구 변경) 전량 복원 + 태풍 task바 빨강떡칠 완화(#e11d48→#fb7185). 통과: WCAG AA(5.89:1/5.25:1), 게이지 각도수학, _safe_url XSS.
- **R5-a (배포 보안) ✅:** server.py — 웹훅 토큰 인증(env WEBHOOK_TOKEN, ?token= 불일치→401) + IP rate limit(env RATE_LIMIT, 윈도우 초과→429). 라이브 통과. **[자율결정]** 고난도 단계(카피·디자인)는 Gemini 3.1 Pro, 루틴(채점·요약)은 2.5 Pro/flash로 모델 분리(비용·품질 균형).
- **R5-b (진행 중):**
  - **CI propagation(weighted) ✅:** `scoring._propagate_job_ci` — 태스크 CI→직업 CI 전파(부분상관 휴리스틱, 정식 통계CI 아님=참고지표). None/음수 가드 + 과신 방지 하한(0.75·가중평균, fear-adjacent 보수성, Codex fix-first). 데모 ±7.6~9.1.
  - **Gemini 중앙 클라이언트 ✅(비용·신뢰성):** `src/gemini_client.py` — 역할별 모델체인(premium=3.1 Pro→2.5 Pro→flash / routine=2.5 Pro→flash) + 프리뷰 deprecate 자동강등 + 429/5xx backoff + 빈응답/MAX_TOKENS soft-fail 강등 + 키 없으면 즉시실패. report·notify를 premium 티어로 연결(역할분담: 디자인·UX·카피=Gemini premium, 코드=Codex+Claude). **[사용자 비용 확인사항]** AI Studio 결제 티어/예산알림은 사용자가 콘솔에서 확인. 다음: actionplan·gemini_scorer도 클라이언트로 이관 + dead import 청소.
  - **발송 파이프라인 ✅:** `src/sender.py` — outbox queued→발송→sent/failed 마킹 + 재시도(max 3) + per-user throttle. `StubSender`(검증용)·`KakaoSender`(스텁, 발신프로필+템플릿 승인 후 연결). batch._flush_outbox가 사용. 라이브: throttle/재시도 검증 통과.
  - **이벤트 아카이브/프루닝 ✅:** `pipeline.prune_events` — 감쇠계수<0.03 non-regulation 이벤트를 events_archive로 이동(무한 재읽기 방지). 규제·최신 보존. 매 배치 실행.
- **R5-b 완료.** 백엔드+제품+발송+하드닝 전부 실작동.
- **R6 (배포, 일부 사용자 필요):** ① README 배포가이드(서버 호스팅·batch cron·env·TLS) ← 자율 가능 ② 카카오 비즈채널+발신프로필+템플릿 승인 ← **사용자 필요** ③ 호스팅(서버 띄우기)+도메인 ← 사용자 결정.
- **R6 (배포):** 서버 호스팅 + 도메인 + TLS + cron(배치) + 카카오 채널 연결(사용자 비즈계정 필요) + README 배포가이드.
- **R5 (하드닝, 이후로 미룸):** 이벤트 만료·아카이브 / CI propagation(weighted) / 비용·쿼터(batch·캐시·backoff) / notify 가드레일 의미검증 강화.
- **R4 (이후):** 카카오 채널봇 카피·UI (Gemini 투입) + 미니웹 결과리포트(전략가타입 공유) + 유료트리거.
- **V1 (수요검증 + 포지셔닝 재설계) ✅:** 사용자 질문="실제로 지갑을 여는 수요가 있나"에 deep-research 하니스(27소스→105주장→상위25 3표 적대검증)로 답. **판정: 순수 B2C 공포구독 유료수요 약함~제한적** — 불안은 크나(전세계 40%) "불안→결제" 인과주장은 검증서 기각(1-2), 위협지수는 이미 무료 commodity(amicooked.io), churn 1위='사용부족' 37%, 커리어 인텔리전스 매출은 B2B 쏠림(리멤버 70~75% B2B). `POSITIONING.md` v2 작성: 위협지수=무료미끼 격하 / 액션플랜=결제정점 / 매출베팅 B2B·정부. **Codex 적대리뷰 반영(fix-first):** ① 액션플랜 텍스트=다음 commodity → "결과물 남는 패키지(첨삭·코호트·연계)"로 ② "혼자막막한 층"=결제력 약한 역설 ③ B2B는 다른 사업(인터뷰20+LOI3 선행) ④ KDT는 매출 아니라 법적지뢰(위탁계약 모집금지)→매출라인 삭제 ⑤ **최대리스크=지불주체 부재**. **다음=만들기 동결, 30일 내 지불주체 1명 증명**(B2C 결제 선판매 권장 / B2B LOI / 훈련기관 합법계약 중 택1). 미증명 시 코드 추가 동결.
- **V2 (런칭=지불주체 테스트 표면) ✅:** 사용자 "런칭까지 자율 진행" 지시 → 검증결론(지불주체 먼저)과 런칭을 합쳐 **사전판매 오퍼를 런칭 표면에 박음**(런칭=30일 스모크테스트). `report.offer_html`(AI 대응 스프린트, 결과물 남는 패키지=Codex fix) + server `/offer`·`POST /offer/interest` + store `append_interest`(중복제거)·`interest_count`. **정직성 fix-first 2건(중요):** ① report CTA의 **검증 안 된 가짜 사회증명 "상위 5%는 이미 대응 중" 제거** → 가치 소구로 교체 ② 오퍼 **가짜 할인 취소선(14,900) 제거** → "테스트 가격, 정식가 오픈 전 확정". **버그수정:** scoring 결과에 `job_id` 누락 → `/detail`·`/offer` 링크가 빈 링크였음(기존 detail도 깨져있던 것 발견·수정). **Codex 적대리뷰 6건 fix-first:** honeypot+동의(PIPA)필수+contact형식검증+(contact,job)중복제거 / fetch `r.ok` 미확인 거짓"완료" / 결제모드vs사전모드 고지 분리 / 가짜할인 제거 / 지표 honest 라벨(`presale_leads`=리드≠지불, 실WTP는 PAYMENT_URL 결제이벤트로) / 원시IP 평문저장 금지→해시(iph). PAYMENT_URL env 연결 시 실결제 버튼 자동전환(코드변경 불필요). 30테스트 통과·라이브 E2E 통과. 미리보기 `web/sample-offer.html`. **다음(자율 계속):** 정적 배포 가능화 + 런칭 런북(사용자 5분 계정작업: 호스팅/결제링크/카카오채널) + 측정 대시.
- **P6 (캘리브레이션 어댑터 스캐폴드 + 정직성 강등, 3-AI 루프) ✅:** baseline 손추정→실데이터 결박 기반 구축. **조사:** O*NET 자체엔 자동화확률 없음 → O*NET-SOC 기반 공개연구(Felten AIOE 2021 / Eloundou GPT exposure 2024 / Frey-Osborne) 사용. **AIOE는 명시적 오픈라이선스 없음** → 외부데이터 커밋 금지. **구현:** `src/calibrate.py`(노출 CSV→percentile 앵커, SOC 자동정규화) + `data/calibration/job_soc_map.json`(15직무→SOC, confidence high/medium) + `data/calibration/README.md` + `.gitignore`(`*.csv`/`*.xlsx`). **★Codex 적대검증이 치명결함 적발 → 정직하게 강등(가짜 캘리 방지):** ① **scoring 표시점수=태스크 롤업이라 baseline.index는 fallback일 뿐** → 직업-레벨 앵커는 표시점수 미반영 → `calibrated:true` 붙이면 가짜 정밀도 → **`calibrated:false` 유지 + `baseline.index_anchor`(참고치)만 부착**으로 강등 ② **외부 raw 점수 유출**(job JSON에 저장→라이선스 위반) → raw 미저장, 파생 percentile만 ③ medium SOC(data-analyst·teacher 등) 동일취급 위험 → **기본 보류(`--apply-medium`만)** ④ percentile은 'CSV 전체 분포' 기준임을 README 경고(15개만 넣으면 왜곡) ⑤ CI 수식 오류 제거. **진짜 캘리브레이션=태스크-레벨 노출 데이터로 태스크 baseline 결박(다음 작업), 지금은 그 기반.** 40테스트 통과(calibrate 5종), 커밋된 직무 전부 calibrated:false 유지(실데이터 미적용=정직). **다음:** 태스크-레벨 노출(Eloundou) 결박 또는 사용자 실제 배포.
- **P5 (배포 준비 감사, 3-AI 루프) ✅:** README/DEPLOY를 P1~P4 변경에 맞춰 점검·갱신 + 런칭 체크리스트 정비. **Codex 적대 감사 fix-first(배포 안전·법무·정직성):** ① **결제 후 이행 절차 미고정**(결제 받고 이행 못 함 위험) → DEPLOY §2.5에 '결제 오픈 전 고정' 블록 추가(PG가 이름·이메일·order_id 수집 / 이력서 제출 흐름 / 주5건 하드캡=PG재고or수동마감) ② **PII 방침이 연락처 중심** → 결제 후 수집 이력서·포트폴리오·인터뷰까지 포함한 처리방침·별도동의 명시 ③ **통신판매업 신고 + 사업자정보 표시** 누락 → §7 체크리스트 추가 ④ 환불/청약철회 고지 위치 반복(오퍼·결제버튼·PG·계약통지, 7일/3개월/3영업일) ⑤ 보안 footgun(umask 077·chmod 600·data 웹루트밖·`*.csv`/백업 .gitignore 추가·`?token=` 로그). **정직성:** README '공포 훅'→'미끼→결과물·통제감', '규제 가드레일 내장'→'일부 제품 가드레일'(법무 전체준수 아님), 오퍼 '커리어 디렉터'→'운영자'(1인 MVP 과장 완화), 공유문구 '너의 직업은 안전할까'(공포)→'얼마나 영향받을까'. 오퍼 grounded 운영노트(배치 1회 먼저). 직군수 10→15 정정. 35테스트 통과, 시크릿 clean. **다음:** O*NET 캘리브레이션(손추정→calibrated, 신뢰성 핵심) 또는 사용자 실제 배포 액션.
- **P4 (액션플랜 프롬프트 정직성 하드닝, 3-AI 루프) ✅:** Codex가 두 번 지적한 생성 오염 정리 — `actionplan.py` `_PROMPT` 도입부의 '생존 액션플랜 엔진', "유료 '상위 5% 대응법'의 실체이므로, 남들이 모를 만큼 구체적"(가짜위계·배타성·공포 프레이밍이 LLM 생성을 오염) → **Gemini 재작성**: '직무 대응 액션플랜 엔진 … 사용자가 주도적으로 통제할 수 있는 … 구체성은 입력된 근거와 업무 연결에서 나온다'(통제감·근거결박 톤). docstring '생존'/'상위 5%'도 정리. **Codex 적대검증: 절대규칙/설계원칙·금칙어·format 플레이스홀더 회귀 없음 확인** + 추가 정직성 fix 2건: ① `evidence_reason_ko`를 모델출력 우선 → **검증된 driver값으로 강제 결박**(evidence_title과 동일, 모델 부풀림 차단 — 조언=모델/근거=검증값 분리) ② `fallback_plan` docstring 거짓('항상 guardrail_ok=True') → 실제(무근거 시 False)대로 정정. 35테스트 통과(test_actionplan_* 포함), 시크릿 clean. **다음:** 배포 준비(README/DEPLOY 점검) 또는 O*NET 캘리브레이션(손추정→calibrated).
- **P3 (액션플랜 잠금 ↔ 패키지 오퍼 정합성, 3-AI 루프) ✅:** 잠긴 2·3번이 '🔒 잠금 — 대응법 보기'(돈 내면 텍스트 더 = commodity 함정)로 읽혀 99,000원 결과물 패키지와 불일치하던 걸 정리. **Gemini 카피 재설계:** 텍스트(주간 방향)=무료 미끼/리텐션, 유료=결과물(이력서 재설계)로 메시지 일관화. `_action_plan_html` 재작성 — 잠긴 제목 **blur 제거(방향=맛보기 노출)** + 잠금 카피를 '이 방향을 내 이력서 요약·성과 불릿 초안으로 — 운영자가 직접 검토해 반영(결과물)'로 + 섹션 서브타이틀 + 무료 '이번 주 핵심 방향' 배지 + 섹션명 '생존 액션플랜'→'액션플랜'(공포 톤 완화) + CTA를 '위 방향, 내 이력서로 만들까요?'로 액션플랜↔패키지 브릿지. **Codex 적대리뷰 fix-first 3건:** ① **`/offer` 직링크가 guardrail_ok 무시 → 무근거 직무도 결제화면 도달**(제품레벨 무근거 판매 구멍): offer_html에 `grounded` 파라미터 추가, server `/offer`가 리포트와 동일 기준으로 판정해 무근거면 '준비 중' 정직 안내(결제버튼 없음) ② 잠금 카피 '상세 단계'가 여전히 '텍스트 더' 뉘앙스 → 결과물만 말하게 ③ '전문가가 직접 적용' 1인 MVP 과장 → '운영자가 직접 검토' + **fail-open `guardrail_ok` 기본값 → fail-closed**(플래그 누락 캐시를 무근거로 간주). 라이브(무근거 직무 오퍼 게이팅·CTA 숨김)+35테스트 통과, 시크릿 clean. 샘플 `web/sample-report.html`. **다음:** actionplan.py 내부 프롬프트 '상위 5% 대응법'(생성 오염 소지) 정리 / 배포(호스팅·PG·카카오, 사용자 필요).
- **P2 (Phase 5 — 결제 검증 웹훅 배선, 3-AI 루프) ✅:** 30일 테스트 핵심지표=실결제인데 앱이 결제완료를 몰랐던 구멍을 닫음(Codex·Gemini 공통 '단 하나의 다음 액션'). `store.py` 결제 WIP(save_payment/_reduce_payments/paid_count, 상태랭크 reported<failed<paid<refunded) 활용 + `server.py`에 배선: **POST `/webhook/payment`**(PG 서버→서버, `PAYMENT_WEBHOOK_SECRET` HMAC-SHA256 원본bytes 서명검증=`_payment_sig_ok` compare_digest, 통과 시에만 paid) · **GET `/payment/success`**(클라이언트 리다이렉트=조작가능 → 아무것도 저장 안 함, '접수 확인' 페이지 `report.payment_pending_html`만) · `/health`에 `paid_customers`(서명검증 paid만, reported≠paid). `data/payments.jsonl` .gitignore. **정직성 불가침 구현:** 시크릿 없으면 501(paid 절대 안 셈), success URL 조작으로 paid 못 부풀림. **Codex 적대 보안리뷰 fix-first 3건:** ① 금액 검증 추가(`_finalize_pay_status` — 서명O라도 amount 0/음수/기대가(`PAYMENT_EXPECTED_AMOUNT`=99000) 불일치면 failed로 강등, 무료/타상품 이벤트 차단) ② status 매핑 좁힘(approved/authorized=승인≠캡처 제외, terminal-paid `done/paid/completed`만) ③ `/payment/success` 공개 append-only DoS 차단(리다이렉트 저장 제거). + 서명헤더 비-hex 방어, save_payment extra가 core필드 못 덮게. 라이브 E2E(위조서명401·0원/5만원/approved→failed·success폭격 무저장·멱등) + 35테스트 통과, 시크릿 clean. **다음:** 액션플랜 잠금(2·3 텍스트)과 패키지 오퍼 기대불일치 정리 / 배포 런북에 PG 웹훅 연결 절차.
- **P1 (Phase 1 — 오퍼 재정의, 3-AI 루프) ✅:** 런칭 로드맵을 Gemini(제품/UX)+Codex(적대리뷰) 종합으로 확정(만장일치: 코드 멈추고 30일 내 지불주체 1명 증명, 파는 건 지수 아닌 '손에 남는 결과물'). **오퍼를 '주간 텍스트 플랜 월 구독(9,900/월, =곧 commodity)'에서 → '`AI 시대 커리어 재설계 패키지`(99,000원 1회성)'로 재정의**: 결과물=데이터 기반 직무진단 리포트+사람 고유 역량 중심 이력서 재배치 가이드+커리어 디렉터가 직접 다듬은 이력서 초안+1~3년 디펜스 플랜. 사람-검토 정직 표기, 진행 4단계, 실결제/사전신청 이원화. `src/report.py` offer_html 재작성 + 리포트 CTA 정합. **Codex 적대리뷰 fix-first 5건(정직성·법무 직격):** ① 환불 문구 위험("작업 시작 후 환불 불가"가 전자상거래법 청약철회권 죽임) → "법정 청약철회권·계약불일치 환불권 보장, 개시분만 법령 범위 내 공제" ② **과장 효능('AI-Proof'/'대체 불가' 절대보장 = 표시광고법 리스크) → 'AI 시대'/'상대적으로 덜 대체되는 사람 고유 역량'으로 완화** ③ '주 5명' 인위적 희소성 우려 → "초기에는 주 최대 5명 수동 검토" 톤(가짜 카운터 아님 명시) ④ PII 동의문에 수집항목+거부권·불이익 고지 추가(PIPA §15) ⑤ `real=bool(payment_url)` 버그(javascript: 등 악성 URL이 실결제 모드로 샘) → `_safe_url` 후 `!="#"`로 판정. + 결제완료 자동확인 안 됨 정직 고지. 30테스트 통과, 시크릿 스캔 clean. 미리보기 `web/sample-offer.html`(사전신청)·`web/sample-offer-paid.html`(실결제). **다음(Phase 5 후보):** 결제 웹훅/성공콜백 배선(`store.py`에 save_payment WIP 존재) + 액션플랜 잠금(2·3 텍스트)과 패키지 오퍼의 기대불일치 정리.
- **V3 (런칭 런북 + 측정 도구 + 정직성 하드닝) ✅:** `src/interest.py`(사전예약 리드 측정 CLI — 총/직무별/가격별/최근, 연락처 마스킹) + DEPLOY.md §2.5 런칭 런북(1단계 리드검증·2단계 결제검증)·§2.6 측정. **Codex 적대리뷰 6건 — 정직성·PII·법무 직격, fix-first:** ① **PAYMENT_URL은 외부링크 보내기만 → 결제완료를 앱이 모름**: "결제이벤트로 WTP 측정"은 아직 미구현임을 DEPLOY에 정직 명시(결제 웹훅/`payments` 저장 = 다음 TODO) ② **국내 PG 현실**(토스 사업자+심사~14일, Stripe 한국 미지원) 런북에 반영, Stripe 제거 ③ **개인정보처리방침을 PII 수집 전 선행 게이트로** 격상(PIPA) ④ CSV PII: 마스킹 기본 + `--raw`만 평문(stderr 경고) + 수식인젝션 방어 ⑤ 무염 SHA256 IP는 역추적 가능 → **솔트 HMAC(`INTEREST_SALT`), 솔트 없으면 IP 미저장**, 오해소지 주석 수정 ⑥ `/health`와 CLI 카운트 분기 → 둘 다 유효 JSON 기준 통일. 좀비 테스트서버 정리. 30테스트 통과. **다음:** 결제 웹훅/성공콜백(`/payment/success`,`/webhook/payment`+payments 저장)으로 진짜 지불검증 닫기 / 오퍼 카피 Gemini 다듬기 / 개인정보처리방침·약관 페이지 템플릿.
