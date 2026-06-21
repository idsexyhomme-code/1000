"""
가려움 기반 수요 신호 측정 — 어떤 직업/업무 고통/micro-itch를 먼저 제품화할지 보는 CLI.

사용:
    python3 src/pain_intents.py             # 우선순위 요약(연락처 마스킹)
    python3 src/pain_intents.py --csv       # CSV(연락처 마스킹)
    python3 src/pain_intents.py --csv --raw # CSV 원본(연락처 평문 — 운영자 본인만)

라벨 정직성: 이 수치는 '결제'가 아니라 pain intent다. 즉, 사용자가 어떤 업무 고통과
작은 가려움을 해결하고 싶은지 남긴 신호다. 실제 지불 검증은 payments의 paid 이벤트로만 판단한다.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import painmap  # noqa: E402
import pain_probe  # noqa: E402
import store  # noqa: E402
from scoring import ScoringEngine  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JOBS_DIR = os.path.join(_ROOT, "data", "jobs")


def rows(path: str | None = None) -> list[dict]:
    path = path or store.PAIN_INTENT_FILE
    if not os.path.exists(path):
        return []
    out = []
    for ln in open(path, encoding="utf-8"):
        if not ln.strip():
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            pass
    return out


def _mask(contact: str) -> str:
    c = contact or ""
    if "@" in c:
        local, _, dom = c.partition("@")
        return (local[:2] + "***@" + dom) if local else "***@" + dom
    return (c[:2] + "***") if len(c) > 2 else "***"


def _csv_safe(v: str) -> str:
    s = str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def _job_results() -> dict:
    return ScoringEngine(_JOBS_DIR).score([])


def _pain_labels() -> dict[tuple[str, str], dict]:
    labels = {}
    for jid, job in _job_results().items():
        for p in painmap.build(job, limit=99).get("pains", []):
            labels[(jid, p["pain_id"])] = p
    return labels


def ranked_pains(data: list[dict]) -> list[dict]:
    labels = _pain_labels()
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in data:
        grouped[(r.get("job", ""), r.get("pain_id", ""))].append(r)
    out = []
    for key, items in grouped.items():
        job, pid = key
        uniq = {str(r.get("contact", "")).strip().lower() for r in items if r.get("contact")}
        sample_yes = sum(1 for r in items if r.get("sample_available") in ("yes", "redacted"))
        situations = sum(1 for r in items if str(r.get("situation", "")).strip())
        label = labels.get(key, {})
        # 제품화 우선순위: 수량 + 고유 연락처 + 샘플 제공 가능성 + 구체 상황.
        priority = len(items) * 3 + len(uniq) * 2 + sample_yes + situations * 0.5
        out.append({
            "job": job,
            "pain_id": pid,
            "count": len(items),
            "unique_contacts": len(uniq),
            "sample_available": sample_yes,
            "situations": situations,
            "priority": round(priority, 1),
            "itch_ko": label.get("itch_ko", pid),
            "artifact_ko": label.get("artifact_ko", ""),
        })
    return sorted(out, key=lambda r: (-r["priority"], -r["count"], r["job"], r["pain_id"]))


def _micro_itches(row: dict) -> list[str]:
    raw = row.get("micro_itches", [])
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def ranked_micro_itches(data: list[dict]) -> list[dict]:
    """사용자가 실제로 체크한 작은 가려움 순위."""
    counts: Counter[tuple[str, str]] = Counter()
    unique: dict[tuple[str, str], set[str]] = defaultdict(set)
    pain_ids: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for r in data:
        job = str(r.get("job", ""))
        contact = str(r.get("contact", "")).strip().lower()
        pain_id = str(r.get("pain_id", ""))
        for itch in _micro_itches(r):
            key = (job, itch)
            counts[key] += 1
            if contact:
                unique[key].add(contact)
            if pain_id:
                pain_ids[key][pain_id] += 1

    out = []
    for (job, itch), count in counts.items():
        uniq = len(unique[(job, itch)])
        priority = count * 2 + uniq
        top_pain = pain_ids[(job, itch)].most_common(1)
        out.append({
            "job": job,
            "micro_itch_ko": itch,
            "pain_id": top_pain[0][0] if top_pain else "",
            "count": count,
            "unique_contacts": uniq,
            "priority": round(priority, 1),
        })
    return sorted(out, key=lambda r: (-r["priority"], -r["count"], r["job"], r["micro_itch_ko"]))


def recommended_micro_itches(
    job_id: str,
    pain_id: str = "",
    *,
    limit: int = 2,
    path: str | None = None,
    fallback_to_job: bool = True,
) -> list[str]:
    """실제 선택 데이터 기준으로 온보딩/오퍼 기본 추천 micro-itch를 고른다.

    화면에는 aggregate 결과만 쓰고, 연락처/상황 원문은 노출하지 않는다. pain별 데이터가 아직 없으면
    같은 직업군 전체 선택값으로 fallback한다.
    """
    allowed = (pain_probe.get(job_id) or {}).get("micro_itches_ko", [])
    if not allowed:
        return []
    order = {item: i for i, item in enumerate(allowed)}
    data = rows(path)

    def rank(filtered_pain_id: str) -> list[str]:
        counts: Counter[str] = Counter()
        unique: dict[str, set[str]] = defaultdict(set)
        for r in data:
            if r.get("job") != job_id:
                continue
            if filtered_pain_id and r.get("pain_id") != filtered_pain_id:
                continue
            contact = str(r.get("contact", "")).strip().lower()
            for itch in _micro_itches(r):
                if itch not in order:
                    continue
                counts[itch] += 1
                if contact:
                    unique[itch].add(contact)
        ranked = sorted(
            counts,
            key=lambda itch: (-counts[itch], -len(unique[itch]), order.get(itch, 999)),
        )
        return ranked[:max(0, int(limit))]

    out = rank(pain_id)
    if not out and pain_id and fallback_to_job:
        out = rank("")
    return out


def summary() -> None:
    data = rows()
    print("── 가려움 수요 신호 (결제 아님 · 제품화 우선순위용) ──")
    print(f"총 pain intents: {len(data)}")
    if not data:
        print("아직 없음. /pain 페이지에서 어떤 업무 고통을 줄이고 싶은지 먼저 모아야 함.")
        return

    print("\n제품화 우선순위:")
    for r in ranked_pains(data)[:10]:
        print(f"  {r['priority']:>5}  {r['count']:>3}건  {r['job']:<18}  {r['pain_id']}")
        print(f"        {r['itch_ko']}")
        if r["artifact_ko"]:
            print(f"        결과물: {r['artifact_ko']}")

    micro = ranked_micro_itches(data)
    if micro:
        print("\n작은 가려움 상위:")
        for r in micro[:10]:
            print(f"  {r['priority']:>5}  {r['count']:>3}건  {r['job']:<18}  {r['micro_itch_ko']}")
            if r["pain_id"]:
                print(f"        연결 pain: {r['pain_id']}")

    print("\n직무별:")
    for job, n in Counter(r.get("job", "") or "(미지정)" for r in data).most_common():
        print(f"  {n:>4}  {job}")

    print("\n샘플 제공 가능성:")
    for key, n in Counter(r.get("sample_available", "") or "(미지정)" for r in data).most_common():
        print(f"  {n:>4}  {key}")

    print("\n신청 유형:")
    for key, n in Counter(r.get("offer_type", "") or "pain-intake" for r in data).most_common():
        print(f"  {n:>4}  {key}")

    print("\n최근 10건:")
    for r in data[-10:]:
        situation = str(r.get("situation", "")).replace("\n", " ")[:48]
        print(f"  {r.get('ts','')[:19]}  {r.get('job','')[:18]:<18}  "
              f"{r.get('pain_id','')[:22]:<22}  {_mask(r.get('contact',''))}  {situation}")
    print("\n※ pain intent는 '어떤 문제를 먼저 만들지'의 신호다. 지불 검증은 paid_customers로만 판단.")


def to_csv(raw: bool = False) -> None:
    import csv
    if raw:
        sys.stderr.write("⚠️ 연락처 평문 출력 — 운영자 본인만, 외부공유·커밋 금지.\n")
    labels = _pain_labels()
    w = csv.writer(sys.stdout)
    w.writerow(["ts", "job", "pain_id", "itch_ko", "offer_type", "role_type", "sample_available",
                "micro_itches", "situation", "contact"])
    for r in rows():
        contact = r.get("contact", "") if raw else _mask(r.get("contact", ""))
        label = labels.get((r.get("job", ""), r.get("pain_id", "")), {})
        w.writerow([
            _csv_safe(r.get("ts", "")),
            _csv_safe(r.get("job", "")),
            _csv_safe(r.get("pain_id", "")),
            _csv_safe(label.get("itch_ko", "")),
            _csv_safe(r.get("offer_type", "") or "pain-intake"),
            _csv_safe(r.get("role_type", "")),
            _csv_safe(r.get("sample_available", "")),
            _csv_safe(" | ".join(_micro_itches(r))),
            _csv_safe(str(r.get("situation", "")).replace("\n", " ")),
            _csv_safe(contact),
        ])


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--csv" in args:
        to_csv(raw="--raw" in args)
    else:
        summary()
