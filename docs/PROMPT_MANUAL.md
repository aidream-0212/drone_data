# 드론 예측정비 실습 — 단계별 프롬프트 매뉴얼

`README.md`의 할 일 [1] ~ [8], 제출물 (1) ~ (3), 평가를 Claude Code에 **한 단계씩** 시키는 매뉴얼이다.
각 프롬프트를 그대로 복사해 붙여 넣고, '확인할 것'을 직접 점검한 뒤 다음 단계로 넘어간다.

---

## 0. 프롬프트 프레임워크

### 0.1 프롬프트 6요소: 역할 · 맥락 · 작업 · 제약 · 출력 · 검증
모든 단계 프롬프트는 같은 틀로 쓴다. 이렇게 쓰면 Claude가 맞는 스킬을 고르고 규칙(AGENTS.md)을 지키기 쉽다.

| 요소 | 쓰는 내용 | 예 |
|---|---|---|
| **역할** | Claude가 맡을 역할 | 드론 정비 데이터 분석가 |
| **맥락** | README 단계 번호 · 앞 단계 결과 · 쓸 스킬 | README [5], `drone-train` 스킬 |
| **작업** | 이번에 할 일 하나 | 기간 분할 학습 · 검증 |
| **제약** | 지킬 규칙(AGENTS.md에서 그 단계에 해당하는 것) | 시험 기간으로 임계값 고르지 않기 |
| **출력** | 받을 결과의 형태 · 파일 | 표 3개, `reports/train_log.md` |
| **검증** | 끝난 뒤 확인할 것 | `python scripts/check.py` 결과 그대로 |

### 0.2 진행 흐름 (CRISP-DM)
```
업무 이해 → 데이터 이해 → 데이터 준비 → 모델링 → 평가 → 활용(배포)
 README     [1] eda       [2] preprocess  [5][6][7]  평가       [8] plan
 목적·비용               [3][4] features  train      evaluate   제출물 (2) report
```
데이터 흐름: **train(2023 ~ 2024) 학습 → test(2025) 예측 · 자체 평가 → this_month(2026-01) 재점검 20대**

### 0.3 학습 모델 프레임워크 (프롬프트에서 이 이름으로 부른다)
| 구성 | 내용 | 위치 |
|---|---|---|
| 전처리 | `clean()` — 999 → 결측, 비용 ÷100, 예방정비 고장 결측 → "N/A", 첫 정비 표시 | `drone_lib.py` |
| 시간 피처 | `add_time_features()` — 최근 90일 고장 수, 직전 고장 뒤 경과일, 예방정비 뒤 비행시간 | `drone_lib.py` |
| 모델 | scikit-learn `Pipeline` = `OneHotEncoder` + `LGBMClassifier` | `drone_lib.make_model()` |
| 설명 | LightGBM `pred_contrib`(SHAP) 상위 3개 요인 | `drone_lib.reasons()` |
| 평가 | PR-AUC · ROC-AUC · 월 20대 적중(`monthly_topk`) · 비용(`cost_table`) | `drone_lib.py` |

---

## 1. 준비 — 환경 · Git

**프롬프트**
```
[역할] 이 저장소의 실습 조교.
[맥락] drone_data 폴더, AGENTS.md를 읽었다고 가정한다.
[작업] 가상환경(.venv, Python 3.12)이 켜지는지, requirements.txt 패키지가 설치돼 있는지, git status를 확인해 줘.
[제약] 파일을 만들거나 지우지 마. .venv와 __MACOSX는 .gitignore로 제외돼 있어야 한다.
[출력] 확인 항목 · 결과 표.
[검증] python -c "import pandas, sklearn, lightgbm, streamlit" 결과를 그대로 보여 줘.
```
**확인할 것** — `git status`에 `.venv/`가 보이지 않는다. 패키지 import 오류가 없다.

---

## 2. 데이터 살펴보기 (README [1]) — `drone-eda`

**프롬프트**
```
[역할] 드론 정비 데이터 분석가.
[맥락] README [1]. drone-eda 스킬을 쓴다.
[작업] 원본 3개 파일의 구조 · 결측 원인 · 이상치 · 재고장 비율과 패턴(드론 유형 · 계절 · 고장 유형)을 정리해 줘.
[제약] 원본만 읽고 고치지 마. 그래프는 만들지 마. 원인은 '추정'으로 써.
[출력] 구조 · 결측 · 이상치 · 패턴 표 4개, 결과 파일 reports/eda_summary.md.
[검증] 스크립트 콘솔 출력을 그대로 보여 줘.
```
**확인할 것** — 이번 달 파일에 `availability_rate`가 없는 것, 999 4건과 비용 > 10,000 5건, 분기 재고장 비율 상승(15.2% → 29.5%).

---

## 3. 데이터 처리 기준 (README [2]) — `drone-preprocess`

**프롬프트**
```
[역할] 드론 정비 데이터 분석가.
[맥락] README [2]. drone-eda 결과를 바탕으로 drone-preprocess 스킬을 쓴다.
[작업] 이상치 · 결측을 처리 기준대로 처리하고 처리 기록을 남겨 줘.
[제약] AGENTS.md '데이터 처리' 규칙. 행을 지우지 마. 원본 data/는 덮어쓰지 마.
[출력] 처리 기준 · 근거 표, 파일별 처리 건수 표.
[검증] 콘솔 점검 결과('모두 통과' 여부)를 그대로 보여 주고 python scripts/check.py 실행.
```
**확인할 것** — 행 수 전후 동일, '확인 필요' 0건, `reports/preprocess_log.md`의 드론 번호.

---

## 4. 피처 만들기 · 쓸 컬럼 고르기 (README [3] · [4]) — `drone-features`

**프롬프트**
```
[역할] 드론 정비 데이터 분석가.
[맥락] README [3] · [4]. drone-features 스킬.
[작업] 드론별 지난 기록으로 시간 피처를 만들고(train → test → this_month 이어서), 모델에 넣지 않을 컬럼과 이유를 정리해 줘.
[제약] 그 정비일 뒤 기록은 쓰지 마. availability_rate · equipment_id · unit_code · maintenance_date · fault_code는 제외.
[출력] 피처 정의 표, 넣지 않은 컬럼 · 이유 표, 표본 1건의 90일 창 기록.
[검증] 검산 불일치 건수와 '이어서 계산' 비교 숫자를 보여 줘.
```
**확인할 것** — 표본 드론의 창 기록을 직접 세어 피처 값과 같은지 본다. 불일치 0건.

---

## 5. 학습 · 검증 · 위험 표시 기준 · 시험 예측 (README [5] · [6] · [7]) — `drone-train`

**프롬프트**
```
[역할] 예측정비 모델 개발자.
[맥락] README [5] · [6] · [7]. drone-train 스킬. 학습 모델 프레임워크는 drone_lib.make_model()(OneHot + LightGBM).
[작업] fit(~2024-06)으로 학습해 검증 기간(2024-07~12) 성능과 기준선을 비교하고, 비용 최소 임계값을 300 · 600 · 150만원으로 구한 뒤,
       train 전체로 최종 모델을 학습해 test 1,241건 예측 제출 파일을 만들어 줘.
[제약] 무작위 분할 금지. 임계값을 시험 기간으로 고르지 마. 정확도 하나로 성능을 말하지 마.
[출력] 검증 성능 표(PR-AUC vs 기준선), 월 20대 적중 표(모델 · 오래된 순 · 무작위), 임계값 비교 표, 제출 파일 경로.
[검증] 콘솔 출력 그대로, 그리고 python scripts/check.py.
```
**확인할 것** — PR-AUC가 기준선(재고장 비율)보다 높은가, 모델 적중이 오래된 순 · 무작위보다 많은가, 600만원일 때 기준이 내려가는가(손해가 크면 더 넓게 잡음).

---

## 6. 이번 달 재점검 20대 (README [8] · 제출물 (3)) — `drone-plan`

**프롬프트**
```
[역할] 드론 정비반장에게 보고하는 분석가.
[맥락] README [8], 제출물 (3). drone-plan 스킬. drone-train 모델을 쓴다.
[작업] 이번 달 드론마다 가장 최근 기록으로 확률을 매겨 재점검 20대를 고르고 재점검 계획 보고서를 만들어 줘.
[제약] 순위 · 확률은 스크립트 출력만 인용. 부품 품목 · 업체 · 예산은 결론 내지 마. 한계(limits)를 그대로 적어.
[출력] 20대 표(순위 · 드론 · 유형 · 부대 · 확률 · 위험 요인 · 권고), 기준 초과 드론 수와 20대 밖 처리 방안.
[검증] python scripts/check.py로 보고서 표와 score_2026-01.csv 대조.
```
**확인할 것** — 기준 이상 드론 수가 20을 넘으면 처리 방안이 있는가, 상위 드론의 위험 요인이 납득되는가.

---

## 7. 평가 (README 5. 평가) — `drone-evaluate`

**프롬프트**
```
[역할] 제출 전 검수 담당자.
[맥락] README 5. 평가. drone-evaluate 스킬.
[작업] 제출 파일 형식을 점검하고, README 정답 정의로 2025 정답을 재현해(train 일치율 먼저 확인) 시험 기간 PR-AUC와 월 20대 적중(12개월)을 기준선과 비교해 줘.
[제약] 재현 정답으로 모델 · 임계값을 다시 고르지 마. '공식 점수는 강사 정답 기준'임을 적어.
[출력] 형식 점검 표, 검증 vs 시험 성능 표, 월별 적중 표.
[검증] 콘솔 출력 그대로, python scripts/check.py.
```
**확인할 것** — 형식 5항목 통과, 재현 규칙 train 일치율, 검증보다 시험 성능이 얼마나 다른가(차이의 이유는 '추정').

---

## 8. 분석 보고서 (제출물 (2)) — `drone-report`

**프롬프트**
```
[역할] 발표 자료를 만드는 분석가.
[맥락] 제출물 (2). drone-report 스킬. 앞 단계 산출물만 쓴다.
[작업] 처리 기준 · 넣지 않은 컬럼 · 기간 분할 · 성능과 기준선 · 임계값(300/600) · 위험 요인 · 한계를 담은 분석 보고서와 그래프를 만들어 줘.
[제약] 새로 학습하지 마. 숫자마다 출처 파일을 괄호에 적어. 표 · 그래프마다 '무엇 · 왜 · 그래서'를 써.
[출력] reports/분석보고서.md, reports/figures/ 그래프 5개.
[검증] 그래프 png를 열어 겹침 · 잘림 확인, python scripts/check.py.
```
**확인할 것** — 보고서 숫자가 `model_card.json` · `evaluation.json`과 같은가(check.py가 대조), 그래프 글자가 잘리지 않는가.

---

## 8-1. 추적 확인 — 결과가 지금 데이터 · 모델에서 나왔는가

**프롬프트**
```
[역할] 결과 검수 담당자.
[맥락] AGENTS.md '추적' 규칙. scripts/check.py 9 · 10번.
[작업] 데이터 · 모델 · 제출 파일 · 이번 달 점수의 지문이 서로 이어지는지, 현재 데이터로 다시 계산한 값이 저장된 결과와 같은지 확인해 줘.
       artifacts/run_history.csv의 최근 실행 기록도 보여 줘.
[제약] 결과 파일을 손으로 고치지 마. 불일치가 있으면 다시 실행할 스킬 순서만 제안해.
[출력] 지문 연결 표, 다시 계산 대조 결과, 최근 실행 기록 3줄.
```
**확인할 것** — 9번 6/6 일치, 10번 확률 최대 차이가 1e-5 미만, 이번 달 20대 순위 같음.

---

## 9. 마무리 — 커밋

**프롬프트**
```
[역할] 이 저장소의 실습 조교.
[작업] python scripts/check.py가 8/8인지 확인하고, 바뀐 파일 목록을 보여 준 뒤 내가 확인하면 커밋 · 푸시해 줘.
[제약] .venv · __MACOSX는 커밋하지 마. 커밋 메시지는 한국어로 무엇을 했는지 한 줄.
```

---

## 부록 A. 한 번에 다시 돌리기 (모든 단계)
```powershell
python .claude/skills/drone-eda/scripts/eda.py
python .claude/skills/drone-preprocess/scripts/preprocess.py
python .claude/skills/drone-features/scripts/features.py
python .claude/skills/drone-train/scripts/train.py
python .claude/skills/drone-plan/scripts/plan.py
python .claude/skills/drone-evaluate/scripts/evaluate.py
python .claude/skills/drone-report/scripts/report.py
python scripts/check.py
```
한글이 깨지면 먼저 `$env:PYTHONIOENCODING='utf-8'`.

## 부록 B. 짧게 부를 때
스킬 설명(description)에 단계 이름이 들어 있어서 짧게 말해도 맞는 스킬이 쓰인다.
- "EDA 해줘" → drone-eda
- "전처리해줘" → drone-preprocess
- "피처 만들어줘" → drone-features
- "모델 학습해줘" → drone-train
- "이번 달 재점검 20대 골라줘" → drone-plan
- "평가해줘" → drone-evaluate
- "보고서 만들어줘" → drone-report
- "어디까지 했지?" → python scripts/check.py
