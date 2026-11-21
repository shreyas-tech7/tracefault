# Interview questions and answers

Each answer points at the code and the results in this repo.

<!-- gen:qa -->
Numbers from `results/final-seed2026.json` (seed 2026, 2026-11-21):

- wrong tool recall: 93/150 = 62.0% (54.0 to 69.4), precision 93/96 = 96.9% (91.2 to 98.9)
- repeated calls precision: 150/168 = 89.3% (83.7 to 93.1)
- tool error loop precision: 150/154 = 97.4% (93.5 to 99.0)
- clean traces flagged by any detector: 6/400 = 1.5% (0.7 to 3.2)
- cluster purity: 1142/1172 = 97.4% (96.4 to 98.2) over 402 clusters
- time per trace: about 0.52 ms on one core
<!-- /gen:qa -->

**1. What does tracefault do, in one breath?**
It reads agent traces from files, runs eight rule detectors, groups the failures and writes a static report. `tracefault scan` exits 1 on a finding, so a CI job can fail on it (`src/tracefault/cli.py`, `cmd_scan`).

**2. What does each detector look for?**
All eight live in `src/tracefault/detect.py`. `tool_error_loop` counts tool errors in a row. `repeated_calls` counts identical successful calls. `context_overflow` looks for input near the context limit followed by truncation. `wrong_tool` counts calls to real tools that are off the task list. `timeout` compares a tool's duration with the declared timeout. `budget_exhaustion` sums tokens against the budget. `unknown_tool` checks calls against `gen_ai.tool.definitions`. `handoff_drop` checks a handoff payload for required fields.

**3. Why rules and not an LLM judge?**
The brief rules out an LLM in the loop. Rules are cheap, fast and repeatable. Each one has a threshold you can read and argue with. The cost per task is zero (the cost block in the README).

**4. How did you pick the thresholds?**
`tune` in `src/tracefault/bench.py` tries a small grid for each threshold on seed 1. It keeps the value with the best F1 for that failure type, and a tie keeps the default. The result is in `results/tune-seed1.json` and `src/tracefault/thresholds.json`.

**5. How do you know the thresholds did not overfit?**
The final numbers use seed 2026, which tuning never saw. `run_bench` refuses the tuning seed, and `test_bench_refuses_the_tuning_seed` proves it. A second seed, 7, gives a second check.

**6. Explain the precision and recall trade-off for alerts.**
A noisy alert gets muted, so precision matters. A missed failure costs you in production, so recall matters too. `wrong_tool` shows the trade. It waits for two off-task calls because clean runs sometimes make one exploratory call. That keeps precision high and costs recall (numbers at the top of this page). Setting it to one call would catch more and wake people for nothing more often.

**7. Why are traces untrusted input?**
A trace holds text that came from users, tools and models. A tool error can echo a web page. A prompt injection can put `<script>` in a span name. So `report.py` escapes every string with `esc`, the page holds no script, and its Content Security Policy blocks scripts. `test_report_escapes_all_trace_text` plants script tags and event handlers and checks the output. The terminal output goes through `clean` in `cli.py`, so ANSI escapes cannot rewrite the screen. The readers cap file size and text length and raise `InputError` on bad input.

**8. What does Development status mean for a standard?**
OpenTelemetry marks every `gen_ai.*` attribute as Development. That means names and meanings can change without a deprecation period. So `model.py` pins the version in `OTEL_VERSION`, and the README prints it. If the names move, the converter mapping in `convert.py` (`OP_TO_KIND` and `MAPPED`) is the one place to change.

**9. Why does a trace need declared limits?**
The conventions do not define a context limit, a token budget or a timeout. Without them, "near the limit" means nothing. tracefault reads its own `tracefault.*` attributes from the root span. When a limit is missing, the detector falls back to error text or skips. The generator leaves out one limit in a share of traces set by `MISSING_P` in `generate.py`, to measure that.

**10. How does the generator stop precision from being trivially perfect?**
Clean traces get benign noise in `_add_clean_noise`: a retry after an error, two status polls, rarely three, one exploratory call, slow calls in time, a context near the limit with no truncation. Those cases sit right next to the thresholds.

**11. How does clustering work?**
`signature` in `cluster.py` joins the failure type, the normalized error text and the last three tool names. `normalize` replaces numbers, hex ids and quoted values, so two runs that fail the same way with different ids share a signature. Purity against the planted truth is at the top of this page.

**12. What is the critical path and how do you compute it?**
It is the chain of spans that decided when the trace ended. `critical_path` in `metrics.py` walks back from the root's end: it takes the child that ended last, jumps to that child's start, takes the child that ended before that, and repeats inside each child. It uses a stack and a seen set, so a parent cycle or very deep nesting cannot hang it.

**13. What are the exit codes and why does 2 exist?**
0 means no findings. 1 means at least one finding. 2 means the input could not be used: a usage error, an unreadable file, bad JSON, or no spans at all. Keeping 2 apart from 1 lets CI tell "the agent failed" from "the export broke". `tests/test_cli.py` checks each code.

**14. What would you build next?**
Run it on real traces from a real agent and label a sample by hand, so the numbers stop depending on the generator. Then embedding clustering, measured by purity against signature clustering. Both are in `docs/PROPOSALS.md`.

**15. What are the limits of these numbers?**
The failures are planted by a generator written alongside the rules. The rules catch the faults as the generator plants them. Real traces can fail in other ways and in more than one way at once. The README says this above the table.
