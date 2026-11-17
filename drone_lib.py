"""드론 예측정비 실습 공통 함수 — 모든 스킬 스크립트가 함께 쓴다.

이름 · 인자 · 상수(FEATURES, TARGET, 기간 경계 등)를 바꾸면 스킬 결과가 함께 바뀐다.
흐름:  load_all() = 원본 3개 읽기 → clean() → add_time_features()  (train → test → this_month 이어서 계산)
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ART = ROOT / "artifacts"
REP = ROOT / "reports"
OUTPUTS = ROOT / "outputs"
FIG = REP / "figures"
PARTS = {"train": DATA / "drone_train.csv", "test": DATA / "drone_test.csv",
         "this_month": DATA / "drone_this_month.csv"}
MODEL_PATH = ART / "drone_model.joblib"
CARD_PATH = ART / "model_card.json"
SUBMIT_PATH = OUTPUTS / "test_predictions_2025.csv"

TARGET = "failure_within_30days"
FAIL_TYPES = ["사후정비", "긴급정비"]          # 고장 때문에 한 정비
PM = "예방정비"
DOWNTIME_MISSING_CODE = 999
COST_LIMIT = 10000
CAPACITY = 20                                 # 한 달 재점검 가능 대수
COST_MISS, COST_CHECK = 300, 60               # 만원: 놓친 재고장 1건, 재점검 1대
FIT_END = "2024-06-30"                        # 학습: ~ 2024-06-30
VAL_START, VAL_END = "2024-07-01", "2024-12-31"   # 검증(임계값 선택)
TEST_START = "2025-01-01"                     # 시험(제출)
THRESHOLDS = np.round(np.arange(0.05, 0.95, 0.01), 2)

SEASON = {12: "겨울", 1: "겨울", 2: "겨울", 3: "봄", 4: "봄", 5: "봄",
          6: "여름", 7: "여름", 8: "여름", 9: "가을", 10: "가을", 11: "가을"}
CAT_COLS = ["equipment_type", "maintenance_type", "fault_category", "season"]
BASE_NUM = ["equipment_age_years", "severity", "downtime_hours", "repair_duration_hours",
            "parts_replaced_count", "maintenance_cost", "maintenance_success",
            "cumulative_operating_hours", "days_since_last_maintenance", "is_first_maintenance"]
TIME_COLS = ["fail_count_90d", "days_since_last_failure", "hours_since_last_pm"]
FEATURES = CAT_COLS + BASE_NUM + TIME_COLS
EXCLUDED = {
    "availability_rate": "그 달 전체 가동률 — 정비 직후에는 알 수 없음(누수), 이번 달 데이터에도 없음",
    "equipment_id": "식별자 — 드론 번호를 외우게 됨",
    "unit_code": "식별자(부대) — 부대 번호를 외우게 됨",
    "maintenance_date": "날짜 자체는 넣지 않음 — 계절(season)과 시간 피처로 대신함",
    "fault_code": "고장 코드는 세부 코드라 종류가 많음 — fault_category로 대신함",
}

FEATURE_KO = {
    "equipment_type": "드론 유형", "maintenance_type": "정비 구분", "fault_category": "고장 유형",
    "season": "계절", "equipment_age_years": "경과연수", "severity": "고장 심각도",
    "downtime_hours": "운용중단 시간", "repair_duration_hours": "수리 시간",
    "parts_replaced_count": "교체 부품 수", "maintenance_cost": "정비 비용",
    "maintenance_success": "정비 성공 여부", "cumulative_operating_hours": "누적 비행시간",
    "days_since_last_maintenance": "직전 정비 뒤 경과일", "is_first_maintenance": "첫 정비 여부",
    "fail_count_90d": "최근 90일 고장 수", "days_since_last_failure": "직전 고장 뒤 경과일",
    "hours_since_last_pm": "예방정비 뒤 비행시간", "availability_rate": "그 달 가동률",
}


# ── 읽기 · 전처리 ──────────────────────────────────────────────
def load_raw(part):
    df = pd.read_csv(PARTS[part], encoding="utf-8-sig", parse_dates=["maintenance_date"])
    return df.assign(part=part)


def clean(df):
    """README [2] 처리 기준. 원본은 바꾸지 않고 행을 지우지 않는다.
    999 → NaN, 비용 > 10000 → ÷100, 예방정비 고장 결측 → "N/A", 첫 정비 → is_first_maintenance=1"""
    out = df.copy()
    out["downtime_hours"] = out["downtime_hours"].mask(out["downtime_hours"] == DOWNTIME_MISSING_CODE, np.nan)
    cost = out["maintenance_cost"].astype(float)
    out["maintenance_cost"] = cost.mask(cost > COST_LIMIT, cost / 100)
    pm = out["maintenance_type"] == PM
    for c in ("fault_code", "fault_category"):
        out.loc[out[c].isna() & pm, c] = "N/A"
    out["is_first_maintenance"] = out["days_since_last_maintenance"].isna().astype(int)
    out["maintenance_date"] = pd.to_datetime(out["maintenance_date"])
    out["season"] = out["maintenance_date"].dt.month.map(SEASON)
    return out


def add_time_features(df):
    """README [3] 드론별 지난 기록 피처. 그 정비일까지의 기록만 쓴다(같은 날 포함, 뒤 날짜 제외).
      fail_count_90d          최근 90일(90일 전 날짜 포함) 사후 · 긴급정비 수. 이번 정비도 센다
      days_since_last_failure 직전 고장 정비 뒤 경과일(이번이 고장 정비면 0). 고장 기록이 없으면 NaN
      hours_since_last_pm     최근 예방정비 때와 지금의 누적 비행시간 차(이번이 예방정비면 0). 없으면 NaN
    train → test → this_month를 이어 붙인 df에 쓰면 앞 기간 기록과 이어서 계산된다. 행 · 인덱스는 그대로."""
    out = df.copy()
    day = pd.to_datetime(out["maintenance_date"]).to_numpy().astype("datetime64[D]")
    is_fail = out["maintenance_type"].isin(FAIL_TYPES).to_numpy()
    is_pm = (out["maintenance_type"] == PM).to_numpy()
    hours = out["cumulative_operating_hours"].to_numpy(dtype=float)
    fail_cnt = np.zeros(len(out))
    since_fail = np.full(len(out), np.nan)
    since_pm = np.full(len(out), np.nan)
    for _, pos in out.groupby("equipment_id", sort=False).indices.items():
        d, f, p, h = day[pos], is_fail[pos], is_pm[pos], hours[pos]
        for j, i in enumerate(pos):
            seen = d <= d[j]
            fails = seen & f
            fail_cnt[i] = np.sum(fails & (d >= d[j] - np.timedelta64(90, "D")))
            if f[j]:
                since_fail[i] = 0.0
            elif fails.any():
                since_fail[i] = float((d[j] - d[fails].max()).astype(int))
            if p[j]:
                since_pm[i] = 0.0
            elif (seen & p).any():
                pms = np.flatnonzero(seen & p)
                last = pms[np.lexsort((h[pms], d[pms]))[-1]]
                since_pm[i] = round(h[j] - h[last], 1)
    out["fail_count_90d"] = fail_cnt.astype(int)
    out["days_since_last_failure"] = since_fail
    out["hours_since_last_pm"] = since_pm
    return out


def load_all():
    """원본 3개를 이어 붙여 전처리 · 시간 피처까지 만든 표. part 열 = train / test / this_month."""
    df = pd.concat([load_raw(p) for p in PARTS], ignore_index=True)
    df = df.sort_values(["equipment_id", "maintenance_date"], kind="stable").reset_index(drop=True)
    return add_time_features(clean(df))


def split(df):
    """기간 분할(무작위 아님): fit ~2024-06-30 / val 2024-07~12 / train 전체 / test 2025 / month 2026-01."""
    d = df["maintenance_date"]
    tr = df[df["part"] == "train"]
    return {"fit": tr[tr["maintenance_date"] <= FIT_END],
            "val": tr[(tr["maintenance_date"] >= VAL_START) & (tr["maintenance_date"] <= VAL_END)],
            "train": tr,
            "test": df[(df["part"] == "test") & (d >= TEST_START)],
            "month": df[df["part"] == "this_month"]}


# ── 모델 · 평가 ────────────────────────────────────────────────
def make_model():
    """범주형 원-핫 + LightGBM (결측은 LightGBM이 처리). 표본이 적어 얕은 나무 · 강한 규제."""
    from lightgbm import LGBMClassifier
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder
    pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_COLS)],
                            remainder="passthrough", verbose_feature_names_out=False).set_output(transform="pandas")
    lgbm = LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=4, min_child_samples=40,
                          reg_lambda=5.0, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                          random_state=42, verbose=-1)
    return Pipeline([("pre", pre), ("model", lgbm)])


def monthly_topk(df, score_col, y_col=TARGET, k=CAPACITY):
    """달마다 score_col 상위 k건을 골랐을 때 실제 재고장 수와 무작위 기대값. 열: month, n, picked, hits, random."""
    rows = []
    for m, g in df.groupby(df["maintenance_date"].dt.to_period("M")):
        top = g.nlargest(k, score_col)
        rows.append({"month": str(m), "n": len(g), "picked": len(top), "hits": int(top[y_col].sum()),
                     "random": round(min(k, len(g)) * g[y_col].mean(), 1)})
    return pd.DataFrame(rows)


def cost_table(y, prob, miss=COST_MISS, check=COST_CHECK):
    """임계값마다 기준 이상 건수 · 놓친 재고장 · 총비용(만원)."""
    y, prob = np.asarray(y), np.asarray(prob)
    rows = []
    for t in THRESHOLDS:
        flag = prob >= t
        missed = int(((~flag) & (y == 1)).sum())
        rows.append({"threshold": float(t), "flagged": int(flag.sum()), "missed": missed,
                     "cost": missed * miss + int(flag.sum()) * check})
    return pd.DataFrame(rows)


def contributions(model, X):
    """행마다 피처별 기여도(SHAP, 로그 오즈). 원-핫 열은 원래 컬럼으로 합친다."""
    Xt = model["pre"].transform(X)
    raw = model["model"].booster_.predict(Xt, pred_contrib=True)[:, :-1]
    contrib = pd.DataFrame(raw, columns=Xt.columns, index=X.index)
    groups = {c: next((k for k in CAT_COLS if c.startswith(k + "_")), c) for c in Xt.columns}
    return contrib.T.groupby(groups).sum().T[X.columns]


def reasons(model, X, top=3):
    """행마다 위험을 가장 많이 올린 피처 top개를 정비반장이 읽을 수 있는 글로."""
    c = contributions(model, X)
    out = []
    for i in X.index:
        up = c.loc[i][c.loc[i] > 0].sort_values(ascending=False).head(top)
        out.append(", ".join(reason_label(f, X.at[i, f]) for f in up.index))
    return out


UNIT = {"equipment_age_years": "년", "downtime_hours": "시간", "repair_duration_hours": "시간",
        "parts_replaced_count": "개", "maintenance_cost": "만원", "cumulative_operating_hours": "시간",
        "days_since_last_maintenance": "일"}


def reason_label(f, v):
    """피처 값을 뜻이 보이는 말로 (0/1 · 0일 · 결측을 풀어 씀)."""
    na = v is None or (isinstance(v, (float, np.floating)) and np.isnan(v))
    if f == "maintenance_success":
        return "정비 실패" if v == 0 else "정비 성공"
    if f == "is_first_maintenance":
        return "첫 정비" if v == 1 else "첫 정비 아님"
    if f == "days_since_last_failure":
        return "고장 기록 없음" if na else ("이번 정비가 고장 정비" if v == 0 else f"직전 고장 뒤 {_fmt(v)}일")
    if f == "hours_since_last_pm":
        return "예방정비 기록 없음" if na else ("이번 정비가 예방정비" if v == 0 else f"예방정비 뒤 {_fmt(v)}시간 비행")
    if f == "fail_count_90d":
        return f"최근 90일 고장 {_fmt(v)}회"
    if f in CAT_COLS:
        return f"{FEATURE_KO[f]} {v}"
    if f == "severity":
        return f"고장 심각도 {_fmt(v)}"
    return f"{FEATURE_KO.get(f, f)} {'미입력' if na else _fmt(v) + UNIT.get(f, '')}"


def _fmt(v):
    if isinstance(v, (float, np.floating)):
        return "없음" if np.isnan(v) else f"{v:,.1f}".rstrip("0").rstrip(".")
    return str(v)


# ── 추적(지문 · 실행 기록) ─────────────────────────────────────
RUN_LOG = ART / "run_history.csv"
PLAN_META = ART / "plan_meta.json"


def fingerprint(path):
    """파일 내용의 SHA-256 앞 12자리. 내용이 1바이트라도 바뀌면 달라진다."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def data_fingerprints():
    return {p: fingerprint(f) for p, f in PARTS.items()}


def log_run(step, **metrics):
    """실행 기록 한 줄을 artifacts/run_history.csv에 덧붙인다(시각 · 단계 · 데이터 지문 · 핵심 지표)."""
    ART.mkdir(exist_ok=True)
    row = pd.DataFrame([{"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "step": step,
                         **{f"data_{k}": v for k, v in data_fingerprints().items()},
                         "metrics": json.dumps(metrics, ensure_ascii=False)}])
    row.to_csv(RUN_LOG, mode="a", header=not RUN_LOG.exists(), index=False, encoding="utf-8-sig")


def load_model():
    import joblib
    if not MODEL_PATH.exists():
        raise FileNotFoundError("artifacts/drone_model.joblib 이 없습니다. drone-train 스킬을 먼저 실행하세요.")
    return joblib.load(MODEL_PATH), json.loads(CARD_PATH.read_text(encoding="utf-8"))


def md_table(df, floatfmt="{:,.3f}"):
    """tabulate 없이 md 표 만들기."""
    def f(v):
        if isinstance(v, (float, np.floating)):
            return "" if np.isnan(v) else (f"{v:,.0f}" if float(v).is_integer() else floatfmt.format(v))
        if isinstance(v, (int, np.integer)):
            return f"{v:,}"
        return str(v)
    head = "| " + " | ".join(map(str, df.columns)) + " |"
    sep = "|" + "|".join("---" for _ in df.columns) + "|"
    body = ["| " + " | ".join(f(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join([head, sep, *body])
