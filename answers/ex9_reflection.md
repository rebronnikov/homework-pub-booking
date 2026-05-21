# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

I ran Ex7 twice: once offline (`sess_86dab8dc4888`) and once
against real Nebius (`sess_4198f5144a74`). The finding:
the planner did NOT decide handoffs in either run. In the offline
run both planner tickets `tk_44908bc2/raw_output.json` round 1
(`"description": "find venue near haymarket for 12",
"assigned_half": "loop"`) and `tk_3fcfed8a/raw_output.json` round
2 (`"description": "retry with larger venue after rejection",
"assigned_half": "loop"`) assigned every subgoal to the loop
half. The handoff to structured was triggered by the EXECUTOR,
expressed as a `handoff_to_structured` tool call in
`logs/trace.jsonl` event 5 with `arguments.reason = "loop half
identified a candidate venue; passing to structured half for
confirmation under policy rules"`.

The real-Nebius run produced 3 subgoals in round 1 (vs the scripted
1) and the executor's first move was a `handoff_to_structured`
call with an incomplete payload `data` was missing `venue_id`,
which the validator rejected. The bridge surfaced this as
`session.state_changed { from: structured, to: loop, round: 1,
rejection_reason: "normalisation failed: missing venue_id" }`.
Round 2 then recovered via further loop work.

Another important observation: the planner outputs are advisory
metadata about WORK ITEMS; the executor decides WHICH HALF should
run them, expressed as tool calls. The handoff signal is the
`reason` argument on `handoff_to_structured`, not a planner
`assigned_half` field. After the structured half rejects, the
bridge writes a reverse task ("The structured half rejected the
previous proposal..."), and the new loop iteration's planner
might produce different subgoals, but they're still
`assigned_half: "loop"`. In a real-LLM environment the planner
MIGHT choose to assign to "structured" — that path would be a
different signal. 

### Citation

- `sess_86dab8dc4888/logs/tickets/tk_44908bc2/raw_output.json` — offline round-1 planner subgoal (`assigned_half: "loop"`)
- `sess_86dab8dc4888/logs/tickets/tk_3fcfed8a/raw_output.json` — offline round-2 planner subgoal (`assigned_half: "loop"`)
- `sess_86dab8dc4888/logs/trace.jsonl` event 5 — `handoff_to_structured` tool call carrying the reason
- `sess_4198f5144a74/logs/trace.jsonl` — real-Nebius reverse handoff after validator rejected an incomplete payload

---

## Q2 — Dataflow integrity catch

### Your answer

the original implementation in `starter/edinburgh_research/integrity.py`
self-verified its own flyer. The bug — Issue #14 on the repo —
was that `fact_appears_in_log` scanned BOTH `output` AND
`arguments` of every `ToolCallRecord`, INCLUDING `generate_flyer`'s
own record whose arguments contain the flyer's claimed facts. So
if the LLM hallucinated `total_gbp=9999` straight into
`generate_flyer({event_details: {total_gbp: 9999}})`, the value
appeared in `_TOOL_CALL_LOG` (as an argument of the flyer call
itself) and the check happily marked it verified.

I reproduced this. With `_TOOL_CALL_LOG` containing
`calculate_cost(output={"total_gbp": 556, ...})` AND
`generate_flyer(arguments={"event_details": {"total_gbp": 9999}}, ...)`,
the OLD scan returned True for £9999. After my fix —
`verify_dataflow` rebuilds the audit log by (1) excluding any
`tool_name == "generate_flyer"` records and (2) projecting each
remaining record to `output`-only — the same input now correctly
returns `ok=False` with `unverified_facts=['£9999']`.

The real-Nebius run in `sess_80aeea2f1519` exercised the related
question: Qwen made five `venue_search` calls (the spiral pattern
documented in `docs/real-mode-failures.md`); my tool-level guard
short-circuits after >3 calls and replays prior results with a
STOP message. Without that guard the model frequently runs out of
context before ever calling `generate_flyer`. The dataflow check
and the spiral guard are complementary: one catches hallucinated
NUMBERS, the other prevents the agent from never producing
numbers at all. Together they make the offline-and-real story
internally consistent: if `make ex5` exits 0, the flyer's £556
came from `calculate_cost`'s output and not from the LLM's
imagination. 

### Citation

- `starter/edinburgh_research/integrity.py:117-156` — fixed `verify_dataflow` with Issue #14 reference
- `sess_20c6735994dd/workspace/flyer.html` — offline legitimate flyer (£556 verified)
- `sess_80aeea2f1519/logs/trace.jsonl` — real Qwen run, 5 venue_search calls + spiral guard activated
- GitHub Issue #14 on `sovereignagents/homework-pub-booking`

---

## Q3 — First production failure + the one primitive that surfaces it

### Your answer

Shipping this agent to a real pub-booking business next week, the
first failure I would expect — well before any LLM weirdness — is
a **concurrent-write race on the IPC handoff file**: two bridge
rounds for the same session attempt to write
`ipc/handoff_to_structured.json` at overlapping moments (e.g. a
retry triggered by a transient network timeout, while the
original forward path is still in flight). Without a
serialisation guarantee, one round's payload silently overwrites
the other and the structured half receives stale or mixed data.
This is the ordinary "split-brain" failure that sinks small
distributed systems first, ahead of all the more glamorous LLM
problems.

The ONE primitive that surfaces it: **atomic-rename IPC**
(Decision 5 in the sovereign-agent architecture). The handoff
writer pattern is `write_to_temp_path → fsync → rename(temp,
final)` plus a fail-closed rotation (existing forward handoffs
move to `logs/handoffs/round_N_forward.json` before a new one is
written). On Linux/macOS POSIX semantics, `rename` is atomic
within the same filesystem — a reader observing
`ipc/handoff_to_structured.json` either sees the previous version
or the new version, never a torn write. More importantly, the
"only one forward handoff visible at a time" invariant is what
catches the race: if round 2's pre-rotation move sees an
unexpected file already in place, the bridge can fail loudly
instead of silently clobbering.

I observed the invariant holding empirically in both my offline
session `sess_86dab8dc4888/ipc/` and the real-Nebius
`sess_4198f5144a74/ipc/` — at every inspection, exactly one
forward handoff was visible. Without atomic-rename + the rotation
invariant, this failure would manifest as "the manager kept
getting outdated bookings" with no trace pointer. With it, the
rotation step throws and the `session.state_changed` event records
exactly which round was stale. 

### Citation

- `starter/handoff_bridge/bridge.py` — `write_handoff` + fail-closed rotation into `logs/handoffs/`
- `sess_86dab8dc4888/ipc/handoff_to_structured.json` — offline single-handoff invariant
- `sess_4198f5144a74/ipc/` — real-Nebius single-handoff invariant
- sovereign-agent README Decision 5 — atomic IPC rename
