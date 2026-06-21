"""
커리어 시그널 — 법무/PII 배포 전 점검.

연락처, 이력서, 업무자료를 수집하기 전에 /privacy, /terms 페이지가 실제 사업자 정보로
채워졌는지 확인한다. 초안의 [필수 입력]이 남아 있으면 리드 수집/결제를 열면 안 된다.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import report


REQUIRED_ENV = [
    "LEGAL_OPERATOR_NAME",
    "LEGAL_OPERATOR_ADDRESS",
    "LEGAL_CONTACT_EMAIL",
    "LEGAL_PRIVACY_OFFICER",
    "LEGAL_BUSINESS_NUMBER",
    "LEGAL_TELECOMMERCE_NUMBER",
    "LEGAL_PAYMENT_PROCESSOR",
    "LEGAL_HOSTING_PROVIDER",
    "LEGAL_NOTIFICATION_PROVIDER",
    "LEGAL_FULFILLMENT_FIELDS",
]

PRIVACY_MARKERS = [
    "개인정보의 처리 목적",
    "개인정보의 처리 및 보유 기간",
    "제3자 제공",
    "개인정보 처리위탁",
    "정보주체의 권리",
    "파기 절차",
    "자동화된 결정",
]

TERMS_MARKERS = [
    "사업자 정보",
    "상품 및 제공시점",
    "청약철회",
    "환불",
    "전문 판단 제외",
    "개인정보처리방침",
]


def missing_env(env: dict | None = None) -> list[str]:
    env = env or os.environ
    return [key for key in REQUIRED_ENV if not str(env.get(key, "")).strip()]


def check() -> tuple[bool, list[str]]:
    """현재 환경 기준 legal preflight 결과."""
    issues: list[str] = []
    missing = missing_env()
    if missing:
        issues.append("missing env: " + ", ".join(missing))

    privacy = report.privacy_html()
    terms = report.terms_html()
    if "[필수 입력]" in privacy:
        issues.append("privacy page still contains [필수 입력]")
    if "[필수 입력]" in terms:
        issues.append("terms page still contains [필수 입력]")
    if not privacy.rstrip().endswith("</html>"):
        issues.append("privacy page does not end with </html>")
    if not terms.rstrip().endswith("</html>"):
        issues.append("terms page does not end with </html>")

    for marker in PRIVACY_MARKERS:
        if marker not in privacy:
            issues.append(f"privacy missing marker: {marker}")
    for marker in TERMS_MARKERS:
        if marker not in terms:
            issues.append(f"terms missing marker: {marker}")

    return not issues, issues


def main() -> int:
    ok, issues = check()
    if ok:
        print("legal preflight ok")
        return 0
    print("legal preflight failed", file=sys.stderr)
    for issue in issues:
        print(f"- {issue}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
