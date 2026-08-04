# Golden master provenance

`expected_output.txt` is a **real golden master**: it is the verbatim stdout of
`claimcalc.cbl` compiled and executed with GnuCOBOL.

- Compiler: `cobc (GnuCOBOL) 3.1.2.0` (Debian bookworm `gnucobol3` 3.1.2-5+b1)
- Command: `cobc -x -Wall -I copy -o claimcalc claimcalc.cbl && ./claimcalc > golden/expected_output.txt`
- Generated: 2026-08-04, Linux x86_64
- Re-verified 2026-08-04 (resume build): fresh `cobc -x -Wall -I copy` compile
  + run reproduced this file byte-for-byte (diff clean)
- Regenerate with: `assets/samples/golden/regenerate.sh` (requires `cobc` on PATH)

Note: GnuCOBOL-verified is **not** the same as z/OS-verified. IBM Enterprise
COBOL can differ in edge cases (e.g. invalid data in packed fields, some
intermediate-result rules). Treat this fixture as authoritative for GnuCOBOL
semantics only.
