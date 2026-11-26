# Decisions

One line per choice: the options weighed and the reason.

- 2026-11-21 Name: `tracefault` (options tracefault, loopwatch). PyPI and npm both answer 404 for tracefault on 2026-11-21, and the repo already has that name.
- 2026-11-21 Branch: `claude/project-thread-n3u3hh` (options claude/build-tracefault from the brief, or the branch the session allows). The session only allows pushes to claude/project-thread-n3u3hh, and the brief says to use the allowed branch and log it.
- 2026-11-21 Checkout: the build session's existing clone (other option: a second clone). The session already cloned origin there with main at the README commit, so a second clone adds nothing.
- 2026-11-21 Stack: standard library only (options pydantic, opentelemetry-proto). The brief names only the standard library and pytest. JSON parsing needs nothing more.
- 2026-11-21 OTel pin: semantic-conventions-genai main branch docs fetched 2026-11-21 (gen-ai-spans.md sha256 d5903bcc..., gen-ai-agent-spans.md sha256 0d2db04d...). The GitHub API for that repo is closed to this session, so the commit SHA is not known. The date and file hashes stand in.
- 2026-11-21 Limits live in tracefault's own attributes (`tracefault.context_limit`, `tracefault.budget_tokens`, `tracefault.timeout_s`, `tracefault.tools.allowed`, `tracefault.handoff.*`) because the GenAI conventions define no limit attributes. Available tools come from the convention's `gen_ai.tool.definitions`.
- 2026-11-21 Trace-level scoring (options span level, trace level). A trace is positive for a type when the detector fires anywhere in it. The ground truth is one planted fault per trace, so trace level is the fair unit.
- 2026-11-21 Clean traces carry benign noise (retries, two polls, rare three polls, one exploratory call, slow calls, near-limit context, compaction, early length finish) and 15% of traces leave out one declared limit. Without noise, precision would be 100% by construction.
- 2026-11-21 Tuning: coordinate-wise grid search, one threshold at a time, by F1 on its own type, ties keep the default. Simple and easy to explain. Tuned on seed 1 with 1,600 traces.
- 2026-11-21 Held-out seed 2026 for the final numbers and seed 7 as a second check, because several detectors score near 100% and the brief says to rerun a result that looks too good.
- 2026-11-21 Cluster signature = detector type + normalized error text (or finding message) + last 3 tool names. Adding the type keeps a timeout and a loop with the same text apart.
- 2026-11-21 Embedding clustering: not shipped. FastEmbed downloads its model from huggingface.co, which the proxy refuses. The brief's fallback: ship signature clustering only and say so.
- 2026-11-21 Exit code 2 for an input with no spans (options 0 or 2). An empty file in CI more likely means a broken export than a healthy agent.
- 2026-11-21 The report holds no JavaScript and sets a Content Security Policy that blocks scripts, as a second guard behind escaping.
- 2026-11-21 Terminal output escapes control characters, because a hostile trace could hold ANSI escapes.
- 2026-11-21 Skills: install of third-party skills was denied by the permission system on the first try. The rules of ponytail, caveman and humanizer were followed by hand, as in the earlier builds.
- 2026-11-21 Hostile input exits 2, never a traceback (options: catch every exception at the top, or reject each bad shape in the readers). The readers reject each bad shape with a message, so a real bug still shows as a traceback in tests instead of hiding behind a catch-all.
- 2026-11-21 The bench refuses both the `--tune-seed` value and the seed recorded in `thresholds.json`, so a flag cannot sneak the tuning seed into the held-out numbers.
