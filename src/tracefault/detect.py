"""Rule detectors, one per failure type. Each rule states its threshold.

A detector takes a trace and the thresholds and returns findings. No model is in the
loop. Thresholds ship in `thresholds.json`, tuned on one seed by `tracefault tune`.

Trace settings come from the root span. They are tracefault's own attributes, because
the GenAI conventions do not define limits:
`tracefault.context_limit`, `tracefault.budget_tokens`, `tracefault.timeout_s`,
`tracefault.tools.allowed` and, per handoff span, `tracefault.handoff.required` with
`tracefault.handoff.payload`. Available tools come from `gen_ai.tool.definitions`.
When a setting is missing, a detector falls back to the error text or skips.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from importlib import resources

from .model import Span, Trace

DEFAULTS = {
    "tool_error_loop.min_errors": 3,
    "repeated_calls.min_repeats": 3,
    "context_overflow.near_ratio": 0.9,
    "context_overflow.drop_ratio": 0.6,
    "wrong_tool.min_offtask": 2,
    "timeout.ratio": 1.0,
    "budget_exhaustion.ratio": 1.0,
}
TIMEOUT_TEXT = re.compile(r"time ?out|timed out|deadline exceeded", re.I)
UNKNOWN_TEXT = re.compile(r"(unknown|no such) (tool|function)|tool \S+ not found", re.I)
BUDGET_TEXT = re.compile(r"budget (exceeded|exhausted)|token limit reached|quota exceeded", re.I)


@dataclass(frozen=True)
class Finding:
    type: str
    trace_id: str
    span_id: str
    message: str


def tuned_on_seed() -> int | None:
    """The seed the shipped thresholds were tuned on, from `thresholds.json`."""
    try:
        data = json.loads(resources.files("tracefault").joinpath("thresholds.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    seed = data.get("tuned_on_seed")
    return seed if isinstance(seed, int) else None


def load_thresholds() -> dict[str, float]:
    """The shipped thresholds, falling back to the defaults for any missing key."""
    th = dict(DEFAULTS)
    try:
        data = json.loads(resources.files("tracefault").joinpath("thresholds.json").read_text())
        th.update(data.get("thresholds", {}))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return th


def _num(x) -> float | None:
    if isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError, OverflowError):
        return None


def tool_error_loop(t: Trace, th: dict) -> list[Finding]:
    """Fires at `min_errors` or more tool errors in a row. Model calls in between do not
    break the run. Any successful tool call does."""
    k = int(th["tool_error_loop.min_errors"])
    run: list[Span] = []
    for s in t.tools():
        if s.error:
            run.append(s)
            if len(run) == k:
                names = sorted({x.tool_name or x.name for x in run})
                return [
                    Finding(
                        "tool_error_loop",
                        t.trace_id,
                        s.span_id,
                        f"{k}+ tool errors in a row on {', '.join(names)}: {s.error}",
                    )
                ]
        else:
            run = []
    return []


def repeated_calls(t: Trace, th: dict) -> list[Finding]:
    """Fires when one tool gets the same arguments `min_repeats` or more times and
    every one of those calls succeeds (the agent is stuck, not retrying)."""
    k = int(th["repeated_calls.min_repeats"])
    seen: Counter = Counter()
    for s in t.tools():
        if s.error:
            continue
        key = (s.tool_name or s.name, str(s.attrs.get("gen_ai.tool.call.arguments", "")))
        seen[key] += 1
        if seen[key] == k:
            return [
                Finding(
                    "repeated_calls",
                    t.trace_id,
                    s.span_id,
                    f"{key[0]} called {k}+ times with the same arguments",
                )
            ]
    return []


def context_overflow(t: Trace, th: dict) -> list[Finding]:
    """Fires when a model call's input reaches `near_ratio` of the context limit and then
    shows truncation: a `length` finish, or the next model input drops below
    `drop_ratio` of it. With no declared limit, it needs both truncation signs."""
    near, drop = th["context_overflow.near_ratio"], th["context_overflow.drop_ratio"]
    limit = _num(t.conf("tracefault.context_limit"))
    llms = [s for s in t.llms() if s.input_tokens > 0]
    if not llms:
        return []
    for a, b in zip(llms, llms[1:] + [None], strict=True):
        reasons = a.attrs.get("gen_ai.response.finish_reasons")
        length = reasons == "length" or (isinstance(reasons, list) and "length" in reasons)
        dropped = b is not None and b.input_tokens < drop * a.input_tokens
        if limit:
            hit = a.input_tokens >= near * limit and (length or dropped)
        else:
            hit = length and dropped
        if hit:
            where = f"{a.input_tokens} of {int(limit)} tokens" if limit else f"{a.input_tokens} tokens"
            return [
                Finding(
                    "context_overflow",
                    t.trace_id,
                    a.span_id,
                    f"context near its limit ({where}), then truncated",
                )
            ]
    return []


def wrong_tool(t: Trace, th: dict) -> list[Finding]:
    """Fires at `min_offtask` or more calls to tools that exist but are not on the task's
    `tracefault.tools.allowed` list. Skips traces with no list."""
    allowed = t.conf("tracefault.tools.allowed")
    if not isinstance(allowed, list):
        return []
    known = _available(t)
    off = [
        s
        for s in t.tools()
        if (s.tool_name or s.name) not in allowed and (known is None or (s.tool_name or s.name) in known)
    ]
    k = int(th["wrong_tool.min_offtask"])
    if len(off) >= k:
        names = sorted({s.tool_name or s.name for s in off})
        return [
            Finding(
                "wrong_tool",
                t.trace_id,
                off[k - 1].span_id,
                f"{len(off)} calls to tools outside the task list: {', '.join(names)}",
            )
        ]
    return []


def timeout(t: Trace, th: dict) -> list[Finding]:
    """Fires when a tool call lasts `ratio` times the declared timeout or longer, or has
    `error.type` = `timeout`. With no declared timeout, it matches the error text."""
    limit = _num(t.conf("tracefault.timeout_s"))
    for s in t.tools():
        slow = limit is not None and s.duration >= th["timeout.ratio"] * limit
        typed = s.attrs.get("error.type") == "timeout"
        text = limit is None and bool(s.error) and bool(TIMEOUT_TEXT.search(s.error or ""))
        if slow or typed or text:
            return [
                Finding(
                    "timeout",
                    t.trace_id,
                    s.span_id,
                    f"{s.tool_name or s.name} ran {s.duration:.1f} s"
                    + (f" (timeout {limit:g} s)" if limit else "")
                    + (f": {s.error}" if s.error else ""),
                )
            ]
    return []


def budget_exhaustion(t: Trace, th: dict) -> list[Finding]:
    """Fires when the trace's tokens reach `ratio` times `tracefault.budget_tokens`.
    With no declared budget, it matches budget words in the root error."""
    budget = _num(t.conf("tracefault.budget_tokens"))
    used = sum(s.tokens for s in t.spans)
    if budget:
        if used >= th["budget_exhaustion.ratio"] * budget:
            return [
                Finding(
                    "budget_exhaustion",
                    t.trace_id,
                    t.root.span_id,
                    f"used {used} tokens of a {int(budget)} token budget",
                )
            ]
        return []
    if t.root.error and BUDGET_TEXT.search(t.root.error):
        return [Finding("budget_exhaustion", t.trace_id, t.root.span_id, t.root.error)]
    return []


def _available(t: Trace) -> set[str] | None:
    defs = t.conf("gen_ai.tool.definitions")
    if not isinstance(defs, list):
        return None
    return {d["name"] for d in defs if isinstance(d, dict) and isinstance(d.get("name"), str)}


def unknown_tool(t: Trace, th: dict) -> list[Finding]:
    """Fires on a call to a tool that is not in `gen_ai.tool.definitions`. Threshold: one
    call. With no definitions, it matches unknown tool text in the error."""
    known = _available(t)
    for s in t.tools():
        name = s.tool_name or s.name
        if known is not None and name not in known:
            return [
                Finding("unknown_tool", t.trace_id, s.span_id, f"call to a tool that does not exist: {name}")
            ]
        if known is None and s.error and UNKNOWN_TEXT.search(s.error):
            return [Finding("unknown_tool", t.trace_id, s.span_id, s.error)]
    return []


def handoff_drop(t: Trace, th: dict) -> list[Finding]:
    """Fires when a handoff payload lacks a required field, or holds it as null or empty.
    Threshold: one field. A payload that is not a JSON object counts as dropped."""
    for s in t.spans:
        req = s.attrs.get("tracefault.handoff.required")
        if not isinstance(req, list):
            continue
        payload = s.attrs.get("tracefault.handoff.payload", "")
        if not isinstance(payload, dict):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError, RecursionError):
                payload = None
        if not isinstance(payload, dict):
            return [Finding("handoff_drop", t.trace_id, s.span_id, "handoff payload is not a JSON object")]
        # A field name that is not a string can never be present in a JSON object.
        missing = [f for f in req if not isinstance(f, str) or payload.get(f) in (None, "")]
        if missing:
            return [
                Finding(
                    "handoff_drop",
                    t.trace_id,
                    s.span_id,
                    f"handoff to {s.name} dropped required field {', '.join(map(str, missing))}",
                )
            ]
    return []


DETECTORS = {
    "tool_error_loop": tool_error_loop,
    "repeated_calls": repeated_calls,
    "context_overflow": context_overflow,
    "wrong_tool": wrong_tool,
    "timeout": timeout,
    "budget_exhaustion": budget_exhaustion,
    "unknown_tool": unknown_tool,
    "handoff_drop": handoff_drop,
}


def scan(t: Trace, th: dict | None = None) -> list[Finding]:
    th = th or load_thresholds()
    out: list[Finding] = []
    for fn in DETECTORS.values():
        out += fn(t, th)
    return out
