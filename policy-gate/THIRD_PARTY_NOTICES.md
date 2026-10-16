# Third-party notices

## AEGIS scanners (vendored)

`policygate/vendor/aegis_scanners/` contains `SecretScanner`, `PIIDetector`,
and `extract_strings`, copied verbatim (stdlib `re` only) from CABAL's own
AEGIS firewall (W12):

- Source path: `/root/projects/protoGen/aegis-firewall/aegis/scanners/`
- protoGen commit: `dbf1aae837e69bfd27d0c1954ec9afb253dff993`
- Files: `secret_scanner.py`, `pii_detector.py`, `extract.py`

AEGIS is part of the same protoGen monorepo (MIT).

## NOMOS (method source, not code)

PolicyGate reimplements the compile/verify method described in **NOMOS**
(arXiv 2610.11030, Yu, Kim, Choi). The NOMOS implementation is proprietary and
unreleased; **no code from it exists or is used here**. NOMOS is credited as
the method source only.

## No other third-party code

The core is stdlib-only. The optional `[bedrock]` extra declares `boto3`
(Apache-2.0), which is imported lazily and only in
`policygate/extract/live_bedrock.py`; it is not installed by default and is
never exercised by tests or demos.
