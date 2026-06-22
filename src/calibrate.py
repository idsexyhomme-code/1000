"""
커리어 시그널 — baseline 캘리브레이션 어댑터 (R7)

손추정 baseline(calibrated:false)을 외부 '직무 AI 노출' 실데이터에 결박해 신뢰성을 올린다.
사용 가능한 공개 연구(전부 O*NET-SOC 기반):
  - Felten, Raj, Seamans (2021) AI Occupational Exposure(AIOE) — SMJ, github.com/AIOE-Data/AIOE
  - Eloundou et al. (2024) "GPTs are GPTs" GPT exposure — Science 384:1306
  - Frey & Osborne (2017) probability of computerisation

★정직성 불가침 (가짜 캘리브레이션·가짜 정밀도 금지):
  1) 외부 데이터셋은 라이선스/저작권이 있다 → **레포에 커밋하지 않는다**(data/calibration/*.csv = .gitignore).
     사용자가 출처에서 직접 받아 attribution과 함께 둔다. (AIOE는 명시적 오픈라이선스 없음 — 인용 필수.)
  2) 외부 점수는 '상대 AI 노출'(z-score/확률)이지 우리의 0~100 압력지수와 같은 척도가 아니다 →
     **직접 대입 금지.** 직무 간 '상대 순위(percentile)'로만 직업-레벨 index를 앵커링(문서화된 단조변환).
  3) 진짜 데이터로 결박된 직무만 calibrated:true + baseline.calibration 출처블록.
     데이터 없으면 calibrated:false 그대로. SOC confidence=medium은 경고(사용자 확정 전 약한 결박).
  4) 태스크별 baseline은 직업-레벨 노출로는 캘리브레이션 불가 → 손추정 유지(note 명시).
  5) CI(신뢰구간)를 인위로 좁히지 않는다 — 앵커와 손추정이 어긋나면 오히려 넓힌다(정직한 불확실성).

실행:
  python3 src/calibrate.py --data data/calibration/exposure.csv            # dry-run(미리보기, 기본)
  python3 src/calibrate.py --data data/calibration/exposure.csv --apply    # data/jobs/*.json 갱신
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(_ROOT, "data", "jobs")
SOC_MAP = os.path.join(_ROOT, "data", "calibration", "job_soc_map.json")

# 앵커 가중치: 외부 데이터를 맹신하지 않는다(척도 불일치 + 표본·연식 한계) → 손추정과 50/50 블렌드.
_ANCHOR_W = 0.5


def _norm_soc(s: str) -> str:
    """'27-4032.00' / '27-4032' / '274032' → '27-4032'(6자리 SOC)."""
    s = str(s).strip()
    digits = "".join(c for c in s if c.isdigit())
    return f"{digits[:2]}-{digits[2:6]}" if len(digits) >= 6 else s


def load_exposure(path: str) -> dict:
    """외부 노출 CSV → {SOC: float}. SOC 컬럼/점수 컬럼 자동 탐지. 파일 없으면 {}."""
    if not path or not os.path.exists(path):
        return {}
    out: dict[str, float] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        soc_col = next((c for c in cols if "soc" in c.lower() or "occupation code" in c.lower()), None)
        score_col = next((c for c in cols
                          if any(k in c.lower() for k in ("aioe", "exposure", "score", "probability", "index"))), None)
        if not soc_col or not score_col:
            raise ValueError(f"CSV에 SOC/점수 컬럼을 찾지 못함. 컬럼들={cols}")
        for row in reader:
            try:
                out[_norm_soc(row[soc_col])] = float(row[score_col])
            except (ValueError, TypeError, KeyError):
                continue
    return out


def _percentile(value: float, all_values: list) -> float:
    """value가 분포에서 차지하는 백분위(0~100). 동률은 중간순위로."""
    if not all_values:
        return 50.0
    below = sum(1 for v in all_values if v < value)
    equal = sum(1 for v in all_values if v == value)
    return round(100.0 * (below + 0.5 * equal) / len(all_values), 1)


def calibrate_job(job: dict, soc: str, exposure: dict, confidence: str = "high",
                  citation: str = "", apply_medium: bool = False):
    """직업 1개 baseline에 외부 노출 '상대순위 앵커'를 부착. 반환:
      - None: 결박 불가(SOC가 데이터에 없음) → calibrated:false 유지
      - "skip_medium": SOC confidence=medium인데 apply_medium=False → 사용자 확정 전까지 보류
      - dict: baseline.index_anchor 부착된 새 job(제자리 수정 안 함)

    ★정직성(Codex): scoring의 표시 점수는 '태스크 baseline 롤업'이라 baseline.index는 fallback일 뿐.
    이 앵커는 직업-레벨 참고치만 결박하므로 **calibrated:true로 올리지 않는다**(표시 점수 미반영 →
    'calibrated'라 하면 가짜 정밀도). 라이선스: 외부 raw 점수는 저장하지 않고 파생 percentile만."""
    nsoc = _norm_soc(soc)
    if nsoc not in exposure:
        return None
    if confidence != "high" and not apply_medium:
        return "skip_medium"                     # 약한 SOC 매핑 → 기본 보류(사용자 확정 필요)
    raw = exposure[nsoc]
    pct = _percentile(raw, list(exposure.values()))
    b = dict(job["baseline"])
    old_index = float(b.get("index", 50))
    anchored = round(_ANCHOR_W * pct + (1 - _ANCHOR_W) * old_index)   # 문서화된 단조 블렌드(직접대입 금지)
    b["index_anchor"] = {
        "anchored_index": int(anchored),
        "soc": nsoc,
        "soc_confidence": confidence,
        "percentile": pct,                       # 직무 간 '상대 AI 노출' 순위(0~100). 확률·절대수치 아님.
        "divergence_from_estimate": int(abs(anchored - old_index)),
        "source": citation or "외부 직무 AI 노출(O*NET-SOC 기반, 사용자 제공)",
        "method": f"anchored = round({_ANCHOR_W}*percentile + {1-_ANCHOR_W}*손추정). raw 점수는 라이선스로 미저장.",
        "scope": "직업-레벨 참고치 앵커만. 표시 점수는 태스크 baseline 롤업이라 아직 미반영 — 태스크-레벨 캘리브레이션 필요.",
        "as_of": datetime.now(timezone.utc).date().isoformat(),
    }
    # calibrated는 false 유지 — 표시 점수가 캘리브레이션된 게 아님(과대표기 금지, Codex).
    return {**job, "baseline": b}


def run(data_path: str, apply: bool = False, apply_medium: bool = False) -> dict:
    exposure = load_exposure(data_path)
    soc_map = json.load(open(SOC_MAP, encoding="utf-8"))["map"]
    citation = ("Felten, Raj & Seamans (2021) AI Occupational Exposure (AIOE), "
                "github.com/AIOE-Data/AIOE — O*NET-SOC 상대 노출(z-score)")
    summary = {"anchored": [], "skipped_no_data": [], "skipped_no_soc": [], "skipped_medium": []}
    if not exposure:
        print(f"⚠️ 외부 노출 데이터 없음({data_path}). 앵커링할 게 없습니다(직무 baseline은 손추정 그대로).\n"
              f"   → 출처(예: github.com/AIOE-Data/AIOE)에서 받아 data/calibration/에 두고 다시 실행.\n"
              f"   (라이선스/인용 준수 — 데이터는 커밋 금지, .gitignore 처리됨.)")
        return summary
    for fn in sorted(os.listdir(JOBS_DIR)):
        if not fn.endswith(".json"):
            continue
        job = json.load(open(os.path.join(JOBS_DIR, fn), encoding="utf-8"))
        jid = job.get("job_id", fn[:-5])
        m = soc_map.get(jid)
        if not m:
            summary["skipped_no_soc"].append(jid)
            continue
        lookup_soc = m.get("aioe_soc", m["soc"])  # AIOE 2010 SOC 빈티지 등가 우선, 없으면 캐노니컬 soc
        out = calibrate_job(job, lookup_soc, exposure, m.get("confidence", "high"), citation, apply_medium)
        if out is None:
            summary["skipped_no_data"].append(f"{jid}({m['soc']})")
            continue
        if out == "skip_medium":
            summary["skipped_medium"].append(f"{jid}({m['soc']})")
            continue
        a = out["baseline"]["index_anchor"]
        summary["anchored"].append(
            f"{jid}: 손추정 {job['baseline']['index']} → 앵커 {a['anchored_index']} "
            f"(p{a['percentile']}, soc {a['soc']}/{m.get('confidence')}, calibrated는 false 유지)")
        if apply:
            with open(os.path.join(JOBS_DIR, fn), "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
    return summary


if __name__ == "__main__":
    args = sys.argv[1:]
    data = args[args.index("--data") + 1] if "--data" in args else os.path.join(
        _ROOT, "data", "calibration", "exposure.csv")
    apply = "--apply" in args
    apply_medium = "--apply-medium" in args
    s = run(data, apply=apply, apply_medium=apply_medium)
    if s["anchored"]:
        print(("✅ 앵커 적용됨" if apply else "🔎 미리보기(dry-run, --apply로 적용)")
              + " — 직업-레벨 index_anchor(표시 점수는 태스크 롤업이라 미반영, calibrated:false 유지):")
        for line in s["anchored"]:
            print("  •", line)
    for k, label in [("skipped_no_data", "데이터에 SOC 없음(손추정 유지)"),
                     ("skipped_no_soc", "SOC 매핑 없음"),
                     ("skipped_medium", "⚠️ SOC confidence=medium 보류(확정 후 --apply-medium)")]:
        if s[k]:
            print(f"  {label}: {', '.join(s[k])}")
    print("\nℹ️ 표시 점수(태스크 롤업)까지 캘리브레이션하려면 태스크-레벨 노출 데이터가 필요합니다(다음 작업).")
