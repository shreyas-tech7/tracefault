# Prompt for Claude Cowork

Paste this into Claude Cowork. Use ASD-STE100 Simplified Technical English. Do not ask questions. Do not stop without a deliverable outcome.

---

You help Shreyas finish the browser steps for the private GitHub repo `shreyas-tech7/tracefault`. Do only the steps below. They are free and can be undone.

Do not make the repo public. Do not publish a package. Do not enter keys. Do not sign in for Shreyas. Do not pay for anything. If a step needs one of these, skip it and write it in your report.

1. Open the Actions page of the repo. Find the latest CI run on `main` or on `claude/project-thread-n3u3hh`. Write down if it passed. If it failed, copy the name of the failed step.
2. Open Settings, General. If the description is empty, set it to the text in `docs/GITHUB_ABOUT.md`. If the topics are empty, add the topics in `docs/topics.txt`.
3. In Settings, General, Social preview, upload `docs/social-preview.png` from the repo.
4. Open the Releases page. Check if the pre-release `v0.1.0-rc1` exists and points at the release commit in `CHANGELOG.md`. Do not create it if it needs a tag push from a terminal. Write it in your report.
5. Open `README.md` on GitHub. Check that the mermaid diagram renders and the results table shows numbers.

When you finish, write the next Claude Code prompt. It must hold:
- Context: the repo, the branch `claude/project-thread-n3u3hh`, and what you checked.
- What is complete and what is open, from your steps and from `docs/HUMAN_STEPS.md`.
- This resume launcher: "Read docs/build/BUILD_PROMPT.md and follow it. Resume from PROGRESS.md on branch claude/project-thread-n3u3hh. Do not ask questions. Do not stop until every Done-means item is true or blocked with a fallback."
- An instruction to the next Claude Code session: do not ask questions, and do not stop without a deliverable outcome.
