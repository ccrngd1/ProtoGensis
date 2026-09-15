#!/usr/bin/env python3
"""
P1: Warehouse builder - flatten generated world into wide ugly DuckDB table.
Column naming models REAL payor conventions (no rigged traps).
"""
import json
import duckdb

def build_warehouse(generate_path="generate", db_path="warehouse/claims.duckdb"):
    """Load generated JSONs and build wide claim-centric table."""

    # Load generated world
    with open(f"{generate_path}/members.json") as f:
        members = {m["member_id"]: m for m in json.load(f)}

    with open(f"{generate_path}/coverages.json") as f:
        coverages = {c["member_id"]: c for c in json.load(f)}

    with open(f"{generate_path}/providers.json") as f:
        providers = {p["tin"]: p for p in json.load(f)}

    with open(f"{generate_path}/claim_lines.json") as f:
        claim_lines = json.load(f)

    # Build wide rows: realistic payor column names (mix of conventions)
    # Header-level: CLM_, HCFA_, HDR_
    # Line-level: LN_, DTL_, SVC_
    # Financial: BILL_, ALW_, PD_, CHG_
    # Clinical: PROC_, DX_, MOD_
    # Status: STAT_, STS_, FLG_
    # Remittance: GRP_CD_, RSN_CD_, CAS_
    # Member: SUBSCR_, MBR_, PTNT_
    # Provider: SUPLR_, PRVD_, TIN_, NPI_

    rows = []
    for line in claim_lines:
        member = members.get(line["member_id"], {})
        coverage = coverages.get(line["member_id"], {})
        provider = providers.get(line["provider_tin"], {})

        # Real ambiguity: multiple grain/status columns, values carry meaning
        row = {
            # Claim header level
            "CLM_ID": line["claim_id"],
            "HDR_RCVD_DT": "2026-07-15",  # all received post-quarter
            "HCFA_1500_CLM_TYP_CD": "P",  # professional
            "HDR_TOT_CHG_AMT": line["billed_amt"],  # header sum (ambiguous w/ line)

            # Line level
            "LN_NBR": line["line_no"],
            "SVC_FROM_DT": line["service_date"],
            "SVC_TO_DT": line["service_date"],
            "PROC_CD": line["proc_code"],
            "REV_CD": "0450",  # outpatient imaging

            # Financial (line grain)
            "LN_BILL_AMT": line["billed_amt"],
            "LN_ALLOW_AMT": line["allowed_amt"],
            "LN_PD_AMT": line["paid_amt"],

            # Status codes (value carries semantic meaning)
            "CLP_02_CLM_STAT_CD": line["clp02_status"],  # 1=paid, 4=denied, 22=rev
            "LN_PROC_STS_CD": "P" if line["clp02_status"] == 1 else "D",
            "IS_REJECTED": 1 if line["is_rejection"] else 0,

            # Remittance adjustment
            "CAS_GRP_CD": line["group_code"],  # CO=contractual, PR=patient
            "CAS_RSN_CD": line["carc"],  # CARC - THE semantic key
            "CAS_ADJ_AMT": line["allowed_amt"] - line["paid_amt"],

            # Member
            "SUBSCR_ID": line["member_id"],
            "MBR_LAST_NM": member.get("name", ""),
            "MBR_DOB": str(member.get("dob", "")),
            "MBR_STATE_CD": line["state"],

            # Coverage
            "PLAN_CD": line["plan_code"],
            "COV_EFF_DT": coverage.get("effective_date", ""),
            "COV_TERM_DT": coverage.get("term_date", ""),

            # Provider
            "SUPLR_TIN": line["provider_tin"],
            "PRVD_NPI": provider.get("npi", ""),
            "PRVD_NM": provider.get("name", ""),
            "PRVD_SPEC_CD": provider.get("specialty", ""),
            "HLTH_SYS_ID": provider.get("health_system_id", ""),

            # Derived/computed flags (header grain, ambiguous)
            "HDR_DENY_FLG": "Y" if line["clp02_status"] == 4 else "N",
            "PROC_PAY_FLG": "N" if line["clp02_status"] == 4 else "Y",
        }
        rows.append(row)

    # Write to DuckDB using pandas-style registration
    conn = duckdb.connect(db_path)
    conn.execute("DROP TABLE IF EXISTS claim_lines")

    # Convert rows to proper format for DuckDB
    import pandas as pd
    df = pd.DataFrame(rows)
    conn.register("claim_lines_view", df)
    conn.execute("CREATE TABLE claim_lines AS SELECT * FROM claim_lines_view")
    conn.unregister("claim_lines_view")

    print(f"Warehouse built: {db_path}")
    print(f"  Table: claim_lines")
    print(f"  Rows: {conn.execute('SELECT COUNT(*) FROM claim_lines').fetchone()[0]}")
    print(f"  Columns: {len(conn.execute('PRAGMA table_info(claim_lines)').fetchall())}")

    # Write schema dump for ungoverned agent
    schema = conn.execute("PRAGMA table_info(claim_lines)").fetchall()
    with open("warehouse/schema.txt", "w") as f:
        f.write("Table: claim_lines\n")
        f.write("=" * 80 + "\n")
        for col in schema:
            f.write(f"{col[1]:<30} {col[2]:<15}\n")

    conn.close()
    return db_path

if __name__ == "__main__":
    build_warehouse()
