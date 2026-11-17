---
name: drone-features
description: 드론별 지난 정비 기록으로 시간 피처(최근 90일 고장 수 · 직전 고장 뒤 경과일 · 예방정비 뒤 비행시간 · 계절)를 train → test → this_month 이어서 만들고, 모델에 넣지 않을 컬럼과 이유를 정리한다. 피처 만들기, 시간 피처 검산, 쓸 컬럼 고르기, 누수 확인(README [3] · [4])을 요청할 때 쓴다.
---

# drone-features — 피처 만들기 · 쓸 컬럼 고르기 (README [3] · [4])

## 실행
```powershell
python .claude/skills/drone-features/scripts/features.py
```

## 순서
1. `drone_lib.load_all()`로 원본 3개를 이어 붙여 `clean()` → `add_time_features()`를 적용한다.
2. 검산: 최근 90일 고장 수를 다른 방식으로 전체 다시 세어 불일치 0건인지, 2025-01 시험 행이 2024 기록을 보고 계산됐는지 확인한다.
3. 표본 1건(이번 달 최근 90일 고장 수가 가장 큰 드론)의 창 기록을 표로 보여 주고, 사용자가 손으로 세어 보게 한다.
4. 넣지 않은 컬럼(`drone_lib.EXCLUDED`)과 이유, `availability_rate` 누수 근거를 정리한다.
5. 콘솔 출력을 그대로 보여 주고, 다음 단계로 `drone-train`을 제안한다.

## 지킬 것
- 그 정비일 뒤의 기록을 쓰지 않는다(같은 날은 포함).
- 시험 · 이번 달 피처를 따로 계산하지 않는다. 반드시 앞 기간과 이어서 계산한다.
- `availability_rate` · `equipment_id` · `unit_code` · `maintenance_date` · `fault_code`는 모델에 넣지 않는다. 피처는 `drone_lib.FEATURES`만 쓴다.
- 피처를 바꾸면 `drone_lib.py`의 `FEATURES` · `EXCLUDED`를 고치고, 바꾼 파일과 이유를 먼저 말한다.
