---
name: drone-plan
description: 학습된 모델로 drone_this_month.csv(2026-01)의 드론마다 가장 최근 기록에 재고장 확률을 매겨 재점검 20대를 고르고, 위험을 올린 요인 · 권고 · 기준 초과 드론 처리 방안 · 한계를 담은 reports/2026-01_재점검계획.md를 만든다. 이번 달 재점검 대상, 20대 선정, 재점검 계획(README [8] · 제출물 (3))을 요청할 때 쓴다.
---

# drone-plan — 이번 달 재점검 20대 · 재점검 계획 (README [8] · 제출물 (3))

## 실행 (먼저 drone-train으로 모델을 만들어 둔다)
```powershell
python .claude/skills/drone-plan/scripts/plan.py
```

## 순서
1. `load_all()`로 train → test → this_month를 이어 시간 피처를 계산한다(이번 달 피처가 2025 기록을 본다).
2. 드론마다 이번 달 가장 최근 기록 하나를 남기고 확률 · 위험 요인(SHAP 상위 3개)을 매긴다.
3. 확률 높은 순 20대를 고르고, 기준(`model_card.json` threshold) 이상 드론 수와 20대 밖 기준 이상 드론의 처리 방안을 적는다.
4. 저장: `artifacts/score_2026-01.csv`(전체 순위), `reports/2026-01_재점검계획.md`.
5. 콘솔 출력을 그대로 보여 준다.

## 지킬 것
- 드론 위험도 · 순위 · 확률은 이 스크립트 출력(`artifacts/score_2026-01.csv`)만 인용한다. 직접 계산한 숫자를 쓰지 않는다.
- 권고는 '점검 항목 예시'다. 부품 품목 · 납품업체 · 예산 금액은 데이터가 없으므로 결론 내지 않는다.
- 보고서 끝에 `model_card.json`의 `limits`를 그대로 적고, 최종 판단은 정비 담당자가 한다고 밝힌다.
