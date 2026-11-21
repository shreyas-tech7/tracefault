from builders import TID, B

from tracefault.metrics import cost, critical_path, measure, retries
from tracefault.model import AGENT, LLM, Span, Trace


def test_critical_path_follows_the_blocking_chain():
    """Root has two parallel children. The one that ends last is on the path. Inside it,
    the grandchild that ends last is on the path."""
    spans = [
        Span(TID, "r", None, AGENT, "root", 0, 10),
        Span(TID, "a", "r", LLM, "short", 0, 3),
        Span(TID, "b", "r", AGENT, "long", 1, 9),
        Span(TID, "b1", "b", LLM, "b first", 1, 4),
        Span(TID, "b2", "b", LLM, "b last", 4, 9),
    ]
    names = [s.name for s in critical_path(Trace(TID, spans))]
    assert names == ["root", "long", "b first", "b last"]


def test_critical_path_survives_cycles_and_deep_nesting():
    """Broken case: a hostile trace with a parent cycle or 5,000 levels hangs or overflows."""
    spans = [Span(TID, "r", None, AGENT, "root", 0, 10)]
    spans += [Span(TID, f"n{i}", "r" if i == 0 else f"n{i - 1}", LLM, "x", 0, 10) for i in range(5000)]
    spans += [Span(TID, "c1", "c2", LLM, "c", 0, 1), Span(TID, "c2", "c1", LLM, "c", 0, 1)]
    path = critical_path(Trace(TID, spans))
    assert len(path) == 5001


def test_retries_and_metrics():
    t = B().llm().tool(error="503").tool().tool("geocode").build()
    assert retries(t) == 1
    m = measure(t)
    assert (m.errors, m.retries, m.input_tokens, m.output_tokens) == (1, 1, 1000, 100)
    assert m.cost_usd is None
    assert m.latency_s == round(t.root.end - t.root.start, 3)


def test_cost_from_price_table():
    t = B().llm(inp=1_000_000, out=0).build()
    t.root.attrs["gen_ai.request.model"] = "m1"
    assert cost(t, {"m1": [0.5, 2.0]}) == 0.5
    assert cost(t, {"other": [1, 1]}) is None
