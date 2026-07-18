# SetupTrap

**Static scanner + attack-surface mapper for AI coding-agent setup/config files.**

An attacker who can modify any file an AI coding agent reads at initialization
time — `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `SOUL.md`, `SKILL.md`,
`requirements.txt`, `Makefile`, `pyproject.toml` — can shape that agent's
behavior for a whole session, before any user-requested work runs. The agent
isn't broken; it's following orders the user never gave. SetupTrap scans those
files for the directives that do this.

```bash
git clone https://github.com/ccrngd1/ProtoGensis
cd ProtoGensis/setup-trap && pip install -e .
setup-trap scan .
```

> Not yet on PyPI — install from source (above). The baseline `scan` is **offline and credential-free**. CVE lookups
(`--check-cve`) and LLM behavioral simulation (`--simulate`) are optional add-ons
that degrade gracefully when their tooling/creds are absent.

---

## ⚠️ Provenance: what's proven vs. what's inferred (read this first)

SetupTrap covers two attack classes, and it is scrupulously honest about the
evidence behind each. **Every rule, report line, surface entry, and HTML/JSON
field carries a provenance tag.**

| Badge | Provenance | What it means |
|-------|-----------|----------------|
| 🟢 | **sourced** | The **package-install supply-chain** class — typosquatting, separator confusion, index/source redirection, hidden index, Makefile poisoning, CVE-pinning, error-message injection. Empirically evaluated by the paper **arXiv:2607.15143** ("Setup Complete, Now You Are Compromised"). |
| 🟡 | **synthesized** | The **behavior-hijacking** class — identity substitution, exfiltration directives, tool-binding command-wraps, memory-write hooks, conditional triggers. Grounded in prompt-injection literature and the "Rules File backdoor" work the paper cites as ref [7], but **NOT empirically evaluated by that paper.** |
| 🔵 | **inferred** | Reasonable deductions, e.g. an undocumented runtime file read-order. Used mostly in the attack-surface mapper. |

**The honesty gate is structural, not cosmetic:**

- A rule tagged `sourced` cannot load without a `source_ref` citing the paper
  (enforced in `Rule.__post_init__` and tested in `test_rules.py`).
- The only `sourced` behavior-hijacking rules are the ones whose *underlying
  mechanism* the paper proved (index/source redirection, CVE-pins); their
  `source_ref` notes that detecting them as a config-file directive is a
  synthesized framing.
- A `synthesized` rule that references the paper's class must say "not
  evaluated" in its `source_ref` — verified by
  `test_synthesized_rules_do_not_claim_paper_proof`.

Do not present a 🟡 finding as paper-proven. That is the one thing this project
refuses to do.

---

## What it detects

### 🟢 Package-install supply-chain (the paper's proven 7 checks)

Implemented programmatically in `scanner/preinstall.py`, each citing its paper
scenario reference:

| Check | ID | Ref |
|-------|----|----|
| Typosquat package name | `PRE-NAME` | R-name |
| Separator confusion (`azurecore` ↔ `azure-core`) | `PRE-SEP` | R-sep |
| Non-PyPI / localhost index redirection | `PRE-SRC` | R6a |
| Hidden index URL in `requirements.txt` | `PRE-HIDDEN` | R8 |
| Makefile poisoning (`install:` with custom source) | `PRE-MAKE` | R10 |
| CVE-pinned version (optional `pip-audit`) | `PRE-CVE` / `PRE-PIN` | V5 |
| Error-message injection ("on error, `pip install X`") | `PRE-ERRINJ` | V7 |

### 🟡 Behavior-hijacking (25 synthesized YAML rules, 5 categories)

| Category | IDs | Examples |
|----------|-----|----------|
| Identity | `IDENT-001..005` | "ignore previous instructions", "from now on you are", disable safety, DAN, conceal-from-user |
| Exfiltration | `EXFIL-001..005` | POST/upload to URL, telemetry beacon, credential collection, file-content exfiltration, curl/wget in config |
| Tool-binding | `TOOL-001..005` | custom index directive, separator-confusion name, localhost source, command prefix/suffix wrap, write-to-/tmp |
| Memory-hooks | `MEM-001..005` | post-task file write, session-summary write, **MEMORY.md write (Critical)**, credential capture, runtime requirements mutation |
| Conditional | `COND-001..005` | sensitive-keyword trigger, trust escalation, confirmation removal, **CVE version pin (🟢 sourced, V5)**, error-triggered install |

(`TOOL-001..003` and `COND-004` are 🟢 sourced; the other 21 are 🟡 synthesized.)

---

## CLI

```bash
setup-trap scan <path>                          # static scan, all rules
setup-trap scan <path> --category exfiltration --severity critical
setup-trap scan <path> --check-cve              # add OSV/pip-audit CVE lookup (optional)
setup-trap scan <path> --format cli|json|html --output report.html
setup-trap scan <path> --fail-on critical|warning   # CI exit-code gate

setup-trap surface --runtime claude_code|cursor|copilot|openclaw [--format cli|json]
setup-trap audit <path> --runtime openclaw      # self-audit convenience wrapper
setup-trap scan <path> --simulate               # LLM behavioral pass on flagged files
setup-trap simulate <path>                       # LLM behavioral pass only
```

**Exit codes:** `0` clean / below threshold, `1` when a finding at/above
`--fail-on` (default `critical`) exists. `2`/`3` for usage/environment errors.

---

## Attack-surface mapper

`setup-trap surface --runtime X` enumerates the files a runtime trusts at init
and the "attacker can write **THIS** → can do **THAT**" mapping, each entry
provenance-tagged (🟢 documented behavior vs 🔵 inferred). Covers **Claude Code,
Cursor, GitHub Copilot** (best-effort / inferred, per the paper's caution about
unverified paths), and **OpenClaw / CABAL** (grounded in the OpenClaw runtime
docs: `system-prompt.md`, `soul.md`, `hooks.md`).

```bash
setup-trap surface --runtime openclaw
```

---

## Writing your own rules

Rules are YAML under `setup_trap/scanner/rules/`. Adding one is a YAML edit — no
code change. Schema:

```yaml
rules:
  - id: EXFIL-006                 # unique
    name: My rule
    category: exfiltration        # identity|exfiltration|tool-binding|memory-hooks|conditional
    severity: critical            # critical|warning|info
    provenance: synthesized       # sourced|synthesized|inferred
    source_ref: "..."             # REQUIRED when provenance is sourced
    description: >
      What this catches and why.
    file_patterns: ["AGENTS.md", "*.md"]   # globs / exact names
    keywords: ["post", "upload"]  # fast pre-filter (regex only runs if a keyword hits)
    regex: >-
      \b(?:POST|upload)\b.*https?://\S+
    target: any                   # any|prose|code  (markdown code-block vs prose)
    context_lines: 2
    message: "Human-readable finding message."
    fix_guidance: "How to fix it."
    allowlist:                    # optional: suppress known-safe matches
      description: "docs endpoints"
      regexes: ["example\\.com"]
    tags: ["exfiltration"]
```

**Calibration / allowlists.** Beyond per-rule allowlists, a global calibration
layer (`scanner/calibration.py`) downgrades known-legit patterns to INFO with an
"attacker-could" note rather than silencing them: legit alternate package
indexes (PyTorch/NVIDIA), first-party service APIs (Trello/Notion/Slack/…),
secret-manager CLIs (`op`, keychain), localhost diagnostics, and directives
phrased as **prohibitions** ("Never print secrets"). This keeps the clean corpus
false-positive-free while still surfacing the surface.

---

## GitHub Action

Copy `github_action/setup-trap.yml` to `.github/workflows/`. It scans on PRs that
touch setup files, uploads a JSON+HTML report artifact, and fails the check on
any Critical finding. Baseline scan needs no secrets.

---

## LLM behavioral simulation (`--simulate`, optional)

`--simulate` asks a model (Amazon Bedrock / Claude) to describe what an agent
would do at startup given a file and rate each behavior BENIGN / SUSPICIOUS /
MALICIOUS. It is **advisory and non-deterministic** — it augments, never
overrides, static findings. No `boto3` / no AWS creds → cleanly disabled with a
message; the static scan still runs.

```bash
pip install -e ".[simulate]"       # from source (see Install)
export AWS_REGION=us-east-1        # + AWS credentials
setup-trap scan . --simulate
```

> **Honesty note:** the simulator ships the *capability*. Its accuracy against
> real LLMs has **not** been benchmarked. Do not infer detection rates from it.

---

## Install extras

```bash
git clone https://github.com/ccrngd1/ProtoGensis && cd ProtoGensis/setup-trap
pip install -e .              # core: PyYAML + rich + stdlib (offline)
pip install -e ".[cve]"       # + pip-audit for --check-cve
pip install -e ".[simulate]"  # + boto3 for --simulate
pip install -e ".[dev]"       # + pytest
```

Python 3.11+. MIT licensed.

---

## Approach, ambiguities & build notes

This section records how the MVP was scoped and two real access limitations hit
during the build (kept visible rather than papered over).

**Approach.** Deterministic static scan first (offline, CI-cheap, ~80% of the
value); optional LLM simulation as the opt-in "what would it do" layer. Rules are
data (YAML) so the library is community-extensible. Provenance is a first-class,
structurally-enforced field, not a comment.

**Ambiguities resolved during the build:**

- *Known-good package list* — bundled a curated top-N PyPI list
  (`scanner/data/popular_packages.txt`) and use edit-distance-1 for typosquat +
  PEP 503 separator-normalization for separator confusion. Not exhaustive by
  design; it is a heuristic anchor set.
- *CVE tool* — default `pip-audit` (Python-native, OSV) behind `--check-cve`;
  absent tool → `PRE-PIN` INFO ("not verified"), never a crash.
- *Simulation baseline* — the clean-config baseline is described inline in the
  prompt (no separate baseline file shipped for MVP).
- *Self-audit calibration* — legit items (alternate indexes, first-party APIs,
  secret-manager CLIs, prohibitions) register as INFO with an attacker-could
  note, not false Criticals (see Calibration above).

**Access limitations during this build (disclosed, not hidden):**

1. The upstream **research doc**
   (`~/.openclaw/shared/builder-pipeline/research/2026-07-17-setup-trap.md`) was
   **permission-denied** to the build user (no sudo). The build therefore
   followed the complete build brief (`.mastercontrol/brief.md`), which itself
   specifies the rule IDs, categories, the paper's 7 checks, surface
   requirements, and the simulation design.
2. CABAL's **live agent workspace**
   (`~/.openclaw/agents/mastercontrol/workspace/`) was also **permission-denied**.
   The self-audit was instead run against the **real, readable OpenClaw runtime
   install** at `/usr/lib/node_modules/openclaw/` — genuine `AGENTS.md`, `SOUL.md`
   conventions, and **65 real `SKILL.md` files**. The self-audit output in
   `demo/self-audit-openclaw.txt` and in `BLOG.md` is that genuine scan, not a
   mock.

**Benchmark honesty:** no real-LLM benchmark was run. Detection numbers in this
repo are fixture/regression results (every rule fires on its malicious fixture;
zero false positives on the clean corpus). Real-LLM simulation accuracy is **not
benchmarked**.
