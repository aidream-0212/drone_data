"""결과 검증 — drone-verify 스킬.  실행: python .claude/skills/drone-verify/scripts/verify.py [--quick]
결과가 '맞게 계산됐는지'를 네 가지로 확인한다(예측이 맞았는지는 drone-evaluate의 몫).
  A 재현성      train · plan · evaluate를 다시 실행해 결과 파일이 바이트 단위로 같은가 (--quick이면 건너뜀)
  B 독립 대조    같은 값을 다른 방식으로 다시 계산해 일치하는가
  C 데이터 가정  코드가 전제한 데이터 조건(같은 날 중복 없음 등)이 지금 데이터에서 성립하는가
  D 결함 주입    일부러 바꾼 복사본을 추적 점검(check.py 9 · 10번)이 잡아내는가 — 원본 data/는 건드리지 않음
결과: reports/verification.md, run_history.csv에 한 줄"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
SK = ROOT / ".claude" / "skills"
for p in (ROOT, ROOT / "scripts", SK / "drone-evaluate" / "scripts", SK / "drone-features" / "scripts"):
    sys.path.insert(0, str(p))
import check as C  # noqa: E402
import drone_lib as L  # noqa: E402
import evaluate as E  # noqa: E402
import features as F  # noqa: E402
import plan_hits as P  # noqa: E402

CMD = "python .claude/skills/drone-verify/scripts/verify.py"
OUTS = [L.SUBMIT_PATH, L.ART / "score_2026-01.csv", L.CARD_PATH, L.ART / "evaluation.json", L.MODEL_PATH]
results = []


def add(group, item, expect, got, ok):
    results.append({"구분": group, "항목": item, "기대": expect, "결과": got, "판정": "통과" if ok else "**실패**"})


def a_reproduce():
    before = {p.name: L.fingerprint(p) for p in OUTS}
    for s in ["drone-train/scripts/train.py", "drone-plan/scripts/plan.py", "drone-evaluate/scripts/evaluate.py"]:
        r = subprocess.run([sys.executable, str(SK / s)], cwd=ROOT, capture_output=True)
        if r.returncode:
            add("A 재현성", s, "정상 종료", f"종료 코드 {r.returncode}", False)
            return
    after = {p.name: L.fingerprint(p) for p in OUTS}
    diff = [k for k in before if before[k] != after[k]]
    add("A 재현성", "다시 실행 후 결과 파일 지문", f"{len(OUTS)}개 모두 같음", "모두 같음" if not diff else f"다름: {diff}", not diff)


def b_cross(df, model, card, ev):
    re = F.recount_fail_90d(df)
    n = int((re != df.fail_count_90d).sum())
    add("B 독립 대조", "최근 90일 고장 수: 표 필터 방식 재계산", "불일치 0", f"불일치 {n} / {len(df):,}", n == 0)

    df = df.assign(y=E.rebuild_target(df))
    tr = df[df.part == "train"]
    rate = float((tr.y == tr[L.TARGET]).mean())
    add("B 독립 대조", "정답 재현 규칙 vs train 실제 정답", "일치율 100%", f"{rate * 100:.2f}%", rate == 1.0)

    mism, rows = 0, []
    for month in [f"2025-{m:02d}" for m in range(1, 13)]:
        plan, follow = P.sim_plan(df, model, month)        # plan 행에 재현 정답 y가 함께 들어 있다
        j, _ = P.judge(plan, follow)
        mism += int(((j.result == "재고장").astype(int) != j.y).sum())
        s = P.summarize(j, card["threshold"])
        rows.append((s["top20_hits"], s["oldest_hits"], s["failures"]))
    add("B 독립 대조", "계획 적중 판정(plan_hits) vs 정답 재현 함수, 2025 12개월", "불일치 0", f"불일치 {mism}", mism == 0)

    sim = [sum(r[i] for r in rows) for i in range(3)]
    t = ev["test_2025"]["top20_hits_12m"]
    want = [t["model"], t["oldest"], t["failures"]]
    add("B 독립 대조", "계획 적중 시험 합계 vs evaluate 드론 단위 합계 (모델 · 오래된 순 · 재고장)",
        f"{[int(x) for x in want]}", f"{sim}", [int(x) for x in want] == sim)

    ok, msg = C.recompute()
    add("B 독립 대조", "저장된 제출 · 이번 달 20대 vs 현재 데이터로 다시 계산", "최대 차이 < 1e-5 · 순위 같음", msg, ok)


def c_assume(df):
    raw = {p: L.load_raw(p) for p in L.PARTS}
    dup = {p: int(d.duplicated(["equipment_id", "maintenance_date"]).sum()) for p, d in raw.items()}
    cross = int(df.duplicated(["equipment_id", "maintenance_date"]).sum())
    add("C 데이터 가정", "같은 드론 · 같은 날 정비 기록(시간 피처 '같은 날 포함'의 전제)", "0건", f"{dup} · 파일 사이 {cross}",
        not any(dup.values()) and cross == 0)
    m = raw["this_month"]
    ties = int(m.groupby("equipment_id").maintenance_date.apply(lambda s: (s == s.max()).sum() > 1).sum())
    add("C 데이터 가정", "이번 달 드론별 최근 기록 동점(가장 최근 기록 선택의 전제)", "0대", f"{ties}대", ties == 0)
    unseen = {p: len(set(raw[p].equipment_id) - set(raw["train"].equipment_id)) for p in ("test", "this_month")}
    add("C 데이터 가정", "test · 이번 달 드론이 train에 있음(지난 기록 이어 계산의 전제)", "모두 있음", f"없는 드론 {unseen}",
        not any(unseen.values()))
    miss = [c for c in ("availability_rate", L.TARGET) if c in m]
    add("C 데이터 가정", "이번 달 파일에 누수 컬럼 · 정답 없음", "없음", f"있음: {miss}" if miss else "없음", not miss)
    nonpm = sum(int((d.fault_code.isna() & (d.maintenance_type != L.PM)).sum()) for d in raw.values())
    add("C 데이터 가정", "고장 코드 결측 = 예방정비('N/A' 채움의 전제)", "예외 0건", f"예외 {nonpm}건", nonpm == 0)


def d_inject():
    tmp = Path(tempfile.mkdtemp(prefix="drone_verify_"))
    orig = L.PARTS["this_month"]
    try:
        m = pd.read_csv(orig)
        m.loc[0, "severity"] = m.loc[0, "severity"] + 1
        m.to_csv(tmp / "month.csv", index=False)
        L.PARTS["this_month"] = tmp / "month.csv"
        ok, msg = C.lineage()
        add("D 결함 주입", "이번 달 데이터 1칸 변경(복사본)", "지문 연결 X", msg, not ok)
    finally:
        L.PARTS["this_month"] = orig
    bak = tmp / "sub.csv"
    shutil.copy(L.SUBMIT_PATH, bak)
    try:
        s = pd.read_csv(L.SUBMIT_PATH)
        s.loc[0, "prob"] = 1 - s.loc[0, "prob"]
        s.to_csv(L.SUBMIT_PATH, index=False)
        ok1, m1 = C.lineage()
        ok2, m2 = C.recompute()
        add("D 결함 주입", "제출 확률 1개 변경(복원 전제)", "지문 X · 다시 계산 X", f"{m1} / {m2}", not ok1 and not ok2)
    finally:
        shutil.copy(bak, L.SUBMIT_PATH)
        shutil.rmtree(tmp, ignore_errors=True)
    ok1, _ = C.lineage()
    ok2, _ = C.recompute()
    add("D 결함 주입", "복원 뒤 다시 점검", "지문 O · 다시 계산 O", f"{'O' if ok1 else 'X'} · {'O' if ok2 else 'X'}", ok1 and ok2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="A 재현성(다시 실행)을 건너뜀")
    a = ap.parse_args()
    if not a.quick:
        a_reproduce()
    model, card = L.load_model()
    ev = json.loads((L.ART / "evaluation.json").read_text(encoding="utf-8"))
    df = L.load_all()
    b_cross(df, model, card, ev)
    c_assume(df)
    d_inject()

    r = pd.DataFrame(results)
    ok = bool((r.판정 == "통과").all())
    fp = {"model": L.fingerprint(L.MODEL_PATH), "submission": L.fingerprint(L.SUBMIT_PATH),
          "score": L.fingerprint(L.ART / "score_2026-01.csv")}
    out = ["# 결과 검증 기록", "", f"생성: `{CMD}{' --quick' if a.quick else ''}` · drone-verify 스킬", "",
           "결과가 **맞게 계산됐는지**(재현성 · 독립 대조 · 데이터 가정 · 결함 감지)를 확인한다. "
           "예측이 실제로 맞았는지는 `reports/evaluation.md` · `reports/plan_hits_*.md`에서 본다.", "",
           L.md_table(r), "",
           f"- 종합: **{'모두 통과' if ok else '실패 항목 있음'}** ({int((r.판정 == '통과').sum())}/{len(r)})",
           f"- 검증한 결과의 지문: 모델 `{fp['model']}` · 제출 `{fp['submission']}` · 이번 달 점수 `{fp['score']}`",
           "- A를 건너뛰었으면(--quick) 재현성은 이번 검증에 포함되지 않았다." if a.quick else "", ""]
    (L.REP / "verification.md").write_text("\n".join(out), encoding="utf-8")
    L.log_run("verify", passed=int((r.판정 == "통과").sum()), total=len(r), quick=a.quick, **fp)
    for x in results:
        print(f"{'O' if x['판정'] == '통과' else 'X'}  [{x['구분']}] {x['항목']} → {x['결과']}")
    print(f"\n종합: {'모두 통과' if ok else '실패 항목 있음'} ({int((r.판정 == '통과').sum())}/{len(r)}) · 저장: reports/verification.md")


if __name__ == "__main__":
    main()
