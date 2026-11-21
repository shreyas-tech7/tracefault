"""Tune the thresholds on one seed, then measure precision and recall on another.

The bench sends every generated trace through a converter first: even traces go
through OTLP JSON, odd traces through JSON Lines. So the numbers cover the readers too.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import platform
import time
from collections import Counter
from pathlib import Path

from . import __version__
from .cluster import cluster
from .convert import parse_text, to_jsonl, to_otlp
from .detect import DEFAULTS, DETECTORS, scan, tuned_on_seed
from .generate import FAULTS, generate
from .model import Trace

TUNE_SEED = 1
GRID = {
    "tool_error_loop.min_errors": [2, 3, 4, 5],
    "repeated_calls.min_repeats": [2, 3, 4, 5],
    "context_overflow.near_ratio": [0.8, 0.85, 0.9, 0.95],
    "context_overflow.drop_ratio": [0.4, 0.5, 0.6, 0.7, 0.8],
    "wrong_tool.min_offtask": [1, 2, 3],
    "timeout.ratio": [0.9, 0.95, 1.0, 1.05],
    "budget_exhaustion.ratio": [0.9, 0.95, 1.0, 1.05],
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes in n trials."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    lo = 0.0 if k == 0 else max(0.0, c - h)
    hi = 1.0 if k == n else min(1.0, c + h)
    return (lo, hi)


def rate(k: int, n: int) -> dict:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "rate": k / n if n else 0.0, "lo": lo, "hi": hi}


def roundtrip(traces: list[Trace]) -> list[Trace]:
    out = []
    for i, t in enumerate(traces):
        if i % 2 == 0:
            out += parse_text(json.dumps(to_otlp([t])), "otlp", "otlp")
        else:
            out += parse_text(to_jsonl([t]), "jsonl", "jsonl")
    return out


def counts(traces: list[Trace], truth: dict, th: dict, only: str | None = None) -> dict:
    out = {}
    for k, fn in DETECTORS.items():
        if only and k != only:
            continue
        tp = fp = fn_ = 0
        for t in traces:
            hit, lab = bool(fn(t, th)), truth[t.trace_id] == k
            tp += hit and lab
            fp += hit and not lab
            fn_ += lab and not hit
        out[k] = {"tp": tp, "fp": fp, "fn": fn_}
    return out


def f1(c: dict) -> float:
    d = 2 * c["tp"] + c["fp"] + c["fn"]
    return 2 * c["tp"] / d if d else 0.0


def tune(seed: int = TUNE_SEED, n_per_fault: int = 150, n_clean: int = 400) -> dict:
    """Pick each threshold by F1 on its own failure type, one key at a time.
    A tie keeps the default."""
    traces, truth = generate(n_per_fault, n_clean, seed)
    th = dict(DEFAULTS)
    sweep = {}
    for key, values in GRID.items():
        kind = key.split(".")[0]
        scores = []
        for v in values:
            trial = dict(th, **{key: v})
            scores.append((round(f1(counts(traces, truth, trial, kind)[kind]), 6), v))
        best = max(s for s, _ in scores)
        pick = (
            th[key]
            if any(s == best and v == th[key] for s, v in scores)
            else next(v for s, v in scores if s == best)
        )
        th[key] = pick
        sweep[key] = {"values": values, "f1": [s for s, _ in scores], "picked": pick}
    return {"tune_seed": seed, "n_traces": len(traces), "thresholds": th, "sweep": sweep}


def _cpu() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def run_bench(
    seed: int, th: dict, n_per_fault: int = 150, n_clean: int = 400, tune_seed: int = TUNE_SEED
) -> dict:
    shipped = tuned_on_seed()
    if seed in (tune_seed, shipped):
        raise ValueError(f"seed {seed} was used for tuning, pick another bench seed")
    traces, truth = generate(n_per_fault, n_clean, seed)
    t0 = time.perf_counter()
    traces = roundtrip(traces)
    pairs, flagged = [], set()
    for t in traces:
        for f in scan(t, th):
            pairs.append((t, f))
            flagged.add(t.trace_id)
    clusters = cluster(pairs)
    secs = time.perf_counter() - t0
    c = counts(traces, truth, th)
    by_type = {}
    for k in FAULTS:
        x = c[k]
        by_type[k] = {
            **x,
            "precision": rate(x["tp"], x["tp"] + x["fp"]),
            "recall": rate(x["tp"], x["tp"] + x["fn"]),
        }
    clean = [t for t in traces if truth[t.trace_id] is None]
    faulty = [t for t in traces if truth[t.trace_id] is not None]
    # Purity: for each cluster, the share of its traces whose planted fault matches the
    # cluster's detector type. Weighted by cluster size.
    match = sum(sum(truth[i] == cl.type for i in cl.trace_ids) for cl in clusters)
    members = sum(cl.size for cl in clusters)
    return {
        "meta": {
            "tool": f"tracefault {__version__}",
            "date": dt.date.today().isoformat(),
            "seed": seed,
            "tune_seed": tune_seed,
            "model": "none (rule detectors, synthetic traces)",
            "traces": len(traces),
            "fault_traces": len(faulty),
            "clean_traces": len(clean),
            "fault_mix": dict(Counter(v for v in truth.values() if v)),
            "thresholds": th,
            "seconds": round(secs, 2),
            "cpu": _cpu(),
            "cores_used": 1,
            "cpus_allowed": len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "python": platform.python_version(),
            "cost_usd": 0.0,
        },
        "by_type": by_type,
        "clean_flagged": rate(sum(t.trace_id in flagged for t in clean), len(clean)),
        "faulty_flagged": rate(sum(t.trace_id in flagged for t in faulty), len(faulty)),
        "clusters": {"count": len(clusters), "findings": members, "purity": rate(match, members)},
    }


def write_json(path: str | Path, data: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
