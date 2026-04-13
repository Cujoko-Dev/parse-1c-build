---
name: parse-1c-build-architecture
description: >-
  Architecture of parse-1c-build: EPF/ERF unpack/pack pipeline (v8unpack, V8Reader, gcomp),
  BSL extraction layout (managed UUID.0 vs module/text vs form), meta/bin structure,
  and round-trip rebuild. Use when modifying Parser/Builder, extending BSL split/merge,
  debugging roundtrip mismatches, or working with the p1cb CLI.
---

# parse-1c-build: архитектура парсера

## Что делает проект

**parse-1c-build** — Python-библиотека и CLI для **распаковки и сборки** 1C-артефактов:
- `.epf`/`.erf` — через **v8unpack** (по умолчанию) или **V8Reader + 1C платформа**
- `.md`/`.ert` — через **GComp**

Проект **не** парсит BSL в AST. Он оркестрирует внешние инструменты и добавляет слой **извлечения BSL** из артефактов v8unpack чтобы модули были редактируемы как `.bsl`-файлы со стабильной структурой `bin/ + meta/`.

## Точки входа

- **CLI:** `p1cb` → `parse_1c_build.__main__:run` → `core.run()`
- **Субкоманды:** `parse` (модуль `parse.py`) и `build` (модуль `build.py`)
- **Программный API:** `Parser`, `Builder` из `parse_1c_build`

## Ключевые модули

| Файл | Роль |
|------|------|
| `base.py` | `Processor`: настройки из `settings.yaml`, пути к `v8unpack`/`gcomp`, флаг `use_reader` |
| `parse.py` | `Parser`: распаковка EPF/ERF (v8unpack или V8Reader), опционально `bsl.split_dir` |
| `build.py` | `Builder`: сборка EPF/ERF через `v8unpack -B` после подготовки дерева (BSL merge) |
| `bsl.py` | **Центральный модуль:** split/merge BSL, `meta/` + `bin/` layout, `bsl_renames.txt` |
| `process_utils.py` | `run_silent` / `check_silent` — subprocess-обёртки |

## Пайплайн распаковки EPF/ERF

```
Parser.run(input.epf)
  → output dir = parent / "{stem}_epf_src"
  → rmtree existing output
  → v8unpack -P input.epf output_dir   (или V8Reader bat)
  → (если не --raw) bsl.split_dir(output_dir)
```

**V8Reader-ветка:** пишет временный `.bat` (cp866), запускает 1cv8 с `/Execute V8Reader.epf` и командной строкой `decompile;pathToCF;...;pathOut;...;shutdown;convert-mxl2txt;`, удаляет bat после.

## Типы форм и как извлекается BSL (`bsl.py`)

### Управляемые формы (`UUID.0`)

- Имя файла соответствует regex `[0-9a-f]{8}-...-[0-9a-f]{12}\.0`
- BSL спрятан как **строка** внутри 1C-кортежа — **3-й элемент** (index 2) корневого кортежа
- `split_file` извлекает строку, убирает `""` → `"`, пишет `<companion>.bsl`, заменяет строку на `"<BSL_MODULE_PLACEHOLDER>"`

### Файлы `module` и `text`

- Если содержимое **не** выглядит как кортеж (`{ … }`) → считается **plain BSL**
- Файл целиком копируется в `.bsl`, оригинал заменяется однострочным placeholder

### ❌ Файл `form`

**Обычные формы** — файл `form` содержит **разметку/метаданные**, **НЕ** текст модуля. `split_file` **не обрабатывает** файл `form` как BSL, даже если внутри есть текст процедур. Это специфика `bsl-forms.mdc`.

### ❌ UUID без `.0`

Чистые UUID-файлы (без суффикса `.0`) — не содержат модуля, не трогать.

```
UUID           ← дескриптор (имя формы) — не BSL
UUID.0         ← управляемая форма — BSL внутри кортежа
UUID.0/form    ← обычная форма — разметка, НЕ BSL
UUID.0/module  ← модуль обычной формы — plain BSL
UUID.0/text    ← объектный модуль — plain BSL
```

## Структура `meta/` + `bin/` после split_dir

```
output_dir/
  0_ОбъектName.bsl          ← объектный модуль (из text)
  1_ФормаName.bsl           ← модуль формы (из UUID.0 или module)
  meta/
    bsl_renames.txt         ← .bsl → companion path map
    renames.txt             ← target → bin/... для v8unpack rebuild
  bin/
    ...все остальные файлы...
```

`_apply_bin_layout` перемещает всё (кроме `meta/`, `bin/`, корневых `*.bsl`) в `bin/` и перезаписывает оба `meta/*.txt`.

## Round-trip: сборка обратно

```
Builder.run(output_dir/)
  → prepare_temp_for_build:
      copy bin/ → flat tree (per meta/renames.txt)
      copy root *.bsl
      rewrite meta/bsl_renames.txt (убрать bin/ prefix)
      merge_dir (BSL → placeholder замены обратно)
      delete temp bsl_renames
  → v8unpack -B temp_dir result.epf
  → backup старого result.epf (опционально)
```

## Структура тестов

```
tests/
  test_parse.py    # CLI parse → bin/root существует
  test_build.py    # Roundtrip: parse → build → parse --raw, побайтовое сравнение
  test_bsl.py      # split_file / merge_file edge cases, split_dir/merge_dir, meta/ invariants
  test_base.py     # Processor / settings failures
  data/
    test.epf                  # фикстура для parse/build
    test_epf_src/             # эталонное дерево для byte-for-byte сравнения
```

## Практические заметки

- **`--raw`:** только `v8unpack -P`, без `split_dir` — кортежные файлы остаются нетронутыми
- **Кодировка:** читает с BOM → `utf-8-sig`; пишет через `write_bytes` чтобы не менять переводы строк
- **Merge:** ищет `"<BSL_MODULE_PLACEHOLDER>"` в кортеже; если нет — первую пустую `""` (пустые модули)
- **`_move_to_bin_with_retry`:** обход `PermissionError` при перемещении файлов на Windows
- **Нет AST-модели:** «parsed state» — это файловая система; никакого in-memory графа объектов 1C нет
