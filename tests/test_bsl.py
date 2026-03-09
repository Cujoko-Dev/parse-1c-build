"""Tests for parse_1c_build.bsl — BSL extraction / merge utilities.

Tests use sample data from tests/data/test_epf_src/ as the reference layout:
- Managed form: single file UUID.0 with BSL embedded in tuple (e.g. faa87ad8-...0).
- Object/form as directory: UUID.0/module (plain BSL), UUID.0/form (structure), etc.
- File "text" — plain BSL; file "info" — tuple {3,1,0,"",0} (empty module).
"""

import shutil
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

# Path to reference EPF source (read-only samples).
TESTS_DIR = Path(__file__).resolve().parent
TEST_EPF_SRC = TESTS_DIR / "data" / "test_epf_src"


def _read(path: Path, encoding: str = "utf-8-sig") -> str:
    return path.read_text(encoding=encoding)


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _write(path: Path, text: str, encoding: str = "utf-8-sig") -> None:
    path.write_text(text, encoding=encoding)


# ---------------------------------------------------------------------------
# Sample content from test_epf_src
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_plain_bsl():
    """Plain BSL from test_epf_src (e.g. UUID.0/module or UUID.0/text)."""
    path = TEST_EPF_SRC / "00884b3a-f65e-4956-8e79-e69cfac8c10e.0" / "module"
    if not path.exists():
        pytest.skip("test_epf_src/00884b3a.../module not found")
    return _read(path)


@pytest.fixture(scope="module")
def sample_text_bsl():
    """Plain BSL from test_epf_src UUID.0/text (slightly shorter than module)."""
    path = TEST_EPF_SRC / "b5b7a1e8-0705-4409-b78b-32500d067116.0" / "text"
    if not path.exists():
        pytest.skip("test_epf_src/b5b7a1e8.../text not found")
    return _read(path)


@pytest.fixture(scope="module")
def sample_info_empty_tuple():
    """Empty module tuple from test_epf_src UUID.0/info."""
    path = TEST_EPF_SRC / "b5b7a1e8-0705-4409-b78b-32500d067116.0" / "info"
    if not path.exists():
        pytest.skip("test_epf_src/b5b7a1e8.../info not found")
    return _read(path)


@pytest.fixture(scope="module")
def sample_managed_form_path():
    """Path to managed form file with embedded BSL (faa87ad8...0)."""
    path = TEST_EPF_SRC / "faa87ad8-a8e9-4e88-8a2c-739a776cfad5.0"
    if not path.exists():
        pytest.skip("test_epf_src/faa87ad8...0 not found")
    return path


@pytest.fixture
def copied_epf_src(tmp_path):
    """Copy test_epf_src to tmp_path for tests that modify files."""
    dest = tmp_path / "epf_src"
    shutil.copytree(TEST_EPF_SRC, dest)
    return dest


# ---------------------------------------------------------------------------
# _find_empty_string
# ---------------------------------------------------------------------------


class TestFindEmptyString:
    def test_finds_empty_string_in_info_tuple(self, sample_info_empty_tuple):
        content = sample_info_empty_tuple
        result = _find_empty_string(content)
        assert result is not None
        start, end = result
        assert start == end
        assert content[start - 1] == '"'
        assert content[end] == '"'

    def test_returns_none_when_no_empty_string(self):
        assert _find_empty_string('{3,1,0,"код",0}') is None

    def test_finds_first_empty_string(self):
        content = '{3,1,0,"",0,""}'
        result = _find_empty_string(content)
        assert result is not None
        start, end = result
        assert start == end
        assert content[start - 1 : end + 1] == '""'


# ---------------------------------------------------------------------------
# split_file — образцы из test_epf_src
# ---------------------------------------------------------------------------


class TestSplitFile:
    def test_plain_module_extracts_to_bsl(self, tmp_path, sample_plain_bsl):
        """Файл 'module' с plain BSL (как в 00884b3a...0/module) — код в .bsl, сам файл → placeholder."""
        src = tmp_path / "module"
        _write(src, sample_plain_bsl)

        result = split_file(src)

        assert result is True
        assert _read(src) == BSL_PLACEHOLDER
        bsl_path = tmp_path / "module.bsl"
        assert bsl_path.exists()
        assert _read(bsl_path) == sample_plain_bsl

    def test_plain_text_extracts_to_bsl(self, tmp_path, sample_text_bsl):
        """Файл 'text' с plain BSL (как в b5b7a1e8...0/text) — код в .bsl."""
        src = tmp_path / "text"
        _write(src, sample_text_bsl)

        result = split_file(src)

        assert result is True
        assert (tmp_path / "text.bsl").exists()
        assert _read(tmp_path / "text.bsl") == sample_text_bsl

    def test_managed_form_extracts_bsl(self, tmp_path, sample_managed_form_path):
        """Управляемая форма (UUID.0) с BSL в кортеже — извлечение в .bsl, в файле placeholder."""
        src = tmp_path / sample_managed_form_path.name
        src.write_bytes(sample_managed_form_path.read_bytes())

        result = split_file(src)

        assert result is True
        bsl_path = tmp_path / (src.name + ".bsl")
        assert bsl_path.exists()
        # В образце модуль формы содержит &НаКлиенте и процедуры
        content = _read(bsl_path)
        assert "&НаКлиенте" in content
        assert "Процедура А()" in content
        assert "НекийКод = 2" in content

    def test_empty_info_returns_false(self, tmp_path, sample_info_empty_tuple):
        """Файл 'info' с пустым кортежем {3,1,0,\"\",0} — не извлекаем, .bsl не создаётся."""
        src = tmp_path / "info"
        _write(src, sample_info_empty_tuple)

        assert split_file(src) is False
        assert not (tmp_path / "info.bsl").exists()
        assert _read(src) == sample_info_empty_tuple

    def test_returns_false_for_base64(self, tmp_path):
        base64_content = "{4,\n{#base64:77u/PD94bWwgdmVyc2lvbj0iMS4wIj8+}\n}"
        src = tmp_path / "layout"
        _write(src, base64_content)

        assert split_file(src) is False
        assert not (tmp_path / "layout.bsl").exists()

    def test_returns_false_for_xml_string(self, tmp_path):
        xml_content = '{1,0,"<xml><tag>value</tag></xml>",1}'
        src = tmp_path / "xmlfile"
        _write(src, xml_content)

        assert split_file(src) is False

    def test_skips_bsl_file(self, tmp_path, sample_plain_bsl):
        """Файл .bsl не обрабатывается (нет кортежа 1С)."""
        src = tmp_path / "module.bsl"
        _write(src, sample_plain_bsl)

        assert split_file(src) is False

    def test_ordinary_form_file_skipped(self, tmp_path):
        """Файл 'form' — обычная форма, модуля формы в файле нет (правило bsl-forms)."""
        form_content = (
            "{0,\n0,\n"
            '"Процедура ПриОткрытии()\n\tСообщить(1);\nКонецПроцедуры\n",\n'
            "0}\n"
        )
        src = tmp_path / "form"
        _write(src, form_content)

        result = split_file(src)

        assert result is False
        assert not (tmp_path / "form.bsl").exists()
        assert _read(src) == form_content

    def test_managed_form_moxcel_skipped(self, tmp_path):
        """Управляемая форма с префиксом MOXCEL — без BSL модуля, не извлекаем."""
        src = tmp_path / "3a3209bb-e006-49cf-89f4-92fd41c3adf5.0"
        _write(src, "MOXCEL\t \n???{8,1,12,\n")

        result = split_file(src)

        assert result is False
        assert not (tmp_path / "3a3209bb-e006-49cf-89f4-92fd41c3adf5.0.bsl").exists()


# ---------------------------------------------------------------------------
# merge_file
# ---------------------------------------------------------------------------


class TestMergeFile:
    def test_merges_plain_module_back(self, tmp_path, sample_plain_bsl):
        """Слияние .bsl обратно в 'module' с placeholder — весь файл заменяется кодом."""
        base = tmp_path / "module"
        bsl_path = tmp_path / "module.bsl"
        _write(base, BSL_PLACEHOLDER)
        _write(bsl_path, sample_plain_bsl)

        result = merge_file(bsl_path)

        assert result is True
        assert _read(base) == sample_plain_bsl

    def test_merges_into_tuple_with_placeholder(self, tmp_path, sample_text_bsl):
        """Базовый файл с placeholder в кортеже — вставляем код из .bsl (escape кавычек)."""
        base = tmp_path / "info"
        bsl_path = tmp_path / "info.bsl"
        content_with_placeholder = '{3,1,0,"' + BSL_PLACEHOLDER + '",0}'
        _write(base, content_with_placeholder)
        _write(bsl_path, sample_text_bsl)

        result = merge_file(bsl_path)

        assert result is True
        merged = _read(base)
        assert "Процедура А()" in merged
        assert BSL_PLACEHOLDER not in merged

    def test_returns_false_when_base_missing(self, tmp_path, sample_plain_bsl):
        bsl_path = tmp_path / "ghost.bsl"
        _write(bsl_path, sample_plain_bsl)

        assert merge_file(bsl_path) is False

    def test_returns_false_when_no_placeholder(self, tmp_path, sample_plain_bsl):
        base = tmp_path / "module"
        bsl_path = tmp_path / "module.bsl"
        _write(base, sample_plain_bsl)
        _write(bsl_path, sample_plain_bsl)

        assert merge_file(bsl_path) is False


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


class TestRoundtrip:
    def test_plain_module_split_then_merge_restores(self, tmp_path, sample_plain_bsl):
        src = tmp_path / "module"
        _write(src, sample_plain_bsl)

        split_file(src)
        merge_file(tmp_path / "module.bsl")

        assert _read(src) == sample_plain_bsl

    def test_managed_form_split_then_merge_restores(self, tmp_path, sample_managed_form_path):
        src = tmp_path / sample_managed_form_path.name
        src.write_bytes(sample_managed_form_path.read_bytes())
        original = _read_bytes(src)

        split_file(src)
        bsl_path = tmp_path / (src.name + ".bsl")
        merge_file(bsl_path)

        assert _read_bytes(src) == original


# ---------------------------------------------------------------------------
# split_dir / merge_dir — на копии test_epf_src
# ---------------------------------------------------------------------------


class TestSplitDir:
    def test_on_epf_src_extracts_expected_files(self, copied_epf_src):
        """split_dir по структуре test_epf_src: 2 управляемые формы (faa87ad8, 47291cc9) + module + text = 4 извлечения."""
        count = split_dir(copied_epf_src)

        assert count == 4
        # Управляемые формы (UUID.0) с BSL в кортеже
        assert (copied_epf_src / "faa87ad8-a8e9-4e88-8a2c-739a776cfad5.0.bsl").exists()
        assert (copied_epf_src / "47291cc9-8ef9-4425-8d37-28bcf15b372d.0.bsl").exists()
        # Каталоги с plain BSL: module, text
        assert (copied_epf_src / "00884b3a-f65e-4956-8e79-e69cfac8c10e.0" / "module.bsl").exists()
        assert (copied_epf_src / "b5b7a1e8-0705-4409-b78b-32500d067116.0" / "text.bsl").exists()
        # info — пустой кортеж, не извлекается
        assert not (copied_epf_src / "b5b7a1e8-0705-4409-b78b-32500d067116.0" / "info.bsl").exists()
        # form — обычная форма, не извлекается
        assert not (copied_epf_src / "00884b3a-f65e-4956-8e79-e69cfac8c10e.0" / "form.bsl").exists()

    def test_skips_existing_bsl_files(self, tmp_path, sample_plain_bsl):
        (tmp_path / "module.bsl").write_text(sample_plain_bsl, encoding="utf-8-sig")

        count = split_dir(tmp_path)

        assert count == 0

    def test_returns_zero_when_nothing_to_extract(self, tmp_path):
        (tmp_path / "versions").write_text("{1,2}", encoding="utf-8-sig")
        assert split_dir(tmp_path) == 0


class TestMergeDir:
    def test_merges_and_deletes_bsl_files(self, tmp_path, sample_plain_bsl):
        base = tmp_path / "module"
        bsl_path = tmp_path / "module.bsl"
        _write(base, BSL_PLACEHOLDER)
        _write(bsl_path, sample_plain_bsl)

        count = merge_dir(tmp_path)

        assert count == 1
        assert not bsl_path.exists()
        assert _read(base) == sample_plain_bsl

    def test_does_not_delete_on_failed_merge(self, tmp_path, sample_plain_bsl):
        bsl_path = tmp_path / "ghost.bsl"
        _write(bsl_path, sample_plain_bsl)

        count = merge_dir(tmp_path)

        assert count == 0
        assert bsl_path.exists()

    def test_full_roundtrip_via_dir(self, copied_epf_src):
        """split_dir по копии test_epf_src, затем merge_dir — исходники восстанавливаются."""
        split_dir(copied_epf_src)

        build_dir = copied_epf_src.parent / "build"
        shutil.copytree(copied_epf_src, build_dir)
        merge_dir(build_dir)

        # Управляемая форма
        ref_managed = TEST_EPF_SRC / "faa87ad8-a8e9-4e88-8a2c-739a776cfad5.0"
        restored_managed = build_dir / "faa87ad8-a8e9-4e88-8a2c-739a776cfad5.0"
        assert restored_managed.read_bytes() == ref_managed.read_bytes()
        assert not (build_dir / "faa87ad8-a8e9-4e88-8a2c-739a776cfad5.0.bsl").exists()

        # module, text
        ref_module = TEST_EPF_SRC / "00884b3a-f65e-4956-8e79-e69cfac8c10e.0" / "module"
        restored_module = build_dir / "00884b3a-f65e-4956-8e79-e69cfac8c10e.0" / "module"
        assert restored_module.read_text(encoding="utf-8-sig") == ref_module.read_text(encoding="utf-8-sig")
        assert not (build_dir / "00884b3a-f65e-4956-8e79-e69cfac8c10e.0" / "module.bsl").exists()

        ref_text = TEST_EPF_SRC / "b5b7a1e8-0705-4409-b78b-32500d067116.0" / "text"
        restored_text = build_dir / "b5b7a1e8-0705-4409-b78b-32500d067116.0" / "text"
        assert restored_text.read_text(encoding="utf-8-sig") == ref_text.read_text(encoding="utf-8-sig")
        assert not (build_dir / "b5b7a1e8-0705-4409-b78b-32500d067116.0" / "text.bsl").exists()

        # Вторая управляемая форма
        ref_47291 = TEST_EPF_SRC / "47291cc9-8ef9-4425-8d37-28bcf15b372d.0"
        restored_47291 = build_dir / "47291cc9-8ef9-4425-8d37-28bcf15b372d.0"
        assert restored_47291.read_bytes() == ref_47291.read_bytes()
        assert not (build_dir / "47291cc9-8ef9-4425-8d37-28bcf15b372d.0.bsl").exists()
