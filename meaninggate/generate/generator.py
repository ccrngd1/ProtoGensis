#!/usr/bin/env python3
"""
P1: Deterministic synthetic payor world generator.
Produces: members, coverage, claims, lines, 835 remittance, providers, health systems,
UM policies, 278 auth requests (with deliberate HS-14 gap), and truth.json ground truth.
"""
import random
import json
from datetime import date, timedelta
from dataclasses import dataclass, asdict
from typing import List, Optional

SEED = 42
random.seed(SEED)

# Ohio imaging scenario: Q2 2026 (Apr-Jun)
QUARTER_START = date(2026, 4, 1)
QUARTER_END = date(2026, 6, 30)

# CARC taxonomy (real codes, semantic families)
DENIAL_CARCS = {197, 198, 199, 96, 16}  # real denials
AUTH_FAMILY = {197, 198, 199}  # authorization-defect subset
CONTRACTUAL_REDUCTION = {45}  # fee schedule, not a denial
DUPLICATE = {18}

@dataclass
class Member:
    member_id: str
    name: str
    dob: date
    state: str

@dataclass
class Coverage:
    coverage_id: str
    member_id: str
    plan_code: str
    plan_name: str
    effective_date: date
    term_date: Optional[date]

@dataclass
class Provider:
    tin: str
    npi: str
    name: str
    health_system_id: Optional[str]
    specialty: str

@dataclass
class ClaimLine:
    claim_id: str
    line_no: int
    member_id: str
    provider_tin: str
    service_date: date
    proc_code: str
    billed_amt: float
    allowed_amt: float
    paid_amt: float
    clp02_status: int  # 1=paid, 4=denied, 22=reversal
    group_code: str  # CO or PR
    carc: int
    is_rejection: bool  # 277CA front-end reject
    state: str
    plan_code: str

@dataclass
class AuthRequest:
    auth_id: str
    member_id: str
    provider_tin: str
    service_date: date
    proc_code: str
    notification_cohort: str

@dataclass
class UMPolicy:
    policy_id: str
    effective_date: date
    requires_278_notice: bool
    notice_days: int

@dataclass
class MedicalPolicy:
    policy_id: str
    section: str
    text: str

def gen_date_in_quarter():
    days = (QUARTER_END - QUARTER_START).days
    return QUARTER_START + timedelta(days=random.randint(0, days))

def generate_world(n_members=500, n_claims=4000):
    """Generate the complete synthetic world."""

    # Members
    members = []
    for i in range(n_members):
        members.append(Member(
            member_id=f"MBR-{i:06d}",
            name=f"Member {i}",
            dob=date(1970, 1, 1) + timedelta(days=random.randint(0, 18250)),
            state="OH"
        ))

    # Coverage (all active in Q2 2026)
    coverages = []
    for m in members:
        coverages.append(Coverage(
            coverage_id=f"COV-{m.member_id}",
            member_id=m.member_id,
            plan_code="ACME-PPO-OH",
            plan_name="ACME Commercial PPO - Ohio",
            effective_date=date(2026, 1, 1),
            term_date=None
        ))

    # Health System 14 (HS-14) with 9 TINs
    hs14_tins = [f"HS14-TIN-{i:02d}" for i in range(9)]

    # Providers: imaging specialists, mix of HS-14 and others
    providers = []
    for i, tin in enumerate(hs14_tins):
        providers.append(Provider(
            tin=tin,
            npi=f"NPI-{tin}",
            name=f"HS-14 Imaging Center {i+1}",
            health_system_id="HS-14",
            specialty="Radiology"
        ))

    # Add some non-HS-14 providers
    for i in range(10):
        tin = f"OTHER-TIN-{i:02d}"
        providers.append(Provider(
            tin=tin,
            npi=f"NPI-{tin}",
            name=f"Independent Imaging {i+1}",
            health_system_id=None,
            specialty="Radiology"
        ))

    # UM Policy (effective 2026-04-01, requiring 120-day prior auth notice)
    um_policy = UMPolicy(
        policy_id="UM-RAD-2026",
        effective_date=date(2026, 4, 1),
        requires_278_notice=True,
        notice_days=120
    )

    # Medical policy
    med_policy = MedicalPolicy(
        policy_id="MP-RAD-114",
        section="4.2",
        text="Outpatient imaging requires prior authorization per UM-RAD-2026. "
             "Authorization requests via X12 278 must be submitted 120 days in advance "
             "per contract §7.3. Failure to notify results in CARC-197 denial."
    )

    # Claims and lines
    claim_lines = []
    auth_requests = []

    # Track HS-14 spike scenario
    hs14_denied_lines = []

    for c in range(n_claims):
        claim_id = f"CLM-{c:06d}"
        member = random.choice(members)
        provider = random.choice(providers)
        svc_date = gen_date_in_quarter()
        proc_code = random.choice(["70450", "70551", "71250", "72148"])  # CT/MRI codes

        # Front-end rejection (8%)
        if random.random() < 0.08:
            claim_lines.append(ClaimLine(
                claim_id=claim_id,
                line_no=1,
                member_id=member.member_id,
                provider_tin=provider.tin,
                service_date=svc_date,
                proc_code=proc_code,
                billed_amt=1500.0,
                allowed_amt=0.0,
                paid_amt=0.0,
                clp02_status=0,
                group_code="",
                carc=0,
                is_rejection=True,
                state="OH",
                plan_code="ACME-PPO-OH"
            ))
            continue

        # Lines per claim
        n_lines = random.choices([1, 2, 3], weights=[60, 30, 10])[0]

        for ln in range(1, n_lines + 1):
            billed = round(random.uniform(800, 2500), 2)
            allowed = round(billed * random.uniform(0.6, 0.9), 2)

            r = random.random()

            if r < 0.11:  # Real denial
                # HS-14 + new UM policy -> CARC-197 (auth missing)
                # This is the spike: HS-14 was omitted from notification cohort
                if provider.health_system_id == "HS-14" and svc_date >= um_policy.effective_date:
                    carc = 197
                    paid = 0.0
                    hs14_denied_lines.append((claim_id, ln, allowed))
                else:
                    carc = random.choice([197, 96, 16])
                    paid = 0.0

                claim_lines.append(ClaimLine(
                    claim_id=claim_id,
                    line_no=ln,
                    member_id=member.member_id,
                    provider_tin=provider.tin,
                    service_date=svc_date,
                    proc_code=proc_code,
                    billed_amt=billed,
                    allowed_amt=allowed,
                    paid_amt=paid,
                    clp02_status=4,
                    group_code="CO",
                    carc=carc,
                    is_rejection=False,
                    state="OH",
                    plan_code="ACME-PPO-OH"
                ))

            elif r < 0.16:  # Fee schedule reduction (not a denial)
                paid = round(allowed * 0.8, 2)
                claim_lines.append(ClaimLine(
                    claim_id=claim_id,
                    line_no=ln,
                    member_id=member.member_id,
                    provider_tin=provider.tin,
                    service_date=svc_date,
                    proc_code=proc_code,
                    billed_amt=billed,
                    allowed_amt=allowed,
                    paid_amt=paid,
                    clp02_status=1,
                    group_code="CO",
                    carc=45,
                    is_rejection=False,
                    state="OH",
                    plan_code="ACME-PPO-OH"
                ))

            elif r < 0.20:  # Patient responsibility
                paid = 0.0
                claim_lines.append(ClaimLine(
                    claim_id=claim_id,
                    line_no=ln,
                    member_id=member.member_id,
                    provider_tin=provider.tin,
                    service_date=svc_date,
                    proc_code=proc_code,
                    billed_amt=billed,
                    allowed_amt=allowed,
                    paid_amt=paid,
                    clp02_status=1,
                    group_code="PR",
                    carc=1,
                    is_rejection=False,
                    state="OH",
                    plan_code="ACME-PPO-OH"
                ))

            elif r < 0.23:  # Duplicate
                claim_lines.append(ClaimLine(
                    claim_id=claim_id,
                    line_no=ln,
                    member_id=member.member_id,
                    provider_tin=provider.tin,
                    service_date=svc_date,
                    proc_code=proc_code,
                    billed_amt=billed,
                    allowed_amt=allowed,
                    paid_amt=0.0,
                    clp02_status=4,
                    group_code="CO",
                    carc=18,
                    is_rejection=False,
                    state="OH",
                    plan_code="ACME-PPO-OH"
                ))

            elif r < 0.26:  # Reversal
                claim_lines.append(ClaimLine(
                    claim_id=claim_id,
                    line_no=ln,
                    member_id=member.member_id,
                    provider_tin=provider.tin,
                    service_date=svc_date,
                    proc_code=proc_code,
                    billed_amt=billed,
                    allowed_amt=allowed,
                    paid_amt=0.0,
                    clp02_status=22,
                    group_code="CO",
                    carc=0,
                    is_rejection=False,
                    state="OH",
                    plan_code="ACME-PPO-OH"
                ))

            else:  # Clean paid
                paid = allowed
                claim_lines.append(ClaimLine(
                    claim_id=claim_id,
                    line_no=ln,
                    member_id=member.member_id,
                    provider_tin=provider.tin,
                    service_date=svc_date,
                    proc_code=proc_code,
                    billed_amt=billed,
                    allowed_amt=allowed,
                    paid_amt=paid,
                    clp02_status=1,
                    group_code="CO",
                    carc=0,
                    is_rejection=False,
                    state="OH",
                    plan_code="ACME-PPO-OH"
                ))

    # Auth requests: notification cohort NC-2026-03 OMITS HS-14 (the gap)
    for provider in providers:
        if provider.health_system_id != "HS-14":  # HS-14 deliberately omitted
            for _ in range(random.randint(5, 15)):
                auth_requests.append(AuthRequest(
                    auth_id=f"AUTH-{provider.tin}-{random.randint(1000, 9999)}",
                    member_id=random.choice(members).member_id,
                    provider_tin=provider.tin,
                    service_date=gen_date_in_quarter(),
                    proc_code=random.choice(["70450", "70551", "71250", "72148"]),
                    notification_cohort="NC-2026-03"
                ))

    # Compute ground truth
    # Governed path should find: first_pass_line_denial_rate spike,
    # CARC-197 dominance, HS-14 root cause, $X at risk

    adjudicated = [l for l in claim_lines if not l.is_rejection]
    eligible = [l for l in adjudicated
                if l.clp02_status != 22  # not reversal
                and l.group_code != "PR"  # not patient resp
                and l.carc not in DUPLICATE  # not duplicate
                and l.carc not in CONTRACTUAL_REDUCTION]  # not fee schedule

    denied = [l for l in eligible if l.clp02_status == 4 and l.carc in DENIAL_CARCS]
    baseline_rate = len([l for l in eligible if l.clp02_status == 4 and l.carc in DENIAL_CARCS]) / len(eligible) if eligible else 0.0

    # HS-14 contribution to the spike
    hs14_denied_allowed = sum(amt for _, _, amt in hs14_denied_lines)
    carc197_count = sum(1 for l in denied if l.carc in AUTH_FAMILY)
    carc197_pct = carc197_count / len(denied) if denied else 0.0

    truth = {
        "question": "Our outpatient imaging denials spiked in Ohio last quarter. Why, and what is it costing us?",
        "governed_answer": {
            "metric": "first_pass_line_denial_rate",
            "metric_version": "v4.2",
            "rate_pct": round(baseline_rate * 100, 1),
            "eligible_lines": len(eligible),
            "denied_lines": len(denied),
            "carc_197_dominance_pct": round(carc197_pct * 100, 1),
            "root_cause": "UM-RAD-2026 policy effective 2026-04-01 requires 120-day prior auth notice per MP-RAD-114 §4.2 and contract §7.3. Health System 14 (HS-14) was omitted from notification cohort NC-2026-03, resulting in CARC-197 denials for all HS-14 outpatient imaging.",
            "accountable_party": "Plan (ACME Commercial PPO - Ohio) - notification gap",
            "at_risk_allowed_dollars": round(hs14_denied_allowed, 2),
            "hs14_tins": hs14_tins,
            "remediation": "Add HS-14 TINs to notification cohort and reprocess denied claims under appeal."
        }
    }

    return {
        "members": members,
        "coverages": coverages,
        "providers": providers,
        "um_policy": um_policy,
        "med_policy": med_policy,
        "claim_lines": claim_lines,
        "auth_requests": auth_requests,
        "truth": truth
    }

def write_world(world, base_path="."):
    """Write generated world to JSON files."""
    import os
    os.makedirs(base_path, exist_ok=True)

    with open(f"{base_path}/members.json", "w") as f:
        json.dump([asdict(m) for m in world["members"]], f, indent=2, default=str)

    with open(f"{base_path}/coverages.json", "w") as f:
        json.dump([asdict(c) for c in world["coverages"]], f, indent=2, default=str)

    with open(f"{base_path}/providers.json", "w") as f:
        json.dump([asdict(p) for p in world["providers"]], f, indent=2, default=str)

    with open(f"{base_path}/claim_lines.json", "w") as f:
        json.dump([asdict(l) for l in world["claim_lines"]], f, indent=2, default=str)

    with open(f"{base_path}/auth_requests.json", "w") as f:
        json.dump([asdict(a) for a in world["auth_requests"]], f, indent=2, default=str)

    with open(f"{base_path}/um_policy.json", "w") as f:
        json.dump(asdict(world["um_policy"]), f, indent=2, default=str)

    with open(f"{base_path}/med_policy.json", "w") as f:
        json.dump(asdict(world["med_policy"]), f, indent=2, default=str)

    with open(f"{base_path}/truth.json", "w") as f:
        json.dump(world["truth"], f, indent=2)

    print(f"Generated world written to {base_path}/")
    print(f"  Members: {len(world['members'])}")
    print(f"  Claim lines: {len(world['claim_lines'])}")
    print(f"  Auth requests: {len(world['auth_requests'])}")
    print(f"  Ground truth: {base_path}/truth.json")

if __name__ == "__main__":
    world = generate_world()
    write_world(world, "generate")
