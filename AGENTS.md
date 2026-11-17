# AGENTS.md — 드론 예측정비 실습 (drone_data)

드론 정비 기록으로 '정비 뒤 30일 안 재고장'을 예측하고, 2026-01 재점검할 드론 20대를 고르는 프로젝트다.
**train(2023 ~ 2024)으로 학습 → test(2025)로 예측 · 평가 → this_month(2026-01)로 재점검 계획**을 만든다.
데이터는 **교육용 가상 데이터**다. 실습 안내는 `README.md`, 단계별 프롬프트는 `docs/PROMPT_MANUAL.md`.

## 폴더
- `data/` — 원본 `drone_train.csv`(정답 있음) · `drone_test.csv`(정답 없음) · `drone_this_month.csv`(정답 · availability_rate 없음)
- `drone_lib.py` — 공통 함수 · 상수. 모든 스킬 스크립트가 함께 쓴다
- `.claude/skills/drone-*/` — 단계별 스킬(SKILL.md + scripts/)
- `scripts/check.py` — 진행 확인 · 보고서 숫자 대조
- `artifacts/` — 전처리 결과 · 피처 · 모델 · 모델 정보 · 점수
- `outputs/` — 제출물 (1) `test_predictions_2025.csv`
- `reports/` — 단계 기록 · 제출물 (2) `분석보고서.md` · (3) `2026-01_재점검계획.md`, 그래프 `reports/figures/`

## 학습 모델 프레임워크
- scikit-learn `Pipeline` = `ColumnTransformer`(범주형 원-핫) + `LightGBMClassifier`(얕은 나무 · 강한 규제), `drone_lib.make_model()`
- 결측은 LightGBM이 처리한다(채우지 않음). 위험 요인 설명은 LightGBM `pred_contrib`(SHAP).
- 평가: scikit-learn `average_precision_score`(PR-AUC) · `roc_auc_score`, 업무 지표 `monthly_topk`(월 20대 적중), 비용 `cost_table`.

## 스킬과 순서 (README 할 일 번호)
| 순서 | 스킬 | README | 결과 |
|---|---|---|---|
| 1 | `drone-eda` | [1] 데이터 살펴보기 | `reports/eda_summary.md` |
| 2 | `drone-preprocess` | [2] 처리 기준 | `artifacts/clean/` · `reports/preprocess_log.md` |
| 3 | `drone-features` | [3] 피처 · [4] 쓸 컬럼 | `artifacts/features_all.csv` · `reports/features_log.md` |
| 4 | `drone-train` | [5] 검증 · [6] 기준 · [7] 제출 | 모델 · `model_card.json` · `outputs/test_predictions_2025.csv` · `reports/train_log.md` |
| 5 | `drone-plan` | [8] 20대 · 제출물 (3) | `artifacts/score_2026-01.csv` · `reports/2026-01_재점검계획.md` |
| 6 | `drone-evaluate` | 5. 평가 | `artifacts/evaluation.json` · `reports/evaluation.md` |
| 7 | `drone-report` | 제출물 (2) | `reports/분석보고서.md` · `reports/figures/` |

## 명령 (Windows PowerShell, drone_data 폴더, 가상환경 켠 상태)
- 가상환경: `.venv\Scripts\Activate.ps1` (Python 3.12, `pip install -r requirements.txt`)
- 스킬 실행: `python .claude/skills/<스킬>/scripts/<스크립트>.py`
- 진행 확인: `python scripts/check.py`

## 고정 약속 (바꾸지 않는다)
- `drone_lib.py`의 함수 이름 · 인자 · 상수(`FEATURES`, `TARGET`, 기간 경계, `CAPACITY`, 비용)와 위 파일 이름 · 위치는 바꾸지 않는다. 바꿔야 하면 이유를 먼저 말하고 확인받는다.
- 모델은 `drone_lib.make_model()`, 전처리는 `drone_lib.clean()`, 시간 피처는 `drone_lib.add_time_features()`만 쓴다.

## 규칙

### 기본
- 답은 한국어, 업무 보고서 문체로 쓴다.
- `data/` 원본 CSV는 고치지 않는다. 새 파일은 `artifacts/` · `outputs/` · `reports/`에 만든다.
- 요청한 단계의 스킬만 실행한다. 요청하지 않은 그래프 · 파일을 만들지 않는다.
- 코드를 고칠 때는 바꿀 파일과 이유를 먼저 말한다.
- API 키 · 실제 부대 정보 · 개인정보를 파일에 쓰지 않는다.

### 데이터 처리
- `downtime_hours` 999는 미입력 코드다. 행을 지우지 않고 결측으로 바꾼다.
- `maintenance_cost`가 10,000을 넘으면 자릿수 실수다. 100으로 나눈다.
- `fault_code` · `fault_category` 결측은 예방정비(고장 없음)다. `"N/A"`로 채운다(최빈값 X).
- `days_since_last_maintenance` 결측은 첫 정비다. 비워 두고 `is_first_maintenance`(0/1)를 만든다.
- 시간 피처는 그 정비일까지의 기록만 쓰고(같은 날 포함), train → test → this_month를 이어서 계산한다.

### 분석 · 검증
- 예측 시점은 '정비를 마친 직후'다. `availability_rate` · `equipment_id` · `unit_code` · `maintenance_date` · `fault_code`는 모델에 넣지 않는다.
- 기간으로 나눈다: fit ~ 2024-06-30, 검증 2024-07-01 ~ 12-31, 최종 학습 = train 전체, 시험 2025. 무작위로 나누지 않는다.
- 성능은 PR-AUC와 월 20대 적중 수를 기준선(재고장 비율 · 무작위 · 오래된 순)과 함께 적는다. 정확도 하나로 말하지 않는다.
- 임계값은 검증 기간에서 고른다(300 · 600만원 비교). 시험 기간으로 고르지 않는다.
- 2025 재현 정답(drone-evaluate)은 평가 확인용이다. 학습 · 피처 · 임계값 선택에 쓰지 않는다.
- 집계 결과를 원인으로 단정하지 않는다. 확인할 수 없으면 '추정'이라고 쓴다.
- 코드를 고치거나 스킬을 실행한 뒤에는 `python scripts/check.py`를 실행하고 결과를 그대로 보여 준다(10항목).

### 추적
- train · plan · evaluate는 입력 데이터 · 모델 · 결과 파일의 지문(SHA-256 앞 12자리)을 `model_card.json` · `plan_meta.json` · `evaluation.json`에 남기고, `artifacts/run_history.csv`에 실행 기록 한 줄을 덧붙인다.
- `check.py` 9번(지문 연결)이 X면 데이터나 결과가 바뀐 뒤 다시 실행하지 않은 것이다. 손으로 고치지 말고 drone-train → drone-plan → drone-evaluate → drone-report를 다시 실행한다.
- `check.py` 10번(다시 계산 대조)은 현재 데이터 + 저장된 모델로 시험 1,241건 · 이번 달 20대를 다시 계산해 저장된 결과와 비교한다.
- 원본 `data/`는 공개 저장소에 올리지 않는다(.gitignore). 지문으로 어느 데이터에서 나온 결과인지 확인한다.

### 보고
- 드론 위험도 · 순위 · 확률은 `drone-plan` 출력(`artifacts/score_2026-01.csv`)만 인용한다.
- 숫자마다 어느 파일 · 어느 명령에서 나왔는지 적는다. 실행하지 않은 계산의 숫자는 쓰지 않는다.
- 표 · 그래프마다 '무엇을 보여 주는가 · 왜 중요한가 · 그래서 무엇을 하는가'를 쓴다.
- 보고서 끝에 `artifacts/model_card.json`의 `limits`를 그대로 적고, 최종 판단은 정비 담당자가 한다고 밝힌다.
