"""README 5. 평가 — drone-evaluate 스킬.  실행: python .claude/skills/drone-evaluate/scripts/evaluate.py
1) 제출 파일 형식 점검  2) 정답 재현 규칙을 train으로 검증  3) 재현한 2025 정답으로 시험 기간 자체 평가
※ 재현 정답은 '평가 확인용'이다. 모델 · 피처 · 임계값 선택에 쓰지 않는다(쓰면 시험 기간 누수).
   공식 점수는 강사가 가진 정답으로 매긴다. 결과: artifacts/evaluation.json, reports/evaluation.md"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import drone_lib as L  # noqa: E402

CMD = "`python .claude/skills/drone-evaluate/scripts/evaluate.py`"
Y = "y_rebuilt"


def rebuild_target(df):
    """README 정의 그대로: 정비 뒤 1 ~ 30일 안에 같은 드론의 사후 · 긴급정비가 있으면 1."""
    y = np.zeros(len(df), dtype=int)
    day = df["maintenance_date"].to_numpy().astype("datetime64[D]")
    fail = df["maintenance_type"].isin(L.FAIL_TYPES).to_numpy()
    for _, pos in df.groupby("equipment_id", sort=False).indices.items():
        d, f = day[pos], fail[pos]
        for j, i in enumerate(pos):
            gap = (d - d[j]).astype(int)
            y[i] = int(np.any(f & (gap >= 1) & (gap <= 30)))
    return y


def check_submission():
    sub = pd.read_csv(L.SUBMIT_PATH, dtype={"maintenance_date": str})
    raw = pd.read_csv(L.PARTS["test"], dtype={"maintenance_date": str})
    key = lambda d: sorted(zip(d.equipment_id, d.maintenance_date.str[:10]))  # noqa: E731
    checks = {
        "열 이름 = equipment_id, maintenance_date, prob": list(sub.columns) == ["equipment_id", "maintenance_date", "prob"],
        f"행 수 = drone_test.csv ({len(raw):,})": len(sub) == len(raw),
        "드론 · 정비일 조합이 drone_test.csv와 같음": key(sub) == key(raw),
        "날짜 형식 YYYY-MM-DD": bool(sub.maintenance_date.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()),
        "prob 결측 없음 · 0 ~ 1": bool(sub.prob.notna().all() and sub.prob.between(0, 1).all()),
    }
    return sub, checks


def main():
    sub, checks = check_submission()
    _, card = L.load_model()
    thr = card["threshold"]
    t600 = card["threshold_by_miss_cost"]["600"]["threshold"]

    df = L.load_all()
    df[Y] = rebuild_target(df)
    tr = df[df.part == "train"]
    match = float((tr[Y] == tr[L.TARGET]).mean())

    te = df[df.part == "test"].copy()
    te["_d"] = te.maintenance_date.dt.strftime("%Y-%m-%d")
    s = sub.assign(_d=sub.maintenance_date)
    te = te.merge(s[["equipment_id", "_d", "prob"]], on=["equipment_id", "_d"], how="left", validate="1:1")
    y, p = te[Y], te["prob"]
    m = L.monthly_topk(te, "prob", y_col=Y)
    o = L.monthly_topk(te, "equipment_age_years", y_col=Y)
    top = m[["month", "n", "hits"]].rename(columns={"hits": "model"}).assign(oldest=o.hits.to_numpy(), random=m.random.to_numpy())
    hits = {k: float(top[k].sum()) for k in ["model", "oldest", "random"]}
    costs = {}
    for miss, t in [(300, thr), (600, t600)]:
        c = L.cost_table(y, p, miss=miss)
        costs[miss] = c[np.isclose(c.threshold, t)].iloc[0].to_dict()
    res = {
        "submission_checks": checks, "all_pass": all(checks.values()),
        "rebuild_rule_match_train": round(match, 4),
        "test_2025": {"pr_auc": round(float(average_precision_score(y, p)), 3),
                      "roc_auc": round(float(roc_auc_score(y, p)), 3),
                      "base_rate": round(float(y.mean()), 3), "n": len(te), "positives": int(y.sum()),
                      "top20_hits_12m": hits,
                      "cost_at_val_threshold": {str(k): {kk: (float(vv) if kk == "threshold" else int(vv)) for kk, vv in v.items()}
                                                for k, v in costs.items()}},
        "validation_ref": card["validation"],
        "note": "정답은 README 정의로 재현한 값(train에서 일치율 확인). 강사 채점과 다를 수 있으며 모델 · 임계값 선택에 쓰지 않았다.",
        "lineage": {"data": L.data_fingerprints(), "model": L.fingerprint(L.MODEL_PATH),
                    "submission": L.fingerprint(L.SUBMIT_PATH)},
    }
    L.ART.mkdir(exist_ok=True)
    (L.ART / "evaluation.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    top.to_csv(L.ART / "test_monthly_top20.csv", index=False, encoding="utf-8-sig")
    L.log_run("evaluate", test_pr_auc=res["test_2025"]["pr_auc"], top20_test=hits["model"],
              format_pass=res["all_pass"], model=res["lineage"]["model"], submission=res["lineage"]["submission"])

    t, v = res["test_2025"], card["validation"]
    out = ["# 평가 기록 (README 5. 평가)", "", f"생성: {CMD} · 결과 `artifacts/evaluation.json`", "",
           "## 1. 제출 파일 형식 점검 (`outputs/test_predictions_2025.csv`)", "",
           "| 항목 | 결과 |", "|---|---|"] + [f"| {k} | {'통과' if ok else '**실패**'} |" for k, ok in checks.items()] + [
           "", "## 2. 정답 재현 규칙 검증", "",
           f"- 규칙: '정비 뒤 1 ~ 30일 안에 같은 드론의 사후 · 긴급정비가 있으면 1'(README 1장 정의)",
           f"- train 2,346건에서 실제 정답과 일치율 **{match * 100:.2f}%** → 같은 규칙으로 2025 정답을 재현(2025-12 행은 2026-01 기록으로 판정)", "",
           "## 3. 시험 기간(2025) 자체 평가 — 재현 정답 기준", "",
           L.md_table(pd.DataFrame([
               {"구분": "검증 2024-07~12 (model_card)", "PR-AUC": v["pr_auc"], "기준선(재고장 비율)": v["base_rate"], "ROC-AUC": v["roc_auc"], "건수": v["n"]},
               {"구분": "시험 2025 (재현 정답)", "PR-AUC": t["pr_auc"], "기준선(재고장 비율)": t["base_rate"], "ROC-AUC": t["roc_auc"], "건수": t["n"]}])), "",
           "### 월 20대 적중 수 (2025, 12개월)", "", L.md_table(top, "{:,.1f}"), "",
           f"- 합계: 모델 **{hits['model']:.0f}** · 오래된 순 {hits['oldest']:.0f} · 무작위(기대값) {hits['random']:.1f}", "",
           "### 검증 기간에서 고른 기준을 2025에 그대로 쓰면", "",
           L.md_table(pd.DataFrame([{"놓친 재고장 비용(만원)": k, **vv} for k, vv in t["cost_at_val_threshold"].items()])), "",
           f"- {res['note']}", ""]
    (L.REP / "evaluation.md").write_text("\n".join(out), encoding="utf-8")

    for k, ok in checks.items():
        print(("통과 " if ok else "실패 ") + k)
    print(f"재현 규칙 train 일치율 {match * 100:.2f}%")
    print(f"2025 PR-AUC {t['pr_auc']} (기준선 {t['base_rate']}) · ROC-AUC {t['roc_auc']} · 재고장 {t['positives']}/{t['n']}")
    print(f"2025 월 20대 적중 합: 모델 {hits['model']:.0f} · 오래된 순 {hits['oldest']:.0f} · 무작위 {hits['random']:.1f}")
    print("저장: artifacts/evaluation.json · reports/evaluation.md")


if __name__ == "__main__":
    main()
