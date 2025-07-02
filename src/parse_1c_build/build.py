import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from loguru import logger

from parse_1c_build.base import Processor, add_generic_arguments

logger.disable(__name__)


class Builder(Processor):
    @staticmethod
    def get_temp_source_dir_path(input_dir_path: Path) -> Path:
        temp_source_dir_path = Path(tempfile.mkdtemp())
        renames_file_path = Path(input_dir_path, "renames.txt")

        with renames_file_path.open(encoding="utf-8-sig") as renames_file:
            for line in renames_file:
                names = line.split("-->")
                new_path = temp_source_dir_path / names[0].strip()
                new_dir_path = Path(new_path).parent

                if not new_dir_path.is_dir():
                    new_dir_path.mkdir(parents=True)

                old_path = Path(input_dir_path, names[1].strip())

                if old_path.is_dir():
                    new_path = Path(temp_source_dir_path, names[0].strip())
                    shutil.copytree(old_path, new_path)
                else:
                    shutil.copy(old_path, new_path)

        return temp_source_dir_path

    def run(
        self,
        input_dir_path: Path,
        output_path: Path = None,
        do_not_backup: bool = False,
    ) -> None:
        """Собирает обработку из исходных файлов"""

        if output_path is None or output_path.is_dir():
            if output_path is None:
                parent = input_dir_path.parent
            else:
                parent = output_path

            output_file_name_and_ext_str = input_dir_path.name.rpartition("_")[0]
            output_file_name_and_ext = output_file_name_and_ext_str.rpartition("_")

            output_file_path = Path(
                parent,
                f"{output_file_name_and_ext[0]}.{output_file_name_and_ext[2]}",
            )
        else:
            output_file_path = output_path

        if not do_not_backup and output_file_path.is_file():
            # Файл уже существует. Нужно переименовать
            n = 1

            while True:
                bak_file_path = Path(
                    output_file_path.parent,
                    output_file_path.name + "." + str(n) + ".bak",
                )
                if bak_file_path.is_file():
                    n += 1
                else:
                    break

            output_file_path.rename(bak_file_path)

        output_file_path_suffix_lower = output_file_path.suffix.lower()

        if output_file_path_suffix_lower in [".epf", ".erf"]:
            args_au = [str(self.get_v8_unpack_file_path()), "-B"]

            if self.use_reader:
                temp_source_dir_path = Builder.get_temp_source_dir_path(input_dir_path)
                args_au += [str(temp_source_dir_path)]
            else:
                args_au += [str(input_dir_path)]

            args_au += [str(output_file_path)]

            exit_code = subprocess.check_call(args_au, stdout=open(os.devnull, "w"))

            if exit_code:
                raise Exception(f"building '{output_file_path}' failed", exit_code)

            logger.info(f"'{output_file_path}' built from '{input_dir_path}'")

        elif output_file_path_suffix_lower in [".md", ".ert"]:
            # todo Может быть такое, что md-файл будет занят, тогда при его записи возникнет ошибка
            args_au = [str(self.get_gcomp_file_path())]

            if output_file_path_suffix_lower == ".ert":
                args_au += ["--external-report"]
            elif output_file_path_suffix_lower == ".md":
                args_au += ["--meta-data"]

            args_au += [
                "-c",
                "-F",
                str(output_file_path),
                "-DD",
                str(input_dir_path),
            ]

            exit_code = subprocess.check_call(args_au, stdout=open(os.devnull, "w"))

            if exit_code:
                raise Exception(f"building '{output_file_path}' failed", exit_code)

            logger.info(f"'{output_file_path}' built from '{input_dir_path}'")

        else:
            raise Exception("Undefined output file type")


def run(args) -> None:
    """Запустить"""

    logger.enable("cjk_commons")
    logger.enable("commons_1c")
    logger.enable(__name__)

    try:
        processor = Builder()

        # Args
        input_dir_path = Path(args.input[0])
        output_file_path = None if args.output is None else Path(args.output)
        processor.run(input_dir_path, output_file_path, args.do_not_backup)
    except Exception as exc:
        logger.exception(exc)
        sys.exit(1)


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
