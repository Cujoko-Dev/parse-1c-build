"""Tests for parse_1c_build.bsl — BSL extraction / merge utilities."""

import tempfile
from pathlib import Path

import pytest

from parse_1c_build.bsl import (
    BSL_PLACEHOLDER,
    _find_empty_string,
    merge_dir,
    merge_file,
    split_dir,
    split_file,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Plain BSL code — no quote characters, so no escaping needed.
BSL_CODE = "Процедура Тест()\n\tМассив = Новый Массив();\nКонецПроцедуры\n"

# BSL code that contains a literal quote character.
# In BSL / 1C strings a literal " is written as "".
# bsl.split_file returns this with single quotes (unescaped from 1C format).
BSL_CODE_WITH_QUOTE = 'Стр = "текст";\n'

# 1C tuple format: the code field is a 1C string, so " → "".
MODULE_CONTENT = '{3,1,0,"' + BSL_CODE + '",0}'
MODULE_CONTENT_WITH_QUOTE = '{3,1,0,"Стр = ""текст"";\n",0}'
MODULE_EMPTY = '{3,1,0,"",0}'
# After split_file the code is replaced by this placeholder.
MODULE_WITH_PLACEHOLDER = f'{{3,1,0,"{BSL_PLACEHOLDER}",0}}'

BASE64_CONTENT = "{4,\n" "{#base64:77u/PD94bWwgdmVyc2lvbj0iMS4wIj8+}\n" "}"

XML_STRING_CONTENT = '{1,0,"<xml><tag>value</tag></xml>",1}'

MULTILINE_WITH_INNER_NEWLINE = '{3,1,0,"line1\nline2\n",0}'

# Minimal form file: root tuple; 3rd element (index 2) = form module (V8Reader rule).
FORM_FILE_CONTENT = (
    "{0,\n"
    "0,\n"
    '"Процедура ПриОткрытии()\n'
    "\tСообщить(1);\n"
    "КонецПроцедуры\n"
    '",\n'
    "0}\n"
)
FORM_MODULE_CODE = "Процедура ПриОткрытии()\n\tСообщить(1);\nКонецПроцедуры\n"


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8-sig")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# _find_empty_string
# ---------------------------------------------------------------------------


class TestFindEmptyString:
    def test_finds_empty_string(self):
        result = _find_empty_string(MODULE_EMPTY)
        assert result is not None
        start, end = result
        assert start == end  # empty body
        assert MODULE_EMPTY[start - 1] == '"'
        assert MODULE_EMPTY[end] == '"'

    def test_returns_none_when_no_empty_string(self):
        assert _find_empty_string('{3,1,0,"код",0}') is None

    def test_finds_first_empty_string(self):
        content = '{3,1,0,"",0,""}'
        result = _find_empty_string(content)
        assert result is not None
        # First empty string is right after {3,1,0,
        start, end = result
        assert start == end
        assert content[start - 1 : end + 1] == '""'


# ---------------------------------------------------------------------------
# split_file
# ---------------------------------------------------------------------------


class TestSplitFile:
    def test_extracts_code(self, tmp_path):
        src = tmp_path / "module"
        _write(src, MODULE_CONTENT)

        result = split_file(src)

        assert result is True
        assert _read(src) == MODULE_WITH_PLACEHOLDER
        bsl_path = tmp_path / "module.bsl"
        assert bsl_path.exists()
        assert _read(bsl_path) == BSL_CODE

    def test_unescapes_quotes(self, tmp_path):
        src = tmp_path / "module"
        _write(src, MODULE_CONTENT_WITH_QUOTE)

        split_file(src)

        bsl_path = tmp_path / "module.bsl"
        assert _read(bsl_path) == BSL_CODE_WITH_QUOTE

    def test_returns_false_for_empty_module(self, tmp_path):
        src = tmp_path / "module"
        _write(src, MODULE_EMPTY)

        assert split_file(src) is False
        assert not (tmp_path / "module.bsl").exists()
        assert _read(src) == MODULE_EMPTY

    def test_returns_false_for_base64(self, tmp_path):
        src = tmp_path / "layout"
        _write(src, BASE64_CONTENT)

        assert split_file(src) is False
        assert not (tmp_path / "layout.bsl").exists()

    def test_returns_false_for_xml_string(self, tmp_path):
        src = tmp_path / "xmlfile"
        _write(src, XML_STRING_CONTENT)

        assert split_file(src) is False

    def test_skips_bsl_file(self, tmp_path):
        src = tmp_path / "module.bsl"
        _write(src, BSL_CODE)
        # split_file itself does not check the extension — but split_dir does.
        # Direct call: the file has no multi-line string in 1C tuple format.
        assert split_file(src) is False

    def test_form_file_extracts_second_element_as_module(self, tmp_path):
        """File named 'form': module = 3rd element of root tuple (index 2), as in V8Reader."""
        src = tmp_path / "form"
        _write(src, FORM_FILE_CONTENT)

        result = split_file(src)

        assert result is True
        bsl_path = tmp_path / "form.bsl"
        assert bsl_path.exists()
        assert _read(bsl_path) == FORM_MODULE_CODE
        # Placeholder is the full quoted token for form (we replaced the whole string).
        assert _read(src) == ('{0,\n0,\n"' + BSL_PLACEHOLDER + '",\n0}\n')

    def test_managed_form_file_with_moxcel_prefix_skips_extraction(self, tmp_path):
        """Managed form (UUID.0) that starts with MOXCEL has no BSL module — do not extract."""
        src = tmp_path / "3a3209bb-e006-49cf-89f4-92fd41c3adf5.0"
        _write(src, "MOXCEL\t \n???{8,1,12,\n")

        result = split_file(src)

        assert result is False
        assert not (tmp_path / "3a3209bb-e006-49cf-89f4-92fd41c3adf5.0.bsl").exists()
        assert _read(src) == "MOXCEL\t \n???{8,1,12,\n"

    def test_module_file_is_plain_bsl_replaced_by_placeholder(self, tmp_path):
        """File named 'module' is already plain BSL: save to module.bsl, file becomes placeholder."""
        src = tmp_path / "module"
        _write(src, BSL_CODE)

        result = split_file(src)

        assert result is True
        assert _read(tmp_path / "module.bsl") == BSL_CODE
        assert _read(src) == BSL_PLACEHOLDER


# ---------------------------------------------------------------------------
# merge_file
# ---------------------------------------------------------------------------


class TestMergeFile:
    def test_merges_code_back(self, tmp_path):
        base = tmp_path / "module"
        bsl_path = tmp_path / "module.bsl"
        _write(base, MODULE_EMPTY)
        _write(bsl_path, BSL_CODE)

        result = merge_file(bsl_path)

        assert result is True
        assert _read(base) == MODULE_CONTENT

    def test_escapes_quotes(self, tmp_path):
        base = tmp_path / "module"
        bsl_path = tmp_path / "module.bsl"
        _write(base, MODULE_EMPTY)
        _write(bsl_path, BSL_CODE_WITH_QUOTE)

        merge_file(bsl_path)

        assert _read(base) == MODULE_CONTENT_WITH_QUOTE

    def test_returns_false_when_base_missing(self, tmp_path):
        bsl_path = tmp_path / "ghost.bsl"
        _write(bsl_path, BSL_CODE)

        assert merge_file(bsl_path) is False

    def test_returns_false_when_no_placeholder(self, tmp_path):
        base = tmp_path / "module"
        bsl_path = tmp_path / "module.bsl"
        _write(base, MODULE_CONTENT)  # already has code, no "" placeholder
        _write(bsl_path, BSL_CODE)

        assert merge_file(bsl_path) is False

    def test_merge_plain_module_file(self, tmp_path):
        """When base is 'module' and contains only placeholder, replace entire file with .bsl."""
        base = tmp_path / "module"
        bsl_path = tmp_path / "module.bsl"
        _write(base, BSL_PLACEHOLDER)
        _write(bsl_path, BSL_CODE)

        result = merge_file(bsl_path)

        assert result is True
        assert _read(base) == BSL_CODE


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


class TestRoundtrip:
    def test_split_then_merge_restores_original(self, tmp_path):
        src = tmp_path / "module"
        _write(src, MODULE_CONTENT)

        split_file(src)
        bsl_path = tmp_path / "module.bsl"
        merge_file(bsl_path)

        assert _read(src) == MODULE_CONTENT

    def test_roundtrip_with_inner_quotes(self, tmp_path):
        src = tmp_path / "module"
        _write(src, MODULE_CONTENT_WITH_QUOTE)

        split_file(src)
        merge_file(tmp_path / "module.bsl")

        assert _read(src) == MODULE_CONTENT_WITH_QUOTE


# ---------------------------------------------------------------------------
# split_dir / merge_dir
# ---------------------------------------------------------------------------


class TestSplitDir:
    def test_processes_module_files(self, tmp_path):
        (tmp_path / "module1").write_text(MODULE_CONTENT, encoding="utf-8-sig")
        (tmp_path / "module2").write_text(MODULE_CONTENT, encoding="utf-8-sig")
        (tmp_path / "version").write_text("{216,0,{80327,0}}", encoding="utf-8-sig")

        count = split_dir(tmp_path)

        assert count == 2
        assert (tmp_path / "module1.bsl").exists()
        assert (tmp_path / "module2.bsl").exists()
        assert not (tmp_path / "version.bsl").exists()

    def test_recurses_into_subdirectory(self, tmp_path):
        sub = tmp_path / "b5b7a1e8-0705-4409-b78b-32500d067116.0"
        sub.mkdir()
        (sub / "info").write_text(MODULE_CONTENT, encoding="utf-8-sig")

        count = split_dir(tmp_path)

        assert count == 1
        assert (sub / "info.bsl").exists()

    def test_skips_existing_bsl_files(self, tmp_path):
        (tmp_path / "already.bsl").write_text(BSL_CODE, encoding="utf-8-sig")

        count = split_dir(tmp_path)

        assert count == 0

    def test_returns_zero_when_nothing_to_extract(self, tmp_path):
        (tmp_path / "versions").write_text("{1,2}", encoding="utf-8-sig")
        assert split_dir(tmp_path) == 0


class TestMergeDir:
    def test_merges_and_deletes_bsl_files(self, tmp_path):
        base = tmp_path / "module"
        bsl_path = tmp_path / "module.bsl"
        _write(base, MODULE_EMPTY)
        _write(bsl_path, BSL_CODE)

        count = merge_dir(tmp_path)

        assert count == 1
        assert not bsl_path.exists()
        assert _read(base) == MODULE_CONTENT

    def test_does_not_delete_on_failed_merge(self, tmp_path):
        bsl_path = tmp_path / "ghost.bsl"
        _write(bsl_path, BSL_CODE)

        count = merge_dir(tmp_path)

        assert count == 0
        assert bsl_path.exists()

    def test_full_roundtrip_via_dir(self, tmp_path):
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "module").write_text(MODULE_CONTENT, encoding="utf-8-sig")

        split_dir(src_dir)

        import shutil

        build_dir = tmp_path / "build"
        shutil.copytree(src_dir, build_dir)
        merge_dir(build_dir)

        assert (build_dir / "module").read_text(encoding="utf-8-sig") == MODULE_CONTENT
        assert not (build_dir / "module.bsl").exists()
        # Original src still has the split form.
        assert (src_dir / "module.bsl").exists()
