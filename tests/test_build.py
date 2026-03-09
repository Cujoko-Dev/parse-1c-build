import shutil
from pathlib import Path

import pytest

from parse_1c_build import bsl
from parse_1c_build.build import run as build_run
from parse_1c_build.cli import get_argparser
from parse_1c_build.parse import run as parse_run


def _collect_rel_paths(root: Path) -> set[Path]:
    """Все относительные пути файлов (в т.ч. без расширения: root, version)."""
    out = set()
    for p in root.rglob("*"):
        if p.is_file():
            out.add(p.relative_to(root))
    return out


def _first_byte_diff(a: bytes, b: bytes) -> tuple[int, int | None, int | None]:
    """Индекс первого отличающегося байта и значения в a и b (None если конец)."""
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return (i, int(a[i]), int(b[i]))
    if len(a) != len(b):
        i = min(len(a), len(b))
        return (i, int(a[i]) if i < len(a) else None, int(b[i]) if i < len(b) else None)
    return (-1, None, None)


def compare_raw_dirs(ref_dir: Path, other_dir: Path):
    """
    Сравнить два каталога raw-исходников побайтово.
    Возвращает dict: only_in_ref, only_in_other, differing.
    differing — список кортежей (rel_path, ref_len, other_len, diff_offset, ref_byte, other_byte).
    """
    ref_files = _collect_rel_paths(ref_dir)
    other_files = _collect_rel_paths(other_dir)
    only_in_ref = sorted(ref_files - other_files, key=str)
    only_in_other = sorted(other_files - ref_files, key=str)
    common = ref_files & other_files
    differing = []
    for rel in sorted(common, key=str):
        ref_path = ref_dir / rel
        other_path = other_dir / rel
        if ref_path.is_dir() or other_path.is_dir():
            continue
        ref_bytes = ref_path.read_bytes()
        other_bytes = other_path.read_bytes()
        if ref_bytes != other_bytes:
            offset, rb, ob = _first_byte_diff(ref_bytes, other_bytes)
            differing.append((rel, len(ref_bytes), len(other_bytes), offset, rb, ob))
    return {
        "only_in_ref": only_in_ref,
        "only_in_other": only_in_other,
        "differing": differing,
    }


def _format_raw_diff_report(cmp: dict) -> str:
    lines = []
    if cmp["only_in_ref"]:
        lines.append("Только в образце: " + ", ".join(str(p) for p in cmp["only_in_ref"]))
    if cmp["only_in_other"]:
        lines.append("Только в полученном: " + ", ".join(str(p) for p in cmp["only_in_other"]))
    for rel, rlen, olen, offset, rb, ob in cmp["differing"]:
        detail = f"  {rel}: размеры {rlen} vs {olen}"
        if offset >= 0:
            detail += f", первый различающийся байт @{offset}: образец={rb!r}, получен={ob!r}"
        lines.append(detail)
    return "\n".join(lines)


@pytest.fixture()
def test():
    parser = get_argparser()

    return parser


def test_build_roundtrip_raw_sources_identical(test, tmpdir):
    """
    Разобрать test.epf (без --raw), собрать test_build.epf, разобрать test_build.epf с --raw
    и сравнить raw-исходники с образцовыми tests/data/test_epf_src побайтово.
    При расхождениях проверяем, где ошибка: split_dir (parse) или merge_dir (build).
    """
    parser = test
    tests_dir = Path(__file__).parent
    sample_epf = tests_dir / "data" / "test.epf"
    reference_raw = tests_dir / "data" / "test_epf_src"
    if not sample_epf.is_file():
        pytest.skip(f"Образцовый файл отсутствует: {sample_epf}")
    if not reference_raw.is_dir():
        pytest.skip(f"Образцовые raw-исходники отсутствуют: {reference_raw}")

    tmp = Path(tmpdir)
    parsed_dir = tmp / "test_epf_src"
    built_epf = tmp / "test_build.epf"
    raw_from_built = tmp / "test_build_epf_src"

    # parse test.epf (без --raw) → split-исходники
    args_parse = parser.parse_args(["parse", str(sample_epf), str(parsed_dir)])
    parse_run(args_parse)

    # build → test_build.epf
    args_build = parser.parse_args(["build", str(parsed_dir), str(built_epf), "-x"])
    build_run(args_build)

    # parse test_build.epf с --raw
    args_parse_raw = parser.parse_args(
        ["parse", str(built_epf), str(raw_from_built), "--raw"]
    )
    parse_run(args_parse_raw)

    cmp = compare_raw_dirs(reference_raw, raw_from_built)
    has_diff = (
        bool(cmp["only_in_ref"])
        or bool(cmp["only_in_other"])
        or bool(cmp["differing"])
    )

    if has_diff:
        msg = [
            "Raw-исходники после roundtrip (parse→build→parse --raw) отличаются от образца:",
            _format_raw_diff_report(cmp),
        ]
        # Проверка: ошибка в split/merge (parse или build)?
        ref_copy = tmp / "reference_copy"
        shutil.copytree(reference_raw, ref_copy)
        bsl.split_dir(ref_copy)
        bsl.merge_dir(ref_copy)
        cmp_roundtrip = compare_raw_dirs(reference_raw, ref_copy)
        roundtrip_ok = (
            not cmp_roundtrip["only_in_ref"]
            and not cmp_roundtrip["only_in_other"]
            and not cmp_roundtrip["differing"]
        )
        if not roundtrip_ok:
            msg.append(
                "Проверка split_dir→merge_dir на образце: roundtrip даёт отличия "
                "(ошибка в разборке split_dir и/или сборке merge_dir)."
            )
            msg.append(_format_raw_diff_report(cmp_roundtrip))
        else:
            msg.append(
                "Проверка split_dir→merge_dir на образце: roundtrip побайтово совпадает; "
                "расхождение, вероятно, в сборке/распаковке EPF (v8unpack -B/-P)."
            )
        pytest.fail("\n".join(msg))

    assert not has_diff


def test_build_1(test, tmpdir):
    parser = test

    temp_file_path = Path(tmpdir.join("test.epf"))
    args = parser.parse_args(
        f"build tests/data/test_epf_src {temp_file_path}".split()
    )
    build_run(args)

    assert temp_file_path.exists()
    assert temp_file_path.suffix == ".epf"


def test_build_2(test, tmpdir):
    with pytest.raises(SystemExit) as exc:
        parser = test

        temp_file_path = Path(tmpdir.join("test"))
        args = parser.parse_args(
            f"build tests/data/test_epf_src {temp_file_path}".split(),
        )
        build_run(args)

        assert exc.type == SystemExit
        assert exc.value.code == 1
