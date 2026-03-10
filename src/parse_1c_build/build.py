import shutil
import tempfile
from pathlib import Path

from loguru import logger

from parse_1c_build import bsl
from parse_1c_build.base import (
    EXTENSIONS_EPF_ERF,
    EXTENSIONS_MD_ERT,
    Processor,
    add_generic_arguments,
)
from parse_1c_build.process_utils import check_silent

logger.disable(__name__)


def _resolve_output_path(
    input_dir_path: Path,
    output_path: Path | None,
) -> Path:
    """Resolve output file path from input dir and optional output path."""
    if output_path is not None and not output_path.is_dir():
        return output_path
    parent = output_path if (output_path is not None and output_path.is_dir()) else input_dir_path.parent
    # input_dir_path.name is like "name_epf_src" or "name_ert_src"
    name_with_ext = input_dir_path.name.rpartition("_")[0]
    name, _, ext = name_with_ext.rpartition("_")
    return Path(parent, f"{name}.{ext}")


def _backup_existing(path: Path) -> None:
    """Rename existing file to path.name.1.bak, .2.bak, ..."""
    n = 1
    while True:
        bak = path.parent / f"{path.name}.{n}.bak"
        if not bak.exists():
            break
        n += 1
    path.rename(bak)


class Builder(Processor):
    @staticmethod
    def _build_temp_from_renames(input_dir_path: Path) -> Path:
        """Build temp directory from renames.txt (target -> source)."""
        temp_source_dir_path = Path(tempfile.mkdtemp())
        renames_path = input_dir_path / "renames.txt"
        with renames_path.open(encoding="utf-8-sig") as f:
            for line in f:
                if bsl.RENAMES_ARROW not in line:
                    continue
                target_str, source_str = (s.strip() for s in line.split("-->", 1))
                new_path = temp_source_dir_path / target_str
                new_path.parent.mkdir(parents=True, exist_ok=True)
                old_path = input_dir_path / source_str
                if old_path.is_dir():
                    shutil.copytree(old_path, new_path)
                else:
                    shutil.copy2(old_path, new_path)
        return temp_source_dir_path

    def _get_source_dir_for_epf_build(self, input_dir_path: Path) -> Path:
        """Return path to source directory for v8unpack -B (temp or input_dir_path)."""
        if self.use_reader:
            return self._build_temp_from_renames(input_dir_path)
        if bsl.has_bin_layout(input_dir_path):
            temp_parent = Path(tempfile.mkdtemp())
            return bsl.prepare_temp_for_build(input_dir_path, temp_parent)
        bsl_files = list(input_dir_path.rglob("*.bsl"))
        if bsl_files:
            temp_parent = Path(tempfile.mkdtemp())
            temp_source = temp_parent / input_dir_path.name
            shutil.copytree(input_dir_path, temp_source)
            bsl.merge_dir(temp_source)
            return temp_source
        return input_dir_path

    def _run_epf_erf_build(
        self,
        input_dir_path: Path,
        output_file_path: Path,
    ) -> None:
        """Build EPF/ERF from source directory via v8unpack -B."""
        source_dir = self._get_source_dir_for_epf_build(input_dir_path)
        args = [str(self.get_v8_unpack_file_path()), "-B", str(source_dir), str(output_file_path)]
        check_silent(args)
        logger.info(f"'{output_file_path}' built from '{input_dir_path}'")

    def _run_md_ert_build(
        self,
        input_dir_path: Path,
        output_file_path: Path,
    ) -> None:
        """Build MD/ERT via gcomp -c -F ... -DD ..."""
        suffix = output_file_path.suffix.lower()
        args = [str(self.get_gcomp_file_path())]
        if suffix == ".ert":
            args.append("--external-report")
        elif suffix == ".md":
            args.append("--meta-data")
        args += ["-c", "-F", str(output_file_path), "-DD", str(input_dir_path)]
        check_silent(args)
        logger.info(f"'{output_file_path}' built from '{input_dir_path}'")

    def run(
        self,
        input_dir_path: Path,
        output_path: Path | None = None,
        do_not_backup: bool = False,
    ) -> None:
        """Собирает обработку из исходных файлов"""
        output_file_path = _resolve_output_path(input_dir_path, output_path)
        if not do_not_backup and output_file_path.exists() and output_file_path.is_file():
            _backup_existing(output_file_path)

        suffix = output_file_path.suffix.lower()
        if suffix in EXTENSIONS_EPF_ERF:
            self._run_epf_erf_build(input_dir_path, output_file_path)
        elif suffix in EXTENSIONS_MD_ERT:
            self._run_md_ert_build(input_dir_path, output_file_path)
        else:
            raise Exception("Undefined output file type")


def _get_run_kwargs(args) -> dict:
    """Build run() kwargs from parsed CLI args."""
    return {
        "input_dir_path": Path(args.input[0]),
        "output_path": None if args.output is None else Path(args.output),
        "do_not_backup": args.do_not_backup,
    }


def run(args) -> None:
    """Запустить"""
    from parse_1c_build.cli_runner import run_subcommand

    run_subcommand(Builder, args, _get_run_kwargs)


def add_subparser(subparsers) -> None:
    """Добавить подпарсер"""
    desc = "Build files in a directory to 1C:Enterprise file"
    subparser = subparsers.add_parser(
        Path(__file__).stem,
        add_help=False,
        description=desc,
        help=desc,
    )
    subparser.set_defaults(func=run)
    add_generic_arguments(subparser)
    subparser.add_argument(
        "-x",
        "--do-not-backup",
        action="store_true",
        help="Do not backup 1C-file before building",
    )
