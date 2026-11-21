# Walkthrough

A tour of every file. Short sentences, one idea each.

## The big picture

tracefault reads trace files. A trace is the record of one agent run. It turns every file into one internal model. Then eight rules look for failures. Findings get grouped into clusters. A report page and an exit code come out at the end.

## Source code: `src/tracefault/`

- `__init__.py` holds the version number.
- `model.py` defines two classes. `Span` is one timed step. `Trace` is a list of spans that share a trace id. `Trace.conf` reads a setting from the root span. `OTEL_VERSION` records which version of the OpenTelemetry docs the field names follow.
- `convert.py` reads and writes the two formats. `spans_from_otlp` reads OTLP JSON. It maps `gen_ai.operation.name` to a span kind. It maps `gen_ai.usage.input_tokens` and `gen_ai.usage.output_tokens` to token counts. It maps a status code of 2 to an error. `span_from_jsonl` reads one JSON Lines span. `parse_text` picks the format. `load` reads a file and caps its size. `to_otlp` and `to_jsonl` write the formats back. Any bad input raises `InputError` with the file and line.
- `generate.py` makes fake traces with known faults. `generate` returns the traces and a truth map. The truth map says which fault each trace holds. The truth never goes inside a trace. `_add_clean_noise` adds harmless oddities to every trace. `_plant` adds one fault. `_render` turns a plan into spans with times and tokens.
- `detect.py` holds the eight rules. Each rule is one function. Each function reads the trace and a thresholds dict. Each returns a list of `Finding` objects. `scan` runs all eight. `load_thresholds` reads `thresholds.json`.
- `thresholds.json` stores the tuned thresholds and the seed they came from.
- `metrics.py` measures each trace. `critical_path` finds the chain of spans that set the end time. It walks back from the end and uses a stack, so a hostile trace cannot crash it. `retries` counts calls that repeat a tool right after it failed. `cost` multiplies tokens by a price table you supply.
- `cluster.py` groups findings. `normalize` lowercases error text and swaps numbers, ids and quoted values for placeholders. `ngram` takes the last three tool names before the failing span. `signature` joins the type, the text and the n-gram. `cluster` groups by signature.
- `report.py` writes the HTML page. `esc` escapes every string from a trace. `waterfall` draws one trace as an SVG timeline. `render` builds the whole page. The page has no script and a Content Security Policy that blocks scripts.
- `bench.py` measures the detectors. `tune` tries each threshold value on seed 1 and keeps the best F1. `run_bench` generates traces on another seed, sends them through the converters, runs the detectors and counts true and false positives. `wilson` computes the 95% interval.
- `readme.py` writes the number blocks in `README.md`, `docs/INTERVIEW_QA.md` and the page `docs/index.html`. It reads only the files in `results/`.
- `cli.py` is the command line. `cmd_scan` is the main command. It returns 0, 1 or 2. `clean` turns control characters into visible escapes before they reach the terminal.

## Tests: `tests/`

- `conftest.py` blocks every network connection except to localhost.
- `test_network_guard.py` proves that the guard works.
- `builders.py` builds small hand-made traces for the tests.
- `test_convert.py` checks that the OTel example and the JSON Lines example give the same model. It also feeds broken input.
- `test_detectors.py` checks each rule on a faulty trace, a clean trace and the threshold edge.
- `test_metrics.py` checks the critical path, retries and cost.
- `test_cluster.py` checks that the same failure shape lands in one cluster.
- `test_report.py` plants script tags and HTML in names and messages and checks the page.
- `test_cli.py` checks every exit code and the terminal escape.
- `test_bench.py` checks the interval math, the generator, the tuning seed and the held-out seed.
- `test_repo.py` checks the README order, the README numbers, the writing rules and the shipped files.

## Data and results

- `examples/otel_genai.json` is one trace written by hand in OTLP JSON.
- `examples/simple.jsonl` is the same trace in JSON Lines.
- `examples/demo-traces.jsonl` and `examples/demo-truth.json` are 20 generated traces and their truth.
- `results/tune-seed1.json` holds the tuning sweep.
- `results/final-seed2026.json` holds the held-out numbers.
- `results/second-seed7.json` holds the second check.

## Docs and repo files

- `README.md` explains the project. Its numbers come from `readme.py`.
- `docs/index.html` is a results page that opens from disk.
- `docs/report-example.html` is a real scan report of the demo traces.
- `docs/DEMO.md` is a real terminal session.
- `docs/INTERVIEW_QA.md` has questions and answers for interviews.
- `docs/HUMAN_STEPS.md` lists what only Shreyas can do.
- `docs/handoff/COWORK_PROMPT.md` is a prompt for Claude Cowork.
- `docs/build/BUILD_PROMPT.md` is the brief this repo was built from.
- `docs/PLAN.md`, `docs/TOOLING.md`, `docs/ENVIRONMENT.md` and `docs/RELEASE_CHECK.md` record how the build went.
- `scripts/check_links.py` checks every relative link.
- `scripts/make_social_preview.py` draws `docs/social-preview.png` with no image library.
- `init.sh` sets up and tests everything in one command.
- `.github/workflows/ci.yml` runs `init.sh` on every push. `bench.yml` runs the benchmark by hand.
- `PROGRESS.md`, `HANDOVER.md`, `DECISIONS.md`, `BLOCKERS.md` and `feature_list.json` are the build agent's memory.
