# Judge validation (AC #8)

**State: pending live run.**

The LLM judge is allowed only for compliance-style probes (e.g. "prose, not
bullets"). Offline, the judge is the deterministic rule checker in
`memdoc/scorer.py` (`COMPLIANCE_RULES`); no LLM judge runs in mock mode, so
there is nothing to validate yet.

Before any live hypothesis evaluation that uses the judge, agreement must be
validated by hand on **>= 5 storylines** and recorded here.

## Template (fill after the first live run)

| storyline | probe | judge model (pinned ID) | judge verdict | hand verdict | agree? |
|---|---|---|---|---|---|
| c1s0 | p3 | _pending live run_ | | | |
| c1s1 | p3 | _pending live run_ | | | |
| c1s2 | p3 | _pending live run_ | | | |
| c1s3 | p3 | _pending live run_ | | | |
| c1s4 | p3 | _pending live run_ | | | |

- Judge rubric: fixed, versioned alongside this file when the live judge lands.
- Disagreements: list each one with the transcript excerpt and the resolution.
- Agreement threshold before the judge's scores are used: record the measured
  agreement rate here; if below 0.9, the probes are scored by hand instead.
