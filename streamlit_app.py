"""2026-01 드론 재점검 우선순위 앱.

- 순위 · 확률 · 사유는 drone-plan 출력을 Supabase(public.drone_score_2026_01)에서 그대로 읽는다. 앱에서 다시 계산하지 않는다.
- 데이터 올리기: python scripts/upload_scores.py
- 실행: streamlit run streamlit_app.py
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
TABLE = "drone_score_2026_01"
CAPACITY = 20  # drone_lib.CAPACITY 와 같은 값(한 달 재점검 가능 대수)

st.set_page_config(page_title="드론 재점검 우선순위", page_icon=":material/flight:", layout="wide")

st.title("2026-01 드론 재점검 우선순위")
st.caption("정비 뒤 30일 안 재고장 확률 순 · 출처: drone-plan 결과(Supabase `drone_score_2026_01`) · 교육용 가상 데이터")


@st.cache_data
def load_model_card() -> dict:
    return json.loads((ROOT / "artifacts" / "model_card.json").read_text(encoding="utf-8"))


card = load_model_card()
threshold = card.get("threshold")

conn = st.connection("supabase", type="sql")
try:
    df: pd.DataFrame = conn.query(f'select * from public."{TABLE}" order by rank', ttl=600)
except Exception as e:  # 테이블이 없거나 연결 실패
    st.error(
        "Supabase에서 점수 테이블을 읽지 못했습니다. `python scripts/upload_scores.py`로 먼저 올렸는지, "
        "Secrets의 `[connections.supabase]` 설정을 확인하세요.",
        title="데이터를 불러오지 못했습니다",
    )
    st.exception(e)
    st.stop()

if df.empty:
    st.warning("점수 테이블이 비어 있습니다. `python scripts/upload_scores.py`를 실행하세요.", title="데이터 없음")
    st.stop()

# 핵심 수치
top = df[df["rank"] <= CAPACITY]
with st.container(horizontal=True):
    st.metric("평가 드론", f"{len(df)}대", border=True)
    st.metric("재점검 대상 (상위)", f"{len(top)}대", border=True)
    st.metric(
        f"임계값 {threshold:.2f} 이상" if threshold is not None else "임계값 이상",
        f"{int(df['over_threshold'].sum())}대",
        border=True,
    )
    st.metric("최고 확률", f"{df['prob'].max():.1%}", border=True)

# 필터
with st.container(horizontal=True, vertical_alignment="bottom"):
    scope = st.segmented_control(
        "보기", [f"상위 {CAPACITY}대", "전체"], default=f"상위 {CAPACITY}대", required=True, key="scope"
    )
    units = st.multiselect("부대", sorted(df["unit_code"].dropna().unique()), key="units", placeholder="전체")
    types = st.multiselect("드론 종류", sorted(df["equipment_type"].dropna().unique()), key="types", placeholder="전체")

view = df if scope == "전체" else top
if units:
    view = view[view["unit_code"].isin(units)]
if types:
    view = view[view["equipment_type"].isin(types)]

st.subheader(f"재점검 목록 · {len(view)}대")
st.dataframe(
    view,
    hide_index=True,
    alt="2026-01 드론별 재고장 확률 순위와 권장 조치",
    column_order=[
        "rank", "equipment_id", "equipment_type", "unit_code", "maintenance_date",
        "maintenance_type", "fault_category", "fail_count_90d", "prob", "over_threshold",
        "reasons", "advice",
    ],
    column_config={
        "rank": st.column_config.NumberColumn("순위", width="small"),
        "equipment_id": "드론",
        "equipment_type": "종류",
        "unit_code": "부대",
        "maintenance_date": st.column_config.DateColumn("최근 정비일", format="YYYY-MM-DD"),
        "maintenance_type": "정비 유형",
        "fault_category": "고장 분류",
        "fail_count_90d": st.column_config.NumberColumn("90일 고장", format="%d회"),
        "prob": st.column_config.ProgressColumn("재고장 확률", min_value=0.0, max_value=1.0, format="percent"),
        "over_threshold": st.column_config.CheckboxColumn("임계값 이상"),
        "reasons": st.column_config.TextColumn("위험 사유", width="large"),
        "advice": st.column_config.TextColumn("권장 조치", width="large"),
    },
)
st.caption(
    f"상위 {CAPACITY}대는 한 달 재점검 가능 대수 기준입니다. 확률은 drone-plan 출력 그대로이며, "
    f"score 지문 `{df['score_fp'].iloc[0] if 'score_fp' in df else '-'}`로 어느 결과인지 확인할 수 있습니다."
)

# 한계 · 최종 판단
with st.expander("모델 한계 (model_card.json)", icon=":material/info:"):
    for item in card.get("limits", []):
        st.markdown(f"- {item}")
st.info("최종 판단은 정비 담당자가 합니다. 이 목록은 재점검 순서를 정하는 참고 자료입니다.", icon=":material/engineering:")
