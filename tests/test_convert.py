import json
from pathlib import Path

import pytest

from tracefault.convert import InputError, load, parse_text, to_jsonl, to_otlp
from tracefault.generate import generate

EX = Path(__file__).resolve().parents[1] / "examples"


def test_otel_and_jsonl_examples_give_the_same_model():
    """Broken case: a converter that drops or renames a field makes the two differ."""
    a = load(EX / "otel_genai.json")
    b = load(EX / "simple.jsonl")
    assert len(a) == len(b) == 1
    sa, sb = a[0].spans, b[0].spans
    assert len(sa) == len(sb) == 8
    for x, y in zip(sa, sb, strict=True):
        assert x.__dict__.keys() == y.__dict__.keys()
        for k in x.__dict__:
            if k in ("start", "end"):
                assert getattr(x, k) == pytest.approx(getattr(y, k), abs=1e-6)
            else:
                assert getattr(x, k) == getattr(y, k), k
    assert [s.kind for s in sa] == ["agent", "llm", "tool", "llm", "tool", "llm", "tool", "llm"]
    assert sa[2].error == "ConnectionError: upstream returned 503" and sa[2].tool_name == "get_weather"
    assert sa[1].input_tokens == 1200 and sa[0].attrs["tracefault.context_limit"] == 8192


@pytest.mark.parametrize("fmt", ["otlp", "jsonl"])
def test_round_trip_keeps_every_field(fmt):
    traces, _ = generate(2, 4, seed=3)
    text = json.dumps(to_otlp(traces)) if fmt == "otlp" else to_jsonl(traces)
    back = {t.trace_id: t for t in parse_text(text, fmt=fmt)}
    for t in traces:
        for x, y in zip(t.spans, back[t.trace_id].spans, strict=True):
            for k, v in x.__dict__.items():
                if k in ("start", "end"):
                    assert getattr(y, k) == pytest.approx(v, abs=1e-6)
                else:
                    assert getattr(y, k) == v, k


def test_collector_file_exporter_lines():
    """One OTLP document per line, as the collector file exporter writes it."""
    traces, _ = generate(1, 2, seed=4)
    text = "\n".join(json.dumps(to_otlp([t])) for t in traces)
    assert len(parse_text(text)) == len(traces)


@pytest.mark.parametrize(
    "text,msg",
    [
        ("{not json", "not valid JSON"),
        ('{"trace_id": "a", "span_id": "b", "start": 0}', "missing end"),
        ('{"trace_id": "a", "span_id": "b", "start": 0, "end": 1, "input_tokens": -5}', "negative"),
        ('{"trace_id": "a", "span_id": "b", "start": 0, "end": 1, "kind": "<script>"}', "unknown kind"),
        ('{"trace_id": "a", "span_id": "b", "start": "x", "end": 1}', "not a number"),
        ('{"resourceSpans": [{"scopeSpans": [{"spans": [{"traceId": "a"}]}]}]}', "missing spanId"),
        (
            '{"resourceSpans": [{"scopeSpans": [{"spans": [{"traceId": "a", "spanId": "b", '
            '"startTimeUnixNano": "1", "endTimeUnixNano": "2", "attributes": {}}]}]}]}',
            "attributes must be a list",
        ),
        ("[" * 100000, "not valid JSON"),
        ("[1, 2]", "not an object"),
    ],
)
def test_bad_input_raises_input_error(text, msg):
    """Traces are untrusted. Broken case: a crash with a traceback instead of a clear error."""
    with pytest.raises(InputError, match=msg):
        parse_text(text)


def test_long_text_is_capped():
    line = json.dumps({"trace_id": "a", "span_id": "b", "start": 0, "end": 1, "name": "x" * 10000})
    assert len(parse_text(line)[0].spans[0].name) == 4000


def test_unreadable_file(tmp_path):
    p = tmp_path / "bin.json"
    p.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(InputError, match="cannot read"):
        load(p)


def _line(**k):
    base = {"trace_id": "t", "span_id": "r", "kind": "agent", "name": "root", "start": 0, "end": 1}
    base.update(k)
    return json.dumps(base)


@pytest.mark.parametrize(
    "text",
    [
        _line()
        + "\n"
        + '{"trace_id": "t", "span_id": "a", "start": 0, "end": 1, "input_tokens": '
        + "9" * 5000
        + "}",
        _line(input_tokens=10**40),
        _line(start="NaN"),
        _line(end="Infinity"),
        _line(start=5, end=1),
        json.dumps({"resourceSpans": [{"scopeSpans": "x"}]}),
        json.dumps({"resourceSpans": [{"scopeSpans": [{"spans": {"a": 1}}]}]}),
        json.dumps(
            {
                "resourceSpans": [
                    {
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "t",
                                        "spanId": "s",
                                        "startTimeUnixNano": "9" * 400,
                                        "endTimeUnixNano": "9" * 400,
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ),
        json.dumps(
            {
                "resourceSpans": [
                    {
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "traceId": "t",
                                        "spanId": "s",
                                        "startTimeUnixNano": "1",
                                        "endTimeUnixNano": "2",
                                        "status": "bad",
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ),
    ],
    ids=[
        "huge-int",
        "huge-tokens",
        "nan-start",
        "inf-end",
        "end-before-start",
        "scopes-str",
        "spans-obj",
        "huge-time",
        "status-str",
    ],
)
def test_hostile_shapes_raise_input_error(text):
    """Broken case: a value that Python cannot hold as a float, or a wrong JSON shape,
    used to end in a traceback (exit 1, read by CI as findings) instead of exit 2."""
    with pytest.raises(InputError):
        parse_text(text)


def test_span_that_names_itself_as_parent_is_a_root():
    (t,) = parse_text(_line(parent_id="r"))
    assert t.root.parent_id is None and t.children("r") == []
