"""지난달 재점검 계획 적중 확인 — drone-evaluate 스킬.

실제 모드 (다음 달 기록이 들어온 뒤):
    python .claude/skills/drone-evaluate/scripts/plan_hits.py --followup <2026-02 기록.csv> [<2026-03 기록.csv>]
    저장된 계획(artifacts/score_2026-01.csv)을 고치지 않은 그대로 쓰고(plan_meta 지문 대조),
    드론마다 이번 달 최근 정비일 뒤 1 ~ 30일 안에 사후 · 긴급정비가 있었는지 판정한다.
시험 모드 (지금 있는 데이터로 로직 검증):
    python .claude/skills/drone-evaluate/scripts/plan_hits.py --simulate 2025-12
    그 달 기록으로 같은 방식의 계획을 만들고, 이후 기록(test · this_month)으로 판정한다.
결과: reports/plan_hits_<달>[_sim].md, artifacts/plan_hits_<달>[_sim].json"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import drone_lib as L  # noqa: E402

CMD = "python .claude/skills/drone-evaluate/scripts/plan_hits.py"
WINDOW = 30


def judge(plan, follow):
    """plan: equipment_id · maintenance_date · prob · rank · equipment_age_years. follow: 이후 정비 기록.
    결과 열: result = 재고장 / 정상 / 보류(30일 창을 덮는 기록이 아직 없음), fail_date."""
    covered_until = follow["maintenance_date"].max()
    fails = follow[follow["maintenance_type"].isin(L.FAIL_TYPES)]
    res, fdate = [], []
    for eid, d0 in zip(plan.equipment_id, plan.maintenance_date):
        hit = fails[(fails.equipment_id == eid) & (fails.maintenance_date > d0) &
                    (fails.maintenance_date <= d0 + pd.Timedelta(days=WINDOW))]
        if len(hit):
            res.append("재고장")
            fdate.append(hit.maintenance_date.min().strftime("%Y-%m-%d"))
        elif covered_until >= d0 + pd.Timedelta(days=WINDOW):
            res.append("정상")
            fdate.append("")
        else:
            res.append("보류")
            fdate.append("")
    return plan.assign(result=res, fail_date=fdate), covered_until


def summarize(j, thr):
    done = j[j.result != "보류"]
    y = (done.result == "재고장").astype(int)
    top = done[done["rank"] <= L.CAPACITY]
    old = done.sort_values("equipment_id", kind="stable").nlargest(L.CAPACITY, "equipment_age_years")
    k = min(L.CAPACITY, len(done))
    hits = int((top.result == "재고장").sum())
    missed = int(y.sum()) - hits
    over = done[done.prob >= thr]
    return {"drones": len(j), "judged": len(done), "pending": int((j.result == "보류").sum()),
            "failures": int(y.sum()), "base_rate": round(float(y.mean()), 3) if len(done) else None,
            "top20_judged": len(top), "top20_hits": hits,
            "oldest_hits": int((old.result == "재고장").sum()),
            "random_expected": round(k * float(y.mean()), 1) if len(done) else None,
            "over_threshold": len(over), "over_threshold_hits": int((over.result == "재고장").sum()),
            "missed": missed, "cost": missed * L.COST_MISS + L.CAPACITY * L.COST_CHECK}


def write(tag, month, j, s, covered, source, thr):
    L.REP.mkdir(exist_ok=True)
    (L.ART / f"plan_hits_{tag}.json").write_text(json.dumps({"month": month, "source": source, "threshold": thr,
                                                              "covered_until": f"{covered:%Y-%m-%d}", **s},
                                                             ensure_ascii=False, indent=2), encoding="utf-8")
    top = j[j["rank"] <= L.CAPACITY].assign(확률=(j.prob * 100).round(1).astype(str) + "%",
                                            최근정비일=j.maintenance_date.dt.strftime("%Y-%m-%d"))
    tbl = top[["rank", "equipment_id", "equipment_type", "최근정비일", "확률", "result", "fail_date"]].set_axis(
        ["순위", "드론", "유형", "최근 정비일", "확률", "판정", "첫 재고장일"], axis=1)
    missed = j[(j["rank"] > L.CAPACITY) & (j.result == "재고장")]
    pct = lambda a, b: f"{a / b * 100:.0f}%" if b else "-"  # noqa: E731
    o = [f"# {month} 재점검 계획 적중 확인{' (시험 모드)' if tag.endswith('_sim') else ''}", "",
         f"생성: `{CMD} {source}` · 결과 `artifacts/plan_hits_{tag}.json`", "",
         f"판정 규칙: 드론의 {month} 최근 정비일 뒤 1 ~ {WINDOW}일 안에 사후 · 긴급정비가 있으면 '재고장'(README 정답 정의). "
         f"후속 기록이 {covered:%Y-%m-%d}까지라 30일 창을 다 덮지 못한 드론은 '보류'.", "",
         "## 1. 요약", "",
         L.md_table(pd.DataFrame([{
             "판정 드론": f"{s['judged']} / {s['drones']} (보류 {s['pending']})",
             "실제 재고장": f"{s['failures']} ({s['base_rate']})",
             f"계획 {L.CAPACITY}대 적중": f"{s['top20_hits']} / {s['top20_judged']} ({pct(s['top20_hits'], s['top20_judged'])})",
             "오래된 순 20대": s["oldest_hits"], "무작위 기대값": s["random_expected"],
             f"기준 {thr:.2f} 이상 적중": f"{s['over_threshold_hits']} / {s['over_threshold']}",
             "20대 밖 놓친 재고장": s["missed"], "비용(만원)": f"{s['cost']:,}"}]), "{:,.1f}"), "",
         f"- 비용 = 놓친 재고장 {s['missed']} × {L.COST_MISS} + 재점검 {L.CAPACITY} × {L.COST_CHECK} (README 가정)",
         f"- 재고장 잡은 비율(재현율): {pct(s['top20_hits'], s['failures'])}", "",
         f"## 2. 계획 {L.CAPACITY}대 판정", "", L.md_table(tbl), "",
         f"## 3. 계획 밖에서 재고장 난 드론 ({len(missed)}대)", ""]
    if len(missed):
        o.append(L.md_table(missed.assign(확률=(missed.prob * 100).round(1).astype(str) + "%")[
            ["rank", "equipment_id", "equipment_type", "확률", "fail_date"]].set_axis(["순위", "드론", "유형", "확률", "첫 재고장일"], axis=1)))
    else:
        o.append("- 없음")
    o += ["", "## 4. 읽을 때 주의", "",
          "- **개입 효과:** 계획한 20대는 실제로 재점검을 받는다. 재점검으로 고장을 막았다면 '정상'으로 판정되므로, "
          "실제 운용에서는 적중 수가 모델 실력보다 낮게 나온다(좋은 일이다). 모델 실력은 시험 모드 · 2025 자체 평가로 본다.",
          "- '보류' 드론은 다음 달 기록이 더 들어온 뒤 다시 실행해 판정한다.",
          "- 판정 결과로 지난 계획 · 모델 · 임계값을 고치지 않는다. 다음 학습에 반영할지는 별도로 정한다.", ""]
    (L.REP / f"plan_hits_{tag}.md").write_text("\n".join(o), encoding="utf-8")


def sim_plan(df, model, month):
    """지난 달로 drone-plan과 같은 방식의 계획을 만든다(드론별 최근 기록 → 확률 순위)."""
    rows = df[df.maintenance_date.dt.strftime("%Y-%m") == month]
    if rows.empty or (rows.part == "train").any():
        raise SystemExit(f"{month}: 시험 모드는 학습에 쓰지 않은 2025년 달만 가능합니다.")
    plan = L.latest_per_drone(rows).copy()
    plan["prob"] = model.predict_proba(plan[L.FEATURES])[:, 1]
    plan = plan.sort_values("prob", ascending=False, kind="stable").reset_index(drop=True)
    plan["rank"] = plan.index + 1
    return plan, df[df.maintenance_date > pd.Period(month).end_time]


def simulate_all(df, model, thr):
    """2025년 12개월 모두 시험 모드로 판정해 월별 표 · 합계를 만든다."""
    rows = []
    for month in [f"2025-{m:02d}" for m in range(1, 13)]:
        j, _ = judge(*sim_plan(df, model, month))
        rows.append({"month": month, **summarize(j, thr)})
    t = pd.DataFrame(rows)
    tot = {k: float(t[k].sum()) for k in ["judged", "pending", "failures", "top20_hits", "oldest_hits",
                                           "random_expected", "missed", "cost"]}
    (L.ART / "plan_hits_2025_sim.json").write_text(json.dumps({"months": rows, "total": tot}, ensure_ascii=False, indent=2),
                                                   encoding="utf-8")
    show = t[["month", "judged", "failures", "top20_hits", "oldest_hits", "random_expected", "missed", "cost"]].set_axis(
        ["달", "판정 드론", "실제 재고장", "계획 20대 적중", "오래된 순", "무작위 기대", "놓친 재고장", "비용(만원)"], axis=1)
    o = ["# 2025년 12개월 재점검 계획 적중 확인 (시험 모드)", "",
         f"생성: `{CMD} --simulate all` · 결과 `artifacts/plan_hits_2025_sim.json`", "",
         "매달 drone-plan과 같은 방식(드론별 최근 기록 → 확률 상위 20대)으로 계획을 만들고, 이후 기록으로 30일 안 재고장을 판정했다. "
         "모델은 2023 ~ 2024로만 학습했으므로 2025는 처음 보는 기간이다. 실제 재점검을 하지 않은 가정이라 개입 효과가 없다.", "",
         L.md_table(show, "{:,.1f}"), "",
         f"- 합계: 계획 20대 적중 **{tot['top20_hits']:.0f}** · 오래된 순 {tot['oldest_hits']:.0f} · 무작위 기대 {tot['random_expected']:.1f} "
         f"/ 실제 재고장 {tot['failures']:.0f}대 중 {tot['top20_hits'] / max(tot['failures'], 1) * 100:.0f}% 포착 · 놓친 재고장 {tot['missed']:.0f} · 비용 {tot['cost']:,.0f}만원",
         f"- 이 합계는 drone-evaluate의 드론 단위 월 20대 적중(`evaluation.json` top20_hits_12m)과 같아야 한다(drone-verify가 대조).", ""]
    (L.REP / "plan_hits_2025_sim.md").write_text("\n".join(o), encoding="utf-8")
    L.log_run("plan_hits 2025_sim", **{k: tot[k] for k in ("failures", "top20_hits", "oldest_hits", "random_expected")})
    print(f"2025 12개월: 계획 20대 적중 {tot['top20_hits']:.0f} · 오래된 순 {tot['oldest_hits']:.0f} · 무작위 {tot['random_expected']:.1f}"
          f" · 실제 재고장 {tot['failures']:.0f} · 비용 {tot['cost']:,.0f}만원")
    print("저장: reports/plan_hits_2025_sim.md · artifacts/plan_hits_2025_sim.json")
    return t, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--followup", nargs="*", help="다음 달(이후) 정비 기록 CSV")
    ap.add_argument("--simulate", help="지난 달로 시험: YYYY-MM (2025-01 ~ 2025-12) 또는 all(12개월)")
    a = ap.parse_args()
    model, card = L.load_model()
    thr = card["threshold"]
    df = L.load_all()

    if a.simulate == "all":
        simulate_all(df, model, thr)
        return
    if a.simulate:
        month = a.simulate
        plan, follow = sim_plan(df, model, month)
        tag, source = f"{month}_sim", f"--simulate {month}"
    else:
        month = "2026-01"
        meta = json.loads(L.PLAN_META.read_text(encoding="utf-8"))
        score_path = L.ART / "score_2026-01.csv"
        if L.fingerprint(score_path) != meta["score"]:
            raise SystemExit("score_2026-01.csv 지문이 plan_meta.json과 다릅니다 — 계획이 바뀌었으므로 판정하지 않음")
        if not a.followup:
            print(f"후속 기록이 없습니다. 2026-02 정비 기록 CSV를 받으면 실행하세요:\n  {CMD} --followup <파일.csv>")
            print(f"(로직 확인은 시험 모드: {CMD} --simulate 2025-12)")
            return
        plan = pd.read_csv(score_path, parse_dates=["maintenance_date"])
        ages = L.latest_per_drone(L.split(df)["month"])[["equipment_id", "equipment_age_years"]]
        plan = plan.merge(ages, on="equipment_id", how="left")
        follow = pd.concat([pd.read_csv(p, encoding="utf-8-sig", parse_dates=["maintenance_date"]) for p in a.followup],
                           ignore_index=True)
        need = {"equipment_id", "maintenance_date", "maintenance_type"}
        if not need <= set(follow.columns):
            raise SystemExit(f"후속 기록에 필요한 열이 없습니다: {sorted(need - set(follow.columns))}")
        follow = follow[follow.maintenance_date > pd.Period(month).end_time]
        tag, source = month, "--followup " + " ".join(Path(p).name for p in a.followup)

    j, covered = judge(plan, follow)
    s = summarize(j, thr)
    write(tag, month, j, s, covered, source, thr)
    L.log_run(f"plan_hits {tag}", **{k: s[k] for k in ("judged", "pending", "failures", "top20_hits", "oldest_hits", "random_expected")})
    print(f"{month} 판정 {s['judged']}/{s['drones']}대(보류 {s['pending']}) · 실제 재고장 {s['failures']}대")
    print(f"계획 20대 적중 {s['top20_hits']}/{s['top20_judged']} · 오래된 순 {s['oldest_hits']} · 무작위 기대 {s['random_expected']}"
          f" · 놓친 재고장 {s['missed']} · 비용 {s['cost']:,}만원")
    print(f"저장: reports/plan_hits_{tag}.md · artifacts/plan_hits_{tag}.json")


if __name__ == "__main__":
    main()
