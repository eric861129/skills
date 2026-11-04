---
name: organize-files
description: Use when the user wants files or folders organized, sorted, tidied, restructured, or deduplicated, such as a messy Downloads or Desktop folder, a photo dump, a shared drive, or a project folder full of loose files. Runs a four-phase process (inventory, plan with approval, move, report), never deletes files (duplicates and clutter go to a staging folder for the user to decide), handles locked or in-use files by retrying and then skipping with the holding program named, keeps run records and an undo journal on the Desktop, and ends by reporting what moved, the final folder tree, and anything that needs the user's action.
---

# Organize Files

## Goals

- Turn a messy folder into a clear structure the user approved, with every change recorded and reversible.
- **Never delete a file.** Duplicates, clutter, and suspected junk go to `<root>/_organize-staging/<run-id>/`; the user decides what to delete, and you tell them where it is.
- Keep run records (inventory, manifest, journal, folder trees, summary) in `<Desktop>/organize-files-logs/<run-id>/`, and tell the user that path.
- Leave nothing unexplained: at the end, every planned item is moved, staged, or listed with a reason and a next step.

## Bundled resources

- `scripts/inventory_files.py`: read-only inventory; creates the run folder on the Desktop.
- `scripts/apply_manifest.py`: validates and dry-runs the manifest by default; `--execute` and `--retry-failed` perform it.
- `scripts/undo.py`: reverses a run from its journal (dry run unless `--execute`).
- `references/presets.md`: built-in organization presets and how to choose one. Read it before planning.
- `references/data-structures.md`: run folder layout, JSON schemas, and the plan and result report templates. Read it before writing the manifest.
- `references/error-handling.md`: locked-file procedure and every status with its handling. Read it when anything fails.

The scripts use only the Python standard library. Run `--help` first. If Python is unavailable, follow the same phases with the shell's own read-only listing and single-file move commands, keep the same records by hand in the run folder, and do not relax any safety rule.

## Phase 0: Scope and safety

1. Confirm the root folder and anything the user wants excluded. If the request is vague ("clean up my computer"), ask which folder; never organize a whole drive, the user profile root, or system or program folders.
2. If the root itself is a repository or project (`risks.root_is_unit`), stop and confirm. Organizing inside a repository belongs to that project's own tooling.
3. Note what must not move: atomic units (repositories, projects, photo libraries, VM folders), excluded folders, links and junctions, system files, and app-managed folders whose paths other software stores.
4. Allowed operations are moving, renaming, creating folders, and staging. Removing an emptied folder needs explicit approval. Nothing else.

## Phase 1: Inventory (read-only)

```text
python <skill-dir>/scripts/inventory_files.py "<root>"
```

This creates the run folder on the Desktop, writes `inventory.json` and `tree-before.txt`, and prints the summary (counts by category, year, and extension; largest files; duplicates; atomic units; risks; the current tree). It does not touch the root folder.

Read the summary, not the whole file list. Note the dominant categories, time span, duplicate volume, atomic units, and every risk group: `locked`, `likely_open_in_office`, `cloud_placeholders`, `permission_denied`, `long_paths`, `partial_downloads`.

## Phase 2: Plan (approval gate)

1. Pick a preset from `references/presets.md` using the inventory signals, adapt it, and name the adaptation. Offer one alternative only if it fits clearly better for a different goal.
2. Write `<run-dir>/manifest.json` following `references/data-structures.md`, with `approval.approved_by_user: false`. Use `move` for moves and renames, `stage` (with a `reason`) for duplicates and clutter. Never write a delete.
3. Run the dry run and fix every validation error:

   ```text
   python <skill-dir>/scripts/apply_manifest.py "<run-dir>"
   ```

4. Present the plan with the template in `references/data-structures.md`: scope, records path, counts, target tree, rules with counts and samples, staging, exceptions, risks, and approval status. Show rules and samples in the conversation; the full per-file list stays in the manifest.
5. Stop and wait. Do not move anything until the user approves this plan. If they change it, update the manifest, dry-run again, and show what changed.

When approved, set `approval.approved_by_user: true`, `approved_at`, and a one-line `summary` of what was approved. Approval covers exactly the manifest shown; anything new needs a new approval.

## Phase 3: Move

```text
python <skill-dir>/scripts/apply_manifest.py "<run-dir>" --execute
```

- The script performs only manifest operations, appends each result to `journal.jsonl`, and continues past failures.
- Locked files are retried after 1 s, 3 s, and 10 s, then skipped with the holding program recorded. Do not close, kill, or unlock anything yourself. Tell the user which program holds which file. After they close it, run `--retry-failed`.
- Cross-volume moves and online-only cloud files are skipped unless the user approved `--allow-cross-volume` or `--allow-cloud-placeholders`.
- If something unexpected appears (a new risk, files not in the inventory, many `source_missing` results), stop, report, and get confirmation before continuing.
- An interrupted run resumes with the same command; finished items are skipped.

## Phase 4: Report

Use `summary.json` and the result template in `references/data-structures.md`. Always include:

- Counts per status and bytes moved.
- The final folder tree (`tree-after.txt`) with a short before/after comparison.
- Where each category went.
- The staging folder's absolute path, item count, and size, plus a clear statement that nothing was deleted and the user decides what to remove.
- Every item that needs attention, with its holder or error and the next step.
- The run folder's absolute path on the Desktop, and the exact undo command.

Write in the conversation's language. Do not claim success for items that were skipped or failed.

## Stop conditions

Stop when every approved operation is `done`, `staged`, or reported with a reason, and the result report is delivered. Do not reorganize further, rename files for style, or start a second round unless the user asks. If the user asks to delete staged files, tell them where the staging folder is and let them delete it themselves; this skill does not delete.
