import json

from click.testing import CliRunner

from harness_guard.cli import EXIT_ERROR, EXIT_FAIL, EXIT_PASS, cli


def _run(args):
    return CliRunner().invoke(cli, args)


def test_cli_help():
    result = _run(["--help"])
    assert result.exit_code == 0
    assert "scan" in result.output


def test_scan_help_lists_options():
    result = _run(["scan", "--help"])
    assert result.exit_code == 0
    for opt in ("--target", "--adapter", "--vectors", "--output", "--allow-destructive", "--self-test"):
        assert opt in result.output


def test_self_test_passes_differential():
    result = _run(["scan", "--self-test", "--output", "rich"])
    assert result.exit_code == EXIT_PASS
    assert "differential oracle satisfied" in result.output


def test_scan_vulnerable_target_exits_fail():
    result = _run(["scan", "--target", "vulnerable", "--output", "json"])
    assert result.exit_code == EXIT_FAIL
    payload = json.loads(result.output.strip().splitlines()[0] if False else
                         _first_json(result.output))
    assert payload["overall_verdict"] == "VULNERABLE"


def test_scan_hardened_target_exits_pass():
    result = _run(["scan", "--target", "hardened", "--output", "json"])
    assert result.exit_code == EXIT_PASS
    payload = json.loads(_first_json(result.output))
    assert payload["overall_verdict"] == "HARDENED"


def test_scan_json_output_is_valid_json():
    result = _run(["scan", "--target", "hardened", "--output", "json"])
    payload = json.loads(_first_json(result.output))
    assert set(["target", "adapter", "overall_verdict", "hardening_tier",
                "vectors", "remediation"]) <= set(payload)


def test_scan_missing_target_errors():
    result = _run(["scan", "--output", "json"])
    assert result.exit_code == EXIT_ERROR
    assert "required" in result.output


def test_scan_bad_vector_errors():
    result = _run(["scan", "--target", "hardened", "--vectors", "bogus"])
    assert result.exit_code == EXIT_ERROR


def test_scan_subset_of_vectors():
    result = _run(["scan", "--target", "hardened", "--vectors", "direct,replay",
                   "--output", "json"])
    payload = json.loads(_first_json(result.output))
    assert set(payload["vectors"]) == {"direct", "replay"}


def test_non_mcp_adapter_with_target_errors():
    result = _run(["scan", "--target", "hardened", "--adapter", "openai"])
    assert result.exit_code == EXIT_ERROR


def _first_json(output: str) -> str:
    """Extract the first top-level JSON object from mixed CLI output."""
    start = output.index("{")
    depth = 0
    for i, ch in enumerate(output[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return output[start:i + 1]
    raise ValueError("no complete JSON object found")
