"""드론 정비 기록 전처리 — drone-preprocess 스킬.

실행 (drone_data 폴더):  python .claude/skills/drone-preprocess/scripts/preprocess.py
원본 data/*.csv는 읽기만 하고, 결과는 artifacts/clean/ 와 reports/preprocess_log.md 에 쓴다.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]  # drone_data/
sys.path.insert(0, str(ROOT))
import drone_lib as L  # noqa: E402  처리 기준은 drone_lib.clean() 한 곳에만 둔다

DATA = L.DATA
OUT = L.ART / "clean"
LOG = L.REP / "preprocess_log.md"
FILES = list(L.PARTS)
DOWNTIME_MISSING_CODE, COST_LIMIT, PM = L.DOWNTIME_MISSING_CODE, L.COST_LIMIT, L.PM


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """drone_lib.clean()을 적용하고, 처리 전후를 비교해 처리 기록을 돌려준다."""
    log = {"rows_in": len(raw)}
    m = raw["downtime_hours"] == DOWNTIME_MISSING_CODE
    log["downtime_999"] = raw.loc[m, "equipment_id"].tolist()
    m = raw["maintenance_cost"] > COST_LIMIT
    log["cost_fix"] = [(e, b, round(b / 100, 2)) for e, b in
                       zip(raw.loc[m, "equipment_id"], raw.loc[m, "maintenance_cost"])]
    na = raw["fault_code"].isna() | raw["fault_category"].isna()
    is_pm = raw["maintenance_type"] == PM
    log["fault_na_pm"] = int((na & is_pm).sum())
    log["fault_na_not_pm"] = raw.loc[na & ~is_pm, "equipment_id"].tolist()  # 확인 필요

    df = L.clean(raw).drop(columns=["season"])
    log["first_maint"] = int(df["is_first_maintenance"].sum())
    df = df.sort_values(["equipment_id", "maintenance_date"], kind="stable").reset_index(drop=True)

    # 점검
    log["rows_out"] = len(df)
    log["dup"] = int(df.duplicated().sum())
    log["left_999"] = int((df["downtime_hours"] == DOWNTIME_MISSING_CODE).sum())
    log["left_cost"] = int((df["maintenance_cost"] > COST_LIMIT).sum())
    log["na_after"] = {c: int(v) for c, v in df.isna().sum().items() if v > 0}
    return df, log


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    logs, ids = {}, {}
    for name in FILES:
        raw = pd.read_csv(DATA / f"drone_{name}.csv", encoding="utf-8-sig")
        df, logs[name] = clean(raw)
        df = df.drop(columns=["part"], errors="ignore")
        ids[name] = set(df["equipment_id"])
        out = df.copy()
        out["maintenance_date"] = out["maintenance_date"].dt.strftime("%Y-%m-%d")
        out.to_csv(OUT / f"drone_{name}_clean.csv", index=False, encoding="utf-8-sig")

    unseen = {n: sorted(ids[n] - ids["train"]) for n in ["test", "this_month"]}

    # 콘솔 점검 결과
    print("파일        행(전→후)  999→NaN  비용÷100  고장N/A  첫정비  중복  남은이상값  확인필요")
    for n, g in logs.items():
        bad = len(g["fault_na_not_pm"]) + g["left_999"] + g["left_cost"]
        print(f"{n:<11} {g['rows_in']:>4}→{g['rows_out']:<4}  {len(g['downtime_999']):>6}  {len(g['cost_fix']):>7}"
              f"  {g['fault_na_pm']:>6}  {g['first_maint']:>5}  {g['dup']:>3}  {g['left_999'] + g['left_cost']:>9}  {bad:>6}")
    ok = all(g["rows_in"] == g["rows_out"] and g["dup"] == 0 and not g["fault_na_not_pm"]
             and g["left_999"] == 0 and g["left_cost"] == 0 for g in logs.values()) and not any(unseen.values())
    print("train에 없는 드론:", {n: len(v) for n, v in unseen.items()})
    print("점검:", "모두 통과" if ok else "확인 필요 항목 있음 — reports/preprocess_log.md 참고")
    print("저장:", OUT.relative_to(ROOT), "·", LOG.relative_to(ROOT))

    # 처리 기록 md
    L = ["# 전처리 기록", "",
         "생성: `python .claude/skills/drone-preprocess/scripts/preprocess.py` (drone-preprocess 스킬). "
         "원본 `data/*.csv`는 바꾸지 않았고 결과는 `artifacts/clean/`에 있다.", "",
         "## 1. 파일별 처리 건수", "",
         "| 파일 | 행(전 → 후) | downtime 999 → NaN | 비용 ÷100 | 고장 결측 → N/A(예방정비) | 첫 정비 표시 | 중복 |",
         "|---|---|---:|---:|---:|---:|---:|"]
    for n, g in logs.items():
        L.append(f"| drone_{n} | {g['rows_in']:,} → {g['rows_out']:,} | {len(g['downtime_999'])} | {len(g['cost_fix'])} "
                 f"| {g['fault_na_pm']:,} | {g['first_maint']} | {g['dup']} |")
    t = logs["train"]
    L += ["", "## 2. 이상치 처리 상세 (train)", "",
          f"- `downtime_hours` 999 → NaN {len(t['downtime_999'])}건: " + (" · ".join(t["downtime_999"]) or "없음"),
          f"- `maintenance_cost` > {COST_LIMIT:,} → ÷100 {len(t['cost_fix'])}건:", "",
          "| 드론 | 처리 전(만원) | 처리 후(만원) |", "|---|---:|---:|"]
    L += [f"| {e} | {b:,.0f} | {a:,.2f} |" for e, b, a in t["cost_fix"]]
    L += ["", "## 3. 처리 뒤 남은 결측 (의도한 결측)", "",
          "| 파일 | 컬럼별 결측 수 | 이유 |", "|---|---|---|"]
    for n, g in logs.items():
        why = "downtime NaN = 999 미입력, days_since NaN = 첫 정비" if g["na_after"] else "-"
        L.append(f"| drone_{n} | {g['na_after'] or '없음'} | {why} |")
    L += ["", "## 4. 점검", "",
          f"- 행 수 유지(삭제 없음): {'통과' if all(g['rows_in'] == g['rows_out'] for g in logs.values()) else '실패'}",
          f"- 예방정비가 아닌데 고장 코드가 빈 행: {sum(len(g['fault_na_not_pm']) for g in logs.values())}건",
          f"- 처리 뒤 남은 999 · 비용 > {COST_LIMIT:,}: {sum(g['left_999'] + g['left_cost'] for g in logs.values())}건",
          f"- train에 없는 드론: test {len(unseen['test'])}대 · this_month {len(unseen['this_month'])}대 "
          "(0이면 시간 피처를 train 기록에 이어 계산 가능)",
          f"- 종합: {'모두 통과' if ok else '확인 필요 항목 있음'}", "",
          "## 5. 다음 단계에서 할 일 (이 스킬에서 하지 않음)", "",
          "- `availability_rate`는 이번 달 데이터에 없는 '그 달 가동률'(정비 직후 알 수 없음) → 컬럼 선택 단계(README [4])에서 제외",
          "- 시간 피처(최근 90일 고장 수 등)는 train → test → this_month를 이어 붙여 계산(README [3])", ""]
    LOG.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
