---
name: drone-evaluate
description: 제출 파일(outputs/test_predictions_2025.csv) 형식을 점검하고, README 정답 정의로 2025 정답을 재현해(train 일치율로 규칙 검증) 시험 기간 PR-AUC · 월 20대 적중 수(드론 단위, 12개월)를 기준선과 비교하는 자체 평가를 한다. 또 다음 달 기록으로 지난달 재점검 20대의 실제 적중을 판정한다(plan_hits.py, 시험 모드 포함). 평가, 채점, 제출 전 점검, 시험 성능 확인, 지난달 계획 적중 · 맞았는지 확인(README 5. 평가)을 요청할 때 쓴다.
---

# drone-evaluate — 제출 점검 · 시험 기간 자체 평가 (README 5. 평가)

## 실행 (drone-train 다음)
```powershell
python .claude/skills/drone-evaluate/scripts/evaluate.py
python scripts/check.py
```

## 순서
1. 제출 파일 형식 5가지(열 이름 · 행 수 · 드론-정비일 조합 · 날짜 형식 · prob 범위)를 점검한다.
2. 정답 재현 규칙('정비 뒤 1 ~ 30일 안에 사후 · 긴급정비')을 train에 적용해 실제 정답과 일치율을 확인한다.
3. 같은 규칙으로 2025 정답을 재현해 PR-AUC(기준선 = 재고장 비율), 월 20대 적중 수(드론 단위 주 지표 + 기록 단위 참고, 모델 · 오래된 순 · 무작위), 재고장 드론 중 잡은 비율, 검증 기간 기준을 그대로 썼을 때의 비용을 계산한다.
4. `python scripts/check.py`로 단계별 진행과 보고서 숫자 대조를 확인한다.
5. 콘솔 출력을 그대로 보여 준다.

## 지난달 계획 적중 확인 (`scripts/plan_hits.py`)
다음 달 정비 기록이 들어오면 지난달 재점검 20대가 실제로 재고장 났는지 판정한다. "계획 적중 확인", "지난달 20대 맞았어?" 같은 요청에 쓴다.
```powershell
# 실제: 2026-02 기록(필요하면 2026-03까지)을 받은 뒤
python .claude/skills/drone-evaluate/scripts/plan_hits.py --followup <2026-02 기록.csv>
# 시험: 지금 데이터로 로직 확인(2025년 달만). all이면 12개월 표 · 합계
python .claude/skills/drone-evaluate/scripts/plan_hits.py --simulate 2025-12
python .claude/skills/drone-evaluate/scripts/plan_hits.py --simulate all
```
- 판정: 드론의 그 달 최근 정비일 뒤 1 ~ 30일 안에 사후 · 긴급정비 → 재고장. 30일 창을 다 덮는 기록이 없으면 '보류'(다음 기록이 오면 다시 실행).
- 비교: 계획 20대 적중 · 오래된 순 20대 · 무작위 기대값 · 기준 이상 적중 · 놓친 재고장 · 비용.
- 저장된 계획(`score_2026-01.csv`) 지문이 `plan_meta.json`과 다르면 판정하지 않는다(계획을 나중에 고친 경우).
- 결과: `reports/plan_hits_<달>[_sim].md`, `artifacts/plan_hits_<달>[_sim].json`, `run_history.csv`에 한 줄.
- 한 달 결과는 들쭉날쭉하다(2025 시험: 달마다 2 ~ 9대 적중). 모델 판단은 `--simulate all` 12개월 합계로 하고, 한 달 결과로 결론 내지 않는다.
- `--simulate all` 합계는 evaluate의 드론 단위 합계와 같아야 한다(drone-verify B 항목이 대조).

## 지킬 것
- 계획 적중 판정에는 **개입 효과**가 있다. 재점검으로 고장을 막으면 '정상'으로 나오므로 실제 적중이 모델 실력보다 낮을 수 있다. 결과와 함께 이 점을 적는다.
- 판정 결과를 보고 지난 계획 · 모델 · 임계값을 고치지 않는다.
- 재현 정답은 평가 확인용이다. 이 결과를 보고 모델 · 피처 · 임계값을 다시 고르지 않는다(시험 기간 누수). 바꾸고 싶으면 검증 기간 기준으로만 바꾼다.
- '공식 점수는 강사 정답으로 매긴다 · 재현 정답과 다를 수 있다'를 결과와 함께 적는다.
- 검증 기간보다 시험 기간 성능이 낮으면 그대로 보고하고, 이유는 '추정'으로 쓴다(예: 재고장 비율 상승 추세).
