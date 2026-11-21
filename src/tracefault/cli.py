"""Command line. `tracefault scan <files>` is the main command.

Exit codes:
  0  scan finished, no findings (or none of the types named in --fail-on)
  1  scan finished and found at least one failure
  2  usage error, or a trace file that cannot be read or parsed, or no spans at all
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from . import __version__
from .bench import TUNE_SEED, run_bench, tune, write_json
from .cluster import cluster
from .convert import InputError, load, to_jsonl, to_otlp
from .detect import DETECTORS, load_thresholds, scan
from .generate import generate
from .metrics import measure
from .report import render

OK, FOUND, ERROR = 0, 1, 2


def clean(text: object, limit: int = 300) -> str:
    """Trace text goes to a terminal. Control characters (such as ANSI escapes) are shown
    as escapes instead of being sent raw."""
    s = str(text)[:limit]
    return "".join(c if c.isprintable() else repr(c)[1:-1] for c in s)


def _json_file(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as e:
        raise InputError(f"{path}: cannot read JSON ({e.__class__.__name__})") from e
    if not isinstance(data, dict):
        raise InputError(f"{path}: must hold a JSON object")
    return data


def cmd_scan(a: argparse.Namespace) -> int:
    try:
        traces = []
        for f in a.files:
            traces += load(f, a.format)
        th = load_thresholds()
        th.update((_json_file(a.thresholds) or {}).get("thresholds", {}))
        prices = _json_file(a.prices)
    except InputError as e:
        print(f"tracefault: error: {clean(e)}", file=sys.stderr)
        return ERROR
    if not traces:
        print("tracefault: error: no spans found in the input", file=sys.stderr)
        return ERROR
    fail_on = set(a.fail_on.split(",")) if a.fail_on else set(DETECTORS)
    unknown = fail_on - set(DETECTORS)
    if unknown:
        print(f"tracefault: error: unknown type in --fail-on: {', '.join(sorted(unknown))}", file=sys.stderr)
        return ERROR
    findings, pairs, metrics = {}, [], {}
    for t in traces:
        fs = scan(t, th)
        findings[t.trace_id] = fs
        pairs += [(t, f) for f in fs]
        metrics[t.trace_id] = measure(t, prices)
    clusters = cluster(pairs)
    if not a.quiet:
        for f in (f for _, f in pairs):
            print(
                f"FAIL {f.type} trace={clean(f.trace_id, 64)} span={clean(f.span_id, 32)}: {clean(f.message)}"
            )
    failing = sum(1 for fs in findings.values() if fs)
    print(
        f"scanned {len(traces)} traces: {failing} with findings, {len(pairs)} findings in {len(clusters)} clusters"
    )
    for c in clusters[:5]:
        print(f"  {c.size:4d}  {clean(c.signature, 160)}")
    if a.html:
        Path(a.html).write_text(render(traces, findings, metrics, clusters, title=a.title), encoding="utf-8")
        print(f"wrote {a.html}")
    if a.json:
        out = {
            "version": __version__,
            "traces": len(traces),
            "findings": [f.__dict__ for _, f in pairs],
            "clusters": [{"signature": c.signature, "type": c.type, "traces": c.trace_ids} for c in clusters],
            "metrics": {k: m.__dict__ for k, m in metrics.items()},
        }
        Path(a.json).write_text(json.dumps(out, indent=2) + "\n")
        print(f"wrote {a.json}")
    return FOUND if any(f.type in fail_on for _, f in pairs) else OK


def cmd_generate(a: argparse.Namespace) -> int:
    traces, truth = generate(a.per_fault, a.clean, a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.format in ("otlp", "both"):
        (out / "traces.otlp.json").write_text(json.dumps(to_otlp(traces)) + "\n")
    if a.format in ("jsonl", "both"):
        (out / "traces.jsonl").write_text(to_jsonl(traces))
    write_json(out / "truth.json", {"seed": a.seed, "truth": truth})
    print(f"wrote {len(traces)} traces and truth.json to {out}")
    return OK


def cmd_tune(a: argparse.Namespace) -> int:
    res = tune(a.seed, a.per_fault, a.clean)
    write_json(a.out, res)
    if a.write_thresholds:
        write_json(
            Path(__file__).with_name("thresholds.json"),
            {"tuned_on_seed": a.seed, "thresholds": res["thresholds"]},
        )
    for k, v in res["thresholds"].items():
        print(f"{k} = {v}")
    return OK


def cmd_bench(a: argparse.Namespace) -> int:
    th = load_thresholds()
    try:
        res = run_bench(a.seed, th, a.per_fault, a.clean, a.tune_seed)
    except ValueError as e:
        print(f"tracefault: error: {e}", file=sys.stderr)
        return ERROR
    write_json(a.out, res)
    for k, v in res["by_type"].items():
        p, r = v["precision"], v["recall"]
        print(
            f"{k:18s} precision {p['rate']:.3f} ({p['lo']:.3f} to {p['hi']:.3f})  recall {r['rate']:.3f} ({r['lo']:.3f} to {r['hi']:.3f})"
        )
    print(f"wrote {a.out}")
    return OK


def cmd_readme(a: argparse.Namespace) -> int:
    from .readme import write

    root = Path(a.root)
    stale = write(root, check=a.check)
    if a.check and stale:
        print("out of date: " + ", ".join(stale), file=sys.stderr)
        return FOUND
    print("generated files are up to date" if a.check else "wrote README.md and docs/index.html")
    return OK


def cmd_demo(a: argparse.Namespace) -> int:
    out = Path(a.out or tempfile.mkdtemp(prefix="tracefault-demo-"))
    traces, _ = generate(2, 4, a.seed)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "demo.jsonl"
    path.write_text(to_jsonl(traces))
    print(f"demo: wrote {len(traces)} generated traces to {path}")
    ns = argparse.Namespace(
        files=[str(path)],
        format="auto",
        html=str(out / "report.html"),
        json=None,
        prices=None,
        thresholds=None,
        fail_on=None,
        quiet=False,
        title="tracefault demo report",
    )
    code = cmd_scan(ns)
    print(f"demo: scan exit code {code} (1 means failures were found, as planted)")
    return OK if code == FOUND else ERROR


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tracefault", description="Find failed agent runs in trace files.")
    p.add_argument("--version", action="version", version=f"tracefault {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan trace files, exit 1 on findings")
    s.add_argument("files", nargs="+")
    s.add_argument("--format", choices=["auto", "otlp", "jsonl"], default="auto")
    s.add_argument("--html", help="write the static HTML report here")
    s.add_argument("--json", help="write findings, clusters and metrics as JSON here")
    s.add_argument("--prices", help="JSON file: model name to [input, output] dollars per million tokens")
    s.add_argument("--thresholds", help="JSON file with a thresholds object to override the shipped values")
    s.add_argument("--fail-on", help="comma separated failure types that set exit code 1 (default: all)")
    s.add_argument("--title", default="tracefault report")
    s.add_argument("-q", "--quiet", action="store_true", help="print only the summary")
    s.set_defaults(fn=cmd_scan)

    g = sub.add_parser("generate", help="write seeded traces with planted failures and truth.json")
    g.add_argument("--out", required=True)
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--per-fault", type=int, default=10)
    g.add_argument("--clean", type=int, default=20)
    g.add_argument("--format", choices=["otlp", "jsonl", "both"], default="both")
    g.set_defaults(fn=cmd_generate)

    t = sub.add_parser("tune", help="pick thresholds by F1 on the tuning seed")
    t.add_argument("--seed", type=int, default=TUNE_SEED)
    t.add_argument("--per-fault", type=int, default=150)
    t.add_argument("--clean", type=int, default=400)
    t.add_argument("--out", default=f"results/tune-seed{TUNE_SEED}.json")
    t.add_argument("--write-thresholds", action="store_true")
    t.set_defaults(fn=cmd_tune)

    b = sub.add_parser("bench", help="precision and recall on a held-out seed")
    b.add_argument("--seed", type=int, default=2026)
    b.add_argument("--tune-seed", type=int, default=TUNE_SEED)
    b.add_argument("--per-fault", type=int, default=150)
    b.add_argument("--clean", type=int, default=400)
    b.add_argument("--out", required=True)
    b.set_defaults(fn=cmd_bench)

    r = sub.add_parser("readme", help="rewrite the README number blocks and docs/index.html")
    r.add_argument("--check", action="store_true", help="exit 1 if a generated file is out of date")
    r.add_argument("--root", default=".")
    r.set_defaults(fn=cmd_readme)

    d = sub.add_parser("demo", help="generate a few traces, scan them, write a report")
    d.add_argument("--out")
    d.add_argument("--seed", type=int, default=7)
    d.set_defaults(fn=cmd_demo)
    return p


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
