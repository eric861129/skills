#!/usr/bin/env python3
"""Reverse an organize-files run using its journal.

Default is a dry run that lists what would be restored. `--execute` moves
every completed or staged item back to its original path (newest first),
recreates folders the run removed because they were empty, and removes only
the folders the run created, and only if they are empty again. It never
deletes files. Results go to undo-journal.jsonl in the run folder.
"""

from __future__ import annotations

import argparse
from collections import Counter
import os
from pathlib import Path
import sys
from typing import Any

sys.dont_write_bytecode = True

from apply_manifest import cross_volume_move, make_parents  # noqa: E402
from organize_common import (  # noqa: E402
    OrganizeError,
    STAGING_DIR_NAME,
    append_jsonl,
    classify_os_error,
    configure_stdout,
    now_iso,
    print_json,
    read_jsonl,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", help="Run folder that holds journal.jsonl")
    parser.add_argument("--execute", action="store_true", help="Perform the restore")
    parser.add_argument("--allow-cross-volume", action="store_true",
                        help="Allow copy+verify+remove-source restores between volumes")
    return parser.parse_args(argv)


def try_rmdir(path: Path) -> bool:
    try:
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            return True
    except OSError:
        pass
    return False


def main(argv: list[str]) -> int:
    configure_stdout()
    args = parse_args(argv)
    run_dir = Path(args.run_dir).expanduser().resolve()
    journal = run_dir / "journal.jsonl"
    undo_journal = run_dir / "undo-journal.jsonl"
    records = read_jsonl(journal)
    if not records:
        print(f"error: no journal at {journal}", file=sys.stderr)
        return 2
    already = {r["id"] for r in read_jsonl(undo_journal) if r.get("status") in ("restored", "recreated")}
    root = Path(next((r["root"] for r in records if r.get("op") == "run_start"), run_dir))

    # Latest record per id, kept in journal order.
    latest: dict[Any, tuple[int, dict[str, Any]]] = {}
    for index, record in enumerate(records):
        if record.get("op") != "run_start":
            latest[record["id"]] = (index, record)
    ordered = [rec for _i, rec in sorted(latest.values(), key=lambda pair: pair[0], reverse=True)]

    plan: list[dict[str, Any]] = []
    for record in ordered:
        if record["id"] in already:
            continue
        status = record.get("status")
        if status in ("done", "staged"):
            plan.append({"id": record["id"], "action": "move_back",
                         "from": record["final_dst"], "to": record["src"],
                         "created_dirs": record.get("created_dirs", [])})
        elif status == "rmdir_empty":
            plan.append({"id": record["id"], "action": "recreate_dir", "to": record["src"]})
        elif status == "copied_source_locked":
            plan.append({"id": record["id"], "action": "manual",
                         "note": f"both {record['src']} and its verified copy {record['final_dst']} exist; "
                                 "the user decides which to keep"})
        elif record.get("created_dirs"):
            plan.append({"id": record["id"], "action": "remove_created_dirs",
                         "created_dirs": record["created_dirs"]})

    if not args.execute:
        print_json({"mode": "dry-run", "run_dir": str(run_dir), "steps": len(plan),
                    "actions": dict(Counter(p["action"] for p in plan)), "plan": plan})
        return 0

    results = []
    for step in plan:
        result: dict[str, Any] = {**step, "ts": now_iso()}
        try:
            if step["action"] == "move_back":
                source, target = Path(step["from"]), Path(step["to"])
                if not source.exists():
                    raise OrganizeError("source_missing", f"{source} is gone; nothing to restore")
                if target.exists():
                    raise OrganizeError("target_exists", f"{target} exists again; restore by hand")
                make_parents(target)
                try:
                    os.rename(source, target)
                except OSError as error:
                    if classify_os_error(error) != "cross_volume":
                        raise
                    if not args.allow_cross_volume:
                        raise OrganizeError("cross_volume", "different volume; rerun with --allow-cross-volume") from error
                    cross_volume_move(source, target)
                for directory in reversed(step.get("created_dirs", [])):
                    try_rmdir(Path(directory))
                result["status"] = "restored"
            elif step["action"] == "recreate_dir":
                Path(step["to"]).mkdir(parents=True, exist_ok=True)
                result["status"] = "recreated"
            elif step["action"] == "remove_created_dirs":
                for directory in reversed(step["created_dirs"]):
                    try_rmdir(Path(directory))
                result["status"] = "cleaned"
            else:
                result["status"] = "manual"
        except OrganizeError as error:
            result["status"], result["error"] = error.kind, str(error)
        except OSError as error:
            result["status"], result["error"] = classify_os_error(error), str(error)
        append_jsonl(undo_journal, result)
        results.append(result)

    staging_run = root / STAGING_DIR_NAME / run_dir.name
    try_rmdir(staging_run)
    try_rmdir(root / STAGING_DIR_NAME)

    problems = [r for r in results if r["status"] not in ("restored", "recreated", "cleaned")]
    print_json({"mode": "undo", "run_dir": str(run_dir), "undo_journal": str(undo_journal),
                "status_counts": dict(Counter(r["status"] for r in results)),
                "needs_attention": problems})
    return 0 if not problems else 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
