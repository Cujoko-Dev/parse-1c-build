# -*- coding: utf-8 -*-
from argparse import ArgumentParser
from configparser import RawConfigParser
from pathlib import Path
import shutil
import subprocess
import tempfile

from appdirs import site_data_dir, user_data_dir
from commons_1c import get_last_1c_exe_file_path

__version__ = '2.5.6'

APP_AUTHOR = 'util-1c'
APP_NAME = 'parse-1c-build'


class Processor:
    def __init__(self) -> None:
        self.argparser = ArgumentParser()

        self.argparser.add_argument('-v', '--version', action='version', version='%(prog)s, ver. {}'.format(
            __version__))
        self.argparser.add_argument('input', nargs=1)
        self.argparser.add_argument('output', nargs='?')

        settings_file_path = Path('settings.ini')
        if not settings_file_path.is_file():
            settings_file_path = Path(user_data_dir(APP_NAME, APP_AUTHOR, roaming=True)) / settings_file_path.name
            if not settings_file_path.is_file():
                settings_file_path = Path(site_data_dir(APP_NAME, APP_AUTHOR)) / settings_file_path.name
                if not settings_file_path.is_file():
                    raise SettingsException('Settings file does not exist!')

        self.settings = RawConfigParser()
        self.settings.optionxform = str
        self.settings.read(str(settings_file_path), 'utf-8')

        self.settings_general = self.settings['General']

        self.last_1c_exe_file_path = None
        if '1C' in self.settings_general:
            self.last_1c_exe_file_path = Path(self.settings_general['1C'])
        if self.last_1c_exe_file_path is None or not self.last_1c_exe_file_path.is_file():
            self.last_1c_exe_file_path = get_last_1c_exe_file_path()
            if self.last_1c_exe_file_path is None:
                raise SettingsException('1C:Enterprise 8 does not exist!')

        self.ib_dir_path = Path(self.settings_general['IB'])
        if not self.ib_dir_path.is_dir():
            raise SettingsException('Service information base does not exist!')

        self.v8_reader_file_path = Path(self.settings_general['V8Reader'])
        if not self.v8_reader_file_path.is_file():
            raise SettingsException('V8Reader does not exist!')

        self.v8_unpack_file_path = Path(self.settings_general['V8Unpack'])
        if not self.v8_unpack_file_path.is_file():
            raise SettingsException('V8Unpack does not exist!')

        self.gcomp_file_path = Path(self.settings_general['GComp'])
        if not self.gcomp_file_path.is_file():
            raise SettingsException('GComp does not exist!')

    def run(self) -> None:
        pass


class Parser(Processor):
    def parse(self, input_file_path: Path, output_dir_path: Path) -> None:
        with tempfile.NamedTemporaryFile('w', encoding='cp866', suffix='.bat', delete=False) as bat_file:
            bat_file.write('@echo off\n')
            input_file_path_suffix_lower = input_file_path.suffix.lower()
            if input_file_path_suffix_lower in ['.epf', '.erf']:
                bat_file.write('"{}" /F"{}" /DisableStartupMessages /Execute"{}" {}'.format(
                    str(self.last_1c_exe_file_path),
                    str(self.ib_dir_path),
                    str(self.v8_reader_file_path),
                    '/C"decompile;pathtocf;{};pathout;{};shutdown;convert-mxl2txt;"'.format(
                        str(input_file_path),
                        str(output_dir_path)
                    )
                ))
            elif input_file_path_suffix_lower in ['.ert', '.md']:
                input_file_path_ = input_file_path

                if input_file_path_suffix_lower == '.md':  # fixme Тут что-то непонятное и скорее всего неработоспособное
                    temp_dir_name = tempfile.mkdtemp()
                    input_file_path_ = Path(shutil.copy(str(input_file_path_), temp_dir_name))

                bat_file.write('"{}" -d -F "{}" -DD "{}"'.format(
                    str(self.gcomp_file_path),
                    str(input_file_path_),
                    str(output_dir_path)
                ))

        exit_code = subprocess.check_call(['cmd.exe', '/C', str(bat_file.name)])
        if not exit_code == 0:
            raise Exception('Parsing "{}" is failed!'.format(str(input_file_path)))

        Path(bat_file.name).unlink()

    def run(self) -> None:
        args = self.argparser.parse_args()

        input_file_path = Path(args.input[0])

        if args.output is None:
            output_dir_path = input_file_path.stem + '_' + input_file_path.suffix[1:] + '_src'
        else:
            output_dir_path = Path(args.output)

        self.parse(input_file_path, output_dir_path)


class Builder(Processor):
    @staticmethod
    def get_temp_source_dir_path(input_dir_path: Path) -> Path:
        temp_source_dir_path = Path(tempfile.mkdtemp())

        renames_file_path = input_dir_path / 'renames.txt'

        with renames_file_path.open(encoding='utf-8-sig') as file:
            for line in file:
                names = line.split('-->')

                new_path = temp_source_dir_path / names[0].strip()
                new_dir_path = new_path.parent

                if not new_dir_path.is_dir():
                    new_dir_path.mkdir(parents=True)

                old_path = input_dir_path / names[1].strip()

                if old_path.is_dir():
                    new_path = temp_source_dir_path / names[0].strip()
                    shutil.copytree(str(old_path), str(new_path))
                else:
                    shutil.copy(str(old_path), str(new_path))

        return temp_source_dir_path

    def build_raw(self, temp_source_dir_path: Path, output_file_path: Path) -> None:
        exit_code = subprocess.check_call([
            str(self.v8_unpack_file_path),
            '-B',
            str(temp_source_dir_path),
            str(output_file_path)
        ])

        if not exit_code == 0:
            raise Exception('Building "{}" is failed!'.format(str(output_file_path)))

    def build(self, input_dir_path: Path, output_file_path: Path) -> None:
        temp_source_dir_path = Builder.get_temp_source_dir_path(input_dir_path)

        self.build_raw(temp_source_dir_path, output_file_path)

        shutil.rmtree(str(temp_source_dir_path))

    def run(self) -> None:
        args = self.argparser.parse_args()

        input_dir_path = Path(args.input[0])

        if args.output is None:
            output_file_name = input_dir_path.name.rpartition('_')[0]
            parts = output_file_name.rpartition('_')

            output_file_path = Path('{}.{}'.format(parts[0], parts[2]))
        else:
            output_file_path = Path(args.output)

        self.build(input_dir_path, output_file_path)


class SettingsException(Exception):
    pass


def parse() -> None:
    Parser().run()


def build() -> None:
    Builder().run()
