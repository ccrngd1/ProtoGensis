"""Contract tests for the cobalt-parser-v0 schema validator."""

import pytest

from cobalt.schema import SCHEMA_VERSION, SchemaError, validate, walk_items


def test_fixture_validates(fixture_doc):
    assert validate(fixture_doc) is fixture_doc
    assert fixture_doc["schema_version"] == SCHEMA_VERSION


def test_rejects_non_dict():
    with pytest.raises(SchemaError, match="must be an object"):
        validate([])


def test_rejects_missing_top_level_key(fixture_doc):
    del fixture_doc["perform_graph"]
    with pytest.raises(SchemaError, match="perform_graph"):
        validate(fixture_doc)


def test_rejects_wrong_schema_version(fixture_doc):
    fixture_doc["schema_version"] = "cobalt-parser-v99"
    with pytest.raises(SchemaError, match="schema_version mismatch"):
        validate(fixture_doc)


def test_rejects_unknown_parser(fixture_doc):
    fixture_doc["parser"] = "regex"
    with pytest.raises(SchemaError, match="unknown parser"):
        validate(fixture_doc)


def test_rejects_data_item_missing_keys(fixture_doc):
    del fixture_doc["data_items"][0]["picture"]
    with pytest.raises(SchemaError, match="missing keys"):
        validate(fixture_doc)


def test_rejects_nested_bad_item(fixture_doc):
    # Corrupt a grandchild to prove validation recurses.
    child = fixture_doc["data_items"][0]["children"][0]
    child["level"] = "05"
    with pytest.raises(SchemaError, match="level must be int"):
        validate(fixture_doc)


def test_walk_items_covers_nested_items(fixture_doc):
    names = [i["name"] for i in walk_items(fixture_doc)]
    # Top-level, nested, and copybook-sourced items all appear.
    assert "CLAIM-RECORD" in names          # 01 from CLAIMREC.cpy
    assert "CLM-BILLED-AMT" in names        # 05 child
    assert "BEN-COPAY" in names             # 10 grandchild from BENFTABL.cpy
    assert len(names) == len(set(id(i) for i in walk_items(fixture_doc)))
