"""Utilities for extracting and merging BSL code embedded in 1C tuple format files.

v8unpack sometimes produces files where BSL module code is embedded as a multi-line
string inside a 1C tuple, e.g.:

    {3,1,0,"Процедура Тест()
    КонецПроцедуры
    ",0}

For managed form files (UUID.0 only), the module is the 3rd element of the root tuple;
extraction uses the same logic as V8Reader (ПолучитьСтрокиМодуляУФ). Files named "form"
are ordinary form files and are not processed (they do not contain form module text).

split_file / split_dir extract the code into a companion .bsl file and leave a
placeholder in the original.  merge_file / merge_dir do the reverse before the
file is fed back to v8unpack.
"""

import re
import shutil
import time
from pathlib import Path
from typing import Callable

from loguru import logger

logger.disable(__name__)

# Placeholder written into the source file where BSL code was extracted.
# Must be unique so merge can find it and substitute the .bsl content.
BSL_PLACEHOLDER = "<BSL_MODULE_PLACEHOLDER>"

# Forms that start with this (e.g. spreadsheet/document) have no BSL module in the file.
MOXCEL_FORM_PREFIX = "MOXCEL"

# Regex for 1C internal tuple (form). Literally from V8Reader ПолучитьСтрокиМодуляУФ:
# Pattern: (\{\n?)|("(""|[^"]*)*")|([^},\{]+)|(,\n?)|(\}\n?)
# Use \r?\n? so files written with CRLF on Windows are parsed correctly.
# 1C SubMatches are 1-based: (1)=open, (2)=string, (3)=other, (4)=comma, (5)=close
_RE_FORM_TUPLE = re.compile(
    r'(\{\r?\n?)|("(?:""|[^"]*)*")|([^},\{]+)|(,\r?\n?)|(\}\r?\n?)',
    re.MULTILINE,
)

# Managed form file name: UUID.0 (e.g. 011e7aea-f182-4640-aaad-f8abe975274c.0)
_RE_MANAGED_FORM_FILE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\.0$"
)

# Form description file (sibling of UUID.0): first string after {1,0,uuid} is form name
_RE_FORM_DESC_NAME = re.compile(r"\{1,0,[0-9a-fA-F-]{36}\},\s*\"([^\"]+)\"")

BSL_RENAMES_FILENAME = "bsl_renames.txt"
BIN_DIRNAME = "bin"
# Каталог со вспомогательными для сборки файлами (bsl_renames.txt, renames.txt)
META_DIRNAME = "meta"
# Разделитель в renames (как в renames.txt): "имя --> путь"
RENAMES_ARROW = " --> "
# Префиксы имён BSL в корне: 0_ — модуль объекта (обработки), 1_ — модуль формы
BSL_PREFIX_OBJECT = "0_"
BSL_PREFIX_FORM = "1_"


def _write_text_no_newline_translate(path: Path, text: str, encoding: str) -> None:
    """Записать текст без подмены \\n на os.linesep (побайтовое совпадение с образцом)."""
    path.write_bytes(text.encode(encoding))


def _read_text_preserve_newlines(path: Path, encoding: str = "utf-8-sig") -> str:
    """Прочитать текст без преобразования \\r/\\n (read_text даёт universal newlines)."""
    return path.read_bytes().decode(encoding)


def _read_file_content(path: Path) -> tuple[str, str] | None:
    """Read file as UTF-8, return (content, encoding) or None on error.

    encoding is 'utf-8-sig' if file has BOM, else 'utf-8'.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None
    encoding = "utf-8-sig" if has_bom else "utf-8"
    return (content, encoding)


def _writer_for_encoding(encoding: str) -> Callable[[Path, str], None]:
    """Return a (path, text) -> None writer that uses the given encoding."""
    return lambda p, s: _write_text_no_newline_translate(p, s, encoding)


def _is_managed_form_file(path: Path) -> bool:
    """True if *path* is a managed form (UUID.0)."""
    return _RE_MANAGED_FORM_FILE.match(path.name) is not None


def _get_form_or_object_name(root: Path, uuid_dot0_name: str) -> str | None:
    """Read description file (UUID) and return form/object name, or None.

    The form/module content lives in UUID.0 (file for managed form, dir for
    ordinary form); the name is stored in the sibling file UUID (without .0).
    E.g. name from "d820e314-6991-4b80-95fc-5960b9474823", content in
    "d820e314-6991-4b80-95fc-5960b9474823.0".
    """
    if not uuid_dot0_name.endswith(".0"):
        return None
    desc_name = uuid_dot0_name[:-2]  # UUID.0 → read file UUID
    desc_path = root / desc_name
    result = _read_file_content(desc_path)
    if result is None:
        return None
    content, _ = result
    m = _RE_FORM_DESC_NAME.search(content)
    return m.group(1) if m else None


def _find_form_module_by_tuple(
    content: str, element_index: int = 2
) -> tuple[str, int, int, int, int] | None:
    """Literal port of V8Reader ПолучитьСтрокиМодуляУФ (form_module.bsl lines 4862–4912).

    Finds BSL module as (element_index+1)-th element of root tuple (ИндексРодителя = "0").
    Form module = 3rd element (element_index=2); object module = 4th (element_index=3).
    Same order of checks: comma (4), open (1), close (5), else value (3=other, 2=string).
    Same line counting and text post-processing (strip quotes, ""→", ВК→ПС).
    Returns (code, start_pos, end_pos, start_line, end_line) or None.
    """
    line_no = 1
    index_parent = ""
    current_index = 0
    start_line = 0
    end_line = 0
    value: str | None = None
    value_span: tuple[int, int] | None = None

    for m in _RE_FORM_TUPLE.finditer(content):
        if index_parent == "0" and current_index == element_index:
            start_line = line_no

        if m.group(4) is not None:
            current_index += 1
            line_no += m.group(4).count("\n")
        elif m.group(1) is not None:
            index_parent = (index_parent + ":" if index_parent else "") + str(
                current_index
            )
            current_index = 0
            line_no += m.group(1).count("\n")
        elif m.group(5) is not None:
            if index_parent:
                parts = index_parent.split(":")
                current_index = int(parts[-1])
                index_parent = ":".join(parts[:-1])
            line_no += m.group(5).count("\n")
        else:
            if m.group(3) is not None:
                value = m.group(3)
                line_no += m.group(3).count("\n") + m.group(3).count("\r")
            else:
                value = m.group(2)
                value_span = (m.start(), m.end())
                line_no += m.group(2).count("\n")
                if start_line != 0:
                    end_line = line_no
                    break

    if value is None or value_span is None or start_line == 0:
        return None

    raw = value
    body = raw[1:-1].replace('""', '"')
    # Allow empty body so that empty form modules are still extracted
    return (body, value_span[0], value_span[1], start_line, end_line)


def _find_empty_string(content: str) -> tuple[int, int] | None:
    """Return (start, end) of the first empty string ``""`` in a 1C tuple file.

    start == end because the body between the quotes is empty.  Inserting text
    at that position effectively fills in the placeholder.

    Returns None when no empty string is found.
    """
    i = 0
    n = len(content)

    while i < n:
        if content[i] != '"':
            i += 1
            continue

        j = i + 1
        if j < n and content[j] == '"':
            if j + 1 >= n or content[j + 1] != '"':
                return (i + 1, j)

        j = i + 1
        while j < n:
            if content[j] == '"':
                if j + 1 < n and content[j + 1] == '"':
                    j += 2
                else:
                    break
            else:
                j += 1
        i = j + 1

    return None


def _find_placeholder_string(content: str) -> tuple[int, int] | None:
    """Return (start, end) of the full placeholder '"<BSL_MODULE_PLACEHOLDER>"'.

    Replacing content[start:end] with '"' + escaped_code + '"' restores the
    module string in the file.
    """
    marker = f'"{BSL_PLACEHOLDER}"'
    idx = content.find(marker)
    if idx == -1:
        return None
    return (idx, idx + len(marker))


def _extract_plain_module(
    path: Path,
    content: str,
    write: Callable[[Path, str], None],
    bsl_path: Path | None = None,
) -> bool:
    """Handle 'module' or 'text' file with plain BSL (no tuple). Return True if done."""
    dest = bsl_path if bsl_path is not None else path.with_name(path.name + ".bsl")
    write(dest, content)
    write(path, BSL_PLACEHOLDER)
    logger.debug(f"Extracted BSL from '{path}' → '{dest}' (plain module)")
    return True


def _extract_managed_form(
    path: Path,
    content: str,
    write: Callable[[Path, str], None],
    bsl_path: Path | None = None,
) -> bool:
    """Handle managed form (UUID.0) with BSL in tuple. Return True if extracted."""
    if content.startswith(MOXCEL_FORM_PREFIX):
        return False

    form_result = _find_form_module_by_tuple(content)
    if form_result is None:
        return False

    code, replace_start, replace_end, _line_start, _line_end = form_result
    # Skip if content is already placeholder (re-parse of already-split file)
    if code.strip() == BSL_PLACEHOLDER:
        return False
    dest = bsl_path if bsl_path is not None else path.with_name(path.name + ".bsl")
    write(dest, code)

    placeholder_in_file = f'"{BSL_PLACEHOLDER}"'
    new_content = content[:replace_start] + placeholder_in_file + content[replace_end:]
    write(path, new_content)
    logger.debug(f"Extracted BSL from '{path}' → '{dest}'")
    return True


def split_file(path: Path, bsl_dest_path: Path | None = None) -> bool:
    """Extract BSL code embedded in *path* into a companion .bsl file.

    If *bsl_dest_path* is given, write BSL there; otherwise use path.name + ".bsl"
    alongside *path*.
    """
    result = _read_file_content(path)
    if result is None:
        return False
    content, encoding = result
    # Skip already-split files (plain placeholder) to avoid writing placeholder into .bsl
    if content.strip() == BSL_PLACEHOLDER:
        return False
    write = _writer_for_encoding(encoding)

    if path.name in ("module", "text"):
        stripped = content.strip()
        if not (stripped.startswith("{") and "}" in stripped):
            return _extract_plain_module(path, content, write, bsl_dest_path)

    if _is_managed_form_file(path):
        return _extract_managed_form(path, content, write, bsl_dest_path)

    return False


def merge_file(bsl_path: Path, base_path: Path | None = None) -> bool:
    """Merge BSL code from *bsl_path* back into the corresponding 1C tuple file.

    The companion file is *base_path* if given, otherwise ``bsl_path`` without
    its ``.bsl`` suffix. Looks for the placeholder string
    ``"<BSL_MODULE_PLACEHOLDER>"`` first; if not found, uses the first empty
    string ``""``. Replaces it with the code (quotes escaped as ``""``).

    Returns True when the merge was performed, False otherwise.
    """
    if base_path is None:
        base_path = bsl_path.with_name(bsl_path.stem)
    if not base_path.exists():
        logger.warning(f"Base file not found for '{bsl_path}' — skipping")
        return False

    result = _read_file_content(base_path)
    if result is None:
        logger.warning(f"Cannot read/decode base file '{base_path}' — skipping")
        return False
    content, encoding = result
    write = _writer_for_encoding(encoding)

    try:
        code = _read_text_preserve_newlines(bsl_path)
    except (OSError, UnicodeDecodeError):
        logger.warning(f"Cannot read BSL file '{bsl_path}' — skipping")
        return False

    if (base_path.name in ("module", "text")) and content.strip() == BSL_PLACEHOLDER:
        write(base_path, code)
        logger.debug(f"Merged BSL from '{bsl_path}' → '{base_path}' (plain module)")
        return True

    result_span = _find_placeholder_string(content)
    if result_span is None:
        result_span = _find_empty_string(content)
    if result_span is None:
        logger.warning(
            f"No placeholder found in '{base_path}' — skipping (expected "
            f'"{BSL_PLACEHOLDER}" or empty string "")'
        )
        return False

    start, end = result_span
    escaped_code = code.replace('"', '""')

    if content[start:end].startswith('"'):
        new_content = content[:start] + '"' + escaped_code + '"' + content[end:]
    else:
        new_content = content[:start] + escaped_code + content[end:]

    write(base_path, new_content)
    logger.debug(f"Merged BSL from '{bsl_path}' → '{base_path}'")
    return True


def _unique_bsl_name(root: Path, base_name: str) -> str:
    """Return base_name + '.bsl' or base_name_n.bsl if name already exists."""
    name = f"{base_name}.bsl"
    if not (root / name).exists():
        return name
    n = 1
    while (root / f"{base_name}_{n}.bsl").exists():
        n += 1
    return f"{base_name}_{n}.bsl"


def _read_existing_bsl_renames(root: Path) -> dict[str, str]:
    """Read meta/bsl_renames.txt or bsl_renames.txt; return companion -> bsl_name map."""
    result: dict[str, str] = {}
    for renames_path in (
        root / META_DIRNAME / BSL_RENAMES_FILENAME,
        root / BSL_RENAMES_FILENAME,
    ):
        if not renames_path.exists():
            continue
        with renames_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if RENAMES_ARROW not in line:
                    continue
                bsl_name, companion = line.split(RENAMES_ARROW, 1)
                result[companion.strip()] = bsl_name.strip()
    return result


def _write_bsl_renames_file(root: Path, renames_entries: list[tuple[str, str]]) -> None:
    """Write meta/bsl_renames.txt from (bsl_filename, companion_rel) list."""
    if not renames_entries:
        return
    meta_path = root / META_DIRNAME
    meta_path.mkdir(exist_ok=True)
    path = meta_path / BSL_RENAMES_FILENAME
    with path.open("w", encoding="utf-8") as f:
        for bsl_name, companion in renames_entries:
            f.write(f"{bsl_name}{RENAMES_ARROW}{companion}\n")


def _move_to_bin_with_retry(p: Path, dest: Path, *, max_attempts: int = 5) -> None:
    """Move file or dir to dest, retrying on PermissionError (Windows: antivirus/indexer may hold handles)."""
    for attempt in range(max_attempts):
        try:
            if p.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                p.rename(dest)
            else:
                shutil.move(str(p), str(dest))
            return
        except PermissionError:
            if attempt == max_attempts - 1:
                raise
            time.sleep(0.15 * (attempt + 1))


def _apply_bin_layout(root: Path) -> None:
    """Move all non-BSL, non-meta content under bin/; write renames.txt; update bsl_renames with bin/ prefix."""
    bin_path = root / BIN_DIRNAME
    bin_path.mkdir(exist_ok=True)
    for p in list(root.iterdir()):
        if p.name in (META_DIRNAME, BIN_DIRNAME):
            continue
        if p.is_file() and p.suffix.lower() == ".bsl":
            continue
        dest = bin_path / p.name
        _move_to_bin_with_retry(p, dest)
    renames_txt_entries: list[tuple[str, str]] = []
    for p in bin_path.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(root)
        rel_str = str(rel).replace("\\", "/")
        prefix = BIN_DIRNAME + "/"
        target = rel_str[len(prefix) :] if rel_str.startswith(prefix) else rel_str
        renames_txt_entries.append((target, rel_str))
    meta_path = root / META_DIRNAME
    renames_txt_path = meta_path / "renames.txt"
    with renames_txt_path.open("w", encoding="utf-8") as f:
        for target, source in sorted(renames_txt_entries, key=lambda x: x[0]):
            f.write(f"{target}{RENAMES_ARROW}{source}\n")
    bsl_renames_path = meta_path / BSL_RENAMES_FILENAME
    with bsl_renames_path.open("r", encoding="utf-8") as rf:
        lines = rf.readlines()
    with bsl_renames_path.open("w", encoding="utf-8") as wf:
        for line in lines:
            line = line.strip()
            if RENAMES_ARROW not in line:
                continue
            bsl_name, companion = line.split(RENAMES_ARROW, 1)
            bsl_name, companion = bsl_name.strip(), companion.strip()
            wf.write(f"{bsl_name}{RENAMES_ARROW}{BIN_DIRNAME}/{companion}\n")


def split_dir(
    dir_path: Path,
    use_form_names: bool = True,
    use_bin_layout: bool = True,
) -> int:
    """Recursively extract BSL code from all mixed files under *dir_path*.

    If *use_form_names* is True, BSL files are named and placed in *dir_path*
    root: form modules (managed and ordinary) get prefix ``1_``, object module
    (text) gets prefix ``0_`` (e.g. ``0_Объект.bsl``, ``1_ФормаОбычная.bsl``).
    Names come from description file (UUID without .0); bsl_renames.txt
    records the companion path for each .bsl file. If
    *use_bin_layout* is True, all non-BSL files are moved under a ``bin``
    subdir and renames.txt is written for build.

    Returns the number of files from which code was extracted.
    """
    root = dir_path
    use_names = use_form_names
    renames_entries: list[tuple[str, str]] = []  # (bsl_filename, companion_rel)
    # Reuse existing bsl names when re-parsing so we overwrite 0_Объект.bsl instead of creating 0_Объект_1.bsl
    existing_companion_to_bsl = _read_existing_bsl_renames(root) if use_names else {}

    count = 0
    items = sorted(dir_path.rglob("*"), key=lambda p: (len(p.parts), str(p)))
    for item in items:
        if item.is_dir() or item.suffix.lower() == ".bsl":
            continue
        if META_DIRNAME in item.parts:
            continue
        # Skip files under bin/ when using bin layout: they are from a previous run (with placeholder)
        if use_bin_layout and BIN_DIRNAME in item.parts:
            continue
        bsl_dest_path: Path | None = None
        renames_entry: tuple[str, str] | None = None
        if use_names:
            try:
                rel = item.relative_to(root)
            except ValueError:
                rel = item
            companion = str(rel).replace("\\", "/")
            companion_after_bin = (
                f"{BIN_DIRNAME}/{companion}" if use_bin_layout else companion
            )

            def _choose_bsl_name(base_name: str) -> str:
                existing = existing_companion_to_bsl.get(
                    companion_after_bin
                ) or existing_companion_to_bsl.get(companion)
                return existing if existing else _unique_bsl_name(root, base_name)

            if _is_managed_form_file(item):
                form_name = _get_form_or_object_name(root, item.name)
                if form_name:
                    base_name = BSL_PREFIX_FORM + form_name
                    bsl_name = _choose_bsl_name(base_name)
                    bsl_dest_path = root / bsl_name
                    renames_entry = (bsl_name, companion)
            elif item.name in ("module", "text") and rel.parts:
                parent_name = item.parent.name
                if parent_name.endswith(".0"):
                    obj_name = _get_form_or_object_name(root, parent_name)
                    if item.name == "module":
                        if obj_name:
                            base_name = BSL_PREFIX_FORM + obj_name
                            bsl_name = _choose_bsl_name(base_name)
                            bsl_dest_path = root / bsl_name
                            renames_entry = (bsl_name, companion)
                    else:
                        # object module (text): 0_Имя или 0_Объект при отсутствии описания
                        base_name = BSL_PREFIX_OBJECT + (
                            obj_name if obj_name else "Объект"
                        )
                        bsl_name = _choose_bsl_name(base_name)
                        bsl_dest_path = root / bsl_name
                        renames_entry = (bsl_name, companion)
        if split_file(item, bsl_dest_path):
            count += 1
            if renames_entry is not None:
                renames_entries.append(renames_entry)

    _write_bsl_renames_file(root, renames_entries)
    if (
        use_bin_layout
        and count
        and (root / META_DIRNAME / BSL_RENAMES_FILENAME).exists()
    ):
        _apply_bin_layout(root)

    if count:
        logger.debug(f"Extracted BSL from {count} file(s) in '{dir_path}'")
    return count


def merge_dir(dir_path: Path) -> int:
    """Recursively merge all ``.bsl`` files under *dir_path* back into their
    companion 1C tuple files, then delete the ``.bsl`` files.

    If *dir_path* contains bsl_renames.txt, each listed .bsl file is merged
    into the path given in that file (allowing named .bsl in root and bin layout).

    Returns the number of files merged.
    """
    count = 0
    renames_path = dir_path / META_DIRNAME / BSL_RENAMES_FILENAME
    if renames_path.exists():
        with renames_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                parts = line.split(RENAMES_ARROW, 1)
                bsl_name, companion = parts[0].strip(), parts[1].strip()
                bsl_path = dir_path / bsl_name
                base_path = dir_path / companion
                if bsl_path.exists() and base_path.exists():
                    if merge_file(bsl_path, base_path):
                        bsl_path.unlink()
                        count += 1
    if count:
        logger.debug(f"Merged BSL into {count} file(s) in '{dir_path}'")
    return count


def has_bin_layout(dir_path: Path) -> bool:
    """True if *dir_path* has meta/renames.txt, meta/bsl_renames.txt and bin/."""
    meta = dir_path / META_DIRNAME
    return (
        (meta / "renames.txt").exists()
        and (meta / BSL_RENAMES_FILENAME).exists()
        and (dir_path / BIN_DIRNAME).is_dir()
    )


def prepare_temp_for_build(input_dir_path: Path, temp_parent: Path) -> Path:
    """Подготовить во временном каталоге дерево для v8unpack -B из раскладки bin + meta.

    Копирует содержимое bin по meta/renames.txt, копирует .bsl, записывает
    bsl_renames (без префикса bin/), вызывает merge_dir, удаляет bsl_renames из temp.
    Возвращает путь к подготовленному каталогу (temp_parent / input_dir_path.name).
    """
    temp_source_dir_path = temp_parent / input_dir_path.name
    temp_source_dir_path.mkdir(parents=True)
    meta_dir = input_dir_path / META_DIRNAME
    renames_path = meta_dir / "renames.txt"
    bsl_renames_path = meta_dir / BSL_RENAMES_FILENAME
    prefix_bin = BIN_DIRNAME + "/"

    with renames_path.open(encoding="utf-8-sig") as f:
        for line in f:
            if RENAMES_ARROW not in line:
                continue
            parts = line.strip().split(RENAMES_ARROW, 1)
            if len(parts) != 2:
                continue
            target, source = parts[0].strip(), parts[1].strip()
            src_path = input_dir_path / source
            dest_path = temp_source_dir_path / target
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if src_path.is_dir():
                shutil.copytree(src_path, dest_path)
            else:
                shutil.copy2(src_path, dest_path)

    for bsl_file in input_dir_path.glob("*.bsl"):
        shutil.copy2(bsl_file, temp_source_dir_path / bsl_file.name)

    temp_meta = temp_source_dir_path / META_DIRNAME
    temp_meta.mkdir(parents=True, exist_ok=True)
    temp_bsl_renames = temp_meta / BSL_RENAMES_FILENAME
    with bsl_renames_path.open(encoding="utf-8") as rf:
        lines = rf.readlines()
    with temp_bsl_renames.open("w", encoding="utf-8") as tf:
        for line in lines:
            line = line.strip()
            if not line or RENAMES_ARROW not in line:
                continue
            parts = line.split(RENAMES_ARROW, 1)
            bsl_name, companion = parts[0].strip(), parts[1].strip()
            if companion.startswith(prefix_bin):
                companion = companion[len(prefix_bin) :]
            tf.write(f"{bsl_name}{RENAMES_ARROW}{companion}\n")

    merge_dir(temp_source_dir_path)
    temp_bsl_renames.unlink(missing_ok=True)
    if temp_meta.exists() and not any(temp_meta.iterdir()):
        temp_meta.rmdir()
    return temp_source_dir_path
