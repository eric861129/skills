# Skills

[English](./README.md) | **繁體中文**

我自己寫、自己也在用的 Agent Skill。每個 Skill 是 `skills/` 底下的一個資料夾，核心是一份 `SKILL.md`，任何支援 `SKILL.md` 格式的 Agent（Claude Code、Codex 等）都能使用。

| Skill | 用途 |
| --- | --- |
| [`control-document-growth`](./skills/control-document-growth/) | 在文件增生前介入。Agent 準備建立、拆分或重寫文件時，優先更新既有的唯一真實來源，不再產生階段文件、摘要與 final 版本。 |
| [`consolidate-document-sprawl`](./skills/consolidate-document-sprawl/) | 清理已經堆疊的文件。盤點重複、過時與互相矛盾的文件，提出逐檔處置清單，經你核准後才整併或刪除。 |
| [`finish-project-work`](./skills/finish-project-work/) | 讓長任務真正收尾。先定義完成條件，限制無止境打底與範圍擴張，驗證通過就停止。 |
| [`organize-files`](./skills/organize-files/) | 以盤點、核准計畫、實際搬遷、結果告知四個階段整理雜亂資料夾。絕不刪除檔案（重複檔移到暫存資料夾），遇到鎖定檔會重試後略過並指出占用程式，還原用 journal 存在桌面。 |
| [`reply-with-gricean-maxims`](./skills/reply-with-gricean-maxims/) | 以格萊斯會話準則讓回覆直接、不說廢話：真實、適量、切題、清楚，但不漏掉你需要的資訊。 |

每個 Skill 資料夾內，`SKILL.md` 是英文版，`SKILL.zh-TW.md` 是繁中版。想讓 Agent 使用繁中版，安裝後把 `SKILL.zh-TW.md` 改名為 `SKILL.md`（取代英文版）即可。

## 安裝

把需要的 Skill 資料夾複製到 Agent 的 skills 目錄：

```bash
git clone https://github.com/eric861129/skills.git
cp -r skills/skills/finish-project-work ~/.claude/skills/   # Codex：~/.codex/skills/
```

## 授權

[MIT](./LICENSE)
