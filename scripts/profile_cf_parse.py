#!/usr/bin/env python3
"""Профиль CF/CFE parse: v8unpack vs organize_configuration_dir (по фазам).

Пример::

    pdm run -p .dev python scripts/profile_cf_parse.py ^
        --in "D:\\Temp\\...\\КД_3.0 Типовая (3.0.5.3).cf" ^
        --out D:\\Temp\\parse-1c-build\\cf-kd-profile
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from parse_1c_build import cf_layout
from parse_1c_build.parse import Parser


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Profile CF parse: v8unpack vs layout.")
    parser.add_argument("--in", dest="input_cf", required=True, help="Путь к .cf/.cfe")
    parser.add_argument(
        "--out",
        required=True,
        help="Каталог распаковки (будет очищен перед прогоном).",
    )
    parser.add_argument(
        "--json-out",
        help="Опциональный JSON-отчёт с таймингами.",
    )
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="Не удалять сырой dump после замера (полезно для отладки).",
    )
    args = parser.parse_args(argv)

    input_cf = Path(args.input_cf).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    if not input_cf.is_file():
        print(f"input not found: {input_cf}", file=sys.stderr)
        return 1
    if input_cf.suffix.lower() not in {".cf", ".cfe"}:
        print(f"expected .cf/.cfe, got: {input_cf.suffix}", file=sys.stderr)
        return 1

    if out_dir.exists():
        shutil.rmtree(out_dir)
    # v8unpack создаёт каталог сам; пустой заранее созданный out мешает.

    proc = Parser()
    wall0 = time.perf_counter()

    t0 = time.perf_counter()
    proc._run_v8unpack_parse(input_cf, out_dir, raw=True)  # noqa: SLF001
    v8unpack_s = time.perf_counter() - t0

    layout_timings: dict[str, float] = {}
    t0 = time.perf_counter()
    cf_layout.organize_configuration_dir(out_dir, timings=layout_timings)
    organize_s = time.perf_counter() - t0

    wall_s = time.perf_counter() - wall0
    file_count = sum(1 for p in out_dir.rglob("*") if p.is_file())
    bsl_count = sum(1 for p in out_dir.rglob("*.bsl") if p.is_file())

    report = {
        "input": str(input_cf),
        "out": str(out_dir),
        "wall_s": wall_s,
        "v8unpack_s": v8unpack_s,
        "organize_s": organize_s,
        "organize_phases_s": layout_timings,
        "files": file_count,
        "bsl_files": bsl_count,
        "v8unpack_share": (v8unpack_s / wall_s) if wall_s else 0.0,
        "organize_share": (organize_s / wall_s) if wall_s else 0.0,
    }

    print("=== CF parse profile ===")
    print(f"input: {input_cf}")
    print(f"out:   {out_dir}")
    print(f"files: {file_count}  bsl: {bsl_count}")
    print(f"wall:      {wall_s:8.3f}s")
    print(
        f"v8unpack:  {v8unpack_s:8.3f}s  ({100 * report['v8unpack_share']:.1f}%)"
    )
    print(
        f"organize:  {organize_s:8.3f}s  ({100 * report['organize_share']:.1f}%)"
    )
    print("organize phases:")
    for name, seconds in sorted(layout_timings.items(), key=lambda x: -x[1]):
        share = (seconds / organize_s) if organize_s else 0.0
        print(f"  {name:<22} {seconds:8.3f}s  ({100 * share:.1f}% of organize)")

    if args.json_out:
        json_path = Path(args.json_out).expanduser().resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"json: {json_path}")

    if not args.keep_raw:
        # дерево уже организовано; флаг только документирует намерение оставить out
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
