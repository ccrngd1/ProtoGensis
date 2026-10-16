# 2026-02-19 reconstruction — sources

**This is a RECONSTRUCTED fixture.** The original techwriter-researcher
transcript does not exist (that agent's session store is a 2-byte legacy file;
the main archive starts 2026-03-31). The event streams in `episodes.json` are
rebuilt from the four evidence sources below (research §6.1). In-episode
timestamps are approximate.

1. `~/.openclaw/workspace/mistakes/archive/2026-02-19-techwriter-cron-disable.md`
   — the mistake log.
2. `~/.openclaw/backups/memory-pre-mnemosyne-2026-03-31/main-memory/2026-02-19.md`
   — main's memory backup covering both episodes.
3. git `f84fecd8` (2026-02-19T16:38Z) — adds the SOUL.md "INFRASTRUCTURE RULES"
   and the MEMORY.md "DO NOT TOUCH" block naming the two protected jobs.
4. git `943e5e1d` (2026-02-20T01:01Z) — `cron/jobs.json` shows enabled→false and
   two new jobs; the MEMORY.md "DO NOT TOUCH" block is replaced by "PAUSED"
   listing six disabled IDs (both protected); SOUL.md is rewritten to the
   "MANDATORY, NO EXCEPTIONS" version.

**Redaction (AC #16, #20).** Job IDs keep their real 8-hex prefix with a
synthetic suffix of the form `<prefix>-0000-4000-8000-<12 hex>`. The Slack
channel ID is `C_REDACTED`. No message text beyond the spike's own synthetic
lines. `spike_feb19.py` and its `.out` are **not** copied into this repo
(they contain the real full IDs and channel ID).
