"""README [3] 피처 만들기 · [4] 쓸 컬럼 고르기 — drone-features 스킬.
실행: python .claude/skills/drone-features/scripts/features.py
결과: artifacts/features_all.csv (train → test → this_month 이어서 계산), reports/features_log.md"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import drone_lib as L  # noqa: E402

CMD = "`python .claude/skills/drone-features/scripts/features.py`"


def recount_fail_90d(df):
    """검산용: drone_lib과 다른 방식(드론별 표 필터)으로 최근 90일 고장 수를 다시 센다."""
    out = pd.Series(0, index=df.index)
    fails = df[df["maintenance_type"].isin(L.FAIL_TYPES)][["equipment_id", "maintenance_date"]]
    for eid, g in df.groupby("equipment_id"):
        fd = fails.loc[fails.equipment_id == eid, "maintenance_date"].to_numpy()
        for i, d in zip(g.index, g["maintenance_date"].to_numpy()):
            out[i] = int(((fd <= d) & (fd >= d - np.timedelta64(90, "D"))).sum())
    return out


def main():
    df = L.load_all()
    ART = L.ART
    ART.mkdir(exist_ok=True)
    save = df.copy()
    save["maintenance_date"] = save["maintenance_date"].dt.strftime("%Y-%m-%d")
    save.to_csv(ART / "features_all.csv", index=False, encoding="utf-8-sig")

    # 검산 1: 다른 방식으로 다시 센 값과 비교
    re = recount_fail_90d(df)
    mism = int((re != df["fail_count_90d"]).sum())

    # 검산 2: 이어서 계산했는지 — 2025-01 test 행이 2024 기록을 보고 계산됐는가
    jan = df[(df.part == "test") & (df.maintenance_date < "2025-02-01")]
    only_test = L.add_time_features(L.clean(pd.concat([L.load_raw("test")], ignore_index=True)
                                            .sort_values(["equipment_id", "maintenance_date"], kind="stable")))
    only_jan = only_test[only_test.maintenance_date < "2025-02-01"]
    cont = {"2025-01 test 행": len(jan),
            "직전 고장 경과일 있음(이어 계산)": int(jan.days_since_last_failure.notna().sum()),
            "직전 고장 경과일 있음(test만 따로 계산했다면)": int(only_jan.days_since_last_failure.notna().sum())}

    # 표본: 이번 달 최근 90일 고장 수가 가장 큰 드론의 최근 기록
    m = df[df.part == "this_month"].sort_values(["fail_count_90d", "maintenance_date"]).iloc[-1]
    eid, d0 = m.equipment_id, m.maintenance_date
    win = df[(df.equipment_id == eid) & (df.maintenance_date <= d0) &
             (df.maintenance_date >= d0 - pd.Timedelta(days=90))][
        ["part", "maintenance_date", "maintenance_type", "fault_category", "cumulative_operating_hours"]]
    win = win.assign(maintenance_date=win.maintenance_date.dt.strftime("%Y-%m-%d"),
                     고장정비=win.maintenance_type.isin(L.FAIL_TYPES).map({True: "O", False: ""}))

    # [4] 누수 근거: availability_rate와 정답의 관계(train)
    tr = df[df.part == "train"]
    ar = tr.groupby(L.TARGET)["availability_rate"].mean().round(3)

    desc = df[df.part != "this_month"][L.TIME_COLS].describe().T[["count", "mean", "50%", "max"]].round(1)
    out = ["# 피처 기록 (README [3] · [4])", "", f"생성: {CMD} · 결과 `artifacts/features_all.csv`", "",
           "## 1. 만든 피처 (그 정비일까지의 기록만 사용, 같은 날 포함 · 뒤 날짜 제외)", "",
           "| 피처 | 정의 |", "|---|---|",
           "| fail_count_90d | 최근 90일(90일 전 날짜 포함) 사후 · 긴급정비 수, 이번 정비 포함 |",
           "| days_since_last_failure | 직전 고장 정비 뒤 경과일(이번이 고장이면 0, 없으면 비움) |",
           "| hours_since_last_pm | 최근 예방정비 때와 지금의 누적 비행시간 차(이번이 예방정비면 0, 없으면 비움) |",
           "| season | 정비월 → 계절(12~2 겨울 · 3~5 봄 · 6~8 여름 · 9~11 가을). 정비일에 이미 아는 값 |",
           "| is_first_maintenance | 직전 정비 경과일이 빈 행(첫 정비) = 1 |", "",
           "### 시간 피처 요약 (train + test)", "", L.md_table(desc.reset_index().rename(columns={"index": "피처"}), "{:,.1f}"), "",
           "## 2. 검산", "",
           f"- 최근 90일 고장 수: 다른 방식으로 전체 {len(df):,}행을 다시 셈 → 불일치 **{mism}건**",
           "- 앞 기간과 이어서 계산했는지 (2025-01 시험 행):", "",
           L.md_table(pd.DataFrame([cont])), "",
           f"### 표본: {eid} · {d0:%Y-%m-%d} (이번 달) — 창 {(d0 - pd.Timedelta(days=90)):%Y-%m-%d} ~ {d0:%Y-%m-%d}", "",
           L.md_table(win), "",
           f"- 손으로 센 고장 정비: {int((win.고장정비 == 'O').sum())}건 / 피처 값: {int(m.fail_count_90d)}건", "",
           "## 3. 모델에 넣는 컬럼 (`drone_lib.FEATURES`)", "",
           f"- 범주형 {len(L.CAT_COLS)}개: " + ", ".join(L.CAT_COLS),
           f"- 수치형 {len(L.BASE_NUM)}개: " + ", ".join(L.BASE_NUM),
           f"- 시간 피처 {len(L.TIME_COLS)}개: " + ", ".join(L.TIME_COLS), "",
           "## 4. 넣지 않은 컬럼과 이유 (README [4])", "", "| 컬럼 | 이유 |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in L.EXCLUDED.items()]
    out += ["", f"- 누수 근거: train에서 `availability_rate` 평균 — 재고장 0: {ar.get(0)}, 재고장 1: {ar.get(1)}. "
            "그 달 전체 가동률은 정비 뒤 30일의 고장을 일부 반영하므로 정비 직후에는 알 수 없음(이번 달 파일에도 없음).", ""]
    (L.REP / "features_log.md").write_text("\n".join(out), encoding="utf-8")

    print("행:", df.part.value_counts().to_dict(), "· 피처", len(L.FEATURES), "개")
    print("검산 fail_count_90d 불일치:", mism, "건")
    print("이어서 계산:", cont)
    print(f"표본 {eid} {d0:%Y-%m-%d}: 손으로 센 값 {int((win.고장정비 == 'O').sum())} / 피처 {int(m.fail_count_90d)}")
    print("availability_rate 평균(재고장 0/1):", ar.to_dict())
    print("저장: artifacts/features_all.csv · reports/features_log.md")


if __name__ == "__main__":
    main()
