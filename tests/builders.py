"""Small helpers that build hand-made traces for the detector tests."""

from tracefault.model import AGENT, LLM, TOOL, Span, Trace

TID = "t" * 32
CONF = {
    "tracefault.tools.allowed": ["get_weather", "geocode", "get_time", "check_status"],
    "gen_ai.tool.definitions": [
        {"type": "function", "name": n}
        for n in ["get_weather", "geocode", "get_time", "check_status", "book_flight"]
    ],
    "tracefault.context_limit": 8192,
    "tracefault.budget_tokens": 20000,
    "tracefault.timeout_s": 30.0,
}


class B:
    """Builds a trace step by step. Each call adds one span after the last one."""

    def __init__(self, conf=None, drop=()):
        c = dict(CONF if conf is None else conf)
        for k in drop:
            c.pop(k, None)
        self.t = 0.0
        self.n = 0
        self.root = Span(TID, "root", None, AGENT, "invoke_agent test_agent", 0.0, 0.0, attrs=c)
        self.spans = [self.root]

    def _id(self):
        self.n += 1
        return f"s{self.n:03d}"

    def llm(self, inp=1000, out=100, finish="tool_call", dur=1.0, parent="root"):
        s = Span(
            TID,
            self._id(),
            parent,
            LLM,
            "chat m",
            self.t,
            self.t + dur,
            inp,
            out,
            attrs={"gen_ai.response.finish_reasons": [finish]},
        )
        self.t += dur
        self.spans.append(s)
        return self

    def tool(self, name="get_weather", args='{"id": 1}', error=None, dur=0.5, error_type=None, parent="root"):
        a = {"gen_ai.tool.call.arguments": args}
        if error_type:
            a["error.type"] = error_type
        s = Span(
            TID,
            self._id(),
            parent,
            TOOL,
            f"execute_tool {name}",
            self.t,
            self.t + dur,
            error=error,
            tool_name=name,
            attrs=a,
        )
        self.t += dur
        self.spans.append(s)
        return self

    def span(self, s):
        self.spans.append(s)
        return self

    def build(self, root_error=None):
        self.root.end = self.t + 0.1
        self.root.error = root_error
        return Trace(TID, list(self.spans))


def clean():
    """A healthy run: three model calls, two different tool calls, all fine."""
    return B().llm().tool("geocode").llm().tool("get_weather").llm(finish="stop").build()
