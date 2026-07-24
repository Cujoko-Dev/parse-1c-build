"""Organize flat v8unpack CF/CFE dumps into Class/Object layout with BSL prefixes."""

from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from parse_1c_build import bsl
from parse_1c_build.metadata_types import (
    CONFIG_MODULE_SLOTS,
    CONFIGURATION_TYPE_UUID,
    METADATA_TYPES,
)

logger.disable(__name__)

_RE_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_RE_COLLECTION = re.compile(
    r"\{("
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"),(\d+)((?:,[0-9a-fA-F-]{36})*)\}"
)
_RE_OBJECT_NAME = re.compile(
    r'\{0,0,([0-9a-fA-F-]{36})\},"([^"]+)"'
)

CF_OBJECTS_FILENAME = "cf_objects.txt"
ROOT_MARKER_FILES = frozenset({"root", "version", "versions"})


@dataclass
class MetaObject:
    type_uuid: str
    object_uuid: str
    name: str
    class_folder: str
    root_prefix: str | None
    related_stems: set[str] = field(default_factory=set)

    @property
    def rel_dir(self) -> str:
        if self.root_prefix is not None:
            return ""
        return f"{self.class_folder}/{self.name}"


def _read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8-sig")


def _config_uuid_from_root(dump_dir: Path) -> str:
    root_path = dump_dir / "root"
    if not root_path.is_file():
        raise Exception(f"CF dump has no root file: '{dump_dir}'")
    m = _RE_UUID.search(_read_text(root_path))
    if not m:
        raise Exception(f"Cannot find configuration UUID in '{root_path}'")
    return m.group(0).lower()


def _object_name(dump_dir: Path, object_uuid: str) -> str:
    path = dump_dir / object_uuid
    if not path.is_file():
        return object_uuid
    text = _read_text(path)
    for m in _RE_OBJECT_NAME.finditer(text):
        if m.group(1).lower() == object_uuid.lower():
            return m.group(2)
    m = _RE_OBJECT_NAME.search(text)
    return m.group(2) if m else object_uuid


def _parse_collections(config_text: str) -> list[tuple[str, list[str]]]:
    result: list[tuple[str, list[str]]] = []
    for m in _RE_COLLECTION.finditer(config_text):
        type_uuid = m.group(1).lower()
        count = int(m.group(2))
        uuids = [u.lower() for u in _RE_UUID.findall(m.group(3))]
        if count == 0:
            continue
        if type_uuid == CONFIGURATION_TYPE_UUID:
            continue
        result.append((type_uuid, uuids[:count]))
    return result


def _discover_objects(dump_dir: Path) -> tuple[str, str, list[MetaObject]]:
    config_uuid = _config_uuid_from_root(dump_dir)
    config_path = dump_dir / config_uuid
    if not config_path.is_file():
        raise Exception(f"Configuration descriptor missing: '{config_path}'")
    config_text = _read_text(config_path)
    objects: list[MetaObject] = []
    top_level: set[str] = {config_uuid}
    for type_uuid, uuids in _parse_collections(config_text):
        class_folder, root_prefix = METADATA_TYPES.get(
            type_uuid, (f"Тип_{type_uuid[:8]}", None)
        )
        for object_uuid in uuids:
            top_level.add(object_uuid)
            name = _object_name(dump_dir, object_uuid)
            objects.append(
                MetaObject(
                    type_uuid=type_uuid,
                    object_uuid=object_uuid,
                    name=name,
                    class_folder=class_folder,
                    root_prefix=root_prefix,
                )
            )
    # related stems: object uuid itself + referenced UUIDs that are not other top-level objects
    for obj in objects:
        obj.related_stems.add(obj.object_uuid)
        desc = dump_dir / obj.object_uuid
        if not desc.is_file():
            continue
        for ref in _RE_UUID.findall(_read_text(desc)):
            ref_l = ref.lower()
            if ref_l in top_level and ref_l != obj.object_uuid:
                continue
            if _stem_exists(dump_dir, ref_l):
                obj.related_stems.add(ref_l)
    return config_uuid, config_text, objects


def _stem_exists(dump_dir: Path, stem: str) -> bool:
    if (dump_dir / stem).exists():
        return True
    return any(dump_dir.glob(f"{stem}.*"))


def _iter_stem_paths(dump_dir: Path, stem: str) -> list[Path]:
    paths: list[Path] = []
    direct = dump_dir / stem
    if direct.exists():
        paths.append(direct)
    paths.extend(sorted(dump_dir.glob(f"{stem}.*")))
    return paths


def _safe_move(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if dest.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    shutil.move(str(src), str(dest))


def _extract_plain_module(module_path: Path, dest_bsl: Path) -> bool:
    """Extract plain-text module file to .bsl and replace with placeholder."""
    if not module_path.is_file():
        return False
    content = module_path.read_bytes().decode("utf-8-sig")
    if content.strip() == "":
        dest_bsl.write_bytes(b"")
        module_path.write_bytes("\r\n".encode("utf-8"))
        return True
    # keep original newlines
    raw = module_path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        body = raw[3:]
        dest_bsl.write_bytes(body)
    else:
        dest_bsl.write_bytes(raw)
    module_path.write_bytes(b"\xef\xbb\xbf" + bsl.BSL_PLACEHOLDER.encode("utf-8"))
    return True


def _extract_root_prefixed_object(
    dump_dir: Path,
    obj: MetaObject,
    root: Path,
    renames: list[tuple[str, str]],
) -> None:
    """Place dump files into root bin/ and extract BSL with root_prefix."""
    assert obj.root_prefix is not None
    bin_dir = root / bsl.BIN_DIRNAME
    for stem in sorted(obj.related_stems):
        for src in _iter_stem_paths(dump_dir, stem):
            rel = src.name
            dest = bin_dir / rel
            _safe_move(src, dest)
            renames.append((rel, f"{bsl.BIN_DIRNAME}/{rel}"))

    # module body: prefer object_uuid.0/text, else object_uuid.0 file (form)
    text_path = bin_dir / f"{obj.object_uuid}.0" / "text"
    form_path = bin_dir / f"{obj.object_uuid}.0"
    bsl_name = f"{obj.root_prefix}{obj.name}.bsl"
    bsl_path = root / bsl_name
    if text_path.is_file():
        if _extract_plain_module(text_path, bsl_path):
            renames.append(
                (
                    bsl_name,
                    f"{bsl.BIN_DIRNAME}/{obj.object_uuid}.0/text",
                )
            )
    elif form_path.is_file() and not form_path.is_dir():
        # managed form / form module embedded in UUID.0
        if bsl.split_file(form_path, bsl_path):
            renames.append(
                (bsl_name, f"{bsl.BIN_DIRNAME}/{obj.object_uuid}.0")
            )


def _extract_object_modules(object_dir: Path, object_uuid: str) -> None:
    """Extract modules inside an object mini-layout (bin already filled)."""
    bin_dir = object_dir / bsl.BIN_DIRNAME
    meta_dir = object_dir / bsl.META_DIRNAME
    meta_dir.mkdir(parents=True, exist_ok=True)
    renames: list[tuple[str, str]] = []
    handled_texts: set[Path] = set()

    def _add_plain(text_path: Path, bsl_name: str) -> None:
        if text_path in handled_texts or not text_path.is_file():
            return
        body = text_path.read_bytes().decode("utf-8-sig")
        if body.strip() == "":
            return
        dest = object_dir / bsl_name
        if dest.exists():
            return
        if _extract_plain_module(text_path, dest):
            rel = text_path.relative_to(bin_dir).as_posix()
            renames.append((bsl_name, f"{bsl.BIN_DIRNAME}/{rel}"))
            handled_texts.add(text_path)

    # Object module: uuid.0/text
    _add_plain(bin_dir / f"{object_uuid}.0" / "text", f"{bsl.BSL_PREFIX_OBJECT}Объект.bsl")

    # Manager module: uuid.2/text without command handler
    mgr_text = bin_dir / f"{object_uuid}.2" / "text"
    if mgr_text.is_file():
        body = mgr_text.read_bytes().decode("utf-8-sig")
        if body.strip() and "ОбработкаКоманды" not in body:
            _add_plain(mgr_text, f"{bsl.BSL_PREFIX_OBJECT}Менеджер.bsl")

    # Command modules: any *.2/text with ОбработкаКоманды (including object's .2)
    for text_path in sorted(bin_dir.rglob("text")):
        if text_path in handled_texts or not text_path.is_file():
            continue
        parent_name = text_path.parent.name
        if not parent_name.endswith(".2"):
            continue
        body = text_path.read_bytes().decode("utf-8-sig")
        if "ОбработкаКоманды" not in body or not body.strip():
            continue
        stem = parent_name[:-2]
        cmd_name = stem
        desc = bin_dir / stem
        if desc.is_file():
            m = _RE_OBJECT_NAME.search(_read_text(desc))
            if m:
                cmd_name = m.group(2)
        else:
            cmd_name = stem.split("-")[0]
        bsl_name = f"{bsl.BSL_PREFIX_COMMAND}{cmd_name}.bsl"
        if (object_dir / bsl_name).exists():
            bsl_name = f"{bsl.BSL_PREFIX_COMMAND}{cmd_name}_{stem[:8]}.bsl"
        _add_plain(text_path, bsl_name)

    # Forms (managed UUID.0 files and ordinary form modules)
    for item in sorted(bin_dir.rglob("*"), key=lambda p: (len(p.parts), str(p))):
        if item.is_dir() or item.suffix.lower() == ".bsl":
            continue
        if item.name == "text":
            continue
        companion = item.relative_to(bin_dir).as_posix()
        bsl_name: str | None = None
        if bsl.is_managed_form_file(item):
            form_name = bsl.get_form_or_object_name(bin_dir, item.name)
            if form_name:
                bsl_name = f"{bsl.BSL_PREFIX_FORM}{form_name}.bsl"
        elif item.name == "module" and item.parent.name.endswith(".0"):
            form_name = bsl.get_form_or_object_name(bin_dir, item.parent.name)
            if form_name:
                bsl_name = f"{bsl.BSL_PREFIX_FORM}{form_name}.bsl"
        if bsl_name and bsl.split_file(item, object_dir / bsl_name):
            renames.append((bsl_name, f"{bsl.BIN_DIRNAME}/{companion}"))

    with (meta_dir / "renames.txt").open("w", encoding="utf-8") as f:
        for path in sorted(bin_dir.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(bin_dir).as_posix()
            f.write(f"{rel}{bsl.RENAMES_ARROW}{bsl.BIN_DIRNAME}/{rel}\n")
    if renames:
        bsl.write_bsl_renames_file(object_dir, sorted(set(renames)))


def _extract_config_modules(
    dump_dir: Path,
    config_text: str,
    root: Path,
    renames: list[tuple[str, str]],
) -> None:
    """Extract configuration application/session modules into root 0_*.bsl."""
    # Identity uuid often appears as {0,0,uuid},"ConfigName"
    m = re.search(
        r'\{0,0,([0-9a-fA-F-]{36})\},"([^"]+)"',
        config_text,
    )
    if not m:
        return
    identity = m.group(1).lower()
    bin_dir = root / bsl.BIN_DIRNAME
    for slot, role in CONFIG_MODULE_SLOTS.items():
        src_dir = dump_dir / f"{identity}.{slot}"
        text_path = src_dir / "text"
        if not text_path.is_file():
            continue
        # move whole slot dir into bin
        dest_dir = bin_dir / f"{identity}.{slot}"
        if src_dir.exists() and not dest_dir.exists():
            _safe_move(src_dir, dest_dir)
            renames.append(
                (f"{identity}.{slot}", f"{bsl.BIN_DIRNAME}/{identity}.{slot}")
            )
        text_path = dest_dir / "text"
        if not text_path.is_file():
            continue
        if text_path.read_bytes().decode("utf-8-sig").strip() == "":
            continue
        bsl_name = f"{bsl.BSL_PREFIX_OBJECT}{role}.bsl"
        if _extract_plain_module(text_path, root / bsl_name):
            renames.append(
                (bsl_name, f"{bsl.BIN_DIRNAME}/{identity}.{slot}/text")
            )


def organize_configuration_dir(dump_dir: Path) -> None:
    """Transform flat v8unpack CF dump into Class/Object + root BSL layout."""
    dump_dir = dump_dir.resolve()
    config_uuid, config_text, objects = _discover_objects(dump_dir)
    logger.info(f"CF layout: {len(objects)} metadata object(s) in '{dump_dir}'")

    # Work in a staging directory then replace contents
    staging = Path(tempfile.mkdtemp(prefix="cf_layout_"))
    try:
        root_bin = staging / bsl.BIN_DIRNAME
        root_meta = staging / bsl.META_DIRNAME
        root_bin.mkdir(parents=True)
        root_meta.mkdir(parents=True)
        root_renames: list[tuple[str, str]] = []
        objects_index: list[tuple[str, str]] = []  # rel_dir --> object_uuid

        claimed: set[str] = set()

        # Root-prefixed objects (common modules/forms/commands)
        for obj in objects:
            if obj.root_prefix is None:
                continue
            _extract_root_prefixed_object(dump_dir, obj, staging, root_renames)
            for stem in obj.related_stems:
                claimed.add(stem)
            objects_index.append((f"@{obj.root_prefix}{obj.name}", obj.object_uuid))

        _extract_config_modules(dump_dir, config_text, staging, root_renames)

        # Class/Name objects
        for obj in objects:
            if obj.root_prefix is not None:
                continue
            obj_dir = staging / obj.class_folder / obj.name
            obj_bin = obj_dir / bsl.BIN_DIRNAME
            obj_bin.mkdir(parents=True, exist_ok=True)
            for stem in sorted(obj.related_stems):
                for src in _iter_stem_paths(dump_dir, stem):
                    _safe_move(src, obj_bin / src.name)
                    claimed.add(stem)
            _extract_object_modules(obj_dir, obj.object_uuid)
            objects_index.append((obj.rel_dir, obj.object_uuid))

        # Remaining dump files → root bin (including root/version/versions/config descriptor)
        for item in list(dump_dir.iterdir()):
            name = item.name
            stem = name.split(".", 1)[0].lower()
            if stem in claimed and name not in ROOT_MARKER_FILES:
                # might still have leftover if partial
                if not item.exists():
                    continue
            if not item.exists():
                continue
            dest = root_bin / name
            _safe_move(item, dest)
            root_renames.append((name, f"{bsl.BIN_DIRNAME}/{name}"))

        # Write root meta
        with (root_meta / CF_OBJECTS_FILENAME).open("w", encoding="utf-8") as f:
            for rel, uuid in sorted(objects_index, key=lambda x: x[0]):
                f.write(f"{rel}{bsl.RENAMES_ARROW}{uuid}\n")
        with (root_meta / "renames.txt").open("w", encoding="utf-8") as f:
            for target, source in sorted(set(root_renames), key=lambda x: x[0]):
                if target.endswith(".bsl"):
                    continue
                f.write(f"{target}{bsl.RENAMES_ARROW}{source}\n")
        bsl_root_entries = [
            (t, s) for t, s in root_renames if t.endswith(".bsl")
        ]
        if bsl_root_entries:
            bsl.write_bsl_renames_file(staging, sorted(set(bsl_root_entries)))

        # Replace dump_dir contents with staging
        for item in list(dump_dir.iterdir()):
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        for item in staging.iterdir():
            shutil.move(str(item), str(dump_dir / item.name))
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    logger.info(f"CF layout organized in '{dump_dir}'")


def has_cf_layout(dir_path: Path) -> bool:
    """True if directory looks like organized CF sources."""
    return (dir_path / bsl.META_DIRNAME / CF_OBJECTS_FILENAME).is_file()


def _copy_tree_entries(src_dir: Path, dest_dir: Path) -> None:
    """Copy all entries from src_dir into dest_dir (no overwrite of existing)."""
    for item in src_dir.iterdir():
        dest = dest_dir / item.name
        if dest.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)


def prepare_configuration_for_build(input_dir: Path, temp_parent: Path) -> Path:
    """Flatten organized CF layout to a temp dump directory for v8unpack -B."""
    input_dir = input_dir.resolve()
    temp_dump = temp_parent / "cf_dump"
    temp_dump.mkdir(parents=True, exist_ok=True)

    objects_path = input_dir / bsl.META_DIRNAME / CF_OBJECTS_FILENAME
    with objects_path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if bsl.RENAMES_ARROW not in line:
                continue
            rel, _uuid = (s.strip() for s in line.split("-->", 1))
            if rel.startswith("@"):
                continue
            obj_dir = input_dir / rel
            if not obj_dir.is_dir():
                continue
            if bsl.has_bin_layout(obj_dir):
                prepared = bsl.prepare_temp_for_build(
                    obj_dir, temp_parent / f"obj_{obj_dir.name}"
                )
                _copy_tree_entries(prepared, temp_dump)
            else:
                bin_dir = obj_dir / bsl.BIN_DIRNAME
                if bin_dir.is_dir():
                    _copy_tree_entries(bin_dir, temp_dump)

    # Root bin + root BSL merge
    if (input_dir / bsl.META_DIRNAME / bsl.BSL_RENAMES_FILENAME).is_file() and (
        input_dir / bsl.BIN_DIRNAME
    ).is_dir():
        # Ensure renames.txt exists for prepare_temp_for_build
        root_renames = input_dir / bsl.META_DIRNAME / "renames.txt"
        if root_renames.is_file() and (
            input_dir / bsl.META_DIRNAME / bsl.BSL_RENAMES_FILENAME
        ).is_file():
            # has_bin_layout requires both renames; synthesize minimal if needed
            pass
        if bsl.has_bin_layout(input_dir):
            prepared_root = bsl.prepare_temp_for_build(
                input_dir, temp_parent / "cf_root"
            )
            _copy_tree_entries(prepared_root, temp_dump)
        else:
            # merge root bsl manually then copy bin
            bsl.merge_dir(input_dir)
            _copy_tree_entries(input_dir / bsl.BIN_DIRNAME, temp_dump)
    elif (input_dir / bsl.BIN_DIRNAME).is_dir():
        _copy_tree_entries(input_dir / bsl.BIN_DIRNAME, temp_dump)

    return temp_dump
