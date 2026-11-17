"""README [8] 이번 달 재점검 20대 선정 · 제출물 (3) — drone-plan 스킬.
실행: python .claude/skills/drone-plan/scripts/plan.py
드론마다 이번 달 가장 최근 기록 하나로 판단하고, 확률 높은 순 20대를 고른다.
결과: artifacts/score_2026-01.csv (전체 순위), reports/2026-01_재점검계획.md"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import drone_lib as L  # noqa: E402

CMD = "`python .claude/skills/drone-plan/scripts/plan.py`"
ADVICE = {  # 고장 유형별 점검 권고 (정비 담당자가 최종 판단)
    "배터리": "배터리 셀 전압 · 충전 사이클 · 저온 보관 상태 점검",
    "모터": "모터 베어링 · 진동 · 프로펠러 균형 점검",
    "통신": "데이터링크 · 안테나 · 커넥터 접촉 점검",
    "기체": "기체 프레임 · 암 체결부 균열 점검",
    "센서": "IMU · GPS · 카메라 보정 상태 점검",
}


def advice(r):
    tips = []
    if r.maintenance_success == 0:
        tips.append("직전 정비 실패 → 재정비 우선")
    if r.fault_category in ADVICE:
        tips.append(ADVICE[r.fault_category])
    elif r.fail_count_90d >= 2:
        tips.append("최근 반복 고장 이력 → 주요 계통 전반 점검")
    else:
        tips.append("예방정비 뒤 기본 계통 점검")
    if r.fail_count_90d >= 3:
        tips.append(f"90일 고장 {int(r.fail_count_90d)}회 → 운용 제한 검토")
    return " · ".join(tips)


def main():
    model, card = L.load_model()
    thr = card["threshold"]
    df = L.load_all()
    month = L.split(df)["month"]
    latest = L.latest_per_drone(month).copy()
    latest["prob"] = model.predict_proba(latest[L.FEATURES])[:, 1]
    latest["reasons"] = L.reasons(model, latest[L.FEATURES])
    latest = latest.sort_values("prob", ascending=False).reset_index(drop=True)
    latest.insert(0, "rank", latest.index + 1)
    latest["advice"] = latest.apply(advice, axis=1)
    latest["over_threshold"] = (latest.prob >= thr).astype(int)

    cols = ["rank", "equipment_id", "equipment_type", "unit_code", "maintenance_date", "maintenance_type",
            "fault_category", "fail_count_90d", "prob", "over_threshold", "reasons", "advice"]
    save = latest[cols].assign(maintenance_date=latest.maintenance_date.dt.strftime("%Y-%m-%d"), prob=latest.prob.round(4))
    save.to_csv(L.ART / "score_2026-01.csv", index=False, encoding="utf-8-sig")
    meta = {"data": L.data_fingerprints(), "model": L.fingerprint(L.MODEL_PATH),
            "score": L.fingerprint(L.ART / "score_2026-01.csv"), "threshold": thr,
            "records": len(month), "drones": len(latest), "over_threshold": int(latest.over_threshold.sum())}
    L.PLAN_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    L.log_run("plan", drones=meta["drones"], over_threshold=meta["over_threshold"],
              top1=f"{save.equipment_id.iloc[0]} {save.prob.iloc[0]}", model=meta["model"], score=meta["score"])

    n_rec, n_drone = len(month), len(latest)
    n_over = int(latest.over_threshold.sum())
    top = save.head(L.CAPACITY)
    extra = save[(save["rank"] > L.CAPACITY) & (save.over_threshold == 1)]
    tbl = top.assign(확률=(top.prob * 100).round(1).astype(str) + "%")[
        ["rank", "equipment_id", "equipment_type", "unit_code", "maintenance_date", "maintenance_type", "확률", "reasons", "advice"]
    ].set_axis(["순위", "드론", "유형", "부대", "최근 정비일", "정비 구분", "확률", "위험을 올린 요인", "권고"], axis=1)
    by_type = top.groupby("equipment_type").size().rename("대수").reset_index().rename(columns={"equipment_type": "유형"})
    by_unit = top.groupby("unit_code").size().rename("대수").reset_index().rename(columns={"unit_code": "부대"}).sort_values("대수", ascending=False)

    out = ["# 2026-01 드론 재점검 계획", "",
           f"생성: {CMD} · 모델 `artifacts/drone_model.joblib`(train 2023 ~ 2024 학습) · 전체 순위 `artifacts/score_2026-01.csv`", "",
           f"추적 지문: 이번 달 데이터 `{meta['data']['this_month']}` · 모델 `{meta['model']}` · 점수 파일 `{meta['score']}` "
           "(`artifacts/plan_meta.json`, `python scripts/check.py`로 대조)", "",
           "## 1. 요약", "",
           f"- 이번 달 정비 기록 {n_rec}건 · 드론 {n_drone}대(여러 번 정비한 드론은 가장 최근 기록으로 판단)",
           f"- 위험 표시 기준 {thr:.2f}(검증 기간 비용 최소, `model_card.json`) 이상: **{n_over}대**",
           f"- 재점검 가능 {L.CAPACITY}대 → 확률 높은 순 {L.CAPACITY}대 선정. 20위 확률 {top.prob.iloc[-1] * 100:.1f}%", "",
           f"## 2. 재점검 대상 {L.CAPACITY}대", "", L.md_table(tbl), "",
           "- '위험을 올린 요인'은 모델 기여도(SHAP) 상위 3개 피처와 그 값이다. 권고는 고장 유형 · 정비 결과에 따른 점검 항목 예시다.", "",
           "### 유형별 · 부대별 대수", "", L.md_table(by_type), "", L.md_table(by_unit), "",
           f"## 3. 기준을 넘었지만 20대에 들지 못한 드론 ({len(extra)}대)", ""]
    if len(extra):
        out += [L.md_table(extra.assign(확률=(extra.prob * 100).round(1).astype(str) + "%")[
                    ["rank", "equipment_id", "equipment_type", "unit_code", "확률", "reasons"]]
                    .set_axis(["순위", "드론", "유형", "부대", "확률", "위험을 올린 요인"], axis=1)), "",
                "처리 방안:",
                f"1. 다음 달 재점검 목록 최우선 배치(2026-02 정비 기록이 생기면 다시 점수 매김)",
                "2. 그 전까지 비행 전 점검(배터리 전압 · 모터 진동 · 통신 상태)을 강화하고, 운용 일정에서 장거리 · 고하중 임무를 줄임",
                "3. 부대 정비반에 목록을 공유해 현장 판단으로 이번 달 추가 점검이 가능하면 우선 반영", ""]
    else:
        out += ["- 없음(기준 이상 드론이 모두 20대 안에 들었음)", ""]
    out += ["## 4. 모델의 한계 (`artifacts/model_card.json` limits)", ""] + [f"- {x}" for x in card["limits"]]
    out += ["- 이번 달 확률은 정답이 없어 맞았는지 아직 알 수 없다. 2026-02 기록이 쌓이면 적중 여부를 확인한다.", ""]
    (L.REP / "2026-01_재점검계획.md").write_text("\n".join(out), encoding="utf-8")

    print(f"이번 달 기록 {n_rec}건 · 드론 {n_drone}대 · 기준 {thr:.2f} 이상 {n_over}대 · 20대 밖 기준 이상 {len(extra)}대")
    print(top[["rank", "equipment_id", "equipment_type", "unit_code", "prob"]].head(5).to_string(index=False))
    print("저장: artifacts/score_2026-01.csv · reports/2026-01_재점검계획.md")


if __name__ == "__main__":
    main()
