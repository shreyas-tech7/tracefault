# Human steps

Only Shreyas can do these. Do them in order.

Release commit: RELEASE_SHA on branch `claude/project-thread-n3u3hh`.

1. Open a pull request from `claude/project-thread-n3u3hh` into `main` on GitHub. Read the diff. Merge with a merge commit, so the release commit stays in the history of `main`. The project coordinator may already have done this.
2. Create the tag on the release commit. Either run `git fetch origin`, then `git tag -a v0.1.0-rc1 RELEASE_SHA -m "Release candidate 1"`, then `git push origin v0.1.0-rc1`, or create a pre-release with that tag on the GitHub releases page. The coordinator may already have done this.
3. Run the secret scan once more: `gitleaks git -v .` in a fresh clone.
4. Check that the CI run on the merge commit is green on the Actions page. The build agent ran every CI step locally and could not read the Actions page.
5. Make the repo public when you are ready. All history becomes public at that moment.
6. Pages: not needed. The results page `docs/index.html` opens from disk. Turn on Pages from `/docs` only if you want it online.
7. Upload `docs/social-preview.png` in Settings, General, Social preview. Fill in the About box from [GITHUB_ABOUT.md](GITHUB_ABOUT.md) and the topics from [topics.txt](topics.txt) if the coordinator did not.
8. Pin the repo or list it in your profile README.
9. Publish to PyPI with trusted publishing, if you want the package public. Check first that the name `tracefault` is free.
10. Decide whether `docs/build/BUILD_PROMPT.md` stays public.
11. Stretch: run `tracefault scan` on traces from a real agent and label 50 of them by hand. That gives the first numbers that do not depend on the generator.
12. Stretch: embedding clustering needs a small model from huggingface.co, which was blocked in the build session. See [PROPOSALS.md](PROPOSALS.md).
13. The build agent could not install the toolkit skills (the install was denied). It applied their rules by hand. Install them yourself if you want a second pass. See [TOOLING.md](TOOLING.md).
14. Do the human checks listed at the end of the README.
