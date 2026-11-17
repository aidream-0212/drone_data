---
name: drone-eda
description: 드론 정비 기록 원본 3개를 읽어 구조 · 결측 원인 · 이상치 · 재고장 비율(정비 구분 · 드론 유형 · 계절 · 고장 유형 · 분기) · 교차 패턴을 reports/eda_summary.md에 정리한다. 데이터 살펴보기, EDA, 분포 · 결측 · 이상치 확인, 패턴 찾기(README [1])를 요청할 때 쓴다.
---

# drone-eda — 데이터 살펴보기 (README [1])

## 실행 (drone_data 폴더, 가상환경 켠 상태)
```powershell
python .claude/skills/drone-eda/scripts/eda.py
```

## 순서
1. 스크립트를 실행하고 콘솔 출력을 그대로 보여 준다.
2. `reports/eda_summary.md`를 읽고 다음을 표로 요약해 답한다.
   - 구조(행 · 기간 · 드론 · 정답 열 · `availability_rate` 유무)
   - 결측 원인(입력 실수인지, 원래 값이 없는 것인지)
   - 이상치(값 · 건수 · 이상값을 뺀 최댓값)
   - 재고장 비율과 눈에 띄는 패턴(드론 유형 · 계절 · 고장 유형)
3. 다음 단계로 `drone-preprocess`(README [2])를 제안한다.

## 지킬 것
- 원본만 읽는다. 처리 · 그래프 파일을 만들지 않는다(그래프는 보고서 단계).
- 패턴은 '집계 결과'로 쓰고, 원인은 '추정'이라고 적는다(예: 겨울 배터리 고장 → 저온 영향 추정).
- 숫자는 `reports/eda_summary.md`에서 인용하고 출처를 적는다.
