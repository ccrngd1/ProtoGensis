# I Built a Tool to Attack My Own AI Agent's Brain — And Found Real Vulnerabilities

Your AI coding agent reads a stack of files before it does a single thing you
asked. `AGENTS.md`. `CLAUDE.md`. `.cursorrules`. `SOUL.md`. Every `SKILL.md` it
loads. `requirements.txt`, the `Makefile`, `pyproject.toml`. Whoever can write to
any of those files gets to shape how the agent behaves for the entire session —
*before* your first prompt. The agent isn't hacked. It's just following orders.
They're not your orders.

There's a name for the package-install half of this: a July 2026 paper from
Microsoft, [*"Setup Complete, Now You Are Compromised: Weaponizing Setup
Instructions Against AI Coding Agents"*](https://arxiv.org/abs/2607.15143)
(arXiv:2607.15143). It shows that setup docs can smuggle typosquatted packages,
redirected install indexes, poisoned Makefiles and CVE-pinned dependencies past
an agent — and, crucially, that **whether the attack lands depends on the agent
harness, not on how smart the model is.** There is no pre-install
authenticity check. They call it the "install gap."

So I built **SetupTrap** — a scanner that reads the same files my agent reads and
flags the directives that could hijack it. Then I pointed it at my own agent's
brain. This post is about what it is, how it works, and the honesty rule I
refused to break while building it.

---

## Two attack classes — and I will not pretend they're equally proven

This is the most important section, so it goes first.

SetupTrap covers **two** classes of setup-file attack, and it is meticulous about
which one has evidence behind it:

- 🟢 **SOURCED — package-install supply-chain.** Typosquatting, separator
  confusion (`azurecore` vs `azure-core`), index/source redirection
  (`--extra-index-url` to a host you don't control), hidden index URLs, Makefile
  poisoning, CVE-pinned versions, error-message injection. This is exactly what
  arXiv:2607.15143 empirically evaluated. When SetupTrap flags one of these, it
  cites the paper's scenario reference (R6a, R8, R10, V5, V7…).

- 🟡 **SYNTHESIZED — behavior hijacking.** Identity substitution ("from now on
  you are…"), exfiltration directives, tool-binding command-wraps, memory-write
  hooks, conditional triggers. This class is *grounded in* prompt-injection
  literature and the "Rules File backdoor" work the paper cites as reference
  [7] — but **the paper did not test it.** I built these rules because the
  threat is real and obvious once you see the surface. That does **not** make
  them paper-proven, and SetupTrap never says they are.

Every rule, every line of every report, every attack-surface entry, and every
field of the JSON/HTML output carries a provenance badge: 🟢 sourced, 🟡
synthesized, or 🔵 inferred. The gate is enforced in code, not by good
intentions — a rule tagged `sourced` literally cannot load without a citation to
the paper, and the test suite asserts that a synthesized rule which references
the paper's class must spell out "not evaluated." If you take one thing from
this post: **a tool that mixes proven and inferred findings without labeling
them is lying to you.** I would rather ship a smaller honest claim.

---

## How it works

The core is a deterministic static scanner. Rules live in YAML, so the library
is extensible without touching Python:

```yaml
- id: IDENT-002
  name: Identity substitution ("you are no longer / from now on you are")
  category: identity
  severity: critical
  provenance: synthesized
  source_ref: "prompt-injection literature (not evaluated by arXiv:2607.15143)"
  file_patterns: ["*.md", ".cursorrules", "AGENTS.md", "CLAUDE.md"]
  keywords: ["you are", "from now on", "no longer", "act as"]
  regex: >-
    \b(?:from now on,?\s+you\s+are|you\s+are\s+(?:no\s+longer|now\s+a\b)|...)\b
  message: >
    Setup file reassigns the agent's identity/role — session-wide persona hijack.
  fix_guidance: >
    Remove identity reassignment. Provide project role context descriptively.
```

The pipeline per file: resolve → match file patterns → keyword pre-filter (fast)
→ regex → allowlist/calibration → build a finding with context lines and
provenance → sort by severity. The paper's 7 package-install checks are
programmatic (they need parsed package lists, index refs, and Makefile targets,
not just a regex), but they produce the same finding shape and carry the same
provenance discipline.

The scanner design is:

- **Offline and credential-free** for the baseline scan. Core dependencies are
  PyYAML, `rich`, and the standard library. Nothing on the scan path imports a
  cloud SDK.
- **CVE lookups optional** — `--check-cve` shells out to `pip-audit` (OSV) if
  it's installed; if not, a pinned version is reported as INFO ("not verified"),
  never a crash.
- **LLM simulation optional** — `--simulate` asks a model to narrate what an
  agent would do at startup and rate each behavior BENIGN/SUSPICIOUS/MALICIOUS.
  No credentials → cleanly disabled, static scan still runs.

It also maps the **attack surface** per runtime — Claude Code, Cursor, GitHub
Copilot (best-effort, inferred paths clearly marked), and OpenClaw/CABAL — as an
"attacker can write **THIS** → can do **THAT**" table, so you can reason about
the surface even when every current file is clean.

---

## The money moment: I scanned my own agent

My agent runs on OpenClaw. So I ran SetupTrap against the real OpenClaw runtime
on this machine — the genuine `AGENTS.md` conventions, the `SOUL.md` personality
layer, and **65 real `SKILL.md` files** that the agent loads on demand.

> **A note on scope.** I intended to scan CABAL's live agent workspace directly,
> but that directory was permission-locked to my build user (no sudo), as was the
> upstream research doc. Rather than fake it, I scanned the real, readable
> OpenClaw install at `/usr/lib/node_modules/openclaw/`. Everything below is
> genuine scanner output over 65 real skill files — not a mock, not a fixture.

Here's the real summary:

```
────────────────────────── SetupTrap scan ──────────────────────────
path: /usr/lib/node_modules/openclaw/skills
files scanned: 65    rules: 25

        Summary                    Provenance
┏━━━━━━━━━━━━━┳━━━━━━━┓    ┏━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Severity    ┃ Count ┃    ┃ Provenance     ┃ Count ┃
┡━━━━━━━━━━━━━╇━━━━━━━┩    ┡━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ 🔴 Critical │     0 │    │ 🟢 sourced     │     0 │
│ 🟡 Warning  │     6 │    │ 🟡 synthesized │    27 │
│ 🔵 Info     │    21 │    │ 🔵 inferred    │     0 │
│ Total       │    27 │    └────────────────┴───────┘
└─────────────┴───────┘
```

Zero criticals. That's the honest headline, and it's a *good* headline: this is a
mature, well-built agent runtime. But 27 findings across 8 skills is exactly the
point — it's a map of where the trust is.

**What the INFO findings show (the surface).** The `1password` skill really runs
`op read op://app-prod/db/password`. The `trello` skill really does
`POST https://api.trello.com/1/cards?key=$TRELLO_API_KEY&token=$TRELLO_TOKEN`.
The `notion` skill curls `api.notion.com`. These are all **legitimate** — a
secret manager reading a secret, a Trello skill talking to Trello. SetupTrap
calibrates them down to INFO and attaches an attacker-could note rather than
crying wolf:

```
[EXFIL-003] Credential / secret collection directive        🟡 synthesized
  file: .../skills/1password/SKILL.md
  match: 'read op://app-prod/db/password'
  note: Secret-manager/keychain CLI access (e.g. 1Password `op`) — reading a
        secret is the manager's job. Attacker-could: a tampered skill could point
        the same CLI at a different item and forward it.
```

That note *is* the value. Today it's benign. But it tells me precisely which
files, if an attacker could write to them, become a credential-exfiltration
primitive with zero new tooling.

**What the WARNING findings show (a genuine dual-use flag).** Six warnings, all
from one skill: `weather` curls `https://wttr.in/...`. That's a real external
host embedded in a skill body. It's almost certainly fine — wttr.in is a
well-known weather service — but "a skill reaches out to a third-party host you
might not have noticed" is precisely the kind of thing worth a human glance. The
tool did its job.

**What SetupTrap got wrong — and why that's in the tool now.** My first run
flagged `healthcheck/SKILL.md` for "print secrets" and `xurl/SKILL.md` for "Never
ask" as criticals. Both are *prohibitions*: the actual lines are
`- Never print secrets.` and `- Never ask user to paste tokens into chat.` —
safety instructions, the opposite of an attack. Regex can't read intent. So I
added a negation guard: when a matched directive's line leads with
"Never"/"Do not"/"Avoid", it's downgraded to INFO with a note saying exactly why.
Finding my own false positives on real files, and building the fix into the
tool, is the whole reason you run a scanner against real data instead of only
fixtures.

---

## Does it catch the actual attacks?

On planted malicious fixtures — yes, and that's what the test suite verifies.
Here's SetupTrap on a deliberately hostile `AGENTS.md`:

```
🔴 Critical
  [IDENT-001] Instruction override ("ignore previous instructions")   🟡 synthesized
  [IDENT-002] Identity substitution ("from now on you are")           🟡 synthesized
  [IDENT-003] Safety / guardrail disable directive                    🟡 synthesized
  [TOOL-003] Directive to install from localhost / private network    🟢 sourced (R6a)
  [MEM-003] MEMORY.md / external memory write attempt                 🟡 synthesized
```

And on a poisoned `requirements.txt` — the paper's proven class:

```
  [PRE-NAME]   Typosquat package name 'torchh' (one edit from 'torch')  🟢 sourced (R-name)
  [PRE-SEP]    Separator-confusion name 'azurecore' ↔ 'azure-core'      🟢 sourced (R-sep)
  [PRE-SRC]    Non-PyPI install source http://10.0.0.5:8080/simple      🟢 sourced (R6a)
  [PRE-HIDDEN] Hidden index URL in requirements.txt                     🟢 sourced (R8)
```

Meanwhile the legitimate PyTorch CUDA index —
`--extra-index-url https://download.pytorch.org/whl/cu121` — is recognized and
reported as INFO, not Critical. No false-positive spam on clean configs is a
hard requirement, not a nice-to-have.

---

## What the test suite validates (and what it doesn't)

SetupTrap is a **new build, not a deployed product.** I'm not going to invent
usage metrics or production timelines. Here's what is actually true, today:

- **116 tests pass.** Every one of the 25 behavior rules fires on its malicious
  fixture; the clean corpus produces **zero** Critical or Warning findings.
- The paper's 7 package-install checks each fire on a malicious fixture and cite
  their scenario reference; the clean `requirements.txt` (with a real PyTorch
  index) stays clean.
- The provenance honesty gate is enforced by tests: sourced rules must cite the
  paper; synthesized rules that mention the paper's class must say "not
  evaluated."
- The GitHub Action passes on a clean repo and fails on a repo with a planted
  Critical.
- The self-audit above is real output over 65 real skill files.

**What is *not* benchmarked:** real-LLM behavior. The `--simulate` layer ships
the *capability* to ask a model "what would this config make an agent do," but I
have not run a real-LLM benchmark, so I have no honest detection-rate number for
it. **Real-LLM performance is unknown without empirical measurement**, and I'm
not going to fabricate one. Static-scan effectiveness is measured the honest way
it can be right now: fixtures and regression, not extrapolation.

---

## Why this matters

The paper's deepest finding is that the *harness* decides whether a setup-file
attack lands — the model's capability barely moves the needle. That reframes the
defense: you don't need a smarter model, you need a **deterministic pre-scan** of
the files the agent trusts, run in CI before the agent ever reads them.
SetupTrap is that pre-scan, plus an honest extension into the behavior-hijacking
surface no scanner currently covers.

And the self-audit taught me the thing I couldn't have learned from fixtures:
even a clean, mature agent has a large, legitimate trust surface — secret-manager
calls, service-API POSTs, external fetches — and *every one of those is a place
an attacker wants to write.* The findings aren't bugs today. They're a map of
tomorrow's blast radius.

```bash
pip install setup-trap
setup-trap scan .
setup-trap audit ~/my-agent-workspace --runtime openclaw
```

Scan your own agent's brain. You might find it's clean. You'll definitely find
out how much it trusts.

---

*SetupTrap is MIT-licensed. The 🟢 sourced package-install class is grounded in
arXiv:2607.15143; the 🟡 synthesized behavior-hijacking class is my own extension,
grounded in prompt-injection literature but not empirically evaluated by that
paper. Provenance tags are on every finding so you always know which is which.*
