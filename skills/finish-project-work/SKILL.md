---
name: finish-project-work
description: Use when an agent runs multi-step development, refactoring, debugging, migration, documentation, or long-running goal work and needs to judge where the real finish line is, or when it keeps laying groundwork, abstracts prematurely, keeps adding improvements, keeps building after the work is done, or has finished local code without reaching the required deployment or public verification. Also for work that must not be declared done too early, or a project that never wraps up.
---

# Finish Project Work

## Core principles

- Finish the task or goal currently agreed on; do not treat continued development as success in itself.
- Drive work by verifiable outcomes, not by infrastructure, layers of abstraction, document count, or time spent.
- First deliver a vertical slice that crosses the necessary layers and can actually be verified, then fill in only the foundations that truly block delivery.
- Wrapping up does not mean lowering quality; prove completion with verification that fits the risk, rather than skipping necessary work.
- What closes is the currently agreed scope; do not call one finished task the permanent completion of the whole product or codebase.

## Set a completion contract

Before implementation, confirm from the user's request and existing evidence:

1. **Target outcome**: what the user can finally get, operate, or confirm.
2. **Scope boundary**: what this work includes and explicitly excludes.
3. **Done criteria**: which observable results must hold for the work to count as done.
4. **Verification evidence**: which tests, builds, checks, run results, or manual confirmations are needed.
5. **Finish line**: whether done means code only, or also merge, data changes, deployment, health checks, or public verification.

If the information is enough to proceed safely, adopt the smallest reasonable assumption and state it in the current conversation; stop to ask only when different answers would materially change the outcome, risk, or permissions. Keep the completion contract in the current task plan or conversation; do not create a new planning or status document for it.

Scale the contract to the task: keep it in the current task plan or conversation for multi-step or high-risk work; for single-step, low-risk work with a clear finish line, infer it briefly in the current reply. Do not create a formal plan, tracking document, or extra work items just to use this skill. The contract must never be more detailed than safe completion of the task requires.

## Limit groundwork

Do infrastructure, shared abstractions, framework changes, research, or broad refactoring only when all of these hold:

- It directly removes a current blocker to one of the done criteria.
- There is no smaller, more direct delivery path of sufficient quality.
- You can name the vertical slice it will unlock and its stop condition.

Do not keep laying groundwork because it might be needed later, the architecture could be prettier, the test framework could be more complete, or tidying along the way feels nicer. After one piece of necessary groundwork, return immediately to verifiable outcomes; do not keep stacking a second and third layer of prerequisite work.

## Drive delivery

Choose the next step in this order:

1. The unmet done criterion closest to completion.
2. The integration gap that keeps existing work from being usable.
3. Defects caused by this change or blocking verification.
4. Necessary foundational blockers that cannot be worked around.

Every work item must answer: "Which done criterion does it advance, and how will it be verified?" If it cannot, do not add it to the current scope automatically.

When exploration turns up new work, classify it:

- **Required for completion**: include it and update the completion contract; if it materially changes the approach, risk, or timeline, tell the user first.
- **Problem caused by this change**: fix it and re-verify before wrapping up.
- **Optional improvement or pre-existing issue**: mention it briefly only if it affects the user's decisions, risk, or next steps; do not implement it, refactor for it, or open a next phase on your own.

After each verifiable batch, recheck the completion gate. If the current completion contract is met, do not generate another batch of work.

## Completion gate

Declare the work done only when all of these hold:

- Every done criterion in the agreed scope has checkable evidence.
- Relevant tests, builds, static checks, and necessary smoke tests pass, in proportion to risk.
- Cross-layer integration, error paths, and important regression risks are verified to a reasonable extent.
- No known issue still keeps the user from getting the target outcome.
- Temporary artifacts are handled, and nothing overwrote or mixed in the user's unrelated changes.
- The finish line the user asked for is reached; if they asked for staging, deployment, or public verification, do not declare done when only local checks pass.

Run only the verification the current scope needs. Do not add new documents, refactors, features, deployments, or long-term improvements to make the wrap-up look more complete.

## Stop and report

After the completion gate passes:

1. Stop changing code, architecture, data, and documents.
2. Lead with the result, then briefly list what was completed and the verification evidence.
3. Disclose only risks, limitations, or gaps that still exist and relate to the current outcome.
4. Leave optional improvements as follow-up candidates; unless the user asks, do not keep implementing or create a next-phase plan.
5. If your tools track goals, to-do lists, or task status, mark them done only when the goal is actually met and no necessary work remains.

Every final report, whether done, not done, or blocked, gives these eight required fields in this order. This closing record is the completion judgment itself; even if the user only asks "is it done?", answer with the eight fields. For small tasks, one sentence per field is enough; do not add verification, documents, or scope to fill the format.

```text
Result (required): done / not done / blocked, and what the user can get now
Target outcome (required): the observable result this work agreed to deliver
Scope boundary (required): what is covered, and extra ideas explicitly left out
Done criteria (required): whether each criterion holds
Verification evidence (required): tests, builds, checks, deployments, or public verification actually run, and their results
Finish line (required): the level actually reached: code, merge, data, deployment, health check, or public status
Remaining risks (required): known risks still relevant to the outcome; if none, write "no known blockers"
Stop reason (required): the completion gate passed, or the current blocker and the external decision needed
```

Write the labels and values in the conversation's language. When evidence is missing, mark the matching done criterion as not met; do not substitute "should pass", lack of remaining time, or "mostly done" for evidence.

Even if time, tokens, or budget remain, do not widen the scope, reinforce foundations, or look for new improvements just to keep working.

If all safe, in-scope alternatives are exhausted and the completion gate still cannot pass, stop expanding foundational work and report the exact blocker, the evidence so far, the criteria still unmet, and the user decision or external change needed.
