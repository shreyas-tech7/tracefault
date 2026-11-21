"""Write the README number blocks and docs/index.html from the results files.

Nobody types a number into the README. Each block sits between `<!-- gen:NAME -->` and
`<!-- /gen:NAME -->`, and this module rewrites it.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from .model import OTEL_VERSION

FINAL = "results/final-seed2026.json"
SECOND = "results/second-seed7.json"
TUNE = "results/tune-seed1.json"
BLOCK = re.compile(r"(<!-- gen:(\w+) -->\n)(.*?)(<!-- /gen:\2 -->)", re.S)
LABELS = {
    "tool_error_loop": "tool error loop",
    "repeated_calls": "identical repeated calls",
    "context_overflow": "context overflow",
    "wrong_tool": "wrong tool for the task",
    "timeout": "timeout",
    "budget_exhaustion": "budget exhaustion",
    "unknown_tool": "call to a tool that does not exist",
    "handoff_drop": "handoff drops a required field",
}
RULES = {
    "tool_error_loop": "{tool_error_loop.min_errors:g} or more tool errors in a row",
    "repeated_calls": "one tool gets the same arguments {repeated_calls.min_repeats:g} or more times, all successful",
    "context_overflow": "model input at {context_overflow.near_ratio:g} of the limit or more, then a `length` finish or the next input under {context_overflow.drop_ratio:g} of it",
    "wrong_tool": "{wrong_tool.min_offtask:g} or more calls to known tools outside the task list",
    "timeout": "a tool call lasts {timeout.ratio:g} times the timeout or longer, or `error.type` is `timeout`",
    "budget_exhaustion": "tokens reach {budget_exhaustion.ratio:g} times the budget",
    "unknown_tool": "one call to a tool missing from `gen_ai.tool.definitions`",
    "handoff_drop": "one required field missing, null or empty in the handoff payload",
}
HEAD = ["Failure (planted by the generator)", "Precision, 95% CI", "Recall, 95% CI", "TP / FP / FN"]


def pct(r: dict) -> str:
    return f"{r['k']}/{r['n']} = {100 * r['rate']:.1f}% ({100 * r['lo']:.1f} to {100 * r['hi']:.1f})"


def _load(root: Path, rel: str) -> dict:
    return json.loads((root / rel).read_text())


def rows(res: dict) -> list[list[str]]:
    out = []
    for k, label in LABELS.items():
        t = res["by_type"][k]
        out.append([label, pct(t["precision"]), pct(t["recall"]), f"{t['tp']} / {t['fp']} / {t['fn']}"])
    return out


def blocks(root: Path) -> dict[str, str]:
    final, second, tune = _load(root, FINAL), _load(root, SECOND), _load(root, TUNE)
    m = final["meta"]
    table = ["| " + " | ".join(HEAD) + " |", "| " + " | ".join(["---"] * len(HEAD)) + " |"]
    table += ["| " + " | ".join(r) + " |" for r in rows(final)]
    s2 = []
    for k, label in LABELS.items():
        t = second["by_type"][k]
        s2.append(f"| {label} | {pct(t['precision'])} | {pct(t['recall'])} |")
    results = "\n".join(
        [
            f"Run of {m['date']}, model: {m['model']}, held-out seed {m['seed']}, file `{FINAL}`.",
            f"{m['traces']} traces: {m['fault_traces']} with one planted failure ({m['fault_traces'] // len(LABELS)} per type) "
            f"and {m['clean_traces']} clean. Thresholds were tuned on seed {m['tune_seed']} only (`{TUNE}`).",
            "",
            *table,
            "",
            f"Clean traces flagged by any detector: {pct(final['clean_flagged'])}.",
            f"Faulty traces flagged by any detector: {pct(final['faulty_flagged'])}.",
            f"Clustering put {final['clusters']['findings']} findings into {final['clusters']['count']} signature clusters. "
            f"Cluster purity (the share of a cluster's traces whose planted failure matches the cluster's type): {pct(final['clusters']['purity'])}.",
            "",
            f"Second check on seed {second['meta']['seed']} (file `{SECOND}`), because several rows sit near 100%:",
            "",
            "| Failure | Precision, 95% CI | Recall, 95% CI |",
            "| --- | --- | --- |",
            *s2,
            "",
            "Intervals are Wilson 95% score intervals over traces. A trace counts for a type when that detector fires anywhere in it.",
        ]
    )
    th = m["thresholds"]
    rules = ["| Detector | Fires when | Threshold source |", "| --- | --- | --- |"]
    for k, rule in RULES.items():
        txt = rule
        for key, v in th.items():
            txt = txt.replace("{" + key + ":g}", f"{v:g}")
        src = (
            f"tuned on seed {m['tune_seed']}"
            if any(x.startswith(k) for x in tune["thresholds"])
            else "fixed (one event)"
        )
        rules.append(f"| `{k}` | {txt} | {src} |")
    per = 1000 * m["seconds"] / m["traces"]
    cost = "\n".join(
        [
            f"Cost per task: ${m['cost_usd']:.2f}. tracefault calls no model and no API.",
            f"The held-out bench ({m['traces']} traces, both converters, eight detectors and clustering) took "
            f"{m['seconds']} s on {m['cores_used']} core of an {m['cpu']}, Python {m['python']}, on {m['date']}. "
            f"That is about {per:.2f} ms per trace.",
        ]
    )
    status = (
        f"**Status:** v0.1.0-rc1 release candidate. Numbers come from `{FINAL}` "
        f"({m['date']}, {m['model']}, seed {m['seed']})."
    )
    otel = f"Field names are pinned to: {OTEL_VERSION}"
    return {"status": status, "results": results, "cost": cost, "rules": "\n".join(rules), "otel": otel}


def render_readme(text: str, gen: dict[str, str]) -> str:
    def sub(mo):
        name = mo.group(2)
        if name not in gen:
            return mo.group(0)
        return f"{mo.group(1)}{gen[name]}\n{mo.group(4)}"

    return BLOCK.sub(sub, text)


def render_html(root: Path) -> str:
    final = _load(root, FINAL)
    gen = blocks(root)
    m = final["meta"]
    head = "".join(f"<th>{html.escape(h)}</th>" for h in HEAD)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>" for r in rows(final))
    clean = html.escape(pct(final["clean_flagged"]))
    cost = html.escape(gen["cost"].replace("\n", " "))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'self'">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>tracefault results</title>
<style>
:root {{ --bg: #ffffff; --fg: #1f2328; --muted: #59636e; --line: #d1d9e0; --accent: #0969da; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg: #0d1117; --fg: #e6edf3; --muted: #9aa4ae; --line: #30363d; --accent: #6ea8ff; }} }}
body {{ background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif; margin: 0 auto; max-width: 1100px; padding: 24px 16px; }}
p {{ color: var(--muted); }} a {{ color: var(--accent); }}
.wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
th, td {{ border-bottom: 1px solid var(--line); padding: 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--accent); }}
</style>
</head>
<body>
<h1>tracefault results</h1>
<p>Held-out seed {m["seed"]}, run of {html.escape(m["date"])}, {html.escape(m["model"])}. {m["traces"]} traces. The failures are planted by a generator. Real traces can fail in other ways.</p>
<div class="wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>
<p>Clean traces flagged by any detector: {clean}.</p>
<p>{cost}</p>
<p>An example scan report from the demo traces: <a href="report-example.html">report-example.html</a>.</p>
</body>
</html>
"""


def write(root: Path, check: bool = False) -> list[str]:
    """Rewrite the generated files. With check=True, write nothing and return the stale ones."""
    stale = []
    gen = blocks(root)
    readme = root / "README.md"
    new = render_readme(readme.read_text(), gen)
    targets = {readme: new, root / "docs" / "index.html": render_html(root)}
    for path, text in targets.items():
        old = path.read_text() if path.exists() else ""
        if old != text:
            stale.append(str(path.relative_to(root)))
            if not check:
                path.write_text(text)
    found = {mo.group(2) for mo in BLOCK.finditer(new)}
    missing = set(BLOCK_NAMES) - found
    if missing:
        stale += [f"README.md block {n} missing" for n in sorted(missing)]
    return stale


BLOCK_NAMES = ("status", "results", "cost", "rules", "otel")
