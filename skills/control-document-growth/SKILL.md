---
name: control-document-growth
description: Use when an agent is about to create, split, rewrite, summarize, or hand off project documentation, especially when the topic already has a README, spec, ADR, runbook, plan, research note, or dev log, or when the only reason for a new file is a new phase, version, date, proof of completion, convenience, or possible future use. Decides whether to update the existing source of truth, create one necessary new document, or leave the docs unchanged.
---

# Control Document Growth

## Core principles

- Aim for information that can be found and maintained correctly, not for document count or a paper trail of deliverables.
- Update existing documents by default. Not finding a perfect place does not mean a new document is required.
- Keep a single source of truth; do not store the same rule, status, or decision in multiple documents.
- Do not create documents the user did not ask for just to preserve reasoning, work logs, or phase results.
- When the user explicitly asks for a specific document, create it, but do not spin off summaries, supplements, or handoff versions.

## Survey before writing

1. Look at the file names, directories, and headings of existing documents first, then read only the relevant sections; do not load every document in full up front.
2. Find the closest existing single source of truth, along with its readers, purpose, and maintenance lifecycle.
3. Classify the content as: adding to existing content, replacing outdated content, splitting oversized content, or a standalone topic.
4. If an existing document can clearly hold the content, update that document and stop evaluating new files.

## Gate for new documents

Create a new document only when no suitable existing document can hold the content and at least one of these needs applies:

- The readers, maintainers, permissions, or lifecycle clearly differ from those of existing documents.
- The content has a stable purpose that can be maintained on its own, and putting it in an existing document would blur that document's responsibility.
- An existing document has become hard to navigate or maintain, and splitting out one cohesive topic materially improves readability.
- Project conventions, the toolchain, regulation, or the user explicitly require a separate document.

These reasons alone are not enough to create a document:

- A new phase, a date change, or a version name change.
- Wanting to keep work history, reasoning, scratch research, or proof of completion.
- Feeling that a new file is easier than reorganizing existing sections.
- Wanting a summary, a quick reference, a full version, and a final version at the same time.
- It might be useful someday, but has no clear reader or maintainer today.

## Updating and splitting

- Prefer adding or reorganizing sections in existing documents, and replace outdated text directly; do not keep appending addenda to the end of a document.
- When moving content, keep one canonical version and update existing links; remove duplicates confirmed to have no references only when permissions and safety allow.
- When a split is necessary, split out only one cohesive topic, and leave a summary and a direct link in the original document.
- Link every secondary document directly from the main entry point; avoid multi-level indexes and deep reference chains.
- Do not create a README, CHANGELOG, quick reference, install guide, or handoff document on your own unless it is a product convention or an explicit deliverable.
- Do not hand-edit generated documents; update the source or the generation process.

## Execute and report

1. Decide which existing document to update before writing; if the agent creates a document the user did not specify, first explain in the current conversation why the content cannot go into an existing document and which gate it passed.
2. Change only the minimum set of documents the current request needs; do not tidy unrelated documents along the way.
3. When done, check that the new content has not introduced duplicate rules, conflicting sources, broken links, or unrequested derivative documents.
4. If no document change is needed, leave things as they are and continue the original task; do not create a document just to use this skill.

Before writing, record the following decision in the current conversation; do not save it as a project document:

```text
Decision: update an existing document / create one document / no document change
Canonical source: the existing file that takes the content, or the single responsibility the new document will own
Creation gate: not applicable, or the specific gate passed and its evidence
Change scope: the minimum list of documents this change will modify or add
Stop reason: the content is in the correct source and no derivative document is needed
```

Write the labels and values in the conversation's language. If the information is still insufficient to determine the canonical source or the creation gate, finish the necessary read-only checks first; do not fill fields with guesses. Small changes use the same fields at one sentence each; do not expand the survey or create a formal plan just to complete the format.

## Stop condition

Stop document work as soon as the request sits in the correct single source of truth, required links work, and nothing is duplicated. Unless the user asks, do not create summaries, history, indexes, handoffs, or follow-up planning documents.
