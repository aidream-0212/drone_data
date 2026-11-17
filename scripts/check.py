"""진행 확인 · 숫자 대조 — README 할 일 [1] ~ [8], 제출물 (1) ~ (3), 평가.
실행 (drone_data 폴더):  python scripts/check.py
파일을 만들지 않고 읽기만 한다. 각 항목 O(완료) / X(미완료 · 불일치)와 다음에 쓸 스킬을 보여 준다."""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import drone_lib as L  # noqa: E402

A, R = L.ART, L.REP


def txt(p):
    return p.read_text(encoding="utf-8") if p.exists() else ""


def step1():
    return (R / "eda_summary.md").exists(), "reports/eda_summary.md"


def step2():
    ok = (R / "preprocess_log.md").exists() and all((A / "clean" / f"drone_{p}_clean.csv").exists() for p in L.PARTS)
    return ok and "모두 통과" in txt(R / "preprocess_log.md"), "preprocess_log.md '모두 통과' · artifacts/clean 3개"


def step34():
    t = txt(R / "features_log.md")
    return (A / "features_all.csv").exists() and "불일치 **0건**" in t and "availability_rate" in t, "features_log 검산 0건 · 제외 컬럼"


def step56():
    if not L.CARD_PATH.exists():
        return False, "model_card.json 없음"
    c = json.loads(txt(L.CARD_PATH))
    ok = "availability_rate" not in c["features"] and {"300", "600"} <= set(c["threshold_by_miss_cost"])
    return ok, f"검증 PR-AUC {c['validation']['pr_auc']} · 기준 {c['threshold']} (600만원 {c['threshold_by_miss_cost']['600']['threshold']})"


def step7():
    if not L.SUBMIT_PATH.exists():
        return False, "outputs/test_predictions_2025.csv 없음"
    s = pd.read_csv(L.SUBMIT_PATH)
    return len(s) == 1241 and list(s.columns) == ["equipment_id", "maintenance_date", "prob"], f"{len(s):,}행"


def step8():
    p, s = R / "2026-01_재점검계획.md", A / "score_2026-01.csv"
    if not (p.exists() and s.exists()):
        return False, "재점검 계획 없음"
    sc = pd.read_csv(s).head(L.CAPACITY)
    rows = re.findall(r"^\| (\d+) \| (DR-\d+) \|[^|]*\|[^|]*\|[^|]*\|[^|]*\| ([\d.]+)% \|", txt(p), re.M)
    got = {(int(r), e, float(pr)) for r, e, pr in rows}
    want = {(int(r), e, round(pr * 100, 1)) for r, e, pr in zip(sc["rank"], sc.equipment_id, sc.prob)}
    return got == want and len(got) == L.CAPACITY, f"재점검 표 {len(got)}행 · score_2026-01.csv와 {'일치' if got == want else '불일치'}"


def report():
    t = txt(R / "분석보고서.md")
    if not t or not L.CARD_PATH.exists():
        return False, "reports/분석보고서.md 없음"
    c, e = json.loads(txt(L.CARD_PATH)), json.loads(txt(A / "evaluation.json") or "{}")
    figs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", t)
    missing = [f for f in figs if not (R / f).exists()]
    nums = [str(c["validation"]["pr_auc"]), str(c["threshold"]), str(c["threshold_by_miss_cost"]["600"]["threshold"])]
    if e:
        nums.append(str(e["test_2025"]["pr_auc"]))
    lack = [n for n in nums if n not in t]
    lim = all(x in t for x in c["limits"])
    return not missing and not lack and lim, f"그림 {len(figs)}개(없는 파일 {len(missing)}) · 핵심 숫자 누락 {lack or '없음'} · limits {'일치' if lim else '불일치'}"


def evaluation():
    p = A / "evaluation.json"
    if not p.exists():
        return False, "evaluation.json 없음"
    e = json.loads(txt(p))
    t = e["test_2025"]
    return e["all_pass"], (f"제출 형식 {'통과' if e['all_pass'] else '실패'} · 2025 PR-AUC {t['pr_auc']} (기준선 {t['base_rate']}) · "
                          f"20대 적중(드론 단위) {t['top20_hits_12m']['model']:.0f} vs 오래된 순 {t['top20_hits_12m']['oldest']:.0f}")


def lineage():
    """지문 연결: 지금 파일들의 지문이 각 단계가 기록한 지문과 같은가(데이터 교체 · 오래된 결과 탐지)."""
    c = json.loads(txt(L.CARD_PATH))["lineage"]
    e = json.loads(txt(A / "evaluation.json"))["lineage"]
    m = json.loads(txt(L.PLAN_META))
    now = {"data": L.data_fingerprints(), "model": L.fingerprint(L.MODEL_PATH),
           "submission": L.fingerprint(L.SUBMIT_PATH), "score": L.fingerprint(A / "score_2026-01.csv")}
    pairs = {
        "train · test 데이터 = 학습 때": all(now["data"][p] == c["data"][p] for p in ("train", "test")),
        "this_month 데이터 = 계획 때": now["data"]["this_month"] == m["data"]["this_month"],
        "모델 = 학습 · 평가 · 계획 때": now["model"] == c["model"] == e["model"] == m["model"],
        "제출 파일 = 학습 · 평가 때": now["submission"] == c["submission"] == e["submission"],
        "점수 파일 = 계획 때": now["score"] == m["score"],
        "보고서 지문 = 현재": all(x in txt(R / "분석보고서.md") for x in (now["model"], now["submission"], now["score"])),
    }
    bad = [k for k, ok in pairs.items() if not ok]
    return not bad, f"{len(pairs) - len(bad)}/{len(pairs)} 연결 일치" + (f" · 불일치: {bad}" if bad else "")


def recompute():
    """다시 계산 대조: 현재 데이터 + 저장된 모델로 시험 1,241건 · 이번 달 20대를 다시 계산해 저장된 결과와 비교한다."""
    model, card = L.load_model()
    s = L.split(L.load_all())
    te = s["test"].copy()
    te["prob"] = model.predict_proba(te[L.FEATURES])[:, 1]
    sub = pd.read_csv(L.SUBMIT_PATH)
    te["maintenance_date"] = te.maintenance_date.dt.strftime("%Y-%m-%d")
    mg = sub.merge(te[["equipment_id", "maintenance_date", "prob"]], on=["equipment_id", "maintenance_date"],
                   suffixes=("_saved", "_now"), how="outer", validate="1:1")
    diff_t = float((mg.prob_saved - mg.prob_now).abs().max())
    mo = L.latest_per_drone(s["month"]).copy()
    mo["prob"] = model.predict_proba(mo[L.FEATURES])[:, 1]
    now_top = list(mo.nlargest(L.CAPACITY, "prob").equipment_id)
    saved = pd.read_csv(A / "score_2026-01.csv")
    same_top = now_top == list(saved.head(L.CAPACITY).equipment_id)
    ok = len(mg) == 1241 and mg.isna().sum().sum() == 0 and diff_t < 1e-5 and same_top
    return ok, f"시험 {len(mg):,}건 확률 최대 차이 {diff_t:.1e} · 이번 달 20대 순위 {'같음' if same_top else '다름'}"


def verified():
    """drone-verify가 지금 결과(모델 · 제출 · 점수 지문)를 대상으로 '모두 통과'했는가."""
    t = txt(R / "verification.md")
    if not t:
        return False, "reports/verification.md 없음"
    fresh = all(L.fingerprint(p) in t for p in (L.MODEL_PATH, L.SUBMIT_PATH, A / "score_2026-01.csv"))
    passed = "**모두 통과**" in t
    full = "--quick" not in t
    return passed and fresh, (f"{'모두 통과' if passed else '실패 항목 있음'} · 지문 {'최신' if fresh else '오래됨(다시 검증 필요)'}"
                              f" · {'재현성 포함' if full else '재현성 제외(--quick)'}")


ITEMS = [("[1] 데이터 살펴보기", step1, "drone-eda"), ("[2] 데이터 처리 기준", step2, "drone-preprocess"),
         ("[3·4] 피처 · 쓸 컬럼", step34, "drone-features"), ("[5·6] 학습 · 검증 · 기준", step56, "drone-train"),
         ("[7] 제출물(1) 시험 예측", step7, "drone-train"), ("[8] 제출물(3) 재점검 계획", step8, "drone-plan"),
         ("평가 자체 점검", evaluation, "drone-evaluate"), ("제출물(2) 분석 보고서", report, "drone-report"),
         ("추적 · 지문 연결", lineage, "drone-train → plan → evaluate → report 다시 실행"),
         ("추적 · 다시 계산 대조", recompute, "drone-train → plan 다시 실행"),
         ("결과 검증(verify)", verified, "drone-verify")]

if __name__ == "__main__":
    done = []
    for name, fn, skill in ITEMS:
        try:
            ok, msg = fn()
        except Exception as ex:  # noqa: BLE001
            ok, msg = False, f"오류: {ex}"
        done.append(ok)
        print(f"{'O' if ok else 'X'}  {name:<18} {msg}" + ("" if ok else f"  → {skill} 스킬"))
    print("\n진행:", " ".join(f"{i + 1}{'O' if d else 'X'}" for i, d in enumerate(done)), f"({sum(done)}/{len(done)})")
