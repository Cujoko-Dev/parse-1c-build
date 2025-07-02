import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cjk_commons.settings import get_path_attribute
from commons_1c import platform_
from loguru import logger

from parse_1c_build.base import Processor, add_generic_arguments

logger.disable(__name__)


class Parser(Processor):
    def get_1c_exe_file_path(self, **kwargs) -> Path:
        result = get_path_attribute(
            kwargs,
            "1c_file_path",
            default_path=platform_.get_last_1c_exe_file_fullpath(),
            is_dir=False,
        )
        return result

    def get_ib_dir_path(self, **kwargs) -> Path:
        result = get_path_attribute(
            kwargs, "ib_dir_path", self.settings, "ib_dir", Path("IB"), create_dir=False
        )
        return result

    def get_v8_reader_file_path(self, **kwargs) -> Path:
        result = get_path_attribute(
            kwargs,
            "v8reader_file_path",
            self.settings,
            "v8reader_file",
            Path("V8Reader/V8Reader.epf"),
            False,
        )
        return result

    def run(self, input_file_path: Path, output_dir_path: Path = None) -> None:
        """Разбирает обработку на исходные файлы"""

        input_file_path_suffix_lower = input_file_path.suffix.lower()

        if output_dir_path is None:
            output_dir_path = Path(
                input_file_path.parent,
                input_file_path.stem + "_" + input_file_path.suffix[1:] + "_src",
            )

        if input_file_path_suffix_lower in [".epf", ".erf"]:
            if self.use_reader:
                with tempfile.NamedTemporaryFile(
                    "w", suffix=".bat", delete=False, encoding="cp866"
                ) as bat_file:
                    bat_file.write("@echo off\n")

                    command = f'/C "decompile;pathToCF;{input_file_path};pathOut;{output_dir_path};shutdown;convert-mxl2txt;"'

                    bat_file.write(
                        f'"{self.get_1c_exe_file_path()}" /F "{self.get_ib_dir_path()}" /DisableStartupMessages /Execute "{self.get_v8_reader_file_path()}" {command}'
                    )

                Path(bat_file.name).unlink()
            else:
                args_au = [
                    str(self.get_v8_unpack_file_path()),
                    "-P",
                    str(input_file_path),
                    str(output_dir_path),
                ]
                exit_code = subprocess.check_call(args_au, stdout=open(os.devnull, "w"))

                if exit_code:
                    raise Exception(f"parsing '{input_file_path}' failed", exit_code)

            logger.info(f"'{input_file_path}' parsed to '{output_dir_path}'")
        elif input_file_path_suffix_lower in [".md", ".ert"]:
            input_file_path_ = input_file_path  # todo

            if input_file_path_suffix_lower == ".md":
                temp_dir_path = Path(tempfile.mkdtemp())
                input_file_path_ = Path(temp_dir_path, input_file_path_.name)
                shutil.copyfile(str(input_file_path), str(input_file_path_))

            args_au = [
                str(self.get_gcomp_file_path()),
                "-d",
                "-F",
                str(input_file_path_),
                "-DD",
                str(output_dir_path),
            ]

            exit_code = subprocess.check_call(args_au, stdout=open(os.devnull, "w"))

            if exit_code:
                raise Exception(f"parsing '{input_file_path}' failed", exit_code)

            logger.info(f"'{input_file_path}' parsed to '{output_dir_path}'")
        else:
            raise Exception("Undefined input file type")


def run(args) -> None:
    """Запустить"""

    logger.enable("cjk_commons")
    logger.enable("commons_1c")
    logger.enable(__name__)

    try:
        processor = Parser()

        # Args
        input_file_path = Path(args.input[0])
        output_dir_path = None if args.output is None else Path(args.output)
        processor.run(input_file_path, output_dir_path)
    except Exception as exc:
        logger.exception(exc)
        sys.exit(1)


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
