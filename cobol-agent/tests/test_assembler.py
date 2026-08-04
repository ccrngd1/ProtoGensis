"""Context-assembly tests, driven entirely by the canned parser JSON."""

from pathlib import Path

from cobalt import assembler

SAMPLE_CBL = (Path(__file__).resolve().parent.parent
              / "assets" / "samples" / "claimcalc.cbl")


def test_data_dictionary_decodes_comp3(fixture_doc):
    table = assembler.render_data_dictionary(fixture_doc)
    # Money fields must show BigDecimal with an explicit scale.
    assert "CLM-BILLED-AMT" in table
    line = next(l for l in table.splitlines() if "CLM-BILLED-AMT" in l)
    assert "S9(7)V99" in line
    assert "COMP-3" in line
    assert "BigDecimal(scale=2)" in line


def test_data_dictionary_flags_redefines_for_review(fixture_doc):
    table = assembler.render_data_dictionary(fixture_doc)
    line = next(l for l in table.splitlines() if "BENEFIT-TABLE " in l
                and "REDEFINES" in l)
    assert "review both layouts" in line


def test_data_dictionary_lists_88s(fixture_doc):
    table = assembler.render_data_dictionary(fixture_doc)
    line = next(l for l in table.splitlines() if "CLM-TYPE " in l)
    assert "CLM-TYPE-PHARMACY" in line


def test_perform_graph_tree_from_entry(fixture_doc):
    tree = assembler.render_perform_graph(fixture_doc)
    lines = tree.splitlines()
    assert lines[1] == "0000-MAIN"
    # Children indented under their caller.
    assert any(l.startswith("  1000-INIT") for l in lines)
    assert any(l.startswith("    2300-CALC-ALLOWED") for l in lines)
    # Every paragraph is reachable in this program.
    assert not any("not reached" in l for l in lines)


def test_semantics_notes_state_the_rules(fixture_doc):
    notes = assembler.render_semantics_notes(fixture_doc)
    assert "RoundingMode.DOWN" in notes
    assert "RoundingMode.HALF_UP" in notes
    assert "NEVER use double or float" in notes
    assert "scale=M" in notes
    # Program-specific REDEFINES get called out by name.
    assert "BENEFIT-TABLE REDEFINES BENEFIT-TABLE-INIT" in notes


def test_assemble_context_full(fixture_doc):
    ctx = assembler.assemble_context(fixture_doc, source_path=str(SAMPLE_CBL))
    assert "PROGRAM: CLAIMCALC" in ctx
    assert "CLAIMREC" in ctx and "BENFTABL" in ctx
    assert "=== DATA DICTIONARY" in ctx
    assert "=== SEMANTICS RULES ===" in ctx
    assert "=== FULL SOURCE ===" in ctx
    assert "2500-APPLY-COST-SHARE" in ctx  # source really included


def test_assemble_context_single_paragraph(fixture_doc):
    ctx = assembler.assemble_context(
        fixture_doc, source_path=str(SAMPLE_CBL), paragraph="2300-CALC-ALLOWED")
    assert "=== SOURCE (paragraph 2300-CALC-ALLOWED) ===" in ctx
    assert "CLM-ALLOWED-AMT = CLM-BILLED-AMT * 0.80" in ctx
    # Other paragraphs' bodies are trimmed out of the source section.
    assert "STOP RUN" not in ctx.split("=== SOURCE")[1]


def test_extract_paragraph_bounds():
    source = SAMPLE_CBL.read_text()
    para = assembler.extract_paragraph(source, "2600-DENY-CLAIM")
    assert para is not None
    assert "CLM-STATUS-DENIED" in para
    assert "7000-PRINT-CLAIM" not in para
    assert assembler.extract_paragraph(source, "NO-SUCH-PARA") is None
