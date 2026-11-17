"""README [5] 학습 · 검증, [6] 위험 표시 기준, [7] 시험 기간 예측 제출 — drone-train 스킬.
실행: python .claude/skills/drone-train/scripts/train.py
  1) fit(~2024-06) 학습 → val(2024-07~12) 성능 · 기준선 · 임계값(300/600/150만원)
  2) train 전체(2023~2024) 재학습 → 최종 모델 → test 1,241건 예측 제출 파일
시험 기간(2025)으로는 아무것도 고르지 않는다."""
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import drone_lib as L  # noqa: E402

CMD = "`python .claude/skills/drone-train/scripts/train.py`"


def main():
    df = L.load_all()
    s = L.split(df)
    fit, val, train, test = s["fit"], s["val"], s["train"], s["test"].copy()

    # 1) 검증
    m_val = L.make_model().fit(fit[L.FEATURES], fit[L.TARGET])
    val = val.assign(prob=m_val.predict_proba(val[L.FEATURES])[:, 1])
    y = val[L.TARGET]
    metrics = {"pr_auc": round(float(average_precision_score(y, val.prob)), 3),
               "roc_auc": round(float(roc_auc_score(y, val.prob)), 3),
               "base_rate": round(float(y.mean()), 3), "n": len(val), "positives": int(y.sum())}
    mt = L.monthly_topk(val, "prob")
    old = L.monthly_topk(val, "equipment_age_years")
    top = mt[["month", "n", "hits"]].rename(columns={"hits": "model"}).assign(
        oldest=old["hits"].to_numpy(), random=mt["random"].to_numpy())
    hits = {k: float(top[k].sum()) for k in ["model", "oldest", "random"]}

    th, ct = {}, {}
    for miss in (150, 300, 600):
        c = L.cost_table(y, val.prob, miss=miss)
        ct[miss] = c
        th[miss] = c.loc[c.cost.idxmin()].to_dict()
    thr = th[L.COST_MISS]["threshold"]

    # 2) 최종 모델(train 전체) → 시험 기간 예측
    model = L.make_model().fit(train[L.FEATURES], train[L.TARGET])
    test["prob"] = model.predict_proba(test[L.FEATURES])[:, 1]
    sub = pd.DataFrame({"equipment_id": test.equipment_id,
                        "maintenance_date": test.maintenance_date.dt.strftime("%Y-%m-%d"),
                        "prob": test.prob.round(6)})
    raw_test = L.load_raw("test")
    if not len(sub) == len(raw_test) == 1241:
        raise SystemExit(f"제출 행 수 {len(sub)}가 drone_test.csv({len(raw_test)}) · README(1,241)와 다릅니다 — 저장하지 않음")
    L.OUTPUTS.mkdir(exist_ok=True)
    sub.to_csv(L.SUBMIT_PATH, index=False, encoding="utf-8")

    imp = pd.Series(model["model"].booster_.feature_importance("gain"),
                    index=model["pre"].get_feature_names_out())
    groups = {c: next((k for k in L.CAT_COLS if c.startswith(k + "_")), c) for c in imp.index}
    imp = (imp.groupby(groups).sum() / imp.sum()).sort_values(ascending=False).round(3)

    # 저장
    L.ART.mkdir(exist_ok=True)
    joblib.dump(model, L.MODEL_PATH)
    val[["equipment_id", "maintenance_date", "equipment_age_years", L.TARGET, "prob"]].to_csv(
        L.ART / "val_predictions.csv", index=False, encoding="utf-8-sig")
    top.to_csv(L.ART / "val_monthly_top20.csv", index=False, encoding="utf-8-sig")
    card = {
        "model": "LightGBM + 원-핫 (drone_lib.make_model)",
        "target": "정비 뒤 30일 안 재고장(사후 · 긴급정비) 여부",
        "split": {"fit": f"~ {L.FIT_END} ({len(fit):,}건)", "val": f"{L.VAL_START} ~ {L.VAL_END} ({len(val):,}건)",
                  "final_train": f"2023-01-01 ~ 2024-12-31 ({len(train):,}건)", "test": f"2025 ({len(test):,}건, 정답 없음)"},
        "features": L.FEATURES, "excluded": L.EXCLUDED,
        "validation": {**metrics, "top20_hits_6m": hits},
        "threshold": thr, "threshold_rule": f"검증 기간 비용 최소: 놓친 재고장 {L.COST_MISS}만원 × 건수 + 재점검 {L.COST_CHECK}만원 × 기준 이상 건수",
        "threshold_by_miss_cost": {str(k): {kk: (float(vv) if kk == "threshold" else int(vv)) for kk, vv in v.items()} for k, v in th.items()},
        "capacity_per_month": L.CAPACITY,
        "importance_gain": imp.to_dict(),
        "submission": {"path": "outputs/test_predictions_2025.csv", "rows": len(sub),
                       "prob_mean": round(float(sub.prob.mean()), 3), "flag_ge_threshold": int((sub.prob >= thr).sum())},
        "limits": ["교육용 가상 데이터로 학습했다. 실제 드론 운용에 그대로 쓰지 않는다.",
                   "학습 기간(2023 ~ 2024)보다 재고장 비율이 오르는 추세여서, 확률 · 기준이 뒤 기간에 낮게 맞을 수 있다.",
                   "확률은 '정비 뒤 30일' 기준이다. 정비 기록이 없는 드론은 판단하지 않는다.",
                   "최종 판단은 정비 담당자가 한다. 모델은 재점검 순서를 정하는 참고 자료다."],
        "lineage": {"data": L.data_fingerprints(), "model": L.fingerprint(L.MODEL_PATH),
                    "submission": L.fingerprint(L.SUBMIT_PATH)},
    }
    L.CARD_PATH.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    L.log_run("train", val_pr_auc=metrics["pr_auc"], threshold=thr, top20_val=hits["model"],
              model=card["lineage"]["model"], submission=card["lineage"]["submission"])

    # 기록 md
    near = lambda c, t: c[(c.threshold >= t - 0.03) & (c.threshold <= t + 0.03)]  # noqa: E731
    out = ["# 학습 · 검증 기록 (README [5] · [6] · [7])", "", f"생성: {CMD} · 모델 정보 `artifacts/model_card.json`", "",
           "## 1. 기간 분할 (무작위 아님)", "", L.md_table(pd.DataFrame([card["split"]])), "",
           "## 2. 검증 기간 성능 (fit 모델)", "",
           L.md_table(pd.DataFrame([{"PR-AUC": metrics["pr_auc"], "기준선(재고장 비율)": metrics["base_rate"],
                                     "ROC-AUC": metrics["roc_auc"], "건수": metrics["n"], "재고장": metrics["positives"]}])), "",
           "### 월 20대 적중 수 (검증 6개월)", "", L.md_table(top, "{:,.1f}"), "",
           f"- 합계: 모델 {hits['model']:.0f} · 오래된 순 {hits['oldest']:.0f} · 무작위(기대값) {hits['random']:.1f}", "",
           "## 3. 위험 표시 기준 (검증 기간에서 선택)", "",
           L.md_table(pd.DataFrame([{"놓친 재고장 비용(만원)": k, **v} for k, v in card["threshold_by_miss_cost"].items()])), "",
           f"- 300만원 기준 {thr:.2f} → 600만원이면 {th[600]['threshold']:.2f}"
           f" (기준 이상 {int(th[300]['flagged'])} → {int(th[600]['flagged'])}건, 놓침 {int(th[300]['missed'])} → {int(th[600]['missed'])}건)", "",
           "### 300만원 기준 주변", "", L.md_table(near(ct[300], thr), "{:,.2f}"), "",
           "### 600만원 기준 주변", "", L.md_table(near(ct[600], th[600]["threshold"]), "{:,.2f}"), "",
           "## 4. 최종 모델 · 제출", "",
           f"- 최종 모델: train 전체 {len(train):,}건으로 재학습 → `artifacts/drone_model.joblib`",
           f"- 제출 파일: `outputs/test_predictions_2025.csv` {len(sub):,}행 (열 equipment_id, maintenance_date, prob) · "
           f"평균 확률 {card['submission']['prob_mean']} · 기준 {thr:.2f} 이상 {card['submission']['flag_ge_threshold']}건", "",
           "### 피처 중요도 (gain 비율, 최종 모델)", "",
           L.md_table(imp.rename(lambda k: f"{L.FEATURE_KO.get(k, k)} ({k})").reset_index().set_axis(["피처", "비율"], axis=1)), ""]
    (L.REP / "train_log.md").write_text("\n".join(out), encoding="utf-8")

    print(f"검증 PR-AUC {metrics['pr_auc']} (기준선 {metrics['base_rate']}) · ROC-AUC {metrics['roc_auc']}")
    print(f"검증 월 20대 적중 합: 모델 {hits['model']:.0f} · 오래된 순 {hits['oldest']:.0f} · 무작위 {hits['random']:.1f}")
    for k, v in th.items():
        print(f"임계값({k}만원): {v['threshold']:.2f} · 기준 이상 {int(v['flagged'])} · 놓침 {int(v['missed'])} · 비용 {int(v['cost']):,}")
    print(f"제출: {L.SUBMIT_PATH.relative_to(ROOT)} {len(sub)}행 · 상위 피처: {', '.join(imp.index[:3])}")


if __name__ == "__main__":
    main()
