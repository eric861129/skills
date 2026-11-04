# Data structures and file formats

Every run keeps its records on the user's Desktop, outside the folder being organized, so the target folder only ever contains the organized files and the staging folder.

## Locations

```
<Desktop>/organize-files-logs/<run-id>/       run folder (records only)
  inventory.json       phase 1: written by inventory_files.py
  tree-before.txt      phase 1: folder tree before organizing
  manifest.json        phase 2: written by the agent, approved by the user
  journal.jsonl        phase 3: one line per attempt, appended and fsynced
  summary.json         phase 4: written by apply_manifest.py
  tree-after.txt       phase 4: folder tree after organizing
  undo-journal.jsonl   only if undo.py --execute was run

<root>/_organize-staging/<run-id>/             staged files, original relative paths kept
```

- `<Desktop>` is the real Desktop known folder (it follows OneDrive redirection on Windows). The environment variable `ORGANIZE_FILES_LOG_DIR` overrides the base folder; use it only when the user asks.
- `<run-id>` is `YYYYMMDD-HHMMSS-<root folder name>`.
- Staging lives inside the root on purpose: moving within one volume is an atomic rename, so staging never copies data.
- Always give the user both absolute paths: the run folder and the staging folder.

## `inventory.json`

```jsonc
{
  "schema_version": "1.0",
  "tool": "organize-files/inventory_files.py",
  "generated_at": "2026-11-04T08:25:12+08:00",
  "root": "D:\\Users\\me\\Downloads",
  "run_dir": "C:\\Users\\me\\Desktop\\organize-files-logs\\20261104-082512-Downloads",
  "run_id": "20261104-082512-Downloads",
  "staging_dir_name": "_organize-staging",
  "summary": {
    "file_count": 1240, "dir_count": 37, "unit_count": 2,
    "total_bytes": 9876543210, "loose_file_bytes": 8123456789,
    "top_level_entry_count": 310, "max_depth": 4,
    "by_category": { "image": { "count": 600, "bytes": 1200000000 } },
    "by_year": { "2023": 400, "2024": 840 },
    "top_extensions": { ".jpg": 580, ".pdf": 120 },
    "largest_files": [ { "path": "isos/win.iso", "size": 5400000000, "human": "5.0 GB" } ],
    "duplicate_groups": 14, "duplicate_reclaimable_bytes": 340000000
  },
  "risks": {
    "root_is_unit": null,                  // e.g. "git-repo": stop and confirm scope
    "locked": [ { "path": "a.xlsx", "holders": ["EXCEL.EXE (pid 4120)"] } ],
    "likely_open_in_office": [ { "path": "report.docx" } ],
    "permission_denied": [], "cloud_placeholders": [], "long_paths": [],
    "readonly": [], "system": [], "partial_downloads": [], "unreadable": []
  },
  "atomic_units": [
    { "path": "my-app", "kind": "git-repo", "files": 812, "bytes": 45000000, "mtime": "2024-02-01T10:00:00" }
  ],
  "duplicates": [
    { "sha256": "…", "size": 2311456, "paths": ["IMG_0012.jpg", "old/IMG_0012 (1).jpg"] }
  ],
  "skipped": [ { "path": "node_modules", "reason": "excluded-name" } ],
  "files": [
    {
      "path": "IMG_0012.jpg",              // relative to root, "/" separators
      "size": 2311456,
      "mtime": "2024-05-02T10:11:00",
      "ext": ".jpg",
      "category": "image",                 // see "Categories" below
      "flags": ["hidden"],                 // see "Flags" below
      "sha256": "…",                       // only for files that share a size
      "holders": ["…"]                     // only when flagged locked
    }
  ],
  "tree": "Downloads/  (1240 files, 9.2 GB)\n├── …"
}
```

The script prints everything except `files` to stdout, so the conversation never has to hold the per-file list. Read `files` from `inventory.json` only when building the manifest.

### Categories

`image`, `video`, `audio`, `document`, `spreadsheet`, `presentation`, `ebook`, `archive`, `installer`, `code`, `font`, `design`, `shortcut`, `partial-download`, `office-lock-file`, `other`. The extension lists are in `scripts/organize_common.py` (`CATEGORIES`).

### Flags

| Flag | Meaning | Default handling |
| --- | --- | --- |
| `hidden`, `system` | Hidden or OS file | Leave in place |
| `readonly` | Read-only attribute | Movable; mention it |
| `symlink`, `reparse-point` | Link or junction | Leave in place |
| `cloud-placeholder` | Online-only cloud file | Leave in place unless approved |
| `long-path` | Path ≥ 260 characters | Prefer a shorter destination |
| `locked` | Another process blocks moving it | Plan it; expect a retry |
| `permission-denied` | No right to move it | Leave in place; report |
| `likely-open-in-office` | A `~$` owner file sits beside it | Ask the user to close it first |
| `unreadable` | Could not be hashed | Report |

### Atomic unit kinds

`git-repo`, `hg-repo`, `svn-checkout`, `project` (package.json, pyproject.toml, *.sln, Cargo.toml, go.mod, …), `lightroom-catalog`, `photos-library`, `app-bundle`, `video-library`, `bundle`, `virtual-machine`. A unit is listed once, with totals, and its contents never appear in `files`.

## `manifest.json` (written by the agent)

```jsonc
{
  "schema_version": "1.0",
  "root": "D:\\Users\\me\\Downloads",
  "destination_roots": [],                 // extra absolute roots allowed as dst
  "preset": "downloads-triage",
  "options": {
    "remove_emptied_dirs": false,          // true only if the user approved it
    "tree_depth": 3
  },
  "approval": {
    "approved_by_user": false,             // set true only after explicit approval
    "approved_at": null,
    "summary": "Approved: 1,180 moves, 14 staged duplicates, 3 locked files kept in plan"
  },
  "operations": [
    { "id": 1, "op": "move", "src": "IMG_0012.jpg", "dst": "Media/IMG_0012.jpg",
      "rule": "downloads-triage:media", "on_conflict": "auto" },
    { "id": 2, "op": "stage", "src": "old/IMG_0012 (1).jpg",
      "reason": "duplicate of IMG_0012.jpg", "rule": "duplicates" },
    { "id": 3, "op": "move", "src": "my-app", "dst": "Projects/my-app", "rule": "units" }
  ]
}
```

Rules enforced by `apply_manifest.py`:

- `op` is `move` (also used for renames) or `stage`. Any `delete` is rejected.
- `src` and `dst` are relative to `root` (or absolute). `dst` must be inside `root` or a `destination_roots` entry and outside the staging folder.
- `stage` needs a `reason`; its destination is computed: `<root>/_organize-staging/<run-id>/<src>`.
- No two operations share a `src` or a `dst`, and no `src` sits inside another operation's `src`.
- A `src` inside an atomic unit is rejected unless the operation sets `"allow_inside_unit": true` (only with the user's explicit approval).
- `on_conflict` when `dst` already exists: `auto` (default; stage `src` if it is byte-identical to `dst`, else add ` (2)`), `suffix`, or `skip`.
- `--execute` refuses to run unless `approval.approved_by_user` is `true`.

## `journal.jsonl`

One JSON object per line, appended and flushed to disk right after each attempt, so an interrupted run can resume (`--execute` skips finished ids) and be undone.

```jsonc
{"id": "run", "op": "run_start", "status": "info", "root": "…", "staging_dir": "…", "ts": "…"}
{"id": 1, "op": "move", "effective_op": "move", "src": "D:\\…\\IMG_0012.jpg",
 "planned_dst": "D:\\…\\Media\\IMG_0012.jpg", "final_dst": "D:\\…\\Media\\IMG_0012.jpg",
 "status": "done", "error": null, "note": null, "attempts": 1,
 "created_dirs": ["D:\\…\\Media"], "ts": "…"}
{"id": 4, "op": "move", "status": "locked", "attempts": 4,
 "error": "[WinError 32] …", "holders": ["EXCEL.EXE (pid 4120)"], "…": "…"}
{"id": "rmdir:old", "op": "rmdir_empty", "status": "rmdir_empty", "src": "D:\\…\\old", "ts": "…"}
```

Paths in the journal are absolute. The latest line for an id is its current status. Statuses are listed in `error-handling.md`.

## `summary.json`

```jsonc
{
  "schema_version": "1.0",
  "mode": "execute",                       // or "retry-failed"
  "finished_at": "…", "root": "…", "run_dir": "…", "journal": "…", "staging_dir": "…",
  "planned_operations": 1197, "attempted_this_run": 1197,
  "status_counts": { "done": 1180, "staged": 14, "locked": 3 },
  "bytes_moved": 8000000000, "bytes_moved_human": "7.5 GB",
  "staged": [ { "src": "old/IMG_0012 (1).jpg", "staged_at": "…", "note": "…" } ],
  "removed_empty_dirs": [],
  "needs_attention": [ { "id": 4, "status": "locked", "src": "…", "holders": ["EXCEL.EXE (pid 4120)"] } ],
  "tree_after": "Downloads/ …",
  "undo_command": "python \"…/undo.py\" \"…/20261104-082512-Downloads\" --execute"
}
```

Exit codes: `0` everything finished, `1` manifest invalid, `2` missing input, `3` not approved, `4` finished with items needing attention.

## Report templates

### Plan (phase 2): approval gate

Present in the conversation, in this order, with labels in the conversation's language:

```text
Scope: root, included/excluded folders, atomic units kept whole
Records: run folder on the Desktop (absolute path)
Counts: files/folders/top-level entries now → expected top-level entries after
Target structure: tree of the proposed layout with file counts per folder
Rules: preset and each rule → match → destination → count/bytes → samples
Staging: what goes to <root>/_organize-staging/<run-id>/ and why (nothing is deleted)
Exceptions: locked / open / cloud / permission / long-path / uncovered files and how each is handled
Risks and open questions: anything the evidence cannot settle
Approval status: not approved; waiting for the user to confirm
```

### Result (phase 4)

```text
Outcome: counts per status (moved, staged, skipped, locked, failed) and bytes moved
Final structure: tree-after, with a short before/after comparison
Changes by rule: where each category went
Staging: staging folder path, item count, and size; the user decides what to delete
Needs attention: each locked/failed item, its holder or error, and the next step
Records: run folder path on the Desktop (journal, manifest, trees, summary)
Undo: the exact undo command
```
