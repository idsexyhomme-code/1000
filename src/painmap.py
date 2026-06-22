"""
커리어 시그널 — 직업별 가려움 지도 (product pain map)

AI 압력지수는 "어떤 업무가 자동화 신호를 받는가"를 말한다. 이 모듈은 한 단계 더 내려가
"현업자가 매주 반복해서 짜증나는 순간"과 "서비스가 실제로 만들어줄 산출물"을 연결한다.

중요: 이 데이터는 사용자 인터뷰 전 제품 가설이다. 리포트에서는 calibrated 지표처럼 보이지 않게
"제품 가설"로 라벨링하고, 유료 결제 근거가 아니라 문제 발견/온보딩 문맥으로만 사용한다.
"""
from __future__ import annotations

from copy import deepcopy

_WTP_SCORE = {"high": 2.0, "medium": 1.0, "low": 0.0}


PAIN_MAP: dict[str, list[dict]] = {
    "junior-developer": [
        {
            "pain_id": "unknown-codebase-context",
            "task_ids": ["architecture", "debugging-complex", "bug-fixing"],
            "itch_ko": "처음 보는 코드에서 어디를 고쳐야 하는지 찾는 시간",
            "moment_ko": "작은 버그처럼 보였는데 관련 파일, 사이드이펙트, 테스트 범위가 안 잡힐 때",
            "service_move_ko": "이슈와 레포를 읽고 수정 후보 파일, 영향 범위, 검증 명령을 묶어준다",
            "artifact_ko": "수정 영향도 맵 + 테스트 초안 + PR 설명문",
            "severity": 5,
            "frequency": 4,
            "wtp": "high",
        },
        {
            "pain_id": "pr-review-anxiety",
            "task_ids": ["code-review", "testing"],
            "itch_ko": "PR 올리기 전 뭘 놓쳤는지 몰라 불안한 상태",
            "moment_ko": "리뷰어가 볼 만한 엣지케이스, 네이밍, 테스트 누락을 스스로 점검해야 할 때",
            "service_move_ko": "diff 기준으로 예상 리뷰 코멘트와 보완 패치를 먼저 만든다",
            "artifact_ko": "사전 리뷰 체크리스트 + 보완 커밋 후보",
            "severity": 4,
            "frequency": 5,
            "wtp": "medium",
        },
        {
            "pain_id": "resume-from-tickets",
            "task_ids": ["boilerplate-coding", "bug-fixing", "testing"],
            "itch_ko": "내가 한 티켓을 이력서 성과로 바꾸지 못하는 문제",
            "moment_ko": "분명 많이 일했는데 포트폴리오에는 '기능 개발' 같은 말만 남을 때",
            "service_move_ko": "커밋/PR/이슈를 성과 문장과 기술 키워드로 재구성한다",
            "artifact_ko": "포트폴리오 불릿 5개 + 면접 설명 스크립트",
            "severity": 4,
            "frequency": 3,
            "wtp": "high",
        },
    ],
    "video-editor": [
        {
            "pain_id": "revision-chaos",
            "task_ids": ["cut-editing", "subtitle", "sound-mixing"],
            "itch_ko": "클라이언트 수정 요청이 흩어져 버전 관리가 무너지는 순간",
            "moment_ko": "카톡, 메일, 댓글로 온 수정사항을 타임라인 기준으로 다시 정리해야 할 때",
            "service_move_ko": "수정 요청을 타임코드와 작업 유형으로 정리하고 체크리스트화한다",
            "artifact_ko": "타임코드별 수정 체크리스트 + 클라이언트 회신문",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "shorts-repurpose",
            "task_ids": ["cut-editing", "subtitle", "thumbnail"],
            "itch_ko": "긴 영상을 쇼츠 여러 개로 쪼개는 반복 노동",
            "moment_ko": "하이라이트 후보, 자막, 제목, 썸네일 문구를 매번 새로 뽑아야 할 때",
            "service_move_ko": "원본에서 쇼츠 후보와 후킹 문구, 자막 초안을 함께 뽑는다",
            "artifact_ko": "쇼츠 후보 5개 + 제목/자막/썸네일 문구",
            "severity": 4,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "portfolio-defense",
            "task_ids": ["directing", "color-grading", "thumbnail"],
            "itch_ko": "내 편집이 단순 컷 노동이 아니라 기획 역량이라는 걸 증명하기 어려움",
            "moment_ko": "단가 협상이나 포트폴리오 설명에서 '왜 내가 필요한지' 말해야 할 때",
            "service_move_ko": "작업물을 기획 의도, 시청 유지, 브랜드 톤 관점으로 재해석한다",
            "artifact_ko": "포트폴리오 케이스 스터디 + 단가 방어 문장",
            "severity": 4,
            "frequency": 3,
            "wtp": "high",
        },
    ],
    "marketer": [
        {
            "pain_id": "weekly-report-story",
            "task_ids": ["report-writing", "campaign-management"],
            "itch_ko": "성과 리포트가 숫자 나열로 끝나고, 왜 올랐는지/떨어졌는지 설명이 안 됨",
            "moment_ko": "월요일 회의 전 GA, 광고관리자, CRM 숫자를 엮어 한 문장으로 말해야 할 때",
            "service_move_ko": "지표 변동을 원인 후보, 다음 실험, 상사용 문장으로 바꾼다",
            "artifact_ko": "주간 성과 해석 + 다음 실험 3개 + 보고서 문장",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "content-variation-fatigue",
            "task_ids": ["content-creation", "market-research"],
            "itch_ko": "한 캠페인을 채널별 카피와 소재로 계속 변형해야 하는 피로",
            "moment_ko": "인스타, 블로그, 문자, 랜딩, 광고 카피를 브랜드 톤 맞춰 동시에 내야 할 때",
            "service_move_ko": "하나의 오퍼를 채널별 목적과 톤에 맞게 변주한다",
            "artifact_ko": "채널별 카피팩 + A/B 테스트 가설",
            "severity": 4,
            "frequency": 5,
            "wtp": "medium",
        },
        {
            "pain_id": "campaign-postmortem",
            "task_ids": ["strategy-planning", "campaign-management"],
            "itch_ko": "캠페인이 실패했을 때 다음 액션보다 책임 설명에 시간을 쓰는 문제",
            "moment_ko": "성과가 낮은 이유를 예산, 타깃, 메시지, 랜딩 중 어디서 찾아야 할지 막힐 때",
            "service_move_ko": "실패 원인 후보를 분해하고 다음 주 실험 우선순위를 정한다",
            "artifact_ko": "캠페인 회고 템플릿 + 우선순위 실험안",
            "severity": 4,
            "frequency": 3,
            "wtp": "high",
        },
    ],
    "sales-rep": [
        {
            "pain_id": "pre-call-brief",
            "task_ids": ["lead-generation", "client-negotiation"],
            "itch_ko": "미팅 전 고객사를 조사하느라 정작 질문 설계 시간이 부족함",
            "moment_ko": "30분 뒤 미팅인데 회사 뉴스, 담당자, 기존 대화, 제안 포인트를 빠르게 알아야 할 때",
            "service_move_ko": "고객사 맥락과 구매 가능성, 질문, 리스크를 한 장으로 압축한다",
            "artifact_ko": "3분 미팅 브리프 + 발견 질문 7개",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "follow-up-drag",
            "task_ids": ["cold-outreach", "relationship-management"],
            "itch_ko": "미팅 후 후속 메일과 CRM 입력이 밀려 딜 모멘텀이 죽는 문제",
            "moment_ko": "통화가 끝났는데 다음 액션, 반대논리, 내부 공유 메모를 바로 써야 할 때",
            "service_move_ko": "미팅 메모를 고객용 후속메일과 내부 CRM 메모로 분리한다",
            "artifact_ko": "후속메일 + CRM 업데이트 + 다음 액션",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "proposal-tailoring",
            "task_ids": ["contract-admin", "client-negotiation"],
            "itch_ko": "제안서가 매번 비슷한데 고객별로 다르게 보이게 고치는 시간",
            "moment_ko": "고객 업종, 예산권자, 반대 논리에 맞춰 한 장을 고쳐야 할 때",
            "service_move_ko": "기존 제안서를 고객 맥락과 의사결정자 언어로 재작성한다",
            "artifact_ko": "고객별 제안서 요약 + 반대논리 대응문",
            "severity": 4,
            "frequency": 4,
            "wtp": "high",
        },
    ],
    "data-analyst": [
        {
            "pain_id": "why-did-it-drop",
            "task_ids": ["writing-queries", "statistical-analysis", "insight-generation"],
            "itch_ko": "'왜 떨어졌어요?' 질문이 오면 데이터 정의부터 다시 파야 하는 고통",
            "moment_ko": "지표 하락 알림 뒤에 세그먼트, 기간, 분모, 이벤트 변경을 빠르게 확인해야 할 때",
            "service_move_ko": "가능한 원인 후보와 검증 SQL을 우선순위로 만든다",
            "artifact_ko": "원인 후보 트리 + SQL 초안 + 이해관계자 설명문",
            "severity": 5,
            "frequency": 4,
            "wtp": "high",
        },
        {
            "pain_id": "metric-definition-fight",
            "task_ids": ["dashboard-creation", "stakeholder-communication"],
            "itch_ko": "팀마다 같은 지표를 다르게 이해해 대시보드 신뢰가 깨짐",
            "moment_ko": "회의에서 '이 숫자 맞아요?' 질문이 반복될 때",
            "service_move_ko": "지표 정의, 제외조건, 분모/분자, 소유자를 문서화한다",
            "artifact_ko": "지표 사전 + 대시보드 주석 + 회의 답변",
            "severity": 5,
            "frequency": 3,
            "wtp": "high",
        },
        {
            "pain_id": "adhoc-sql-queue",
            "task_ids": ["data-cleaning", "writing-queries"],
            "itch_ko": "임시 SQL 요청이 쌓여 분석보다 추출 대행자가 되는 문제",
            "moment_ko": "비슷한 추출 요청을 매번 슬랙으로 받아 새로 짜야 할 때",
            "service_move_ko": "요청을 표준 쿼리 템플릿과 셀프서브 질문으로 바꾼다",
            "artifact_ko": "SQL 템플릿 + 요청 폼 + 반복 요청 자동응답",
            "severity": 4,
            "frequency": 5,
            "wtp": "medium",
        },
    ],
    "accountant": [
        {
            "pain_id": "missing-client-docs",
            "task_ids": ["data-entry", "tax-calculation"],
            "itch_ko": "고객 자료 누락을 계속 추적하고 다시 요청하는 반복",
            "moment_ko": "마감 직전 영수증, 통장, 매출자료가 빠져 있는데 고객은 뭘 내야 하는지 모를 때",
            "service_move_ko": "고객별 누락자료를 자동 체크하고 쉬운 요청문으로 보낸다",
            "artifact_ko": "누락자료 체크리스트 + 고객 안내문",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "month-end-reconciliation",
            "task_ids": ["data-entry", "financial-reporting"],
            "itch_ko": "월말 숫자가 안 맞을 때 원인을 역추적하는 시간",
            "moment_ko": "전표, 계정과목, 증빙, 잔액 차이를 하나씩 대조해야 할 때",
            "service_move_ko": "불일치 후보를 금액/계정/거래처 기준으로 정렬한다",
            "artifact_ko": "불일치 원인 후보표 + 확인 순서",
            "severity": 5,
            "frequency": 4,
            "wtp": "high",
        },
        {
            "pain_id": "tax-change-explain",
            "task_ids": ["tax-calculation", "strategic-advisory"],
            "itch_ko": "세법 변화나 신고 기준을 고객 언어로 설명하는 부담",
            "moment_ko": "고객이 '그래서 제가 뭘 해야 하죠?'라고 물을 때",
            "service_move_ko": "변경사항을 고객 유형별 영향과 액션으로 번역한다",
            "artifact_ko": "고객용 설명문 + 대응 체크리스트",
            "severity": 4,
            "frequency": 3,
            "wtp": "medium",
        },
    ],
    "bookkeeper": [
        {
            "pain_id": "reconciliation-mismatch",
            "task_ids": ["reconciliation", "journal-entry"],
            "itch_ko": "월말에 통장·장부 잔액이 안 맞아 차이를 한 건씩 역추적하는 반복",
            "moment_ko": "마감 직전 계정 잔액이 몇 천 원 단위로 안 맞는데 어느 전표가 원인인지 안 보일 때",
            "service_move_ko": "불일치 후보를 금액·계정·거래처·날짜 기준으로 정렬해 의심 전표를 먼저 보여준다",
            "artifact_ko": "불일치 원인 후보표 + 확인 순서",
            "severity": 5,
            "frequency": 4,
            "wtp": "high",
        },
        {
            "pain_id": "receipt-categorization",
            "task_ids": ["expense-categorization", "journal-entry"],
            "itch_ko": "쌓인 영수증·카드내역을 계정과목으로 일일이 분류해 입력하는 단순반복",
            "moment_ko": "수백 건 경비 증빙을 계정과목·부가세 구분까지 손으로 찍어 넣어야 할 때",
            "service_move_ko": "증빙 항목을 계정과목·부가세 구분 후보로 1차 분류하고 애매한 것만 따로 모은다",
            "artifact_ko": "경비 분류 초안표 + 확인 필요 항목 목록",
            "severity": 4,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "payroll-edge-cases",
            "task_ids": ["payroll", "month-end-close"],
            "itch_ko": "급여·4대보험에서 중도입퇴사·수당 변동 같은 예외를 매달 다시 확인하는 부담",
            "moment_ko": "중도 입퇴사자·비과세 수당·보험요율 변경이 겹쳐 계산이 표준에서 벗어날 때",
            "service_move_ko": "이번 달 예외 케이스만 골라 변경 사유와 확인 포인트를 정리한다",
            "artifact_ko": "급여 예외 케이스 점검표 + 근거 메모",
            "severity": 4,
            "frequency": 3,
            "wtp": "medium",
        },
    ],
    "copywriter": [
        {
            "pain_id": "brand-voice-drift",
            "task_ids": ["brand-messaging", "ad-copy"],
            "itch_ko": "AI로 빨리 뽑은 카피가 브랜드 톤·금지표현을 매번 어긋나 다시 손보는 반복",
            "moment_ko": "초안은 그럴듯한데 브랜드 보이스·법적 금지문구·기존 캠페인 톤과 안 맞아 통째로 고칠 때",
            "service_move_ko": "브랜드 보이스 가이드·금지표현·레퍼런스 카피를 결박해 초안을 톤에 맞게 1차 교정한다",
            "artifact_ko": "브랜드 톤 체크 카피 초안 + 위반 항목 표시",
            "severity": 5,
            "frequency": 4,
            "wtp": "high",
        },
        {
            "pain_id": "variation-volume",
            "task_ids": ["ad-copy", "product-description"],
            "itch_ko": "같은 상품을 채널·타깃·길이별로 수십 개 변형 카피로 찍어내는 단순반복",
            "moment_ko": "A/B 테스트와 채널별 규격 때문에 헤드라인·디스크립션을 수십 버전 써야 할 때",
            "service_move_ko": "핵심 메시지를 채널·길이·타깃 규격에 맞춰 변형안으로 펼치고 중복을 제거한다",
            "artifact_ko": "채널별 카피 변형표 + 규격 점검",
            "severity": 4,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "client-feedback-loop",
            "task_ids": ["client-revision", "brand-messaging"],
            "itch_ko": "'느낌이 좀…' 같은 모호한 피드백을 구체적 수정 방향으로 번역하는 부담",
            "moment_ko": "클라이언트가 추상적으로 반려했는데 무엇을 어떻게 바꿔야 할지 다시 추측해야 할 때",
            "service_move_ko": "모호한 피드백을 수정 가설·확인 질문·대안 카피로 구조화한다",
            "artifact_ko": "피드백 해석표 + 확인 질문 + 대안안",
            "severity": 4,
            "frequency": 3,
            "wtp": "medium",
        },
    ],
    "office-admin": [
        {
            "pain_id": "request-chasing",
            "task_ids": ["internal-communication", "document-formatting"],
            "itch_ko": "여러 부서 요청을 받고 마감까지 계속 재촉해야 하는 일",
            "moment_ko": "문서 취합, 승인, 회신, 자료 제출이 동시에 굴러갈 때",
            "service_move_ko": "요청을 담당자/마감/상태로 정리하고 리마인드 문구를 만든다",
            "artifact_ko": "요청 추적 보드 + 리마인드 메시지",
            "severity": 5,
            "frequency": 5,
            "wtp": "medium",
        },
        {
            "pain_id": "expense-proof-cleanup",
            "task_ids": ["expense-processing"],
            "itch_ko": "영수증과 경비 항목을 다시 맞추는 반복 노동",
            "moment_ko": "누락 영수증, 잘못된 계정, 승인 규칙을 한 번에 확인해야 할 때",
            "service_move_ko": "영수증을 규정 기준으로 분류하고 누락 항목을 표시한다",
            "artifact_ko": "경비 정산 오류 리스트 + 요청문",
            "severity": 4,
            "frequency": 5,
            "wtp": "medium",
        },
        {
            "pain_id": "notice-writing",
            "task_ids": ["internal-communication", "schedule-management"],
            "itch_ko": "사내 공지를 매번 오해 없이 짧게 쓰는 부담",
            "moment_ko": "휴무, 교육, 회의, 제출 요청을 부서별로 다르게 알려야 할 때",
            "service_move_ko": "공지 목적과 대상에 맞춰 톤과 액션을 정리한다",
            "artifact_ko": "사내공지 초안 + FAQ 5개",
            "severity": 3,
            "frequency": 4,
            "wtp": "low",
        },
    ],
    "call-center-agent": [
        {
            "pain_id": "after-call-work",
            "task_ids": ["data-entry", "issue-escalation"],
            "itch_ko": "상담 후 기록 때문에 다음 콜 전 숨 돌릴 시간이 없음",
            "moment_ko": "통화 요약, 처리결과, 이관 사유, 고객 감정을 짧게 남겨야 할 때",
            "service_move_ko": "상담 내용을 표준 항목으로 요약하고 이관 메모를 만든다",
            "artifact_ko": "상담 요약 + 이관 메모 + 후속조치",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "angry-customer-script",
            "task_ids": ["empathetic-complaint-handling", "simple-inquiry-response"],
            "itch_ko": "불만 고객에게 공감은 해야 하지만 보상/정책 선을 넘으면 안 되는 긴장",
            "moment_ko": "고객 감정이 격해졌고, 정책상 가능한 답변을 즉시 골라야 할 때",
            "service_move_ko": "상황별 공감 문장과 정책 범위 내 답변을 제안한다",
            "artifact_ko": "공감 응대 스크립트 + 금지 표현",
            "severity": 5,
            "frequency": 4,
            "wtp": "high",
        },
        {
            "pain_id": "knowledge-hunt",
            "task_ids": ["simple-inquiry-response", "issue-escalation"],
            "itch_ko": "정답은 어딘가에 있는데 고객 대기 중에 찾기 어려움",
            "moment_ko": "FAQ, 정책, 공지, 이전 티켓 중 어떤 답이 최신인지 모를 때",
            "service_move_ko": "질문을 내부 지식베이스 검색어와 답변 후보로 바꾼다",
            "artifact_ko": "답변 후보 + 근거 문서 링크 + 이관 기준",
            "severity": 4,
            "frequency": 5,
            "wtp": "medium",
        },
    ],
    "teacher": [
        {
            "pain_id": "differentiated-materials",
            "task_ids": ["lesson-planning", "grading"],
            "itch_ko": "한 수업을 수준별 자료와 과제로 다시 쪼개는 시간",
            "moment_ko": "같은 단원인데 상/중/하 학생에게 다른 활동과 피드백이 필요할 때",
            "service_move_ko": "수업 목표를 수준별 활동, 예시, 평가 기준으로 변환한다",
            "artifact_ko": "수준별 활동지 + 채점 루브릭",
            "severity": 5,
            "frequency": 4,
            "wtp": "medium",
        },
        {
            "pain_id": "parent-message",
            "task_ids": ["parent-communication", "student-counseling"],
            "itch_ko": "학부모에게 민감한 내용을 오해 없이 쓰는 부담",
            "moment_ko": "학생 행동, 과제 미제출, 상담 필요를 단정 없이 전달해야 할 때",
            "service_move_ko": "관찰 사실, 협조 요청, 다음 행동을 차분한 문장으로 정리한다",
            "artifact_ko": "학부모 메시지 초안 + 상담 질문",
            "severity": 5,
            "frequency": 3,
            "wtp": "medium",
        },
        {
            "pain_id": "admin-paperwork",
            "task_ids": ["administrative-duties", "lesson-planning"],
            "itch_ko": "수업 외 행정 문서가 수업 준비 시간을 잠식함",
            "moment_ko": "계획서, 결과보고, 안내문을 같은 내용으로 여러 양식에 맞춰야 할 때",
            "service_move_ko": "핵심 내용을 학교 양식별 문장으로 변환한다",
            "artifact_ko": "행정문서 초안 + 제출 체크리스트",
            "severity": 4,
            "frequency": 4,
            "wtp": "low",
        },
    ],
    "nurse": [
        {
            "pain_id": "handoff-compression",
            "task_ids": ["medical-communication", "charting-documentation", "patient-monitoring"],
            "itch_ko": "인수인계 때 중요한 변화만 빠뜨리지 않고 압축해야 하는 부담",
            "moment_ko": "바쁜 교대 시간에 상태 변화, 처치, 주의사항을 짧게 전달해야 할 때",
            "service_move_ko": "기록을 SBAR 형태의 인수인계 초안으로 정리한다",
            "artifact_ko": "SBAR 인수인계 요약 + 확인 질문",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "charting-fatigue",
            "task_ids": ["charting-documentation", "patient-monitoring"],
            "itch_ko": "반복 차팅이 환자 케어 시간을 갉아먹는 문제",
            "moment_ko": "관찰, 처치, 반응을 빠짐없이 기록해야 하지만 시간이 부족할 때",
            "service_move_ko": "메모를 표준 차팅 문장 초안으로 바꾼다",
            "artifact_ko": "차팅 문장 초안 + 누락 확인 리스트",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "guardian-explain",
            "task_ids": ["emotional-support", "medical-communication"],
            "itch_ko": "보호자에게 설명은 해야 하지만 진료 판단처럼 들리면 안 되는 긴장",
            "moment_ko": "불안한 보호자에게 현재 절차와 확인할 사항을 쉽게 말해야 할 때",
            "service_move_ko": "의료 판단을 배제하고 절차/관찰/문의 경로를 설명하는 문장을 만든다",
            "artifact_ko": "보호자 설명문 + 의료진 문의 체크리스트",
            "severity": 4,
            "frequency": 3,
            "wtp": "medium",
        },
    ],
    "translator": [
        {
            "pain_id": "mtpe-quality-trap",
            "task_ids": ["draft-translation", "proofreading-editing"],
            "itch_ko": "AI 초벌번역이 그럴듯해서 오히려 오류를 더 세밀하게 봐야 하는 피로",
            "moment_ko": "문장은 자연스러운데 의미, 뉘앙스, 숫자, 고유명사가 틀렸을 수 있을 때",
            "service_move_ko": "원문-번역문을 위험 유형별로 대조하고 QA 포인트를 표시한다",
            "artifact_ko": "번역 QA 리포트 + 수정 우선순위",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "terminology-consistency",
            "task_ids": ["terminology-management", "proofreading-editing"],
            "itch_ko": "용어 일관성이 무너지면 품질 전체가 낮아 보이는 문제",
            "moment_ko": "긴 문서나 여러 번역자가 작업한 파일에서 같은 용어가 다르게 번역될 때",
            "service_move_ko": "용어 후보를 추출하고 문서 내 일관성 위반을 찾는다",
            "artifact_ko": "프로젝트 용어집 + 불일치 리스트",
            "severity": 4,
            "frequency": 5,
            "wtp": "medium",
        },
        {
            "pain_id": "value-defense",
            "task_ids": ["cultural-localization", "client-communication"],
            "itch_ko": "클라이언트가 'AI로 되잖아요'라고 단가를 낮추려는 상황",
            "moment_ko": "사람 번역이 필요한 이유를 품질, 리스크, 현지화 관점으로 설명해야 할 때",
            "service_move_ko": "AI 초벌과 인간 현지화의 차이를 샘플 기반으로 보여준다",
            "artifact_ko": "품질 비교표 + 단가 방어 문장",
            "severity": 5,
            "frequency": 3,
            "wtp": "high",
        },
    ],
    "graphic-designer": [
        {
            "pain_id": "vague-brief",
            "task_ids": ["creative-concept", "client-communication"],
            "itch_ko": "브리프가 애매한데 결과물 책임은 디자이너가 지는 상황",
            "moment_ko": "'세련되게', '힙하게' 같은 말만 있고 타깃, 톤, 금지사항이 없을 때",
            "service_move_ko": "애매한 요청을 질문, 레퍼런스 기준, 의사결정 항목으로 바꾼다",
            "artifact_ko": "브리프 정리표 + 클라이언트 확인 질문",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "revision-boundary",
            "task_ids": ["layout-design", "client-communication"],
            "itch_ko": "수정 요청이 계속 늘어나는데 범위가 흐려지는 문제",
            "moment_ko": "색, 문구, 레이아웃, 새 시안 요청이 섞여 기존 계약 범위를 넘을 때",
            "service_move_ko": "수정 요청을 범위 내/범위 외로 분류하고 회신 문장을 만든다",
            "artifact_ko": "수정 범위표 + 정중한 추가비 안내문",
            "severity": 5,
            "frequency": 4,
            "wtp": "high",
        },
        {
            "pain_id": "format-export",
            "task_ids": ["file-formatting", "image-generation"],
            "itch_ko": "플랫폼별 사이즈, 포맷, 용량 맞추기에 시간이 새는 문제",
            "moment_ko": "같은 디자인을 인스타, 상세페이지, 배너, 인쇄용으로 다시 뽑아야 할 때",
            "service_move_ko": "납품처별 규격과 파일명을 체크리스트로 관리한다",
            "artifact_ko": "출력 규격표 + 납품 체크리스트",
            "severity": 3,
            "frequency": 5,
            "wtp": "medium",
        },
    ],
    "hr-manager": [
        {
            "pain_id": "resume-screening-rationale",
            "task_ids": ["resume-screening", "interviewing"],
            "itch_ko": "이력서 선별은 빨리 해야 하지만 왜 통과/탈락인지 근거가 남아야 함",
            "moment_ko": "지원자가 많고 JD 기준에 맞는 후보를 짧은 시간에 정리해야 할 때",
            "service_move_ko": "JD 기준으로 후보 강점/리스크를 요약하되 자동 탈락 판정은 하지 않는다",
            "artifact_ko": "후보자 요약표 + 면접 확인 질문",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "interview-consistency",
            "task_ids": ["interviewing", "hr-strategy"],
            "itch_ko": "면접관마다 질문과 평가 기준이 달라 비교가 어려움",
            "moment_ko": "여러 면접관의 평가를 같은 기준으로 모아야 할 때",
            "service_move_ko": "직무 역량별 질문, 루브릭, 평가 메모 구조를 맞춘다",
            "artifact_ko": "면접 질문지 + 평가 루브릭",
            "severity": 4,
            "frequency": 4,
            "wtp": "medium",
        },
        {
            "pain_id": "onboarding-repeat",
            "task_ids": ["onboarding-training", "payroll-processing"],
            "itch_ko": "신규 입사자에게 같은 절차와 질문을 반복 설명하는 일",
            "moment_ko": "입사 서류, 근태, 장비, 계정, 복지 질문이 계속 들어올 때",
            "service_move_ko": "입사자 유형별 체크리스트와 FAQ를 만든다",
            "artifact_ko": "온보딩 체크리스트 + FAQ",
            "severity": 4,
            "frequency": 3,
            "wtp": "medium",
        },
    ],
    "journalist": [
        {
            "pain_id": "press-release-triage",
            "task_ids": ["press-release-rewriting", "article-writing"],
            "itch_ko": "보도자료는 많지만 기사 가치가 있는지 빠르게 걸러야 함",
            "moment_ko": "수십 개 자료 중 새로움, 이해관계자, 검증 필요 지점을 골라야 할 때",
            "service_move_ko": "보도자료를 뉴스가치, 확인 질문, 이해관계자로 분류한다",
            "artifact_ko": "보도자료 선별표 + 추가취재 질문",
            "severity": 5,
            "frequency": 5,
            "wtp": "medium",
        },
        {
            "pain_id": "fact-check-pack",
            "task_ids": ["investigative-reporting", "data-journalism"],
            "itch_ko": "기사 초안보다 팩트체크와 반론 확인이 더 오래 걸림",
            "moment_ko": "숫자, 인용, 주장, 이해관계자 반론을 빠짐없이 확인해야 할 때",
            "service_move_ko": "초안에서 검증 필요한 문장과 확인 출처를 뽑는다",
            "artifact_ko": "팩트체크 체크리스트 + 반론 요청문",
            "severity": 5,
            "frequency": 4,
            "wtp": "high",
        },
        {
            "pain_id": "interview-questions",
            "task_ids": ["interviewing", "investigative-reporting"],
            "itch_ko": "짧은 인터뷰 시간에 핵심 질문을 못 던질까 봐 생기는 압박",
            "moment_ko": "취재원 배경과 쟁점을 읽고 질문 흐름을 빨리 만들어야 할 때",
            "service_move_ko": "취재 목적별 질문 순서와 후속 질문을 설계한다",
            "artifact_ko": "인터뷰 질문지 + 회피 답변 후속 질문",
            "severity": 4,
            "frequency": 4,
            "wtp": "medium",
        },
    ],
    "paralegal": [
        {
            "pain_id": "case-timeline",
            "task_ids": ["document-review", "client-intake"],
            "itch_ko": "사건 자료가 흩어져 사실관계 타임라인을 다시 세우는 시간",
            "moment_ko": "계약서, 문자, 메일, 영수증, 진술이 섞여 날짜순 정리가 필요할 때",
            "service_move_ko": "자료를 날짜, 당사자, 쟁점, 증거로 구조화한다",
            "artifact_ko": "사건 타임라인 + 증거목록",
            "severity": 5,
            "frequency": 5,
            "wtp": "high",
        },
        {
            "pain_id": "filing-checklist",
            "task_ids": ["court-filing", "drafting-contracts"],
            "itch_ko": "제출 서류 하나 빠지면 일정이 밀리는 행정 리스크",
            "moment_ko": "법원/기관별 양식, 첨부, 기한, 제출 방식을 확인해야 할 때",
            "service_move_ko": "사건 유형별 제출 체크리스트와 누락 항목을 만든다",
            "artifact_ko": "제출서류 체크리스트 + 마감 알림",
            "severity": 5,
            "frequency": 4,
            "wtp": "high",
        },
        {
            "pain_id": "precedent-search-brief",
            "task_ids": ["case-research", "document-review"],
            "itch_ko": "판례 검색 결과는 많은데 사건에 맞는 논점을 추리는 데 시간이 듦",
            "moment_ko": "키워드 검색 후 유사/차이점과 인용 가능성을 정리해야 할 때",
            "service_move_ko": "후보 판례를 쟁점, 유사점, 주의점으로 요약한다",
            "artifact_ko": "판례 후보 브리프 + 검토 질문",
            "severity": 4,
            "frequency": 4,
            "wtp": "medium",
        },
    ],
}


def _task_lookup(job_result: dict) -> dict[str, dict]:
    return {t.get("task_id"): t for t in job_result.get("tasks", []) if t.get("task_id")}


def _pain_score(pain: dict, tasks: dict[str, dict]) -> float:
    task_ids = pain.get("task_ids") or []
    task_pressure = max((float(tasks.get(tid, {}).get("index", 0)) for tid in task_ids), default=0.0)
    return (
        float(pain.get("severity", 0)) * 2.0
        + float(pain.get("frequency", 0)) * 1.5
        + _WTP_SCORE.get(pain.get("wtp"), 0.0)
        + task_pressure / 25.0
    )


def build(job_result: dict, limit: int = 3) -> dict:
    """현재 직무 리포트에 붙일 상위 가려움 카드.

    점수는 제품 우선순위 정렬용 내부값이다. 사용자에게는 "가설"로만 보여준다.
    """
    jid = job_result.get("job_id", "")
    tasks = _task_lookup(job_result)
    cards = []
    for pain in PAIN_MAP.get(jid, []):
        row = deepcopy(pain)
        row["task_names_ko"] = [
            tasks[tid]["name_ko"] for tid in row.get("task_ids", []) if tid in tasks
        ]
        row["priority_score"] = round(_pain_score(row, tasks), 2)
        cards.append(row)
    cards.sort(key=lambda p: (-p["priority_score"], p["pain_id"]))
    return {
        "job_id": jid,
        "label_ko": "제품 가설",
        "note_ko": "실제 사용자 인터뷰 전 가설입니다. 유료 판단 근거가 아니라 문제 발견용입니다.",
        "pains": cards[:max(0, int(limit))],
    }


def get(job_result: dict, pain_id: str) -> dict | None:
    """직무 결과 기준 pain_id 1건 조회. task_names_ko/priority_score 포함."""
    pm = build(job_result, limit=99)
    for pain in pm["pains"]:
        if pain.get("pain_id") == pain_id:
            return pain
    return None


def validate_against_jobs(jobs: dict) -> list[str]:
    """테스트/감사용 스키마 검증. jobs는 ScoringEngine.jobs."""
    errors: list[str] = []
    for jid, pains in PAIN_MAP.items():
        if jid not in jobs:
            errors.append(f"{jid}: unknown job_id")
            continue
        task_ids = {t.get("task_id") for t in jobs[jid].get("tasks", [])}
        seen = set()
        for i, pain in enumerate(pains):
            loc = f"{jid}[{i}]"
            if pain.get("pain_id") in seen:
                errors.append(f"{loc}: duplicate pain_id")
            seen.add(pain.get("pain_id"))
            for key in ("itch_ko", "moment_ko", "service_move_ko", "artifact_ko"):
                if not str(pain.get(key, "")).strip():
                    errors.append(f"{loc}: missing {key}")
            if pain.get("wtp") not in _WTP_SCORE:
                errors.append(f"{loc}: invalid wtp")
            if not (1 <= int(pain.get("severity", 0)) <= 5):
                errors.append(f"{loc}: invalid severity")
            if not (1 <= int(pain.get("frequency", 0)) <= 5):
                errors.append(f"{loc}: invalid frequency")
            missing = [tid for tid in pain.get("task_ids", []) if tid not in task_ids]
            if missing:
                errors.append(f"{loc}: unknown task_ids {missing}")
    missing_jobs = set(jobs) - set(PAIN_MAP)
    for jid in sorted(missing_jobs):
        errors.append(f"{jid}: missing pain map")
    return errors
