"""The static HTML report: a summary table, the top failure clusters and a waterfall for
each failing trace, drawn as inline SVG.

Trace text is untrusted. Every string from a trace goes through `esc` before it reaches
the page, in HTML text, in attributes and in SVG. The page holds no script at all, and
its Content Security Policy blocks scripts, so a missed escape still cannot run code.
"""

from __future__ import annotations

import html
from collections import Counter

from .cluster import Cluster
from .detect import DETECTORS, Finding
from .metrics import TraceMetrics, critical_path
from .model import AGENT, LLM, TOOL, Trace

CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src 'none'"
COLORS = {AGENT: "#8250df", LLM: "#0969da", TOOL: "#1a7f37"}
W, ROW, LEFT = 900, 18, 260


def esc(x: object, limit: int = 300) -> str:
    s = str(x)
    if len(s) > limit:
        s = s[:limit] + "..."
    return html.escape(s, quote=True)


def waterfall(t: Trace, crit: set[str] | None = None) -> str:
    spans = t.spans[:200]
    t0 = min(s.start for s in spans)
    total = max(max(s.end for s in spans) - t0, 1e-9)
    depth = {}
    ids = {s.span_id: s for s in spans}
    for s in spans:
        d, p, hops = 0, s.parent_id, 0
        while p in ids and hops < 50:
            d, p, hops = d + 1, ids[p].parent_id, hops + 1
        depth[s.span_id] = d
    h = ROW * len(spans) + 24
    out = [
        f'<svg class="wf" viewBox="0 0 {W + LEFT} {h}" width="100%" role="img" '
        f'aria-label="waterfall of trace {esc(t.trace_id)}">'
    ]
    for i, s in enumerate(spans):
        y = 4 + i * ROW
        x = LEFT + (s.start - t0) / total * W
        w = max(1.5, s.duration / total * W)
        color = COLORS.get(s.kind, "#6e7781")
        stroke = ' stroke="#cf222e" stroke-width="2"' if s.error else ""
        bold = ' font-weight="bold"' if crit and s.span_id in crit else ""
        label = esc(("  " * depth[s.span_id]) + s.name, 40)
        tip = esc(f"{s.name} {s.duration:.2f} s" + (f" error: {s.error}" if s.error else ""))
        out.append(
            f'<g><title>{tip}</title><text x="4" y="{y + 12}" font-size="11"{bold} xml:space="preserve">{label}</text>'
            f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{ROW - 5}" fill="{color}"{stroke}/></g>'
        )
    out.append(
        f'<text x="{LEFT}" y="{h - 4}" font-size="11">0 s</text>'
        f'<text x="{LEFT + W - 60}" y="{h - 4}" font-size="11">{total:.1f} s</text></svg>'
    )
    if len(t.spans) > len(spans):
        out.append(f"<p>Showing the first {len(spans)} of {len(t.spans)} spans.</p>")
    return "".join(out)


def _table(head: list[str], rows: list[list[object]]) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="wrap"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


def render(
    traces: list[Trace],
    findings: dict[str, list[Finding]],
    metrics: dict[str, TraceMetrics],
    clusters: list[Cluster],
    title: str = "tracefault report",
    max_traces: int = 50,
) -> str:
    failing = [t for t in traces if findings.get(t.trace_id)]
    by_type = Counter(f.type for fs in findings.values() for f in fs)
    summary = [["traces scanned", len(traces)], ["traces with findings", len(failing)]]
    summary += [[k, by_type.get(k, 0)] for k in DETECTORS]
    crows = [[c.size, c.type, c.signature] for c in clusters[:10]]
    parts = [
        "<h2>Summary</h2>",
        _table(["what", "count"], summary),
        "<h2>Top failure clusters</h2>",
        _table(["traces", "type", "signature"], crows) if crows else "<p>No failures found.</p>",
        "<h2>Failing traces</h2>",
    ]
    for t in failing[:max_traces]:
        m = metrics[t.trace_id]
        crit = {s.span_id for s in critical_path(t)}
        parts.append(f"<section><h3>Trace <code>{esc(t.trace_id, 80)}</code></h3>")
        parts.append(
            "<ul>"
            + "".join(f"<li><b>{esc(f.type)}</b>: {esc(f.message)}</li>" for f in findings[t.trace_id])
            + "</ul>"
        )
        cost = "n/a" if m.cost_usd is None else f"${m.cost_usd:.4f}"
        parts.append(
            f"<p>{m.spans} spans, {m.errors} errors, {m.retries} retries, "
            f"{m.input_tokens + m.output_tokens} tokens, cost {esc(cost)}, latency {m.latency_s:.2f} s, "
            f"critical path {len(m.critical_path)} spans covering {m.critical_path_s:.2f} s (bold labels).</p>"
        )
        parts.append(waterfall(t, crit) + "</section>")
    if len(failing) > max_traces:
        parts.append(f"<p>{len(failing) - max_traces} more failing traces are not drawn.</p>")
    legend = " ".join(f'<span style="color:{c}">&#9632; {esc(k)}</span>' for k, c in COLORS.items())
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
:root {{ --bg: #ffffff; --fg: #1f2328; --muted: #59636e; --line: #d1d9e0; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #0d1117; --fg: #e6edf3; --muted: #9aa4ae; --line: #30363d; }} }}
body {{ background: var(--bg); color: var(--fg); font: 15px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 1200px; padding: 24px 16px; }}
.wrap {{ overflow-x: auto; }} table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ border-bottom: 1px solid var(--line); padding: 6px; text-align: left; vertical-align: top; word-break: break-word; }}
svg.wf text {{ fill: var(--fg); font-family: ui-monospace, monospace; }} p {{ color: var(--muted); }}
section {{ border-top: 1px solid var(--line); margin-top: 16px; }}
</style>
</head>
<body>
<h1>{esc(title)}</h1>
<p>Static report. No script runs on this page. Legend: {legend}, red outline = error.</p>
{"".join(parts)}
</body>
</html>
"""
