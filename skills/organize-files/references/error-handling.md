# Locked files and error handling

Every failure is recorded with a status, kept out of the way of the other operations, and reported to the user with a concrete next step. A failure never widens what the agent is allowed to do.

## Hard limits

- Never terminate, kill, or restart a process to free a file, even if the holder is known.
- Never force-close handles (Process Explorer, `handle.exe -c`, `openfiles /disconnect`, and the like).
- Never change ownership, ACLs, attributes, or security settings to get past `permission_denied`.
- Never delete a file to resolve a conflict, a failed copy, or a duplicate. Stage it or report it.
- Never retry indefinitely: the retry schedule is fixed and short.

## Locked files

**Detect.** During inventory on Windows, each file is opened with DELETE access while sharing everything. This is what a rename needs, so a sharing violation (WinError 32/33) flags the file `locked`. The Restart Manager API then names the holder, e.g. `EXCEL.EXE (pid 4120)`. On macOS and Linux, open files rarely block a rename; `lsof` is used to name holders when a move does fail. A `~$name.docx` or `.~lock.name#` owner file next to a document flags it `likely-open-in-office`.

**Plan.** Keep locked files in the manifest, but list them under exceptions. Ask the user to close the holding programs before approval. Locks from antivirus, search indexing, thumbnail generation, or cloud sync are often brief.

**Execute.** A locked move is retried after 1 s, 3 s, and 10 s (`--retry-delays`). If it is still locked, the journal records `locked` with the holders, and the run continues with the next operation. One locked file never stops the run.

**Retry.** After the user closes the programs, run `apply_manifest.py <run-dir> --retry-failed`. It re-runs only operations whose latest status is retryable and leaves finished ones untouched.

**Partial state.** For a cross-volume move whose copy was verified but whose source stayed locked, the status is `copied_source_locked`: both copies exist. Report both paths. A retry completes the move once the source is free; otherwise the user decides which copy to keep.

## Status reference

| Status | Cause | Automatic handling | Tell the user |
| --- | --- | --- | --- |
| `done` | Moved | — | Counted in the result |
| `staged` | Moved to staging | — | Listed under staging; the user decides what to delete |
| `skipped` | `on_conflict: skip` and target exists | None | Which target blocked it |
| `locked` | Another process has it open | Retried 3 times, then skipped | Holder name; "close it, then I will rerun the failed items" |
| `copied_source_locked` | Cross-volume copy verified, source locked | Copy kept, source kept | Both paths; retry or choose |
| `permission_denied` | No rights, or protected location | Not retried automatically | Path; suggest running with the right account or leaving it |
| `cloud_placeholder` | Online-only cloud file | Skipped unless `--allow-cloud-placeholders` | Moving it may download it; ask first |
| `cross_volume` | Destination on another volume | Skipped unless `--allow-cross-volume` (files only; folders never) | Ask before copying across volumes |
| `path_too_long` | Path exceeds the OS limit | Not retried | Propose a shorter destination |
| `disk_full` | No space at destination | Not retried | Free space needed; nothing was removed |
| `source_missing` | File moved or deleted since inventory | None | Probably changed by the user or an app |
| `target_exists` | Target appeared during the run | None | Path; rerun picks a suffix |
| `failed` | Anything else, including a copy hash mismatch | Not retried automatically | Raw error |
| `rmdir_empty` | Emptied folder removed (only if approved) | Recreated by undo | Listed under removed empty folders |

Retryable with `--retry-failed`: `locked`, `copied_source_locked`, `permission_denied`, `cloud_placeholder`, `cross_volume`, `path_too_long`, `disk_full`, `failed`.

## Interrupted runs

The journal is flushed after every operation. If a run stops (crash, closed terminal, reboot), run `--execute` again with the same run folder: finished ids are skipped. Before resuming, rerun the dry run and check that `source_missing` predictions are explained.

## Undo

`undo.py <run-dir>` lists what would be restored. With `--execute` it moves every `done` and `staged` item back to its original path (newest first), recreates folders removed as empty, and removes folders the run created only if they are empty again. Items that cannot go back (the original path is occupied again, or the file is gone) are reported, not forced. Undo also never deletes files.
