import sys

from cjk_commons.logging_ import add_loggers

from parse_1c_build import logger
from parse_1c_build.cli import get_argparser


def run() -> None:
    """Запустить"""

    argparser = get_argparser()
    args = argparser.parse_args(sys.argv[1:])

    add_loggers(args, logger)

    args.func(args)
