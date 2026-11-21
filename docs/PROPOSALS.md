# Proposals

Ideas that the brief did not list. Shreyas picks what gets built.

- Embedding clustering with FastEmbed and a small model, as the brief's optional variant. Blocked here because huggingface.co was unreachable. Measure it against signature clustering by cluster purity before shipping it.
- A GitHub Action that runs `tracefault scan` on trace files in this repo and posts a summary comment in this repo (the brief's stretch item).
- Read traces from Langfuse or Phoenix exports, converted to the internal model.
- A span-level score next to the trace-level score, so a detector that fires on the wrong span gets caught.
- Feed traces from a real agent, for example NousResearch/hermes-agent, and label a small set by hand to get numbers on real failures.
- Multiple planted faults per trace, to measure how detectors interfere.
- A `--baseline` flag that ignores findings already present in an accepted baseline file, for CI on noisy agents.
