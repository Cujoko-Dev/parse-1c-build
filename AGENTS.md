# Codex Agent Notes

This repository already keeps most project-specific agent guidance in Cursor files.
Codex should use those files as the source of truth instead of duplicating them here.

## Before Making Changes

- Read the relevant files under `.cursor/rules/*.mdc`.
- For architecture or larger changes, read the relevant `.cursor/skills/*/SKILL.md`.
- Treat Cursor rules as project instructions unless they conflict with an explicit user request or higher-priority Codex/system instructions.

## Common Cursor Rules To Check

- `.cursor/rules/workspace-junctions.mdc` for local `.temp/` and `.notes/` junctions (when present).
- `.cursor/rules/terminal-test-execution-policy.mdc` before running tests, builds, 1C, or long-running commands.
- `.cursor/rules/testing-workflow.mdc` and `.cursor/rules/pdm-package-manager.mdc` before Python/test workflow changes.
- `.cursor/rules/bsl-forms.mdc` before changing BSL form parsing, form files, or related fixtures.
- `.cursor/rules/no-temp-in-project.mdc` before creating temporary files or generated artifacts.
- `.cursor/rules/auto-commit-message.mdc` before preparing commits.

## Common Cursor Skills To Check

- `.cursor/skills/parse-1c-build-architecture/SKILL.md` for parser architecture, build parsing flow, and larger design changes.

## Test And Terminal Policy

For tests, builds, 1C launches, or long-running commands, use `.\scripts\run.ps1` as described in `.cursor/rules/terminal-test-execution-policy.mdc`.
Do not run `pytest`, `python -m pytest`, `pdm run pytest`, or 1C commands directly for those workflows.

Safe read-only inspection commands such as `git status`, `git diff`, `rg`, `Get-Content`, `ls`, and `dir` are fine directly.

## External project notes

This project may have a `.notes` directory that points to external working notes.

Rules for using `.notes`:

- `.notes` is not automatically authoritative.
- Prefer `.notes/_current.md` as the curated current context.
- Treat other notes as non-authoritative unless they have explicit metadata such as `status: active` or `status: reference`.
- Treat `.notes/00-inbox/`, `.notes/30-someday/`, `.notes/90-archive/`, old plans, drafts and raw imported notes as historical or unprocessed context only.
- Folders `.notes/10-urgent/` and `.notes/20-active/` may hold current task notes; still verify them against the repository before acting.
- Source code, tests, configs, migrations, build scripts and repository files override external notes.
- If an external note conflicts with repository files, do not silently follow the note. Mention the conflict and prefer the repository.
- Do not perform large changes based only on old notes. First verify against current code and current project instructions.
