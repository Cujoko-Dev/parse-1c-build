# Codex Agent Notes

Shared agent guidance lives in `AGENTS.md` (this file) and `.agents/skills/`.
`CLAUDE.md` imports this file. Cursor, Codex, and Claude Code all read it.

## Before Making Changes

- Files under `.cursor/rules/` are project-only extras (globs, 1C, terminals), not a second copy of the shared rules.
- For architecture or larger changes, read the relevant `.agents/skills/*/SKILL.md`.
- Follow the managed sections below; they apply to every agent.

## Project-specific Cursor rules

- `.cursor/rules/terminal-test-execution-policy.mdc` before running tests, builds, 1C, or long-running commands.
- `.cursor/rules/bsl-forms.mdc` before changing BSL form parsing, form files, or related fixtures.
- `.cursor/rules/no-temp-in-project.mdc` before creating temporary files or generated artifacts.

## Skills To Check

- `.agents/skills/parse-1c-build-architecture/SKILL.md` for parser architecture, build parsing flow, and larger design changes.
- `.agents/skills/pdm-dev-workflow/SKILL.md` for PDM-based development workflow.

## Test And Terminal Policy

For tests, builds, 1C launches, or long-running commands, use `.\scripts\run.ps1` as described in `.cursor/rules/terminal-test-execution-policy.mdc`.
Do not run `pytest`, `python -m pytest`, `pdm run pytest`, or 1C commands directly for those workflows.

Safe read-only inspection commands such as `git status`, `git diff`, `rg`, `Get-Content`, `ls`, and `dir` are fine directly.

<!-- agent-rules:begin | управляется sync-agent-rules.py, правьте dev-utils/agent-rules/ -->

## External project notes

This project may have a `.notes` directory that points to external working notes.

Rules for using `.notes`:

- `.notes` is not automatically authoritative.
- Prefer `.notes/_current.md` as the curated current context.
- Treat other notes as non-authoritative unless they have explicit metadata such as `status: active` or `status: reference`.
- Treat `.notes/00-inbox/`, `.notes/30-someday/`, `.notes/80-completed/`, `.notes/90-archive/`, old plans, drafts and raw imported notes as historical or unprocessed context only.
- Folders `.notes/10-urgent/` and `.notes/20-active/` may hold current task notes; still verify them against the repository before acting.
- Closed tasks live in `.notes/80-completed/`; reference, dumps and historical material live in `.notes/90-archive/`.
- Source code, tests, configs, migrations, build scripts and repository files override external notes.
- If an external note conflicts with repository files, do not silently follow the note. Mention the conflict and prefer the repository.
- Do not perform large changes based only on old notes. First verify against current code and current project instructions.

## Local junction directories

The project root on a developer machine may contain **junction** directories
(not in git; they may be missing on other machines).

### `.temp/`

- Temporary files **for this project**: debug output, intermediate artifacts,
  manual experiments.
- The junction points outside the repository (typically `D:\Temp\<project>`).
- If `.temp/` exists, prefer it over `tmp`, `temp`, `test_output`, and similar
  directories inside the tracked tree.
- If the junction is absent, use the system temp directory (Python:
  `tempfile.mkdtemp()`, `tempfile.TemporaryDirectory()`; PowerShell: `$env:TEMP`,
  `[System.IO.Path]::GetTempPath()`).
- Do not commit `.temp/` contents.

### `.notes/`

- Local external working notes. The junction typically points outside the
  repository, for example `D:\Notes\Work\_Dev\...\<project>`.
- Policy for those notes is in the "External project notes" section.
- If `.notes/` is absent, do not require it in CI or on other machines.

## Python package manager: PDM

This project uses **PDM** for dependencies and virtual environments.

- Install or sync with `pdm install` or `pdm sync`.
- Add or remove packages with `pdm add` / `pdm remove`.
- Run tools and scripts with `pdm run -p .dev …` when they are configured in
  `pyproject.toml`.

Do **not** use `uv`, `pip install` (for project lockfiles), or Poetry unless the
user explicitly asks for an exception.

`PDM_USE_UV` must stay **unset** in every environment — Windows, WSL and the
dev container alike. The uv resolver does not support PDM's `inherit_metadata`
lock strategy and silently discards it. When that happens, `requires_python` and
`groups` disappear from every entry in `pdm.lock`, so the lock no longer records
which group a package belongs to. Updating a single package rewrites roughly
600 lines.

A mixed setup is the worst case: with uv enabled on one machine and disabled on
another, `pdm.lock` flips between `strategy = ["inherit_metadata"]` and
`strategy = []` on every update, producing conflicts across the whole file.

`PDM_USE_UV` is an environment variable and overrides a per-project `pdm.toml`,
so the setting cannot be pinned inside the repository. Check before locking:

```sh
pdm config use_uv   # must report False
```

## Python environment safety

These rules apply to **every** Python invocation: tests, apps, helpers,
migrations, generators, one-off scripts, and `python -c`.

- Resolve the repository environment first and check the real interpreter with
  `sys.executable`.
- Prefer the nested `.dev` project (typically `.dev/.venv`) through the project
  manager: `pdm run -p .dev ...`. If `.dev` is absent, use the root `.venv`.
- Do not run task logic with system/base Python or user-site, even for a
  temporary script that only uses the standard library.
- Base Python is allowed only to discover interpreters and verify the
  environment (`py -0p`, `python --version`, printing `sys.executable`). After
  that, run further Python through the project environment.
- Do not install dependencies into system/base Python or user-site
  (`pip install`, `python -m pip install`, and equivalents aimed there).
- If there is no suitable venv, or a dependency is missing from it, stop and
  tell the user. Do not "fix" that with a global install.
- Installing or upgrading anything in base Python needs an explicit user OK for
  that exact action.
- Use `pipx` only for a planned user-facing CLI install or parity check, never
  as a substitute for the repository dev environment.

## Environment and testing

- Run Python and tests with `pdm run -p .dev ...`. Do not activate the venv by
  hand.
- Do not edit test files unless the user asked, or the change is impossible
  without touching tests.

## Commit message format

When the agent stops and has changed files, it must proactively suggest commit
messages.

For each affected project/repository with file changes, provide exactly one
ready-to-use message.

If no files were changed, do not suggest a commit message.

Each message must be concise, imperative, and aligned with repository style.
This is a suggestion only. Creating a commit is a separate explicit request
(`/cm` or `$cm`).

<!-- agent-rules:end -->
