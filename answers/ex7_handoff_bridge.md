# Ex7 — Handoff bridge

## Your answer

I ran the bridge offline (`make ex7`, session `sess_86dab8dc4888`)
and against real Nebius (`make ex7-real`, session
`sess_4198f5144a74`, loop driven by Qwen3-Next-80B-A3B-Thinking /
Qwen3-32B, structured by the stdlib mock because I haven't added a
RASA_PRO_LICENSE yet). The scripted offline trajectory hits the
canonical happy-recovery path: round 1 proposes Haymarket Tap with
party=12, structured rejects with `party_too_large` (trace event 7
`session.state_changed { from: structured, to: loop, round: 1,
rejection_reason: "...party_too_large" }`), round 2 proposes Royal
Oak with party=6 and structured confirms (event 14, `structured →
complete`).

The real-Nebius run was more honest about how LLMs misbehave. The
round-1 planner produced 3 subgoals (vs the scripted 1), and the
executor called `handoff_to_structured` without a `venue_id` in the
data payload — `normalise_booking_payload` raised
`ValidationFailed: missing venue_id`, which the bridge surfaced as
a reverse handoff with `rejection_reason: "normalisation failed:
missing venue_id"`. Round 2 produced 2 subgoals, the executor
exercised `venue_search` and `list_files` to recover, and the
bridge eventually emitted `state_changed { from: executing, to:
complete }`. The framework caught the malformed handoff at the
validator boundary — exactly where Decision 6 (deterministic
enforcement at the structured half) is supposed to bite.

The IPC discipline is fail-closed in both runs: only one
`ipc/handoff_to_structured.json` ever visible. Before writing a
new forward handoff, the bridge moves any existing file into
`logs/handoffs/`. Inspecting `sess_86dab8dc4888/ipc/` after each
round confirmed this — never two handoffs in flight.

One Makefile bug surfaced: `make ex7-real` was advertised in
README/ASSIGNMENT but the target was missing AND the underlying
`run.py` was wired to FakeLLMClient regardless of `--real` (Issue
#5 only flagged the missing target). I fixed both — the target
now exists and `run.py` switches to `OpenAICompatibleClient` when
`--real`, with a mock-Rasa fallback when no `RASA_PRO_LICENSE`.

## Citations

- `sess_86dab8dc4888/logs/trace.jsonl` events 6, 7, 13, 14 — offline state transitions
- `sess_4198f5144a74/logs/trace.jsonl` — real-Nebius reverse handoff with normalisation failure
- `sess_86dab8dc4888/logs/tickets/tk_44908bc2/raw_output.json` — round-1 planner output
- `sess_86dab8dc4888/ipc/handoff_to_structured.json` — single-forward-handoff invariant
- `starter/handoff_bridge/bridge.py` — HandoffBridge.run, fail-closed IPC rotation
- `starter/handoff_bridge/run.py` — fixed `--real` to switch loop to OpenAI-compatible
- `Makefile` — added `ex7-real` target
