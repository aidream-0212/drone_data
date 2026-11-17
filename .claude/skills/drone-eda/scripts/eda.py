"""README [1] 데이터 살펴보기 — drone-eda 스킬.  실행: python .claude/skills/drone-eda/scripts/eda.py
원본을 읽기만 하고(전처리 전 상태), 결과를 reports/eda_summary.md 한 파일에 쓴다."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import drone_lib as L  # noqa: E402

CMD = "`python .claude/skills/drone-eda/scripts/eda.py`"


def rate(df, by):
    g = df.groupby(by, observed=True)[L.TARGET].agg(["count", "sum", "mean"]).reset_index()
    g.columns = [by if isinstance(by, str) else "/".join(by), "건수", "재고장", "비율"]
    g["비율"] = (g["비율"] * 100).round(1)
    return g.sort_values("비율", ascending=False)


def main():
    raw = {p: L.load_raw(p) for p in L.PARTS}
    tr = raw["train"].copy()
    out = ["# EDA 요약 (README [1])", "", f"생성: {CMD} · 원본 `data/*.csv`(전처리 전)", ""]

    # 1. 구조
    rows = []
    for p, d in raw.items():
        rows.append({"파일": p, "행": len(d), "컬럼": d.shape[1] - 1,
                     "기간": f"{d.maintenance_date.min():%Y-%m-%d} ~ {d.maintenance_date.max():%Y-%m-%d}",
                     "드론": d.equipment_id.nunique(), "부대": d.unit_code.nunique(),
                     "정답 열": "있음" if L.TARGET in d else "없음",
                     "availability_rate": "있음" if "availability_rate" in d else "**없음**",
                     "중복": int(d.drop(columns="part").duplicated().sum())})
    out += ["## 1. 구조", "", L.md_table(pd.DataFrame(rows)), ""]
    multi = raw["this_month"].equipment_id.value_counts()
    out += [f"- 이번 달: 드론 {raw['this_month'].equipment_id.nunique()}대 중 {int((multi > 1).sum())}대가 2회 이상 정비 → 가장 최근 기록으로 판단",
            f"- test · 이번 달 드론 중 train에 없는 드론: "
            f"{len(set(raw['test'].equipment_id) - set(tr.equipment_id))}대 · "
            f"{len(set(raw['this_month'].equipment_id) - set(tr.equipment_id))}대", ""]

    # 2. 결측과 원인
    rows = []
    for p, d in raw.items():
        for c, n in d.isna().sum().items():
            if n:
                if c.startswith("fault"):
                    why = f"예방정비 {int((d.maintenance_type == L.PM).sum()):,}건과 "
                    why += "일치 → 고장 없음" if (d[c].isna() == (d.maintenance_type == L.PM)).all() else "불일치 → 확인 필요"
                elif c == "days_since_last_maintenance":
                    first = d.groupby("equipment_id").maintenance_date.transform("min") == d.maintenance_date
                    why = "드론별 첫 정비와 일치 → 직전 정비 없음" if (d[c].isna() == first).all() else "확인 필요"
                else:
                    why = "확인 필요"
                rows.append({"파일": p, "컬럼": c, "결측": int(n), "원인": why})
    out += ["## 2. 결측과 원인", "", L.md_table(pd.DataFrame(rows)), ""]

    # 3. 이상치
    rows = []
    for c, cond, label in [("downtime_hours", lambda s: s == L.DOWNTIME_MISSING_CODE, "= 999"),
                           ("maintenance_cost", lambda s: s > L.COST_LIMIT, f"> {L.COST_LIMIT:,}")]:
        for p, d in raw.items():
            m = cond(d[c])
            rows.append({"컬럼": c, "조건": label, "파일": p, "건수": int(m.sum()),
                         "이상값 제외 최댓값": float(d.loc[~m, c].max()),
                         "이상값": ", ".join(f"{v:,.0f}" for v in sorted(d.loc[m, c])) or "-"})
    out += ["## 3. 이상치", "", L.md_table(pd.DataFrame(rows), "{:,.1f}"), ""]
    num = tr.select_dtypes("number").drop(columns=[L.TARGET])
    desc = num.describe().T[["mean", "50%", "min", "max"]].round(1).reset_index().rename(columns={"index": "컬럼"})
    out += ["### train 수치형 요약", "", L.md_table(desc, "{:,.1f}"), ""]

    # 4. 정답 비율과 패턴
    tr["season"] = tr.maintenance_date.dt.month.map(L.SEASON)
    tr["fault_category"] = tr["fault_category"].fillna("N/A(예방정비)")
    tr["quarter"] = tr.maintenance_date.dt.to_period("Q").astype(str)
    out += ["## 4. 정답(30일 안 재고장) 비율", "",
            f"- 전체: {tr[L.TARGET].mean() * 100:.1f}% ({int(tr[L.TARGET].sum()):,} / {len(tr):,})", ""]
    for by, title in [("maintenance_type", "정비 구분"), ("equipment_type", "드론 유형"),
                      ("season", "계절"), ("fault_category", "고장 유형")]:
        out += [f"### {title}별", "", L.md_table(rate(tr, by)), ""]
    q = rate(tr, "quarter").sort_values("quarter")
    out += ["### 분기 추이", "", L.md_table(q), ""]

    # 5. 교차 패턴 (고장 건수)
    f = tr[tr.maintenance_type.isin(L.FAIL_TYPES)]
    for idx, title in [("season", "계절 × 고장 유형 (고장 정비 건수)"), ("equipment_type", "드론 유형 × 고장 유형 (고장 정비 건수)")]:
        ct = pd.crosstab(f[idx], f["fault_category"]).reset_index()
        out += [f"## 5. {title}", "", L.md_table(ct), ""]

    path = L.REP / "eda_summary.md"
    L.REP.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")
    print(f"전체 재고장 비율 {tr[L.TARGET].mean() * 100:.1f}% · 분기 {q.iloc[0]['비율']}% → {q.iloc[-1]['비율']}%")
    print("이상치: downtime 999", int((tr.downtime_hours == 999).sum()), "건 · 비용 >10000",
          int((tr.maintenance_cost > 10000).sum()), "건")
    print("저장:", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
