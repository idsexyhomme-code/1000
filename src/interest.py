"""
사전예약 리드 측정 — 30일 지불주체 스모크테스트 대시 (CLI).

사용:
    python3 src/interest.py            # 요약(총 리드·직무별·가격별·최근, 연락처 마스킹)
    python3 src/interest.py --csv      # CSV(연락처 마스킹 — 공유해도 비교적 안전)
    python3 src/interest.py --csv --raw # CSV 원본(연락처 평문 — 운영자 본인만, 외부공유·커밋 금지)

★ 라벨 정직성: 이 수치는 '사전예약 리드(무료 연락처)'다. '지불 의사(WTP)'가 아니다.
실제 결제는 PAYMENT_URL 연결 후 결제 이벤트로만 측정된다(리드≠지불).
연락처는 PII → 출력/CSV는 운영자 본인만, 커밋·외부공유 금지(data/interest.jsonl은 .gitignore).
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402


def _rows() -> list[dict]:
    if not os.path.exists(store.INTEREST_FILE):
        return []
    out = []
    for ln in open(store.INTEREST_FILE, encoding="utf-8"):
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def _mask(contact: str) -> str:
    """연락처 부분 마스킹(어깨너머 노출 완화). 이메일은 앞2자+도메인, ID는 앞2자."""
    c = contact or ""
    if "@" in c:
        local, _, dom = c.partition("@")
        return (local[:2] + "***@" + dom) if local else "***@" + dom
    return (c[:2] + "***") if len(c) > 2 else "***"


def summary() -> None:
    rows = _rows()
    print("── 사전예약 리드 (지불 의사 아님 · 무료 연락처 · 중복제거됨) ──")
    print(f"총 리드: {len(rows)}")
    if not rows:
        print("아직 없음. /offer 페이지 유입·전환을 늘려야 함.")
        return
    by_job = Counter(r.get("job", "") or "(미지정)" for r in rows)
    print("\n직무별:")
    for job, n in by_job.most_common():
        print(f"  {n:>4}  {job}")
    by_price = Counter(r.get("price_shown", "") or "(미표기)" for r in rows)
    if len(by_price) > 1:
        print("\n표시가격별:")
        for p, n in by_price.most_common():
            print(f"  {n:>4}  {p}")
    print("\n최근 10건:")
    for r in rows[-10:]:
        print(f"  {r.get('ts','')[:19]}  {r.get('job','')[:18]:<18}  {_mask(r.get('contact',''))}")
    print("\n※ 다음 단계: 리드가 모이면 PAYMENT_URL을 연결해 '실제 결제'를 측정하라.")
    print("  리드는 관심 신호일 뿐, 카드가 긁혀야 지불주체 검증이다.")


def _csv_safe(v: str) -> str:
    """CSV 수식 인젝션 방어 — =,+,-,@,탭으로 시작하면 ' 접두로 무력화(Excel/Sheets)."""
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def to_csv(raw: bool = False) -> None:
    import csv
    if raw:
        sys.stderr.write("⚠️ 연락처 평문 출력 — 운영자 본인만, 외부공유·커밋 금지.\n")
    w = csv.writer(sys.stdout)
    w.writerow(["ts", "job", "price_shown", "contact"])
    for r in _rows():
        contact = r.get("contact", "") if raw else _mask(r.get("contact", ""))
        w.writerow([_csv_safe(r.get("ts", "")), _csv_safe(r.get("job", "")),
                    _csv_safe(r.get("price_shown", "")), _csv_safe(contact)])


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--csv" in args:
        to_csv(raw="--raw" in args)
    else:
        summary()
