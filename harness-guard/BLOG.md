# CoreBreak: when a tool runs but the model never did

On 2026-08-06, AWS, Google, and Vercel shipped near-simultaneous patches to their
agent harnesses. The bugs were independent but shared a shape: a tool could be
dispatched from input that merely *looked* like a model's tool call, without any
proof that a model produced it. We call this class **CoreBreak**. HarnessGuard is
a small tool designed to test whether a harness is susceptible.

## The one-line invariant

Everything here reduces to a single property a correct harness must hold:

> For every tool execution, exactly one unconsumed, unexpired, model-issued
> authorization exists whose bound fields match the call.

Break any clause — *unconsumed* (replay), *unexpired* (stale token), *model-issued*
(forged provenance), *bound fields match* (arg/session confusion) — and you have a
CoreBreak. The vulnerable pattern in the wild was structural: harnesses decided to
run a tool because a `tool_use`-shaped block sat in the latest message. Shape was
mistaken for provenance.

## What HarnessGuard does

HarnessGuard forges that shape three ways and watches what happens:

1. **Direct dispatch** — a `tool_use` block placed exactly where the event loop
   reads it, with no preceding model turn. This mirrors the
   `_has_tool_use_in_latest_message` pattern.
2. **Replay / forged approval** — a fabricated approval or a replayed
   authorization object, and session-history injection on resume.
3. **Cross-session injection** — a payload or auth token lifted from one session
   and presented in another.

Injection goes through an adapter. The **MCP stdio** adapter is primary: it spawns
the target server, completes the `initialize` handshake, lists tools (to tier
their risk), then sends a `tools/call` with no model turn in front of it. OpenAI
tool-calling and Bedrock AgentCore `InvokeHarness` request shapes are also
provided.

To judge the outcome without trusting the harness's own words, HarnessGuard relies
on **canary tools** that record execution into a private temp workspace. That file
evidence is ground truth: if a sentinel file appears, the tool ran — full stop. A
timing tell (a result returned faster than any real model turn) and response
classification (tool result vs. an explicit authorization reject) corroborate.

## The fix, demonstrated

The bundled hardened harness shows tier-2 hardening. On a genuine model turn it
mints a one-time authorization bound to
`{session_id, turn_id, tool_name, args_hash, nonce, issued_at, expires_at}` and
signs it with an **ephemeral** HMAC key — fresh per process, never written to
disk, never logged. At dispatch it requires a matching, unexpired, unconsumed
authorization and consumes it on use. Because the key never leaves the process,
the direct vector (no auth), the replay vector (a signature the harness never
produced), and the cross-session vector (an auth bound to a different session) all
fail verification.

## What the test suite verifies

HarnessGuard is a new build; these are properties the test suite is designed to
check, not production results. The differential oracle runs all three vectors
against both demo harnesses and asserts the vulnerable one is reported
`VULNERABLE` while the hardened one is reported `HARDENED`. Payload construction,
adapter handshake and injection, canary side-effect detection, response and timing
classification, risk tiering, hardening-tier scoring, and the CLI exit codes are
each covered. No test makes a live outbound connection.

**Real-LLM behavior: not benchmarked.** The demos use deterministic canary tools
and a simulated model-turn path, so results speak to the harness's dispatch logic,
not to any language model's behavior. Measuring how a specific production harness
behaves requires running HarnessGuard against that harness.

## Using it

HarnessGuard is authorized-use-only and non-destructive by default. Point it at a
harness you own, start with `--self-test` to see the differential, then aim the
MCP stdio adapter at your own server. If a canary fires, a tool ran that no model
asked for — and that is the whole point.
