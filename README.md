# Skills

這裡收錄我自己寫、自己也在用的 Agent Skill，以開源方式公開。每個 Skill 都是 `skills/` 底下的獨立資料夾，核心是一份 `SKILL.md`，可以用在 Claude Code，也可以用在 Codex。

## Skill 一覽

| Skill | 使用時機 | 核心作用 |
| --- | --- | --- |
| [`control-document-growth`](./skills/control-document-growth/) | Agent 準備建立、拆分或重寫文件時 | 優先更新既有權威文件，阻止不必要的新文件與版本堆疊 |
| [`consolidate-document-sprawl`](./skills/consolidate-document-sprawl/) | 專案已出現重複、過時、矛盾或難以導覽的文件時 | 盤點並整併有效內容，在核准後安全移除多餘文件 |
| [`finish-project-work`](./skills/finish-project-work/) | 執行多階段開發、重構、移轉或 Goal 任務時 | 以完成條件推進交付，限制無止境打底與範圍擴張 |

### control-document-growth

[`control-document-growth`](./skills/control-document-growth/SKILL.md) 在文件建立前介入。它要求 Agent 先盤點現有文件，找到唯一真實來源，再判斷內容應補充、取代、拆分或獨立建立。

只有在讀者、維護責任、生命週期或工具要求確實不同時，才允許新增文件。新階段、日期改變、完成證明或「未來可能有用」都不足以成為新增理由。

### consolidate-document-sprawl

[`consolidate-document-sprawl`](./skills/consolidate-document-sprawl/SKILL.md) 處理已經形成的文件堆疊。它先以唯讀方式建立文件清冊，辨識權威來源、重複內容、矛盾版本、生成文件與依法必須保留的紀錄。

Skill 會先提出精確的整併與刪除清單並等待核准。核准後才整併有效內容、修復引用，並依明確路徑移除多餘文件；它不會把所有舊文件搬進 `archive` 假裝完成整理。

### finish-project-work

[`finish-project-work`](./skills/finish-project-work/SKILL.md) 從任務開始就建立完成契約，包括目標、範圍、完成條件、驗證證據與終點層級。

它要求每項工作直接推進可驗證成果，限制連續打底、預先抽象化與自行追加範圍。每完成一個批次就重新檢查完成閘門；條件通過後立即停止，不會因仍有時間或 Token 而繼續開發。

### 搭配方式

三個 Skill 可以單獨使用，也可以依工作階段搭配：

- 文件尚未失控：使用 `control-document-growth` 預防增生。
- 文件已經堆疊：使用 `consolidate-document-sprawl` 完成盤點、整併與安全清理。
- 任務需要真正收尾：使用 `finish-project-work` 建立終點並在驗證後停止。

## 安裝

先取得這個 Repo：

```bash
git clone https://github.com/eric861129/skills.git
```

再把需要的 Skill 資料夾整個複製到 Agent 的 skills 目錄（以 `finish-project-work` 為例）。

### Claude Code

```bash
cp -r skills/skills/finish-project-work ~/.claude/skills/
```

放在 `~/.claude/skills/` 對所有專案生效；只想用在單一專案時，改放到該專案的 `.claude/skills/`。Claude 會依 `description` 自動載入，也可以輸入 `/finish-project-work` 直接呼叫。

### Codex

```bash
cp -r skills/skills/finish-project-work ~/.codex/skills/
```

在對話中以 `$finish-project-work` 呼叫。各 Skill 的 `agents/openai.yaml` 是 Codex 介面使用的顯示名稱與預設提示，Claude Code 會忽略它。

## 驗證與唯讀工具

三個 Skill 都以對話內的固定輸出契約提供可核對的決策證據，不會為了回報自行建立新的專案文件。

[`evals/cases.json`](./evals/cases.json) 收錄壓力案例、反例、必要輸出欄位與禁止行為。案例應在全新對話中分別測試未載入與載入 Skill 的結果；fixture 通過不代表模型效能保證。

`consolidate-document-sprawl` 另附一個預設唯讀的文件盤點工具：

```text
python skills/consolidate-document-sprawl/scripts/inventory_documents.py <project-root> --format json
```

它只輸出路徑、標題、雜湊、Git 狀態、連結、編碼與生成線索，不會修改或刪除文件，也不會自行判定權威來源。

執行 Repo 驗證：

```bash
python -m unittest discover -s tests -v
```
