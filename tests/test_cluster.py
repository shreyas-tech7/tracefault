from builders import B

from tracefault.cluster import cluster, normalize
from tracefault.detect import DEFAULTS, scan


def test_normalize_removes_ids_and_numbers():
    a = normalize("ConnectionError: upstream returned 503 for request 7f3a9c21 'Austin'")
    b = normalize("connectionerror:   upstream returned 502 for request 99aa11bb 'Paris'")
    assert a == b == "connectionerror: upstream returned N for request X S"


def test_same_failure_shape_groups_together():
    """Broken case: two traces that fail the same way land in two clusters."""
    pairs = []
    for code in ("503", "504"):
        b = B()
        for _ in range(3):
            b.llm().tool(error=f"ConnectionError: upstream returned {code}")
        t = b.build()
        t.trace_id = code
        for s in t.spans:
            s.trace_id = code
        pairs += [(t, f) for f in scan(t, DEFAULTS)]
    cs = cluster(pairs)
    assert len(cs) == 1 and cs[0].size == 2 and cs[0].type == "tool_error_loop"
