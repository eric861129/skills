---
name: consolidate-document-sprawl
description: Use when a project has too many documents, such as the same topic piled up as final, v2, dated, summary, handoff, or archive copies, no single source of truth, documents that contradict each other, have lost their readers, or are hard to navigate, or when the user asks for a full cleanup of existing Markdown, specs, plans, ADRs, READMEs, runbooks, research, and dev logs. For inventorying, consolidating, and safely disposing of existing documents based on evidence.
---

# Consolidate Document Sprawl

## Goals

- Actually reduce document count and maintenance cost; do not just move old documents into a new archive folder.
- Give every kept document a clear purpose, reader, maintenance lifecycle, and single-source-of-truth responsibility.
- Keep content that is still correct and uniquely valuable; remove duplicated, stale, contradictory, and unmaintained content.
- Finish a read-only inventory and consolidation proposal first, then wait for the user to approve an exact list of operations.
- Report the inventory in the current conversation or task plan by default; do not create an inventory report, migration log, or new index document to tidy documents.

## Confirm scope and safety first

1. Check applicable project instructions, version-control status, document sources, and generation pipelines; preserve the user's unrelated changes.
2. Confirm the inventory scope and document types; handle third-party, build output, cache, and auto-generated documents separately.
3. Identify documents bound by regulation, audit, contract, release versioning, or external links, and do not treat them as ordinary duplicates.
4. Record the document count and main entry points before cleanup, but do not write that list as a new project document.
5. Before deleting, confirm version control or another recoverable source; files that are untracked and not backed up need individual confirmation.

Unless the user asks otherwise, touch only documents and their navigation, metadata, or links. You may read code, configuration, tests, and run results to judge whether documents are accurate, but do not modify product features, data, or architecture along the way.

## Build a document inventory

List file names, paths, headings, and link relationships first, then read only the content that needs comparing; do not load every document into context at the start.

If the skill directory contains `scripts/inventory_documents.py`, prefer running the read-only inventory from the project root:

```text
python <skill-directory>/scripts/inventory_documents.py <project-root> --format json
```

Run `--help` first to confirm the arguments. The script writes only to stdout and must not create or modify project documents; it reports paths, headings, hashes, Git status, links, encodings, and generation hints. Identical hashes, file-name hints, or broken links are only leads; they do not replace semantic comparison, canonical-source judgment, retention checks, or deletion approval. If the script cannot run in this environment, complete the same inventory by other read-only means; do not lower the safety gates because of it.

For each document, determine:

- Its path, purpose, primary reader, and maintenance lifecycle.
- Whether it is a hand-written source, a generated result, an external copy, or a temporary work product.
- Whether it is referenced by the main entry point, other documents, code, CI, release pipelines, or external systems.
- Whether it contains correct content that no other document has.
- Which documents it duplicates, contradicts, or stacks with as old and new versions.
- Whether to keep, merge, remove, retain for compliance, regenerate, or hold for a decision.

When determining the canonical source, rely first on current code, configuration, data models, generation pipelines, tests, and runtime evidence, then on maintained official documents and Git history. Do not assume a file is the most correct because its name contains `final` or `v2`, its date is newer, or it is longer.

## Classification and consolidation rules

Assign each document one primary disposition:

- **Keep**: already a clear, correct, and maintained canonical source.
- **Merge**: move the unique, still-correct content into the designated canonical document, then remove the duplicate source.
- **Fix and keep**: the responsibility is right, but the content, navigation, or references need updating.
- **Remove**: fully duplicated, obsolete, only a process log, or without a clear reader and maintainer.
- **Retain for compliance**: cannot be deleted because of audit, regulation, versioning, or external commitments; clearly mark it as not the current source.
- **Regenerate**: a generated result; fix the source or pipeline and regenerate instead of hand-merging generated files.
- **Pending decision**: involves a contradiction, external reference, or ownership question that evidence cannot resolve.

Follow these limits:

- By default, converge content back into existing canonical documents; do not solve too many documents by creating new ones.
- Propose a new canonical document only when no existing document can reasonably serve as the canonical source, and explain why the content cannot be merged.
- Do not substitute "move everything to archive" for judgment; archive only where there is a retention obligation.
- Do not split large documents into more small files during cleanup unless the user explicitly asks and the split genuinely improves ownership boundaries.
- Do not decide deletions on word count, modification date, or file-name similarity alone; confirm the content, references, and canonical source.

## Approval gate

Every time you report document-cleanup decisions, output these seven required fields in this order. Before any delete, move, rename, or large rewrite, present the full cleanup proposal in the current conversation; do not save it as a project report. If evidence for a field is not yet available, write "pending read-only inventory" in that field; do not omit the field or fill it with guesses.

```text
Inventory scope (required): directories, document types, and generation sources included and excluded
Count before/after (required): current document count / expected count after approval
Canonical sources (required): each kept document and its single responsibility
Per-path disposition (required): exact path / keep, merge, fix and keep, remove, retain for compliance, regenerate, or pending decision / reason / where unique content goes
Reference fixes (required): internal links, navigation, metadata, CI, generation pipelines, and known external references to update
Open risks (required): contradictions, retention obligations, ownership, or unbacked content that current evidence cannot resolve
Approval status (required): not approved; waiting for the user to confirm the exact list above
```

Write the labels and values in the conversation's language. Stop after the list and wait for the user's confirmation. Until you have exact approval, do only the read-only inventory; do not clean up part of it first, move files, delete documents, or rewrite canonical sources.

## After approval

1. Update the canonical documents first, bringing in all unique content confirmed as still correct, and remove duplication and contradictions within each document.
2. After verifying the canonical documents are complete, update all internal links, navigation, metadata, CI, and generation-pipeline references.
3. Perform only the moves, renames, and deletions on the approved list; use explicit file paths, not broad paths, wildcards, or recursive delete commands.
4. If the project or environment requires per-file deletion, handle files one at a time; batch deletion requires the user's explicit authorization of the complete list.
5. Do not create a cleanup report, old-file index, mapping table, or archive copy. Version-controlled history is kept by Git or the project's existing history mechanism.
6. If you find a new risk or a document not on the list during execution, stop that operation and get confirmation again; do not widen the authorization.

## Verify and finish

- Compare document counts before and after, and state the reduction; a lower count never justifies sacrificing necessary content.
- Confirm that every piece of unique, still-correct content has a clear destination.
- Search for removed or renamed paths and confirm no references remain in internal links, navigation, metadata, code, or CI.
- Run the project's existing document validators, link checks, doc builds, or necessary smoke tests.
- Check encoding, formatting, and the version-control diff to make sure there is no mojibake, no unrelated change, and no drift between generation sources and outputs.
- In the final report, list only what was kept, merged, removed, and left pending, with verification evidence; do not create a plan for the next round of cleanup.

Stop as soon as every remaining document has a clear responsibility, the single source of truth is no longer duplicated, necessary references work, and all approved operations and verification are complete. If items remain unapproved or cannot be judged safely, list them and stop; do not finish the cleanup by guessing.
