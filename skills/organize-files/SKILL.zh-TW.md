---
name: organize-files
description: 當使用者要求整理、分類、歸檔、重整或去除重複檔案與資料夾時使用，例如雜亂的下載或桌面資料夾、大量匯入的照片、共用磁碟，或塞滿零散檔案的專案資料夾。依四個階段執行（盤點、計畫並取得核准、搬遷、結果告知），絕不刪除檔案（重複與雜物移到暫存資料夾由使用者決定），遇到被鎖定或使用中的檔案會重試後略過並指出占用程式，執行紀錄與還原用 journal 放在桌面，最後說明搬了什麼、整理後的完整資料夾結構，以及需要使用者處理的項目。
---

# 整理檔案

## 整理目標

- 把雜亂的資料夾整理成使用者核准過的清楚結構，每一筆變更都有紀錄、都能還原。
- **絕不刪除檔案。** 重複檔、雜物與疑似垃圾一律移到 `<root>/_organize-staging/<run-id>/`，由使用者決定要不要刪，並告知使用者位置。
- 執行紀錄（盤點、manifest、journal、前後資料夾樹、摘要）放在 `<桌面>/organize-files-logs/<run-id>/`，並告知使用者這個路徑。
- 不留下沒交代的項目：結束時，每個計畫中的項目都已搬移、已暫存，或附上原因與下一步列出。

## 附帶資源

- `scripts/inventory_files.py`：唯讀盤點；在桌面建立本次執行的紀錄資料夾。
- `scripts/apply_manifest.py`：預設只驗證並試跑 manifest；加 `--execute` 或 `--retry-failed` 才實際執行。
- `scripts/undo.py`：依 journal 還原整次執行（未加 `--execute` 時只列出計畫）。
- `references/presets.md`：內建整理規格與挑選方式。擬計畫前先讀。
- `references/data-structures.md`：紀錄資料夾配置、JSON 結構、計畫與結果的報告範本。寫 manifest 前先讀。
- `references/error-handling.md`：鎖定檔處理流程與每種狀態的處理方式。任何操作失敗時閱讀。

腳本只用 Python 標準函式庫，先執行 `--help` 確認參數。若環境沒有 Python，用 shell 內建的唯讀列舉與單檔搬移指令完成相同階段，手動在紀錄資料夾保留相同紀錄，任何安全規則都不得放寬。

## 階段 0：範圍與安全確認

1. 確認根目錄與使用者想排除的項目。需求模糊時（例如「幫我整理電腦」）先問要整理哪個資料夾；絕不整理整顆磁碟、使用者家目錄根層，或系統、程式資料夾。
2. 若根目錄本身就是 repo 或專案（`risks.root_is_unit`），停下來確認。repo 內部的整理應交給該專案自己的工具。
3. 記下不可搬動的項目：整體單位（repo、專案、相片圖庫、虛擬機資料夾）、排除的資料夾、連結與 junction、系統檔，以及路徑被其他軟體記錄的應用程式管理資料夾。
4. 允許的操作只有搬移、改名、建立資料夾與移到暫存區。移除被清空的資料夾需要明確核准。除此之外一律不做。

## 階段 1：盤點（唯讀）

```text
python <skill-dir>/scripts/inventory_files.py "<root>"
```

此指令會在桌面建立紀錄資料夾，寫入 `inventory.json` 與 `tree-before.txt`，並輸出摘要（依類別、年份、副檔名的統計；最大檔案；重複檔；整體單位；風險；目前的資料夾樹）。它不會碰根目錄裡的任何東西。

閱讀摘要即可，不要讀完整檔案清單。記下主要類別、時間跨度、重複檔量、整體單位，以及每一組風險：`locked`、`likely_open_in_office`、`cloud_placeholders`、`permission_denied`、`long_paths`、`partial_downloads`。

## 階段 2：計畫（核准閘門）

1. 依盤點訊號從 `references/presets.md` 挑一套規格，加以調整並說明調整內容。只有在另一套明顯更符合不同目標時，才額外提供一個替代方案。
2. 依 `references/data-structures.md` 寫出 `<run-dir>/manifest.json`，`approval.approved_by_user` 設為 `false`。搬移與改名用 `move`，重複檔與雜物用 `stage`（附 `reason`）。絕不寫入刪除操作。
3. 執行試跑並修正所有驗證錯誤：

   ```text
   python <skill-dir>/scripts/apply_manifest.py "<run-dir>"
   ```

4. 用 `references/data-structures.md` 的範本呈現計畫：範圍、紀錄路徑、數量、目標資料夾樹、各規則的數量與範例、暫存、例外、風險與核准狀態。對話中只呈現規則與範例，逐檔清單留在 manifest。
5. 停下來等待。使用者核准前不得搬動任何檔案。使用者要求修改時，更新 manifest、重新試跑，並說明改了什麼。

核准後，將 `approval.approved_by_user` 設為 `true`，填入 `approved_at`，並用一行 `summary` 寫下核准內容。核准只涵蓋當時呈現的 manifest；任何新增項目都要重新核准。

## 階段 3：實際搬遷

```text
python <skill-dir>/scripts/apply_manifest.py "<run-dir>" --execute
```

- 腳本只執行 manifest 中的操作，每一筆結果都追加寫入 `journal.jsonl`，遇到失敗會繼續處理下一筆。
- 被鎖定的檔案會在 1 秒、3 秒、10 秒後重試，仍失敗就略過並記錄占用程式。不要自己關閉、終止或解鎖任何東西。告訴使用者哪個程式占用了哪個檔案；使用者關閉後，執行 `--retry-failed`。
- 跨磁碟搬移與僅限線上的雲端檔案會被略過，除非使用者核准了 `--allow-cross-volume` 或 `--allow-cloud-placeholders`。
- 出現意外狀況（新的風險、不在盤點中的檔案、大量 `source_missing`）時，停下來回報，取得確認後再繼續。
- 執行中斷時，用同一個指令即可續跑；已完成的項目會自動略過。

## 階段 4：結果告知

依 `summary.json` 與 `references/data-structures.md` 的結果範本回報。一定要包含：

- 各狀態的數量與搬移的總容量。
- 整理後的完整資料夾樹（`tree-after.txt`），並簡短對照整理前後。
- 每個類別被搬到哪裡。
- 暫存資料夾的絕對路徑、項目數與容量，並明確說明沒有刪除任何檔案，要刪什麼由使用者決定。
- 每個需要處理的項目，附上占用程式或錯誤，以及下一步。
- 桌面上紀錄資料夾的絕對路徑，以及完整的還原指令。

使用對話的語言撰寫。被略過或失敗的項目不得宣稱成功。

## 停止條件

當每一筆已核准的操作都是 `done`、`staged`，或已附原因回報，並且結果報告已交付，就停止。除非使用者要求，不要繼續重整、為了風格改檔名，或開始第二輪整理。若使用者要求刪除暫存檔，告訴他們暫存資料夾的位置，請他們自行刪除；本 Skill 不執行刪除。
