# Contributing

Thanks for helping. Keep changes small and plain.

1. Run `./init.sh` before and after your change. It must pass offline.
2. Write a test that fails first. Name the broken case in its docstring.
3. Never type a number into the README. Change the code, rerun the benchmark and run `tracefault readme`.
4. Never tune thresholds on the held-out seed. Tuning uses seed 1 only.
5. Treat traces as untrusted input. Escape every trace string that reaches HTML, and strip control characters before the terminal.
6. Use synthetic traces in issues and tests. Do not paste traces with private data.
7. New ideas go in `docs/PROPOSALS.md` first.

The secret scan runs as a pre-commit hook: `pre-commit install` once, then commit as usual.
