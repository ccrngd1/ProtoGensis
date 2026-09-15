#!/usr/bin/env python3
"""
P4: Verification layer.
Diff governed answer vs generate/truth.json.
Must be == 0 for reproducible verification.
"""
import json
import re
from typing import Dict, Any


def extract_structured_answer(text: str) -> Dict[str, Any]:
    """
    Extract key facts from LLM answer text.
    Returns structured dict matching truth.json schema.
    """
    answer = {}

    # Extract denial rate percentage
    rate_match = re.search(r"(?:denial rate|rate).*?(\d+\.?\d*)%", text, re.IGNORECASE)
    if rate_match:
        answer["rate_pct"] = float(rate_match.group(1))

    # Extract CARC-197 dominance
    carc_match = re.search(r"CARC[- ]?197.*?(\d+\.?\d*)%", text, re.IGNORECASE)
    if carc_match:
        answer["carc_197_dominance_pct"] = float(carc_match.group(1))

    # Extract dollar amount (look for the largest one, likely the at-risk amount)
    dollar_matches = re.findall(r"\$?([\d,]+\.?\d+)", text)
    if dollar_matches:
        # Convert to floats and pick the largest
        dollars = [float(d.replace(",", "")) for d in dollar_matches if d.replace(",", "")]
        if dollars:
            answer["at_risk_allowed_dollars"] = max(dollars)

    # Check for HS-14 mention
    if "HS-14" in text or "Health System 14" in text:
        answer["mentions_hs14"] = True

    # Check for notification gap (gap, omit, missing, cohort)
    if ("notification" in text.lower() and ("gap" in text.lower() or "omit" in text.lower() or "missing" in text.lower())) or \
       ("cohort" in text.lower() and "omit" in text.lower()):
        answer["identifies_notification_gap"] = True

    # Check for policy citations
    if "UM-RAD-2026" in text or "MP-RAD-114" in text:
        answer["cites_policy"] = True

    return answer


def verify_governed_answer(governed_result: Dict[str, Any], truth_path: str = "generate/truth.json") -> Dict[str, Any]:
    """
    Verify governed agent answer against ground truth.
    Returns diff report.
    """
    with open(truth_path) as f:
        truth = json.load(f)

    truth_answer = truth["governed_answer"]
    governed_text = governed_result.get("answer", "")

    # Extract structured facts from LLM text
    extracted = extract_structured_answer(governed_text)

    # Compare key facts
    diffs = []

    # Rate
    if "rate_pct" in extracted:
        expected = truth_answer["rate_pct"]
        actual = extracted["rate_pct"]
        if abs(actual - expected) > 1.0:  # Allow 1% tolerance
            diffs.append(f"rate_pct: expected {expected}%, got {actual}%")

    # CARC-197 dominance
    if "carc_197_dominance_pct" in extracted:
        expected = truth_answer["carc_197_dominance_pct"]
        actual = extracted["carc_197_dominance_pct"]
        if abs(actual - expected) > 5.0:  # Allow 5% tolerance
            diffs.append(f"carc_197_dominance_pct: expected {expected}%, got {actual}%")

    # At-risk dollars
    if "at_risk_allowed_dollars" in extracted:
        expected = truth_answer["at_risk_allowed_dollars"]
        actual = extracted["at_risk_allowed_dollars"]
        if abs(actual - expected) > expected * 0.05:  # 5% tolerance
            diffs.append(f"at_risk_allowed_dollars: expected ${expected:,.2f}, got ${actual:,.2f}")

    # Check critical facts
    if not extracted.get("mentions_hs14"):
        diffs.append("Missing mention of HS-14")

    if not extracted.get("identifies_notification_gap"):
        diffs.append("Missing identification of notification gap")

    if not extracted.get("cites_policy"):
        diffs.append("Missing policy citations (UM-RAD-2026, MP-RAD-114)")

    # Diff count
    diff_count = len(diffs)

    return {
        "diff_count": diff_count,
        "diffs": diffs,
        "extracted": extracted,
        "truth": truth_answer,
        "passed": diff_count == 0
    }


def verify_ungoverned_variance(ungoverned_runs: list) -> Dict[str, Any]:
    """
    Verify ungoverned agent shows honest variance (N>=20 runs).
    MUST fail honestly - never rigged.
    """
    if len(ungoverned_runs) < 20:
        return {
            "error": f"Need at least 20 ungoverned runs, got {len(ungoverned_runs)}",
            "passed": False
        }

    # Extract rates from each run
    rates = []
    for run in ungoverned_runs:
        if "error" in run:
            continue  # Honest failures are OK
        text = run.get("answer", "")
        match = re.search(r"(\d+\.?\d*)%", text)
        if match:
            rates.append(float(match.group(1)))

    if len(rates) < 15:  # At least 15 successful runs
        return {
            "error": f"Only {len(rates)} successful runs out of {len(ungoverned_runs)}",
            "passed": False
        }

    # Calculate variance
    import statistics
    mean_rate = statistics.mean(rates)
    stdev_rate = statistics.stdev(rates) if len(rates) > 1 else 0.0

    # Honest variance check: stdev should be non-zero (not rigged)
    is_varied = stdev_rate > 0.5  # At least 0.5% stdev

    return {
        "n_runs": len(ungoverned_runs),
        "n_successful": len(rates),
        "mean_rate": round(mean_rate, 1),
        "stdev_rate": round(stdev_rate, 1),
        "is_varied": is_varied,
        "passed": is_varied,
        "rates_sample": rates[:10]  # First 10 for inspection
    }


if __name__ == "__main__":
    # Test verification
    print("Verification Layer Test")
    print("=" * 80)

    # Mock governed result
    mock_governed = {
        "answer": """The outpatient imaging denial rate in Ohio is 12.9%.
        CARC-197 accounts for 61.6% of all denials. The at-risk allowed amount is $354,110.56.
        Root cause: Health System 14 (HS-14) was omitted from notification cohort NC-2026-03
        for the UM-RAD-2026 policy, which requires 120-day prior auth notice per MP-RAD-114 §4.2."""
    }

    result = verify_governed_answer(mock_governed)
    print(f"Diff count: {result['diff_count']}")
    print(f"Passed: {result['passed']}")
    if result['diffs']:
        print("Diffs:")
        for diff in result['diffs']:
            print(f"  - {diff}")

    print("\n✅ Verification layer ready")
