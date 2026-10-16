# Prior art (research §4)

PolicyGate does **not** claim to be a pioneer at compiling or auditing
AGENTS.md/CLAUDE.md rules. Several tools already exist. The table summarizes what each does; the point is
to be honest about where PolicyGate overlaps and where its niche is.

| Tool / paper | Policy source | Static verification | Principal provenance | Replay over transcripts | Live gate | Domain |
|---|---|---|---|---|---|---|
| agenthook | CLAUDE.md / AGENTS.md | — | — | — | Claude Code PreToolUse + git hooks | Coding hygiene |
| claude-enforce (archived) | CLAUDE.md | — | — | — | Generated hooks | Coding |
| abide (closest replayer) | CLAUDE.md / AGENTS.md | — | — | Yes (Claude Code JSONL) | hooks | Coding |
| claude-md-doctor | CLAUDE.md / AGENTS.md | Dead refs, drift | — | Backtests | — | Coding |
| ToolReplay | scope.json | — | — | Yes | — | Generic |
| ContextCov (arXiv 2603.00822) | AGENTS.md | Code synthesis | — | Catalogued violations | Shell shims | Coding conventions |
| Mondl et al. (arXiv 2606.26649) | prompts + MCP + policy | Cedar analyzer | Cedar principal model | Coverage replay | Cedar | Medical |
| AWS AgentCore NL2Cedar | NL statements | Cedar validation | Gateway identity | — | AgentCore Gateway | AWS tools |
| MS Agent Governance Toolkit | YAML / OPA / Cedar | — | Identity (SPIFFE/DID) | Audit log | govern() | Enterprise |
| Invariant Guardrails | trace DSL | — | — | Trace-native flow rules | Gateway | Generic |
| NOMOS (arXiv 2610.11030) | written policy | Yes (5 structural classes) | user vs tool vs agent | Yes (preflight firing rates) | Deterministic gate | Customer service |
| OpenClaw `openclaw policy` | policy.jsonc | Config attestation | — | — | No ("does not enforce tool calls") | OpenClaw config |
| AEGIS (W12, vendored here) | hand-written YAML | — | — | Signed audit chain | MCP proxy | Content scanning |
| ConfigLint (W25) | AGENTS.md | — | — | Ablation probes | — | Behavioural density |
| HarnessGuard (W32) | — | — | — | — | — | Dispatch reachability |

**Also credited** (research §12): Reason Less Verify More (2607.07405),
PolicyGuard (2606.29225), FORGE/PCAS (2602.16708), Zwerdling et al.
(2507.16459), AgentSpec (2503.18666), VAI (2610.18230), ActPlane (2606.25189),
Compositional Policy Violations (2609.18820).

**What is genuinely unclaimed (as of 2026-10-16; research §4), PolicyGate's
niche:** the *combination* of (a) operator-governance rules (autonomy, infra,
approvals, quiet hours, self-modification), (b) principal provenance in a
multi-agent system, (c) NOMOS-style static (structural) verification on a real
operator policy, (d) virtual tools over shell strings, (e) version-pinned
replay plus policy self-edit detection, and (f) an ambiguity queue instead of
silent coverage gaps. No published tool we found combines these.

## `openclaw policy`

`openclaw policy` already exists, but it is **config conformance**: it attests
that `policy.jsonc` is well-formed and matches configuration. Per
`docs/cli/policy.md` it **"does not enforce tool calls."** PolicyGate governs
the tool calls themselves, offline, by replaying transcripts.

## MXC

MXC 1.0.0 (GA 2026-10-07) is **OS-level resource containment** (files,
network) declared in versioned JSON. It is **complementary**: MXC decides what
an agent *can* touch; PolicyGate decides what it *may* do and on whose say-so.
