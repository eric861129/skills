#!/usr/bin/env python3
"""Validate, preview, or execute an organize-files manifest.

Default is a dry run: validates manifest.json and predicts each operation
without touching anything. `--execute` performs the approved operations and
appends every result to journal.jsonl in the run folder; `--retry-failed`
re-runs only operations whose latest journal status is retryable.

This script never deletes files. Supported operations are `move` (also used
for renames) and `stage` (move into <root>/_organize-staging/<run-id>/ for
the user to review). The only removal it ever performs is the source of a
cross-volume move after the copy's SHA-256 has been verified, and only with
--allow-cross-volume; folders are removed only when already empty and only
when the manifest sets options.remove_emptied_dirs.
"""

from __future__ import annotations

import argparse
from collections import Counter
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any

sys.dont_write_bytecode = True

from organize_common import (  # noqa: E402
    EXCLUDED_DIR_NAMES,
    SCHEMA_VERSION,
    STAGING_DIR_NAME,
    OrganizeError,
    append_jsonl,
    classify_os_error,
    configure_stdout,
    enclosing_unit,
    human_size,
    is_cloud_placeholder,
    is_within,
    lock_holders,
    norm_key,
    now_iso,
    print_json,
    read_json,
    read_jsonl,
    rel_posix,
    render_tree,
    scan_tree,
    sha256_file,
    windows_rename_blocked,
    write_json,
)

ALLOWED_OPS = {"move", "stage"}
CONFLICT_POLICIES = {"auto", "suffix", "skip"}
SUCCESS_STATUSES = {"done", "staged"}
FINAL_STATUSES = SUCCESS_STATUSES | {"skipped"}
RETRYABLE_STATUSES = {
    "locked", "permission_denied", "disk_full", "failed", "cloud_placeholder",
    "cross_volume", "copied_source_locked", "path_too_long",
}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", help="Run folder created by inventory_files.py")
    parser.add_argument("--manifest", help="Manifest path (default: <run_dir>/manifest.json)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--execute", action="store_true", help="Perform the approved operations")
    mode.add_argument("--retry-failed", action="store_true", help="Re-run retryable failures only")
    parser.add_argument("--allow-cross-volume", action="store_true",
                        help="Allow copy+verify+remove-source moves between volumes")
    parser.add_argument("--allow-cloud-placeholders", action="store_true",
                        help="Allow moving online-only cloud files (may trigger downloads)")
    parser.add_argument("--retry-delays", default="1,3,10",
                        help="Seconds to wait between retries of locked files (default 1,3,10)")
    return parser.parse_args(argv)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def resolve_path(value: str, root: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return Path(os.path.normpath(path))


def validate(manifest: dict[str, Any], run_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION!r}")
    root_value = manifest.get("root")
    if not root_value:
        return [], errors + ["manifest.root is required"]
    root = Path(root_value).resolve()
    if not root.is_dir():
        errors.append(f"root does not exist: {root}")
    destination_roots = [root] + [Path(p).resolve() for p in manifest.get("destination_roots", [])]
    staging_root = root / STAGING_DIR_NAME / run_dir.name

    ops = manifest.get("operations")
    if not isinstance(ops, list) or not ops:
        return [], errors + ["manifest.operations must be a non-empty list"]

    seen_ids: set[Any] = set()
    seen_src: dict[str, Any] = {}
    seen_dst: dict[str, Any] = {}
    resolved: list[dict[str, Any]] = []
    for op in ops:
        op_id = op.get("id")
        label = f"op {op_id!r}"
        if op_id is None or op_id in seen_ids:
            errors.append(f"{label}: id is missing or duplicated")
            continue
        seen_ids.add(op_id)
        kind = op.get("op")
        if kind == "delete" or "delete" in op:
            errors.append(f"{label}: deleting is not allowed; use op 'stage' so the user can decide")
            continue
        if kind not in ALLOWED_OPS:
            errors.append(f"{label}: op must be one of {sorted(ALLOWED_OPS)}")
            continue
        policy = op.get("on_conflict", "auto")
        if policy not in CONFLICT_POLICIES:
            errors.append(f"{label}: on_conflict must be one of {sorted(CONFLICT_POLICIES)}")
        if not op.get("src"):
            errors.append(f"{label}: src is required")
            continue
        src = resolve_path(op["src"], root)
        if not is_within(src, root) or norm_key(src) == norm_key(root):
            errors.append(f"{label}: src must be inside root: {op['src']}")
            continue
        if is_within(src, root / STAGING_DIR_NAME):
            errors.append(f"{label}: src is inside the staging folder")
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in Path(rel_posix(src, root)).parts):
            errors.append(f"{label}: src is inside an excluded folder")
            continue
        unit = enclosing_unit(src, root)
        if unit and not op.get("allow_inside_unit"):
            errors.append(f"{label}: src is inside atomic unit {rel_posix(unit, root)}; move the unit as a whole")
            continue

        if kind == "stage":
            if not op.get("reason"):
                errors.append(f"{label}: stage operations need a reason")
            dst = staging_root / rel_posix(src, root)
        else:
            if not op.get("dst"):
                errors.append(f"{label}: dst is required for move")
                continue
            dst = resolve_path(op["dst"], root)
            if not any(is_within(dst, base) for base in destination_roots):
                errors.append(f"{label}: dst is outside root and destination_roots: {op['dst']}")
                continue
            if is_within(dst, root / STAGING_DIR_NAME):
                errors.append(f"{label}: use op 'stage' to put files in the staging folder")
                continue
            if norm_key(dst) == norm_key(src):
                errors.append(f"{label}: dst equals src")
                continue
            if is_within(dst, src):
                errors.append(f"{label}: dst is inside src")
                continue

        src_key, dst_key = norm_key(src), norm_key(dst)
        if src_key in seen_src:
            errors.append(f"{label}: src also used by op {seen_src[src_key]!r}")
        if dst_key in seen_dst:
            errors.append(f"{label}: dst also used by op {seen_dst[dst_key]!r}")
        seen_src[src_key] = op_id
        seen_dst[dst_key] = op_id
        resolved.append({**op, "on_conflict": policy, "_src": src, "_dst": dst})

    # A later op must not move something an earlier op already moved away.
    for op in resolved:
        for other in resolved:
            if other is not op and is_within(op["_src"], other["_src"]) and norm_key(op["_src"]) != norm_key(other["_src"]):
                errors.append(f"op {op['id']!r}: src is inside op {other['id']!r}'s src; move one or the other")
    return resolved, errors


# --------------------------------------------------------------------------
# Execution helpers
# --------------------------------------------------------------------------

def suffixed(path: Path) -> Path:
    stem, suffix = (path.name, "") if path.is_dir() else (path.stem, path.suffix)
    counter = 2
    while True:
        candidate = path.with_name(f"{stem} ({counter}){suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def identical_files(a: Path, b: Path) -> bool:
    return (
        a.is_file() and b.is_file()
        and a.stat().st_size == b.stat().st_size
        and sha256_file(a) == sha256_file(b)
    )


def resolve_conflict(op: dict[str, Any], staging_root: Path, root: Path) -> tuple[str, Path, str | None]:
    """Return (effective_op, destination, note) after checking the target."""
    src, dst = op["_src"], op["_dst"]
    if not dst.exists():
        return op["op"], dst, None
    policy = op["on_conflict"]
    if op["op"] == "stage":
        return "stage", suffixed(dst), "staging path existed; suffixed"
    if policy == "skip":
        return "skip", dst, "target exists"
    if policy == "auto" and identical_files(src, dst):
        return "stage", staging_root / rel_posix(src, root), f"identical to existing {rel_posix(dst, root)}"
    return "move", suffixed(dst), "target existed with different content; suffixed"


def make_parents(path: Path) -> list[str]:
    missing = []
    current = path.parent
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir()
    return [str(d) for d in reversed(missing)]


def cross_volume_move(src: Path, dst: Path) -> tuple[str, str]:
    if src.is_dir():
        raise OrganizeError("cross_volume", "folders are not moved across volumes; move them by hand")
    partial = dst.with_name(dst.name + ".organize-partial")
    try:
        shutil.copy2(src, partial)
    except OSError as error:
        kind = classify_os_error(error)
        leftover = f"; partial copy left at {partial} for the user to review" if partial.exists() else ""
        raise OrganizeError(kind, f"copy failed, source untouched: {error}{leftover}") from error
    src_hash, copy_hash = sha256_file(src), sha256_file(partial)
    if src_hash != copy_hash:
        partial.rename(dst.with_name(dst.name + ".organize-mismatch"))
        raise OrganizeError("failed", "copy verification failed; source left untouched")
    partial.rename(dst)
    try:
        os.remove(src)  # source of a verified copy: this completes the move
    except OSError as error:
        raise OrganizeError(
            "copied_source_locked" if classify_os_error(error) == "locked" else classify_os_error(error),
            f"copied and verified, but the source could not be removed: {error}",
        ) from error
    return src_hash, copy_hash


def attempt(op: dict[str, Any], args: argparse.Namespace, root: Path, staging_root: Path,
            delays: list[float]) -> dict[str, Any]:
    src = op["_src"]
    record: dict[str, Any] = {
        "id": op["id"], "op": op["op"], "src": str(src), "planned_dst": str(op["_dst"]),
        "ts": now_iso(), "attempts": 0, "created_dirs": [],
    }
    if not src.exists() and not src.is_symlink():
        return {**record, "status": "source_missing", "error": "source no longer exists"}
    if is_cloud_placeholder(src) and not args.allow_cloud_placeholders:
        return {**record, "status": "cloud_placeholder",
                "error": "online-only cloud file; moving it may download it"}

    effective, dst, note = resolve_conflict(op, staging_root, root)
    record["note"] = note
    if effective == "skip":
        return {**record, "status": "skipped", "final_dst": None, "error": note}
    record["effective_op"] = effective
    record["final_dst"] = str(dst)

    for wait in [0.0] + delays:
        if wait:
            time.sleep(wait)
        record["attempts"] += 1
        try:
            if not record["created_dirs"]:
                record["created_dirs"] = make_parents(dst)
            if dst.exists():
                raise OrganizeError("target_exists", f"target appeared during the run: {dst}")
            try:
                os.rename(src, dst)
            except OSError as error:
                if classify_os_error(error) != "cross_volume":
                    raise
                if not args.allow_cross_volume:
                    raise OrganizeError("cross_volume", "different volume; rerun with --allow-cross-volume") from error
                record["src_sha256"], record["dst_sha256"] = cross_volume_move(src, dst)
            record["status"] = "staged" if effective == "stage" else "done"
            record["error"] = None
            return record
        except OrganizeError as error:
            record["status"], record["error"] = error.kind, str(error)
            if error.kind != "locked":
                break
        except OSError as error:
            record["status"], record["error"] = classify_os_error(error), str(error)
            if record["status"] != "locked":
                break
    if record["status"] in ("locked", "copied_source_locked"):
        record["holders"] = lock_holders(src)
    return record


def remove_emptied_dirs(moved_sources: list[Path], root: Path, journal: Path) -> list[str]:
    removed = []
    candidates = set()
    for src in moved_sources:
        parent = src.parent
        while is_within(parent, root) and norm_key(parent) != norm_key(root):
            candidates.add(parent)
            parent = parent.parent
    for directory in sorted(candidates, key=lambda p: len(str(p)), reverse=True):
        try:
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()  # rmdir only succeeds on an empty folder
                removed.append(str(directory))
                append_jsonl(journal, {"id": f"rmdir:{rel_posix(directory, root)}", "op": "rmdir_empty",
                                       "status": "rmdir_empty", "src": str(directory), "ts": now_iso()})
        except OSError:
            continue
    return removed


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def latest_by_id(records: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
    latest: dict[Any, dict[str, Any]] = {}
    for record in records:
        latest[record["id"]] = record
    return latest


def preview(ops: list[dict[str, Any]], root: Path, staging_root: Path) -> list[dict[str, Any]]:
    rows = []
    for op in ops:
        src = op["_src"]
        row: dict[str, Any] = {"id": op["id"], "op": op["op"], "src": rel_posix(src, root)}
        if not src.exists():
            row["prediction"] = "source_missing"
        elif is_cloud_placeholder(src):
            row["prediction"] = "cloud_placeholder"
        else:
            blocked = windows_rename_blocked(src)
            effective, dst, note = resolve_conflict(op, staging_root, root)
            row.update({"dst": rel_posix(dst, root), "effective_op": effective, "note": note})
            row["prediction"] = blocked or ("skipped" if effective == "skip" else "ok")
        rows.append(row)
    return rows


def main(argv: list[str]) -> int:
    configure_stdout()
    args = parse_args(argv)
    run_dir = Path(args.run_dir).expanduser().resolve()
    manifest_path = Path(args.manifest).resolve() if args.manifest else run_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"error: manifest not found: {manifest_path}", file=sys.stderr)
        return 2
    manifest = read_json(manifest_path)
    ops, errors = validate(manifest, run_dir)
    if errors:
        print_json({"mode": "validate", "valid": False, "errors": errors})
        return 1
    root = Path(manifest["root"]).resolve()
    staging_root = root / STAGING_DIR_NAME / run_dir.name
    journal = run_dir / "journal.jsonl"
    delays = [float(x) for x in args.retry_delays.split(",") if x.strip()]

    if not (args.execute or args.retry_failed):
        rows = preview(ops, root, staging_root)
        print_json({
            "mode": "dry-run", "valid": True, "root": str(root),
            "staging_dir": str(staging_root), "operation_count": len(ops),
            "predictions": dict(Counter(r["prediction"] for r in rows)),
            "effective_ops": dict(Counter(r.get("effective_op", "-") for r in rows)),
            "operations": rows,
        })
        return 0

    approval = manifest.get("approval") or {}
    if approval.get("approved_by_user") is not True:
        print("error: manifest.approval.approved_by_user must be true; get the user's approval first",
              file=sys.stderr)
        return 3

    previous = latest_by_id(read_jsonl(journal))
    if args.retry_failed:
        todo = [op for op in ops if previous.get(op["id"], {}).get("status") in RETRYABLE_STATUSES]
    else:
        todo = [op for op in ops if previous.get(op["id"], {}).get("status") not in FINAL_STATUSES]
    if not journal.exists():
        append_jsonl(journal, {"id": "run", "op": "run_start", "status": "info", "root": str(root),
                               "staging_dir": str(staging_root), "ts": now_iso()})

    moved_sources: list[Path] = []
    for op in todo:
        record = attempt(op, args, root, staging_root, delays)
        append_jsonl(journal, record)
        if record["status"] in SUCCESS_STATUSES:
            moved_sources.append(op["_src"])

    removed_dirs: list[str] = []
    if (manifest.get("options") or {}).get("remove_emptied_dirs") and moved_sources:
        removed_dirs = remove_emptied_dirs(moved_sources, root, journal)

    latest = latest_by_id([r for r in read_jsonl(journal) if r.get("op") not in ("run_start", "rmdir_empty")])
    statuses = Counter(record["status"] for record in latest.values())
    attention = [
        {k: record.get(k) for k in ("id", "status", "src", "final_dst", "error", "holders") if record.get(k)}
        for record in latest.values() if record["status"] not in FINAL_STATUSES
    ]
    staged = [
        {"src": rel_posix(Path(r["src"]), root), "staged_at": r["final_dst"], "note": r.get("note")}
        for r in latest.values() if r["status"] == "staged"
    ]
    moved_bytes = 0
    for record in latest.values():
        if record["status"] in SUCCESS_STATUSES and record.get("final_dst"):
            target = Path(record["final_dst"])
            if target.is_file():
                moved_bytes += target.stat().st_size
    tree_after = render_tree(scan_tree(root), depth=int((manifest.get("options") or {}).get("tree_depth", 3)))
    (run_dir / "tree-after.txt").write_text(tree_after + "\n", encoding="utf-8")

    summary = {
        "schema_version": SCHEMA_VERSION,
        "mode": "retry-failed" if args.retry_failed else "execute",
        "finished_at": now_iso(),
        "root": str(root),
        "run_dir": str(run_dir),
        "journal": str(journal),
        "staging_dir": str(staging_root),
        "planned_operations": len(ops),
        "attempted_this_run": len(todo),
        "status_counts": dict(statuses),
        "bytes_moved": moved_bytes,
        "bytes_moved_human": human_size(moved_bytes),
        "staged": staged,
        "removed_empty_dirs": removed_dirs,
        "needs_attention": attention,
        "tree_after": tree_after,
        "undo_command": f'python "{Path(__file__).with_name("undo.py")}" "{run_dir}" --execute',
    }
    write_json(run_dir / "summary.json", summary)
    print_json(summary)
    return 0 if not attention else 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
