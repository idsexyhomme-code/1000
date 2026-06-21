# Pain 파일럿 이행서 카탈로그

이 카탈로그는 15개 직업군 대표 pain을 실제 납품 가능한 컨시어지 파일럿으로 좁힌 운영용 샘플입니다. 모든 이행서는 `src/fulfillment.py`로 생성하며, 연락처는 출력에서 마스킹됩니다.

결제 오퍼를 열기 전에는 먼저 `python3 src/pain_deepdive.py > web/sample-pain-atlas.md`로 각 직업군의 구매 트리거, 첫 10분 안도감, 성공 지표를 확인합니다.

실제 신청이 들어온 뒤에는 샘플 입력 대신 저장된 intent를 사용합니다.

```bash
python3 src/fulfillment.py --from-intent latest
python3 src/fulfillment.py --from-intent latest --job video-editor
python3 src/fulfillment.py --from-intent -1 --job marketer --pain weekly-report-story
```

micro-itch 산출물 조정 샘플은 영상편집자와 주니어 개발자 파일로 먼저 확인합니다.

```bash
python3 src/fulfillment.py --job video-editor --pain revision-chaos --sample
python3 src/fulfillment.py --job video-editor --pain revision-chaos --kickoff --sample
python3 src/fulfillment.py --job junior-developer --pain unknown-codebase-context --sample
```

여러 신청을 놓치지 않으려면 작업 큐로 승격해 상태를 기록합니다.

```bash
python3 src/fulfillment_queue.py import
python3 src/fulfillment_queue.py list   # due/overdue 포함
python3 src/fulfillment_queue.py report # 병목 + 다음 운영 액션/첫 확인 질문 + paid pain 이행 경고
python3 src/fulfillment_queue.py memo   # data/fulfillment_reports/YYYY-MM-DD.md 저장(paid 경고 포함)
python3 src/fulfillment_queue.py weekly # 주간 병목 변화 + 제품화 우선순위 + paid 이행 경고
python3 src/fulfillment_queue.py productize # 주간 병목 1~3위 기준 좁은 오퍼 카피 초안 저장
python3 src/fulfillment_queue.py productize-preview # 주간 제품화 후보의 /pain-offer HTML preview 저장
python3 src/fulfillment_queue.py reconcile-paid # paid pain 주문과 큐/kickoff 누락 대조
python3 src/fulfillment_queue.py repair-paid --all # 이슈 paid pain 주문의 큐/kickoff 멱등 복구
python3 src/fulfillment_queue.py checkpoint ORDER_ID kickoff_sent --note "자료 요청 발송"
python3 src/fulfillment_queue.py checkpoint ORDER_ID materials_received --note "원본 자료 수신"
python3 src/fulfillment_queue.py checkpoint ORDER_ID draft_ready --note "초안 검수 대기"
python3 src/fulfillment_queue.py next   # due_at이 가장 빠른 queued 작업
python3 src/fulfillment_queue.py render fq_xxxxxxxxxxxx
python3 src/fulfillment_queue.py status fq_xxxxxxxxxxxx delivered --note "결과물 전달 완료"
```

| job_id | 대표 pain | 납품물 | 샘플 생성 명령 |
|---|---|---|---|
| `accountant` | `missing-client-docs` | 누락자료 체크리스트 + 고객 안내문 | `python3 src/fulfillment.py --job accountant --pain missing-client-docs --sample` |
| `call-center-agent` | `after-call-work` | 상담 요약 + 이관 메모 + 후속조치 | `python3 src/fulfillment.py --job call-center-agent --pain after-call-work --sample` |
| `data-analyst` | `why-did-it-drop` | 원인 후보 트리 + SQL 초안 + 이해관계자 설명문 | `python3 src/fulfillment.py --job data-analyst --pain why-did-it-drop --sample` |
| `graphic-designer` | `revision-boundary` | 수정 범위표 + 정중한 추가비 안내문 | `python3 src/fulfillment.py --job graphic-designer --pain revision-boundary --sample` |
| `hr-manager` | `resume-screening-rationale` | 후보자 요약표 + 면접 확인 질문 | `python3 src/fulfillment.py --job hr-manager --pain resume-screening-rationale --sample` |
| `journalist` | `press-release-triage` | 보도자료 선별표 + 추가취재 질문 | `python3 src/fulfillment.py --job journalist --pain press-release-triage --sample` |
| `junior-developer` | `unknown-codebase-context` | 수정 영향도 맵 + 테스트 초안 + PR 설명문 | `python3 src/fulfillment.py --job junior-developer --pain unknown-codebase-context --sample` |
| `marketer` | `weekly-report-story` | 주간 성과 해석 + 다음 실험 3개 + 보고서 문장 | `python3 src/fulfillment.py --job marketer --pain weekly-report-story --sample` |
| `nurse` | `charting-fatigue` | 차팅 문장 초안 + 누락 확인 리스트 | `python3 src/fulfillment.py --job nurse --pain charting-fatigue --sample` |
| `office-admin` | `request-chasing` | 요청 추적 보드 + 리마인드 메시지 | `python3 src/fulfillment.py --job office-admin --pain request-chasing --sample` |
| `paralegal` | `case-timeline` | 사건 타임라인 + 증거목록 | `python3 src/fulfillment.py --job paralegal --pain case-timeline --sample` |
| `sales-rep` | `pre-call-brief` | 3분 미팅 브리프 + 발견 질문 7개 | `python3 src/fulfillment.py --job sales-rep --pain pre-call-brief --sample` |
| `teacher` | `differentiated-materials` | 수준별 활동지 + 채점 루브릭 | `python3 src/fulfillment.py --job teacher --pain differentiated-materials --sample` |
| `translator` | `mtpe-quality-trap` | 번역 QA 리포트 + 수정 우선순위 | `python3 src/fulfillment.py --job translator --pain mtpe-quality-trap --sample` |
| `video-editor` | `revision-chaos` | 타임코드별 수정 체크리스트 + 클라이언트 회신문 | `python3 src/fulfillment.py --job video-editor --pain revision-chaos --sample` |

## 운영 원칙
- 이행서는 결제 전 운영 가능성을 확인하기 위한 샘플이다.
- 킥오프 문서는 결제 직후 고객에게 보낼 자료 요청 메시지와 D0-D3 운영 체크리스트다.
- 실결제는 3영업일 내 납품 가능한 pain에만 연다. 큐는 import 시 `due_at`과 선택된 micro-itch를 보존하고 overdue와 작은 가려움 병목을 표시한다.
- pain-paid 웹훅이 서명검증과 금액검증을 통과하면 `fq_pay_*` 작업과 `kickoff-ORDER_ID.md`가 자동 생성된다. `report/memo/weekly`는 paid 주문, 큐 작업, kickoff 파일 누락 경고와 체크포인트 진행률을 포함하고, `reconcile-paid`는 주문별 상세 대조, `repair-paid`는 누락 복구를 수행한다.
- 체크포인트는 `kickoff_sent` → `materials_received` → `draft_ready` → `final_delivered` 순서로 기록한다. `final_delivered`는 큐 상태도 `delivered`로 바꾼다.
- 운영 메모 `data/fulfillment_reports/*.md`는 큐 상황 요약을 포함하므로 외부공유·커밋하지 않는다.
- 제품화 초안 `data/fulfillment_reports/productization-*.md`는 주간 micro-itch 병목을 좁은 랜딩 문구, promise, deliverable fields, 첫 질문, CTA로 바꾼 운영용 초안이다.
- 제품화 preview `data/fulfillment_reports/productization-preview-*/*.html`은 같은 후보를 실제 `/pain-offer` 화면으로 렌더링해 결제 오픈 전 문구·범위·CTA를 점검하는 파일이다.
- `/pain-offer`는 URL에 `mi=`가 없을 때 해당 pain의 실제 선택값을 먼저 쓰고, 없으면 주간 운영 메모의 제품화 micro-itch를 기본값으로 사용한다.
- micro-itch 산출물 조정은 15개 직업군의 대표 작은 가려움에 전용 칸/QA 기준을 적용한다. 선택 항목이 아직 세부 규칙에 없으면 공통 안전 표로 fallback한다.
- 법률, 의료, 세무, 회계, 노무, 채용 판단은 자동화하지 않고 담당 전문가 또는 책임자가 최종 검토한다.
- 개인정보, 고객자료, 영업비밀은 필요한 최소 범위만 사용한다.
