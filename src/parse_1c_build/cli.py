from argparse import ArgumentParser

from cjk_commons.logging_ import add_logging_arguments

from parse_1c_build import __version__, build, parse


def get_argparser() -> ArgumentParser:
    """Получить парсер командной строки"""

    parser = ArgumentParser(
        add_help=False,
        description="Parse and build utilities for 1C:Enterprise",
        prog="p1cb",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s, ver. {__version__}",
        help="Show version",
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit",
    )

    add_logging_arguments(parser)

    subparsers = parser.add_subparsers(dest="subparser_name")

    build.add_subparser(subparsers)
    parse.add_subparser(subparsers)

    return parser
