# Skills

**English** | [繁體中文](./README.zh-TW.md)

Agent skills I write and use myself. Each skill is a folder under `skills/` built around a `SKILL.md`, so it works with any agent that supports the `SKILL.md` format (Claude Code, Codex, and others).

| Skill | What it does |
| --- | --- |
| [`control-document-growth`](./skills/control-document-growth/) | Stops document sprawl before it starts. When an agent is about to create, split, or rewrite docs, it updates the existing source of truth instead of adding phase notes, summaries, and "final" versions. |
| [`consolidate-document-sprawl`](./skills/consolidate-document-sprawl/) | Cleans up sprawl that already exists. Inventories duplicate, stale, and conflicting docs, proposes an exact per-file plan, and merges or deletes only after you approve it. |
| [`finish-project-work`](./skills/finish-project-work/) | Gets long tasks to a real finish. Sets done criteria up front, cuts endless groundwork and scope creep, and stops once verification passes. |
| [`reply-with-gricean-maxims`](./skills/reply-with-gricean-maxims/) | Makes replies direct and fluff-free using Grice's maxims: true, as informative as needed, relevant, and clear, without dropping details you need. |

Each skill also ships a Traditional Chinese version, `SKILL.zh-TW.md`, next to its `SKILL.md`.

## Install

Copy a skill folder into your agent's skills directory:

```bash
git clone https://github.com/eric861129/skills.git
cp -r skills/skills/finish-project-work ~/.claude/skills/   # Codex: ~/.codex/skills/
```

## License

[MIT](./LICENSE)
