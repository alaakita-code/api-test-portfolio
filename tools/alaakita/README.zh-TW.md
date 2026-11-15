# AlaAkita 擋關(CI Gate)

沒全綠就不能合併。每次 PR 與推送到 `main` 時,GitHub Actions 依序執行:

| 步驟 | 工具 | 證明什麼 |
|---|---|---|
| verify | `verify.py` | 單檔 HTML 結果合格(BOM、ES5、簡體字…) |
| path | `path_check.py` | 改動真的發生在預期位置 |
| test | 你在 `gate.txt` 寫的指令 | 專案自己的測試通過 |

## 一、放進專案(一次性)

1. 把壓縮檔內容複製到 repo 根目錄,會得到:
   ```
   .github/workflows/alaakita-gate.yml
   .alaakita/gate.txt
   .alaakita/expect.txt
   tools/alaakita/(gate.py、verify.py、path_check.py、測試、references/)
   ```
2. 用你本機的 **verify.py v1.2** 覆蓋 `tools/alaakita/verify.py`(壓縮檔內附的是 v1.1)。
3. 修改 `.alaakita/gate.txt`:`verify` 改成專案實際的 HTML 路徑;Python 專案加一行 `test python -m pytest -q`。
4. 本機先跑一次(在 repo 根目錄):
   ```
   python tools/alaakita/gate.py
   ```
   最後一段顯示「全綠,可以合併」才繼續。
5. commit 並推送。到 Actions 頁面確認出現「AlaAkita Gate」且為綠色。

## 二、在 GitHub 開啟「擋住合併」(一次性)

只放工作流程不會擋住任何東西,它只會顯示紅綠燈。要真的擋住,需設定規則:

1. repo 的 **Settings → Rules → Rulesets → New ruleset → New branch ruleset**
2. Ruleset name 填 `alaakita-gate`;Enforcement status 選 **Active**
3. Target branches → **Add target → Include default branch**
4. 勾選 **Require a pull request before merging**
5. 勾選 **Require status checks to pass** → **Add checks** → 輸入 `gate` 並選取
6. Bypass list 保持空白(你自己也要遵守),按 **Create**

注意:

- 狀態檢查 `gate` 要至少跑過一次,才選得到。
- Rulesets 在 GitHub 免費方案只適用於**公開** repo;私人 repo 需要 Pro 以上方案。
- 開啟後不能直接推送到 `main`,一律走 PR。

## 三、每次改動的流程

```
git switch -c 改動名稱
```
1. **先**改寫 `.alaakita/expect.txt`,寫下這次預期的改動
2. 修改程式
3. 本機檢查(對照 main):`python tools/alaakita/gate.py --base main`
4. commit、push、開 PR,等 `gate` 變綠再合併

預期檔沒更新時,舊規則會讓擋關失敗,這是刻意設計:每次改動都要重新證明。

## 四、改動工作室(studio.py)與工具檢查(doctor.py)

**與 Claude 配合前先跑工具檢查**(任何資料夾都能跑,輸出已遮蔽使用者資料夾與 token,可直接貼給 Claude):

```
python tools/alaakita/doctor.py
```

全部 ✅ 才開始;❌ 的項目下方會寫怎麼修。

**改動工作室**:把下一節的三個指令收成一個本機網頁,六步驟、範本、紀錄都在同一頁。

```
python tools/alaakita/studio.py
```

- 瀏覽器會自動打開;網址帶一次性通行碼,只在這台電腦有效。按 Ctrl+C 結束。
- 六步:開始 → 預期(人工確認,可套範本)→ 修改 → 送出 → 審查(人工確認,在 GitHub 合併)→ 收尾
- 工作室沒有合併按鈕;預期檔還有 `<…>` 範本欄位時不能送出。
- 紀錄存在 `.alaakita/local/history.jsonl`,已遮蔽使用者資料夾與 token;此資料夾必須被 `.gitignore` 排除,否則工作室拒絕執行。

## 五、一鍵流程(ship.py)

人工只留兩個點:改之前寫好預期、合併前看 PR 內容。其他步驟自動執行。
需要 GitHub CLI:`winget install --id GitHub.cli -e`,重開 PowerShell 後執行 `gh auth login`。

```
python tools/alaakita/ship.py start 分支名稱
python tools/alaakita/ship.py submit "commit 訊息"
python tools/alaakita/ship.py finish
```

| 步驟 | 自動做的事 | 會停下來的情況 |
|---|---|---|
| start | 從最新 main 開分支、建立預期檔範本 | 有尚未 commit 的修改、分支已存在 |
| submit | 本機擋關 → commit → push → 開 PR → 等檢查 | 本機擋關沒過(不 commit、不推送)、任何檢查失敗、檢查沒出現或逾時、缺少必要檢查 |
| finish | 切回 main、pull、刪除本地與遠端分支 | PR 還沒合併 |

- **不會自動合併**:submit 全綠後只印出 PR 網址,由你在 GitHub 看 Files changed 後按合併。
- 必要檢查列在 `.alaakita/required_checks.txt`,一行一個名稱;缺任何一個都不算通過。

## 六、重複錯誤計數(lesson_counter.py)

同一類錯第二次出現,就列為晉升候選,不用等週五儀式。

**journal 記錯誤時加標記**(類別用英文小寫與連字號,先用 `--list` 查既有類別沿用):
```
- 知識庫 tbl() 收尾括號又寫錯 [錯誤:tbl-bracket]
```

**lessons.md 晉升時寫上類別與檢查**:
```
- L-20261115-01 類別:tbl-bracket 檢查:check_tbl_bracket — 說明
- L-20261114-02 類別:sql-null-compare 檢查:tests/test_ingest.py::test_null_batch
```
只寫函式名 → 必須存在於 verify.py;寫「檔案::函式」→ 必須存在於該檔案。

**執行**:
```
python tools/alaakita/lesson_counter.py --journal journal --lessons lessons.md
python tools/alaakita/lesson_counter.py --journal journal --lessons lessons.md --list
```

| 判定 | 意思 | 結果 |
|---|---|---|
| 晉升候選 | 同類出現 2 次以上,還沒有對應檢查 | 擋下 |
| 復發 | 已晉升,晉升日期之後又出現 | 擋下(檢查沒擋住) |
| 假關閉 | lessons.md 寫了檢查,但找不到那個函式 | 擋下 |
| 疑似同類 | 兩個類別名稱很像 | 只提醒 |

只想看報告不想擋,加 `--warn-only`。

## 七、限制

- `lesson_counter` 只認得有加 `[錯誤:類別]` 的條目;沒標記的錯誤不會被計數。
- `path_check` 只比對文字標記,無法判斷邏輯是否正確,這部分仍靠 verify 與測試。
- 排程與手動執行沒有比較基準,會略過路徑檢查(報告中標示「略過」)。
- Windows 本機尚未實測,待確認。
