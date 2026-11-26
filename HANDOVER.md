# Handover

## Done

- Model, converters (OTLP JSON and JSON Lines), seeded generator, eight detectors, metrics, clustering, HTML report, CLI with exit codes 0, 1 and 2.
- Thresholds tuned on seed 1. Held-out benchmark on seed 2026 and a second check on seed 7, rerun pinned to one core.
- README and docs/index.html written by `tracefault readme` from the results files.
- CI, quality bar files, study kit, hand-off docs and repo quality tests.
- Release check: gitleaks, pip-audit, ruff S, actionlint, link check, hand review, outside review. See docs/RELEASE_CHECK.md.
- Features F01 to F19 verified. F20 is the release check.

## Next

- Coordinator: open the PR, merge, create the v0.1.0-rc1 pre-release on the release commit in CHANGELOG.md, set the About box and topics.
- Shreyas: docs/HUMAN_STEPS.md.

## Open blockers

See BLOCKERS.md: skill installs denied, embedding clustering blocked (huggingface.co), OTel repo commit SHA not readable.

## Last ./init.sh

Passed on 2026-11-21 (all tests, ruff, format, link check). CI on GitHub passed on the branch.

## Exact commands to resume

```bash
cd tracefault   # the local clone of shreyas-tech7/tracefault
git fetch origin && git checkout claude/project-thread-n3u3hh
./init.sh
.venv/bin/tracefault readme --check
```
