# Live enforcement — design note

## NOT IMPLEMENTED: requires CC approval (Infrastructure Change Protocol)

v1 is offline only. This document summarizes the live-enforcement design from
research §5.5. **None of it is built.** Installing a plugin is a config change
plus a gateway restart, which is CC-decision territory (CC-D1).

## Design (phase 2, CC-gated)

- An OpenClaw plugin `before_tool_call` can return `block` with a `blockReason`
  (the clause text goes back to the agent so it can re-plan, as NOMOS does) or
  `requireApproval` (it pauses and asks the owner; `/approve` works).
- **Fail-closed by default** for gated vtools only: a timeout or a throw blocks
  the call. Do **not** fail-closed on a hook crash for everything.
- `api.registerTrustedToolPolicy(...)` runs before ordinary hooks.
- **Map PRECONDITION `cc_authorized` → `requireApproval`, not a hard block.**
  CC's approval then becomes a structured authorization record — exactly VAI's
  detection lever.
- For provenance, record `ctx.inputProvenance.kind` in `before_prompt_build`
  (keyed by `runId`); in `before_tool_call`, use `ctx.requester.senderIsOwner`.
  When `requester` is absent (cron/system runs), fail closed for gated actions.
- **Ship shadow mode first** (log verdicts, never block).

## Why it is gated

Under BASE-AGENTS, installing a plugin and restarting the gateway is an
Infrastructure Change. It needs CC approval (CC-D1). Until then, PolicyGate
only replays history offline and files ambiguity items locally.
