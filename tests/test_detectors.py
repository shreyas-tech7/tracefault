"""Each detector: it fires on a trace with its fault and stays quiet on a clean trace.
The boundary tests show the stated threshold."""

import json

import pytest
from builders import TID, B, clean

from tracefault.detect import DEFAULTS, DETECTORS, scan
from tracefault.generate import FAULTS, generate
from tracefault.model import AGENT, Span

TH = dict(DEFAULTS)
ERR = "ConnectionError: upstream returned 503"


def fired(trace, kind):
    return [f.type for f in DETECTORS[kind](trace, TH)] == [kind]


def test_clean_trace_has_no_findings():
    """Broken case: any detector that fires on a healthy run."""
    assert scan(clean(), TH) == []


@pytest.mark.parametrize("kind", FAULTS)
def test_each_detector_quiet_on_clean(kind):
    assert DETECTORS[kind](clean(), TH) == []


# tool_error_loop: 3 tool errors in a row


def test_error_loop_fires_at_three():
    b = B()
    for _ in range(3):
        b.llm().tool(error=ERR)
    assert fired(b.llm(finish="stop").build(), "tool_error_loop")


def test_error_loop_quiet_on_two_then_success():
    """Broken case: a normal retry counted as a loop."""
    t = B().llm().tool(error=ERR).llm().tool(error=ERR).llm().tool().llm(finish="stop").build()
    assert DETECTORS["tool_error_loop"](t, TH) == []


# repeated_calls: 3 identical successful calls


def test_repeated_calls_fires_at_three():
    b = B()
    for _ in range(3):
        b.llm().tool("get_weather", '{"city": "Austin"}')
    assert fired(b.build(), "repeated_calls")


def test_repeated_calls_ignores_failed_calls_and_two_polls():
    b = B().llm().tool("check_status", '{"job": 1}').tool("check_status", '{"job": 1}')
    for _ in range(3):
        b.llm().tool("get_weather", '{"city": "Austin"}', error=ERR)
    assert DETECTORS["repeated_calls"](b.build(), TH) == []


# context_overflow: input at 90% of the limit, then truncation


def test_overflow_fires_on_near_limit_then_drop():
    t = B().llm(inp=7900, finish="length").llm(inp=2500).build()
    assert fired(t, "context_overflow")


def test_overflow_quiet_when_near_limit_without_truncation():
    t = B().llm(inp=7500).tool().llm(inp=7700, finish="stop").build()
    assert DETECTORS["context_overflow"](t, TH) == []


def test_overflow_quiet_on_compaction_far_from_limit():
    """Broken case: a summary step that halves a small context counted as overflow."""
    t = B().llm(inp=3000).llm(inp=1500).build()
    assert DETECTORS["context_overflow"](t, TH) == []


def test_overflow_without_limit_needs_both_signs():
    no_limit = ("tracefault.context_limit",)
    assert fired(B(drop=no_limit).llm(inp=9000, finish="length").llm(inp=2000).build(), "context_overflow")
    assert (
        DETECTORS["context_overflow"](
            B(drop=no_limit).llm(inp=9000, finish="length").llm(inp=9100).build(), TH
        )
        == []
    )


# wrong_tool: 2 calls to existing tools outside the task list


def test_wrong_tool_fires_at_two_offtask_calls():
    t = B().llm().tool("book_flight").llm().tool("book_flight", '{"id": 2}').build()
    assert fired(t, "wrong_tool")


def test_wrong_tool_quiet_on_one_exploratory_call_and_without_list():
    assert DETECTORS["wrong_tool"](B().llm().tool("book_flight").build(), TH) == []
    t = B(drop=("tracefault.tools.allowed",)).tool("book_flight").tool("book_flight").build()
    assert DETECTORS["wrong_tool"](t, TH) == []


# timeout: a tool call that lasts the declared timeout or longer


def test_timeout_fires_on_long_call():
    assert fired(B().llm().tool(dur=31.0, error="deadline exceeded").build(), "timeout")


def test_timeout_fires_on_error_type():
    assert fired(B().llm().tool(dur=2.0, error="boom", error_type="timeout").build(), "timeout")


def test_timeout_quiet_on_slow_call_in_time():
    assert DETECTORS["timeout"](B().llm().tool(dur=29.0).build(), TH) == []


def test_timeout_text_fallback_only_without_limit():
    t = B(drop=("tracefault.timeout_s",)).tool(dur=1.0, error="TimeoutError: no answer").build()
    assert fired(t, "timeout")
    assert DETECTORS["timeout"](B().tool(dur=1.0, error="TimeoutError: no answer").build(), TH) == []


# budget_exhaustion: tokens at or over the budget


def test_budget_fires_at_budget():
    b = B()
    for _ in range(10):
        b.llm(inp=1900, out=100)
    assert fired(b.build(), "budget_exhaustion")


def test_budget_quiet_under_budget_and_text_fallback():
    b = B()
    for _ in range(9):
        b.llm(inp=1900, out=100)
    assert DETECTORS["budget_exhaustion"](b.build(), TH) == []
    t = B(drop=("tracefault.budget_tokens",)).llm().build(root_error="budget exceeded: token limit reached")
    assert fired(t, "budget_exhaustion")


# unknown_tool: a call to a tool that is not defined


def test_unknown_tool_fires():
    assert fired(B().llm().tool("get_wether", error="unknown tool 'get_wether'").build(), "unknown_tool")


def test_unknown_tool_text_fallback_and_file_not_found():
    no_defs = ("gen_ai.tool.definitions",)
    assert fired(B(drop=no_defs).tool("x", error="Tool x not found").build(), "unknown_tool")
    t = B(drop=no_defs).tool("geocode", error="FileNotFoundError: file not found: a.csv").build()
    assert DETECTORS["unknown_tool"](t, TH) == []


# handoff_drop: a required field missing, null or empty


def _handoff(payload):
    s = Span(
        TID,
        "h1",
        "root",
        AGENT,
        "invoke_agent refund_agent",
        1.0,
        2.0,
        attrs={
            "tracefault.handoff.required": ["customer_id", "order_id"],
            "tracefault.handoff.payload": payload,
        },
    )
    return B().llm().span(s).build()


@pytest.mark.parametrize(
    "payload",
    [
        json.dumps({"customer_id": "C1"}),
        json.dumps({"customer_id": "C1", "order_id": None}),
        json.dumps({"customer_id": "", "order_id": "O1"}),
        "not json",
        "[1, 2]",
    ],
)
def test_handoff_drop_fires(payload):
    assert fired(_handoff(payload), "handoff_drop")


def test_handoff_complete_is_quiet():
    assert (
        DETECTORS["handoff_drop"](_handoff(json.dumps({"customer_id": "C1", "order_id": "O1", "x": 1})), TH)
        == []
    )


@pytest.mark.parametrize("kind", FAULTS)
def test_generated_fault_is_found(kind):
    """Every planted fault type gets found on a generated trace of that type."""
    traces, truth = generate(8, 0, seed=11)
    hits = [bool(DETECTORS[kind](t, TH)) for t in traces if truth[t.trace_id] == kind]
    assert sum(hits) >= 4, hits
