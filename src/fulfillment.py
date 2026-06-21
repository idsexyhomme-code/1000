"""
커리어 시그널 — pain 파일럿 이행 템플릿 생성기.

`/pain-offer`에서 신청받는 상품은 자동화 SaaS가 아니라 컨시어지 파일럿이다.
이 모듈은 결제/신청 이후 운영자가 바로 만들 수 있는 납품 골격을 생성한다.

사용:
    python3 src/fulfillment.py --job video-editor --pain revision-chaos --sample
    python3 src/fulfillment.py --job video-editor --pain revision-chaos --kickoff --sample
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import painmap  # noqa: E402
import pain_probe  # noqa: E402
import store  # noqa: E402
from scoring import ScoringEngine  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JOBS_DIR = os.path.join(_ROOT, "data", "jobs")


SAMPLE_INPUTS: dict[tuple[str, str], dict] = {
    ("video-editor", "revision-chaos"): {
        "contact": "sample@example.com",
        "role_type": "freelancer",
        "sample_available": "redacted",
        "situation": (
            "브랜드 유튜브 1차본 납품 후 카톡, 구글문서 댓글, 메일로 수정 요청이 섞여 들어왔고 "
            "최종본 파일명이 v3_final_final로 꼬인 상태."
        ),
        "micro_itches": [
            "수정 요청이 카톡, 메일, 댓글, 캡처 이미지에 흩어져 타임라인에 다시 꽂아야 한다.",
            "클라이언트 요청끼리 서로 충돌하는데 어느 방향을 확인해야 할지 정리되지 않는다.",
        ],
    },
    ("junior-developer", "unknown-codebase-context"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "결제 실패 버그가 배정됐지만 주문, 쿠폰, 알림 코드가 섞여 영향 범위를 못 잡는 상태.",
        "micro_itches": [
            "작은 티켓인데 어느 파일부터 봐야 할지 몰라 README, Slack, 코드 검색을 계속 오간다.",
            "PR 설명에 수정 의도, 위험한 사이드이펙트, 검증 명령을 쓰는 게 어렵다.",
        ],
    },
    ("marketer", "weekly-report-story"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "광고비는 늘었는데 전환율은 떨어졌고, 월요일 회의용으로 원인과 다음 실험을 설명해야 하는 상태.",
    },
    ("sales-rep", "pre-call-brief"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "30분 뒤 신규 고객 미팅인데 회사 맥락, 담당자 관심사, 발견 질문을 한 장으로 정리해야 하는 상태.",
    },
    ("data-analyst", "why-did-it-drop"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "어제 가입 전환율이 18% 떨어졌다는 질문을 받았지만 세그먼트와 이벤트 변경 여부가 정리되지 않은 상태.",
    },
    ("accountant", "missing-client-docs"): {
        "contact": "sample@example.com",
        "role_type": "lead",
        "sample_available": "redacted",
        "situation": "부가세 마감 전 고객별 통장내역, 카드매출, 누락 영수증을 다시 요청해야 하는 상태.",
    },
    ("office-admin", "request-chasing"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "교육 참석자 명단, 비용 승인, 장소 확정 요청이 여러 부서에 흩어져 마감 전 재촉해야 하는 상태.",
    },
    ("graphic-designer", "revision-boundary"): {
        "contact": "sample@example.com",
        "role_type": "freelancer",
        "sample_available": "redacted",
        "situation": "계약 범위를 넘는 추가 시안과 문구 변경 요청이 계속 들어오지만 추가비 안내를 꺼내기 어려운 상태.",
    },
    ("teacher", "differentiated-materials"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "같은 단원 안에서도 기초, 보통, 심화 학생 수준 차이가 커서 활동지와 채점 기준을 따로 만들어야 하는 상태.",
    },
    ("nurse", "charting-fatigue"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "교대 전 투약, 활력징후, 환자 호소, 인계 내용을 빠뜨리지 않고 차팅 문장으로 정리해야 하는 상태.",
    },
    ("translator", "mtpe-quality-trap"): {
        "contact": "sample@example.com",
        "role_type": "freelancer",
        "sample_available": "redacted",
        "situation": "기계번역 후편집 문서에서 용어 불일치와 어색한 문장이 많지만 어디부터 고쳐야 할지 정리되지 않은 상태.",
    },
    ("journalist", "press-release-triage"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "하루에 들어온 보도자료가 많아 기사화 가치와 추가취재 질문을 빠르게 골라야 하는 상태.",
    },
    ("hr-manager", "resume-screening-rationale"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "후보자 이력서가 많이 들어왔고, 왜 면접 대상인지/아닌지 설명 가능한 근거를 남겨야 하는 상태.",
    },
    ("call-center-agent", "after-call-work"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "상담 후 요약, 이관 메모, 후속조치 등록을 동시에 해야 해서 통화가 끝나도 업무가 쌓이는 상태.",
    },
    ("paralegal", "case-timeline"): {
        "contact": "sample@example.com",
        "role_type": "employee",
        "sample_available": "redacted",
        "situation": "계약서, 메일, 영수증, 문자 캡처가 섞여 있어 사건 순서와 증거목록을 변호사에게 전달하기 어려운 상태.",
    },
}


def _job_results() -> dict[str, dict]:
    return ScoringEngine(_JOBS_DIR).score([])


def load_job(job_id: str) -> dict:
    jobs = _job_results()
    if job_id not in jobs:
        raise ValueError(f"unknown job: {job_id}")
    return jobs[job_id]


def intent_rows(path: str | None = None) -> list[dict]:
    """저장된 pain intent를 오래된 순서대로 읽는다. 깨진 줄은 건너뛴다."""
    path = path or store.PAIN_INTENT_FILE
    if not os.path.exists(path):
        return []
    out: list[dict] = []
    for ln in open(path, encoding="utf-8"):
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except Exception:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def select_intent(
    selector: str = "latest",
    *,
    job_id: str = "",
    pain_id: str = "",
    path: str | None = None,
) -> dict:
    """pain intent 1건 선택.

    selector:
      - latest: 필터와 맞는 가장 최근 row
      - 1 이상의 숫자: 필터 후 오래된 순서 기준 1-based index
      - 음수 숫자: 필터 후 뒤에서부터 index(-1=가장 최근)
    """
    rows = intent_rows(path)
    if job_id:
        rows = [r for r in rows if r.get("job") == job_id]
    if pain_id:
        rows = [r for r in rows if r.get("pain_id") == pain_id]
    if not rows:
        raise ValueError("no matching pain intent")

    s = str(selector or "latest").strip().lower()
    if s == "latest":
        return rows[-1]
    try:
        idx = int(s)
    except Exception as e:
        raise ValueError("intent selector must be 'latest' or an integer") from e
    if idx == 0:
        raise ValueError("intent selector is 1-based; use 1 or -1, not 0")
    pos = idx - 1 if idx > 0 else len(rows) + idx
    if pos < 0 or pos >= len(rows):
        raise ValueError("pain intent selector out of range")
    return rows[pos]


def _mask_contact(contact: str) -> str:
    c = (contact or "").strip()
    if not c:
        return "미기재"
    if "@" in c:
        local, _, dom = c.partition("@")
        return f"{local[:2]}***@{dom}" if local else f"***@{dom}"
    return f"{c[:2]}***" if len(c) > 2 else "***"


def _line(value: str, fallback: str = "미기재") -> str:
    s = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return s or fallback


def _micro_lines(values) -> str:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        values = []
    out = []
    for value in values:
        s = _line(value, "")
        if s and s not in out:
            out.append(s)
    return "\n".join(f"  - {x}" for x in out[:6]) or "  - 미기재"


def _focus_block(job_id: str, micro_itches) -> str:
    focus = pain_probe.fulfillment_focus(job_id, micro_itches)
    if not focus.get("selected_micro_itches_ko"):
        return ""
    moves = "\n".join(f"- {x}" for x in focus.get("operator_moves_ko", []))
    questions = "\n".join(f"- {x}" for x in focus.get("followup_questions_ko", []))
    avoid = focus.get("avoid_ko", "")
    return f"""## micro-itch 우선순위
- 작업 초점: {focus.get("priority_focus_ko", "")}

### 운영자 반영 규칙
{moves}

### 추가 확인 질문
{questions}

### 넘지 말아야 할 경계
- {avoid or "전문 판단이나 성과 보장을 대신하지 않는다."}
"""


def _md_cell(value: str) -> str:
    return str(value or "").replace("|", "/").replace("\r", " ").replace("\n", " ").strip()


def _artifact_adjustment_block(job_id: str, micro_itches) -> str:
    adjustment = pain_probe.artifact_adjustment(job_id, micro_itches)
    rows = adjustment.get("adjustment_rows", [])
    if not rows:
        return ""
    table = [
        "| 선택한 작은 가려움 | 산출물 위치 | 추가할 필수 칸/행 | QA 기준 |",
        "|---|---|---|---|",
    ]
    for row in rows:
        table.append(
            "| {micro} | {slot} | {fields} | {qa} |".format(
                micro=_md_cell(row.get("micro_itch_ko", "")),
                slot=_md_cell(row.get("artifact_slot_ko", "")),
                fields=_md_cell(row.get("template_fields_ko", "")),
                qa=_md_cell(row.get("qa_check_ko", "")),
            )
        )
    return f"""## micro-itch 산출물 조정
{adjustment.get("note_ko", "")}

{chr(10).join(table)}
"""


def _sample_table_rows(job_id: str, pain_id: str) -> list[str]:
    if (job_id, pain_id) == ("video-editor", "revision-chaos"):
        return [
            "| 카톡 | 00:13-00:18 | 오프닝 호흡이 길다는 피드백 | 컷 편집 | 높음 | 대기 | 편집자 | 0.5초 단축안으로 반영 |",
            "| 구글문서 | 01:42 | 제품명 자막 표기 수정 | 자막 | 높음 | 대기 | 편집자 | 브랜드 표기 가이드 확인 후 반영 |",
            "| 메일 | 전체 | 배경음이 발표 목소리를 덮음 | 사운드 | 중간 | 대기 | 편집자 | BGM -4dB 테스트본 전달 |",
        ]
    return [
        "| 신청자 설명 | 핵심 반복 업무 | 결과물 초안 작성 | 높음 | 대기 | 운영자 | 샘플 자료 확인 후 반영 |",
        "| 신청자 설명 | 이해관계자 커뮤니케이션 | 회신문 초안 | 중간 | 대기 | 운영자 | 과장 표현 제거 후 전달 |",
    ]


def _video_revision_sections(sample: bool) -> str:
    rows = _sample_table_rows("video-editor", "revision-chaos") if sample else [
        "|  |  |  |  |  |  |  |  |",
        "|  |  |  |  |  |  |  |  |",
        "|  |  |  |  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 수정요청 원문 정리
- 요청 출처별로 원문을 보존한다: 카톡, 메일, 댓글, 문서, 통화 메모.
- 중복 요청은 합치되, 충돌하는 요청은 "확인 필요"로 남긴다.
- 작업자가 임의로 해석한 내용은 원문과 분리한다.

### 2. 타임코드별 수정 체크리스트
| source | timecode | request | edit_type | priority | status | owner | reply |
|---|---:|---|---|---|---|---|---|
{chr(10).join(rows)}

### 3. 클라이언트 회신문 초안
안녕하세요. 전달주신 수정 요청은 아래 기준으로 정리했습니다.

- 바로 반영: 타임코드가 명확하고 기존 방향과 충돌하지 않는 항목
- 확인 필요: 요청끼리 충돌하거나 추가 자료가 필요한 항목
- 제안 조정: 전체 완성도나 납기상 대안이 더 안전한 항목

확인 필요 항목만 회신 주시면, 나머지는 다음 버전에 반영해 전달드리겠습니다.

### 4. 버전 관리 규칙
- 최신 작업본 파일명: `프로젝트명_YYYYMMDD_v번호`
- 클라이언트 전달본과 내부 작업본을 분리한다.
- 수정 요청 수집 마감 시각을 한 번 정하고, 이후 요청은 다음 라운드로 넘긴다.
- "최종", "진짜최종" 같은 파일명은 쓰지 않는다.

### 5. 전달 전 QA
- 요청마다 상태가 `완료` 또는 `확인 필요`인지 확인
- 자막 표기, 이름, 브랜드명, 가격, 날짜처럼 되돌리기 어려운 항목 재확인
- 음량 피크, 무음 구간, 컷 튐, 화면비, 썸네일 문구 확인
- 클라이언트 회신문과 실제 반영본이 서로 모순되지 않는지 확인
"""


def _developer_context_sections(sample: bool) -> str:
    rows = [
        "| 주문 생성 | `orders/create` | 결제 실패 후 주문 상태가 `pending`으로 남음 | 쿠폰 복원/알림 발송 중복 가능 | 결제 실패 통합 테스트 | 확인 필요 |",
        "| 쿠폰 적용 | `coupons/apply` | 실패 시 롤백 경로 불명확 | 쿠폰 재사용 가능성 | 쿠폰 롤백 단위 테스트 | 대기 |",
        "| 알림 발송 | `notifications/payment` | 실패 이벤트에서도 발송될 수 있음 | 고객 혼란 | 이벤트 조건 테스트 | 대기 |",
    ] if sample else [
        "|  |  |  |  |  |  |",
        "|  |  |  |  |  |  |",
        "|  |  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 이슈 원문과 재현 조건
- 사용자가 받은 티켓/버그 리포트 원문을 보존한다.
- 기대 동작, 실제 동작, 재현 단계, 관련 로그를 분리한다.
- 재현이 안 되면 "추정 수정"을 하지 말고 추가 확인 질문으로 남긴다.

### 2. 수정 영향도 맵
| area | file_or_module | evidence | side_effect_risk | verification | status |
|---|---|---|---|---|---|
{chr(10).join(rows)}

### 3. 테스트 초안
- 단위 테스트:
- 통합 테스트:
- 회귀 테스트:
- 수동 확인 명령:

### 4. PR 설명문 초안
**문제:**  
**원인 후보:**  
**수정 범위:**  
**검증:**  
**리뷰어가 봐야 할 위험:**  

### 5. 전달 전 QA
- 파일 후보가 이슈와 직접 연결되는지 확인
- 테스트 없이 "고친 것 같다"는 표현을 제거
- 보안키, 토큰, 고객정보, 로그 원문이 PR 설명에 남지 않았는지 확인
"""


def _marketer_weekly_sections(sample: bool) -> str:
    rows = [
        "| CAC | +24% | 신규 캠페인 | CPC 상승 + 랜딩 전환 하락 | medium | 소재별 CTR/랜딩 CVR 분리 |",
        "| 전환율 | -11% | 모바일 | 폼 이탈 증가 가능성 | low | 디바이스별 퍼널 확인 |",
        "| 재방문 구매 | +8% | 기존 고객 | 리마케팅 메시지 반응 | medium | 쿠폰 사용률 확인 |",
    ] if sample else [
        "|  |  |  |  |  |  |",
        "|  |  |  |  |  |  |",
        "|  |  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 지표 원문 정리
- 기간, 비교 기준, 예산, 채널, 캠페인명을 먼저 고정한다.
- 숫자는 원천을 표시하고, 추정 원인은 숫자와 분리한다.
- "잘 됐다/망했다"가 아니라 어떤 행동을 바꿀지 중심으로 쓴다.

### 2. 주간 성과 해석표
| metric | change | segment | likely_cause | confidence | next_check |
|---|---:|---|---|---|---|
{chr(10).join(rows)}

### 3. 다음 실험 3개
1. 가설:
   실행:
   성공 기준:
2. 가설:
   실행:
   성공 기준:
3. 가설:
   실행:
   성공 기준:

### 4. 보고서 문장
이번 주 핵심 변화는 ___입니다. 숫자만 보면 ___처럼 보이지만, 채널/세그먼트 기준으로 나누면 ___ 가능성이 더 큽니다. 다음 주에는 ___ 실험을 먼저 진행하고, ___ 지표로 판단하겠습니다.

### 5. 전달 전 QA
- 원인 후보를 확정 원인처럼 쓰지 않았는지 확인
- 보고서 문장이 상사용 한 문장과 실무자용 액션으로 분리되는지 확인
- 예산 증액/감액 같은 결정은 근거와 리스크를 함께 둔다
"""


def _sales_precall_sections(sample: bool) -> str:
    rows = [
        "| 회사 맥락 | 최근 채용 증가 | 도입 예산/팀 확장 가능성 | medium | 어떤 팀에서 병목이 커졌나요? |",
        "| 담당자 관심사 | 운영 효율 | 수작업 감축 메시지 | low | 지금 가장 많이 반복되는 수작업은 무엇인가요? |",
        "| 리스크 | 기존 솔루션 사용 | 전환비용 반대논리 | medium | 현재 도구에서 바꾸기 어려운 이유가 있나요? |",
    ] if sample else [
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 3분 미팅 브리프
- 고객사가 지금 돈/시간을 쓰고 있을 가능성이 큰 문제:
- 담당자가 관심 가질 만한 업무 병목:
- 오늘 미팅에서 확인해야 할 구매 신호:
- 미리 피해야 할 과장 메시지:

### 2. 고객 맥락표
| signal | evidence | sales_angle | confidence | discovery_question |
|---|---|---|---|---|
{chr(10).join(rows)}

### 3. 발견 질문 7개
1. 지금 이 문제를 어떤 방식으로 처리하고 있나요?
2. 이 문제가 반복될 때 누가 가장 많은 시간을 쓰나요?
3. 최근에 이 문제 때문에 놓친 기회나 비용이 있었나요?
4. 이미 써본 도구가 있다면 무엇이 부족했나요?
5. 의사결정에 누가 함께 들어오나요?
6. 도입하면 가장 먼저 검증하고 싶은 기준은 무엇인가요?
7. 이 문제가 해결되면 다음으로 풀고 싶은 병목은 무엇인가요?

### 4. 미팅 후속 메모 틀
- 고객이 직접 말한 pain:
- 구매 신호:
- 반대논리:
- 다음 액션:
- CRM 업데이트 문장:
"""


def _data_drop_sections(sample: bool) -> str:
    rows = [
        "| 이벤트 변경 | 가입 완료 이벤트 누락/중복 | 높음 | 배포 로그, 이벤트 카운트 | SQL A |",
        "| 유입 믹스 변화 | 저전환 채널 비중 증가 | 중간 | channel별 전환율 | SQL B |",
        "| 분모 변경 | 봇/테스트 트래픽 포함 | 중간 | user_agent, internal flag | SQL C |",
    ] if sample else [
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 지표 정의 잠금
- 지표명:
- 분자:
- 분모:
- 기간/타임존:
- 제외 조건:
- 대시보드/테이블 출처:

### 2. 원인 후보 트리
| candidate | hypothesis | priority | validation | sql_slot |
|---|---|---|---|---|
{chr(10).join(rows)}

### 3. SQL 초안
```sql
-- SQL A: 이벤트 카운트 일자별 비교
select event_date, count(*) as events
from analytics.events
where event_name = 'SIGNUP_COMPLETED'
group by event_date
order by event_date;

-- SQL B: 채널별 전환율 비교
select channel, count_if(converted) * 1.0 / nullif(count(*), 0) as conversion_rate
from analytics.funnel
where event_date between :start_date and :end_date
group by channel;
```

### 4. 이해관계자 설명문
현재 하락은 확정 원인 하나로 말하기 어렵습니다. 우선순위가 높은 후보는 ___이고, ___를 확인하면 이벤트 문제인지 유입 믹스 문제인지 분리할 수 있습니다. 오늘은 ___까지 확인하고, 내일 ___ 기준으로 후속 공유하겠습니다.

### 5. 전달 전 QA
- SQL은 초안이며 실제 테이블명/권한/정의 검토가 필요하다고 표시
- 분모와 기간을 쓰지 않은 증감률 문장을 제거
- 원인 후보와 확정 원인을 문장상 분리
"""


def _accountant_docs_sections(sample: bool) -> str:
    rows = [
        "| 카드매출 내역 | 2026-06-24 | 미수령 | 매출 누락 가능 | 카드사 월별 매출자료 PDF로 전달 부탁드립니다. |",
        "| 사업용 계좌 입출금 | 2026-06-24 | 일부 수령 | 비용/매출 대사 지연 | 6월 전체 거래내역이 필요합니다. |",
        "| 누락 영수증 | 2026-06-25 | 미수령 | 비용 반영 지연 | 현금/간이영수증 사진을 모아 보내주세요. |",
    ] if sample else [
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 고객별 누락자료 체크
- 신고/마감 유형:
- 고객명 또는 내부 관리번호:
- 받은 자료:
- 빠진 자료:
- 마감 영향:

### 2. 누락자료 체크리스트
| document | due_date | status | risk | client_request |
|---|---:|---|---|---|
{chr(10).join(rows)}

### 3. 고객 안내문
안녕하세요. 신고 준비를 위해 아래 자료가 추가로 필요합니다. 자료가 늦어지면 일부 비용/매출 확인이 지연될 수 있어, 가능한 항목부터 먼저 전달 부탁드립니다.

- 오늘 바로 필요한 자료:
- 있으면 좋은 자료:
- 민감정보 가림 가능 여부:
- 제출 방법:

### 4. 내부 확인 순서
1. 고객이 이미 보낸 파일과 중복 요청인지 확인
2. 마감에 직접 영향 있는 자료를 먼저 표시
3. 고객이 이해하기 쉬운 이름으로 자료명을 바꿔 안내
4. 세무 판단이 필요한 항목은 담당자가 직접 검토
"""


def _office_request_sections(sample: bool) -> str:
    rows = [
        "| 교육 운영 | 참석자 명단 | 인사팀 | 2026-06-24 12:00 | 대기 | 양식 링크 재전달 |",
        "| 비용 처리 | 강사비 승인 | 재무팀 | 2026-06-24 15:00 | 진행중 | 승인권자 확인 필요 |",
        "| 장소 예약 | 회의실 확정 | 총무팀 | 2026-06-23 18:00 | 완료 | 확정 공지 반영 |",
    ] if sample else [
        "|  |  |  |  |  |  |",
        "|  |  |  |  |  |  |",
        "|  |  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 요청 취합 기준
- 요청명을 동사형이 아니라 완료 상태로 쓴다.
- 담당자, 마감, 현재 상태, 막힌 이유를 분리한다.
- 이미 완료된 항목은 다시 재촉하지 않도록 표시한다.

### 2. 요청 추적 보드
| project | request_item | owner | deadline | status | blocker_or_next |
|---|---|---|---:|---|---|
{chr(10).join(rows)}

### 3. 리마인드 메시지
안녕하세요. ___ 마감 확인차 짧게 공유드립니다. 현재 ___ 항목이 아직 미확인 상태라, ___까지 회신 주시면 전체 일정에 맞춰 취합하겠습니다. 이미 처리하셨다면 이 메시지는 무시하셔도 됩니다.

### 4. 에스컬레이션 기준
- 마감 24시간 전 미회신:
- 마감 4시간 전 미회신:
- 의사결정자 승인이 필요한 항목:
- 일정 변경이 필요한 항목:
"""


def _designer_revision_sections(sample: bool) -> str:
    rows = [
        "| 문구 오탈자 수정 | 포함 | 1회 | 즉시 반영 | 무료 범위 |",
        "| 전체 레이아웃 재구성 | 제외 | 신규 시안 | 1영업일 추가 | 추가 견적 필요 |",
        "| 이미지 소스 교체 | 조건부 | 제공 자료 필요 | 자료 수령 후 반영 | 저작권 확인 필요 |",
    ] if sample else [
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 요청 원문 분류
- 계약/견적에 포함된 수정과 새 작업을 분리한다.
- 디자인 취향 피드백과 명확한 오류 수정은 따로 표시한다.
- 추가비 안내는 감정 표현 없이 범위와 작업량 기준으로 쓴다.

### 2. 수정 범위표
| request | scope_status | round_or_size | operator_move | fee_note |
|---|---|---|---|---|
{chr(10).join(rows)}

### 3. 정중한 추가비 안내문
말씀주신 ___는 기존 수정 범위를 넘어 새 시안 작업에 가까워 별도 작업으로 분리하는 것이 안전합니다. 기존 범위 안에서는 ___까지 반영 가능하고, ___까지 진행하려면 추가 견적과 일정 확인이 필요합니다.

### 4. 버전/승인 규칙
- 현재 기준 버전:
- 무료 수정 라운드:
- 추가비 전환 기준:
- 최종 승인 후 변경 처리:
"""


def _teacher_material_sections(sample: bool) -> str:
    rows = [
        "| 기초 | 핵심 개념 빈칸 채우기 | 예시 제공, 선택지 3개 | 개념 3개 중 2개 설명 |",
        "| 보통 | 짧은 적용 문제 | 힌트 1개 제공 | 풀이 과정 포함 |",
        "| 심화 | 실제 사례 분석 | 추가 자료 링크 | 근거 2개 이상 제시 |",
    ] if sample else [
        "|  |  |  |  |",
        "|  |  |  |  |",
        "|  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 수업 목표 잠금
- 단원/차시:
- 오늘 반드시 남길 개념:
- 학생이 스스로 할 수 있어야 하는 행동:
- 평가할 증거:

### 2. 수준별 활동지
| level | activity | support | success_criteria |
|---|---|---|---|
{chr(10).join(rows)}

### 3. 채점 루브릭
| criterion | 1점 | 2점 | 3점 |
|---|---|---|---|
| 개념 이해 | 핵심어 없음 | 핵심어 일부 사용 | 핵심어를 정확히 설명 |
| 적용 | 예시 없음 | 익숙한 예시에 적용 | 새로운 사례에 적용 |
| 설명 | 답만 제시 | 이유 일부 제시 | 근거와 과정을 함께 제시 |

### 4. 수업 전 확인
- 학교/학급 맥락에 맞지 않는 예시 제거
- 학생 개인정보나 민감 상황이 드러나는 문항 제거
- 교사가 최종 난이도와 표현을 조정
"""


def _nurse_charting_sections(sample: bool) -> str:
    rows = [
        "| 09:00 | 활력징후 확인 | BP/HR/BT 기록 | 수치 재확인 |",
        "| 10:30 | 통증 호소 | 부위/강도/양상 | 담당자 보고 여부 확인 |",
        "| 12:00 | 투약 | 약명/용량/반응 | 투약 기록 대조 |",
    ] if sample else [
        "|  |  |  |  |",
        "|  |  |  |  |",
        "|  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 사건/처치 타임라인
| time | event | charting_point | missing_check |
|---:|---|---|---|
{chr(10).join(rows)}

### 2. 차팅 문장 초안
- ___ 시 ___ 확인함.
- 환자 ___ 호소하여 ___ 관찰함.
- ___ 시행 후 ___ 변화 확인함.
- 담당자/의료진에게 ___ 보고함.

### 3. 누락 확인 리스트
- 시간
- 객관적 수치
- 환자 주관 호소
- 시행한 처치
- 반응/변화
- 보고/인계 여부

### 4. 전달 전 QA
- 의료 판단이나 처방 제안으로 보이는 문장 제거
- 실제 기록 기준과 병원 양식에 맞춰 면허자가 최종 검토
- 환자 식별정보는 외부 샘플에서 제거
"""


def _translator_mtpe_sections(sample: bool) -> str:
    rows = [
        "| terminology | product suite | 제품군/제품 묶음 혼용 | 높음 | 용어집 기준으로 통일 |",
        "| fluency | machine-like sentence | 한국어 어순 부자연 | 중간 | 의미 보존 후 재문장화 |",
        "| accuracy | may/shall | 의무/가능 의미 혼동 | 높음 | 원문 문맥 재확인 |",
    ] if sample else [
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 용어/문체 기준 잠금
- 용어집:
- 금지 표현:
- 고객 문체:
- 원문에서 의미가 흔들리는 구간:

### 2. 번역 QA 리포트
| category | source_or_issue | problem | priority | revision_move |
|---|---|---|---|---|
{chr(10).join(rows)}

### 3. 수정 우선순위
1. 의미 오류와 숫자/고유명사
2. 용어 불일치
3. 문장 자연스러움
4. 스타일 선호

### 4. 고객 회신문
기계번역 후편집 기준으로 우선순위를 나누어 점검했습니다. 의미 오류 가능성이 있는 항목을 먼저 표시했고, 문체 개선 항목은 납기와 예산에 맞춰 조정 가능합니다.
"""


def _journalist_release_sections(sample: bool) -> str:
    rows = [
        "| 스타트업 투자유치 | 신규성 있음 | 투자자/금액/시장성 | 중간 | 매출·고객 수 확인 |",
        "| 임원 인사 | 반복 보도자료 | 이해관계자 영향 | 낮음 | 조직 변화 의미 확인 |",
        "| 신제품 출시 | 소비자 영향 가능 | 차별점/가격/출시일 | 높음 | 경쟁 제품 비교 질문 |",
    ] if sample else [
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 보도자료 선별 기준
- 공익성/독자 영향
- 새로움
- 검증 가능한 숫자
- 이해관계자 반응 가능성
- 단순 홍보 문구 비중

### 2. 보도자료 선별표
| item | news_value | angle | priority | follow_up_check |
|---|---|---|---|---|
{chr(10).join(rows)}

### 3. 추가취재 질문
- 이 발표가 독자에게 실제로 바꾸는 것은 무엇인가?
- 숫자나 성과는 독립적으로 확인 가능한가?
- 이해관계자나 경쟁사는 어떻게 반응할 수 있는가?
- 보도자료에서 빠진 불리한 정보는 무엇인가?

### 4. 기사화 메모
- 바로 기사화:
- 추가취재 후 판단:
- 단신 처리:
- 보류/폐기:
"""


def _hr_screening_sections(sample: bool) -> str:
    rows = [
        "| A후보 | B2B SaaS 3년 | 고객 온보딩 경험 | 공백 8개월 | 고객 이탈 대응 사례 | 면접 검토 |",
        "| B후보 | 데이터 분석 프로젝트 | SQL/리포팅 경험 | 도메인 경험 부족 | 실제 대시보드 소유 경험 | 보류 |",
        "| C후보 | 유관 업계 영업 | 산업 이해 | 직무 전환 동기 불명확 | 전환 사유와 학습 계획 | 면접 검토 |",
    ] if sample else [
        "|  |  |  |  |  |  |",
        "|  |  |  |  |  |  |",
        "|  |  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 포지션 기준 잠금
- 필수 요건:
- 우대 요건:
- 이번 채용에서 포기할 수 없는 기준:
- 평가하면 안 되는 민감 기준:

### 2. 후보자 요약표
| candidate | evidence | match_reason | unknown_or_risk | interview_question | status_draft |
|---|---|---|---|---|---|
{chr(10).join(rows)}

### 3. 면접 확인 질문
- 이력서에서 가장 강한 근거를 실제 사례로 확인하는 질문:
- 리스크/공백을 공정하게 확인하는 질문:
- 직무 핵심 상황을 가정한 질문:
- 후보자가 질문할 시간을 남기는 질문:

### 4. 전달 전 QA
- 자동 합격/불합격 판단처럼 쓰지 않는다.
- 나이, 성별, 가족, 건강, 출신 등 민감/차별 요소를 평가 기준에 넣지 않는다.
- 채용 담당자가 최종 판단하고 근거를 남긴다.
"""


def _callcenter_aftercall_sections(sample: bool) -> str:
    rows = [
        "| 본인확인 | 완료 | 이름/주문번호 확인 | 없음 |",
        "| 문의 요지 | 배송 지연 | 고객은 금요일 전 수령 원함 | 물류팀 확인 필요 |",
        "| 약속한 후속조치 | 재안내 | 18시 전 문자 안내 | 담당자 지정 필요 |",
    ] if sample else [
        "|  |  |  |  |",
        "|  |  |  |  |",
        "|  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 상담 요약
| step | status | note | missing_or_next |
|---|---|---|---|
{chr(10).join(rows)}

### 2. 이관 메모
- 고객 요청:
- 지금까지 확인한 사실:
- 약속한 후속조치:
- 이관받는 팀이 확인할 것:
- 고객에게 다시 연락할 시각:

### 3. 후속조치 등록 문장
고객은 ___ 문제로 문의했고, ___까지 확인했습니다. ___ 확인이 필요해 ___팀에 이관합니다. 고객에게는 ___까지 회신 예정이라고 안내했습니다.

### 4. 전달 전 QA
- 고객 감정 표현과 확인된 사실을 분리
- 주민번호, 카드번호 등 민감정보 제거
- 상담사가 약속하지 않은 보상/처리를 임의로 쓰지 않음
"""


def _paralegal_timeline_sections(sample: bool) -> str:
    rows = [
        "| 2026-05-01 | 계약 체결 | 계약서.pdf | 당사자/금액/기한 | 원본 확인 |",
        "| 2026-05-18 | 납품 지연 통보 | 이메일 캡처 | 지연 사유 | 발신자 확인 |",
        "| 2026-06-02 | 환불 요청 | 문자 캡처 | 요청 내용 | 전체 대화 필요 |",
    ] if sample else [
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
        "|  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 사건 타임라인
| date | event | source_doc | relevance | missing_check |
|---:|---|---|---|---|
{chr(10).join(rows)}

### 2. 증거목록
| evidence_id | document | what_it_shows | source | authenticity_check |
|---|---|---|---|---|
| E-01 |  |  |  |  |
| E-02 |  |  |  |  |
| E-03 |  |  |  |  |

### 3. 변호사 검토 질문
- 날짜 순서에서 빠진 구간은 어디인가?
- 원본 확인이 필요한 자료는 무엇인가?
- 상대방 주장과 충돌하는 증거는 무엇인가?
- 법률 판단이 필요한 쟁점은 무엇인가?

### 4. 전달 전 QA
- 법률 의견처럼 단정하지 않고 사실 정리로 제한
- 원본/사본/캡처를 구분
- 개인정보와 민감정보는 사건 필요 범위로만 유지
"""


def _generic_sections(pain: dict, sample: bool) -> str:
    rows = _sample_table_rows("", "") if sample else [
        "|  |  |  |  |  |  |",
        "|  |  |  |  |  |  |",
        "|  |  |  |  |  |  |",
    ]
    return f"""## 납품 골격
### 1. 원문/자료 정리
- 사용자가 보낸 설명, 파일, 링크, 기존 문서를 원문 그대로 보존한다.
- 작업자가 추정한 내용은 "추정"으로 표시하고, 확인 질문으로 분리한다.
- 민감정보와 불필요한 개인정보는 산출물에서 제거한다.

### 2. {pain.get("artifact_ko", "결과물")} 초안
| input | issue | operator_move | priority | status | note |
|---|---|---|---|---|---|
{chr(10).join(rows)}

### 3. 사용자에게 보낼 확인 질문
- 이 결과물이 쓰일 실제 상황은 무엇인가?
- 반드시 지켜야 하는 형식, 마감, 금지 표현은 무엇인가?
- 누가 최종 승인하거나 사용할 산출물인가?
- 샘플 자료에서 그대로 인용하면 안 되는 내용은 무엇인가?

### 4. 회신문/전달문 초안
안녕하세요. 보내주신 자료를 기준으로 반복 업무를 줄일 수 있는 형태로 정리했습니다.

- 정리한 결과물: {pain.get("artifact_ko", "결과물")}
- 바로 사용할 수 있는 부분:
- 확인이 필요한 부분:
- 다음에 같은 문제가 생기지 않도록 남길 규칙:

### 5. 전달 전 QA
- 신청자가 말한 "가려운 순간"과 산출물이 직접 연결되는지 확인
- 전문 판단, 법률/의료/세무 판단, 채용/해고 판단처럼 사람이 책임져야 할 영역을 대신하지 않았는지 확인
- 과장된 성과 보장, 자동 해결, 확정 표현을 제거
- 개인정보, 고객명, 내부자료, 영업비밀이 필요 이상 포함되지 않았는지 확인
"""


def _special_sections(job_id: str, pain_id: str, sample: bool) -> str | None:
    builders = {
        ("video-editor", "revision-chaos"): _video_revision_sections,
        ("junior-developer", "unknown-codebase-context"): _developer_context_sections,
        ("marketer", "weekly-report-story"): _marketer_weekly_sections,
        ("sales-rep", "pre-call-brief"): _sales_precall_sections,
        ("data-analyst", "why-did-it-drop"): _data_drop_sections,
        ("accountant", "missing-client-docs"): _accountant_docs_sections,
        ("office-admin", "request-chasing"): _office_request_sections,
        ("graphic-designer", "revision-boundary"): _designer_revision_sections,
        ("teacher", "differentiated-materials"): _teacher_material_sections,
        ("nurse", "charting-fatigue"): _nurse_charting_sections,
        ("translator", "mtpe-quality-trap"): _translator_mtpe_sections,
        ("journalist", "press-release-triage"): _journalist_release_sections,
        ("hr-manager", "resume-screening-rationale"): _hr_screening_sections,
        ("call-center-agent", "after-call-work"): _callcenter_aftercall_sections,
        ("paralegal", "case-timeline"): _paralegal_timeline_sections,
    }
    builder = builders.get((job_id, pain_id))
    return builder(sample) if builder else None


def _materials(job_id: str, pain_id: str) -> list[str]:
    if (job_id, pain_id) == ("video-editor", "revision-chaos"):
        return [
            "현재 최신 영상본 링크 또는 파일명",
            "수정 요청 원문 전체: 카톡/메일/댓글/문서 캡처 가능",
            "반드시 지켜야 하는 납기와 전달 형식",
            "브랜드명, 제품명, 출연자명처럼 오탈자 리스크가 큰 표기",
            "이전 버전과 최신 버전의 구분 기준",
        ]
    if (job_id, pain_id) == ("junior-developer", "unknown-codebase-context"):
        return [
            "이슈/티켓 원문과 기대 동작",
            "재현 단계, 에러 로그, 스크린샷. 토큰/개인정보는 제거",
            "관련 레포 구조 또는 파일 목록",
            "현재 실패하는 테스트나 실행 명령",
        ]
    if (job_id, pain_id) == ("marketer", "weekly-report-story"):
        return [
            "이번 주와 비교 기간의 핵심 지표",
            "채널/캠페인/소재별 성과 표 또는 캡처",
            "예산 변경, 랜딩 변경, 프로모션 여부",
            "보고 대상과 보고서 톤",
        ]
    if (job_id, pain_id) == ("sales-rep", "pre-call-brief"):
        return [
            "고객사명과 미팅 목적",
            "이전 대화 메모 또는 CRM 기록",
            "참석자 역할과 직함",
            "제안하려는 상품/서비스 요약",
        ]
    if (job_id, pain_id) == ("data-analyst", "why-did-it-drop"):
        return [
            "문제가 된 지표명과 기간",
            "현재 쓰는 지표 정의와 대시보드 링크",
            "관련 테이블/이벤트명. 접근권한 없는 값은 비식별",
            "최근 배포, 캠페인, 추적 변경 여부",
        ]
    if (job_id, pain_id) == ("accountant", "missing-client-docs"):
        return [
            "고객별 이미 받은 자료 목록",
            "마감일과 신고/정산 유형",
            "누락으로 의심되는 자료 목록",
            "고객에게 보낼 수 있는 연락 채널과 톤",
        ]
    if (job_id, pain_id) == ("office-admin", "request-chasing"):
        return [
            "요청 항목, 담당자, 부서, 마감일 목록",
            "이미 보낸 공지/메일/메신저 원문",
            "완료/진행중/막힘 상태",
            "재촉해도 되는 톤과 에스컬레이션 기준",
        ]
    if (job_id, pain_id) == ("graphic-designer", "revision-boundary"):
        return [
            "계약/견적 범위와 무료 수정 라운드",
            "클라이언트 수정 요청 원문",
            "현재 버전 파일명과 이전 승인 내역",
            "추가비 안내가 필요한 항목과 원하지 않는 표현",
        ]
    if (job_id, pain_id) == ("teacher", "differentiated-materials"):
        return [
            "단원, 차시, 학습 목표",
            "학생 수준 그룹과 수업 시간",
            "이미 쓰는 교재/활동지 샘플",
            "평가 기준과 학교에서 피해야 할 표현",
        ]
    if (job_id, pain_id) == ("nurse", "charting-fatigue"):
        return [
            "비식별 처리된 시간대별 관찰/처치 메모",
            "병동/기관 차팅 양식",
            "인계가 필요한 항목",
            "면허자 최종 검토 기준",
        ]
    if (job_id, pain_id) == ("translator", "mtpe-quality-trap"):
        return [
            "원문과 기계번역 결과 일부",
            "용어집, 스타일 가이드, 금지 표현",
            "납기와 우선 검토 범위",
            "고객이 민감하게 보는 품질 기준",
        ]
    if (job_id, pain_id) == ("journalist", "press-release-triage"):
        return [
            "보도자료 원문 또는 제목 목록",
            "매체 독자층과 관심 분야",
            "오늘 처리 가능한 기사 수",
            "이미 확인된 취재원/연락 가능 여부",
        ]
    if (job_id, pain_id) == ("hr-manager", "resume-screening-rationale"):
        return [
            "직무기술서와 필수/우대 요건",
            "비식별 후보자 이력서 또는 요약",
            "조직에서 평가하면 안 되는 민감 기준",
            "면접으로 확인하고 싶은 역량",
        ]
    if (job_id, pain_id) == ("call-center-agent", "after-call-work"):
        return [
            "비식별 상담 메모 또는 녹취 요약",
            "고객 요청, 확인한 사실, 약속한 후속조치",
            "이관할 팀과 SLA",
            "사용 중인 CRM 필드 형식",
        ]
    if (job_id, pain_id) == ("paralegal", "case-timeline"):
        return [
            "사건 관련 문서 목록과 날짜",
            "계약서, 메일, 문자 등 증거 원문. 민감정보는 필요 범위만",
            "변호사가 이미 지시한 정리 기준",
            "법률 판단이 아니라 사실정리로 제한할 범위",
        ]
    return [
        "반복해서 막히는 실제 업무 상황 설명",
        "샘플 자료 1개 이상. 민감정보는 가려도 됨",
        "결과물이 쓰일 대상: 본인, 고객, 상사, 팀원",
        "마감, 형식, 금지 표현, 반드시 포함할 정보",
    ]


def materials_for(job_id: str, pain_id: str) -> list[str]:
    """job/pain별 고객 요청 자료 목록. 결제 직후 요청 메시지와 이행서가 같은 원천을 쓴다."""
    return list(_materials(job_id, pain_id))


def kickoff_plan(
    job: dict,
    pain_id: str,
    *,
    contact: str = "",
    role_type: str = "",
    sample_available: str = "",
    situation: str = "",
    micro_itches=None,
    sample: bool = False,
) -> str:
    pain = painmap.get(job, pain_id)
    if not pain:
        raise ValueError(f"unknown pain for {job.get('job_id')}: {pain_id}")

    job_id = job.get("job_id", "")
    if sample:
        sample_input = SAMPLE_INPUTS.get((job_id, pain_id), {})
        contact = contact or sample_input.get("contact", "")
        role_type = role_type or sample_input.get("role_type", "")
        sample_available = sample_available or sample_input.get("sample_available", "")
        situation = situation or sample_input.get("situation", "")
        micro_itches = micro_itches or sample_input.get("micro_itches", [])

    selected = pain_probe.selected_micro_itches(job_id, micro_itches or [])
    focus = pain_probe.fulfillment_focus(job_id, selected)
    questions = focus.get("followup_questions_ko", [])[:5]
    adjustment = pain_probe.artifact_adjustment(job_id, selected)
    adjustment_rows = adjustment.get("adjustment_rows", [])
    materials = materials_for(job_id, pain_id)
    material_lines = "\n".join(f"{i}. {m}" for i, m in enumerate(materials, 1))
    question_lines = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1)) if questions else "1. 마지막으로 이 문제가 터진 실제 상황, 원문 자료, 마감은 무엇인가요?"
    selected_lines = _micro_lines(selected)
    adj_lines = "\n".join(
        f"- {row.get('artifact_slot_ko', '')}: {row.get('template_fields_ko', '')} / QA: {row.get('qa_check_ko', '')}"
        for row in adjustment_rows[:4]
    ) or "- 선택된 작은 가려움이 없으면 공통 안전 표(input / pain_signal / artifact_move / priority / qa_check)를 사용한다."
    request_message = f"""안녕하세요. {pain.get("artifact_ko")} 제작을 시작하기 위해 아래 자료를 부탁드립니다.

자료는 민감정보, 고객명, 내부 기밀을 필요한 범위만 남기고 가려서 보내셔도 됩니다.
자료를 받은 뒤 영업일 3일 안에 1차 초안을 전달드리고, 자료가 부족하면 먼저 확인 질문을 보내겠습니다.

필요 자료:
{material_lines}

먼저 확인할 질문:
{question_lines}

이번 파일럿 범위는 '{pain.get("service_move_ko")}'이며, 자동화된 전문 판단이나 성과 보장은 제공하지 않습니다."""

    return f"""# {job.get("job_name_ko", job_id)} pain 파일럿 킥오프 — {pain.get("itch_ko")}

생성시각: {datetime.now(timezone.utc).isoformat()}

## release candidate
- 직업군: {job.get("job_name_ko", job_id)} (`{job_id}`)
- pain_id: `{pain_id}`
- 연락처: {_mask_contact(contact)}
- 일하는 형태: {_line(role_type)}
- 샘플 제공 가능성: {_line(sample_available)}
- 현재 상황: {_line(situation)}
- 납품물: {pain.get("artifact_ko")}
- 기본 납기: 자료 수령 후 영업일 3일
- 범위: {pain.get("service_move_ko")}

## 선택한 작은 가려움
{selected_lines}

## 고객에게 보낼 자료 요청 메시지
```text
{request_message}
```

## D0-D3 운영 체크리스트
### D0 결제/신청 직후
- 주문번호, 연락처, 선택 job/pain, 결제금액을 확인한다.
- 위 자료 요청 메시지를 보내고, 자료 제출 경로와 마감 시각을 남긴다.
- 개인정보, 고객자료, 영업비밀은 필요한 최소 범위만 받는다고 다시 안내한다.

### D1 자료 검수와 질문
- 받은 자료를 `{pain.get("artifact_ko")}`에 필요한 입력으로 분류한다.
- 부족하거나 충돌하는 정보는 확인 질문으로 분리한다.
- 샘플이 부족하면 완성본처럼 쓰지 말고 예시/템플릿 납품으로 전환한다.

### D2 산출물 초안 작성
- 첫 번째 작은 가려움이 결과물의 어느 표/문장/체크리스트로 해결되는지 상단에 표시한다.
- 전용 산출물 칸을 반영한다.
{adj_lines}
- 확정할 수 없는 해석은 `확인 필요`로 남긴다.

### D3 QA와 전달
- 약속 산출물, 확인 필요 항목, 다음 액션을 한 번에 볼 수 있게 정리한다.
- 전문 판단, 성과 보장, 법률/의료/세무/채용 판단으로 읽힐 문장을 제거한다.
- 전달 후 상태를 fulfillment queue에서 `delivered` 또는 `blocked`로 갱신한다.

## 금지/가드레일
- 이 파일럿은 자동화된 전문 판단이나 성과 보장을 제공하지 않는다.
- 법률, 의료, 세무, 회계, 노무, 채용/해고 같은 전문 판단은 담당 전문가 또는 책임자가 최종 검토해야 한다.
- 개인정보, 고객자료, 영업비밀은 필요한 최소 범위만 사용하고 외부 공유용 샘플에는 포함하지 않는다.
"""


def generate(
    job: dict,
    pain_id: str,
    *,
    contact: str = "",
    role_type: str = "",
    sample_available: str = "",
    situation: str = "",
    micro_itches=None,
    sample: bool = False,
) -> str:
    pain = painmap.get(job, pain_id)
    if not pain:
        raise ValueError(f"unknown pain for {job.get('job_id')}: {pain_id}")

    job_id = job.get("job_id", "")
    if sample:
        sample_input = SAMPLE_INPUTS.get((job_id, pain_id), {})
        contact = contact or sample_input.get("contact", "")
        role_type = role_type or sample_input.get("role_type", "")
        sample_available = sample_available or sample_input.get("sample_available", "")
        situation = situation or sample_input.get("situation", "")
        micro_itches = micro_itches or sample_input.get("micro_itches", [])

    task_names = ", ".join(pain.get("task_names_ko") or [])
    sections = _special_sections(job_id, pain_id, sample) or _generic_sections(pain, sample)
    materials = "\n".join(f"- {m}" for m in _materials(job_id, pain_id))
    focus_block = _focus_block(job_id, micro_itches)
    adjustment_block = _artifact_adjustment_block(job_id, micro_itches)

    return f"""# {job.get("job_name_ko", job_id)} pain 파일럿 이행서 — {pain.get("itch_ko")}

생성시각: {datetime.now(timezone.utc).isoformat()}

## 신청 요약
- 직업군: {job.get("job_name_ko", job_id)} (`{job_id}`)
- pain_id: `{pain_id}`
- 연락처: {_mask_contact(contact)}
- 일하는 형태: {_line(role_type)}
- 샘플 제공 가능성: {_line(sample_available)}
- 연결 업무: {task_names or "미기재"}
- 가려운 순간: {pain.get("moment_ko")}
- 사용자가 원하는 결과물: {pain.get("artifact_ko")}
- 현재 상황: {_line(situation)}
- 선택한 작은 가려움:
{_micro_lines(micro_itches)}

{focus_block}
{adjustment_block}
## 파일럿 약속 범위
- 목표: {pain.get("service_move_ko")}
- 납품물: {pain.get("artifact_ko")}
- 처리 방식: 운영자가 자료를 읽고 컨시어지 방식으로 1차 결과물을 만든다.
- 기본 납기: 영업일 3일. 자료가 부족하면 확인 질문을 먼저 보낸다.

## 수집할 자료
{materials}

## 운영자 체크리스트
- 신청자가 실제로 겪은 상황을 원문 기준으로 다시 정리한다.
- 산출물은 "한 번 보고 바로 쓸 수 있는 형식"으로 만든다.
- 샘플 자료가 없으면 완성본처럼 쓰지 말고 예시/템플릿으로 표시한다.
- 결제 상품 범위를 벗어나는 추가 분석, 자동화 구축, 장기 컨설팅은 다음 상품으로 분리한다.
- 결과물 마지막에 확인 필요 항목과 다음 액션을 남긴다.

{sections}
## 금지/가드레일
- 이 파일럿은 자동화된 전문 판단이나 성과 보장을 제공하지 않는다.
- 법률, 의료, 세무, 회계, 노무, 채용/해고 같은 전문 판단은 담당 전문가 또는 책임자가 최종 검토해야 한다.
- 개인정보, 고객자료, 영업비밀은 필요한 최소 범위만 사용하고 외부 공유용 샘플에는 포함하지 않는다.
- "완전히 해결", "무조건 통과", "대체 불가" 같은 보장 표현을 쓰지 않는다.
- 사람이 최종 검토하지 않은 결과물을 고객/상사/외부 이해관계자에게 바로 보내지 않는다.
"""


def build_from_ids(
    job_id: str,
    pain_id: str,
    *,
    contact: str = "",
    role_type: str = "",
    sample_available: str = "",
    situation: str = "",
    micro_itches=None,
    sample: bool = False,
) -> str:
    job = load_job(job_id)
    return generate(
        job,
        pain_id,
        contact=contact,
        role_type=role_type,
        sample_available=sample_available,
        situation=situation,
        micro_itches=micro_itches,
        sample=sample,
    )


def kickoff_from_ids(
    job_id: str,
    pain_id: str,
    *,
    contact: str = "",
    role_type: str = "",
    sample_available: str = "",
    situation: str = "",
    micro_itches=None,
    sample: bool = False,
) -> str:
    job = load_job(job_id)
    return kickoff_plan(
        job,
        pain_id,
        contact=contact,
        role_type=role_type,
        sample_available=sample_available,
        situation=situation,
        micro_itches=micro_itches,
        sample=sample,
    )


def build_from_intent(row: dict) -> str:
    """pain intent row 1건을 실제 이행서로 변환한다."""
    if not isinstance(row, dict):
        raise ValueError("intent row must be a dict")
    job_id = str(row.get("job", "")).strip()
    pain_id = str(row.get("pain_id", "")).strip()
    if not job_id or not pain_id:
        raise ValueError("intent row missing job or pain_id")
    return build_from_ids(
        job_id,
        pain_id,
        contact=str(row.get("contact", "")),
        role_type=str(row.get("role_type", "")),
        sample_available=str(row.get("sample_available", "")),
        situation=str(row.get("situation", "")),
        micro_itches=row.get("micro_itches", []),
        sample=False,
    )


def kickoff_from_intent(row: dict) -> str:
    if not isinstance(row, dict):
        raise ValueError("intent row must be a dict")
    job_id = str(row.get("job", "")).strip()
    pain_id = str(row.get("pain_id", "")).strip()
    if not job_id or not pain_id:
        raise ValueError("intent row missing job or pain_id")
    return kickoff_from_ids(
        job_id,
        pain_id,
        contact=str(row.get("contact", "")),
        role_type=str(row.get("role_type", "")),
        sample_available=str(row.get("sample_available", "")),
        situation=str(row.get("situation", "")),
        micro_itches=row.get("micro_itches", []),
        sample=False,
    )


def _print_or_save(text: str, out_path: str = "") -> None:
    if not out_path:
        print(text)
        return
    dir_name = os.path.dirname(out_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")
    os.replace(tmp, out_path)
    print(f"saved: {out_path}")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="pain 파일럿 이행 템플릿을 생성합니다.")
    ap.add_argument("--job", default="", help="job_id, 예: video-editor")
    ap.add_argument("--pain", default="", help="pain_id, 예: revision-chaos")
    ap.add_argument("--contact", default="", help="연락처. 출력에는 마스킹됩니다.")
    ap.add_argument("--role-type", default="", help="employee/freelancer/jobseeker/lead 등")
    ap.add_argument("--sample-available", default="", help="yes/redacted/no 등")
    ap.add_argument("--situation", default="", help="현재 겪는 상황")
    ap.add_argument("--sample", action="store_true", help="비식별 샘플 입력을 채워 생성")
    ap.add_argument("--kickoff", action="store_true", help="결제 직후 고객 자료 요청 + D0-D3 운영 체크리스트 생성")
    ap.add_argument("--out", default="", help="Markdown 저장 경로. 미지정 시 stdout 출력")
    ap.add_argument("--from-intent", default="", help="pain_intent.jsonl에서 생성: latest, 1, -1 등")
    ap.add_argument("--intent-file", default="", help="테스트/운영용 pain intent jsonl 경로 override")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    try:
        if args.from_intent:
            row = select_intent(
                args.from_intent,
                job_id=args.job,
                pain_id=args.pain,
                path=args.intent_file or None,
            )
            text = kickoff_from_intent(row) if args.kickoff else build_from_intent(row)
            _print_or_save(text, args.out)
            return 0
        if not args.job or not args.pain:
            sys.stderr.write("--job and --pain are required unless --from-intent is used\n")
            return 2
        if args.kickoff:
            text = kickoff_from_ids(
                args.job,
                args.pain,
                contact=args.contact,
                role_type=args.role_type,
                sample_available=args.sample_available,
                situation=args.situation,
                sample=args.sample,
            )
        else:
            text = build_from_ids(
                args.job,
                args.pain,
                contact=args.contact,
                role_type=args.role_type,
                sample_available=args.sample_available,
                situation=args.situation,
                sample=args.sample,
            )
        _print_or_save(text, args.out)
        return 0
    except ValueError as e:
        sys.stderr.write(str(e) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
