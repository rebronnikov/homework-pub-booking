"""Ex5 — reference solution for integrity.py.

verify_dataflow's job: for every concrete fact in the flyer, confirm
that some tool call in the session actually produced that value. If
a fact exists in the flyer but not in any tool output, it's fabrication.

Two competing failure modes to balance:
  - Too lenient → misses fabrications (grader plants £9999; must catch it)
  - Too strict → rejects legitimate flyers (fails the "accepts real flyer" test)

This implementation leans slightly strict but uses the scalar-matching
`fact_appears_in_log` helper provided in the starter to tolerate common
variations (leading £, trailing C, case differences).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict
    output: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


_TOOL_CALL_LOG: list[ToolCallRecord] = []


def record_tool_call(tool_name: str, arguments: dict, output: dict) -> None:
    _TOOL_CALL_LOG.append(
        ToolCallRecord(tool_name=tool_name, arguments=dict(arguments), output=dict(output))
    )


def clear_log() -> None:
    _TOOL_CALL_LOG.clear()


@dataclass
class IntegrityResult:
    ok: bool
    unverified_facts: list[str] = field(default_factory=list)
    verified_facts: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "unverified_facts": self.unverified_facts,
            "verified_facts": self.verified_facts,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_money_facts(text: str) -> list[str]:
    """Find all £<number> occurrences, HTML tags stripped or not."""
    # Strip HTML tags first so e.g. <dd>£540</dd> matches cleanly.
    stripped = re.sub(r"<[^>]+>", " ", text)
    return re.findall(r"£\d+(?:\.\d+)?", stripped)


def extract_temperature_facts(text: str) -> list[str]:
    """Find temperature mentions (number followed by °C or C)."""
    stripped = re.sub(r"<[^>]+>", " ", text)
    return list({m.group(1) for m in re.finditer(r"(\d+)\s*°?\s*[Cc]\b", stripped)})


def extract_condition_facts(text: str) -> list[str]:
    """Find weather condition keywords."""
    stripped = re.sub(r"<[^>]+>", " ", text)
    tl = stripped.lower()
    known = ("sunny", "rainy", "cloudy", "partly_cloudy", "partly cloudy")
    return [c for c in known if c in tl]


def extract_testid_facts(text: str) -> dict[str, str]:
    """For HTML flyers that use data-testid, extract {testid: value} pairs.

    This is the preferred path for HTML — it gives us structured facts
    (e.g. {'total': '£540', 'deposit': '£0'}) instead of loose regex
    matches. The solution flyer ships with data-testid on every fact.
    """
    pattern = re.compile(
        r'<[^>]+data-testid="([^"]+)"[^>]*>([^<]+)</[^>]+>',
        re.IGNORECASE,
    )
    return {m.group(1): m.group(2).strip() for m in pattern.finditer(text)}


def fact_appears_in_log(fact: Any, log: list[ToolCallRecord] | None = None) -> bool:
    records = log if log is not None else _TOOL_CALL_LOG
    target = str(fact).lower().strip("£°c ")

    def _scan(obj: Any) -> bool:
        if isinstance(obj, (str, int, float)):
            return str(obj).lower().strip("£°c ") == target
        if isinstance(obj, dict):
            return any(_scan(v) for v in obj.values())
        if isinstance(obj, (list, tuple, set)):
            return any(_scan(v) for v in obj)
        return False

    return any(_scan(r.output) or _scan(r.arguments) for r in records)


# ---------------------------------------------------------------------------
# verify_dataflow — the main check
# ---------------------------------------------------------------------------
def verify_dataflow(flyer_content: str) -> IntegrityResult:
    """Audit a flyer against the tool-call log.

    Bug fix (homework-pub-booking Issue #14): the original implementation
    let `fact_appears_in_log` scan both `output` and `arguments` of every
    record — including `generate_flyer`'s OWN arguments. Since the flyer's
    facts are passed as arguments into `generate_flyer`, the flyer would
    self-verify even if the LLM made the numbers up. To close that loop:

      1. Build `audit_records` that EXCLUDE generate_flyer's record. The
         flyer cannot be its own source of truth.
      2. PROJECT each remaining record so only `output` is visible to the
         scanner. Arguments to tools like calculate_cost are user-supplied
         (e.g. party_size=6) and shouldn't count as "produced by a tool".
         Only what the tool *returned* is ground truth.

    The helper `fact_appears_in_log()` itself is kept untouched because
    `test_fact_appears_in_log_helper` exercises its raw contract. The fix
    lives in *how* verify_dataflow builds the log it passes in.
    """
    if not flyer_content or not flyer_content.strip():
        return IntegrityResult(ok=True, summary="no facts to verify (empty flyer)")

    # Build the projected audit log: drop generate_flyer's record entirely,
    # and project the rest to outputs-only (arguments={} so the scanner
    # never sees them).
    audit_records: list[ToolCallRecord] = [
        ToolCallRecord(
            tool_name=r.tool_name,
            arguments={},
            output=r.output,
            timestamp=r.timestamp,
        )
        for r in _TOOL_CALL_LOG
        if r.tool_name != "generate_flyer"
    ]

    facts_to_check: list[str] = []
    facts_to_check.extend(extract_money_facts(flyer_content))
    facts_to_check.extend(extract_temperature_facts(flyer_content))
    facts_to_check.extend(extract_condition_facts(flyer_content))

    # De-dupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for f in facts_to_check:
        key = f.lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    if not deduped:
        return IntegrityResult(
            ok=True, summary="no extractable facts in flyer (verified vacuously)"
        )

    verified: list[str] = []
    unverified: list[str] = []
    for fact in deduped:
        if fact_appears_in_log(fact, log=audit_records):
            verified.append(fact)
        else:
            unverified.append(fact)

    if unverified:
        return IntegrityResult(
            ok=False,
            unverified_facts=unverified,
            verified_facts=verified,
            summary=(
                f"dataflow FAIL: {len(unverified)} unverified fact(s): "
                f"{unverified[:5]}" + ("..." if len(unverified) > 5 else "")
            ),
        )

    return IntegrityResult(
        ok=True,
        verified_facts=verified,
        summary=f"dataflow OK: verified {len(verified)} fact(s) against tool outputs",
    )


__all__ = [
    "IntegrityResult",
    "ToolCallRecord",
    "_TOOL_CALL_LOG",
    "clear_log",
    "extract_condition_facts",
    "extract_money_facts",
    "extract_temperature_facts",
    "extract_testid_facts",
    "fact_appears_in_log",
    "record_tool_call",
    "verify_dataflow",
]
