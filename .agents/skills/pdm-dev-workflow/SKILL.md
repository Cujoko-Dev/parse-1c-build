---
name: pdm-dev-workflow
description: >-
  PDM и вложенный проект `.dev`: установка зависимостей, запуск pytest и скриптов через
  `pdm run -p .dev` без активации venv. Use when the repository has `.dev/pyproject.toml`
  and the task touches Python, dependencies, or tests.
---

# PDM и каталог `.dev`

## Структура

В корне — основной `pyproject.toml` пакета. Разработческое окружение (pytest, инструменты) задаётся во **вложенном** проекте **`.dev/pyproject.toml`**. Его скрипты и команды запускают через **`pdm run -p .dev …`** (`-p` — путь к каталогу с dev-`pyproject.toml`).

## Команды

- Зависимости из корня: `pdm install` или `pdm sync` (см. раздел PDM в `AGENTS.md`).
- Тесты и скрипты из `[tool.pdm.scripts]` dev-проекта: например `pdm run -p .dev test`, `pdm run -p .dev pytest …`.
- Не рассчитывать на ручную активацию виртуального окружения: используй `pdm run -p .dev …`.

## Терминал

Если в репозитории есть `scripts/run.ps1` (ctl-1c, codemask-1c и т.п.), команды гоняй через него — см. `terminal-test-execution-policy.mdc`. Иначе выполняй `pdm` из корня репозитория.

## Ограничения

Не подменять управление зависимостями на `uv`, произвольный `pip install` для lockfile проекта или Poetry — см. раздел PDM в `AGENTS.md`.
