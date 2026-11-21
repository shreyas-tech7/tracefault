# Changelog

## v0.1.0-rc1 (2026-11-21)

Release commit: to be filled in at hand-off.

- Converters for OTLP JSON with GenAI attributes and for JSON Lines, into one internal model.
- Seeded trace generator with eight planted failure types and ground truth.
- Eight rule detectors with stated thresholds, tuned on seed 1.
- Metrics per trace: tokens, cost from a price table, latency, critical path, retries.
- Signature clustering of failures.
- Static HTML report with inline SVG waterfalls. All trace text is escaped and the page holds no script.
- `tracefault scan` with exit codes 0, 1 and 2.
- Benchmark on held-out seed 2026 with precision and recall per type, plus a second seed.
