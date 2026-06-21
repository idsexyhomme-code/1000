"""
커리어 시그널 — 직업별 대표 pain 심층 아틀라스.

painmap.py가 "어떤 업무 고통인가"를 정의한다면, 이 모듈은 그 고통이 실제 근무 중
언제 터지고, 왜 돈을 내고라도 줄이고 싶은지, 첫 파일럿이 무엇을 약속해야 하는지를 정의한다.

중요: 인터뷰 전 제품 가설이다. 자동 전문 판단이나 성과 보장이 아니라, 컨시어지 파일럿의
초기 질문/오퍼/이행 범위를 좁히기 위한 운영 데이터로만 사용한다.
"""
from __future__ import annotations

import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import painmap
from scoring import ScoringEngine


REQUIRED_KEYS = (
    "burning_moment_ko",
    "hidden_cost_ko",
    "bad_ai_trap_ko",
    "minimum_inputs_ko",
    "first_relief_ko",
    "paid_trigger_ko",
    "pilot_script_ko",
    "success_metric_ko",
    "human_boundary_ko",
)


DEEP_ATLAS: dict[tuple[str, str], dict] = {
    ("junior-developer", "unknown-codebase-context"): {
        "burning_moment_ko": "티켓은 작아 보이는데 관련 파일을 따라가다 반나절이 사라지고, 리뷰어에게 '이 영향도 봤나요?'를 들을까 봐 멈칫하는 순간",
        "hidden_cost_ko": "코딩 시간이 아니라 맥락 탐색 시간이 성과를 잡아먹고, 신입/주니어라는 불안이 PR 품질 불안으로 전환된다.",
        "bad_ai_trap_ko": "레포 전체 구조, 기존 테스트 관례, 사이드이펙트는 일반 프롬프트만으로 잡히지 않는다.",
        "minimum_inputs_ko": ["이슈/티켓 본문", "관련 에러 로그 또는 재현 절차", "레포 구조/파일 목록", "기존 테스트 명령"],
        "first_relief_ko": "10분 안에 '먼저 볼 파일 5개, 건드리면 위험한 경계, 확인할 테스트'가 한 장으로 나온다.",
        "paid_trigger_ko": "첫 회사/새 팀 투입, 온콜 버그, 레거시 코드 수정처럼 실수 비용이 평판으로 이어질 때",
        "pilot_script_ko": "처음 보는 코드에서 수정 후보 파일과 검증 명령까지 잡아주는 PR 전 맥락 정리 파일럿",
        "success_metric_ko": "수정 시작 전 탐색 시간 30분 이상 절감, PR 설명문에 영향 범위/테스트 근거 포함",
        "human_boundary_ko": "실제 코드를 자동 병합하지 않고, 운영자가 수정 후보와 검증 범위만 정리한다.",
    },
    ("video-editor", "revision-chaos"): {
        "burning_moment_ko": "카톡, 메일, 유튜브 댓글, 프레임 캡처로 온 수정 요청을 타임라인에 다시 꽂느라 편집 시간이 아니라 정리 시간이 늘어나는 순간",
        "hidden_cost_ko": "누락 수정은 재작업과 신뢰 하락으로 이어지고, 범위 밖 요청을 제때 분리하지 못하면 추가비를 받기 어렵다.",
        "bad_ai_trap_ko": "일반 AI는 요청 문장을 예쁘게 정리하지만 타임코드, 버전, 작업 유형, 범위 외 요청을 납품 단위로 묶어주지 못한다.",
        "minimum_inputs_ko": ["수정 요청 원문", "영상 러닝타임/버전명", "계약상 수정 범위", "납품 마감"],
        "first_relief_ko": "10분 안에 타임코드별 체크리스트와 클라이언트에게 보낼 확인 문장이 생긴다.",
        "paid_trigger_ko": "최종본 직전 수정이 한꺼번에 들어오거나, 추가비를 말해야 하는데 관계가 껄끄러울 때",
        "pilot_script_ko": "흩어진 영상 수정 요청을 타임코드 체크리스트와 정중한 회신문으로 바꾸는 파일럿",
        "success_metric_ko": "수정사항 누락 0건, 클라이언트 확인 왕복 1회 이상 감소, 범위 외 요청 분리",
        "human_boundary_ko": "영상 자체를 자동 편집하지 않고, 요청 정리와 커뮤니케이션 초안만 제공한다.",
    },
    ("marketer", "weekly-report-story"): {
        "burning_moment_ko": "월요일 회의 전 숫자는 있는데 '그래서 왜 올랐고 다음에 뭘 할 건데?'라는 한 문장이 비어 있는 순간",
        "hidden_cost_ko": "성과 해석이 약하면 마케터가 실행자가 아니라 보고서 작성자로 보이고, 다음 예산/실험 승인도 느려진다.",
        "bad_ai_trap_ko": "AI는 그럴듯한 원인을 말하지만 실제 지표 정의, 채널 믹스, 기간 효과, 랜딩 변경을 검증 순서로 묶어야 한다.",
        "minimum_inputs_ko": ["주요 지표 캡처/CSV", "전주 대비 변화", "집행한 캠페인/소재", "이번 주 의사결정 질문"],
        "first_relief_ko": "10분 안에 하락/상승 원인 후보 3개와 회의에서 말할 보고 문장이 생긴다.",
        "paid_trigger_ko": "성과가 떨어졌거나 예산을 더 받아야 하는 주간 회의 직전",
        "pilot_script_ko": "숫자 나열 리포트를 원인 가설과 다음 실험으로 바꾸는 주간 마케팅 해석 파일럿",
        "success_metric_ko": "회의용 핵심 문장 3개 확보, 다음 실험 우선순위 3개 합의, 보고서 작성 시간 절감",
        "human_boundary_ko": "광고 성과를 보장하지 않고, 운영자가 데이터 해석 후보와 실험 설계 초안만 만든다.",
    },
    ("sales-rep", "pre-call-brief"): {
        "burning_moment_ko": "미팅 30분 전 회사 뉴스와 기존 대화를 뒤지다 질문 설계 없이 콜에 들어가게 되는 순간",
        "hidden_cost_ko": "맥락 없는 질문은 고객 신뢰를 깎고, 발견 질문을 놓치면 딜이 가격 논의로만 흘러간다.",
        "bad_ai_trap_ko": "웹 검색 요약만으로는 구매 시그널, 반대논리, 이전 대화 맥락, 오늘 반드시 물어볼 질문이 분리되지 않는다.",
        "minimum_inputs_ko": ["고객사명/담당자", "미팅 목적", "이전 통화 메모", "제안 제품/가격대"],
        "first_relief_ko": "10분 안에 고객 맥락, 발견 질문, 예상 반대논리, 다음 액션 후보가 한 장으로 나온다.",
        "paid_trigger_ko": "중요 계정 첫 미팅, 의사결정자 참석, 갱신/업셀 미팅처럼 한 번의 콜 가치가 클 때",
        "pilot_script_ko": "영업 미팅 직전 고객 맥락과 질문을 한 장으로 압축하는 3분 브리프 파일럿",
        "success_metric_ko": "미팅 전 준비 시간 20분 이상 절감, 발견 질문 5개 이상 사용, 후속 액션 명확화",
        "human_boundary_ko": "고객 개인정보를 최소화하고, 운영자가 공개/제공 자료 기반 브리프만 작성한다.",
    },
    ("data-analyst", "why-did-it-drop"): {
        "burning_moment_ko": "슬랙에 '이 지표 왜 떨어졌어요?'가 올라왔는데, 정의/분모/이벤트 변경부터 다시 확인해야 하는 순간",
        "hidden_cost_ko": "분석가가 답변 병목이 되고, 검증 없는 해석을 내면 대시보드 신뢰가 한 번에 무너진다.",
        "bad_ai_trap_ko": "AI는 원인을 추측하지만 실제 테이블, 기간, 세그먼트, 이벤트 배포 이력을 검증 SQL로 연결해야 한다.",
        "minimum_inputs_ko": ["지표 정의", "하락 기간과 비교 기간", "관련 테이블/컬럼 설명", "최근 제품/트래킹 변경"],
        "first_relief_ko": "10분 안에 원인 후보 트리와 우선 실행할 SQL 초안이 나온다.",
        "paid_trigger_ko": "임원/리드가 기다리는 지표 하락 설명, 주간 리뷰 직전, 장애인지 성장 둔화인지 구분해야 할 때",
        "pilot_script_ko": "지표 하락 질문을 원인 후보 트리와 검증 SQL로 바꾸는 분석 응급 파일럿",
        "success_metric_ko": "첫 응답까지 시간 단축, 검증 SQL 3개 이상 확보, 이해관계자 설명문 작성",
        "human_boundary_ko": "실데이터 접속 없이 사용자가 제공한 스키마/샘플 기준으로 SQL 초안과 해석 후보만 만든다.",
    },
    ("accountant", "missing-client-docs"): {
        "burning_moment_ko": "마감이 가까운데 고객은 무엇이 빠졌는지 모르고, 담당자는 같은 자료 요청을 여러 번 보내는 순간",
        "hidden_cost_ko": "누락 자료 추적은 청구하기 어려운 시간이지만 신고 지연, 오류, 고객 불만으로 바로 이어진다.",
        "bad_ai_trap_ko": "일반 AI 문장 생성만으로는 고객별 누락 항목, 제출 양식, 쉬운 요청문, 재촉 톤을 함께 관리하기 어렵다.",
        "minimum_inputs_ko": ["고객 유형", "필요 자료 목록", "현재 받은 자료", "마감일/제출 채널"],
        "first_relief_ko": "10분 안에 누락자료 표와 고객에게 그대로 보낼 요청문이 나온다.",
        "paid_trigger_ko": "부가세/종소세/월마감 직전처럼 반복 요청이 폭증하고 실수 비용이 커질 때",
        "pilot_script_ko": "고객별 누락자료를 쉬운 안내문과 재촉 메시지로 바꾸는 마감 전 정리 파일럿",
        "success_metric_ko": "고객 재질문 감소, 누락 항목 한눈에 확인, 요청 메시지 작성 시간 절감",
        "human_boundary_ko": "세무 판단을 자동화하지 않고, 제출자료 정리와 고객 커뮤니케이션 초안만 제공한다.",
    },
    ("office-admin", "request-chasing"): {
        "burning_moment_ko": "여러 부서에서 온 요청의 담당자, 마감, 승인 상태가 섞여 결국 총무가 사람을 계속 쫓아다니는 순간",
        "hidden_cost_ko": "일정 지연 책임은 흐려지고, 반복 리마인드 때문에 감정 노동이 커진다.",
        "bad_ai_trap_ko": "AI가 공지 문장은 써도 요청 상태, 누락 담당자, 다음 리마인드 타이밍까지 운영 보드로 만들지는 않는다.",
        "minimum_inputs_ko": ["요청 원문", "담당자/부서", "마감일", "현재 상태/승인자"],
        "first_relief_ko": "10분 안에 요청 추적표와 담당자별 리마인드 문장이 생긴다.",
        "paid_trigger_ko": "행사/감사/월마감처럼 여러 부서 취합이 동시에 몰릴 때",
        "pilot_script_ko": "흩어진 사내 요청을 담당자·마감·상태 보드와 리마인드 문장으로 바꾸는 파일럿",
        "success_metric_ko": "누락 담당자 즉시 파악, 리마인드 작성 시간 절감, 마감 전 미회신 항목 감소",
        "human_boundary_ko": "사내 의사결정을 대신하지 않고, 운영자가 상태 정리와 문장 초안만 만든다.",
    },
    ("call-center-agent", "after-call-work"): {
        "burning_moment_ko": "통화가 끝나자마자 다음 콜이 들어오는데 처리결과, 감정 상태, 이관 사유를 짧게 남겨야 하는 순간",
        "hidden_cost_ko": "후처리가 늦으면 대기열이 밀리고, 기록이 부실하면 다음 상담자가 같은 질문을 반복한다.",
        "bad_ai_trap_ko": "녹취 요약만으로는 회사의 처리 코드, 이관 기준, 금지 표현, 후속조치 문장이 맞지 않을 수 있다.",
        "minimum_inputs_ko": ["상담 메모/요약", "처리 정책", "이관 기준", "사용 중인 상담 기록 항목"],
        "first_relief_ko": "10분 안에 상담 요약, 이관 메모, 후속조치 등록 문장이 항목별로 나온다.",
        "paid_trigger_ko": "콜량이 많아 후처리가 밀리거나 신입 상담사의 기록 품질을 맞춰야 할 때",
        "pilot_script_ko": "상담 후 기록을 표준 항목과 이관 메모로 압축하는 후처리 파일럿",
        "success_metric_ko": "후처리 시간 단축, 이관 사유 누락 감소, 다음 상담자 이해도 향상",
        "human_boundary_ko": "고객 보상/정책 판단을 대신하지 않고, 제공된 정책 범위 안에서 기록 초안만 만든다.",
    },
    ("teacher", "differentiated-materials"): {
        "burning_moment_ko": "같은 수업을 하는데 학생 수준 차이 때문에 활동지, 예시, 피드백을 다시 세 갈래로 나눠야 하는 순간",
        "hidden_cost_ko": "개별화 자료를 못 만들면 수업 중 일부 학생은 방치되고, 만들면 퇴근 후 준비 시간이 늘어난다.",
        "bad_ai_trap_ko": "AI가 활동지를 만들 수는 있지만 성취기준, 현재 단원, 난이도, 채점 기준과 맞아야 실제 수업에서 쓸 수 있다.",
        "minimum_inputs_ko": ["학년/과목/단원", "수업 목표", "학생 수준 구분", "기존 활동지 또는 교재 범위"],
        "first_relief_ko": "10분 안에 상·중·하 활동 방향과 채점 루브릭 초안이 생긴다.",
        "paid_trigger_ko": "공개수업, 평가 전 보충, 수준 차가 큰 반의 다음 수업 준비 직전",
        "pilot_script_ko": "한 수업을 수준별 활동지와 채점 루브릭으로 쪼개는 수업 준비 파일럿",
        "success_metric_ko": "수준별 자료 3종 확보, 채점 기준 명확화, 수업 준비 시간 절감",
        "human_boundary_ko": "교육적 최종 판단은 교사가 하며, 운영자는 자료 초안과 루브릭 구조만 만든다.",
    },
    ("nurse", "charting-fatigue"): {
        "burning_moment_ko": "처치와 관찰은 계속 쌓이는데 차팅 문장을 빠짐없이 남겨야 해서 환자 케어 시간이 줄어드는 순간",
        "hidden_cost_ko": "기록 누락은 인수인계 오류와 책임 리스크로 이어지지만, 반복 문장 작성은 높은 피로를 만든다.",
        "bad_ai_trap_ko": "의료 판단처럼 보이는 문장을 만들면 위험하고, 실제로는 관찰 사실과 처치 반응을 중립적으로 정리해야 한다.",
        "minimum_inputs_ko": ["관찰 메모", "처치/투약 사실", "환자 반응", "병동 기록 양식"],
        "first_relief_ko": "10분 안에 중립적 차팅 문장 초안과 누락 확인 리스트가 나온다.",
        "paid_trigger_ko": "교대 전 기록이 밀렸거나 신규 간호사의 기록 문장 품질을 맞춰야 할 때",
        "pilot_script_ko": "짧은 메모를 표준 차팅 문장과 누락 확인 리스트로 바꾸는 기록 보조 파일럿",
        "success_metric_ko": "차팅 초안 작성 시간 절감, 누락 항목 확인, 인수인계용 문장 일관성 향상",
        "human_boundary_ko": "진단/처방/의료 판단은 하지 않고, 사용자가 제공한 관찰 사실의 기록 문장 초안만 만든다.",
    },
    ("translator", "mtpe-quality-trap"): {
        "burning_moment_ko": "AI 초벌번역이 자연스러워 보여서 오히려 의미 왜곡, 숫자, 고유명사 오류를 더 의심해야 하는 순간",
        "hidden_cost_ko": "번역가는 더 싸게 요구받지만 QA 책임은 커지고, 보이지 않는 검수 시간이 단가를 갉아먹는다.",
        "bad_ai_trap_ko": "AI가 자기 번역의 의미 오류를 안정적으로 찾지 못하므로 원문-번역문 대조 기준과 위험 유형 분리가 필요하다.",
        "minimum_inputs_ko": ["원문", "AI 초벌번역", "용어집/스타일가이드", "문서 목적/독자"],
        "first_relief_ko": "10분 안에 위험 문장, 용어 불일치, 숫자/고유명사 확인 리스트가 나온다.",
        "paid_trigger_ko": "납품 전 QA, MTPE 단가 방어, 여러 명이 작업한 긴 문서 검수 때",
        "pilot_script_ko": "AI 초벌번역의 그럴듯한 오류를 위험 유형별 QA 리포트로 잡아내는 파일럿",
        "success_metric_ko": "우선 수정 문장 식별, 용어 불일치 감소, 클라이언트 설명 가능한 QA 근거 확보",
        "human_boundary_ko": "최종 번역 품질 판단은 번역가가 하며, 운영자는 대조 리포트와 우선순위만 제공한다.",
    },
    ("graphic-designer", "revision-boundary"): {
        "burning_moment_ko": "색만 바꿔달라던 수정이 새 시안, 문구 변경, 레이아웃 재작업으로 번지는데 어디까지 무료 수정인지 흐려지는 순간",
        "hidden_cost_ko": "범위를 늦게 말할수록 추가비를 받기 어렵고, 감정 상하지 않게 말하는 데 에너지가 든다.",
        "bad_ai_trap_ko": "AI는 정중한 답장을 쓸 수 있지만 요청을 계약 범위, 추가 작업, 확인 필요 항목으로 분류해야 돈이 된다.",
        "minimum_inputs_ko": ["계약/견적 범위", "수정 요청 원문", "기존 시안 수", "납품 일정"],
        "first_relief_ko": "10분 안에 범위 내/외 수정표와 추가비 안내 문장이 생긴다.",
        "paid_trigger_ko": "최종 납품 전 수정이 늘거나, 클라이언트 관계를 해치지 않고 추가비를 말해야 할 때",
        "pilot_script_ko": "디자인 수정 요청을 범위표와 정중한 추가비 안내문으로 바꾸는 파일럿",
        "success_metric_ko": "범위 외 요청 분리, 추가비 논의 시작, 수정 왕복 횟수 감소",
        "human_boundary_ko": "법적 계약 판단을 대신하지 않고, 제공된 견적/계약 범위 기준으로 커뮤니케이션 초안만 만든다.",
    },
    ("hr-manager", "resume-screening-rationale"): {
        "burning_moment_ko": "지원자는 많고 빨리 걸러야 하지만, 왜 통과/보류인지 JD 기준 근거를 남겨야 하는 순간",
        "hidden_cost_ko": "근거 없는 선별은 면접 품질과 공정성 리스크를 만들고, 채용 담당자는 반복 요약에 시간을 잃는다.",
        "bad_ai_trap_ko": "AI 자동 탈락은 위험하고, 실제로는 JD 기준에 맞춘 요약과 면접에서 확인할 질문이 필요하다.",
        "minimum_inputs_ko": ["JD/필수요건", "이력서/경력기술서", "우대요건", "채용 단계/평가기준"],
        "first_relief_ko": "10분 안에 후보자 강점/리스크 요약과 면접 확인 질문이 나온다.",
        "paid_trigger_ko": "지원자가 몰린 포지션, 채용 일정 압박, 면접관에게 후보 요약을 넘겨야 할 때",
        "pilot_script_ko": "이력서 선별을 자동 판정이 아닌 후보자 요약표와 면접 질문으로 바꾸는 파일럿",
        "success_metric_ko": "후보 요약 시간 절감, 면접 질문 일관성 확보, 통과/보류 근거 기록",
        "human_boundary_ko": "합격/탈락을 자동 결정하지 않고, 운영자가 JD 기준 요약과 확인 질문만 만든다.",
    },
    ("journalist", "press-release-triage"): {
        "burning_moment_ko": "메일함에는 보도자료가 쌓이는데 새로움, 이해관계자, 검증 질문이 있는 자료만 빠르게 골라야 하는 순간",
        "hidden_cost_ko": "가치 없는 자료에 시간을 쓰면 취재 시간이 줄고, 검증 질문을 놓치면 기사 품질이 낮아진다.",
        "bad_ai_trap_ko": "AI 요약만으로는 뉴스가치, 이해관계, 반론 필요성, 추가취재 질문이 분리되지 않는다.",
        "minimum_inputs_ko": ["보도자료 원문", "담당 분야/출입처", "기사 목적", "마감 시간"],
        "first_relief_ko": "10분 안에 기사 가치 점수, 확인할 이해관계자, 추가취재 질문이 나온다.",
        "paid_trigger_ko": "자료가 몰리는 오전, 마감 전 아이템 선별, 신입 기자가 데스크에 보고해야 할 때",
        "pilot_script_ko": "보도자료 더미를 뉴스가치 선별표와 추가취재 질문으로 압축하는 파일럿",
        "success_metric_ko": "검토 자료 수 절감, 취재 질문 확보, 데스크 보고용 한 줄 요약 작성",
        "human_boundary_ko": "기사 작성/사실확정을 자동화하지 않고, 선별표와 취재 질문 초안만 제공한다.",
    },
    ("paralegal", "case-timeline"): {
        "burning_moment_ko": "계약서, 문자, 메일, 영수증, 진술서가 섞여 있는데 변호사 검토 전에 날짜순 사실관계를 다시 세워야 하는 순간",
        "hidden_cost_ko": "타임라인이 흐리면 쟁점 파악이 늦고, 증거 누락 하나가 사건 준비 전체를 밀리게 한다.",
        "bad_ai_trap_ko": "법적 결론보다 중요한 것은 날짜, 당사자, 증거 위치, 확인 필요 사실을 빠짐없이 구조화하는 일이다.",
        "minimum_inputs_ko": ["자료 목록", "문서/메시지 날짜", "당사자 정보", "주요 쟁점 또는 사건 유형"],
        "first_relief_ko": "10분 안에 날짜순 사건표, 증거목록, 변호사 검토 질문이 나온다.",
        "paid_trigger_ko": "초기 상담 직후, 서면 작성 전, 자료가 많은 사건을 담당 변호사에게 넘겨야 할 때",
        "pilot_script_ko": "흩어진 사건 자료를 타임라인과 증거목록으로 정리하는 법률사무 보조 파일럿",
        "success_metric_ko": "자료 누락 감소, 변호사 검토 질문 명확화, 사실관계 정리 시간 절감",
        "human_boundary_ko": "법률 판단/자문을 하지 않고, 제공 자료의 사실관계 정리와 검토 질문만 만든다.",
    },
}


def _job_id(job_or_id) -> str:
    if isinstance(job_or_id, dict):
        return str(job_or_id.get("job_id", ""))
    return str(job_or_id)


def get(job_or_id, pain_id: str) -> dict | None:
    """대표 pain 심층 정보 조회."""
    row = DEEP_ATLAS.get((_job_id(job_or_id), str(pain_id)))
    return deepcopy(row) if row else None


def build(job_result: dict, pain_id: str | None = None) -> dict | None:
    """painmap 카드와 심층 정보를 합쳐 온보딩/오퍼에서 바로 쓸 행을 만든다."""
    pain = painmap.get(job_result, pain_id or "")
    if pain is None:
        pains = painmap.build(job_result, limit=1).get("pains", [])
        pain = pains[0] if pains else None
    if not pain:
        return None
    detail = get(job_result, pain["pain_id"]) or _fallback_detail(pain)
    merged = deepcopy(pain)
    merged.update(detail)
    merged["job_id"] = job_result.get("job_id", "")
    merged["job_name_ko"] = job_result.get("job_name_ko", "")
    return merged


def catalog(scores: dict[str, dict] | None = None) -> list[dict]:
    """15개 직업군 대표 pain 심층 카탈로그."""
    if scores is None:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        scores = ScoringEngine(os.path.join(here, "data", "jobs")).score([])
    rows = []
    for job_id in sorted(scores):
        row = build(scores[job_id])
        if row:
            rows.append(row)
    return rows


def validate_against_jobs(jobs: dict) -> list[str]:
    """대표 심층 pain이 실제 job/pain과 연결되는지 검증."""
    errors: list[str] = []
    covered_jobs = set()
    for (job_id, pain_id), row in DEEP_ATLAS.items():
        covered_jobs.add(job_id)
        if job_id not in jobs:
            errors.append(f"{job_id}/{pain_id}: unknown job")
            continue
        if painmap.get(jobs[job_id], pain_id) is None:
            errors.append(f"{job_id}/{pain_id}: unknown pain")
        for key in REQUIRED_KEYS:
            val = row.get(key)
            if isinstance(val, list):
                if not val or not all(str(x).strip() for x in val):
                    errors.append(f"{job_id}/{pain_id}: missing {key}")
            elif not str(val or "").strip():
                errors.append(f"{job_id}/{pain_id}: missing {key}")
    for job_id in sorted(set(jobs) - covered_jobs):
        errors.append(f"{job_id}: missing deep pain")
    return errors


def markdown_catalog(scores: dict[str, dict] | None = None) -> str:
    """운영자가 읽을 수 있는 심층 pain atlas 문서."""
    rows = catalog(scores)
    parts = [
        "# 직업별 진짜 가려운 업무 심층 아틀라스",
        "",
        "AI 대체 위험을 말하는 데서 끝내지 않고, 각 직업군이 실제 근무 중 돈을 내고라도 줄이고 싶은 순간을 정의합니다.",
        "모든 항목은 사용자 인터뷰 전 제품 가설이며, 결제/성과 보장 근거가 아니라 파일럿 오퍼와 인터뷰 질문을 좁히는 운영 자료입니다.",
        "",
    ]
    for r in rows:
        inputs = ", ".join(r.get("minimum_inputs_ko", []))
        parts.extend([
            f"## {r.get('job_name_ko')} — {r.get('itch_ko')}",
            f"- pain_id: `{r.get('pain_id')}`",
            f"- 터지는 순간: {r.get('burning_moment_ko')}",
            f"- 숨어있는 비용: {r.get('hidden_cost_ko')}",
            f"- 그냥 AI로 부족한 이유: {r.get('bad_ai_trap_ko')}",
            f"- 최소 입력: {inputs}",
            f"- 첫 10분 안도감: {r.get('first_relief_ko')}",
            f"- 구매 트리거: {r.get('paid_trigger_ko')}",
            f"- 파일럿 약속: {r.get('pilot_script_ko')}",
            f"- 성공 지표: {r.get('success_metric_ko')}",
            f"- 사람 경계선: {r.get('human_boundary_ko')}",
            "",
        ])
    return "\n".join(parts).rstrip() + "\n"


def _fallback_detail(pain: dict) -> dict:
    return {
        "burning_moment_ko": pain.get("moment_ko", ""),
        "hidden_cost_ko": "반복 업무 시간이 늘고, 실수/누락이 신뢰 하락으로 이어질 수 있습니다.",
        "bad_ai_trap_ko": "일반 AI 답변은 맥락과 실제 자료 형식을 반영하지 못할 수 있습니다.",
        "minimum_inputs_ko": ["현재 상황 설명", "관련 자료 일부", "마감/제약조건"],
        "first_relief_ko": f"{pain.get('artifact_ko', '업무 산출물')} 초안이 먼저 생깁니다.",
        "paid_trigger_ko": "마감이 가까워지고 반복 작업이 눈에 보이는 비용이 될 때",
        "pilot_script_ko": pain.get("service_move_ko", ""),
        "success_metric_ko": "반복 정리 시간 절감과 누락 감소",
        "human_boundary_ko": "전문 판단이나 성과 보장이 아니라, 사람이 검토한 산출물 초안만 제공합니다.",
    }


if __name__ == "__main__":
    print(markdown_catalog(), end="")
