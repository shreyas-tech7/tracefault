"""Group findings by a signature: normalized error text plus the n-gram of tool calls
that led to the failing span."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from .detect import Finding
from .model import Trace

N = 3
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
_HEX = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{6,}\b")
_NUM = re.compile(r"\d+(?:\.\d+)?")
_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase. Quoted values become S, hex ids X, numbers N. Spaces collapse."""
    s = text.lower()
    s = _QUOTED.sub("S", s)
    s = _HEX.sub("X", s)
    s = _NUM.sub("N", s)
    return _SPACE.sub(" ", s).strip()[:120]


def ngram(t: Trace, span_id: str, n: int = N) -> tuple[str, ...]:
    """The last `n` tool names up to and including the failing span. Empty when the
    failing span is not a tool call (a budget or a handoff finding, for example)."""
    names = []
    for s in t.tools():
        names.append(s.tool_name or s.name)
        if s.span_id == span_id:
            return tuple(names[-n:])
    return ()


def signature(t: Trace, f: Finding) -> str:
    span = next((s for s in t.spans if s.span_id == f.span_id), None)
    text = span.error if span is not None and span.error else f.message
    return f"{f.type} | {normalize(text)} | {' > '.join(ngram(t, f.span_id)) or '-'}"


@dataclass
class Cluster:
    signature: str
    type: str
    trace_ids: list[str]

    @property
    def size(self) -> int:
        return len(self.trace_ids)


def cluster(pairs: list[tuple[Trace, Finding]]) -> list[Cluster]:
    groups: dict[str, list[str]] = defaultdict(list)
    types: dict[str, str] = {}
    for t, f in pairs:
        sig = signature(t, f)
        groups[sig].append(t.trace_id)
        types[sig] = f.type
    out = [Cluster(sig, types[sig], ids) for sig, ids in groups.items()]
    out.sort(key=lambda c: (-c.size, c.signature))
    return out
