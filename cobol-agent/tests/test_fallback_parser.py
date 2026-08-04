"""Pure-Python fallback parser tests. No JVM anywhere near these.

Half the tests parse the bundled real sample (claimcalc.cbl + copybooks);
the rest use small inline sources written to tmp_path.
"""

from __future__ import annotations

import pytest

from pathlib import Path

from cobalt.parser.fallback import _decode_pic, parse_source
from cobalt.schema import validate, walk_items

SAMPLES = Path(__file__).resolve().parent.parent / "assets" / "samples"
SAMPLE_CBL = SAMPLES / "claimcalc.cbl"
SAMPLE_COPY = SAMPLES / "copy"


def _write_cobol(tmp_path, name, body):
    """Write fixed-format COBOL: 7 leading spaces puts code in area B."""
    path = tmp_path / name
    path.write_text("\n".join("       " + line for line in body) + "\n")
    return path


@pytest.fixture(scope="module")
def sample_doc():
    return validate(parse_source(str(SAMPLE_CBL), [str(SAMPLE_COPY)]))


class TestSampleParse:
    def test_program_id(self, sample_doc):
        assert sample_doc["program_id"] == "CLAIMCALC"
        assert sample_doc["parser"] == "fallback"

    def test_copybooks_resolved(self, sample_doc):
        names = {c["name"] for c in sample_doc["copybooks"]}
        assert names == {"CLAIMREC", "BENFTABL"}

    def test_copybook_items_inlined_with_source_attribution(self, sample_doc):
        items = {i["name"]: i for i in walk_items(sample_doc)
                 if i["name"] != "FILLER"}
        assert items["CLM-BILLED-AMT"]["source"] == "CLAIMREC.cpy"
        assert items["BEN-COPAY"]["source"] == "BENFTABL.cpy"
        assert items["WS-COINS-PCT"]["source"] == "claimcalc.cbl"

    def test_comp3_decoded(self, sample_doc):
        items = {i["name"]: i for i in walk_items(sample_doc)}
        billed = items["CLM-BILLED-AMT"]
        assert billed["picture"] == "S9(7)V99"
        assert billed["usage"] == "COMP-3"
        assert billed["signed"] is True
        assert billed["integer_digits"] == 7
        assert billed["fraction_digits"] == 2

    def test_88_levels_folded_into_parent(self, sample_doc):
        items = {i["name"]: i for i in walk_items(sample_doc)}
        conds = {c["name"]: c["values"] for c in items["CLM-TYPE"]["condition_names"]}
        assert conds["CLM-TYPE-PHARMACY"] == ['"RX"']
        status = {c["name"] for c in items["CLM-STATUS"]["condition_names"]}
        assert status == {"CLM-STATUS-OPEN", "CLM-STATUS-ADJUDICATED",
                          "CLM-STATUS-DENIED"}

    def test_occurs_and_redefines(self, sample_doc):
        items = {i["name"]: i for i in walk_items(sample_doc)}
        assert items["BENEFIT-ENTRY"]["occurs"] == {
            "times": 4, "indexed_by": "BEN-IDX"}
        assert items["BENEFIT-TABLE"]["redefines"] == "BENEFIT-TABLE-INIT"
        assert items["INPUT-CLAIM-TABLE"]["redefines"] == "INPUT-CLAIMS"

    def test_perform_graph_structure(self, sample_doc):
        g = sample_doc["perform_graph"]
        assert g["0000-MAIN"] == ["1000-INIT", "2000-PROCESS-ONE-CLAIM",
                                  "8000-PRINT-TOTALS", "9000-TERM"]
        assert "2300-CALC-ALLOWED" in g["2000-PROCESS-ONE-CLAIM"]
        # Leaf paragraphs perform nothing.
        assert g["2300-CALC-ALLOWED"] == []

    def test_all_thirteen_paragraphs_found(self, sample_doc):
        assert len(sample_doc["paragraphs"]) == 13
        assert sample_doc["paragraphs"][0]["name"] == "0000-MAIN"

    def test_no_diagnostics_on_clean_sample(self, sample_doc):
        assert sample_doc["diagnostics"] == []


class TestPicDecoding:
    @pytest.mark.parametrize("pic,expect", [
        ("S9(7)V99", dict(signed=True, integer_digits=7, fraction_digits=2)),
        ("9(5)V9(3)", dict(signed=False, integer_digits=5, fraction_digits=3)),
        ("SV99", dict(signed=True, integer_digits=0, fraction_digits=2)),
        ("9(8)", dict(signed=False, integer_digits=8, fraction_digits=0)),
        ("999V9", dict(signed=False, integer_digits=3, fraction_digits=1)),
    ])
    def test_numeric_pics(self, pic, expect):
        got = _decode_pic(pic)
        for k, v in expect.items():
            assert got[k] == v, f"{pic}: {k}"

    def test_alpha_pics(self):
        assert _decode_pic("X(10)")["alpha_length"] == 10
        assert _decode_pic("XXX")["alpha_length"] == 3
        assert _decode_pic("A(5)")["alpha_length"] == 5

    def test_edited_picture_flagged(self):
        got = _decode_pic("Z(6)9.99-")
        assert got["edited"] is True


class TestInlineSources:
    def test_missing_copybook_is_diagnostic_not_crash(self, tmp_path):
        src = _write_cobol(tmp_path, "p.cbl", [
            "IDENTIFICATION DIVISION.",
            "PROGRAM-ID. P.",
            "DATA DIVISION.",
            "WORKING-STORAGE SECTION.",
            "COPY NOSUCH.",
            "01  WS-A PIC X.",
            "PROCEDURE DIVISION.",
            "MAIN.",
            "    STOP RUN.",
        ])
        doc = validate(parse_source(str(src)))
        assert any("NOSUCH" in d for d in doc["diagnostics"])
        assert [i["name"] for i in doc["data_items"]] == ["WS-A"]

    def test_copybook_found_case_insensitively(self, tmp_path):
        cpy = tmp_path / "copy"
        cpy.mkdir()
        (cpy / "myrec.cpy").write_text("       01  MY-REC PIC X(4).\n")
        src = _write_cobol(tmp_path, "p.cbl", [
            "IDENTIFICATION DIVISION.",
            "PROGRAM-ID. P.",
            "DATA DIVISION.",
            "WORKING-STORAGE SECTION.",
            "COPY MYREC.",
            "PROCEDURE DIVISION.",
            "MAIN.",
            "    STOP RUN.",
        ])
        doc = validate(parse_source(str(src), [str(cpy)]))
        assert doc["copybooks"][0]["name"] == "MYREC"
        assert doc["data_items"][0]["name"] == "MY-REC"

    def test_comment_lines_ignored(self, tmp_path):
        path = tmp_path / "p.cbl"
        path.write_text(
            "      * A COMMENT WITH 01 FAKE-ITEM PIC X.\n"
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. P.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       01  REAL-ITEM PIC 9(3).\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN.\n"
            "           STOP RUN.\n"
        )
        doc = validate(parse_source(str(path)))
        names = [i["name"] for i in walk_items(doc)]
        assert names == ["REAL-ITEM"]

    def test_multiline_sentence_joined(self, tmp_path):
        src = _write_cobol(tmp_path, "p.cbl", [
            "IDENTIFICATION DIVISION.",
            "PROGRAM-ID. P.",
            "DATA DIVISION.",
            "WORKING-STORAGE SECTION.",
            "01  WS-AMT",
            "    PIC S9(5)V99",
            "    COMP-3.",
            "PROCEDURE DIVISION.",
            "MAIN.",
            "    STOP RUN.",
        ])
        doc = validate(parse_source(str(src)))
        item = doc["data_items"][0]
        assert item["name"] == "WS-AMT"
        assert item["picture"] == "S9(5)V99"
        assert item["usage"] == "COMP-3"

    def test_filler_items_allowed(self, tmp_path):
        src = _write_cobol(tmp_path, "p.cbl", [
            "IDENTIFICATION DIVISION.",
            "PROGRAM-ID. P.",
            "DATA DIVISION.",
            "WORKING-STORAGE SECTION.",
            "01  GRP.",
            "    05  FILLER PIC X(3) VALUE \"ABC\".",
            "    05  WS-B   PIC X.",
            "PROCEDURE DIVISION.",
            "MAIN.",
            "    STOP RUN.",
        ])
        doc = validate(parse_source(str(src)))
        kids = doc["data_items"][0]["children"]
        assert [k["name"] for k in kids] == ["FILLER", "WS-B"]
        assert kids[0]["value"] == '"ABC"'

    def test_perform_until_not_treated_as_target(self, tmp_path):
        src = _write_cobol(tmp_path, "p.cbl", [
            "IDENTIFICATION DIVISION.",
            "PROGRAM-ID. P.",
            "DATA DIVISION.",
            "WORKING-STORAGE SECTION.",
            "01  I PIC 9.",
            "PROCEDURE DIVISION.",
            "MAIN.",
            "    PERFORM WORK VARYING I FROM 1 BY 1 UNTIL I > 3",
            "    STOP RUN.",
            "WORK.",
            "    CONTINUE.",
        ])
        doc = validate(parse_source(str(src)))
        assert doc["perform_graph"]["MAIN"] == ["WORK"]
