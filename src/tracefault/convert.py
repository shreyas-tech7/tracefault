"""Read and write the two input formats.

1. OTLP JSON: the JSON form of an OpenTelemetry trace export (`resourceSpans`), with
   GenAI attributes such as `gen_ai.operation.name` and `gen_ai.usage.input_tokens`.
   A file can hold one export document, or one document per line (the collector file
   exporter writes that).
2. JSON Lines: one span per line, with the internal field names.

Traces are untrusted input. Bad input raises `InputError` with the file and line.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .model import AGENT, KINDS, LLM, OTHER, TOOL, Span, Trace

MAX_BYTES = 200 * 1024 * 1024
MAX_TEXT = 4000
MAX_INT = 2**63 - 1

OP_TO_KIND = {
    "chat": LLM,
    "text_completion": LLM,
    "generate_content": LLM,
    "embeddings": LLM,
    "execute_tool": TOOL,
    "invoke_agent": AGENT,
    "create_agent": AGENT,
    "invoke_workflow": AGENT,
}
KIND_TO_OP = {LLM: "chat", TOOL: "execute_tool", AGENT: "invoke_agent"}
MAPPED = {
    "gen_ai.operation.name",
    "gen_ai.usage.input_tokens",
    "gen_ai.usage.output_tokens",
    "gen_ai.tool.name",
}
STATUS_ERROR = (2, "2", "STATUS_CODE_ERROR")


class InputError(ValueError):
    """A trace file that tracefault cannot read."""


def _text(v: Any) -> str:
    return str(v)[:MAX_TEXT]


def _int(v: Any, where: str) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError) as e:
        raise InputError(f"{where}: not a whole number: {_text(v)[:60]!r}") from e
    if n < 0:
        raise InputError(f"{where}: negative number {n}")
    if n > MAX_INT:
        raise InputError(f"{where}: number too large")
    return n


def _float(v: Any, where: str) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError) as e:
        raise InputError(f"{where}: not a number: {_text(v)[:60]!r}") from e
    if not math.isfinite(x):
        raise InputError(f"{where}: number is not finite: {_text(v)[:60]!r}")
    return x


# OTLP attribute values ------------------------------------------------------


def _value(v: dict) -> Any:
    if not isinstance(v, dict):
        return v
    if "stringValue" in v:
        return v["stringValue"]
    if "boolValue" in v:
        return bool(v["boolValue"])
    if "intValue" in v:
        return int(v["intValue"])
    if "doubleValue" in v:
        return float(v["doubleValue"])
    if "arrayValue" in v:
        return [_value(x) for x in v["arrayValue"].get("values", [])]
    if "kvlistValue" in v:
        return {kv["key"]: _value(kv.get("value", {})) for kv in v["kvlistValue"].get("values", [])}
    return None


def _otlp_value(x: Any) -> dict:
    if isinstance(x, bool):
        return {"boolValue": x}
    if isinstance(x, int):
        return {"intValue": str(x)}
    if isinstance(x, float):
        return {"doubleValue": x}
    if isinstance(x, list):
        return {"arrayValue": {"values": [_otlp_value(i) for i in x]}}
    if isinstance(x, dict):
        return {"kvlistValue": {"values": [{"key": k, "value": _otlp_value(v)} for k, v in x.items()]}}
    return {"stringValue": str(x)}


def _attrs(items: Any, where: str) -> dict[str, Any]:
    if not isinstance(items, list):
        raise InputError(f"{where}: attributes must be a list")
    out = {}
    for kv in items:
        if not isinstance(kv, dict) or "key" not in kv:
            raise InputError(f"{where}: attribute without a key")
        try:
            out[str(kv["key"])] = _value(kv.get("value", {}))
        except (TypeError, ValueError, KeyError, AttributeError, OverflowError) as e:
            raise InputError(f"{where}: bad value for attribute {kv['key']!r}") from e
    return out


def _list(x: Any, where: str) -> list:
    if x is None:
        return []
    if not isinstance(x, list):
        raise InputError(f"{where} must be a list")
    return x


def _span(**kw: Any) -> Span:
    """Build a span and check what every reader needs: end not before start, and a
    span that names itself as parent is treated as a root."""
    if kw["end"] < kw["start"]:
        raise InputError(f"{kw.pop('where')}: span ends before it starts")
    kw.pop("where")
    if kw["parent_id"] == kw["span_id"]:
        kw["parent_id"] = None
    return Span(**kw)


def spans_from_otlp(doc: dict, where: str = "otlp") -> list[Span]:
    if not isinstance(doc, dict) or not isinstance(doc.get("resourceSpans"), list):
        raise InputError(f"{where}: no resourceSpans list")
    spans = []
    for rs in doc["resourceSpans"]:
        scopes = _list(rs.get("scopeSpans") if isinstance(rs, dict) else None, f"{where}: scopeSpans")
        for ss in scopes:
            raws = _list(ss.get("spans") if isinstance(ss, dict) else None, f"{where}: spans")
            for i, raw in enumerate(raws):
                w = f"{where} span {i}"
                if not isinstance(raw, dict):
                    raise InputError(f"{w}: not an object")
                for k in ("traceId", "spanId", "startTimeUnixNano", "endTimeUnixNano"):
                    if k not in raw:
                        raise InputError(f"{w}: missing {k}")
                a = _attrs(raw.get("attributes", []), w)
                status = raw.get("status") or {}
                if not isinstance(status, dict):
                    raise InputError(f"{w}: status must be an object")
                error = None
                if status.get("code") in STATUS_ERROR:
                    error = _text(status.get("message") or a.get("error.type") or "error")
                elif "error.type" in a:
                    error = _text(a["error.type"])
                spans.append(
                    _span(
                        where=w,
                        trace_id=_text(raw["traceId"]),
                        span_id=_text(raw["spanId"]),
                        parent_id=_text(raw["parentSpanId"]) if raw.get("parentSpanId") else None,
                        kind=OP_TO_KIND.get(str(a.get("gen_ai.operation.name", "")), OTHER),
                        name=_text(raw.get("name", "")),
                        start=_int(raw["startTimeUnixNano"], w) / 1e9,
                        end=_int(raw["endTimeUnixNano"], w) / 1e9,
                        input_tokens=_int(a.get("gen_ai.usage.input_tokens", 0), w),
                        output_tokens=_int(a.get("gen_ai.usage.output_tokens", 0), w),
                        error=error,
                        tool_name=_text(a["gen_ai.tool.name"]) if "gen_ai.tool.name" in a else None,
                        attrs={k: v for k, v in a.items() if k not in MAPPED},
                    )
                )
    return spans


def span_from_jsonl(obj: dict, where: str) -> Span:
    if not isinstance(obj, dict):
        raise InputError(f"{where}: not an object")
    for k in ("trace_id", "span_id", "start", "end"):
        if k not in obj:
            raise InputError(f"{where}: missing {k}")
    kind = obj.get("kind", OTHER)
    if kind not in KINDS:
        raise InputError(f"{where}: unknown kind {_text(kind)[:40]!r}")
    attrs = obj.get("attrs", {})
    if not isinstance(attrs, dict):
        raise InputError(f"{where}: attrs must be an object")
    err = obj.get("error")
    return _span(
        where=where,
        trace_id=_text(obj["trace_id"]),
        span_id=_text(obj["span_id"]),
        parent_id=_text(obj["parent_id"]) if obj.get("parent_id") else None,
        kind=kind,
        name=_text(obj.get("name", "")),
        start=_float(obj["start"], where),
        end=_float(obj["end"], where),
        input_tokens=_int(obj.get("input_tokens", 0), where),
        output_tokens=_int(obj.get("output_tokens", 0), where),
        error=_text(err) if err not in (None, "") else None,
        tool_name=_text(obj["tool"]) if obj.get("tool") else None,
        attrs={str(k): v for k, v in attrs.items()},
    )


def group(spans: list[Span]) -> list[Trace]:
    by = defaultdict(list)
    for s in spans:
        by[s.trace_id].append(s)
    return [Trace(tid, ss) for tid, ss in by.items()]


def parse_text(text: str, where: str = "input", fmt: str = "auto") -> list[Trace]:
    """Parse the text of one trace file. `fmt` is `auto`, `otlp` or `jsonl`."""
    stripped = text.strip()
    if not stripped:
        return []
    if fmt in ("auto", "otlp"):
        try:
            doc = json.loads(stripped)
        except (ValueError, RecursionError):
            doc = None
        if isinstance(doc, dict) and "resourceSpans" in doc:
            return group(spans_from_otlp(doc, where))
        if fmt == "otlp" and doc is None and "\n" not in stripped:
            raise InputError(f"{where}: not valid JSON")
    spans = []
    for n, line in enumerate(stripped.splitlines(), 1):
        if not line.strip():
            continue
        w = f"{where}:{n}"
        try:
            obj = json.loads(line)
        except (ValueError, RecursionError) as e:
            raise InputError(f"{w}: not valid JSON") from e
        if isinstance(obj, dict) and "resourceSpans" in obj:
            spans += spans_from_otlp(obj, w)
        elif fmt == "otlp":
            raise InputError(f"{w}: no resourceSpans list")
        else:
            spans.append(span_from_jsonl(obj, w))
    return group(spans)


def load(path: str | Path, fmt: str = "auto") -> list[Trace]:
    p = Path(path)
    try:
        if p.stat().st_size > MAX_BYTES:
            raise InputError(f"{p}: larger than {MAX_BYTES // 2**20} MB")
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise InputError(f"{p}: cannot read ({e.__class__.__name__})") from e
    return parse_text(text, str(p), fmt)


# Writers ---------------------------------------------------------------------


def to_otlp(traces: list[Trace]) -> dict:
    out = []
    for t in traces:
        for s in t.spans:
            a = dict(s.attrs)
            if s.kind in KIND_TO_OP:
                a["gen_ai.operation.name"] = KIND_TO_OP[s.kind]
            if s.input_tokens:
                a["gen_ai.usage.input_tokens"] = s.input_tokens
            if s.output_tokens:
                a["gen_ai.usage.output_tokens"] = s.output_tokens
            if s.tool_name:
                a["gen_ai.tool.name"] = s.tool_name
            raw = {
                "traceId": s.trace_id,
                "spanId": s.span_id,
                "name": s.name,
                "kind": 3 if s.kind in (LLM, TOOL) else 1,
                "startTimeUnixNano": str(round(s.start * 1e9)),
                "endTimeUnixNano": str(round(s.end * 1e9)),
                "attributes": [{"key": k, "value": _otlp_value(v)} for k, v in a.items()],
                "status": {"code": 2, "message": s.error} if s.error else {"code": 1},
            }
            if s.parent_id:
                raw["parentSpanId"] = s.parent_id
            out.append(raw)
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "tracefault"}}]},
                "scopeSpans": [{"scope": {"name": "tracefault.generator"}, "spans": out}],
            }
        ]
    }


def to_jsonl(traces: list[Trace]) -> str:
    lines = []
    for t in traces:
        for s in t.spans:
            obj = {
                "trace_id": s.trace_id,
                "span_id": s.span_id,
                "parent_id": s.parent_id,
                "kind": s.kind,
                "name": s.name,
                "start": s.start,
                "end": s.end,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
                "error": s.error,
                "tool": s.tool_name,
                "attrs": s.attrs,
            }
            lines.append(json.dumps(obj, sort_keys=True))
    return "\n".join(lines) + "\n"
