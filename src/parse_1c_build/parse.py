import shutil
import tempfile
from pathlib import Path

from cjk_commons.settings import get_path_attribute
from commons_1c import platform_
from loguru import logger
import questionary

from parse_1c_build import bsl
from parse_1c_build.base import (
    EXTENSIONS_EPF_ERF,
    EXTENSIONS_MD_ERT,
    Processor,
    add_generic_arguments,
)
from parse_1c_build.process_utils import check_silent, run_silent

logger.disable(__name__)

ERR_INPUT_REQUIRED = "Не указан входной путь. Укажите 'input' или '--interactive'"
ERR_INTERACTIVE_NOT_FOUND = "Не найдено подходящих входных файлов для интерактивного выбора"
ERR_INTERACTIVE_CANCELLED = "Интерактивный выбор отменен пользователем"


def _default_output_dir(input_file_path: Path) -> Path:
    """Default output directory: parent / stem_ext_src (e.g. file_epf_src)."""
    ext = input_file_path.suffix[1:]
    return Path(input_file_path.parent, f"{input_file_path.stem}_{ext}_src")


def _input_files_get() -> list[Path]:
    """Возвращает список входных файлов для интерактивного выбора."""
    extensions = {*EXTENSIONS_EPF_ERF, *EXTENSIONS_MD_ERT}
    file_paths = [
        file_path
        for file_path in Path.cwd().rglob("*")
        if file_path.is_file() and file_path.suffix.lower() in extensions
    ]
    return sorted(file_paths)


def _input_file_select_interactive(file_paths: list[Path]) -> Path | None:
    """Интерактивно выбирает входной файл для разбора."""
    if not file_paths:
        raise Exception(ERR_INTERACTIVE_NOT_FOUND)

    try:
        selected = questionary.select(
            "Выберите файл для парсинга",
            choices=[
                questionary.Choice(
                    title=str(path.relative_to(Path.cwd())),
                    value=path,
                )
                for path in file_paths
            ],
            qmark="parse",
        ).ask()
    except KeyboardInterrupt as exc:
        raise Exception(ERR_INTERACTIVE_CANCELLED) from exc

    if selected is None:
        raise Exception(ERR_INTERACTIVE_CANCELLED)

    return selected


class Parser(Processor):
    def get_1c_exe_file_path(self, **kwargs) -> Path:
        return get_path_attribute(
            kwargs,
            "1c_file_path",
            default_path=platform_.get_last_1c_exe_file_fullpath(),
            is_dir=False,
        )

    def get_ib_dir_path(self, **kwargs) -> Path:
        return get_path_attribute(
            kwargs, "ib_dir_path", self.settings, "ib_dir", Path("IB"), create_dir=False
        )

    def get_v8_reader_file_path(self, **kwargs) -> Path:
        return get_path_attribute(
            kwargs,
            "v8reader_file_path",
            self.settings,
            "v8reader_file",
            Path("V8Reader/V8Reader.epf"),
            False,
        )

    def _run_epf_erf(
        self,
        input_file_path: Path,
        output_dir_path: Path,
        raw: bool,
    ) -> None:
        """Parse EPF/ERF: V8Reader (bat) or v8unpack -P, then optionally bsl.split_dir."""
        if self.use_reader:
            self._run_v8reader(input_file_path, output_dir_path)
        else:
            self._run_v8unpack_parse(input_file_path, output_dir_path, raw)
        logger.info(f"'{input_file_path}' parsed to '{output_dir_path}'")

    def _run_v8reader(self, input_file_path: Path, output_dir_path: Path) -> None:
        """Run V8Reader via batch file (1C + EPF)."""
        with tempfile.NamedTemporaryFile(
            "w", suffix=".bat", delete=False, encoding="cp866"
        ) as bat_file:
            bat_file.write("@echo off\n")
            command = (
                f'/C "decompile;pathToCF;{input_file_path};pathOut;{output_dir_path};'
                'shutdown;convert-mxl2txt;"'
            )
            bat_file.write(
                f'"{self.get_1c_exe_file_path()}" /F "{self.get_ib_dir_path()}" '
                f'/DisableStartupMessages /Execute "{self.get_v8_reader_file_path()}" '
                f"{command}\n"
            )
        try:
            exit_code = run_silent([bat_file.name])
            if exit_code:
                raise Exception(
                    f"parsing '{input_file_path}' with V8Reader failed",
                    exit_code,
                )
        finally:
            Path(bat_file.name).unlink(missing_ok=True)

    def _run_v8unpack_parse(
        self,
        input_file_path: Path,
        output_dir_path: Path,
        raw: bool,
    ) -> None:
        """Run v8unpack -P and optionally bsl.split_dir."""
        args = [
            str(self.get_v8_unpack_file_path()),
            "-P",
            str(input_file_path),
            str(output_dir_path),
        ]
        check_silent(args)
        if not raw:
            bsl.split_dir(output_dir_path)

    def _run_md_ert(
        self,
        input_file_path: Path,
        output_dir_path: Path,
    ) -> None:
        """Parse MD/ERT via gcomp -d -F ... -DD ..."""
        work_path = input_file_path
        temp_dir: Path | None = None
        if input_file_path.suffix.lower() == ".md":
            temp_dir = Path(tempfile.mkdtemp())
            work_path = temp_dir / input_file_path.name
            shutil.copyfile(str(input_file_path), str(work_path))
        try:
            args = [
                str(self.get_gcomp_file_path()),
                "-d",
                "-F",
                str(work_path),
                "-DD",
                str(output_dir_path),
            ]
            check_silent(args)
        finally:
            if temp_dir is not None and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info(f"'{input_file_path}' parsed to '{output_dir_path}'")

    def run(
        self,
        input_file_path: Path,
        output_dir_path: Path | None = None,
        raw: bool = False,
    ) -> None:
        """Разбирает обработку на исходные файлы"""
        suffix = input_file_path.suffix.lower()
        if output_dir_path is None:
            output_dir_path = _default_output_dir(input_file_path)

        if suffix in EXTENSIONS_EPF_ERF:
            self._run_epf_erf(input_file_path, output_dir_path, raw)
        elif suffix in EXTENSIONS_MD_ERT:
            self._run_md_ert(input_file_path, output_dir_path)
        else:
            raise Exception("Undefined input file type")


def _get_run_kwargs(args) -> dict:
    """Build run() kwargs from parsed CLI args."""
    input_file_path = Path(args.input) if args.input else None
    if args.interactive:
        input_file_path = _input_file_select_interactive(_input_files_get())

    if input_file_path is None:
        raise Exception(ERR_INPUT_REQUIRED)

    return {
        "input_file_path": input_file_path,
        "output_dir_path": None if args.output is None else Path(args.output),
        "raw": args.raw,
    }


def run(args) -> None:
    """Запустить"""
    from parse_1c_build.cli_runner import run_subcommand

    run_subcommand(Parser, args, _get_run_kwargs)


def add_subparser(subparsers) -> None:
    """Добавить подпарсер"""
    desc = "Parse 1C:Enterprise file in a directory"
    subparser = subparsers.add_parser(
        Path(__file__).stem,
        add_help=False,
        description=desc,
        help=desc,
    )
    subparser.set_defaults(func=run)
    add_generic_arguments(subparser)
    subparser.add_argument(
        "-r",
        "--raw",
        action="store_true",
        help="Parse to raw source files",
    )
