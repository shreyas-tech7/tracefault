# Plan

Made from Part 2 of `docs/build/BUILD_PROMPT.md`. The brief is the spec, so there was no question round. Assumptions are listed at the end and in DECISIONS.md.

**Goal:** an offline tool that reads agent traces, finds eight failure types with stated rule thresholds, clusters them, writes a static report and sets a CI exit code. A benchmark with planted failures measures each detector.

**Architecture:** read files, convert to one internal model, run detectors, cluster, compute metrics, write the report and set the exit code. One module per step under `src/tracefault/`.

## Tasks

1. Initializer: memory files, `init.sh`, network guard, LICENSE, `.gitignore`, `.env.example`, gitleaks hook. Test: `tests/test_network_guard.py`.
2. Model and converters (`model.py`, `convert.py`). Test first: the OTel example and the JSONL example give equal spans. Bad input raises `InputError`.
3. Generator (`generate.py`). Test first: same seed gives the same traces, truth stays outside the traces, clean traces stay inside their limits.
4. Detectors (`detect.py`), one at a time. For each: a failing test on a hand-built faulty trace, a quiet test on a clean trace, a boundary test at the threshold.
5. Metrics (`metrics.py`): critical path by walking back from the end, retries, cost from a price table. Test on a hand-built tree and on a hostile cycle.
6. Clustering (`cluster.py`): normalize text, take the last 3 tool names. Test that two traces with different ids land in one cluster.
7. Report (`report.py`): summary, clusters, SVG waterfalls. Test first: hostile names and messages never reach the page as markup.
8. CLI (`cli.py`): exit 0, 1, 2. Test each code and the console script.
9. Benchmark (`bench.py`): tune on seed 1, bench on seed 2026 and seed 7. README generator (`readme.py`) with a check mode and a test that compares README numbers to `results/`.
10. README, quality bar files, study-later kit, release check, hand-off.

## Assumptions

- A trace declares its limits on the root span with `tracefault.*` attributes. Without them some detectors fall back to error text or skip.
- One planted fault per faulty trace. Scoring is per trace.
- Cost per task means the cost of running tracefault, which is $0 because it calls no API.
