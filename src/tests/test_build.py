from pathlib import Path

import pytest

from parse_1c_build.build import run as build_run
from parse_1c_build.cli import get_argparser


@pytest.fixture()
def test():
    parser = get_argparser()

    return parser


def test_build_1(test, tmpdir):
    parser = test

    temp_file_path = Path(tmpdir.join("test.epf"))
    args = parser.parse_args(f"build tests/data/test_epf_src {temp_file_path}".split())
    build_run(args)

    assert temp_file_path.exists()
    assert temp_file_path.suffix == ".epf"


def test_build_2(test, tmpdir):
    parser = test

    temp_file_path = Path(tmpdir.join("test.erf"))
    args = parser.parse_args(f"build tests/data/test_epf_src {temp_file_path}".split())
    build_run(args)

    assert temp_file_path.exists()
    assert temp_file_path.suffix == ".erf"


def test_build_3(test, tmpdir):
    with pytest.raises(SystemExit) as exc:
        parser = test

        temp_file_path = Path(tmpdir.join("test"))
        args = parser.parse_args(
            f"build tests/data/test_epf_src {temp_file_path}".split()
        )
        build_run(args)

        assert e.type == SystemExit
        assert e.value.code == 1
