"""
커리어 시그널 — 직업별 micro-itch probe atlas.

painmap/pain_deepdive가 대표 pain과 파일럿 오퍼를 정의한다면, 이 모듈은 사용자가
"/pain" 온보딩에서 자기 상황을 더 잘 떠올리게 만드는 작은 업무 순간과 검증 질문을 담는다.

중요: 인터뷰 전 제품 가설이다. 정량 검증이나 직업 전체의 일반 사실처럼 보이면 안 되며,
사용자 입력을 더 구체화하기 위한 질문 재료로만 사용한다.
"""
from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scoring import ScoringEngine


REQUIRED_KEYS = (
    "micro_itches_ko",
    "interview_questions_ko",
    "money_moment_ko",
    "wedge_ko",
    "avoid_ko",
)


PROBE_ATLAS: dict[str, dict] = {
    "junior-developer": {
        "micro_itches_ko": [
            "작은 티켓인데 어느 파일부터 봐야 할지 몰라 README, Slack, 코드 검색을 계속 오간다.",
            "에러 로그 한 줄이 주문, 결제, 알림처럼 여러 도메인으로 이어져 영향 범위가 흐려진다.",
            "시니어에게 질문하기 전에 '내가 뭘 확인했는지'를 정리하는 데 시간이 더 든다.",
            "테스트 실패가 내 변경 때문인지 원래 flaky인지 구분이 안 된다.",
            "PR 설명에 수정 의도, 위험한 사이드이펙트, 검증 명령을 쓰는 게 어렵다.",
            "로컬 환경 세팅이나 fixture 데이터 때문에 실제 수정 전부터 진이 빠진다.",
            "레거시 네이밍과 도메인 용어가 낯설어 같은 코드를 여러 번 다시 읽는다.",
            "내가 한 티켓을 이력서나 면접에서 성과 문장으로 바꾸지 못한다.",
            "배포 전 env, feature flag, 마이그레이션 체크가 빠질까 불안하다.",
            "리뷰 코멘트를 반영하다가 원래 티켓 의도와 다른 수정으로 번진다.",
        ],
        "interview_questions_ko": [
            "최근 막힌 티켓에서 코딩보다 맥락 파악에 쓴 시간은 얼마나 됐나요?",
            "질문하기 전에 정리해야 했던 파일, 로그, 재현 절차는 무엇이었나요?",
            "PR 올리기 전 가장 두려운 리뷰 질문은 무엇인가요?",
            "반복해서 쓰는 테스트/로컬 실행 명령이 이미 정리되어 있나요?",
            "가장 먼저 받고 싶은 결과물은 수정 영향도 맵, 테스트 초안, PR 설명문 중 무엇인가요?",
        ],
        "money_moment_ko": "온콜 버그, 첫 팀 배정, 레거시 코드 수정처럼 실수가 평판으로 이어지는 순간",
        "wedge_ko": "티켓/로그/파일목록을 받아 수정 후보 파일, 영향 범위, 검증 명령, PR 설명문을 한 장으로 만든다.",
        "avoid_ko": "코드를 자동 병합하거나 리뷰어 판단을 대신하지 않는다.",
    },
    "video-editor": {
        "micro_itches_ko": [
            "수정 요청이 카톡, 메일, 댓글, 캡처 이미지에 흩어져 타임라인에 다시 꽂아야 한다.",
            "클라이언트 요청끼리 서로 충돌하는데 어느 방향을 확인해야 할지 정리되지 않는다.",
            "타임코드 없이 '여기 좀 빠르게' 같은 피드백이 와서 영상을 다시 훑어야 한다.",
            "자막 표기, 브랜드명, 가격, 날짜처럼 작은 실수가 납품 직전에 터진다.",
            "BGM, 색감, 템포 피드백이 취향인지 오류인지 분리하기 어렵다.",
            "긴 영상을 쇼츠, 릴스, 썸네일, 제목으로 다시 쪼개는 반복이 많다.",
            "무료 수정 범위가 끝났는데 추가비 안내를 꺼내기 어렵다.",
            "파일명이 final_final_final로 꼬여 최신본과 내부 작업본이 섞인다.",
            "원본 소스, 폰트, 로고 파일 경로를 매번 다시 찾아 프로젝트를 열어야 한다.",
            "수정본을 보낼 때 어떤 변경점이 반영됐는지 설명문이 필요하다.",
        ],
        "interview_questions_ko": [
            "수정 요청은 보통 어떤 채널로 몇 개 정도 흩어져 들어오나요?",
            "최근 누락되거나 충돌했던 수정 요청은 무엇이었나요?",
            "타임코드, 버전명, 계약상 수정 범위가 따로 정리되어 있나요?",
            "추가비를 말해야 했지만 못 말한 요청 유형은 무엇인가요?",
            "가장 먼저 필요한 결과물은 타임코드 체크리스트, 회신문, 버전 규칙 중 무엇인가요?",
        ],
        "money_moment_ko": "최종본 직전 수정 폭탄, 추가비 협상, 납품 지연 위험이 동시에 오는 순간",
        "wedge_ko": "흩어진 수정 요청을 타임코드, 작업 유형, 우선순위, 회신문으로 바꾼다.",
        "avoid_ko": "영상을 대신 편집했다고 말하지 않고, 수정 운영과 커뮤니케이션만 돕는다.",
    },
    "marketer": {
        "micro_itches_ko": [
            "회의 전 숫자는 있는데 '왜 올랐고 왜 떨어졌는지' 한 문장으로 설명이 안 된다.",
            "GA, 광고관리자, CRM, 시트 숫자가 서로 달라 어느 기준으로 말할지 막힌다.",
            "성과 하락 원인이 소재, 타깃, 예산, 랜딩 중 어디인지 우선순위를 못 잡는다.",
            "한 오퍼를 광고, 문자, 블로그, 랜딩, SNS 카피로 계속 변형해야 한다.",
            "보고서는 많이 쓰지만 다음 주 실험으로 연결되지 않는다.",
            "성과가 안 좋을 때 책임 설명과 액션 제안의 균형을 잡기 어렵다.",
            "좋았던 캠페인의 성공 요인을 재사용 가능한 템플릿으로 남기지 못한다.",
            "예산 증액을 요청해야 하는데 리스크와 근거가 한 장으로 정리되지 않는다.",
            "UTM, 캠페인명, 소재명이 뒤섞여 리포트에서 묶어보기 어렵다.",
            "성과 좋은 후기나 댓글을 소재로 바꿀 때 허위·과장 경계가 애매하다.",
        ],
        "interview_questions_ko": [
            "이번 주 회의에서 가장 설명하기 어려운 지표 변화는 무엇인가요?",
            "지표 원천 중 서로 숫자가 달라지는 곳은 어디인가요?",
            "최근 실패한 캠페인에서 다음 실험을 몇 개까지 뽑았나요?",
            "채널별 카피 변형에 보통 얼마나 걸리나요?",
            "받고 싶은 결과물은 성과 해석표, 다음 실험안, 보고서 문장 중 무엇인가요?",
        ],
        "money_moment_ko": "월요일 회의, 예산 재승인, 캠페인 실패 회고처럼 설명 하나가 다음 액션을 결정하는 순간",
        "wedge_ko": "지표 변화와 캠페인 맥락을 받아 원인 후보, 다음 실험, 보고 문장을 만든다.",
        "avoid_ko": "검증되지 않은 원인을 확정처럼 말하거나 성과 개선을 보장하지 않는다.",
    },
    "sales-rep": {
        "micro_itches_ko": [
            "미팅 30분 전 고객사 뉴스, 담당자, 이전 대화, 제안 포인트를 급하게 뒤진다.",
            "고객의 진짜 pain을 묻기 전에 제품 설명부터 하게 된다.",
            "통화 후 후속 메일, 내부 공유, CRM 업데이트가 밀려 딜 모멘텀이 죽는다.",
            "반대논리를 들었는데 다음 회신을 고객 언어로 바꾸는 데 시간이 걸린다.",
            "제안서는 비슷한데 고객별로 다르게 보이게 수정해야 한다.",
            "의사결정자, 사용자, 예산권자가 섞여 누가 막고 있는지 흐려진다.",
            "갱신/업셀 미팅에서 기존 사용성과 다음 확장 포인트를 한 장으로 못 묶는다.",
            "영업 메모가 흩어져 다음 콜 전에 같은 질문을 반복한다.",
            "견적, 보안자료, 사례 링크를 고객 상황에 맞춰 골라 보내는 데 시간이 든다.",
            "챔피언이 내부 설득할 수 있게 한 장짜리 공유 문장이 필요하다.",
        ],
        "interview_questions_ko": [
            "최근 중요한 미팅 전 준비 시간이 얼마나 부족했나요?",
            "미팅 후 가장 자주 밀리는 후속 작업은 무엇인가요?",
            "반대논리는 보통 가격, 우선순위, 보안, 전환비용 중 어디서 나오나요?",
            "CRM에는 무엇을 남기고 무엇이 빠지나요?",
            "가장 먼저 필요한 결과물은 3분 브리프, 발견 질문, 후속메일 중 무엇인가요?",
        ],
        "money_moment_ko": "중요 계정 첫 미팅, 의사결정자 참석, 갱신/업셀처럼 한 번의 콜 가치가 큰 순간",
        "wedge_ko": "미팅 전후 자료를 고객 맥락, 발견 질문, 반대논리, 후속 액션으로 압축한다.",
        "avoid_ko": "고객을 조작하는 문장이나 근거 없는 구매 가능성 판정을 만들지 않는다.",
    },
    "data-analyst": {
        "micro_itches_ko": [
            "'이 지표 왜 떨어졌어요?' 질문이 오면 정의, 기간, 분모부터 다시 확인해야 한다.",
            "대시보드 숫자를 믿지 못해 매번 SQL로 재검증한다.",
            "이벤트 변경, 배포, 마케팅 캠페인, 세그먼트 변화가 한꺼번에 겹친다.",
            "비슷한 임시 추출 요청을 Slack으로 계속 받아 분석보다 추출 대행이 된다.",
            "이해관계자가 원하는 답과 데이터가 말하는 답 사이를 설명해야 한다.",
            "지표 정의 문서가 없어 회의마다 '이 숫자 맞아요?'가 반복된다.",
            "SQL은 썼지만 결과 해석과 다음 액션 문장을 쓰는 데 시간이 든다.",
            "분석 결과가 의사결정으로 이어지지 않고 참고자료로만 끝난다.",
            "실험 결과가 의미 있는 변화인지 샘플 수와 노출 조건부터 다시 따져야 한다.",
            "같은 질문을 다른 팀이 다른 필터로 물어봐 대답이 계속 갈라진다.",
        ],
        "interview_questions_ko": [
            "최근 가장 많이 받은 '왜 변했나요?' 질문은 어떤 지표였나요?",
            "그 지표의 분자, 분모, 제외조건, 타임존은 문서화되어 있나요?",
            "반복 추출 요청 중 템플릿화할 수 있는 요청은 무엇인가요?",
            "분석을 공유할 때 가장 많이 받는 반문은 무엇인가요?",
            "받고 싶은 결과물은 원인 후보 트리, SQL 초안, 이해관계자 설명문 중 무엇인가요?",
        ],
        "money_moment_ko": "임원 리뷰, 지표 급락, 장애 여부 확인처럼 첫 해석이 신뢰를 결정하는 순간",
        "wedge_ko": "지표 질문을 원인 후보 트리, 검증 SQL, 공유 문장으로 바꾼다.",
        "avoid_ko": "실데이터를 보지 않고 확정 원인을 말하거나 의사결정을 자동화하지 않는다.",
    },
    "accountant": {
        "micro_itches_ko": [
            "마감 직전 고객이 어떤 자료를 내야 하는지 몰라 같은 요청을 반복해야 한다.",
            "영수증, 카드매출, 통장내역, 세금계산서가 고객마다 다른 이름으로 온다.",
            "받은 자료와 아직 빠진 자료를 다시 대조하는 데 시간이 샌다.",
            "숫자가 안 맞을 때 계정과목, 거래처, 증빙을 역추적해야 한다.",
            "고객에게 세법/신고 기준을 쉬운 말로 설명해야 하지만 오해가 두렵다.",
            "마감 영향이 큰 누락자료와 나중에 받아도 되는 자료가 섞인다.",
            "고객 재촉 문장을 쓰는 감정 노동이 크다.",
            "자료가 늦어져도 청구하기 어려운 시간이 계속 쌓인다.",
            "개인사업자와 법인 고객의 요청 자료가 달라 안내문을 매번 고쳐야 한다.",
            "자료명은 비슷한데 신고 대상 기간이 달라 잘못 반영될까 불안하다.",
        ],
        "interview_questions_ko": [
            "가장 자주 누락되는 고객 자료는 무엇인가요?",
            "마감 때 고객 한 명당 자료 확인에 얼마나 걸리나요?",
            "고객이 이해하지 못해 다시 묻는 표현은 무엇인가요?",
            "자료 누락이 신고 지연이나 오류로 이어진 사례가 있나요?",
            "먼저 필요한 결과물은 누락자료표, 고객 안내문, 내부 확인 순서 중 무엇인가요?",
        ],
        "money_moment_ko": "부가세, 종소세, 월마감처럼 누락자료 추적이 폭증하는 순간",
        "wedge_ko": "고객별 받은 자료와 빠진 자료를 표로 정리하고 쉬운 요청문을 만든다.",
        "avoid_ko": "세무 판단이나 신고 대리를 자동화하지 않고 자료 정리와 안내문에 한정한다.",
    },
    "bookkeeper": {
        "micro_itches_ko": [
            "월말에 통장과 장부 잔액이 안 맞아 차이를 한 건씩 거슬러 올라간다.",
            "쌓인 영수증·카드내역을 계정과목으로 일일이 분류해 입력한다.",
            "거래처마다 적요·계정과목을 다르게 적어 같은 거래를 매번 다시 판단한다.",
            "부가세 과세·면세·불공제 구분을 증빙마다 확인해야 한다.",
            "중도 입퇴사자·수당 변동이 겹치면 급여 계산이 표준에서 벗어난다.",
            "4대보험 요율·상한이 바뀌면 이번 달 계산 기준을 다시 확인한다.",
            "매입·매출 세금계산서 누락이나 중복을 마감 직전에야 발견한다.",
            "전표 한 건을 잘못 분개하면 결산까지 차이가 따라온다.",
            "월마감 결산 일정에 쫓겨 단순 입력에 시간을 다 쓴다.",
            "대표·세무대리인이 묻기 전에 숫자 근거를 정리해 둬야 한다.",
        ],
        "interview_questions_ko": [
            "월마감에서 가장 시간을 많이 잡아먹는 단계는 어디인가요?",
            "통장·장부 대사 차이를 추적하는 데 보통 얼마나 걸리나요?",
            "경비 분류에서 매번 애매해 다시 판단하는 항목은 무엇인가요?",
            "급여·4대보험에서 예외 케이스는 한 달에 몇 건 정도인가요?",
            "먼저 필요한 결과물은 대사 후보표, 경비 분류 초안, 급여 점검표 중 무엇인가요?",
        ],
        "money_moment_ko": "월마감·분기결산처럼 잔액이 반드시 맞아야 하고 단순입력·대사 시간이 폭증하는 순간",
        "wedge_ko": "통장과 장부 차이를 의심 전표 후보로 좁히고, 경비·증빙을 계정과목 초안으로 1차 분류한다.",
        "avoid_ko": "전표를 자동 확정하거나 세무 판단을 대신하지 않고, 검토할 후보와 확인 순서만 정리한다.",
    },
    "office-admin": {
        "micro_itches_ko": [
            "여러 부서 요청의 담당자, 마감, 승인 상태가 섞여 사람을 계속 쫓아다닌다.",
            "공지 하나를 써도 부서별로 다르게 이해해 다시 설명해야 한다.",
            "경비 영수증, 승인 규정, 계정 항목을 다시 맞추는 반복이 많다.",
            "행사/교육/회의 준비에서 장소, 비용, 참석자, 자료가 동시에 꼬인다.",
            "이미 처리한 사람과 아직 안 한 사람을 구분하지 못해 재촉이 민망해진다.",
            "상사에게 보고할 때 '무엇이 막혀 있는지'만 짧게 뽑아야 한다.",
            "마감 직전 승인권자가 바뀌거나 부재라 일정이 밀린다.",
            "자료 취합 파일명이 제각각이라 최종본을 만들기 어렵다.",
            "회의록에서 결정사항, 담당자, 마감만 뽑아 다시 공유해야 한다.",
            "외부 업체와 내부 요청자가 서로 다른 말을 해 중간에서 조율해야 한다.",
        ],
        "interview_questions_ko": [
            "최근 가장 많이 사람을 쫓아다닌 요청은 무엇이었나요?",
            "담당자, 마감, 상태를 지금 어디에 기록하나요?",
            "리마인드할 때 가장 불편한 표현은 무엇인가요?",
            "상사에게 보고할 때 매번 다시 요약하는 항목은 무엇인가요?",
            "받고 싶은 결과물은 요청 추적 보드, 리마인드 메시지, 보고 요약 중 무엇인가요?",
        ],
        "money_moment_ko": "행사, 감사, 월마감처럼 여러 부서 취합과 승인이 한꺼번에 몰리는 순간",
        "wedge_ko": "흩어진 요청을 담당자, 마감, 상태, blocker, 리마인드 문장으로 정리한다.",
        "avoid_ko": "조직 내 의사결정이나 승인 권한을 대신하지 않는다.",
    },
    "call-center-agent": {
        "micro_itches_ko": [
            "통화가 끝나자마자 다음 콜이 들어오는데 후처리 기록이 남아 있다.",
            "고객 감정은 공감해야 하지만 보상/정책 선을 넘으면 안 된다.",
            "FAQ, 공지, 이전 티켓 중 어떤 답이 최신인지 고객 대기 중에 찾아야 한다.",
            "이관 사유를 짧게 남기지 못하면 다음 상담자가 같은 질문을 반복한다.",
            "고객이 한 말을 사실, 감정, 요청, 약속으로 나누는 데 시간이 든다.",
            "정책상 불가능한 요청을 부드럽게 거절하는 문장이 어렵다.",
            "신입 상담사는 기록 항목을 빠뜨려 품질 피드백을 반복해서 받는다.",
            "민감정보를 기록에 남기면 안 되는데 통화 메모에 섞인다.",
            "고객이 같은 말을 반복할 때 상담 흐름을 끊지 않고 요약 확인해야 한다.",
            "상담 종료 후 약속한 후속조치와 실제 처리 시스템 입력이 어긋날까 불안하다.",
        ],
        "interview_questions_ko": [
            "통화 후처리에 평균 몇 분이 걸리나요?",
            "가장 자주 빠지는 기록 항목은 무엇인가요?",
            "상담 중 바로 찾기 어려운 정책/FAQ는 어떤 유형인가요?",
            "불만 고객에게 말하면 안 되는 표현이 따로 정리되어 있나요?",
            "필요한 결과물은 상담 요약, 이관 메모, 공감 스크립트 중 무엇인가요?",
        ],
        "money_moment_ko": "콜량 폭증, 신입 교육, 품질 점검처럼 기록 일관성이 바로 성과가 되는 순간",
        "wedge_ko": "상담 메모를 표준 요약, 이관 사유, 후속조치 등록 문장으로 바꾼다.",
        "avoid_ko": "보상 결정, 정책 예외, 고객 평가를 자동화하지 않는다.",
    },
    "teacher": {
        "micro_itches_ko": [
            "같은 단원인데 학생 수준 차이 때문에 활동지를 세 갈래로 다시 만들어야 한다.",
            "수업 목표는 있는데 평가 루브릭과 피드백 문장이 늦게 만들어진다.",
            "학부모에게 민감한 내용을 단정 없이 쓰는 문장이 어렵다.",
            "행정 문서가 수업 준비 시간을 잠식한다.",
            "평가 전 보충 자료를 만들 때 기초/심화 학생을 동시에 챙겨야 한다.",
            "수업 후 학생별 피드백을 구체적으로 쓰려면 시간이 부족하다.",
            "공개수업이나 연구수업 전 자료 완성도 압박이 커진다.",
            "생활지도 기록을 사실 중심으로 남기되 낙인처럼 보이지 않게 써야 한다.",
            "결석, 과제 미제출, 보충 안내를 학생·학부모별로 다르게 써야 한다.",
            "동료 교사와 자료를 공유할 때 수업 의도와 사용법을 짧게 설명해야 한다.",
        ],
        "interview_questions_ko": [
            "최근 수준별 자료를 따로 만들어야 했던 수업은 무엇인가요?",
            "활동지, 루브릭, 피드백 문장 중 무엇이 가장 오래 걸리나요?",
            "학부모 메시지에서 가장 조심스러운 주제는 무엇인가요?",
            "학교 양식에 맞춰 반복 작성하는 문서는 무엇인가요?",
            "받고 싶은 결과물은 수준별 활동지, 채점 루브릭, 학부모 메시지 중 무엇인가요?",
        ],
        "money_moment_ko": "공개수업, 평가 전 보충, 수준 차가 큰 반의 다음 수업 준비 직전",
        "wedge_ko": "수업 목표와 단원을 받아 수준별 활동, 루브릭, 피드백 문장 초안을 만든다.",
        "avoid_ko": "교육적 최종 판단이나 학생 평가를 대신하지 않는다.",
    },
    "nurse": {
        "micro_itches_ko": [
            "교대 전 관찰, 처치, 반응을 빠짐없이 차팅해야 하는데 시간이 부족하다.",
            "인수인계 때 중요한 변화만 짧게 압축해야 한다.",
            "보호자에게 절차를 설명하되 진료 판단처럼 들리지 않게 말해야 한다.",
            "객관적 수치, 환자 호소, 처치 사실, 보고 여부가 메모에 섞인다.",
            "반복 차팅 문장을 쓰느라 실제 케어 시간이 줄어드는 느낌이 든다.",
            "신규 간호사의 기록 문장 품질을 병동 기준에 맞춰야 한다.",
            "환자 식별정보를 외부 샘플에서 지우는 기준이 헷갈린다.",
            "교대 직전 누락된 보고/인계 항목이 떠올라 다시 기록을 뒤진다.",
            "검사, 투약, 처치 시간이 겹칠 때 우선순위와 완료 여부를 다시 확인해야 한다.",
            "환자 상태 변화가 작아도 보고가 필요한 변화인지 표현을 조심해야 한다.",
        ],
        "interview_questions_ko": [
            "교대 전 가장 자주 밀리는 기록 항목은 무엇인가요?",
            "차팅 문장, SBAR 인수인계, 보호자 설명 중 어디가 가장 부담인가요?",
            "기록에서 절대 빠지면 안 되는 병동 기준 항목은 무엇인가요?",
            "메모가 어떤 형태로 남아 있을 때 초안화가 가장 도움이 되나요?",
            "필요한 결과물은 차팅 문장 초안, 누락 확인 리스트, SBAR 요약 중 무엇인가요?",
        ],
        "money_moment_ko": "교대 직전, 신규 교육, 기록 품질 점검처럼 누락이 책임 리스크가 되는 순간",
        "wedge_ko": "사용자가 제공한 관찰 사실을 중립적 기록 문장과 누락 확인 리스트로 바꾼다.",
        "avoid_ko": "진단, 처방, 처치 권고 등 의료 판단을 하지 않는다.",
    },
    "translator": {
        "micro_itches_ko": [
            "AI 초벌번역이 자연스러워 보여 의미 왜곡을 더 의심해야 한다.",
            "숫자, 고유명사, 단위, 날짜 오류가 문장 자연스러움에 묻힌다.",
            "용어가 문서 안에서 흔들리면 전체 품질이 낮아 보인다.",
            "클라이언트가 'AI로 되잖아요'라며 단가를 낮추려 한다.",
            "여러 번역자가 작업한 문서에서 스타일과 용어를 맞춰야 한다.",
            "MTPE 단가 안에서 어디까지 고쳐야 하는지 범위가 흐려진다.",
            "원문이 애매한데 번역자가 의미 책임을 떠안는다.",
            "납품 전 QA 근거를 클라이언트에게 설명할 말이 부족하다.",
            "반복되는 문장 패턴을 일괄 수정하고 싶은데 예외 문맥이 섞인다.",
            "클라이언트 피드백을 다음 프로젝트의 용어·스타일 규칙으로 남기지 못한다.",
        ],
        "interview_questions_ko": [
            "최근 AI 초벌번역에서 가장 위험했던 오류 유형은 무엇인가요?",
            "용어집이나 스타일가이드가 있는 프로젝트인가요?",
            "QA에 가장 오래 걸리는 항목은 의미, 용어, 숫자, 자연스러움 중 무엇인가요?",
            "단가 방어를 위해 보여주고 싶은 품질 근거는 무엇인가요?",
            "필요한 결과물은 QA 리포트, 용어 불일치 리스트, 단가 방어 문장 중 무엇인가요?",
        ],
        "money_moment_ko": "납품 전 QA, MTPE 단가 협상, 긴 문서 공동 작업처럼 보이지 않는 검수가 돈이 되는 순간",
        "wedge_ko": "원문과 초벌번역을 위험 유형별로 대조해 수정 우선순위와 설명 근거를 만든다.",
        "avoid_ko": "최종 번역 품질 판단이나 법적 번역 인증을 대신하지 않는다.",
    },
    "graphic-designer": {
        "micro_itches_ko": [
            "브리프가 '세련되게', '힙하게'처럼 애매한데 결과 책임은 디자이너가 진다.",
            "수정 요청이 색 변경에서 새 시안, 문구 변경, 레이아웃 재작업으로 번진다.",
            "추가비를 말해야 하지만 관계가 껄끄러워 무료 수정이 늘어난다.",
            "클라이언트가 레퍼런스를 주지만 어떤 기준으로 좋은지 말하지 않는다.",
            "플랫폼별 사이즈, 포맷, 용량, 파일명을 맞추는 시간이 샌다.",
            "시안 피드백이 취향인지 브랜드 기준인지 분리되지 않는다.",
            "최종 승인 후에 다시 바꾸자는 요청이 들어온다.",
            "포트폴리오에서 디자인 의도와 성과를 설명하는 문장이 약하다.",
            "브랜드 가이드와 실제 요청이 충돌할 때 어느 쪽을 확인해야 할지 애매하다.",
            "인쇄물과 디지털용 색상·여백·해상도 기준을 동시에 맞춰야 한다.",
        ],
        "interview_questions_ko": [
            "최근 가장 애매했던 브리프 문장은 무엇인가요?",
            "수정 요청 중 범위 밖이라고 느낀 항목은 무엇이었나요?",
            "견적서나 계약서에 무료 수정 기준이 적혀 있나요?",
            "출력 규격 때문에 반복하는 작업은 어떤 플랫폼에서 많나요?",
            "필요한 결과물은 브리프 질문표, 수정 범위표, 추가비 안내문 중 무엇인가요?",
        ],
        "money_moment_ko": "최종 납품 전 수정 확산, 추가비 협상, 신규 시안 요청이 한꺼번에 오는 순간",
        "wedge_ko": "브리프와 수정 요청을 의사결정 질문, 범위표, 추가비 회신문으로 바꾼다.",
        "avoid_ko": "법적 계약 해석이나 디자인 성과 보장을 하지 않는다.",
    },
    "hr-manager": {
        "micro_itches_ko": [
            "지원자는 많은데 JD 기준으로 왜 통과/보류인지 근거를 빨리 남겨야 한다.",
            "면접관마다 질문과 평가 기준이 달라 후보 비교가 어렵다.",
            "이력서 요약은 해야 하지만 자동 탈락처럼 보이면 위험하다.",
            "공백, 전환, 잦은 이직 같은 리스크를 공정하게 질문해야 한다.",
            "후보자 강점은 보이는데 실제 직무 상황에서 확인할 질문이 부족하다.",
            "신규 입사자에게 같은 절차와 FAQ를 반복 설명한다.",
            "채용 일정이 밀릴 때 내부 이해관계자에게 상태를 짧게 공유해야 한다.",
            "민감/차별 요소를 평가표에서 빼는 검수가 필요하다.",
            "레퍼런스 체크나 과제 전형 결과를 면접 평가와 연결해 정리해야 한다.",
            "불합격 안내를 정중하게 보내면서 불필요한 분쟁 소지를 줄여야 한다.",
        ],
        "interview_questions_ko": [
            "최근 가장 많은 이력서가 몰린 포지션은 무엇인가요?",
            "JD 기준 중 꼭 확인해야 하는 3가지는 무엇인가요?",
            "면접관들이 서로 다르게 평가하는 항목은 무엇인가요?",
            "후보 요약에서 남기면 안 되는 민감 기준은 무엇인가요?",
            "필요한 결과물은 후보자 요약표, 면접 질문지, 평가 루브릭 중 무엇인가요?",
        ],
        "money_moment_ko": "지원자 급증, 면접 일정 압박, 면접관에게 후보 요약을 넘겨야 하는 순간",
        "wedge_ko": "JD와 이력서를 기준으로 후보 강점/리스크 요약과 면접 확인 질문을 만든다.",
        "avoid_ko": "합격/탈락, 채용 점수, 차별 가능성이 있는 자동 판단을 하지 않는다.",
    },
    "journalist": {
        "micro_itches_ko": [
            "보도자료가 쌓이는데 기사 가치가 있는 것만 빠르게 골라야 한다.",
            "자료 요약보다 새로움, 이해관계자, 반론 필요성을 찾는 게 더 어렵다.",
            "숫자, 인용, 주장, 날짜를 팩트체크해야 하는데 마감이 짧다.",
            "인터뷰 시간이 짧아 핵심 질문과 후속 질문을 미리 설계해야 한다.",
            "보도자료 문장을 그대로 쓰면 홍보처럼 보일까 봐 각도를 다시 잡는다.",
            "데스크에 보고할 한 줄 가치와 추가취재 필요성을 압축해야 한다.",
            "이해관계자 반론 요청 문장을 빠르게 준비해야 한다.",
            "비슷한 아이템이 많아 독자에게 실제 영향이 있는지 구분하기 어렵다.",
            "긴 녹취록에서 기사에 쓸 만한 발언과 맥락을 빠르게 찾아야 한다.",
            "속보 상황에서 아직 확인 안 된 내용과 보도 가능한 사실을 분리해야 한다.",
        ],
        "interview_questions_ko": [
            "하루에 검토하는 보도자료는 대략 몇 건인가요?",
            "기사화 여부를 가르는 기준은 새로움, 공익성, 숫자, 이해관계 중 무엇인가요?",
            "팩트체크에서 가장 자주 빠지는 항목은 무엇인가요?",
            "데스크 보고 전에 필요한 한 줄은 어떤 형식인가요?",
            "필요한 결과물은 선별표, 팩트체크 리스트, 인터뷰 질문지 중 무엇인가요?",
        ],
        "money_moment_ko": "오전 자료 폭주, 마감 직전, 데스크 보고처럼 선별 속도가 취재 시간을 결정하는 순간",
        "wedge_ko": "보도자료와 초안을 뉴스가치, 검증 질문, 반론 요청, 취재 질문으로 압축한다.",
        "avoid_ko": "사실확정, 기사 최종 작성, 취재 윤리 판단을 자동화하지 않는다.",
    },
    "paralegal": {
        "micro_itches_ko": [
            "계약서, 문자, 메일, 영수증, 진술서가 섞여 날짜순 사실관계를 다시 세워야 한다.",
            "증거는 많은데 어떤 문서가 어느 쟁점에 연결되는지 표시되지 않는다.",
            "제출 서류 하나가 빠지면 일정이 밀리는데 기관별 양식이 다르다.",
            "초기 상담 후 변호사에게 넘길 사건 요약을 빠르게 만들어야 한다.",
            "판례 검색 결과는 많지만 사건과 유사/차이점을 추리기 어렵다.",
            "고객이 보낸 자료 파일명이 제각각이라 증거목록을 만들기 어렵다.",
            "법률 판단처럼 보이지 않게 사실관계와 확인 질문만 정리해야 한다.",
            "마감, 제출처, 첨부, 원본 필요 여부를 놓칠까 불안하다.",
            "의뢰인이 보낸 긴 설명에서 시간, 장소, 당사자, 금액만 먼저 뽑아야 한다.",
            "상대방 주장과 우리 쪽 자료가 충돌하는 지점을 변호사에게 표시해야 한다.",
        ],
        "interview_questions_ko": [
            "최근 가장 자료가 흩어진 사건 유형은 무엇이었나요?",
            "타임라인 정리에 보통 몇 개의 문서/메시지가 들어가나요?",
            "변호사가 검토 전에 꼭 보고 싶어 하는 항목은 무엇인가요?",
            "제출 체크리스트에서 가장 자주 누락되는 항목은 무엇인가요?",
            "필요한 결과물은 사건 타임라인, 증거목록, 제출 체크리스트 중 무엇인가요?",
        ],
        "money_moment_ko": "초기 상담 직후, 서면 작성 전, 제출 마감 직전처럼 자료 구조화가 사건 속도를 정하는 순간",
        "wedge_ko": "흩어진 자료를 날짜, 당사자, 쟁점, 증거 위치, 변호사 검토 질문으로 구조화한다.",
        "avoid_ko": "법률 자문, 승소 가능성 판단, 서면 최종 작성을 자동화하지 않는다.",
    },
}


def _job_id(job_or_id) -> str:
    if isinstance(job_or_id, dict):
        return str(job_or_id.get("job_id", ""))
    return str(job_or_id)


def get(job_or_id) -> dict | None:
    row = PROBE_ATLAS.get(_job_id(job_or_id))
    return deepcopy(row) if row else None


def selected_micro_itches(job_or_id, selected) -> list[str]:
    """선택된 micro-itch 중 해당 직업군 atlas에 있는 문장만 보존한다."""
    if isinstance(selected, str):
        selected = [selected]
    if not isinstance(selected, list):
        return []
    row = get(job_or_id) or {}
    allowed = row.get("micro_itches_ko", [])
    out = []
    for item in selected:
        s = str(item or "").strip()
        if s and s in allowed and s not in out:
            out.append(s)
        if len(out) >= 6:
            break
    return out


def fulfillment_focus(job_or_id, selected) -> dict:
    """선택 micro-itch를 이행서용 우선 초점과 확인 질문으로 변환한다."""
    row = get(job_or_id) or {}
    selected_clean = selected_micro_itches(job_or_id, selected)
    questions = []
    for itch in selected_clean[:3]:
        questions.append(f"'{itch}'가 마지막으로 터진 실제 상황, 원문 자료, 마감은 무엇인가요?")
    for q in row.get("interview_questions_ko", []):
        if q not in questions:
            questions.append(q)
        if len(questions) >= 5:
            break

    if selected_clean:
        focus = (
            f"{row.get('wedge_ko', '선택한 작은 가려움을 산출물 기준으로 정리한다.')} "
            f"이번 납품은 '{selected_clean[0]}'를 1순위로 두고, 나머지 선택 항목은 확인 질문과 QA 기준으로 분리한다."
        )
    else:
        focus = row.get("wedge_ko", "선택한 반복 업무를 산출물 기준으로 정리한다.")

    moves = [
        "선택한 작은 가려움을 결과물 상단의 처리 기준으로 적는다.",
        "원문 자료, 위치, 버전, 마감처럼 검증 가능한 단서를 먼저 찾는다.",
        "확인되지 않은 해석은 '확인 필요'로 남기고 확정 표현을 쓰지 않는다.",
    ]
    if selected_clean:
        moves.insert(1, f"가장 먼저 '{selected_clean[0]}'가 산출물의 어느 표/문장/체크리스트로 해결되는지 표시한다.")

    return {
        "selected_micro_itches_ko": selected_clean,
        "priority_focus_ko": focus,
        "operator_moves_ko": moves[:5],
        "followup_questions_ko": questions[:5],
        "avoid_ko": row.get("avoid_ko", ""),
    }


def _artifact_hint(job_id: str, itch: str) -> dict:
    text = str(itch or "")
    if job_id == "video-editor":
        if "흩어져" in text or "타임라인" in text:
            return {
                "artifact_slot_ko": "수정 체크리스트 상단",
                "template_fields_ko": "source / timecode_or_scene / original_request / normalized_request / status",
                "qa_check_ko": "카톡·메일·댓글 등 출처별 원문을 보존하고, 합친 요청은 normalized_request에 따로 쓴다.",
            }
        if "충돌" in text:
            return {
                "artifact_slot_ko": "확인 필요/충돌 요청 표",
                "template_fields_ko": "conflict_group / request_a / request_b / decision_needed / proposed_reply",
                "qa_check_ko": "서로 충돌하는 요청은 임의 반영하지 않고 클라이언트 확인 질문으로 분리한다.",
            }
        if "타임코드 없이" in text:
            return {
                "artifact_slot_ko": "타임코드 보정 행",
                "template_fields_ko": "approx_scene / visual_hint / guessed_range / confirm_question",
                "qa_check_ko": "정확한 타임코드가 없는 요청은 guessed_range로 표시하고 확정처럼 쓰지 않는다.",
            }
        if "자막" in text or "표기" in text or "날짜" in text:
            return {
                "artifact_slot_ko": "납품 전 QA 표",
                "template_fields_ko": "label_type / exact_value / source_of_truth / checked_status",
                "qa_check_ko": "브랜드명·가격·날짜는 원천 자료와 대조 후 checked_status를 남긴다.",
            }
        if "BGM" in text or "색감" in text or "템포" in text:
            return {
                "artifact_slot_ko": "취향/오류 분리 표",
                "template_fields_ko": "feedback / objective_issue / taste_preference / recommended_option",
                "qa_check_ko": "취향 피드백과 오류 수정은 다른 상태값으로 분리한다.",
            }
        if "쇼츠" in text or "릴스" in text:
            return {
                "artifact_slot_ko": "재가공 후보 표",
                "template_fields_ko": "clip_candidate / hook / caption_angle / thumbnail_text",
                "qa_check_ko": "쇼츠 후보는 원본 의도와 다른 과장 문구를 쓰지 않는다.",
            }
    if job_id == "marketer":
        if "숫자" in text or "왜" in text or "지표" in text:
            return {
                "artifact_slot_ko": "성과 해석표",
                "template_fields_ko": "metric / change / segment / cause_candidate / confidence / next_check",
                "qa_check_ko": "원인 후보를 확정 원인처럼 쓰지 않고 검증할 next_check를 붙인다.",
            }
        if "실험" in text:
            return {
                "artifact_slot_ko": "다음 실험 표",
                "template_fields_ko": "hypothesis / action / owner / success_metric / stop_rule",
                "qa_check_ko": "실험은 성공 기준과 중단 기준을 같이 적는다.",
            }
        if "카피" in text or "변형" in text:
            return {
                "artifact_slot_ko": "채널별 카피팩",
                "template_fields_ko": "channel / audience / promise / proof / cta",
                "qa_check_ko": "채널별 문구는 같은 약속을 반복하되 CTA와 톤만 바꾼다.",
            }

    if job_id == "junior-developer":
        if "어느 파일" in text or "README" in text or "코드 검색" in text:
            return {
                "artifact_slot_ko": "수정 후보 파일 맵",
                "template_fields_ko": "entrypoint / likely_file / reason / unknown / first_probe_command",
                "qa_check_ko": "확인하지 않은 파일은 likely로 표시하고 확정 수정 지시처럼 쓰지 않는다.",
            }
        if "에러 로그" in text or "영향 범위" in text:
            return {
                "artifact_slot_ko": "영향 범위 추적표",
                "template_fields_ko": "log_line / domain / touched_component / possible_side_effect / owner_question",
                "qa_check_ko": "로그에서 확인한 사실과 추정 영향을 분리하고 owner_question을 남긴다.",
            }
        if "PR 설명" in text or "수정 의도" in text:
            return {
                "artifact_slot_ko": "PR 설명문 초안",
                "template_fields_ko": "change_summary / why / risk / test_command / rollback_note",
                "qa_check_ko": "검증 명령은 실제 실행 여부를 status로 표시하고 실행했다고 꾸미지 않는다.",
            }
        if "배포 전" in text or "feature flag" in text or "마이그레이션" in text:
            return {
                "artifact_slot_ko": "배포 전 체크리스트",
                "template_fields_ko": "env_key / flag_name / migration_step / owner / verified_status",
                "qa_check_ko": "운영 반영 여부는 담당자 확인 전 verified_status를 pending으로 둔다.",
            }
    if job_id == "sales-rep":
        if "미팅 30분 전" in text or "고객사 뉴스" in text:
            return {
                "artifact_slot_ko": "3분 미팅 브리프",
                "template_fields_ko": "account_signal / stakeholder / likely_pain / proof_point / opening_question",
                "qa_check_ko": "고객 의도를 단정하지 않고 질문으로 확인할 항목을 분리한다.",
            }
        if "후속 메일" in text or "CRM" in text:
            return {
                "artifact_slot_ko": "콜 후속 패키지",
                "template_fields_ko": "customer_ask / promised_followup / email_sentence / crm_next_step / due_date",
                "qa_check_ko": "콜에서 약속하지 않은 후속조치를 새로 만든 것처럼 쓰지 않는다.",
            }
        if "반대논리" in text or "회신" in text:
            return {
                "artifact_slot_ko": "반대논리 대응표",
                "template_fields_ko": "objection / customer_language / evidence_needed / reply_angle / next_question",
                "qa_check_ko": "압박성 문구 대신 고객 표현과 추가 확인 질문을 먼저 둔다.",
            }
        if "의사결정자" in text or "예산권자" in text:
            return {
                "artifact_slot_ko": "구매위원회 맵",
                "template_fields_ko": "person_or_role / influence / concern / needed_proof / next_action",
                "qa_check_ko": "직책만으로 의사결정력을 확정하지 않고 확인 필요로 표시한다.",
            }
    if job_id == "data-analyst":
        if "왜 떨어졌" in text or "정의" in text or "분모" in text:
            return {
                "artifact_slot_ko": "지표 진단 카드",
                "template_fields_ko": "metric / numerator / denominator / comparison_window / first_check_sql",
                "qa_check_ko": "정의와 비교 기간이 확인되지 않으면 원인 분석보다 metric_check를 먼저 둔다.",
            }
        if "대시보드" in text or "SQL" in text or "재검증" in text:
            return {
                "artifact_slot_ko": "대시보드 재현표",
                "template_fields_ko": "dashboard_tile / source_table / filter / sql_check / mismatch_note",
                "qa_check_ko": "대시보드와 SQL 차이는 원인 확정 전 mismatch_note로 남긴다.",
            }
        if "이벤트 변경" in text or "배포" in text or "캠페인" in text:
            return {
                "artifact_slot_ko": "변화 이벤트 타임라인",
                "template_fields_ko": "date / event_type / segment / expected_direction / validation_query",
                "qa_check_ko": "동시 발생 이벤트는 인과가 아니라 후보로 표시한다.",
            }
        if "의사결정" in text or "참고자료" in text:
            return {
                "artifact_slot_ko": "결정 연결 표",
                "template_fields_ko": "finding / decision_option / expected_impact / risk / owner_decision_needed",
                "qa_check_ko": "분석 결과가 자동 결정처럼 보이지 않게 owner_decision_needed를 남긴다.",
            }
    if job_id == "accountant":
        if "고객이 어떤 자료" in text or "같은 요청" in text or "누락자료" in text:
            return {
                "artifact_slot_ko": "고객별 누락자료 체크리스트",
                "template_fields_ko": "client / missing_doc / period / deadline / request_sentence / received_status",
                "qa_check_ko": "신고 판단은 제외하고 받은 자료와 누락 자료 상태만 표시한다.",
            }
        if "영수증" in text or "카드매출" in text or "세금계산서" in text:
            return {
                "artifact_slot_ko": "증빙 분류표",
                "template_fields_ko": "raw_file_name / doc_type / period / amount_hint / rename_rule / issue",
                "qa_check_ko": "금액과 기간은 원본 대조 전 amount_hint로만 표시한다.",
            }
        if "숫자가 안 맞" in text or "계정과목" in text:
            return {
                "artifact_slot_ko": "불일치 추적표",
                "template_fields_ko": "account / expected_amount / actual_amount / evidence / possible_reason / review_owner",
                "qa_check_ko": "계정과목 확정이나 세무 판단은 review_owner 확인 항목으로 남긴다.",
            }
        if "세법" in text or "신고 기준" in text:
            return {
                "artifact_slot_ko": "고객 설명문 초안",
                "template_fields_ko": "topic / plain_explanation / needed_action / caveat / accountant_review",
                "qa_check_ko": "전문 판단처럼 보이는 문장은 accountant_review 전송 전 확인으로 표시한다.",
            }
    if job_id == "office-admin":
        if "여러 부서 요청" in text or "담당자" in text or "승인 상태" in text:
            return {
                "artifact_slot_ko": "요청 추적 보드",
                "template_fields_ko": "request / department / owner / deadline / blocker / reminder_text",
                "qa_check_ko": "담당자와 마감이 불명확한 항목은 임의 지정하지 않고 확인 필요로 둔다.",
            }
        if "공지" in text:
            return {
                "artifact_slot_ko": "공지 버전 분리표",
                "template_fields_ko": "audience / core_message / possible_misread / action_needed / variant_text",
                "qa_check_ko": "부서별로 달라지는 행동 요청을 한 문장씩 분리한다.",
            }
    if job_id == "call-center-agent":
        if "통화가 끝나자마자" in text or "후처리" in text:
            return {
                "artifact_slot_ko": "상담 후처리 요약표",
                "template_fields_ko": "call_reason / customer_emotion / confirmed_fact / promised_action / after_call_task",
                "qa_check_ko": "고객 감정과 확인된 사실, 약속한 조치를 서로 다른 칸에 적는다.",
            }
        if "정책" in text or "FAQ" in text or "최신" in text:
            return {
                "artifact_slot_ko": "정책 확인표",
                "template_fields_ko": "customer_question / policy_source / current_answer / uncertainty / escalation_needed",
                "qa_check_ko": "최신 여부가 불명확하면 답변 확정 대신 escalation_needed로 표시한다.",
            }
    if job_id == "teacher":
        if "학생 수준 차이" in text or "세 갈래" in text:
            return {
                "artifact_slot_ko": "수준별 활동지 설계표",
                "template_fields_ko": "level / learning_goal / activity / scaffold / check_question",
                "qa_check_ko": "수준 구분은 낙인 표현 없이 활동 난이도와 지원 방식으로만 적는다.",
            }
        if "루브릭" in text or "피드백" in text:
            return {
                "artifact_slot_ko": "루브릭/피드백 표",
                "template_fields_ko": "criterion / beginner_evidence / proficient_evidence / feedback_sentence / next_practice",
                "qa_check_ko": "학생 평가 확정이 아니라 교사가 검토할 피드백 초안으로 표시한다.",
            }
    if job_id == "nurse":
        if "교대 전" in text or "차팅" in text:
            return {
                "artifact_slot_ko": "차팅 누락 확인표",
                "template_fields_ko": "observation / intervention / patient_response / report_status / missing_check",
                "qa_check_ko": "진단·처방 판단 없이 사용자가 제공한 관찰 사실과 처치 사실만 문장화한다.",
            }
        if "인수인계" in text:
            return {
                "artifact_slot_ko": "SBAR 인수인계 초안",
                "template_fields_ko": "situation / background / assessment_fact / recommendation_to_confirm / priority",
                "qa_check_ko": "recommendation은 의료 지시가 아니라 확인해야 할 인계 항목으로 쓴다.",
            }
    if job_id == "translator":
        if "AI 초벌번역" in text or "의미 왜곡" in text:
            return {
                "artifact_slot_ko": "MTPE 위험 점검표",
                "template_fields_ko": "segment_id / source_text / mt_output / risk_type / fix_priority / reviewer_note",
                "qa_check_ko": "자연스러움보다 의미 보존, 숫자, 고유명사를 먼저 점검한다.",
            }
        if "숫자" in text or "고유명사" in text or "단위" in text:
            return {
                "artifact_slot_ko": "용어/숫자 QA 표",
                "template_fields_ko": "term_or_number / source_value / target_value / consistency_status / correction",
                "qa_check_ko": "원문 대조 없이 임의 보정하지 않고 source_value를 함께 남긴다.",
            }
    if job_id == "graphic-designer":
        if "브리프" in text or "세련되게" in text or "힙하게" in text:
            return {
                "artifact_slot_ko": "브리프 명확화 질문표",
                "template_fields_ko": "brief_word / possible_meaning / clarifying_question / decision_needed / design_risk",
                "qa_check_ko": "취향어는 시안 지시가 아니라 확인 질문으로 바꾼다.",
            }
        if "수정 요청" in text or "재작업" in text:
            return {
                "artifact_slot_ko": "수정 범위 분리표",
                "template_fields_ko": "request / original_scope / scope_status / extra_work_reason / reply_sentence",
                "qa_check_ko": "추가비 판단은 계약 근거 확인 전 확정하지 않는다.",
            }
    if job_id == "hr-manager":
        if "지원자는 많은데" in text or "JD 기준" in text:
            return {
                "artifact_slot_ko": "후보자 JD 근거표",
                "template_fields_ko": "candidate / jd_requirement / resume_evidence / concern / interview_question",
                "qa_check_ko": "합격/탈락 판단 대신 면접에서 확인할 근거와 질문으로 남긴다.",
            }
        if "면접관" in text or "평가 기준" in text:
            return {
                "artifact_slot_ko": "면접 평가 기준 정렬표",
                "template_fields_ko": "competency / question / strong_signal / weak_signal / forbidden_criteria",
                "qa_check_ko": "차별 가능성이 있는 기준은 forbidden_criteria로 분리한다.",
            }
    if job_id == "journalist":
        if "보도자료" in text or "기사 가치" in text:
            return {
                "artifact_slot_ko": "보도자료 선별표",
                "template_fields_ko": "release_title / news_value / affected_party / fact_to_check / reporting_next_step",
                "qa_check_ko": "홍보 문구를 기사 가치로 오인하지 않고 확인할 사실을 분리한다.",
            }
        if "팩트체크" in text or "숫자" in text or "인용" in text:
            return {
                "artifact_slot_ko": "팩트체크 대기표",
                "template_fields_ko": "claim / source / verification_needed / counterparty / publish_risk",
                "qa_check_ko": "확인 전 주장은 기사 문장으로 확정하지 않는다.",
            }
    if job_id == "paralegal":
        if "날짜순 사실관계" in text or "계약서" in text or "문자" in text:
            return {
                "artifact_slot_ko": "사건 타임라인 표",
                "template_fields_ko": "date / actor / event / evidence_file / issue_tag / attorney_question",
                "qa_check_ko": "법률 판단이 아니라 사실관계와 변호사 확인 질문만 남긴다.",
            }
        if "증거" in text or "쟁점" in text:
            return {
                "artifact_slot_ko": "증거-쟁점 연결표",
                "template_fields_ko": "evidence_id / file_name / related_issue / supports_or_conflicts / missing_context",
                "qa_check_ko": "증거의 법적 효력은 판단하지 않고 연결 후보로 표시한다.",
            }

    if "자료" in text or "누락" in text:
        fields = "missing_item / owner / deadline / risk / request_message"
        slot = "누락자료/요청 표"
        qa = "누락 항목은 마감 영향과 요청 문장을 함께 남긴다."
    elif "기록" in text or "요약" in text or "메모" in text:
        fields = "fact / context / next_action / owner / due"
        slot = "기록/후속조치 표"
        qa = "확인된 사실과 추정, 다음 액션을 분리한다."
    elif "질문" in text or "면접" in text or "인터뷰" in text:
        fields = "topic / evidence / question / followup / risk"
        slot = "질문 설계 표"
        qa = "질문은 판단을 대신하지 않고 확인해야 할 근거로 연결한다."
    elif "범위" in text or "추가비" in text or "계약" in text:
        fields = "request / scope_status / evidence / fee_note / reply"
        slot = "범위 분리 표"
        qa = "범위 밖 요청은 감정 표현 없이 근거와 다음 선택지로 분리한다."
    elif "설명" in text or "공지" in text or "메시지" in text:
        fields = "audience / message_goal / plain_language / action_needed / caveat"
        slot = "설명문/메시지 표"
        qa = "대상자가 해야 할 행동과 주의 문구를 한 문장씩 남긴다."
    else:
        fields = "input / pain_signal / artifact_move / priority / qa_check"
        slot = "핵심 산출물 표"
        qa = "선택한 작은 가려움이 산출물의 어느 행에서 처리됐는지 표시한다."
    return {
        "artifact_slot_ko": slot,
        "template_fields_ko": fields,
        "qa_check_ko": qa,
    }


def artifact_adjustment(job_or_id, selected) -> dict:
    """선택 micro-itch별로 납품 산출물 표/행 조정안을 만든다."""
    job_id = _job_id(job_or_id)
    selected_clean = selected_micro_itches(job_id, selected)
    rows = []
    for itch in selected_clean:
        hint = _artifact_hint(job_id, itch)
        row = {"micro_itch_ko": itch}
        row.update(hint)
        rows.append(row)
    return {
        "selected_micro_itches_ko": selected_clean,
        "adjustment_rows": rows,
        "note_ko": "선택된 작은 가려움이 실제 납품 표의 칸과 QA 기준으로 보이도록 조정합니다.",
    }


def build(job_result: dict) -> dict | None:
    row = get(job_result)
    if not row:
        return None
    row["job_id"] = job_result.get("job_id", "")
    row["job_name_ko"] = job_result.get("job_name_ko", "")
    row["label_ko"] = "micro-itch 가설"
    row["note_ko"] = "사용자 인터뷰 전 가설입니다. 체크리스트는 입력을 돕기 위한 질문 재료입니다."
    return row


def catalog(scores: dict[str, dict] | None = None) -> list[dict]:
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
    errors: list[str] = []
    for job_id, row in PROBE_ATLAS.items():
        if job_id not in jobs:
            errors.append(f"{job_id}: unknown job")
            continue
        for key in REQUIRED_KEYS:
            val = row.get(key)
            if isinstance(val, list):
                if not val or not all(str(x).strip() for x in val):
                    errors.append(f"{job_id}: missing {key}")
            elif not str(val or "").strip():
                errors.append(f"{job_id}: missing {key}")
        itches = row.get("micro_itches_ko", [])
        questions = row.get("interview_questions_ko", [])
        if len(itches) < 10:
            errors.append(f"{job_id}: micro_itches_ko must have at least 10 items")
        if len(questions) < 4:
            errors.append(f"{job_id}: interview_questions_ko must have at least 4 items")
        if len(set(itches)) != len(itches):
            errors.append(f"{job_id}: duplicate micro itch")
    for job_id in sorted(set(jobs) - set(PROBE_ATLAS)):
        errors.append(f"{job_id}: missing probe atlas")
    return errors


def markdown_catalog(scores: dict[str, dict] | None = None) -> str:
    rows = catalog(scores)
    parts = [
        "# 직업별 micro-itch probe atlas",
        "",
        "대표 pain 하나로는 사용자가 자기 상황을 떠올리기 어렵습니다.",
        "아래 항목은 `/pain` 온보딩에서 '혹시 이런 순간인가요?'로 보여줄 작은 업무 고통과 검증 질문입니다.",
        "",
    ]
    for row in rows:
        parts.extend([
            f"## {row.get('job_name_ko')}",
            f"- 라벨: {row.get('label_ko')}",
            f"- 돈 내는 순간: {row.get('money_moment_ko')}",
            f"- 좁은 wedge: {row.get('wedge_ko')}",
            f"- 하지 말아야 할 것: {row.get('avoid_ko')}",
            "",
            "### 작은 가려움",
        ])
        parts.extend(f"- {x}" for x in row.get("micro_itches_ko", []))
        parts.extend(["", "### 검증 질문"])
        parts.extend(f"- {x}" for x in row.get("interview_questions_ko", []))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def write_markdown(path: str, scores: dict[str, dict] | None = None) -> str:
    text = markdown_catalog(scores)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="직업별 micro-itch probe atlas")
    ap.add_argument("--out", default="", help="Markdown 파일로 저장할 경로")
    args = ap.parse_args(argv)
    if args.out:
        write_markdown(args.out)
        print(args.out)
    else:
        print(markdown_catalog(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
