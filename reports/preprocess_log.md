# 전처리 기록

생성: `python .claude/skills/drone-preprocess/scripts/preprocess.py` (drone-preprocess 스킬). 원본 `data/*.csv`는 바꾸지 않았고 결과는 `artifacts/clean/`에 있다.

## 1. 파일별 처리 건수

| 파일 | 행(전 → 후) | downtime 999 → NaN | 비용 ÷100 | 고장 결측 → N/A(예방정비) | 첫 정비 표시 | 중복 |
|---|---|---:|---:|---:|---:|---:|
| drone_train | 2,346 → 2,346 | 4 | 5 | 1,707 | 150 | 0 |
| drone_test | 1,241 → 1,241 | 0 | 0 | 876 | 0 | 0 |
| drone_this_month | 106 → 106 | 0 | 0 | 62 | 0 | 0 |

## 2. 이상치 처리 상세 (train)

- `downtime_hours` 999 → NaN 4건: DR-0014 · DR-0074 · DR-0115 · DR-0141
- `maintenance_cost` > 10,000 → ÷100 5건:

| 드론 | 처리 전(만원) | 처리 후(만원) |
|---|---:|---:|
| DR-0046 | 15,000 | 150.00 |
| DR-0054 | 16,800 | 168.00 |
| DR-0066 | 16,200 | 162.00 |
| DR-0088 | 18,300 | 183.00 |
| DR-0115 | 19,000 | 190.00 |

## 3. 처리 뒤 남은 결측 (의도한 결측)

| 파일 | 컬럼별 결측 수 | 이유 |
|---|---|---|
| drone_train | {'downtime_hours': 4, 'days_since_last_maintenance': 150} | downtime NaN = 999 미입력, days_since NaN = 첫 정비 |
| drone_test | 없음 | - |
| drone_this_month | 없음 | - |

## 4. 점검

- 행 수 유지(삭제 없음): 통과
- 예방정비가 아닌데 고장 코드가 빈 행: 0건
- 처리 뒤 남은 999 · 비용 > 10,000: 0건
- train에 없는 드론: test 0대 · this_month 0대 (0이면 시간 피처를 train 기록에 이어 계산 가능)
- 종합: 모두 통과

## 5. 다음 단계에서 할 일 (이 스킬에서 하지 않음)

- `availability_rate`는 이번 달 데이터에 없는 '그 달 가동률'(정비 직후 알 수 없음) → 컬럼 선택 단계(README [4])에서 제외
- 시간 피처(최근 90일 고장 수 등)는 train → test → this_month를 이어 붙여 계산(README [3])
