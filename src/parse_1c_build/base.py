from pathlib import Path

from cjk_commons.settings import get_attribute, get_path_attribute, get_settings

from parse_1c_build.__about__ import APP_AUTHOR, APP_NAME


class Processor:
    """Процессор"""

    def __init__(self, **kwargs):
        settings_file_path = get_path_attribute(
            kwargs,
            "settings_file_path",
            default_path=Path("settings.yaml"),
            is_dir=False,
            check_if_exists=False,
        )
        self.settings = get_settings(
            settings_file_path, app_name=APP_NAME, app_author=APP_AUTHOR
        )

        self.use_reader = get_attribute(
            kwargs, "use_reader", self.settings, "use_reader", default=False
        )

    def get_v8_unpack_file_path(self, **kwargs) -> Path:
        return get_path_attribute(
            kwargs,
            "v8unpack_file_path",
            self.settings,
            "v8unpack_file",
            Path("V8Unpack/V8Unpack.exe"),
            False,
        )

    def get_gcomp_file_path(self, **kwargs) -> Path:
        return get_path_attribute(
            kwargs,
            "gcomp_file_path",
            self.settings,
            "gcomp_file",
            Path("GComp/Release/gcomp.exe"),
            False,
        )


def add_generic_arguments(subparser) -> None:
    subparser.add_argument(
        "-r",
        "--use-reader",
        action="store_true",
        help="Parse or build with V8Reader",
    )
    subparser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit",
    )

    # todo Добавить help
    subparser.add_argument("input", nargs=1)

    # todo Добавить help
    subparser.add_argument("output", nargs="?")
