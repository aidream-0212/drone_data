"""drone-plan 결과(artifacts/score_2026-01.csv)를 Supabase 테이블에 올린다.

- 연결 정보: .streamlit/secrets.toml 의 [connections.supabase] (git에 올리지 않음)
- 테이블: public.drone_score_2026_01 — 실행할 때마다 통째로 교체한다
- 값은 drone-plan 출력 그대로 올린다(다시 계산하지 않음). 지문 열 score_fp 로 어느 결과인지 확인한다.

실행: python scripts/upload_scores.py
"""
import hashlib
import json
import tomllib
from pathlib import Path

import pandas as pd
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
SCORE = ROOT / "artifacts" / "score_2026-01.csv"
META = ROOT / "artifacts" / "plan_meta.json"
SECRETS = ROOT / ".streamlit" / "secrets.toml"
TABLE = "drone_score_2026_01"


def engine() -> sa.Engine:
    c = tomllib.loads(SECRETS.read_text(encoding="utf-8"))["connections"]["supabase"]
    drivername = f"{c['dialect']}+{c['driver']}" if c.get("driver") else c["dialect"]
    url = sa.URL.create(
        drivername,
        username=c["username"],
        password=c["password"],
        host=c["host"],
        port=int(c["port"]),
        database=c["database"],
        query=c.get("query", {}),
    )
    return sa.create_engine(url, connect_args={"connect_timeout": 15})


def main() -> None:
    fp = hashlib.sha256(SCORE.read_bytes()).hexdigest()[:12]
    meta_fp = json.loads(META.read_text(encoding="utf-8")).get("score")
    if meta_fp and meta_fp != fp:
        raise SystemExit(f"지문 불일치: score 파일 {fp} ≠ plan_meta {meta_fp}. drone-plan을 다시 실행한다.")

    # 'N/A'(예방정비 · 고장 없음)를 결측으로 바꾸지 않도록 빈칸만 결측으로 읽는다
    df = pd.read_csv(SCORE, encoding="utf-8-sig", keep_default_na=False, na_values=[""])
    df["maintenance_date"] = pd.to_datetime(df["maintenance_date"]).dt.date
    df["score_fp"] = fp

    eng = engine()
    with eng.begin() as con:
        df.to_sql(TABLE, con, schema="public", if_exists="replace", index=False)
        n = con.execute(sa.text(f'select count(*) from public."{TABLE}"')).scalar()
    print(f"업로드 완료: public.{TABLE} {n}행 (score 지문 {fp})")


if __name__ == "__main__":
    main()
