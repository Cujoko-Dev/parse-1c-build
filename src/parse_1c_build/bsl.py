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


def _write_text_no_newline_translate(
    path: Path, text: str, encoding: str
) -> None:
    """Записать текст без подмены \\n на os.linesep (побайтовое совпадение с образцом)."""
    path.write_bytes(text.encode(encoding))


def _read_text_preserve_newlines(
    path: Path, encoding: str = "utf-8-sig"
) -> str:
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
    if not body:
        return None

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


def _extract_plain_module(path: Path, content: str, write: Callable[[Path, str], None]) -> bool:
    """Handle 'module' or 'text' file with plain BSL (no tuple). Return True if done."""
    bsl_path = path.with_name(path.name + ".bsl")
    write(bsl_path, content)
    write(path, BSL_PLACEHOLDER)
    logger.debug(f"Extracted BSL from '{path}' → '{bsl_path}' (plain module)")
    return True


def _extract_managed_form(
    path: Path, content: str, write: Callable[[Path, str], None]
) -> bool:
    """Handle managed form (UUID.0) with BSL in tuple. Return True if extracted."""
    if content.startswith(MOXCEL_FORM_PREFIX):
        return False

    form_result = _find_form_module_by_tuple(content)
    if form_result is None:
        return False

    code, replace_start, replace_end, _line_start, _line_end = form_result
    bsl_path = path.with_name(path.name + ".bsl")
    write(bsl_path, code)

    placeholder_in_file = f'"{BSL_PLACEHOLDER}"'
    new_content = (
        content[:replace_start] + placeholder_in_file + content[replace_end:]
    )
    write(path, new_content)
    logger.debug(f"Extracted BSL from '{path}' → '{bsl_path}'")
    return True


def split_file(path: Path) -> bool:
    """Extract BSL code embedded in *path* into a companion ``path.bsl`` file."""
    result = _read_file_content(path)
    if result is None:
        return False
    content, encoding = result
    write = _writer_for_encoding(encoding)

    if path.name in ("module", "text"):
        stripped = content.strip()
        if not (stripped.startswith("{") and "}" in stripped):
            return _extract_plain_module(path, content, write)

    if _is_managed_form_file(path):
        return _extract_managed_form(path, content, write)

    return False


def merge_file(bsl_path: Path) -> bool:
    """Merge BSL code from *bsl_path* back into the corresponding 1C tuple file.

    The companion file is ``bsl_path`` without its ``.bsl`` suffix. Looks for
    the placeholder string ``"<BSL_MODULE_PLACEHOLDER>"`` first; if not found,
    uses the first empty string ``""``. Replaces it with the code (quotes
    escaped as ``""``).

    Returns True when the merge was performed, False otherwise.
    """
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


def split_dir(dir_path: Path) -> int:
    """Recursively extract BSL code from all mixed files under *dir_path*.

    Returns the number of files from which code was extracted.
    """
    count = 0
    for item in dir_path.rglob("*"):
        if item.is_dir() or item.suffix.lower() == ".bsl":
            continue
        if split_file(item):
            count += 1
    if count:
        logger.info(f"Extracted BSL from {count} file(s) in '{dir_path}'")
    return count


def merge_dir(dir_path: Path) -> int:
    """Recursively merge all ``.bsl`` files under *dir_path* back into their
    companion 1C tuple files, then delete the ``.bsl`` files.

    Returns the number of files merged.
    """
    count = 0
    for bsl_path in list(dir_path.rglob("*.bsl")):
        if merge_file(bsl_path):
            bsl_path.unlink()
            count += 1
    if count:
        logger.info(f"Merged BSL into {count} file(s) in '{dir_path}'")
    return count
