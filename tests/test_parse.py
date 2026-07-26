from pathlib import Path

import pytest

from parse_1c_build.cli import get_argparser
from parse_1c_build.cf_layout import _extract_plain_module
from parse_1c_build.parse import run as parse_run


@pytest.fixture()
def test(request):
    return get_argparser()


def test_parse(test, tmpdir):
    parser = test

    temp_dir_path = Path(tmpdir)
    args = parser.parse_args(f"parse tests/fixtures/test.epf {temp_dir_path}".split())

    parse_run(args)

    # With named BSL + bin layout, unpacked structure is under bin/
    assert (temp_dir_path / "bin" / "root").exists()


def test_extract_plain_module_keeps_password_protected_payload(tmp_path: Path) -> None:
    module_path = tmp_path / "text"
    protected_payload = b"\xf9\x30\xa2\xcd\x00\xff"
    module_path.write_bytes(protected_payload)
    bsl_path = tmp_path / "ProtectedModule.bsl"

    assert _extract_plain_module(module_path, bsl_path) is False
    assert module_path.read_bytes() == protected_payload
    assert not bsl_path.exists()
