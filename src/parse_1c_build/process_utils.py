"""Shared subprocess helpers for running external tools with suppressed stdout."""

import os
import subprocess


def run_silent(args: list[str]) -> int:
    """Run subprocess with stdout suppressed. Returns exit code."""
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        return subprocess.call(args, stdout=devnull)


def check_silent(args: list[str]) -> None:
    """Run subprocess with stdout suppressed; raise on non-zero exit."""
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        subprocess.check_call(args, stdout=devnull)
