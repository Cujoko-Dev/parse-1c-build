# Codex Agent Notes

This repository already keeps most project-specific agent guidance in Cursor files.
Codex should use those files as the source of truth instead of duplicating them here.

## Before Making Changes

- Read the relevant files under `.cursor/rules/*.mdc`.
- For architecture or larger changes, read the relevant `.cursor/skills/*/SKILL.md`.
- Treat Cursor rules as project instructions unless they conflict with an explicit user request or higher-priority Codex/system instructions.
- If the local `.notes/` directory exists, check relevant notes there before non-trivial changes, business-logic changes, refactoring, or architecture work.

## Project Notes

Project notes are available in the local `.notes/` directory when it exists.
The `.notes/` directory is local workspace context and may be absent on other machines.

## Common Cursor Rules To Check

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
