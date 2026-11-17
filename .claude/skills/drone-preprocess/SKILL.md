---
name: drone-preprocess
description: 드론 정비 기록(data/drone_train · drone_test · drone_this_month.csv)의 결측 · 이상치를 정해진 기준으로 처리해 artifacts/clean/에 저장하고 처리 기록(reports/preprocess_log.md)을 남긴다. 데이터 전처리, 정제, 결측 · 이상치 처리, 데이터 처리 기준(README [2])을 요청할 때 쓴다.
---

# drone-preprocess — 드론 정비 기록 전처리

원본 `data/`는 고치지 않는다. 처리 기준은 `drone_lib.clean()` 한 곳에 있고, 스크립트는 이를 세 파일에 똑같이 적용한 뒤 처리 기록을 남긴다(이후 스킬도 같은 함수를 쓴다).

## 실행 (drone_data 폴더, 가상환경 켠 상태)
```powershell
python .claude/skills/drone-preprocess/scripts/preprocess.py
```

## 처리 기준 (README [2])
| # | 대상 | 처리 | 근거 |
|---|---|---|---|
| 1 | `downtime_hours` = 999 | 행은 두고 값만 결측(NaN) | 다음 큰 값이 74.0이라 999는 실제 시간이 아닌 미입력 표시값 |
| 2 | `maintenance_cost` > 10,000 | 100으로 나눔 | 다음 큰 값이 478이고, 나누면 150 ~ 190으로 정상 범위 → 자릿수 입력 실수 |
| 3 | `fault_code` · `fault_category` 결측 | `"N/A"`로 채움(최빈값 X) | 결측이 예방정비 행과 정확히 일치 → 고장이 없어 원래 값이 없음 |
| 4 | `days_since_last_maintenance` 결측 | 비워 두고 `is_first_maintenance`(0/1) 열 추가 | 드론마다 첫 정비 1건씩(150건) → 직전 정비가 없는 구조적 결측 |
| 5 | 행 삭제 | 하지 않음 | 처리 전후 행 수가 같아야 함(스크립트가 확인) |
| 6 | 정렬 · 날짜 | `equipment_id`, `maintenance_date` 순 정렬, 날짜는 YYYY-MM-DD | 시간 피처(README [3])를 드론별 날짜순으로 계산하기 위함 |

## 출력
- `artifacts/clean/drone_train_clean.csv`, `drone_test_clean.csv`, `drone_this_month_clean.csv` (utf-8-sig)
- `reports/preprocess_log.md` — 파일별 처리 건수, 해당 드론 번호, 점검 결과

## 지킬 것
- 원본 `data/*.csv`를 덮어쓰지 않는다.
- 컬럼은 지우지 않는다. `availability_rate`(누수) 제외는 컬럼 선택 단계(README [4])에서 한다.
- 예방정비가 아닌데 고장 코드가 빈 행, 처리 뒤에도 남은 이상값이 있으면 고치지 말고 로그에 '확인 필요'로 적는다.
- 보고서에 전처리 숫자를 쓸 때는 `reports/preprocess_log.md`의 값만 인용하고 출처를 적는다.
- 실행 뒤에는 콘솔 출력(점검 결과)을 그대로 보여 준다.
