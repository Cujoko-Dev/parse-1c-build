#!/usr/bin/env python3
"""Профиль CF/CFE build: prepare_configuration_for_build vs v8unpack -B.

Пример::

    pdm run -p .dev python scripts/profile_cf_build.py ^
        --in D:\\Temp\\parse-1c-build\\cf-ut115-profile ^
        --out D:\\Temp\\parse-1c-build\\cf-ut115-rebuilt.cf ^
        --json-out D:\\Temp\\parse-1c-build\\cf-ut115-build-profile.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

from parse_1c_build import cf_layout
from parse_1c_build.build import Builder


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Profile CF build: prepare vs v8unpack -B."
    )
    parser.add_argument(
        "--in",
        dest="input_dir",
        required=True,
        help="Каталог организованных CF-исходников (meta/cfobjects.txt).",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Путь к выходному .cf/.cfe (создаётся/перезаписывается).",
    )
    parser.add_argument(
        "--json-out",
        help="Опциональный JSON-отчёт с таймингами.",
    )
    parser.add_argument(
        "--skip-pack",
        action="store_true",
        help="Только prepare_configuration_for_build, без v8unpack -B.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Не удалять временный flat dump после замера.",
    )
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir).expanduser().resolve()
    out_cf = Path(args.out).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"input not found: {input_dir}", file=sys.stderr)
        return 1
    if not cf_layout.has_cf_layout(input_dir):
        print(
            f"not an organized CF layout (missing meta/cfobjects.txt): {input_dir}",
            file=sys.stderr,
        )
        return 1

    out_cf.parent.mkdir(parents=True, exist_ok=True)
    if out_cf.exists():
        out_cf.unlink()

    temp_parent = Path(tempfile.mkdtemp(prefix="p1cb-cf-build-profile-"))
    wall0 = time.perf_counter()

    t0 = time.perf_counter()
    source_dir = cf_layout.prepare_configuration_for_build(input_dir, temp_parent)
    prepare_s = time.perf_counter() - t0

    pack_s = 0.0
    if not args.skip_pack:
        builder = Builder()
        v8unpack = builder.get_v8_unpack_file_path()
        cmd = [str(v8unpack), "-B", str(source_dir), str(out_cf)]
        t0 = time.perf_counter()
        from parse_1c_build.process_utils import check_silent

        check_silent(cmd)
        pack_s = time.perf_counter() - t0

    wall_s = time.perf_counter() - wall0
    dump_files = sum(1 for p in source_dir.rglob("*") if p.is_file())
    out_size = out_cf.stat().st_size if out_cf.is_file() else 0

    report = {
        "input": str(input_dir),
        "out": str(out_cf),
        "temp_dump": str(source_dir),
        "wall_s": wall_s,
        "prepare_s": prepare_s,
        "v8unpack_b_s": pack_s,
        "skipped_pack": bool(args.skip_pack),
        "dump_files": dump_files,
        "out_bytes": out_size,
        "prepare_share": (prepare_s / wall_s) if wall_s else 0.0,
        "v8unpack_b_share": (pack_s / wall_s) if wall_s else 0.0,
    }

    print("=== CF build profile ===")
    print(f"input: {input_dir}")
    print(f"out:   {out_cf}")
    print(f"dump files: {dump_files}")
    if out_size:
        print(f"out size:   {out_size / (1024 * 1024):.1f} MB")
    print(f"wall:       {wall_s:8.3f}s")
    print(f"prepare:    {prepare_s:8.3f}s  ({100 * report['prepare_share']:.1f}%)")
    if args.skip_pack:
        print("v8unpack -B: skipped")
    else:
        print(f"v8unpack -B:{pack_s:8.3f}s  ({100 * report['v8unpack_b_share']:.1f}%)")

    if args.json_out:
        json_path = Path(args.json_out).expanduser().resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"json: {json_path}")

    if not args.keep_temp:
        shutil.rmtree(temp_parent, ignore_errors=True)
    else:
        print(f"temp kept: {temp_parent}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
