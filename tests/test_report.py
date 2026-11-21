import json
import re

from builders import TID, B

from tracefault.cluster import cluster
from tracefault.convert import parse_text, to_jsonl, to_otlp
from tracefault.detect import DEFAULTS, scan
from tracefault.metrics import measure
from tracefault.report import render

HOSTILE = [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(2)>',
    "</title><svg onload=alert(3)>",
    "javascript:alert(4)",
    "]]><!--",
]


def _hostile_trace():
    b = B()
    for i, h in enumerate(HOSTILE):
        b.llm().tool(name=h, error=f"{h} error {i}")
    t = b.build(root_error=HOSTILE[0])
    t.root.name = HOSTILE[1]
    return t


def _report(t):
    fs = scan(t, DEFAULTS)
    return render(
        [t], {t.trace_id: fs}, {t.trace_id: measure(t)}, cluster([(t, f) for f in fs]), title=HOSTILE[2]
    )


def test_report_escapes_all_trace_text():
    """Broken case: a span name or error message reaches the page as live HTML."""
    out = _report(_hostile_trace())
    assert "<script" not in out.lower()
    assert "<img" not in out.lower()
    assert "<svg onload" not in out.lower()
    assert not re.search(r"<[^>]*\bon\w+\s*=", out), "an event handler attribute reached the page"
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out
    assert "Content-Security-Policy" in out and "default-src &#x27;none&#x27;" not in out


def test_hostile_text_survives_both_converters():
    t = _hostile_trace()
    for text in (json.dumps(to_otlp([t])), to_jsonl([t])):
        back = parse_text(text)[0]
        out = _report(back)
        assert "<script" not in out.lower() and "<img" not in out.lower()


def test_report_has_waterfall_and_clusters():
    b = B()
    for _ in range(3):
        b.llm().tool(error="503")
    out = _report(b.build())
    assert out.count("<svg") == 1 and "<rect" in out and "Top failure clusters" in out
    assert TID in out
