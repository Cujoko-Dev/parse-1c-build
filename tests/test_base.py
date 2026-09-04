import sys
from pathlib import Path

import pytest

from parse_1c_build.base import Processor, bundled_v8unpack_path


def test_processor_1():
    with pytest.raises(Exception) as exc:
        Processor(settings_file_path=Path("tests/fixtures/settings.yaml"))
        assert exc == "There is no GComp in settings"


def test_processor_2():
    with pytest.raises(Exception) as exc:
        Processor(gcomp_file_path=Path(""))  # todo
        assert exc == "GComp does not exist"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows vendor binary")
def test_vendor_v8unpack_exists() -> None:
    path = bundled_v8unpack_path()
    assert path is not None
    assert path.is_file()


def test_bundled_v8unpack_wins_over_settings(tmp_path: Path) -> None:
    bundled = bundled_v8unpack_path()
    if bundled is None:
        pytest.skip("bundled v8unpack is not present")
    fake = tmp_path / "other-v8unpack.exe"
    fake.write_bytes(b"")
    settings = tmp_path / "settings.yaml"
    settings.write_text(f"v8unpack_file: {fake.as_posix()}\n", encoding="utf-8")
    processor = Processor(settings_file_path=settings)
    assert processor.get_v8_unpack_file_path() == bundled


def test_explicit_v8unpack_overrides_bundled(tmp_path: Path) -> None:
    custom = tmp_path / "custom-v8unpack.exe"
    custom.write_bytes(b"")
    processor = Processor(settings_file_path=tmp_path / "missing.yaml")
    assert processor.get_v8_unpack_file_path(v8unpack_file_path=custom) == custom
