# Release check

Run on 2026-11-21 on branch `claude/project-thread-n3u3hh`.

| Step | Command | Result |
| --- | --- | --- |
| Code review (Ponytail rules, by hand) | read the branch diff | Found three detectors that crashed on odd attribute types. Fixed with `test_odd_attribute_values_never_crash`. No extra layers. Standard library only |
| Security audit | skipped | No sign-in, personal data or payments. Traces are treated as untrusted input and tested as such |
| Secret scan, full history | `gitleaks git -v .` | no leaks found |
| Dependency audit | `pip-audit -r (dev deps from the venv) --no-deps --disable-pip` | No known vulnerabilities found. The package has no runtime dependencies |
| Security lint | `ruff check --select S src scripts` | 1 finding, accepted: S311, the seeded `random.Random` in the generator. No crypto use |
| Workflow lint | `actionlint .github/workflows/*.yml` | clean |
| Links | `scripts/check_links.py` | 0 problems. External links listed as not checked |
| Humanizer rules (by hand) | `tests/test_repo.py::test_writing_rules` | README and docs pass: no em dashes, no dashes as punctuation, no semicolons in prose, no listed buzzwords |
| CI on GitHub | Actions run on the branch | green on Python 3.11 |
| Outside check | separate reviewer subagent, fresh clone, `./init.sh` | All seven Done-means items pass. The reviewer found nine weak spots with hostile input. All nine are fixed with tests: huge integers, numbers too large for a float, non-finite times, wrong OTLP shapes, end before start, a self parent, a handoff payload as an object, unhashable names, and a bench guard that trusted a flag. It also noted that control bytes reached the HTML and that the trade-off paragraph typed threshold values. Both are fixed. Both benchmark files have the same counts after the fixes |
| Clean tree and flags | `git status`, feature_list.json | clean, every flag matches a passing check |
