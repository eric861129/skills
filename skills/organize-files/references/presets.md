# Organization presets

Built-in starting points for the plan phase. Pick one (or combine two) based on the inventory signals below, then adapt it to what the inventory actually shows. A preset is a proposal, never a reason to skip approval.

## Choosing a preset

| Inventory signal | Suggested preset |
| --- | --- |
| Mostly installers, archives, and partial downloads; the folder is a download target | `downloads-triage` |
| Mixed file types, few folders, no strong time pattern | `by-type` |
| One or two categories dominate (for example images or scans) and span many years | `by-type-then-date` |
| Images and videos dominate, with camera-style names (IMG_, DSC_, PXL_) | `photo-library` |
| Several atomic units (repos, projects) plus loose files about them | `by-project` |
| Records such as invoices, statements, or reports with dates in the names | `archive-by-date` |

When signals conflict, prefer the preset that moves fewer files to reach a clear structure. If no preset fits, propose a custom rule set in the same format: rule name, match condition, destination pattern.

## Shared rules (apply to every preset)

- **Keep original file names.** Rename only when the user asks, or when a name collision needs a ` (2)` suffix.
- **Atomic units move whole or stay.** Never sort files out of a repo, project, photo library, or VM folder.
- **Do not touch:** excluded folders, links and junctions, system files, and files flagged `locked`, `likely-open-in-office`, or `cloud-placeholder` unless the user approves each one.
- **Duplicates go to staging, never deleted.** Keep the copy that is already in the destination structure, or else the oldest one; stage the rest with `reason: duplicate of <kept path>`.
- **Partial downloads and Office lock files** (`.crdownload`, `.part`, `~$name.docx`) stay where they are and are reported. They usually mean something is still in progress.
- **Depth limit:** target structures go at most 3 levels below the root unless the user asks for more.
- **Folder names:** use the conversation's language or the user's existing naming. Do not mix languages in one level. Avoid characters that are invalid on Windows (`<>:"/\|?*`) and trailing dots or spaces.
- **Empty folders** that the run empties may be removed only if the plan says so (`options.remove_emptied_dirs: true`) and the user approves.

## Presets

### `by-type`

```
<root>/
  Documents/      document, ebook
  Spreadsheets/   spreadsheet
  Presentations/  presentation
  Images/         image
  Videos/         video
  Audio/          audio
  Archives/       archive
  Installers/     installer
  Code/           code (loose files only; projects are units)
  Design/         design, font
  Projects/       atomic units
  Others/         other, shortcut
```

Merge any category with fewer than 3 files into `Others/` so the plan does not create near-empty folders.

### `by-type-then-date`

Same top level as `by-type`, then `YYYY/` (or `YYYY/YYYY-MM/` when a single year has more than about 200 files):

```
<root>/Images/2023/IMG_0012.jpg
<root>/Documents/2024/2024-05/contract.pdf
```

The date is the file's modified time (`mtime` in the inventory). Say so in the plan: copied or downloaded files may carry the copy date, not the creation date. If a file name contains an explicit date (`2023-04-01`, `20230401`, `IMG_20230401_...`), prefer it and state that rule.

### `photo-library`

```
<root>/Photos/YYYY/YYYY-MM-DD[ event]/
<root>/Videos/YYYY/YYYY-MM-DD[ event]/
<root>/Photos/_Edited/        exports from editors, if recognizable
```

Keep RAW and JPEG pairs (`IMG_1234.CR3` + `IMG_1234.JPG`) together and keep sidecars (`.xmp`, `.aae`) next to their image. Never move files out of a `photos-library` or `lightroom-catalog` unit: the catalog stores paths.

### `downloads-triage`

```
<root>/Installers/
<root>/Archives/
<root>/Documents/
<root>/Media/          image, video, audio
<root>/_Review/        anything older than 180 days the user may not need
```

`_Review/` is an ordinary folder, not staging: it holds files the user should look at, and nothing in it is a deletion candidate unless the user says so. Installers that duplicate one another (same hash) go to staging.

### `by-project`

```
<root>/Projects/<project>/      atomic units, moved whole
<root>/Projects/<project>-files/   loose files clearly about that project
<root>/Shared/                  files used by several projects
<root>/Others/
```

Only link a loose file to a project when there is evidence: the project name in the file name, or the file sitting next to the project. Put uncertain files in `Others/` and list them in the plan.

### `archive-by-date`

```
<root>/YYYY/YYYY-MM/<file>
<root>/Undated/
```

Use a date from the file name if there is one, else `mtime`. Files without any usable date go to `Undated/`.

## Writing the plan from a preset

For each rule, report: rule name → match condition → destination pattern → how many files and bytes it affects → 3 to 5 sample moves. Put the full per-file list only in `manifest.json`. List every file the preset does not cover, with the reason.
