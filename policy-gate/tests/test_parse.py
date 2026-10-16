"""PARSE tests: heading inheritance, fences, tables, hashes (AC #4)."""

from policygate import parse

QUALIFIED = """# Policy

## Operating Rules

### Forbidden Actions (without explicit CC instruction):
- Disabling, deleting, or modifying scheduled jobs
- Restarting or stopping services
- Changing gateway configuration
"""

FENCED = """# Doc

## Example

```
openclaw cron disable abc123
```

- A real clause outside the fence.
"""

TABLE = """# Doc

## Matrix

| rule | action |
|---|---|
| r1 | never delete jobs |
| r2 | always log actions |
"""


def test_heading_qualifier_inherited():
    clauses, _ = parse.parse_markdown(QUALIFIED, "f.md", "abc123")
    bullets = [c for c in clauses if c.src["heading"].startswith("Forbidden Actions")]
    assert len(bullets) == 3
    for c in bullets:
        assert "without explicit CC instruction" in c.inherited_qualifiers
        assert c.heading_chain == ["Policy", "Operating Rules",
                                   "Forbidden Actions (without explicit CC instruction):"]


def test_fenced_block_skipped_and_counted():
    clauses, fenced = parse.parse_markdown(FENCED, "f.md", "abc123")
    assert fenced == 1
    assert all("openclaw cron disable" not in c.text for c in clauses)
    assert any("real clause outside" in c.text for c in clauses)


def test_table_rows_one_clause_each():
    clauses, _ = parse.parse_markdown(TABLE, "f.md", "abc123")
    rows = [c for c in clauses if c.kind == "table_row"]
    # header row + 2 data rows (separator skipped)
    texts = [c.text for c in rows]
    assert "r1 | never delete jobs" in texts
    assert "r2 | always log actions" in texts
    assert not any(set(t) <= set("-|: ") for t in texts)


def test_rule_bearing_flag():
    clauses, _ = parse.parse_markdown(TABLE, "f.md", "abc123")
    by_text = {c.text: c for c in clauses}
    assert by_text["r1 | never delete jobs"].rule_bearing
    assert by_text["r2 | always log actions"].rule_bearing
    none_clause, _ = parse.parse_markdown("# T\n\nJust a plain note.\n", "f.md", "x")
    assert not none_clause[0].rule_bearing


def test_hashes_stable():
    a, _ = parse.parse_markdown(QUALIFIED, "f.md", "abc123")
    b, _ = parse.parse_markdown(QUALIFIED, "f.md", "abc123")
    assert [c.clause_sha256 for c in a] == [c.clause_sha256 for c in b]
    assert [c.section_hash for c in a] == [c.section_hash for c in b]


def test_normalization_strips_emphasis():
    c1, _ = parse.parse_markdown("# T\n\n- **Never** delete `jobs`.\n", "f.md", "x")
    c2, _ = parse.parse_markdown("# T\n\n- Never delete jobs.\n", "f.md", "x")
    assert c1[0].clause_sha256 == c2[0].clause_sha256


def test_clause_id_format():
    clauses, _ = parse.parse_markdown(QUALIFIED, "f.md", "abcdef0123456789")
    assert clauses[0].clause_id.startswith("f.md@abcdef01:")


def test_cron_payload_clauses():
    text = '{"jobs": [{"id": "aaaa1111-0000-4000-8000-000000000003", "agentId": "synthetic-agent", "payload": {"message": "Nightly digest. Do NOT execute queued items."}}]}'
    clauses = parse.parse_cron_payloads(text, "cron/jobs.json", "abc")
    assert len(clauses) == 1
    assert clauses[0].src["heading"] == "job:aaaa1111"
    assert clauses[0].rule_bearing
