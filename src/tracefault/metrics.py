"""Per trace metrics: tokens, cost, latency, critical path and retries."""

from __future__ import annotations

from dataclasses import dataclass

from .model import TOOL, Span, Trace


@dataclass
class TraceMetrics:
    trace_id: str
    spans: int
    errors: int
    input_tokens: int
    output_tokens: int
    cost_usd: float | None
    latency_s: float
    critical_path: list[str]
    critical_path_s: float
    retries: int


def critical_path(t: Trace) -> list[Span]:
    """The chain of spans that set the trace's end time, in time order, root first.

    Walk back from a span's end: take the child that ended last, jump to its start, take
    the child that ended before that, and so on. Then do the same inside each child taken.
    Hostile traces can hold parent cycles or deep nesting, so this keeps a seen set and
    uses a stack instead of recursion.
    """
    kids: dict[str, list[Span]] = {}
    for s in t.spans:
        if s.parent_id:
            kids.setdefault(s.parent_id, []).append(s)
    out: list[Span] = []
    seen: set[str] = set()
    stack = [t.root]
    while stack:
        span = stack.pop()
        if span.span_id in seen:
            continue
        seen.add(span.span_id)
        out.append(span)
        picked: list[Span] = []
        cursor = span.end
        for kid in sorted(kids.get(span.span_id, []), key=lambda s: (s.end, s.start), reverse=True):
            if kid.span_id not in seen and kid.end <= cursor + 1e-9:
                picked.insert(0, kid)
                cursor = kid.start
        stack += reversed(picked)
    return out


def _covered(t: Trace) -> float:
    """Seconds of the root covered by its critical children. The rest is the root's own time."""
    path = critical_path(t)
    return sum(s.duration for s in path if s.parent_id == t.root.span_id)


def retries(t: Trace) -> int:
    """Tool calls that repeat the same tool right after that tool failed."""
    n, prev = 0, None
    for s in t.spans:
        if s.kind != TOOL:
            continue
        name = s.tool_name or s.name
        if prev is not None and prev.error and (prev.tool_name or prev.name) == name:
            n += 1
        prev = s
    return n


def cost(t: Trace, prices: dict[str, list[float]] | None) -> float | None:
    """Dollars from a price table: model name to [input, output] dollars per million tokens.
    None when no table is given or a model is missing from it."""
    if not prices:
        return None
    total = 0.0
    default = t.root.attrs.get("gen_ai.request.model")
    for s in t.spans:
        if not s.tokens:
            continue
        model = s.attrs.get("gen_ai.response.model") or s.attrs.get("gen_ai.request.model") or default
        if model not in prices:
            return None
        pin, pout = prices[model]
        total += (s.input_tokens * pin + s.output_tokens * pout) / 1e6
    return round(total, 6)


def measure(t: Trace, prices: dict | None = None) -> TraceMetrics:
    path = critical_path(t)
    start = min(s.start for s in t.spans)
    end = max(s.end for s in t.spans)
    return TraceMetrics(
        trace_id=t.trace_id,
        spans=len(t.spans),
        errors=sum(1 for s in t.spans if s.error),
        input_tokens=sum(s.input_tokens for s in t.spans),
        output_tokens=sum(s.output_tokens for s in t.spans),
        cost_usd=cost(t, prices),
        latency_s=round(end - start, 3),
        critical_path=[s.name for s in path],
        critical_path_s=round(_covered(t), 3),
        retries=retries(t),
    )
