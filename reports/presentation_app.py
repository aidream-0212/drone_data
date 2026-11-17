"""drone_data 분석 과정 발표 앱.

- 저장된 단계별 결과(artifacts/ · reports/ · outputs/)만 읽어 보여 준다. 앱에서 다시 계산하거나 스킬을 실행하지 않는다.
- 드론 순위 · 확률 · 사유는 drone-plan 출력(artifacts/score_2026-01.csv)만 인용한다.
- 실행: streamlit run reports/presentation_app.py
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "artifacts"
REP = ROOT / "reports"
FIG = REP / "figures"
CAPACITY = 20  # drone_lib.CAPACITY 와 같은 값(한 달 재점검 가능 대수)

st.set_page_config(page_title="드론 예측정비 분석 발표", page_icon=":material/flight:", layout="wide")


@st.cache_data
def load_json(name: str) -> dict:
    return json.loads((ART / name).read_text(encoding="utf-8"))


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / path)


@st.cache_data
def load_md(name: str) -> str:
    return (REP / name).read_text(encoding="utf-8")


card = load_json("model_card.json")
ev = load_json("evaluation.json")
plan = load_json("plan_meta.json")
score_eval = load_json("eval_score.json") if (ART / "eval_score.json").exists() else None
val, test = card["validation"], ev["test_2025"]
vh, th = val["top20_hits_6m"], test["top20_hits_12m"]


def explain(what: str, why: str, then: str) -> None:
    """AGENTS.md 보고 규칙: 무엇을 보여 주는가 · 왜 중요한가 · 그래서 무엇을 하는가."""
    with st.container(horizontal=True):
        with st.container(border=True):
            st.markdown(f":material/visibility: **무엇을 보여 주는가**\n\n{what}")
        with st.container(border=True):
            st.markdown(f":material/priority_high: **왜 중요한가**\n\n{why}")
        with st.container(border=True):
            st.markdown(f":material/task_alt: **그래서 무엇을 하는가**\n\n{then}")


def run_info(command: str, outputs: str) -> None:
    with st.container(border=True):
        st.markdown(":material/terminal: **이 단계를 만든 명령과 결과 파일**")
        st.code(command, language="powershell")
        st.caption(f"결과: {outputs}")


def figure(name: str, alt: str) -> None:
    st.image(str(FIG / name), alt=alt, width="stretch")
    st.caption(f"그래프 출처: `reports/figures/{name}` (drone-report 출력)")


def source_doc(name: str) -> None:
    with st.expander(f"단계 기록 원문 보기 · reports/{name}", icon=":material/description:"):
        st.markdown(load_md(name))


STEPS = [
    "0. 개요",
    "1. 데이터 살펴보기 (EDA)",
    "2. 전처리 기준",
    "3. 피처와 제외 컬럼",
    "4. 기간 분할 · 성능",
    "5. 위험 표시 기준 (임계값)",
    "6. 위험을 올리는 요인",
    "7. 2026-01 재점검 계획",
    "8. 평가 · 검증",
    "9. 한계와 결론",
]

if "step" not in st.session_state:
    st.session_state.step = STEPS[0]


def move(delta: int) -> None:
    i = STEPS.index(st.session_state.step) + delta
    st.session_state.step = STEPS[max(0, min(len(STEPS) - 1, i))]


with st.sidebar:
    st.subheader("분석 과정", anchor=False)
    st.radio("단계", STEPS, key="step", label_visibility="collapsed")
    st.caption("교육용 가상 데이터 · 숫자는 모두 저장된 결과 파일에서 읽음")

step = st.session_state.step
idx = STEPS.index(step)

st.caption("드론 정비 뒤 30일 안 재고장 예측 · 분석 과정 발표")
st.title(step[3:] if idx else "드론 예측정비 분석 — 개요")
st.progress((idx + 1) / len(STEPS), text=f"{idx + 1} / {len(STEPS)} 단계")

# ---------------------------------------------------------------- 0. 개요
if idx == 0:
    st.markdown(
        "정비를 마친 드론 가운데 **30일 안에 다시 사후 · 긴급정비를 받을 드론**을 미리 골라, "
        f"한 달 **{CAPACITY}대**의 재점검 여력을 가장 효과적으로 쓰는 것이 목적이다. "
        "재고장을 놓치면 1건 300만원, 재점검은 1대 60만원이 든다고 가정한다(README)."
    )
    with st.container(horizontal=True):
        st.metric("시험 2025 PR-AUC", f"{test['pr_auc']:.3f}", f"기준선 {test['base_rate']:.3f}", delta_color="off", border=True)
        st.metric("2025 월 20대 적중 합", f"{th['model']:.0f}건", f"오래된 순 {th['oldest']:.0f} · 무작위 {th['random']:.1f}", delta_color="off", border=True)
        st.metric("2026-01 기준 이상", f"{plan['over_threshold']}대", f"평가 드론 {plan['drones']}대", delta_color="off", border=True)
        st.metric("위험 표시 기준", f"{card['threshold']:.2f}", "검증 기간 비용 최소", delta_color="off", border=True)
    st.caption("출처: `artifacts/evaluation.json` · `artifacts/plan_meta.json` · `artifacts/model_card.json`")

    st.subheader("분석 흐름", anchor=False)
    flow = pd.DataFrame(
        [
            ("1", "drone-eda", "데이터 구조 · 결측 · 이상치 · 패턴", "reports/eda_summary.md"),
            ("2", "drone-preprocess", "이상치 · 결측 처리 기준 적용", "artifacts/clean/ · reports/preprocess_log.md"),
            ("3", "drone-features", "시간 피처 계산 · 쓸 컬럼 결정", "artifacts/features_all.csv · reports/features_log.md"),
            ("4", "drone-train", "기간 분할 검증 · 임계값 · 2025 제출", "model_card.json · outputs/test_predictions_2025.csv"),
            ("5", "drone-plan", "2026-01 재점검 20대 선정", "artifacts/score_2026-01.csv · reports/2026-01_재점검계획.md"),
            ("6", "drone-evaluate", "2025 재현 정답으로 성능 확인", "artifacts/evaluation.json · reports/evaluation.md"),
            ("7", "drone-report", "분석 보고서 · 그래프", "reports/분석보고서.md · reports/figures/"),
            ("8", "drone-verify", "재현성 · 독립 대조 · 결함 주입", "reports/verification.md"),
        ],
        columns=["순서", "스킬", "하는 일", "결과"],
    )
    st.dataframe(flow, hide_index=True, alt="분석 단계별 스킬과 결과 파일")
    st.info(
        "train(2023 ~ 2024)으로 학습 → test(2025)로 예측 · 평가 → this_month(2026-01)로 재점검 계획.",
        title="데이터 흐름",
        icon=":material/route:",
    )

# ---------------------------------------------------------------- 1. EDA
elif idx == 1:
    st.markdown(
        "train 2,346건(드론 150대) · test 1,241건(2025, 정답 없음) · 이번 달 106건(2026-01). "
        "train 전체 재고장 비율은 22.4%다(`reports/eda_summary.md`)."
    )
    c1, c2 = st.columns(2)
    with c1:
        figure("fig1_rate_by_type.png", "정비 구분 · 드론 유형별 재고장 비율")
    with c2:
        figure("fig2_trend.png", "분기별 재고장 비율 추이")
    explain(
        "긴급정비 64.3% · 사후정비 47.2% · 예방정비 11.4%, 수송드론 31.8% · 교육용드론 13.6%. "
        "분기별 재고장 비율은 15.2%(2023Q1) → 29.5%(2024Q4)로 올랐다.",
        "고장 정비는 예방정비보다 재고장 비율이 약 4.1 ~ 5.6배 높다. 비율이 기간마다 달라 앞 기간으로 학습한 확률이 뒤 기간과 어긋날 수 있다.",
        "정비 구분 · 유형 · 계절을 피처에 넣고, 성능은 반드시 기간 분할로 확인한다. 임계값은 최근 기간(검증)에서 고른다.",
    )
    st.caption("수송드론 · 겨울 배터리 고장이 많은 원인(하중 · 저온)은 집계로 확인할 수 없어 '추정'으로 본다.")
    run_info("python .claude/skills/drone-eda/scripts/eda.py", "`reports/eda_summary.md`")
    source_doc("eda_summary.md")

# ---------------------------------------------------------------- 2. 전처리
elif idx == 2:
    rules = pd.DataFrame(
        [
            ("downtime_hours = 999", 4, "행 유지, 값만 결측", "999 다음 큰 값 74.0 → 미입력 표시값"),
            ("maintenance_cost > 10,000", 5, "÷100", "다음 큰 값 478, 나누면 150 ~ 190 → 자릿수 실수"),
            ("fault_code · fault_category 결측", 1707, '"N/A"', "예방정비 행과 정확히 일치 → 고장 없음"),
            ("days_since_last_maintenance 결측", 150, "비워 두고 is_first_maintenance=1", "드론별 첫 정비 → 직전 정비 없음"),
            ("행 삭제", 0, "하지 않음", "처리 전후 행 수 동일"),
        ],
        columns=["대상", "건수(train)", "처리", "근거"],
    )
    st.dataframe(rules, hide_index=True, alt="이상치 · 결측 처리 기준과 근거")
    st.caption("출처: `reports/preprocess_log.md` · `reports/분석보고서.md` 3장")
    explain(
        "이상치 2종과 결측 2종을 어떻게 처리했는지, 왜 그렇게 판단했는지.",
        "결측을 최빈값으로 채우면 예방정비에 가짜 고장 코드가 붙고, 999를 두면 운용중단 시간이 왜곡된다. 행을 지우면 드론별 시간 피처 흐름이 끊긴다.",
        "같은 기준을 train · test · 이번 달에 한 함수(`drone_lib.clean`)로 똑같이 적용한다. test · 이번 달에는 이상치가 없었다.",
    )
    run_info("python .claude/skills/drone-preprocess/scripts/preprocess.py", "`artifacts/clean/` · `reports/preprocess_log.md`")
    source_doc("preprocess_log.md")

# ---------------------------------------------------------------- 3. 피처
elif idx == 3:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader(f"모델 피처 {len(card['features'])}개", anchor=False)
        st.dataframe(pd.DataFrame({"피처": card["features"]}), hide_index=True, alt="모델에 넣은 피처 목록")
    with c2:
        st.subheader("넣지 않은 컬럼", anchor=False)
        st.dataframe(
            pd.DataFrame(list(card["excluded"].items()), columns=["컬럼", "이유"]),
            hide_index=True,
            alt="모델에서 제외한 컬럼과 이유",
            column_config={"이유": st.column_config.TextColumn(width="large")},
        )
    st.caption("출처: `artifacts/model_card.json` features · excluded")
    explain(
        "시간 피처 3개(최근 90일 고장 수 · 직전 고장 뒤 경과일 · 예방정비 뒤 비행시간)는 그 정비일까지의 기록만 보고, train → test → 이번 달을 이어서 계산했다.",
        "`availability_rate`는 정비 뒤 고장이 반영된 값이라 넣으면 검증 성능은 좋아 보이지만 이번 달 파일에는 없다(누수).",
        "예측 시점(정비 직후)에 알 수 있는 정보만 쓴다. 다른 방식으로 다시 세어 불일치 0건을 확인했다(`reports/features_log.md`).",
    )
    run_info("python .claude/skills/drone-features/scripts/features.py", "`artifacts/features_all.csv` · `reports/features_log.md`")
    source_doc("features_log.md")

# ---------------------------------------------------------------- 4. 분할 · 성능
elif idx == 4:
    st.dataframe(pd.DataFrame([card["split"]]), hide_index=True, alt="기간 분할: fit · 검증 · 최종 학습 · 시험")
    perf = pd.DataFrame(
        {
            "지표": ["PR-AUC", "ROC-AUC", f"월 {CAPACITY}대 적중 합(드론 단위)", "재고장 드론 중 잡은 비율"],
            "검증 2024 하반기": [f"{val['pr_auc']:.3f}", f"{val['roc_auc']:.3f}", f"{vh['model']:.0f} (6개월)", f"{vh['model'] / vh['failures']:.0%}"],
            "시험 2025(재현 정답)": [f"{test['pr_auc']:.3f}", f"{test['roc_auc']:.3f}", f"{th['model']:.0f} (12개월)", f"{th['model'] / th['failures']:.0%}"],
            "기준선": [
                f"{val['base_rate']:.3f} / {test['base_rate']:.3f} (재고장 비율)",
                "0.5",
                f"오래된 순 {vh['oldest']:.0f} / {th['oldest']:.0f} · 무작위 {vh['random']:.1f} / {th['random']:.1f}",
                f"재고장 드론 {vh['failures']:.0f} / {th['failures']:.0f}대",
            ],
        }
    )
    st.dataframe(perf, hide_index=True, alt="검증 · 시험 성능과 기준선 비교")
    st.caption("출처: `artifacts/model_card.json` validation · `artifacts/evaluation.json` test_2025")
    c1, c2 = st.columns([3, 2])
    with c1:
        figure("fig3_monthly_hits.png", "월 20대 적중 수: 모델 · 오래된 순 · 무작위")
    with c2:
        part = st.segmented_control("월별 표", ["시험 2025", "검증 2024"], default="시험 2025", required=True, key="hits_scope")
        path = "artifacts/test_monthly_top20.csv" if part == "시험 2025" else "artifacts/val_monthly_top20.csv"
        st.dataframe(
            load_csv(path),
            hide_index=True,
            alt="월별 20대 적중 수",
            column_config={"month": "월", "n": "드론", "failures": "재고장", "model": "모델", "oldest": "오래된 순", "random": "무작위"},
        )
        st.caption(f"출처: `{path}`")
    explain(
        f"매달 드론별 최근 기록 하나로 확률 상위 {CAPACITY}대를 골랐을 때 실제로 재고장 난 드론 수.",
        f"정비반이 실제로 쓰는 방식으로 본 성능이다. 2025년 모델 {th['model']:.0f}건은 오래된 순({th['oldest']:.0f}건)의 약 {th['model'] / th['oldest']:.1f}배다.",
        "재점검 순서를 경과연수가 아닌 모델 확률로 정한다. 무작위 분할은 쓰지 않았다.",
    )
    st.caption(
        f"참고: 기록 단위로 세면 2025년 모델 {test['top20_hits_12m_records']['model']:.0f}건. 같은 드론이 여러 번 세어져 부풀려지므로 판단에는 드론 단위를 쓴다."
    )
    run_info("python .claude/skills/drone-train/scripts/train.py", "`artifacts/drone_model.joblib` · `artifacts/model_card.json` · `outputs/test_predictions_2025.csv` · `reports/train_log.md`")
    source_doc("train_log.md")

# ---------------------------------------------------------------- 5. 임계값
elif idx == 5:
    c1, c2 = st.columns([3, 2])
    with c1:
        figure("fig4_threshold_cost.png", "임계값별 총비용 곡선")
    with c2:
        tc = pd.DataFrame.from_dict(card["threshold_by_miss_cost"], orient="index").reset_index()
        tc.columns = ["놓친 재고장 비용(만원)", "기준", "기준 이상 건수", "놓친 재고장", "총비용(만원)"]
        st.subheader("검증 기간(기준 선택)", anchor=False)
        st.dataframe(tc, hide_index=True, alt="놓친 재고장 비용별 최적 기준")
        st.caption("출처: `artifacts/model_card.json` threshold_by_miss_cost")
        tt = pd.DataFrame.from_dict(test["cost_at_val_threshold"], orient="index").reset_index()
        tt.columns = ["놓친 재고장 비용(만원)", "기준", "기준 이상 건수", "놓친 재고장", "총비용(만원)"]
        st.subheader("같은 기준을 2025에 적용(참고)", anchor=False)
        st.dataframe(tt, hide_index=True, alt="검증 기준을 2025에 적용한 결과")
        st.caption("출처: `artifacts/evaluation.json` cost_at_val_threshold — 평가 확인용, 기준 선택에 쓰지 않음")
    explain(
        "검증 기간에서 기준을 바꿔 가며 '놓친 재고장 × 비용 + 기준 이상 × 60만원'을 계산한 결과.",
        "놓친 재고장 비용이 300 → 600만원이면 기준이 0.22 → 0.12로 내려간다. 재고장 손해가 클수록 넓게 잡는 것이 싸다.",
        f"운영 기준은 {card['threshold']:.2f}로 두고, 임무 중요도가 높은 시기에는 600만원 기준을 쓴다. 기준은 시험 기간으로 고르지 않았다.",
    )
    st.caption(card["threshold_rule"])

# ---------------------------------------------------------------- 6. 위험 요인
elif idx == 6:
    c1, c2 = st.columns([3, 2])
    with c1:
        figure("fig5_importance.png", "피처 중요도(gain)")
    with c2:
        imp = pd.DataFrame(list(card["importance_gain"].items()), columns=["피처", "중요도"])
        st.dataframe(
            imp,
            hide_index=True,
            alt="피처 중요도 표",
            column_config={"중요도": st.column_config.ProgressColumn(min_value=0.0, max_value=float(imp["중요도"].max()), format="%.3f")},
        )
        st.caption("출처: `artifacts/model_card.json` importance_gain")
    explain(
        "최종 모델이 판단에 많이 쓴 피처.",
        "상위 2개(직전 고장 뒤 경과일 · 최근 90일 고장 수)는 지난 기록으로 만든 시간 피처로, 원본 컬럼만으로는 알 수 없는 반복 고장 흐름을 잡아낸다.",
        "최근 고장이 잦은 드론은 정비 직후에도 재점검 목록에 올린다. 드론별 이유는 재점검 계획의 '위험 사유'(SHAP)로 확인한다.",
    )
    st.caption("중요도는 모델이 많이 쓴 정도이며, 고장의 원인을 뜻하지 않는다.")

# ---------------------------------------------------------------- 7. 재점검 계획
elif idx == 7:
    score = load_csv("artifacts/score_2026-01.csv")
    top = score[score["rank"] <= CAPACITY]
    with st.container(horizontal=True):
        st.metric("이번 달 기록", f"{plan['records']}건", border=True)
        st.metric("평가 드론", f"{plan['drones']}대", border=True)
        st.metric(f"기준 {plan['threshold']:.2f} 이상", f"{plan['over_threshold']}대", border=True)
        st.metric("재점검 대상", f"{len(top)}대", border=True)
        st.metric("다음 달 우선", f"{max(plan['over_threshold'] - CAPACITY, 0)}대", border=True)
    with st.container(horizontal=True, vertical_alignment="bottom"):
        scope = st.segmented_control("보기", [f"상위 {CAPACITY}대", "전체"], default=f"상위 {CAPACITY}대", required=True, key="plan_scope")
        types = st.pills("드론 종류", sorted(score["equipment_type"].dropna().unique()), selection_mode="multi", key="plan_types")
    view = top if scope != "전체" else score
    if types:
        view = view[view["equipment_type"].isin(types)]
    st.dataframe(
        view,
        hide_index=True,
        alt="2026-01 드론별 재고장 확률 순위와 권장 조치",
        column_order=["rank", "equipment_id", "equipment_type", "unit_code", "maintenance_date", "maintenance_type",
                      "fault_category", "fail_count_90d", "prob", "over_threshold", "reasons", "advice"],
        column_config={
            "rank": st.column_config.NumberColumn("순위", width="small"),
            "equipment_id": "드론",
            "equipment_type": "종류",
            "unit_code": "부대",
            "maintenance_date": "최근 정비일",
            "maintenance_type": "정비 유형",
            "fault_category": "고장 분류",
            "fail_count_90d": st.column_config.NumberColumn("90일 고장", format="%d회"),
            "prob": st.column_config.ProgressColumn("재고장 확률", min_value=0.0, max_value=1.0, format="percent"),
            "over_threshold": st.column_config.CheckboxColumn("기준 이상"),
            "reasons": st.column_config.TextColumn("위험 사유", width="large"),
            "advice": st.column_config.TextColumn("권장 조치", width="large"),
        },
    )
    st.caption(f"출처: `artifacts/score_2026-01.csv` (drone-plan 출력 그대로) · score 지문 `{plan['score']}`")
    explain(
        f"이번 달 드론별 가장 최근 기록으로 매긴 재고장 확률 순위. {plan['drones']}대 중 {plan['over_threshold']}대가 기준을 넘었다.",
        f"한 달 재점검 여력은 {CAPACITY}대라 기준 이상 전부를 볼 수 없다. 확률 순으로 잘라야 한다.",
        f"확률 순 {CAPACITY}대를 재점검하고, 나머지 {max(plan['over_threshold'] - CAPACITY, 0)}대는 다음 달 우선 대상으로 둔다. 정비 실패 · 90일 고장이 많은 드론은 운용 제한을 검토한다.",
    )
    run_info("python .claude/skills/drone-plan/scripts/plan.py", "`artifacts/score_2026-01.csv` · `artifacts/plan_meta.json` · `reports/2026-01_재점검계획.md`")
    source_doc("2026-01_재점검계획.md")

# ---------------------------------------------------------------- 8. 평가 · 검증
elif idx == 8:
    st.markdown("'**예측이 맞았는가**'(evaluate)와 '**계산이 맞는가**'(verify)를 나눠서 확인했다.")
    t1, t2, t3 = st.tabs([":material/analytics: 평가 (evaluate)", ":material/verified: 검증 (verify)", ":material/fact_check: 채점표"])
    with t1:
        checks = pd.DataFrame(list(ev["submission_checks"].items()), columns=["제출물 (1) 형식 점검", "통과"])
        st.dataframe(checks, hide_index=True, alt="제출 파일 형식 점검", column_config={"통과": st.column_config.CheckboxColumn()})
        with st.container(horizontal=True):
            st.metric("시험 PR-AUC", f"{test['pr_auc']:.3f}", border=True)
            st.metric("기준선 대비", f"{test['pr_auc'] / test['base_rate']:.2f}배", border=True)
            st.metric("정답 재현 일치율(train)", f"{ev['rebuild_rule_match_train']:.0%}", border=True)
        st.caption(f"출처: `artifacts/evaluation.json` · {ev['note']}")
        run_info("python .claude/skills/drone-evaluate/scripts/evaluate.py", "`artifacts/evaluation.json` · `reports/evaluation.md`")
    with t2:
        st.markdown(load_md("verification.md").split("\n", 4)[-1])
        run_info("python .claude/skills/drone-verify/scripts/verify.py", "`reports/verification.md`")
    with t3:
        if score_eval is None:
            st.warning("`artifacts/eval_score.json`이 없습니다. `python scripts/score_eval.py`를 실행하세요.", title="채점 결과 없음")
        else:
            a = score_eval["areas"]
            with st.container(horizontal=True):
                st.metric("총점", f"{score_eval['total']} / 100", border=True)
                st.metric("A 시험 성능 vs 기준선", f"{a['A']['score']} / {a['A']['max']}", border=True)
                st.metric("B 근거 타당성", f"{a['B']['score']} / {a['B']['max']}", border=True)
                st.metric("C 숫자 일치", f"{a['C']['score']} / {a['C']['max']}", border=True)
            st.dataframe(
                pd.DataFrame(score_eval["items"])[["key", "name", "score", "max", "detail"]],
                hide_index=True,
                alt="채점표 항목별 점수",
                column_config={"key": "항목", "name": "점검", "score": "점수", "max": "배점", "detail": st.column_config.TextColumn("근거", width="large")},
            )
            st.caption(f"출처: `artifacts/eval_score.json` · `{score_eval['command']}` · 채점 {score_eval['scored_at']} · {score_eval['scope_note']}")
    st.subheader("추적 정보 (지문, SHA-256 앞 12자리)", anchor=False)
    lin = card["lineage"]
    st.dataframe(
        pd.DataFrame(
            [("train 데이터", lin["data"]["train"]), ("test 데이터", lin["data"]["test"]), ("이번 달 데이터", lin["data"]["this_month"]),
             ("모델", lin["model"]), ("제출 파일", lin["submission"]), ("이번 달 점수", plan["score"])],
            columns=["항목", "지문"],
        ),
        hide_index=True,
        alt="데이터 · 모델 · 결과 파일 지문",
    )
    st.caption("출처: `artifacts/model_card.json` lineage · `artifacts/plan_meta.json` · `python scripts/check.py`가 현재 파일과 다시 대조")

# ---------------------------------------------------------------- 9. 한계 · 결론
else:
    st.subheader("결론", anchor=False)
    st.markdown(
        f"- 정비 직후 정보만으로 30일 안 재고장 확률을 매기는 모델을 만들었다.\n"
        f"- 2025 시험 PR-AUC {test['pr_auc']:.3f}로 기준선 {test['base_rate']:.3f}의 약 {test['pr_auc'] / test['base_rate']:.1f}배다.\n"
        f"- 매달 {CAPACITY}대를 고르면 2025년 모델 {th['model']:.0f}건 · 오래된 순 {th['oldest']:.0f}건 · 무작위 {th['random']:.1f}건의 재고장을 미리 잡는다.\n"
        f"- 2026-01에는 {plan['drones']}대 중 {plan['over_threshold']}대가 기준을 넘어, 확률 순 {CAPACITY}대를 재점검한다."
    )
    st.caption("출처: `artifacts/evaluation.json` · `artifacts/plan_meta.json`")
    st.subheader("모델의 한계 (model_card.json limits)", anchor=False)
    for item in card["limits"]:
        st.markdown(f"- {item}")
    st.info("최종 판단은 정비 담당자가 합니다. 이 결과는 재점검 순서를 정하는 참고 자료입니다.", icon=":material/engineering:")

st.divider()
with st.container(horizontal=True, horizontal_alignment="distribute"):
    st.button("이전 단계", icon=":material/arrow_back:", on_click=move, args=(-1,), disabled=idx == 0, key="prev")
    st.button("다음 단계", icon=":material/arrow_forward:", on_click=move, args=(1,), disabled=idx == len(STEPS) - 1, key="next")
