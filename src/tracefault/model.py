"""The internal model. Both input formats convert to these two classes.

Field names follow the OpenTelemetry GenAI semantic conventions as fetched on
2026-11-21 (see `OTEL_VERSION`). Every `gen_ai.*` field there is at Development status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OTEL_VERSION = (
    "open-telemetry/semantic-conventions-genai main branch, docs/gen-ai/gen-ai-spans.md and "
    "gen-ai-agent-spans.md fetched 2026-11-21 (core conventions v1.45.0 links). Status: Development."
)

# Span kinds of the internal model.
LLM, TOOL, AGENT, OTHER = "llm", "tool", "agent", "other"
KINDS = (LLM, TOOL, AGENT, OTHER)


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: str | None
    kind: str
    name: str
    start: float  # seconds since the epoch
    end: float
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None  # error text, None when the span succeeded
    tool_name: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class Trace:
    trace_id: str
    spans: list[Span]

    def __post_init__(self) -> None:
        self.spans.sort(key=lambda s: (s.start, s.end, s.span_id))

    @property
    def root(self) -> Span:
        ids = {s.span_id for s in self.spans}
        roots = [s for s in self.spans if not s.parent_id or s.parent_id not in ids]
        return roots[0] if roots else self.spans[0]

    def conf(self, key: str, default: Any = None) -> Any:
        """A trace setting, read from the root span (for example `tracefault.context_limit`)."""
        return self.root.attrs.get(key, default)

    def children(self, span_id: str) -> list[Span]:
        return [s for s in self.spans if s.parent_id == span_id]

    def tools(self) -> list[Span]:
        return [s for s in self.spans if s.kind == TOOL]

    def llms(self) -> list[Span]:
        return [s for s in self.spans if s.kind == LLM]
