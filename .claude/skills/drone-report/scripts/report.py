"""제출물 (2) 분석 보고서 — drone-report 스킬.  실행: python .claude/skills/drone-report/scripts/report.py
앞 단계 산출물(artifacts/*.json · *.csv)만 읽어 그래프 5개(reports/figures/)와 reports/분석보고서.md를 만든다.
여기서 새로 학습 · 예측하지 않는다(숫자는 모두 앞 단계 파일에서 온다)."""
import json
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
import drone_lib as L  # noqa: E402

CMD = "`python .claude/skills/drone-report/scripts/report.py`"
# dataviz 기본 팔레트(검증된 고정 순서): 1 파랑 = 모델, 2 주황 = 오래된 순, 3 청록 = 무작위
C_MODEL, C_OLD, C_RAND = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 10})


def j(word, with_final, without_final):
    """받침에 맞는 조사: j('수송드론', '이', '가') → '수송드론이'."""
    ch = word[-1]
    has = "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0
    return word + (with_final if has else without_final)


def save(fig, name):
    L.FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(L.FIG / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}"


def hbar(ax, s, title, color=C_MODEL, fmt="{:.1f}%"):
    s = s.sort_values()
    ax.barh(s.index, s.values, color=color, height=0.6)
    for y, v in enumerate(s.values):
        ax.text(v, y, " " + fmt.format(v), va="center", color=INK, fontsize=9)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, s.max() * 1.22)


def main():
    card = json.loads(L.CARD_PATH.read_text(encoding="utf-8"))
    ev = json.loads((L.ART / "evaluation.json").read_text(encoding="utf-8"))
    vtop = pd.read_csv(L.ART / "val_monthly_top20.csv")
    ttop = pd.read_csv(L.ART / "test_monthly_top20.csv")
    valp = pd.read_csv(L.ART / "val_predictions.csv")
    plan = pd.read_csv(L.ART / "score_2026-01.csv")
    df = L.load_all()
    tr = df[df.part == "train"]
    raw = L.load_raw("train")

    # 그림 1 정비 구분 · 드론 유형별 재고장 비율
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.2))
    hbar(ax[0], tr.groupby("maintenance_type")[L.TARGET].mean() * 100, "정비 구분별 재고장 비율")
    hbar(ax[1], tr.groupby("equipment_type")[L.TARGET].mean() * 100, "드론 유형별 재고장 비율")
    f1 = save(fig, "fig1_rate_by_type.png")
    r_mt = (tr.groupby("maintenance_type")[L.TARGET].mean() * 100).round(1)
    r_et = (tr.groupby("equipment_type")[L.TARGET].mean() * 100).round(1)

    # 그림 2 분기 추이
    q = tr.groupby(tr.maintenance_date.dt.to_period("Q").astype(str))[L.TARGET].mean() * 100
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(q.index, q.values, color=C_MODEL, lw=2, marker="o", ms=6)
    for x, v in [(q.index[0], q.iloc[0]), (q.index[-1], q.iloc[-1])]:
        ax.annotate(f"{v:.1f}%", (x, v), textcoords="offset points", xytext=(0, 8), ha="center", color=INK)
    vq = [i for i, k in enumerate(q.index) if pd.Period(L.VAL_START, "Q") <= pd.Period(k, "Q") <= pd.Period(L.VAL_END, "Q")]
    if vq:
        ax.axvspan(min(vq) - 0.5, max(vq) + 0.5, color=GRID, alpha=0.6, lw=0)
        ax.text((min(vq) + max(vq)) / 2, q.min(), "검증 기간", ha="center", color=INK2, fontsize=9)
    ax.set_title("분기별 재고장 비율 (train)", loc="left", color=INK, fontsize=11)
    ax.set_ylabel("%")
    f2 = save(fig, "fig2_trend.png")

    # 그림 3 월 20대 적중 수 (검증 · 시험)
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.4), sharey=True, gridspec_kw={"width_ratios": [6, 12]})
    for a, t, title in [(ax[0], vtop, "검증 2024-07~12"), (ax[1], ttop, "시험 2025 (재현 정답)")]:
        x = t.month.str[2:]
        for col, c, lab in [("model", C_MODEL, "모델"), ("oldest", C_OLD, "오래된 순"), ("random", C_RAND, "무작위(기대값)")]:
            a.plot(x, t[col], color=c, lw=2, marker="o", ms=5, label=lab)
        a.set_title(title, loc="left", color=INK, fontsize=11)
        a.tick_params(axis="x", rotation=45)
    ax[0].set_ylabel("20대 중 실제 재고장 드론 수")
    h, lab = ax[1].get_legend_handles_labels()
    fig.legend(h, lab, frameon=False, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 1.0))
    f3 = save(fig, "fig3_monthly_hits.png")

    # 그림 4 임계값별 총비용 (검증)
    fig, ax = plt.subplots(figsize=(8, 3.4))
    for miss, c in [(300, C_MODEL), (600, C_OLD)]:
        ct = L.cost_table(valp[L.TARGET], valp.prob, miss=miss)
        best = ct.loc[ct.cost.idxmin()]
        ax.plot(ct.threshold, ct.cost, color=c, lw=2, label=f"놓친 재고장 {miss}만원")
        ax.scatter([best.threshold], [best.cost], s=60, color=c, edgecolor=SURF, linewidth=2, zorder=3)
        ax.annotate(f"최소 {best.threshold:.2f}", (best.threshold, best.cost), textcoords="offset points",
                    xytext=(0, 10) if miss == 600 else (6, -14), ha="center" if miss == 600 else "left",
                    color=INK, fontsize=9)
    ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))
    ax.set_xlabel("위험 표시 기준(확률)")
    ax.set_ylabel("총비용(만원)")
    ax.set_title("검증 기간 임계값별 총비용 = 놓친 재고장 × 비용 + 기준 이상 × 60", loc="left", color=INK, fontsize=11)
    ax.legend(frameon=False)
    f4 = save(fig, "fig4_threshold_cost.png")

    # 그림 5 피처 중요도
    imp = pd.Series(card["importance_gain"]).head(10) * 100
    imp.index = [L.FEATURE_KO.get(k, k) for k in imp.index]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    hbar(ax, imp, "피처 중요도 상위 10 (gain 비율, 최종 모델)")
    f5 = save(fig, "fig5_importance.png")

    v, t = card["validation"], ev["test_2025"]
    th = card["threshold_by_miss_cost"]
    thr = card["threshold"]
    n_over = int(plan.over_threshold.sum())
    n_extra = int(((plan["rank"] > L.CAPACITY) & (plan.over_threshold == 1)).sum())
    src_c, src_e = "`artifacts/model_card.json`", "`artifacts/evaluation.json`"
    meta = json.loads(L.PLAN_META.read_text(encoding="utf-8"))

    # 본문 문장에 들어가는 값도 모두 계산한다(고정 문장 금지)
    parts_n = {p: int((df.part == p).sum()) for p in L.PARTS}
    fail_ratio = [r_mt[k] / r_mt[L.PM] for k in L.FAIL_TYPES]
    top_type = r_et.idxmax()
    split_s = L.split(df)
    fit_rate, val_rate = split_s["fit"][L.TARGET].mean() * 100, split_s["val"][L.TARGET].mean() * 100
    fails = tr[tr.maintenance_type.isin(L.FAIL_TYPES)]
    bat_season = fails[fails.fault_category == "배터리"].season.value_counts()
    mot_type = fails[fails.fault_category == "모터"].equipment_type.value_counts()
    top_feats = [L.FEATURE_KO.get(k, k) for k in list(card["importance_gain"])[:2]]
    time_top = all(k in L.TIME_COLS for k in list(card["importance_gain"])[:2])
    ratio_old = t["top20_hits_12m"]["model"] / max(t["top20_hits_12m"]["oldest"], 1)
    down600 = th["600"]["threshold"] < thr
    if n_over > L.CAPACITY:
        plan_line = f"{len(plan)}대 중 {n_over}대가 기준을 넘어, 확률 순 {L.CAPACITY}대를 재점검하고 나머지 {n_extra}대는 다음 달 우선 대상으로 둔다"
    else:
        plan_line = f"{len(plan)}대 중 {n_over}대가 기준을 넘어 모두 재점검 {L.CAPACITY}대 안에 든다(남는 {L.CAPACITY - n_over}대는 확률 순으로 채움)"

    kpi = pd.DataFrame([
        {"지표": "PR-AUC", "검증 2024 하반기": v["pr_auc"], "시험 2025(재현 정답)": t["pr_auc"], "기준선": f"{v['base_rate']} / {t['base_rate']} (재고장 비율)"},
        {"지표": "ROC-AUC", "검증 2024 하반기": v["roc_auc"], "시험 2025(재현 정답)": t["roc_auc"], "기준선": "0.5"},
        {"지표": "월 20대 적중 합(드론 단위)", "검증 2024 하반기": f"{v['top20_hits_6m']['model']:.0f} (6개월)",
         "시험 2025(재현 정답)": f"{t['top20_hits_12m']['model']:.0f} (12개월)",
         "기준선": f"오래된 순 {v['top20_hits_6m']['oldest']:.0f} / {t['top20_hits_12m']['oldest']:.0f} · 무작위 {v['top20_hits_6m']['random']:.1f} / {t['top20_hits_12m']['random']:.1f}"},
        {"지표": "재고장 드론 중 잡은 비율", "검증 2024 하반기": f"{v['top20_hits_6m']['model'] / v['top20_hits_6m']['failures'] * 100:.0f}%",
         "시험 2025(재현 정답)": f"{t['top20_hits_12m']['model'] / t['top20_hits_12m']['failures'] * 100:.0f}%",
         "기준선": f"재고장 드론 {v['top20_hits_6m']['failures']:.0f} / {t['top20_hits_12m']['failures']:.0f}대"},
    ])
    rec_v, rec_t = v["top20_hits_6m_records"], t["top20_hits_12m_records"]
    prep = pd.DataFrame([
        {"대상": "downtime_hours = 999", "건수(train)": int((raw.downtime_hours == 999).sum()), "처리": "행 유지, 값만 결측", "근거": "999 다음 큰 값 74.0 → 미입력 표시값"},
        {"대상": "maintenance_cost > 10,000", "건수(train)": int((raw.maintenance_cost > 10000).sum()), "처리": "÷100", "근거": "다음 큰 값 478, 나누면 150~190 → 자릿수 실수"},
        {"대상": "fault_code · fault_category 결측", "건수(train)": int(raw.fault_code.isna().sum()), "처리": "\"N/A\"", "근거": "예방정비 행과 정확히 일치 → 고장 없음"},
        {"대상": "days_since_last_maintenance 결측", "건수(train)": int(raw.days_since_last_maintenance.isna().sum()), "처리": "비워 두고 is_first_maintenance=1", "근거": "드론별 첫 정비 → 직전 정비 없음"},
        {"대상": "행 삭제", "건수(train)": 0, "처리": "하지 않음", "근거": "처리 전후 행 수 동일(preprocess_log)"},
    ])
    thr_tbl = pd.DataFrame([{"놓친 재고장 비용(만원)": k, "기준": x["threshold"], "기준 이상 건수": x["flagged"],
                             "놓친 재고장": x["missed"], "총비용(만원)": x["cost"]} for k, x in th.items()])
    test_cost = pd.DataFrame([{"놓친 재고장 비용(만원)": k, "기준": x["threshold"], "기준 이상 건수": x["flagged"],
                               "놓친 재고장": x["missed"], "총비용(만원)": x["cost"]} for k, x in t["cost_at_val_threshold"].items()])
    top5 = plan.head(5).assign(확률=(plan.prob.head(5) * 100).round(1).astype(str) + "%")[
        ["rank", "equipment_id", "equipment_type", "unit_code", "확률", "reasons"]].set_axis(
        ["순위", "드론", "유형", "부대", "확률", "위험을 올린 요인"], axis=1)

    o = ["# 드론 30일 안 재고장 예측 — 분석 보고서", "",
         f"생성: {CMD} · 교육용 가상 데이터 · 모든 숫자의 출처 파일을 괄호에 적음", "",
         "## 요약", "",
         f"- 정비 직후 정보만으로 30일 안 재고장 확률을 매기는 LightGBM 모델을 만들었다({src_c}).",
         f"- 검증 기간 PR-AUC {v['pr_auc']}로 기준선 {v['base_rate']}의 약 {v['pr_auc'] / v['base_rate']:.1f}배, "
         f"재현 정답으로 본 2025 시험 기간 PR-AUC {t['pr_auc']}(기준선 {t['base_rate']})다({src_e}).",
         f"- 매달 20대를 고르면 2025년 12개월 동안 모델 {t['top20_hits_12m']['model']:.0f}건, 오래된 순 {t['top20_hits_12m']['oldest']:.0f}건, "
         f"무작위 {t['top20_hits_12m']['random']:.1f}건의 재고장을 미리 잡는다({src_e}).",
         f"- 위험 표시 기준은 검증 기간 비용 최소인 {thr:.2f}(놓친 재고장 300만원). 600만원이면 {th['600']['threshold']:.2f}"
         f"{'로 내려간다' if down600 else '(내려가지 않음)'}({src_c}).",
         f"- 2026-01에는 {plan_line}(`artifacts/score_2026-01.csv`).", "",
         L.md_table(kpi), "",
         "## 1. 분석 목적", "",
         "정비를 마친 드론 가운데 30일 안에 다시 사후 · 긴급정비를 받을 드론을 미리 골라, 한 달 20대의 재점검 여력을 가장 효과적으로 쓰는 것이 목적이다. "
         "재고장을 놓치면 1건에 300만원, 재점검은 1대에 60만원이 든다고 가정한다(README).", "",
         "## 2. 데이터와 주요 패턴", "",
         f"train {parts_n['train']:,}건(드론 {tr.equipment_id.nunique()}대), test {parts_n['test']:,}건(2025, 정답 없음), "
         f"이번 달 {parts_n['this_month']:,}건(2026-01)이다. "
         f"train 전체 재고장 비율은 {tr[L.TARGET].mean() * 100:.1f}%다(`reports/eda_summary.md`).", "",
         f"![정비 구분 · 드론 유형별 재고장 비율]({f1})", "",
         f"**무엇을 보여 주는가** — 정비 구분과 드론 유형에 따라 30일 안 재고장 비율이 얼마나 다른지 보여 준다. "
         f"긴급정비 {r_mt['긴급정비']}% · 사후정비 {r_mt['사후정비']}% · 예방정비 {r_mt['예방정비']}%, 수송드론 {r_et['수송드론']}% · 교육용드론 {r_et.get('교육용드론', float('nan'))}%다.", "",
         f"**왜 중요한가** — 고장 때문에 들어온 정비(사후 · 긴급)는 예방정비보다 재고장 비율이 약 {min(fail_ratio):.1f} ~ {max(fail_ratio):.1f}배 높다. "
         f"정비 구분이 강한 단서이고, 유형 중에는 {j(top_type, '이', '가')} {r_et[top_type]}%로 가장 높다"
         f"{'(무거운 짐을 싣는 운용 부하 영향으로 추정)' if top_type == '수송드론' else '(원인은 데이터로 확인할 수 없어 추정 보류)'}.", "",
         f"**그래서 무엇을 하는가** — 정비 구분 · 드론 유형을 모델 피처에 넣고, 재점검 목록을 볼 때 고장 정비를 마친 {j(top_type, '을', '를')} 우선 확인한다.", "",
         f"![분기별 재고장 비율]({f2})", "",
         f"**무엇을 보여 주는가** — 분기별 재고장 비율이 {q.iloc[0]:.1f}%({q.index[0]})에서 {q.iloc[-1]:.1f}%({q.index[-1]})로 "
         f"{'올랐다' if q.iloc[-1] > q.iloc[0] else '내려갔다'}.", "",
         f"**왜 중요한가** — 기간에 따라 재고장 비율이 달라, 앞 기간으로 학습한 모델의 확률이 뒤 기간과 어긋날 수 있다. "
         f"검증 기간(회색) 비율 {val_rate:.1f}%는 학습(fit) 기간 {fit_rate:.1f}%보다 {'높다' if val_rate > fit_rate else '낮다'}.", "",
         "**그래서 무엇을 하는가** — 성능을 반드시 기간 분할로 확인하고, 임계값은 최근 기간(검증)에서 고른다. 한계 항목에 이 추세를 적는다.", "",
         f"그 밖의 패턴(`reports/eda_summary.md` 5장): 배터리 고장은 {bat_season.idxmax()}에 {bat_season.max()}건으로 가장 많고, "
         f"모터 고장 {mot_type.sum()}건 중 {mot_type.max()}건이 {j(mot_type.idxmax(), '이다', '다')}(원인은 저온 · 하중 영향으로 추정). 이를 반영해 계절(season) 피처를 넣었다.", "",
         "## 3. 데이터 처리 기준과 근거 (README [2])", "", L.md_table(prep), "",
         "**무엇을 보여 주는가** — 이상치 2종과 결측 2종을 어떻게 처리했는지, 왜 그렇게 판단했는지를 보여 준다(`reports/preprocess_log.md`).", "",
         "**왜 중요한가** — 결측을 최빈값으로 채우면 예방정비에 가짜 고장 코드가 붙고, 999를 그대로 두면 운용중단 시간이 크게 왜곡된다. 행을 지우면 드론별 시간 피처의 흐름이 끊긴다.", "",
         "**그래서 무엇을 하는가** — 같은 기준을 train · test · 이번 달에 한 함수(`drone_lib.clean`)로 똑같이 적용한다. test · 이번 달에는 이상치가 없었다.", "",
         "## 4. 피처와 넣지 않은 컬럼 (README [3] · [4])", "",
         f"모델 피처 {len(card['features'])}개: " + ", ".join(card["features"]) + " (`drone_lib.FEATURES`).", "",
         "시간 피처 3개(최근 90일 고장 수 · 직전 고장 뒤 경과일 · 예방정비 뒤 비행시간)는 그 정비일까지의 기록만 보고, train → test → 이번 달을 이어서 계산했다. "
         "다른 방식으로 다시 세어 불일치 0건을 확인했다(`reports/features_log.md`).", "",
         "| 넣지 않은 컬럼 | 이유 |", "|---|---|"] + [f"| {k} | {x} |" for k, x in card["excluded"].items()] + [
         "", "**왜 중요한가** — `availability_rate`는 그 달 전체 가동률이라 정비 뒤 고장이 반영된 값이다. 넣으면 검증 성능은 좋아 보이지만 이번 달 파일에는 없어 실제로 쓸 수 없다(누수).", "",
         "## 5. 기간 분할과 성능 (README [5])", "",
         L.md_table(pd.DataFrame([card["split"]])), "",
         f"![월 20대 적중 수]({f3})", "",
         "**무엇을 보여 주는가** — 매달 드론별 최근 기록 하나로 확률 상위 20대를 골랐을 때(재점검 계획과 같은 방식) 실제로 30일 안에 재고장 난 드론 수를 "
         f"모델 · 오래된 순 · 무작위와 비교한다(`artifacts/val_monthly_top20.csv`, `artifacts/test_monthly_top20.csv`). "
         f"2025년 재고장 드론 {t['top20_hits_12m']['failures']:.0f}대 중 {t['top20_hits_12m']['model']:.0f}대"
         f"({t['top20_hits_12m']['model'] / t['top20_hits_12m']['failures'] * 100:.0f}%)를 20대 안에서 잡았다.", "",
         f"참고로 기록 단위로 세면(같은 드론의 여러 정비 기록이 20자리를 함께 차지) 2025년 모델 {rec_t['model']:.0f} · 오래된 순 {rec_t['oldest']:.0f} · "
         f"무작위 {rec_t['random']:.1f}건이다. 한 드론이 여러 번 세어져 실제 재점검 대수보다 커지므로 판단에는 드론 단위를 쓴다({src_e}).", "",
         f"**왜 중요한가** — 정비반이 실제로 쓰는 방식(한 달 20대)으로 본 성능이다. 2025년 모델 {t['top20_hits_12m']['model']:.0f}건은 오래된 순({t['top20_hits_12m']['oldest']:.0f}건)의 "
         f"약 {ratio_old:.1f}배다. "
         f"{'경과연수만으로 고르는 방식보다 더 많은 재고장을 잡는다.' if ratio_old > 1 else '경과연수 방식보다 낫다고 말할 수 없다.'}", "",
         "**그래서 무엇을 하는가** — 재점검 순서를 경과연수가 아닌 모델 확률로 정한다. 2025 결과는 README 정의로 재현한 정답 기준이며(train 일치율 "
         f"{ev['rebuild_rule_match_train'] * 100:.0f}%), 공식 점수는 강사 정답으로 매긴다({src_e}).", "",
         "## 6. 위험 표시 기준 (README [6])", "",
         f"![임계값별 총비용]({f4})", "", L.md_table(thr_tbl), "",
         "**무엇을 보여 주는가** — 검증 기간에서 기준을 0.05 ~ 0.94로 바꿔 가며 '놓친 재고장 × 비용 + 기준 이상 × 60만원'을 계산한 결과다"
         f"({src_c} threshold_by_miss_cost).", "",
         f"**왜 중요한가** — 놓친 재고장 비용이 300 → 600만원으로 오르면 기준이 {thr:.2f} → {th['600']['threshold']:.2f}로 바뀌고, "
         f"기준 이상 건수는 {th['300']['flagged']} → {th['600']['flagged']}건, 놓친 재고장은 {th['300']['missed']} → {th['600']['missed']}건이 된다. "
         f"{'재고장 손해가 클수록 더 넓게 잡는 것이 싸다.' if down600 else '이 데이터에서는 비용이 올라도 기준이 내려가지 않았다.'}", "",
         f"**그래서 무엇을 하는가** — 운영 기준은 {thr:.2f}로 두고, 임무 중요도가 높은 시기(손해가 큰 경우)에는 600만원 기준을 쓴다. 기준은 시험 기간(2025)으로 고르지 않았다. "
         "참고로 같은 기준을 2025에 그대로 쓰면 아래와 같다(재현 정답).", "", L.md_table(test_cost), "",
         "## 7. 무엇이 위험을 올리는가", "",
         f"![피처 중요도]({f5})", "",
         "**무엇을 보여 주는가** — 최종 모델이 판단에 많이 쓴 피처다(`model_card.json` importance_gain).", "",
         f"**왜 중요한가** — 상위 2개는 {top_feats[0]} · {j(top_feats[1], '이다', '다')}. "
         f"{'둘 다 지난 기록으로 만든 시간 피처로, 원본 컬럼만으로는 알 수 없는 반복 고장 흐름을 잡아낸다.' if time_top else '원본 컬럼과 시간 피처가 함께 판단에 쓰인다.'}", "",
         "**그래서 무엇을 하는가** — 최근 고장이 잦은 드론은 정비 직후에도 재점검 목록에 올린다. 드론별 이유는 재점검 계획의 '위험을 올린 요인'(SHAP)으로 확인한다.", "",
         "## 8. 2026-01 재점검 계획 요약", "",
         f"자세한 20대 목록 · 권고는 `reports/2026-01_재점검계획.md`. 상위 5대(`artifacts/score_2026-01.csv`):", "",
         L.md_table(top5), "",
         "## 9. 모델의 한계 (`artifacts/model_card.json` limits)", ""] + [f"- {x}" for x in card["limits"]] + [
         "", "## 10. 추적 정보 (이 보고서가 어떤 데이터 · 모델 · 결과에서 나왔는가)", "",
         "파일 내용의 SHA-256 앞 12자리. `python scripts/check.py`가 현재 파일과 다시 대조한다.", "",
         L.md_table(pd.DataFrame([
             {"항목": "원본 train", "지문": card["lineage"]["data"]["train"], "기록된 곳": "model_card.json"},
             {"항목": "원본 test", "지문": card["lineage"]["data"]["test"], "기록된 곳": "model_card.json"},
             {"항목": "원본 this_month", "지문": meta["data"]["this_month"], "기록된 곳": "plan_meta.json"},
             {"항목": "모델", "지문": card["lineage"]["model"], "기록된 곳": "model_card · plan_meta · evaluation"},
             {"항목": "제출 파일", "지문": card["lineage"]["submission"], "기록된 곳": "model_card · evaluation"},
             {"항목": "이번 달 점수", "지문": meta["score"], "기록된 곳": "plan_meta.json"}])), ""]
    (L.REP / "분석보고서.md").write_text("\n".join(o), encoding="utf-8")
    print("그래프 5개:", ", ".join(p.name for p in sorted(L.FIG.glob("fig*.png"))))
    print("저장: reports/분석보고서.md")


if __name__ == "__main__":
    main()
