# HarnessGuard

**⚠️ AUTHORIZED USE ONLY.** HarnessGuard is a security testing tool for agent
harnesses you own or are explicitly authorized to test. It attempts to trigger
tools without a model turn. Do not point it at third-party systems without
written permission. Canaries are non-destructive by default; destructive
behavior is gated behind an explicit flag.

HarnessGuard tests whether an AI agent harness can have its tools triggered
*without the model ever running* — the **CoreBreak** vulnerability class
(patched by AWS, Google, and Vercel on 2026-08-06).

## The invariant

> For every tool execution, exactly one unconsumed, unexpired, model-issued
> authorization exists whose bound fields match the call.

A harness that dispatches a tool because a `tool_use`-shaped object is present in
the latest message — rather than because the *model* produced it — violates this
invariant. HarnessGuard forges that shape and observes whether the tool runs.

## Attack vectors

- **direct** — deliver a `tool_use` block in the position the event loop
  consumes, with no preceding model turn (AWS/Strands shape).
- **replay** — a forged approval / replayed authorization, or session-history
  injection on resume.
- **cross_session** — move a payload or auth token from one session/context into
  another (session-id swap, auth-token replay, process-path spoof).

## Install (source / monorepo — not published to any registry)

```bash
git clone https://github.com/ccrngd1/ProtoGensis.git
cd ProtoGensis/harness-guard
pip install -e ".[dev]"
```

## Usage

```bash
# Differential self-test: demo vulnerable harness must FAIL, hardened must PASS.
harness-guard scan --self-test

# Scan an MCP stdio server (primary adapter).
harness-guard scan --target "python my_mcp_server.py" --adapter mcp_stdio

# Pick vectors and output format.
harness-guard scan --target hardened --vectors direct,replay --output json
```

Exit codes: `0` PASS (hardened) · `1` FAIL (vulnerable) · `2` error/inconclusive.

## How it decides

Each vector is injected through an adapter (MCP stdio is primary; OpenAI
tool-calling and AgentCore shapes are also provided). HarnessGuard observes three
signals: **side effects** (canary tools record execution into a private temp
workspace — ground truth), **response type** (tool result vs. authorization
reject), and a **timing tell** (a result faster than any model turn). Any
executed tool or returned result for an unauthorized injected call is
`VULNERABLE`; a deliberate provenance reject is `HARDENED`.

## Hardening tiers

- **0** — no provenance check; any vector succeeds.
- **1** — untrusted history; direct blocked, replay/cross-session succeed.
- **2** — model-event-bound; all three blocked.
- **3** — EBTE-style semantic binding (reported if observed).

The bundled hardened harness demonstrates tier 2: it mints a one-time HMAC
authorization on each genuine model turn, bound to
`{session_id, turn_id, tool_name, args_hash, nonce, issued_at, expires_at}`,
signed with an **ephemeral** key (fresh per process, never stored, never logged),
and consumed on use.

## Safety

Canaries write only to temp paths. Outbound callbacks are loopback-only and
disabled unless `--allow-destructive` is passed. The test suite makes no live
network connections. See `BLOG.md` for background.

## License

MIT.
