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

## 四、重複錯誤計數(lesson_counter.py)

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

## 五、限制

- `lesson_counter` 只認得有加 `[錯誤:類別]` 的條目;沒標記的錯誤不會被計數。
- `path_check` 只比對文字標記,無法判斷邏輯是否正確,這部分仍靠 verify 與測試。
- 排程與手動執行沒有比較基準,會略過路徑檢查(報告中標示「略過」)。
- Windows 本機尚未實測,待確認。
