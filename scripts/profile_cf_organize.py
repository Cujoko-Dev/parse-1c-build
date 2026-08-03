#!/usr/bin/env python3
"""Профиль только organize_configuration_dir на уже распакованном raw dump.

Копирует входной dump во временный каталог (organize мутирует in-place), затем
замеряет фазы. Удобно сравнивать Python vs Rust::

    $env:P1CB_RUST_FORCE_PYTHON = '1'
    pdm run -p .dev python scripts/profile_cf_organize.py --in ... --json-out ...-py.json
    Remove-Item Env:P1CB_RUST_FORCE_PYTHON
    pdm run -p .dev python scripts/profile_cf_organize.py --in ... --json-out ...-rs.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from parse_1c_build import cf_layout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Profile CF organize_configuration_dir on a raw dump."
    )
    parser.add_argument(
        "--in",
        dest="input_dir",
        required=True,
        help="Raw v8unpack dump (flat) или путь, который можно скопировать.",
    )
    parser.add_argument(
        "--work",
        help="Рабочий каталог (будет очищен). По умолчанию — temp.",
    )
    parser.add_argument("--json-out", help="JSON-отчёт с таймингами.")
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Организовать --in на месте (разрушительно).",
    )
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"input not found: {input_dir}", file=sys.stderr)
        return 1
    if (input_dir / "meta" / "cfobjects.txt").is_file():
        print(
            "input looks already organized (meta/cfobjects.txt present); "
            "need a raw dump",
            file=sys.stderr,
        )
        return 1

    if args.no_copy:
        work_dir = input_dir
        temp_parent = None
    else:
        if args.work:
            work_dir = Path(args.work).expanduser().resolve()
            if work_dir.exists():
                shutil.rmtree(work_dir)
            work_dir.mkdir(parents=True)
        else:
            temp_parent = Path(tempfile.mkdtemp(prefix="p1cb-organize-profile-"))
            work_dir = temp_parent / "dump"
        print(f"copying {input_dir} → {work_dir} ...")
        t_copy0 = time.perf_counter()
        shutil.copytree(input_dir, work_dir)
        copy_s = time.perf_counter() - t_copy0
        print(f"copy: {copy_s:.3f}s")

    force = os.environ.get("P1CB_RUST_FORCE_PYTHON", "")
    native = cf_layout._rust_organize_configuration_dir is not None  # noqa: SLF001
    mode = (
        "python"
        if (force.strip().casefold() in {"1", "true", "yes"} or not native)
        else "rust"
    )

    layout_timings: dict[str, float] = {}
    t0 = time.perf_counter()
    cf_layout.organize_configuration_dir(work_dir, timings=layout_timings)
    organize_s = time.perf_counter() - t0

    file_count = sum(1 for p in work_dir.rglob("*") if p.is_file())
    bsl_count = sum(1 for p in work_dir.rglob("*.bsl") if p.is_file())

    report = {
        "input": str(input_dir),
        "work": str(work_dir),
        "mode": mode,
        "force_python": force,
        "native_available": native,
        "organize_s": organize_s,
        "organize_phases_s": layout_timings,
        "files": file_count,
        "bsl_files": bsl_count,
    }
    if not args.no_copy:
        report["copy_s"] = locals().get("copy_s", 0.0)

    print("=== CF organize profile ===")
    print(f"mode:  {mode}  (native_available={native})")
    print(f"work:  {work_dir}")
    print(f"files: {file_count}  bsl: {bsl_count}")
    print(f"organize: {organize_s:8.3f}s")
    print("phases:")
    for name, seconds in sorted(layout_timings.items(), key=lambda x: -x[1]):
        share = (seconds / organize_s) if organize_s else 0.0
        print(f"  {name:<22} {seconds:8.3f}s  ({100 * share:.1f}%)")

    if args.json_out:
        json_path = Path(args.json_out).expanduser().resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"json: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
