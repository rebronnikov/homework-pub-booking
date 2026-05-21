# Ex6 — Rasa structured half

## Your answer

I exercised the structured half three ways: tier-1 mock (`make ex6`,
session `sess_72fd85fc0c84`), tier-3 auto-spawn (`make ex6-auto`,
session `sess_a4eba385395c`, real Rasa Pro 3.16.4 trained + run on
the homework's `rasa_project/`, torn down on exit), and validated
the validator unit tests via `pytest tests/public/test_ex6_*` (8/8
pass). The real-Rasa run trained the model from `flows.yml +
domain.yml + actions/actions.py`, started the action server on
`:5055` and Rasa on `:5005`, POSTed the test booking, got back
`Booking confirmed. Reference: BK-7D401E9E.` (with custom action
emitting `committed`), and tore down cleanly. The booking reference
is deterministic — SHA1 over `venue_id|date|time|party_size`.

`normalise_booking_payload` does the boundary work: `"7:30pm" →
"19:30"`, `"£200" → 200`, `"Haymarket Tap" → "haymarket_tap"`,
`"25th April 2026" → "2026-04-25"`, and `"6" → 6` (rejecting 0/
negative). Five normalisations, packaged into a Rasa REST message
with `metadata.booking` carrying the canonical dict. The Rasa side
reads from `tracker.latest_message.metadata.booking` —
`ActionValidateBooking` was rewritten in CHANGELOG v11 to prefer
metadata over slots because CALM starts flows from `/intent` triggers
without auto-populating slots.

Two notes about the YAML side. First, `rasa_project/data/flows.yml`
ships three flows: `confirm_booking` (the live path) plus stub
`resume_from_loop` and `request_research` flows. ASSIGNMENT.md §Ex6
requires all three for full marks, but CHANGELOG v13 deleted the
last two because the Python `HandoffBridge` handles reverse-handoff
at the orchestration layer. I added them back as minimal trainable
stubs with extensive rationale comments — the YAML itself documents
the spec-vs-design conflict. Second, `structured_half.py`'s top
docstring still referenced docker-compose; I corrected it to
RasaHostLifecycle (Docker was removed in CHANGELOG v10), and also
fixed a real bug in `RasaHostLifecycle.__init__` where the default
`rasa_project_dir` walked one `.parent` too many — failed unless
the homework was checked out in a specific parent directory.

## Citations

- `sess_72fd85fc0c84/session.json` — mock-tier session, scenario `ex6-rasa-half`
- `sess_a4eba385395c/logs/rasa/` — real Rasa Pro train + serve logs, model trained from updated flows.yml
- `sess_a4eba385395c/session.json` — committed booking with reference `BK-7D401E9E`
- `starter/rasa_half/validator.py` — normalise_booking_payload + helpers
- `starter/rasa_half/structured_half.py` — RasaStructuredHalf.run, mock handler, RasaHostLifecycle (with path fix)
- `rasa_project/data/flows.yml` — confirm_booking + stub flows with rationale comments
- `rasa_project/actions/actions.py` — ActionValidateBooking (rules mirrored in the mock)
