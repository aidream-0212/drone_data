"""README '5. 평가' 채점표(100점) + 필수 조건으로 현재 결과를 채점한다.

실행: python scripts/score_eval.py            (check.py를 함께 실행, 약 1분)
      python scripts/score_eval.py --no-check (check.py 생략 — 필수 조건 G2는 '확인 안 함'으로 불합격)
결과: artifacts/eval_score.json (앱 '검증 결과'가 이 파일만 읽는다) · artifacts/run_history.csv 한 줄

채점표 (사용자 승인안, 2026-11-17)
  A 시험 성능 vs 기준선 40  — A1 2025 PR-AUC 20 · A2 12개월 20대 적중 합 20
                               합격선은 미리 정해 두고, 2025 결과를 보고 모델을 고치지 않는다(AGENTS.md).
  B 근거 타당성 30         — B1 데이터 처리 10 · B2 컬럼 선택 10 · B3 기간 분할 · 기준 선택 10
  C 숫자 일치 30           — C1 분석 보고서 숫자 15 · C2 재점검 계획 10 · C3 숫자 출처 표기 5
  필수 조건(하나라도 X면 점수와 관계없이 불합격)
    G1 제출물(1) 형식 · G2 check.py 11/11 · G3 독립 검증 노트북 전부 통과(현재 지문으로 실행) · G4 앱 DB 지문 = 현재 score 지문
자동 판정 범위: B는 '근거가 적혀 있고 숫자가 맞는가'까지 본다. 근거가 업무상 타당한지는 사람이 판단한다.
"""
import json
import re
import subprocess
import sys
import tomllib
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import drone_lib as L  # noqa: E402  (지문 · 실행 기록 함수만 쓴다)

ART, REP = ROOT / "artifacts", ROOT / "reports"
PASS_MARK = 95


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


card, plan_meta, ev = jload(ART / "model_card.json"), jload(ART / "plan_meta.json"), jload(ART / "evaluation.json")
report = (REP / "분석보고서.md").read_text(encoding="utf-8")
plan_md = (REP / "2026-01_재점검계획.md").read_text(encoding="utf-8")
score = pd.read_csv(ART / "score_2026-01.csv", encoding="utf-8-sig", keep_default_na=False, na_values=[""])
FP = {"score": L.fingerprint(ART / "score_2026-01.csv"), "model": L.fingerprint(L.MODEL_PATH),
      "submission": L.fingerprint(L.SUBMIT_PATH), **{f"data_{k}": v for k, v in L.data_fingerprints().items()}}

items, gates = [], []


def item(key, area, name, got, mx, detail):
    items.append({"key": key, "area": area, "name": name, "score": round(float(got), 2), "max": mx, "detail": detail})


def gate(key, name, ok, detail):
    gates.append({"key": key, "name": name, "pass": bool(ok), "detail": detail})


def section(md, title_regex):
    """'## n. 제목' 절 본문(다음 '## '까지)."""
    m = re.search(rf"^## [^\n]*{title_regex}[^\n]*\n(.*?)(?=^## |\Z)", md, flags=re.M | re.S)
    return m.group(1) if m else ""


def table_rows(text):
    """마크다운 표의 데이터 행(구분선 · 머리글 제외)을 칸 목록으로."""
    rows, lines = [], [ln for ln in text.splitlines() if ln.strip().startswith("|")]
    for i, ln in enumerate(lines):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if i == 0 or set("".join(cells)) <= set("-: "):
            continue
        rows.append(cells)
    return rows


# ── 필수 조건 ─────────────────────────────────────────────
sub_ok = bool(ev.get("all_pass"))
gate("G1", "제출물(1) 형식", sub_ok, f"evaluation.json submission_checks {sum(ev['submission_checks'].values())}/{len(ev['submission_checks'])}")

if "--no-check" in sys.argv:
    gate("G2", "check.py 11/11", False, "확인 안 함(--no-check)")
else:
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "check.py")], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    m = re.search(r"\((\d+)/(\d+)\)", out.stdout)
    gate("G2", "check.py 11/11", bool(m and m.group(1) == m.group(2) == "11"),
         f"check.py {m.group(0) if m else '결과 읽기 실패'}")

nb_path = REP / "independent_verification.ipynb"
nb_text = ""
if nb_path.exists():
    nb = jload(nb_path)
    nb_text = "\n".join("".join(o.get("text", "")) if o.get("output_type") == "stream" else "".join(o.get("data", {}).get("text/plain", ""))
                        for c in nb["cells"] if c["cell_type"] == "code" for o in c.get("outputs", []))
m = re.search(r"통과 (\d+) / (\d+)\s+·\s+X (\d+)건", nb_text)
fresh = FP["score"] in nb_text
gate("G3", "독립 검증 노트북 전부 통과(현재 지문)", bool(m and m.group(3) == "0" and fresh),
     (f"{m.group(1)}/{m.group(2)} · X {m.group(3)}건" if m else "노트북 결과 없음") + (" · 현재 score 지문으로 실행" if fresh else " · 옛 지문으로 실행됨(다시 실행 필요)"))

try:
    import sqlalchemy as sa
    c = tomllib.loads((ROOT / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["connections"]["supabase"]
    url = sa.URL.create(f"{c['dialect']}+{c['driver']}" if c.get("driver") else c["dialect"], username=c["username"],
                        password=c["password"], host=c["host"], port=int(c["port"]), database=c["database"], query=c.get("query", {}))
    with sa.create_engine(url, connect_args={"connect_timeout": 15}).connect() as con:
        db_fp = [r[0] for r in con.execute(sa.text('select distinct score_fp from public."drone_score_2026_01"'))]
    gate("G4", "앱 DB 지문 = 현재 score 지문", db_fp == [FP["score"]], f"DB {db_fp} · 현재 {FP['score']}")
except Exception as e:  # 연결 실패도 불합격(확인 불가)
    gate("G4", "앱 DB 지문 = 현재 score 지문", False, f"확인 불가: {type(e).__name__}")

# ── A 시험 성능 vs 기준선 (합격선 고정) ─────────────────────
T = ev["test_2025"]
lift = T["pr_auc"] / T["base_rate"]
a1 = 20 if lift >= 2 else 10 if lift >= 1.5 else 0          # 1 ~ 1.5배 구간은 보수적으로 0점
item("A1", "A", "2025 PR-AUC vs 기준선(재고장 비율)", a1, 20, f"{T['pr_auc']} / {T['base_rate']} = {lift:.2f}배 (2배 이상 20 · 1.5배 이상 10)")
h = T["top20_hits_12m"]
base = max(h["oldest"], h["random"])
ratio = h["model"] / base
a2 = 20 if ratio >= 1.5 else 10 if ratio > 1 else 0
item("A2", "A", "12개월 20대 적중 합 vs 오래된 순 · 무작위", a2, 20,
     f"모델 {h['model']:.0f} / max(오래된 순 {h['oldest']:.0f}, 무작위 {h['random']:.1f}) = {ratio:.2f}배 (1.5배 이상 20 · 1배 초과 10)")

# ── B 근거 타당성 ─────────────────────────────────────────
s3 = section(report, "데이터 처리 기준")
rules = {"999": "downtime_hours = 999", "÷100": "maintenance_cost > 10,000", "N/A": "fault_code · fault_category 결측",
         "첫 정비": "days_since_last_maintenance 결측"}
rows = table_rows(s3)
got, miss = 0, []
for key, label in rules.items():
    r = next((r for r in rows if r[0].startswith(label.split(" ")[0])), None)
    if r and len(r) >= 4 and r[3] and r[1]:
        got += 2
    else:
        miss.append(label)
pre = (REP / "preprocess_log.md").read_text(encoding="utf-8")
no_drop = "행 수 유지(삭제 없음): 통과" in pre
got += 2 if no_drop else 0
item("B1", "B", "데이터 처리 기준 · 근거", got, 10, ("규칙 4개 근거 · 건수 기재" if not miss else f"근거 빠짐: {miss}") + f" · 행 삭제 0 {'O' if no_drop else 'X'}")

s4 = section(report, "넣지 않은 컬럼")
excl_rows = {r[0]: r[1] for r in table_rows(s4) if len(r) >= 2}
got = sum(1 for c in card["excluded"] if excl_rows.get(c))
import joblib  # noqa: E402
used = set(joblib.load(L.MODEL_PATH).feature_names_in_)
leak = sorted((set(card["excluded"]) | {"availability_rate", L.TARGET}) & (used | set(card["features"])))
got += 5 if not leak else 0
item("B2", "B", "컬럼 선택 · 누수 제외", got, 10, f"제외 컬럼 이유 {sum(1 for c in card['excluded'] if excl_rows.get(c))}/5 · 모델 입력 누수 {leak or '없음'}")

sp = card["split"]
dates = {k: re.findall(r"\d{4}-\d{2}-\d{2}", v) for k, v in sp.items()}
period_ok = all(k in sp for k in ("fit", "val", "final_train", "test")) and dates["fit"][-1] < dates["val"][0] and "2025" in sp["test"]
thr_ok = card["threshold"] == card["threshold_by_miss_cost"]["300"]["threshold"] and "검증" in card["threshold_rule"]
s6 = section(report, "위험 표시 기준")
cmp_ok = all(f"| {m} | {card['threshold_by_miss_cost'][m]['threshold']:.3f} |" in s6 for m in ("300", "600"))
not_test = "시험 기간(2025)으로 고르지 않았다" in s6
got = 3 * period_ok + 3 * thr_ok + 2 * cmp_ok + 2 * not_test
item("B3", "B", "기간 분할 · 기준 선택", got, 10,
     f"기간 분할 {'O' if period_ok else 'X'} · 검증 기간 비용 최소 {'O' if thr_ok else 'X'} · 300/600 비교 {'O' if cmp_ok else 'X'} · '시험으로 고르지 않음' 명시 {'O' if not_test else 'X'}")

# ── C 숫자 일치 ───────────────────────────────────────────
V, tb = card["validation"], card["threshold_by_miss_cost"]
key_numbers = {
    "검증 PR-AUC": f"{V['pr_auc']}", "검증 기준선": f"{V['base_rate']}", "검증 ROC-AUC": f"{V['roc_auc']}",
    "시험 PR-AUC": f"{T['pr_auc']}", "시험 기준선": f"{T['base_rate']}", "시험 ROC-AUC": f"{T['roc_auc']}",
    "검증 20대 모델": f"{V['top20_hits_6m']['model']:.0f}", "검증 20대 오래된 순": f"{V['top20_hits_6m']['oldest']:.0f}",
    "검증 20대 무작위": f"{V['top20_hits_6m']['random']:.1f}",
    "시험 20대 모델": f"{h['model']:.0f}", "시험 20대 오래된 순": f"{h['oldest']:.0f}", "시험 20대 무작위": f"{h['random']:.1f}",
    "임계값 300": f"{card['threshold']}", "임계값 600": f"{tb['600']['threshold']}",
    "기준 이상 300": f"{tb['300']['flagged']}", "기준 이상 600": f"{tb['600']['flagged']}",
    "총비용 300": f"{tb['300']['cost']:,}", "총비용 600": f"{tb['600']['cost']:,}",
    "이번 달 기준 이상": f"{plan_meta['over_threshold']}대", "이번 달 드론": f"{plan_meta['drones']}대",
}
missing = [k for k, v in key_numbers.items() if not re.search(rf"(?<![\d.]){re.escape(v)}(?![\d])", report)]
s10 = section(report, "추적 정보")
fp_rows = {r[0]: r[1] for r in table_rows(s10) if len(r) >= 2}
fp_expect = {"원본 train": FP["data_train"], "원본 test": FP["data_test"], "원본 this_month": FP["data_this_month"],
             "모델": FP["model"], "제출 파일": FP["submission"], "이번 달 점수": FP["score"]}
fp_bad = [k for k, v in fp_expect.items() if fp_rows.get(k) != v]
n_ok = len(key_numbers) - len(missing) + len(fp_expect) - len(fp_bad)
n_all = len(key_numbers) + len(fp_expect)
item("C1", "C", "분석 보고서 숫자 = 결과 파일", 15 * n_ok / n_all, 15,
     f"핵심 숫자 {len(key_numbers) - len(missing)}/{len(key_numbers)} · 지문 {len(fp_expect) - len(fp_bad)}/{len(fp_expect)}"
     + (f" · 없음/불일치: {missing + fp_bad}" if missing or fp_bad else ""))

p2 = section(plan_md, "재점검 대상 20대")
prow = [r for r in table_rows(p2) if r and r[0].isdigit()]
top = score.head(L.CAPACITY)
match = sum(1 for r, (_, s) in zip(prow, top.iterrows())
            if int(r[0]) == s["rank"] and r[1] == s["equipment_id"] and r[6] == f"{s['prob'] * 100:.1f}%")
got = 6 * match / L.CAPACITY if len(prow) == L.CAPACITY else 0
over_ok = f"**{plan_meta['over_threshold']}대**" in plan_md
extra = int(((score["rank"] > L.CAPACITY) & (score["over_threshold"] == 1)).sum())
extra_ok = f"({extra}대)" in plan_md and "처리 방안" in plan_md
limits_ok = all(x in plan_md and x in report for x in card["limits"])
got += 1 * over_ok + 1.5 * extra_ok + 1.5 * limits_ok
item("C2", "C", "재점검 계획 = score 파일", got, 10,
     f"20대 순위 · 드론 · 확률 {match}/{L.CAPACITY} · 기준 이상 {plan_meta['over_threshold']}대 {'O' if over_ok else 'X'} · "
     f"20대 밖 {extra}대 처리 방안 {'O' if extra_ok else 'X'} · limits 그대로 {'O' if limits_ok else 'X'}")

src = re.compile(r"`[^`]*(artifacts/|reports/|outputs/|README|model_card|evaluation\.json|plan_meta)[^`]*`|\(README\)")
paras = re.findall(r"\*\*무엇을 보여 주는가\*\*[^\n]*", report)
cited = [bool(src.search(p)) for p in paras]
uncited = [p[:40] + "…" for p, ok in zip(paras, cited) if not ok]
item("C3", "C", "숫자 출처 표기(표 · 그림 설명마다)", 5 * sum(cited) / max(len(paras), 1), 5,
     f"'무엇을 보여 주는가' {sum(cited)}/{len(paras)}곳에 출처 파일" + (f" · 출처 없음: {uncited}" if uncited else ""))

# ── 종합 ──────────────────────────────────────────────────
total = round(sum(i["score"] for i in items), 1)
gates_ok = all(g["pass"] for g in gates)
result = {
    "scored_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "command": "python scripts/score_eval.py",
    "rubric": "README 5. 평가 채점표(A 40 · B 30 · C 30) + 필수 조건 G1 ~ G4",
    "pass_mark": PASS_MARK,
    "total": total,
    "gates_pass": gates_ok,
    "passed": gates_ok and total >= PASS_MARK,
    "areas": {a: {"score": round(sum(i["score"] for i in items if i["area"] == a), 1), "max": sum(i["max"] for i in items if i["area"] == a)}
              for a in "ABC"},
    "items": items,
    "gates": gates,
    "scope_note": "B는 근거 기재 · 숫자 일치까지 자동 판정한다. 근거의 업무상 타당성은 사람이 판단한다. "
                  "A의 2025 정답은 README 정의로 재현한 값이며 강사 채점과 다를 수 있다.",
    "lineage": FP,
}
(ART / "eval_score.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
L.log_run("score_eval", total=total, gates_pass=gates_ok, passed=result["passed"], score=FP["score"])

for g in gates:
    print(f"{'O' if g['pass'] else 'X'}  [{g['key']}] {g['name']} — {g['detail']}")
for i in items:
    print(f"{i['score']:>5.1f}/{i['max']:<3} [{i['key']}] {i['name']} — {i['detail']}")
print(f"\n총점 {total} / 100 · 필수 조건 {'통과' if gates_ok else '불합격'} · 판정 {'합격' if result['passed'] else '미달'} (합격선 {PASS_MARK}) · 저장: artifacts/eval_score.json")
