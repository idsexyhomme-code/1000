# baseline 캘리브레이션 (손추정 → 실데이터 결박)

`data/jobs/*.json`의 `baseline`은 현재 **손추정**(`calibrated: false`)입니다. 신뢰성(= #1 레버)을 올리려면
직업-레벨 AI 노출을 **공개 연구 실데이터**에 결박합니다. 이 폴더의 어댑터(`src/calibrate.py`)가 그 일을 합니다.

## 쓸 수 있는 공개 데이터 (전부 O*NET-SOC 기반)
| 데이터셋 | 무엇 | 출처 | 라이선스 |
|---|---|---|---|
| **AIOE** (Felten·Raj·Seamans 2021) | 직업별 AI 노출 z-score(6자리 SOC) | github.com/AIOE-Data/AIOE | **명시적 오픈라이선스 없음 — 인용 필수, 재배포 전 저자 확인** |
| **GPTs are GPTs** (Eloundou et al. 2024) | LLM 노출(태스크→SOC), 가장 최신 | Science 384:1306 / 저자 배포 | 논문 데이터 가용성 확인 |
| Frey & Osborne (2017) | 전산화 확률(SOC), 고전·비판有 | 논문 부록 | 인용 |

## ⚠️ 이 어댑터의 정확한 범위 (Codex 검증 — 과대표기 금지)
- scoring의 **표시 점수는 '태스크 baseline 롤업'**으로 계산됩니다. `baseline.index`는 태스크가 없을 때의 **fallback**일 뿐입니다(15개 직무 모두 태스크 있음). → **직업-레벨 앵커는 표시 점수를 바꾸지 않습니다.**
- 따라서 이 어댑터는 `baseline.index_anchor`(외부 상대순위 참고치)만 부착하고 **`calibrated`는 false로 둡니다.** 'calibrated: true'라 하면 표시 점수가 검증된 것처럼 오인되므로 금지(가짜 정밀도).
- **진짜 캘리브레이션 = 태스크별 baseline을 태스크-레벨 노출 데이터(예: Eloundou GPT exposure task-level)로 결박**하는 것. 그게 다음 작업이며, 그때 비로소 `calibrated: true`가 정당화됩니다. 지금 단계는 **그 기반(앵커·SOC매핑·파이프라인)**입니다.

## 정직성 원칙 (불가침)
- **외부 CSV는 커밋하지 않습니다** (`*.csv`/`*.xlsx`는 `.gitignore`). 라이선스·저작권 존중. **외부 raw 점수는 job JSON에도 저장하지 않습니다**(파생 percentile만).
- 외부 점수는 **'상대 AI 노출'**(z-score/확률) — 우리의 0~100 압력지수와 **같은 척도가 아닙니다.** → 직접 대입 금지. 직무 간 **상대 순위(percentile)**로만 앵커링(문서화된 단조 블렌드).
- ⚠️ percentile은 **CSV에 든 직업 분포 전체** 기준으로 계산됩니다 → **반드시 데이터셋 전체(수백 직업)를 넣으세요.** 우리 15개만 넣으면 순위가 왜곡됩니다.
- `job_soc_map.json`의 `confidence: medium`(data-analyst·teacher 등 직군이 넓음)은 **기본 보류** — `onetonline.org`에서 SOC 확인 후 `--apply-medium`으로만 적용.

## 사용법
1. 위 출처에서 **데이터셋 전체**를 받아 SOC·점수 2컬럼 CSV로 `data/calibration/exposure.csv`에 저장
   (컬럼명에 `soc`와 `aioe`/`exposure`/`score`/`probability` 중 하나 포함 — 자동 탐지).
2. 미리보기: `python3 src/calibrate.py --data data/calibration/exposure.csv`
3. 적용: `python3 src/calibrate.py --data data/calibration/exposure.csv --apply` (medium SOC까지: `--apply-medium`)
   → 결박된 직무에 `baseline.index_anchor`(출처·percentile·scope) 부착. `calibrated`는 false 유지(표시 점수 미반영).

## 인용 (사용 시 필수)
- Felten E, Raj M, Seamans R (2021). *Occupational, industry, and geographic exposure to artificial intelligence.* Strategic Management Journal.
- Eloundou T, Manning S, Mishkin P, Rock D (2024). *GPTs are GPTs.* Science 384:1306–1308.
