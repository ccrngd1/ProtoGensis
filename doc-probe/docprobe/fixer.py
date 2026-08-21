"""Fix mode: turn flags into suggested edits.

Policy (per arXiv:2608.11095): for contradiction findings, prefer ATTACHING a
rationale comment to a directive over deleting it. An orphaned directive's fix
is a proposed rationale, not removal.
"""

from __future__ import annotations

from docprobe.models import FileResult, Fix


def fixes_for(result: FileResult) -> list[Fix]:
    fixes: list[Fix] = []
    for dim in result.dimensions:
        for flag in dim.flags:
            if dim.name == "contradiction":
                # Attach rationale rather than delete (arXiv:2608.11095).
                suggestion = flag.suggestion or (
                    "<!-- rationale: explain why this rule exists, or which rule "
                    "wins when they conflict -->"
                )
                fixes.append(
                    Fix(
                        path=result.path,
                        line=flag.line,
                        dimension=dim.name,
                        kind="attach_rationale",
                        original=flag.passage,
                        suggestion=suggestion,
                        why=flag.rationale,
                    )
                )
            elif dim.name == "specificity" and flag.passage:
                fixes.append(
                    Fix(
                        path=result.path,
                        line=flag.line,
                        dimension=dim.name,
                        kind="rewrite",
                        original=flag.passage,
                        suggestion=flag.suggestion or "Rewrite with a checkable criterion",
                        why=flag.rationale,
                    )
                )
            elif flag.suggestion:
                fixes.append(
                    Fix(
                        path=result.path,
                        line=flag.line,
                        dimension=dim.name,
                        kind="restructure",
                        original=flag.passage,
                        suggestion=flag.suggestion,
                        why=flag.rationale,
                    )
                )
    return fixes
