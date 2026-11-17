# 피처 기록 (README [3] · [4])

생성: `python .claude/skills/drone-features/scripts/features.py` · 결과 `artifacts/features_all.csv`

## 1. 만든 피처 (그 정비일까지의 기록만 사용, 같은 날 포함 · 뒤 날짜 제외)

| 피처 | 정의 |
|---|---|
| fail_count_90d | 최근 90일(90일 전 날짜 포함) 사후 · 긴급정비 수, 이번 정비 포함 |
| days_since_last_failure | 직전 고장 정비 뒤 경과일(이번이 고장이면 0, 없으면 비움) |
| hours_since_last_pm | 최근 예방정비 때와 지금의 누적 비행시간 차(이번이 예방정비면 0, 없으면 비움) |
| season | 정비월 → 계절(12~2 겨울 · 3~5 봄 · 6~8 여름 · 9~11 가을). 정비일에 이미 아는 값 |
| is_first_maintenance | 직전 정비 경과일이 빈 행(첫 정비) = 1 |

### 시간 피처 요약 (train + test)

| 피처 | count | mean | 50% | max |
|---|---|---|---|---|
| fail_count_90d | 3,587 | 1.7 | 0 | 24 |
| days_since_last_failure | 2,707 | 118.7 | 30 | 979 |
| hours_since_last_pm | 3,586 | 13.4 | 0 | 165.2 |

## 2. 검산

- 최근 90일 고장 수: 다른 방식으로 전체 3,693행을 다시 셈 → 불일치 **0건**
- 앞 기간과 이어서 계산했는지 (2025-01 시험 행):

| 2025-01 test 행 | 직전 고장 경과일 있음(이어 계산) | 직전 고장 경과일 있음(test만 따로 계산했다면) |
|---|---|---|
| 124 | 112 | 53 |

### 표본: DR-0115 · 2026-01-24 (이번 달) — 창 2025-10-26 ~ 2026-01-24

| part | maintenance_date | maintenance_type | fault_category | cumulative_operating_hours | 고장정비 |
|---|---|---|---|---|---|
| test | 2025-11-03 | 긴급정비 | 통신 | 2,577 | O |
| test | 2025-11-19 | 예방정비 | N/A | 2,595.700 |  |
| test | 2025-12-04 | 사후정비 | 모터 | 2,612.600 | O |
| test | 2025-12-18 | 사후정비 | 통신 | 2,626.700 | O |
| test | 2025-12-19 | 긴급정비 | 배터리 | 2,627.700 | O |
| test | 2025-12-24 | 긴급정비 | 통신 | 2,633.700 | O |
| test | 2025-12-27 | 긴급정비 | 배터리 | 2,636.900 | O |
| test | 2025-12-31 | 사후정비 | 통신 | 2,640.800 | O |
| this_month | 2026-01-04 | 사후정비 | 모터 | 2,644.600 | O |
| this_month | 2026-01-13 | 예방정비 | N/A | 2,653.300 |  |
| this_month | 2026-01-17 | 사후정비 | 기체 | 2,657.700 | O |
| this_month | 2026-01-23 | 사후정비 | 센서 | 2,664.800 | O |
| this_month | 2026-01-24 | 긴급정비 | 모터 | 2,666.200 | O |

- 손으로 센 고장 정비: 11건 / 피처 값: 11건

## 3. 모델에 넣는 컬럼 (`drone_lib.FEATURES`)

- 범주형 4개: equipment_type, maintenance_type, fault_category, season
- 수치형 10개: equipment_age_years, severity, downtime_hours, repair_duration_hours, parts_replaced_count, maintenance_cost, maintenance_success, cumulative_operating_hours, days_since_last_maintenance, is_first_maintenance
- 시간 피처 3개: fail_count_90d, days_since_last_failure, hours_since_last_pm

## 4. 넣지 않은 컬럼과 이유 (README [4])

| 컬럼 | 이유 |
|---|---|
| availability_rate | 그 달 전체 가동률 — 정비 직후에는 알 수 없음(누수), 이번 달 데이터에도 없음 |
| equipment_id | 식별자 — 드론 번호를 외우게 됨 |
| unit_code | 식별자(부대) — 부대 번호를 외우게 됨 |
| maintenance_date | 날짜 자체는 넣지 않음 — 계절(season)과 시간 피처로 대신함 |
| fault_code | 고장 코드는 세부 코드라 종류가 많음 — fault_category로 대신함 |

- 누수 근거: train에서 `availability_rate` 평균 — 재고장 0: 0.959, 재고장 1: 0.785. 그 달 전체 가동률은 정비 뒤 30일의 고장을 일부 반영하므로 정비 직후에는 알 수 없음(이번 달 파일에도 없음).
