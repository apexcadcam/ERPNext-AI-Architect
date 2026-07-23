# Contributing

Practical rules for working on this repository. For the architecture itself, start at `docs/runtime/RUNTIME_ARCHITECTURE.md` and `ENGINEERING_META_MODEL.md` — this document is about *process*, not design.

## Development Setup

```bash
uv venv --python 3.11 .venv
uv pip install -e ".[dev]" --python .venv/bin/python
.venv/bin/architect --help          # sanity check
.venv/bin/pytest tests/             # should pass, 0 failures
```

Requires Python 3.11+. No other runtime dependency is assumed — keep it that way unless a change genuinely needs one.

## Branch Workflow

- **Never work directly on `main`.** Every unit of work gets its own branch.
- Naming: `review/sprint-<number>-<short-description>` (e.g. `review/sprint2-connectors`).
- Implement a Sprint's work only on its own branch — never split one Sprint across branches, never mix two Sprints on one branch.
- Review branches are never deleted, merged, squashed, rebased, or tagged without explicit approval from whoever owns that decision.

## Commit Message Convention

[Conventional Commits](https://www.conventionalcommits.org/): `<type>(<scope>): <description>`.

Types used in this project: `feat`, `fix`, `docs`, `test`, `chore`.

- **One commit per Sprint.** Do the work, verify it, then commit once — not a trail of incremental WIP commits.
  Example: `feat(runtime): implement Sprint 1 Runtime Bootstrap`
- **One additional commit per review round**, applying exactly the comments received in that round.
  Example: `fix(review): address PR review comments`
- Docs-only or config-only changes use `docs(...)` / `chore(...)` as appropriate.
  Example: `docs(project): add contribution guide and code quality configuration`

## Pull Request Workflow

- Push only the review branch — `main` is never pushed to directly.
- Open the PR from `review/sprint-N-...` into `main`.
- PR description covers: **Scope**, **Features implemented**, **Tests**, **Coverage**, **Out-of-scope**, **Known limitations**, **Risks**, **Checklist**.
- If the PR diff isn't reliably reachable by a reviewer, generate a self-contained review package (Markdown, or a zip of the branch) rather than assuming they can pull it themselves.
- Nothing merges into `main` without explicit approval. No exceptions for "small" changes.

## Review Workflow

For every review comment received:

1. Classify it: **Blocking**, **Major**, **Minor**, or **Style-only**.
2. Explain *why* it's classified that way before touching anything.
3. Propose the smallest possible fix — never bundle in unrelated cleanup.
4. Implement only what was requested. No proactive refactoring, no API changes, no optimization, no drive-by fixes.
5. Land every comment from one review round in a single `fix(review): ...` commit.

Treat every Sprint as if a senior engineer will review it before anything merges — because one will.

## Coding Standards

- Python 3.11+, full type hints throughout. `mypy --strict` must pass with zero errors.
- Format with `ruff format`; lint with `ruff check` (config lives in `pyproject.toml`'s `[tool.ruff]`) — both must pass clean before a commit.
- A module's docstring should name the specific architecture doc section it implements, where one exists (e.g. "Implements `docs/runtime/EVENT_BUS.md` §§1–2") — code that can't point at its own justification is a design smell here.
- No commented-out code, no debug `print()`/`pdb`, no TODO/FIXME left without an explicit reason attached.
- A public API (a class, function, or CLI command signature) doesn't change without an explicit review comment approving it — not a unilateral judgment call while touching nearby code.

## Before Every Commit

```bash
.venv/bin/pytest tests/
.venv/bin/mypy runtime/
.venv/bin/ruff check runtime/ tests/
.venv/bin/ruff format --check runtime/ tests/
```

All four must be run and their results reported honestly in the Sprint/review summary — including when one doesn't fully pass, and why.
