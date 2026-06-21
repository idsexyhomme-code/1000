"""
커리어 시그널 — 런칭 모드별 배포 전 점검.

legal_preflight는 개인정보처리방침/약관만 본다. 이 모듈은 실제 오픈 모드별로
법무, 시크릿, 결제 검증, PII 파일 보호를 한 번에 점검한다.
"""
from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import legal_preflight
import fulfillment
import painmap
import report
from scoring import ScoringEngine


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(ROOT, "data", "jobs")
REQUIRED_GITIGNORE = [
    "data/interest.jsonl",
    "data/pain_intent.jsonl",
    "data/fulfillment_jobs.jsonl",
    "data/payments.jsonl",
]

COMMON_REQUIRED = [
    "GEMINI_API_KEY",
    "REPORT_BASE_URL",
    "WEBHOOK_TOKEN",
    "INTEREST_SALT",
]

PAYMENT_PLACEHOLDERS = {"", "0", "none", "null", "changeme", "secret", "test", "redacted"}


def _env(key: str) -> str:
    return str(os.environ.get(key, "")).strip()


def _missing_or_placeholder(key: str, min_len: int = 3) -> bool:
    val = _env(key)
    if len(val) < min_len:
        return True
    return val.lower().replace("_", "").replace("-", "") in PAYMENT_PLACEHOLDERS


def _https_url(key: str) -> bool:
    val = _env(key)
    try:
        p = urlsplit(val)
    except Exception:
        return False
    return p.scheme == "https" and bool(p.netloc)


def _positive_int(key: str) -> bool:
    try:
        return int(_env(key) or "0") > 0
    except ValueError:
        return False


def _allowed_amounts() -> set[int]:
    vals = set()
    raw = _env("PAYMENT_ALLOWED_AMOUNTS")
    if not raw:
        return vals
    for part in raw.split(","):
        try:
            n = int(part.strip())
        except ValueError:
            continue
        if n > 0:
            vals.add(n)
    return vals


def _job_results() -> dict:
    return ScoringEngine(JOBS_DIR).score([])


def _gitignore_issues() -> list[str]:
    path = os.path.join(ROOT, ".gitignore")
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return [".gitignore missing"]
    return [f".gitignore missing {item}" for item in REQUIRED_GITIGNORE if item not in text]


def _common_issues() -> list[str]:
    issues: list[str] = []
    ok, legal_issues = legal_preflight.check()
    if not ok:
        issues.extend(f"legal: {issue}" for issue in legal_issues)
    for key in COMMON_REQUIRED:
        min_len = 16 if key in {"WEBHOOK_TOKEN", "INTEREST_SALT"} else 3
        if _missing_or_placeholder(key, min_len=min_len):
            issues.append(f"missing or placeholder env: {key}")
    if _env("REPORT_BASE_URL") and not _https_url("REPORT_BASE_URL"):
        issues.append("REPORT_BASE_URL must be https://...")
    issues.extend(_gitignore_issues())
    return issues


def _lead_issues() -> list[str]:
    issues = []
    if _env("PAYMENT_URL"):
        issues.append("lead mode must not set PAYMENT_URL")
    if _env("PAIN_PAYMENT_URL"):
        issues.append("lead mode must not set PAIN_PAYMENT_URL")
    return issues


def _paid_issues() -> list[str]:
    issues = []
    if not _https_url("PAYMENT_URL"):
        issues.append("PAYMENT_URL must be https://...")
    if _missing_or_placeholder("PAYMENT_WEBHOOK_SECRET", min_len=16):
        issues.append("PAYMENT_WEBHOOK_SECRET missing or too weak")
    if not _positive_int("PAYMENT_EXPECTED_AMOUNT"):
        issues.append("PAYMENT_EXPECTED_AMOUNT must be positive")
    allowed = _allowed_amounts()
    amount = int(_env("PAYMENT_EXPECTED_AMOUNT") or "0") if _positive_int("PAYMENT_EXPECTED_AMOUNT") else 0
    if allowed and amount not in allowed:
        issues.append("PAYMENT_ALLOWED_AMOUNTS must include PAYMENT_EXPECTED_AMOUNT")
    return issues


def _pain_paid_issues() -> list[str]:
    issues = []
    if not _https_url("PAIN_PAYMENT_URL"):
        issues.append("PAIN_PAYMENT_URL must be https://...")
    if _missing_or_placeholder("PAYMENT_WEBHOOK_SECRET", min_len=16):
        issues.append("PAYMENT_WEBHOOK_SECRET missing or too weak")
    if not _positive_int("PAIN_PAYMENT_EXPECTED_AMOUNT"):
        issues.append("PAIN_PAYMENT_EXPECTED_AMOUNT must be positive")
    allowed = _allowed_amounts()
    amount = int(_env("PAIN_PAYMENT_EXPECTED_AMOUNT") or "0") if _positive_int("PAIN_PAYMENT_EXPECTED_AMOUNT") else 0
    if allowed and amount not in allowed:
        issues.append("PAYMENT_ALLOWED_AMOUNTS must include PAIN_PAYMENT_EXPECTED_AMOUNT")
    issues.extend(_pain_release_issues())
    return issues


def _pain_release_issues() -> list[str]:
    issues: list[str] = []
    job_id = _env("PAIN_RELEASE_JOB")
    pain_id = _env("PAIN_RELEASE_PAIN")
    preview_path = _env("PAIN_RELEASE_PREVIEW")
    if not job_id:
        issues.append("PAIN_RELEASE_JOB required for pain-paid")
    if not pain_id:
        issues.append("PAIN_RELEASE_PAIN required for pain-paid")
    if not preview_path:
        issues.append("PAIN_RELEASE_PREVIEW required for pain-paid")
    if issues:
        return issues

    jobs = _job_results()
    job = jobs.get(job_id)
    if not job:
        issues.append("PAIN_RELEASE_JOB is unknown")
        return issues
    pain = painmap.get(job, pain_id)
    if not pain:
        issues.append("PAIN_RELEASE_PAIN is not valid for PAIN_RELEASE_JOB")
        return issues

    try:
        preview = open(preview_path, encoding="utf-8").read()
    except OSError:
        issues.append("PAIN_RELEASE_PREVIEW file is not readable")
        return issues
    if not preview.rstrip().endswith("</html>"):
        issues.append("PAIN_RELEASE_PREVIEW must be an HTML file rendered by /pain-offer")
    for marker in [
        report.PAIN_OFFER_NAME,
        job.get("job_name_ko", ""),
        pain.get("artifact_ko", ""),
        "선택 때문에 달라지는 결과물",
        "자동화된 전문 판단이나 성과 보장",
        "/privacy",
        "/terms",
    ]:
        if marker and marker not in preview:
            issues.append(f"PAIN_RELEASE_PREVIEW missing marker: {marker}")

    try:
        sample = fulfillment.generate(job, pain_id, sample=True)
    except Exception:
        issues.append("fulfillment sample cannot be generated for PAIN_RELEASE_JOB/PAIN_RELEASE_PAIN")
        return issues
    for marker in ["파일럿 약속 범위", pain.get("artifact_ko", ""), "자동화된 전문 판단이나 성과 보장"]:
        if marker and marker not in sample:
            issues.append(f"fulfillment sample missing marker: {marker}")
    return issues


def check(mode: str = "lead") -> tuple[bool, list[str]]:
    """mode: lead, paid, pain-paid."""
    if mode not in {"lead", "paid", "pain-paid"}:
        return False, [f"unknown mode: {mode}"]
    issues = _common_issues()
    if mode == "lead":
        issues.extend(_lead_issues())
    elif mode == "paid":
        issues.extend(_paid_issues())
    elif mode == "pain-paid":
        issues.extend(_pain_paid_issues())
    return not issues, issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="커리어 시그널 런칭 preflight")
    ap.add_argument("--mode", choices=["lead", "paid", "pain-paid"], default="lead")
    args = ap.parse_args(argv)
    ok, issues = check(args.mode)
    if ok:
        print(f"launch preflight ok: {args.mode}")
        return 0
    print(f"launch preflight failed: {args.mode}", file=sys.stderr)
    for issue in issues:
        print(f"- {issue}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
