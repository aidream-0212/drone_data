---
name: drone-train
description: 드론 재고장 예측 모델을 기간 분할로 학습 · 검증하고(PR-AUC · 월 20대 적중 vs 무작위 · 오래된 순), 검증 기간에서 비용 최소 임계값(300 · 600 · 150만원)을 고른 뒤, train 전체로 최종 모델을 학습해 시험 기간 제출 파일 outputs/test_predictions_2025.csv를 만든다. 모델 학습, 다시 학습, 성능 검증, 임계값, 제출 파일(README [5] · [6] · [7])을 요청할 때 쓴다.
---

# drone-train — 학습 · 검증 · 위험 표시 기준 · 제출 (README [5] · [6] · [7])

## 실행
```powershell
python .claude/skills/drone-train/scripts/train.py
```

## 순서
1. `drone_lib.load_all()` → `split()`. 학습(fit) ~2024-06-30, 검증(val) 2024-07-01 ~ 12-31, 시험(test) 2025. 무작위로 나누지 않는다.
2. fit으로 `make_model()`을 학습해 val 확률을 구한다. PR-AUC를 기준선(재고장 비율)과, 월 20대 적중 수를 오래된 순 · 무작위(기대값)와 비교한다.
3. val에서 `놓친 재고장 × 300 + 기준 이상 × 60`(만원)이 가장 작은 임계값(0.05 ~ 0.94, 0.01 간격)을 고른다. 600만원 · 150만원도 같이 계산한다.
4. train 전체(2023 ~ 2024)로 최종 모델을 다시 학습해 test 1,241건 모두에 확률을 매기고 `outputs/test_predictions_2025.csv`(equipment_id, maintenance_date YYYY-MM-DD, prob)로 저장한다.
5. 저장: `artifacts/drone_model.joblib`, `artifacts/model_card.json`, `artifacts/val_predictions.csv`, `artifacts/val_monthly_top20.csv`, `reports/train_log.md`.
6. 콘솔 출력을 그대로 보여 주고, 다음 단계로 `drone-plan`(이번 달 20대)과 `drone-evaluate`를 제안한다.

## 지킬 것
- 피처는 `drone_lib.FEATURES`만 쓴다. `availability_rate`는 넣지 않는다.
- 임계값 · 모델 설정을 시험 기간(2025)으로 고르지 않는다. 자체 재현 정답(drone-evaluate)도 학습 · 선택에 쓰지 않는다.
- 성능은 정확도 하나로 말하지 않는다. PR-AUC와 월 20대 적중 수를 기준선과 함께 적는다.
- 숫자는 `reports/train_log.md` · `artifacts/model_card.json`에서 인용하고 출처를 적는다.
