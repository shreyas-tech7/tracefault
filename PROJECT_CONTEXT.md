# PROJECT_CONTEXT

## What it is

tracefault reads agent traces and finds the runs that went wrong and why: tool error loops,
identical repeated calls, context overflow, wrong tools, timeouts, blown budgets, calls to tools
that do not exist and handoffs that drop a required field. It groups the failures and writes a
static HTML report. `tracefault scan` exits 1 on a finding, so it works in CI.

## Status

v0.1.0-rc1 release candidate on branch `claude/project-thread-n3u3hh`. See PROGRESS.md.

## Stack

Python 3.11+, standard library only. pytest and ruff for development. No model in the loop.

## Commands

- `./init.sh`: venv, install, ruff, link check, all tests offline
- `tracefault scan FILES [--html r.html] [--json r.json] [--fail-on a,b]`
- `tracefault generate --out DIR --seed N`: traces with planted faults and truth.json
- `tracefault tune --write-thresholds`: pick thresholds on seed 1
- `tracefault bench --seed 2026 --out results/final-seed2026.json`: held-out numbers
- `tracefault readme [--check]`: write README number blocks and docs/index.html
- `tracefault demo`: generate, scan and report in a temp folder

## Layout

- `src/tracefault/model.py`: Span and Trace, pinned OTel version
- `src/tracefault/convert.py`: OTLP JSON and JSON Lines readers and writers
- `src/tracefault/generate.py`: seeded generator with planted faults
- `src/tracefault/detect.py`: eight rule detectors, `thresholds.json` next to it
- `src/tracefault/metrics.py`: cost, latency, critical path, retries
- `src/tracefault/cluster.py`: signature clustering
- `src/tracefault/report.py`: static HTML report with SVG waterfalls
- `src/tracefault/bench.py`: tuning and the benchmark
- `src/tracefault/readme.py`: README and docs/index.html generator
- `src/tracefault/cli.py`: the command line
- `results/`: tune, final and second-seed result files
- `examples/`: one trace in both formats
- `tests/`: offline tests, network guard in `conftest.py`

## Rules

- Every README number comes from `results/`. `tracefault readme` writes it.
- Final numbers use seed 2026. Tuning uses seed 1 only. The bench refuses the tuning seed.
- Traces are untrusted input: escape in HTML, strip control characters in the terminal.
- Tests run offline. Every subprocess has a timeout. Tests write only to temp folders.

## Skills that fit

superpowers TDD, systematic-debugging, verification-before-completion, requesting-code-review.

## Do not read

`.venv/`, `docs/build/BUILD_PROMPT.md` (unless you need the brief), `results/*.json` in full.
