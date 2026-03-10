"""Shared CLI subcommand runner: create processor, run with args, handle exceptions."""

import sys
from typing import Any, Callable

from parse_1c_build import logger


def run_subcommand(
    processor_class: type,
    args: Any,
    get_run_kwargs: Callable[[Any], dict],
) -> None:
    """Create processor from args, call run(get_run_kwargs(args)), log and exit on error."""
    logger.enable("cjk_commons")
    logger.enable("commons_1c")
    logger.enable(processor_class.__module__)
    try:
        processor = processor_class(**vars(args))
        processor.run(**get_run_kwargs(args))
    except Exception as exc:
        logger.exception(exc)
        sys.exit(1)
