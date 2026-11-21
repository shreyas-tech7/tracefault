"""Seeded trace generator with planted failures and ground truth.

Each trace is one agent run on a task. A run is a list of steps: a model call, then a
tool call. A fault plan changes some steps. The ground truth (which fault, if any,
was planted) is returned next to the traces and never written into them.

Clean traces carry benign noise on purpose, so precision means something:
one retry after a tool error, two identical status polls (rarely three), one
exploratory call outside the task's tool list, slow tool calls that still finish in
time, a context that gets near its limit without truncation, a summary step that
shrinks the context, a `length` finish on a short context and spend up to 97% of the
budget. About 15% of traces also leave out one of their declared limits, as real
traces often do.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

from .model import AGENT, LLM, TOOL, Span, Trace

FAULTS = (
    "tool_error_loop",
    "repeated_calls",
    "context_overflow",
    "wrong_tool",
    "timeout",
    "budget_exhaustion",
    "unknown_tool",
    "handoff_drop",
)
TASKS = {
    "weather": ["get_weather", "geocode"],
    "billing": ["lookup_invoice", "refund_payment"],
    "travel": ["search_flights", "book_flight"],
    "code": ["read_file", "run_tests"],
    "support": ["search_kb", "create_ticket"],
}
HELPERS = ["get_time", "check_status"]
HALLUCINATED = ["get_wether", "lookup_invoices", "search_flight_v2", "run_all_tests", "kb_search"]
TOOL_ERRORS = [
    "ConnectionError: upstream returned 503 for request 7f3a9c21",
    "ValueError: invalid date '2026-13-01'",
    "PermissionError: token for user 4411 lacks scope billing:write",
    "KeyError: 'result' missing in response of 812 bytes",
]
TIMEOUT_ERRORS = [
    "timeout",
    "TimeoutError: tool did not answer in 30 s",
    "deadline exceeded",
    "504 Gateway Timeout",
]
UNKNOWN_ERRORS = ["unknown tool '{t}'", "Tool {t} not found", "no such function: {t}", "invalid request"]
LIMITS = (8192, 16384, 32768)
EPOCH = 1_767_225_600  # 2026-01-01T00:00:00Z
MISSING_P = 0.15
CLEAN_SPEND_MAX = 0.97


@dataclass
class Step:
    tool: str
    args: str
    error: str | None = None
    error_type: str | None = None
    dur: float = 0.4
    result_tokens: int = 300


@dataclass
class Plan:
    task: str
    steps: list[Step]
    timeout_s: float = 30.0
    handoff: dict | None = None
    root_error: str | None = None
    big_ratio: float | None = None  # context peak / limit for a planted overflow
    compaction: bool = False
    length_finish_early: bool = False
    noise: list[str] = field(default_factory=list)


def _hex(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def _args(rng: random.Random) -> str:
    return json.dumps({"id": f"item-{rng.randint(1, 999)}"})


def _step(rng: random.Random, tool: str, timeout: float) -> Step:
    dur = min(rng.lognormvariate(-1.0, 0.8), 0.6 * timeout)
    return Step(tool, _args(rng), dur=round(dur, 3), result_tokens=rng.randint(150, 900))


def _base_plan(rng: random.Random, task: str) -> Plan:
    tools = TASKS[task]
    plan = Plan(task, [_step(rng, rng.choice(tools), 30.0) for _ in range(rng.randint(3, 7))])
    return plan


def _add_clean_noise(rng: random.Random, p: Plan) -> None:
    tools = TASKS[p.task]
    if rng.random() < 0.20:  # one error, then a retry that works
        i = rng.randrange(len(p.steps))
        s = p.steps[i]
        err = Step(s.tool, s.args, error=rng.choice(TOOL_ERRORS), dur=0.2)
        if rng.random() < 0.10:
            err.error = "upstream timed out, retrying"
        p.steps.insert(i, err)
        p.noise.append("retry")
        if rng.random() < 0.25:  # two errors in a row, on two different tools
            other = [t for t in tools if t != s.tool][0]
            p.steps.insert(i, Step(other, _args(rng), error=rng.choice(TOOL_ERRORS), dur=0.2))
            p.noise.append("two_errors")
    if rng.random() < 0.12:  # status polling: two identical calls, rarely three
        n = 3 if rng.random() < 0.15 else 2
        args = _args(rng)
        i = rng.randrange(len(p.steps) + 1)
        for _ in range(n):
            p.steps.insert(i, Step("check_status", args, dur=0.1, result_tokens=40))
        p.noise.append(f"poll{n}")
    if rng.random() < 0.08:  # one exploratory call outside the task's list
        other = rng.choice([t for k, v in TASKS.items() if k != p.task for t in v])
        p.steps.insert(rng.randrange(len(p.steps) + 1), _step(rng, other, p.timeout_s))
        p.noise.append("explore")
    if rng.random() < 0.15:  # slow but in time
        s = rng.choice(p.steps)
        if not s.error:
            s.dur = round(p.timeout_s * rng.uniform(0.6, 0.95), 3)
            p.noise.append("slow")
    if rng.random() < 0.10:  # a big tool result that gets near the limit
        p.big_ratio = -rng.uniform(0.6, 0.92)  # negative marks "no truncation"
        p.noise.append("near_limit")
    if rng.random() < 0.05:
        p.compaction = True
        p.noise.append("compaction")
    if rng.random() < 0.05:
        p.length_finish_early = True
        p.noise.append("length_early")
    if rng.random() < 0.03:
        p.steps.append(Step("read_file", _args(rng), error="FileNotFoundError: file not found: report.csv"))
        p.noise.append("file_not_found")


def _plant(rng: random.Random, p: Plan, fault: str) -> None:
    tools = TASKS[p.task]
    i = rng.randrange(1, len(p.steps) + 1)
    if fault == "tool_error_loop":
        n = rng.randint(3, 7)
        err = rng.choice(TOOL_ERRORS)
        if rng.random() < 0.25:  # two tools that both keep failing
            loop = [Step(tools[k % 2], _args(rng), error=err, dur=0.2) for k in range(n)]
        else:
            args = _args(rng)
            loop = [Step(tools[0], args, error=err, dur=0.2) for _ in range(n)]
        p.steps[i:] = loop
        if rng.random() < 0.5:
            p.root_error = f"agent gave up after {n} tool errors"
    elif fault == "repeated_calls":
        n = rng.randint(3, 6)
        s = _step(rng, rng.choice(tools), p.timeout_s)
        p.steps[i:i] = [Step(s.tool, s.args, dur=s.dur, result_tokens=s.result_tokens) for _ in range(n)]
    elif fault == "context_overflow":
        p.big_ratio = rng.uniform(0.88, 1.0)
    elif fault == "wrong_tool":
        n = rng.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]
        others = [t for k, v in TASKS.items() if k != p.task for t in v]
        for _ in range(n):
            p.steps.insert(rng.randrange(1, len(p.steps) + 1), _step(rng, rng.choice(others), p.timeout_s))
    elif fault == "timeout":
        s = Step(rng.choice(tools), _args(rng), error=rng.choice(TIMEOUT_ERRORS))
        s.dur = round(p.timeout_s * rng.uniform(1.0, 1.25), 3)
        if rng.random() < 0.6:
            s.error_type = "timeout"
        p.steps.insert(i, s)
    elif fault == "budget_exhaustion":
        p.steps += [_step(rng, rng.choice(tools), p.timeout_s) for _ in range(rng.randint(2, 5))]
        if rng.random() < 0.7:
            p.root_error = "budget exceeded: token limit reached"
    elif fault == "unknown_tool":
        bad = rng.choice(HALLUCINATED)
        err = rng.choice(UNKNOWN_ERRORS).format(t=bad)
        p.steps.insert(i, Step(bad, _args(rng), error=err, dur=0.05))
    elif fault == "handoff_drop":
        pass  # handled in _handoff


def _handoff(rng: random.Random, p: Plan, fault: str | None) -> None:
    if fault != "handoff_drop" and rng.random() > 0.3:
        return
    required = ["customer_id", "order_id", "summary"]
    payload: dict = {
        "customer_id": f"C{rng.randint(100, 999)}",
        "order_id": f"O{rng.randint(1000, 9999)}",
        "summary": "refund request",
    }
    if rng.random() < 0.5:
        payload["notes"] = "optional context"
    if fault == "handoff_drop":
        k = rng.choice(required)
        if rng.random() < 0.3:
            payload[k] = rng.choice([None, ""])
        else:
            del payload[k]
    p.handoff = {"required": required, "payload": payload}


def _render(rng: random.Random, p: Plan, fault: str | None, idx: int) -> Trace:
    tid = _hex(rng, 32)
    t = EPOCH + idx * 3600 + rng.randint(0, 3000)
    spans: list[Span] = []
    root_id = _hex(rng, 16)
    context = rng.randint(800, 2000)
    peak = context
    budget_used = 0
    pending_big = p.big_ratio
    limit = rng.choice(LIMITS)

    def llm(parent: str, finish: str, inp: int) -> Span:
        nonlocal t, budget_used
        out = rng.randint(50, 400)
        dur = round(rng.uniform(0.3, 2.5), 3)
        s = Span(
            tid,
            _hex(rng, 16),
            parent,
            LLM,
            "chat synthetic-model",
            round(t, 3),
            round(t + dur, 3),
            inp,
            out,
            attrs={"gen_ai.request.model": "synthetic-model", "gen_ai.response.finish_reasons": [finish]},
        )
        t += dur + 0.01
        budget_used += inp + out
        spans.append(s)
        return s

    def tool(parent: str, st: Step) -> Span:
        nonlocal t
        a = {"gen_ai.tool.call.arguments": st.args, "gen_ai.tool.call.id": "call_" + _hex(rng, 8)}
        if st.error_type:
            a["error.type"] = st.error_type
        s = Span(
            tid,
            _hex(rng, 16),
            parent,
            TOOL,
            f"execute_tool {st.tool}",
            round(t, 3),
            round(t + st.dur, 3),
            error=st.error,
            tool_name=st.tool,
            attrs=a,
        )
        t += st.dur + 0.01
        spans.append(s)
        return s

    start = t
    truncated = False
    for k, st in enumerate(p.steps):
        finish = "tool_call"
        if p.length_finish_early and k == 0:
            finish = "length"
        if pending_big is not None and k == len(p.steps) // 2:
            # a big tool result lands in the context
            ratio = abs(pending_big)
            target = int(ratio * limit)
            if target > context:
                context = target
                peak = max(peak, context)
                if pending_big > 0:  # planted overflow: hit the limit, then truncate
                    llm(root_id, "length", context)
                    context = int(context * rng.uniform(0.3, 0.5))
                    truncated = True
            pending_big = None
        if p.compaction and k == len(p.steps) // 2 and context > 2000:
            context = int(context * 0.5)
        llm(root_id, finish, context)
        context += rng.randint(50, 400)
        tool(root_id, st)
        context += 40 if st.error else st.result_tokens
        peak = max(peak, context)
    if p.big_ratio is not None and p.big_ratio > 0 and not truncated:
        target = int(p.big_ratio * limit)
        llm(root_id, "length", max(target, context))
        peak = max(peak, target)
        context = int(target * 0.4)
    if p.handoff:
        child = _hex(rng, 16)
        cs = len(spans)
        s0 = t
        st = _step(rng, TASKS[p.task][-1], p.timeout_s)
        llm(child, "tool_call", rng.randint(500, 1500))
        tool(child, st)
        llm(child, "stop", rng.randint(500, 1500))
        spans.insert(
            cs,
            Span(
                tid,
                child,
                root_id,
                AGENT,
                "invoke_agent refund_agent",
                round(s0, 3),
                round(t, 3),
                attrs={
                    "gen_ai.agent.name": "refund_agent",
                    "tracefault.handoff.required": p.handoff["required"],
                    "tracefault.handoff.payload": json.dumps(p.handoff["payload"]),
                },
            ),
        )
    llm(root_id, "stop", context)
    # The limit stays above the peak for clean traces.
    if not (p.big_ratio is not None and p.big_ratio > 0):
        while limit < peak / 0.92 and limit != LIMITS[-1]:
            limit = LIMITS[LIMITS.index(limit) + 1]
        if peak > 0.92 * limit:
            limit = int(peak / 0.9)
    total = budget_used
    if fault == "budget_exhaustion":
        budget = int(total / rng.uniform(1.0, 1.3) // 100 * 100)
    else:
        budget = int((total / rng.uniform(0.5, CLEAN_SPEND_MAX)) // 100 * 100 + 100)
    available = sorted({x for v in TASKS.values() for x in v} | set(HELPERS))
    conf = {
        "gen_ai.agent.name": f"{p.task}_agent",
        "gen_ai.request.model": "synthetic-model",
        "tracefault.task": p.task,
        "tracefault.tools.allowed": TASKS[p.task] + HELPERS,
        "gen_ai.tool.definitions": [{"type": "function", "name": n} for n in available],
        "tracefault.context_limit": limit,
        "tracefault.budget_tokens": budget,
        "tracefault.timeout_s": p.timeout_s,
    }
    if rng.random() < MISSING_P:
        drop = rng.choice(
            [
                "gen_ai.tool.definitions",
                "tracefault.tools.allowed",
                "tracefault.context_limit",
                "tracefault.budget_tokens",
                "tracefault.timeout_s",
            ]
        )
        del conf[drop]
    root = Span(
        tid,
        root_id,
        None,
        AGENT,
        f"invoke_agent {p.task}_agent",
        round(start - 0.01, 3),
        round(t, 3),
        error=p.root_error,
        attrs=conf,
    )
    return Trace(tid, [root] + spans)


def generate(n_per_fault: int, n_clean: int, seed: int) -> tuple[list[Trace], dict[str, str | None]]:
    """Make `n_per_fault` traces for each fault type plus `n_clean` clean traces.

    Returns the traces (in shuffled order) and the truth: trace id to fault type or None.
    """
    rng = random.Random(seed)
    kinds: list[str | None] = [f for f in FAULTS for _ in range(n_per_fault)] + [None] * n_clean
    rng.shuffle(kinds)
    traces, truth = [], {}
    for idx, fault in enumerate(kinds):
        p = _base_plan(rng, rng.choice(sorted(TASKS)))
        _add_clean_noise(rng, p)
        if fault:
            _plant(rng, p, fault)
        _handoff(rng, p, fault)
        tr = _render(rng, p, fault, idx)
        traces.append(tr)
        truth[tr.trace_id] = fault
    return traces, truth
