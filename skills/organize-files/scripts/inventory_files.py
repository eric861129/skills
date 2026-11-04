#!/usr/bin/env python3
"""Read-only inventory of a folder before organizing it.

Never modifies the target folder. With the default `--run-dir auto` it writes
inventory.json and tree-before.txt into a new run folder under
<Desktop>/organize-files-logs/ and prints a summary (without the per-file
list) to stdout. With `--run-dir none` it writes nothing and prints the full
inventory to stdout. `--format tree` prints only the folder tree.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import os
from pathlib import Path
import sys
from typing import Any

sys.dont_write_bytecode = True  # keep the skill folder free of __pycache__

from organize_common import (  # noqa: E402
    EXCLUDED_DIR_NAMES,
    IS_WINDOWS,
    SCHEMA_VERSION,
    STAGING_DIR_NAME,
    category_for,
    configure_stdout,
    count_tree,
    human_size,
    lock_holders,
    log_base_dir,
    new_run_id,
    now_iso,
    print_json,
    rel_posix,
    render_tree,
    scan_tree,
    sha256_file,
    stat_flags,
    unit_kind,
    windows_rename_blocked,
    write_json,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", help="Folder to inventory")
    parser.add_argument(
        "--run-dir", default="auto",
        help="'auto' (new folder on the Desktop, default), 'none' (write nothing), or a path",
    )
    parser.add_argument("--format", choices=("summary", "json", "tree"), default="summary",
                        help="stdout format (default: summary; 'json' includes every file)")
    parser.add_argument("--depth", type=int, default=3, help="Tree depth to render (default 3)")
    parser.add_argument("--no-hash", action="store_true", help="Skip duplicate detection hashing")
    parser.add_argument("--no-lock-check", action="store_true", help="Skip Windows lock checks")
    parser.add_argument("--exclude", action="append", default=[], metavar="NAME",
                        help="Extra directory name to skip (repeatable)")
    return parser.parse_args(argv)


def inventory(root: Path, excluded: set[str], do_hash: bool, check_locks: bool) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    units: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    unreadable: list[dict[str, str]] = []
    max_depth = 0
    dir_count = 0

    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError as error:
            unreadable.append({"path": rel_posix(directory, root), "error": str(error)})
            continue
        for entry in entries:
            path = Path(entry.path)
            rel = rel_posix(path, root)
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in excluded:
                        skipped.append({"path": rel, "reason": "excluded-name"})
                        continue
                    st = entry.stat(follow_symlinks=False)
                    flags = stat_flags(path, st)
                    if "reparse-point" in flags or "symlink" in flags:
                        skipped.append({"path": rel, "reason": "link-or-junction"})
                        continue
                    kind = unit_kind(path)
                    if kind:
                        count, size = count_tree(path)
                        units.append({"path": rel, "kind": kind, "files": count, "bytes": size,
                                      "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
                        continue
                    dir_count += 1
                    max_depth = max(max_depth, rel.count("/") + 1)
                    stack.append(path)
                    continue
                st = entry.stat(follow_symlinks=False)
                flags = stat_flags(path, st)
                record: dict[str, Any] = {
                    "path": rel,
                    "size": st.st_size,
                    "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                    "ext": path.suffix.lower(),
                    "category": category_for(path),
                    "flags": flags,
                }
                if check_locks and IS_WINDOWS and "cloud-placeholder" not in flags:
                    blocked = windows_rename_blocked(path)
                    if blocked:
                        record["flags"].append(blocked.replace("_", "-"))
                        if blocked == "locked":
                            record["holders"] = lock_holders(path)
                files.append(record)
            except OSError as error:
                unreadable.append({"path": rel, "error": str(error)})

    # Office/LibreOffice owner files mean the sibling document is open.
    names = {record["path"].lower(): record for record in files}
    for record in files:
        if record["category"] != "office-lock-file":
            continue
        parent, _, name = record["path"].rpartition("/")
        base = name[2:] if name.startswith("~$") else name[len(".~lock."):].rstrip("#")
        for candidate in names:
            cand_parent, _, cand_name = candidate.rpartition("/")
            if cand_parent == parent.lower() and cand_name.endswith(base.lower()) and candidate != record["path"].lower():
                names[candidate]["flags"].append("likely-open-in-office")

    duplicates: list[dict[str, Any]] = []
    if do_hash:
        by_size: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for record in files:
            if record["size"] > 0 and "cloud-placeholder" not in record["flags"]:
                by_size[record["size"]].append(record)
        for group in by_size.values():
            if len(group) < 2:
                continue
            by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for record in group:
                try:
                    record["sha256"] = sha256_file(root / record["path"])
                except OSError as error:
                    record["flags"].append("unreadable")
                    record["error"] = str(error)
                    continue
                by_hash[record["sha256"]].append(record)
            for digest, same in by_hash.items():
                if len(same) > 1:
                    duplicates.append({
                        "sha256": digest,
                        "size": same[0]["size"],
                        "paths": sorted((r["path"] for r in same), key=str.lower),
                    })
        duplicates.sort(key=lambda d: d["size"] * (len(d["paths"]) - 1), reverse=True)

    files.sort(key=lambda r: r["path"].lower())
    units.sort(key=lambda u: u["path"].lower())

    by_category: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "bytes": 0})
    by_year: Counter[str] = Counter()
    by_ext: Counter[str] = Counter()
    for record in files:
        by_category[record["category"]]["count"] += 1
        by_category[record["category"]]["bytes"] += record["size"]
        by_year[record["mtime"][:4]] += 1
        by_ext[record["ext"] or "(none)"] += 1

    def paths_with(flag: str) -> list[dict[str, Any]]:
        out = []
        for record in files:
            if flag in record["flags"]:
                item = {"path": record["path"]}
                if record.get("holders"):
                    item["holders"] = record["holders"]
                out.append(item)
        return out

    top_level_entries = sorted(os.listdir(root)) if root.exists() else []
    root_unit = unit_kind(root)
    summary = {
        "file_count": len(files),
        "dir_count": dir_count,
        "unit_count": len(units),
        "total_bytes": sum(r["size"] for r in files) + sum(u["bytes"] for u in units),
        "loose_file_bytes": sum(r["size"] for r in files),
        "top_level_entry_count": len(top_level_entries),
        "max_depth": max_depth,
        "by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1]["bytes"])),
        "by_year": dict(sorted(by_year.items())),
        "top_extensions": dict(by_ext.most_common(15)),
        "largest_files": [
            {"path": r["path"], "size": r["size"], "human": human_size(r["size"])}
            for r in sorted(files, key=lambda r: -r["size"])[:10]
        ],
        "duplicate_groups": len(duplicates),
        "duplicate_reclaimable_bytes": sum(d["size"] * (len(d["paths"]) - 1) for d in duplicates),
    }
    risks = {
        "root_is_unit": root_unit,
        "locked": paths_with("locked"),
        "likely_open_in_office": paths_with("likely-open-in-office"),
        "permission_denied": paths_with("permission-denied"),
        "cloud_placeholders": paths_with("cloud-placeholder"),
        "long_paths": paths_with("long-path"),
        "readonly": paths_with("readonly"),
        "system": paths_with("system"),
        "partial_downloads": [{"path": r["path"]} for r in files if r["category"] == "partial-download"],
        "unreadable": unreadable,
    }
    return {
        "summary": summary,
        "risks": risks,
        "atomic_units": units,
        "duplicates": duplicates,
        "skipped": skipped,
        "files": files,
    }


def main(argv: list[str]) -> int:
    configure_stdout()
    args = parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2
    excluded = set(EXCLUDED_DIR_NAMES) | set(args.exclude)

    if args.format == "tree":
        print(render_tree(scan_tree(root, excluded), depth=args.depth))
        return 0

    result = inventory(root, excluded, not args.no_hash, not args.no_lock_check)
    tree_text = render_tree(scan_tree(root, excluded), depth=args.depth)
    document: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "tool": "organize-files/inventory_files.py",
        "generated_at": now_iso(),
        "root": str(root),
        "staging_dir_name": STAGING_DIR_NAME,
        "run_dir": None,
        **result,
        "tree": tree_text,
    }

    if args.run_dir != "none":
        run_dir = (log_base_dir() / new_run_id(root)) if args.run_dir == "auto" else Path(args.run_dir)
        run_dir = run_dir.expanduser().resolve()
        document["run_dir"] = str(run_dir)
        document["run_id"] = run_dir.name
        write_json(run_dir / "inventory.json", document)
        (run_dir / "tree-before.txt").write_text(tree_text + "\n", encoding="utf-8")

    if args.format == "json":
        print_json(document)
    else:
        brief = {key: value for key, value in document.items() if key not in ("files",)}
        brief["duplicates"] = document["duplicates"][:20]
        brief["duplicates_truncated"] = len(document["duplicates"]) > 20
        print_json(brief)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
