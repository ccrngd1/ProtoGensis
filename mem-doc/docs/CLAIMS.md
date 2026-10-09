# Claims ledger (AC #16)

Every `<!-- claim:ID -->` marker in README.md / BLOG.md maps to a row here.
`memdoc claims verify` re-runs each command (from the repo root, venv active)
and checks the expected value appears in its output. Rows with kind `host_only`
depend on this host's `/root/.openclaw` git history; off-host they print
`SKIPPED (host-only)` and are not counted as passes or mismatches. External
numbers use `<!-- cite:... -->` markers instead and are not in this ledger.

| id | kind | command | expected | note |
|---|---|---|---|---|
| `breakeven-short` | offline | `memdoc demo costmodel --format json \| /usr/bin/jq -r .breakeven.short` | `4000` | research §5.2 break-even, short session |
| `breakeven-medium` | offline | `memdoc demo costmodel --format json \| /usr/bin/jq -r .breakeven.medium` | `6000` | research §5.2 break-even, medium session |
| `breakeven-long` | offline | `memdoc demo costmodel --format json \| /usr/bin/jq -r .breakeven.long` | `9000` | research §5.2 break-even, long session |
| `cache-head-ratio` | offline | `memdoc demo cache --format json \| /usr/bin/jq -r '(.totals.head.cacheWrite * 10 / .totals.tail.cacheWrite) \| floor \| . / 10'` | `6.9` | head vs tail cacheWrite ratio, simulated 150-call session; baseline A4 tail-inject |
| `decay-commits` | host_only | `memdoc decay --repo /root/.openclaw --file workspace/MEMORY.md --until 2026-10-08 --format json \| /usr/bin/jq -r .commits` | `156` | MEMORY.md commit count on this host |
| `decay-churn` | host_only | `memdoc decay --repo /root/.openclaw --file workspace/MEMORY.md --until 2026-10-08 --format json \| /usr/bin/jq -r .churn_ratio` | `10.8` | distinct-ever vs current lines |
| `decay-90d` | host_only | `memdoc decay --repo /root/.openclaw --file workspace/MEMORY.md --until 2026-10-08 --format json \| /usr/bin/jq -r '.survival_median."90".median'` | `0.62` | median 90-day exact-line survival |
| `decay-lines` | host_only | `memdoc decay --repo /root/.openclaw --file workspace/MEMORY.md --until 2026-10-08 --format json \| /usr/bin/jq -r '"\(.distinct_lines_ever) vs \(.current_content_lines)"'` | `1973 vs 182` | distinct lines ever vs current |

Notes:

- Commands assume the venv is active (`source .venv/bin/activate`) so `memdoc`
  resolves; `claims verify` runs them through `bash -c` from the repo root.
- The pipe characters inside commands are escaped as `\|` for the Markdown
  table; the verifier unescapes backtick spans, not table cells, so commands are
  read from the backtick span verbatim (with `\|` restored to `|`).
