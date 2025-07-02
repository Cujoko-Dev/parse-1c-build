from pathlib import Path

import pytest

from parse_1c_build.cli import get_argparser
from parse_1c_build.parse import run as parse_run


@pytest.fixture()
def test(request):
    return get_argparser()


def test_parse(test, tmpdir):
    parser = test

    temp_dir_path = Path(tmpdir)
    args = parser.parse_args(f"parse tests/data/test.epf {temp_dir_path}".split())

    parse_run(args)

    assert Path(temp_dir_path, "root").exists()
