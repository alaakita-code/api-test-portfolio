# 使用手冊

本手冊說明 API 自動化測試專案的環境需求、安裝、執行、報告判讀、
失敗分析流程與維護方式。指令以 Windows 為例，皆於專案根目錄執行。

## 1. 概述

| 項目 | 內容 |
|---|---|
| 被測對象 | JSONPlaceholder 的 `/posts` 資源（REST API） |
| 測試類型 | API 功能測試：正向、邊界、負向、錯誤處理、重複請求 |
| 測試數量 | 25 個（24 個測試案例加 1 個冒煙測試） |
| 技術堆疊 | Python、pytest、requests、pytest-html |
| 產出 | 單一檔案的 HTML 測試報告 |
| 測試依據 | `docs/test_plan.md`；預期值來自 `docs/api_observed.md` 的實際觀察 |

被測對象的寫入操作（POST、PUT、PATCH、DELETE）只回傳模擬結果、不保存資料，
因此測試之間沒有狀態相依，可單獨或以任意順序執行。

## 2. 環境需求

| 項目 | 需求 |
|---|---|
| Python | 本機已於 3.13.1 驗證；CI 於 3.11 與 3.13 執行（見第 13 節） |
| 作業系統 | 已於 Windows 驗證 |
| 網路 | 需能連線至 `https://jsonplaceholder.typicode.com` |
| 相依套件 | 見 `requirements.txt`，版本皆已鎖定 |

## 3. 安裝

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

第一行建立專案專用的虛擬環境（virtual environment，與系統 Python 隔離的
獨立環境），第二行在其中安裝相依套件。兩者只影響專案目錄；移除 `.venv`
目錄即可還原。

本手冊的指令一律以 `.venv\Scripts\python` 呼叫虛擬環境中的直譯器，
不需先啟用環境，可避免 PowerShell 執行原則阻擋啟用腳本。

## 4. 執行

| 目的 | 指令 |
|---|---|
| 執行全部測試 | `.venv\Scripts\python -m pytest` |
| 只執行冒煙測試 | `.venv\Scripts\python -m pytest -m smoke` |
| 執行單一檔案 | `.venv\Scripts\python -m pytest tests/test_posts_positive.py` |
| 依名稱關鍵字篩選 | `.venv\Scripts\python -m pytest -k delete` |
| 顯示每個測試的名稱與結果 | `.venv\Scripts\python -m pytest -v` |

全部通過時，終端機最後一行的格式如下，秒數依網路狀況而異：

```
25 passed in 25.00s
```

結束代碼（exit code）為 0 表示全部通過，非 0 表示有測試未通過或執行錯誤，
可供 CI 作為品質閘門的判斷依據。

## 5. 測試報告

每次執行後，報告輸出至 `reports/report.html`。報告為單一檔案，可離線開啟。

| 區塊 | 內容 |
|---|---|
| Environment | Python、套件與外掛版本 |
| Summary | 測試總數、執行時間，以及通過、失敗、略過等各狀態的數量 |
| Results | 每個測試的結果與耗時；展開可查看該測試的執行紀錄 |

Environment 區塊預設只保留版本資訊。執行環境的其他資訊（作業系統細節、
環境變數中的路徑）由 `tests/conftest.py` 在報告產生前移除。報告是容易被
附加到工單或轉寄他人的檔案，因此採用「預設過濾」。

排查本機環境問題而需要完整環境資訊時，可針對單次執行開啟（PowerShell）：

```
$env:REPORT_FULL_ENVIRONMENT = "1"
.venv\Scripts\python -m pytest
Remove-Item Env:REPORT_FULL_ENVIRONMENT
```

| 行為 | 說明 |
|---|---|
| 開啟後 | Environment 區塊顯示完整資訊，並多出一列 `Report scope`，標示此報告僅供本機使用、不可分享 |
| 第三行指令 | 移除開關，之後的執行恢復為預設過濾 |
| 在 CI 上 | 開關無效。CI 產出的報告一律過濾，避免誤設開關而發布完整資訊 |

`reports/` 已列入 `.gitignore`，不納入版本控制。

## 6. 專案結構

| 位置 | 職責 |
|---|---|
| `tests/test_smoke.py` | 冒煙測試：驗證環境與連線可用 |
| `tests/test_posts_positive.py` | 正向測試 9 個（POS-01 至 09） |
| `tests/test_posts_boundary.py` | 邊界測試 6 個（BND-01 至 06） |
| `tests/test_posts_negative.py` | 負向測試 5 個（NEG-01 至 05） |
| `tests/test_error_handling.py` | 錯誤處理測試 2 個（ERR-01、02） |
| `tests/test_repeat_requests.py` | 重複請求測試 2 個（REP-01、02） |
| `tests/conftest.py` | pytest 共用設定：報告環境資訊的過濾與開關 |
| `utils/config.py` | 設定值：被測對象網址、逾時秒數 |
| `utils/api_client.py` | 請求封裝：統一網址、逾時與請求紀錄 |
| `data/` | 測試資料 |
| `tools/explore_api.py` | 觀察工具：記錄 API 的實際回應並與前次比對，不屬於測試 |
| `docs/observations/` | 觀察工具的公開版輸出：每次執行的紀錄與總清單（首次執行時建立） |
| `observations_local/` | 觀察工具的完整版輸出，僅供本機排查，不納入版本控制（首次執行時建立） |
| `README.md`、`README.zh-TW.md` | 專案說明（英文、繁體中文） |
| `.github/workflows/tests.yml` | CI 工作流程：自動執行測試並發布報告 |
| `docs/test_plan.md` | 測試計畫：範圍、優先級、測試案例與依據 |
| `docs/api_observed.md` | 專案初期的觀察紀錄（人工整理），為測試計畫預期值的原始依據 |
| `docs/api_notes.md` | 探索摘要與已知限制 |

設計原則：

- 測試、測試資料、共用工具與設定分離。
- 每個測試只驗證一個行為，採 Arrange、Act、Assert 結構。
- 測試名稱的格式為「被測行為、條件、預期結果」。
- 測試函式的說明文字標示對應的 Test ID，可追溯至測試計畫。

程式碼內的說明與註解一律使用英文；中文的輔助說明集中於第 12 節。

## 7. 設定

### 7.1 可調整的設定值

| 設定 | 位置 | 預設值 | 說明 |
|---|---|---|---|
| `BASE_URL` | `utils/config.py` | `https://jsonplaceholder.typicode.com` | 可用環境變數 `API_BASE_URL` 覆寫 |
| `TIMEOUT_SECONDS` | `utils/config.py` | 10 | 單一請求的逾時上限 |

逾時上限依實測決定：單一測試約 1 秒，取約十倍餘裕。此值為穩定性考量的
上限，並非效能驗收標準。

### 7.2 pytest.ini

| 設定 | 作用 |
|---|---|
| `pythonpath = .` | 將專案根目錄加入匯入路徑 |
| `testpaths = tests` | 限定測試蒐集範圍 |
| `addopts` 的 `-ra` | 於結尾列出未通過測試的摘要 |
| `addopts` 的 `--html`、`--self-contained-html` | 產生單一檔案的 HTML 報告 |
| `log_level = INFO` | 擷取請求與回應紀錄，供失敗分析使用 |
| `markers` | 登記 `smoke` 標記 |

### 7.3 編碼注意事項

`requirements.txt`、`pytest.ini` 與 `.gitignore` 的註解僅使用英文。
在以非 UTF-8 為預設編碼的 Windows 環境，套件安裝工具讀取含中文的設定檔
可能發生解碼錯誤，故相關說明集中於本節。

## 8. 失敗分析流程

測試失敗時，先分類原因，再決定處置。不應直接修改斷言。

### 8.1 判斷步驟

1. 執行冒煙測試：`.venv\Scripts\python -m pytest -m smoke`
2. 冒煙測試失敗：優先檢查環境（網路、被測服務是否可用、`BASE_URL`）。
3. 冒煙測試通過：問題在個別測試，依報告中的請求與回應紀錄對照下表。

### 8.2 失敗分類

| 現象 | 分類 | 處置 |
|---|---|---|
| `ConnectionError`、`Timeout` | 環境問題或暫時性問題 | 重新執行；若重現，確認被測服務狀態 |
| 狀態碼與預期不同 | API 行為與預期不同 | 重新觀察並更新紀錄，依 8.3 的順序修訂 |
| 筆數、欄位或型別與預期不同 | 被測資料或 API 行為變更 | 同上 |
| `ModuleNotFoundError` | 環境問題 | 確認使用虛擬環境的直譯器；重新安裝相依套件 |
| `FileNotFoundError` 指向 `data/` | 測試資料問題 | 確認測試資料檔存在且未被更動 |
| 同一測試結果不穩定 | 暫時性問題或測試腳本問題 | 記錄重現條件並找出原因；不直接略過 |

### 8.3 修訂順序

API 行為確實變更時，依下列順序處理，以維持可追溯性：

1. 執行 `tools/explore_api.py` 取得新的觀察紀錄（見 10.3）
2. 更新 `docs/test_plan.md`（預期結果與變更紀錄）
3. 修改測試程式
4. 重新執行全部測試並確認結果

### 8.4 原則

- 不為了讓測試通過而刪除、放寬或註解斷言。
- 測試通過僅表示涵蓋範圍內的行為符合預期，不等同被測對象沒有缺陷。

## 9. 已知限制

- 被測對象不保存寫入結果，無法驗證寫入後查詢的資料一致性。
- 被測對象沒有驗證機制，也不驗證輸入，權限與輸入驗證不在測試範圍內。
- 對不存在的 id，PUT 回 404、DELETE 回 200，行為不一致；
  測試如實記錄此行為（NEG-04、NEG-05）。
- GET 回應多由 CDN 快取提供，重複請求測試（REP-01）驗證到的
  可能是快取的一致性，而非來源伺服器的行為。
- 測試依賴第三方服務的可用性；服務中斷造成的失敗屬於環境問題。
- 未包含併發與負載測試。

完整的範圍說明見 `docs/test_plan.md` 第 1 節。

## 10. 維護

### 10.1 新增測試案例

1. 於 `docs/test_plan.md` 新增案例，指定 Test ID、優先級與預期結果。
2. 預期結果需有觀察依據；若無，先於 `tools/explore_api.py` 的 `PROBES`
   加入對應的請求並執行，取得實際回應的紀錄（見 10.3）。
3. 於對應的測試檔新增測試函式，於說明文字標示 Test ID。
4. 執行全部測試，確認未影響既有測試。

### 10.2 更新相依套件

修改 `requirements.txt` 的版本後重新安裝，並執行全部測試確認相容。
版本維持鎖定，以確保執行結果可重現。

### 10.3 API 觀察紀錄

`tools/explore_api.py` 用來記錄被測對象的實際回應。它只觀察、不判定通過或失敗，
適用於撰寫新測試之前，或懷疑 API 行為變更時。

```
.venv\Scripts\python tools/explore_api.py
```

每次執行同時產生兩份紀錄，既有紀錄不會被覆寫。

**公開版**：位於 `docs/observations/`，納入版本控制。

| 檔案 | 內容 |
|---|---|
| `observed_<日期>_<時間>.md` | 該次執行的紀錄：執行資訊、與前次的差異、摘要表、每個請求的明細 |
| `observed_<日期>_<時間>.json` | 相同資料的結構化版本，供下次執行比對使用 |
| `INDEX.md` | 總清單：每次執行一列，連結至明細檔 |

**完整版**：位於 `observations_local/`，已列入 `.gitignore`，不納入版本控制。

| 檔案 | 內容 |
|---|---|
| `observed_<日期>_<時間>_full.md` | 排查問題所需的完整資料 |
| `INDEX.md` | 總清單：每次執行一列，含 UTC 與本機時間 |

兩份紀錄的差異：

| 項目 | 公開版 | 完整版 |
|---|---|---|
| 回應標頭 | 僅 `Content-Type`、`Cache-Control`、`cf-cache-status`、`Location` | 全部，含 `CF-RAY` 等可供服務提供者追查的識別碼 |
| 請求失敗時 | 僅錯誤類型 | 錯誤類型與完整錯誤訊息 |
| 回應內容 | 超過 1000 字元時截斷 | 完整 |
| 時間 | UTC | UTC 與本機時間 |
| 執行環境 | Python 與 requests 版本 | 另含作業系統資訊 |

檔名中的時間為 UTC（世界協調時間），台灣時間為 UTC 加 8 小時。

**差異比對**：工具會自動讀取前一次的公開版紀錄，比對每個請求的狀態碼與回應結構。
首次執行的結果作為基準；之後若出現差異，會列在終端機輸出、明細檔與總清單中。
回應時間每次都不同，不列入比對。

**出現差異時**：不直接修改測試，依 8.3 的修訂順序處理。需要追查原因時，
查閱同一時間的完整版紀錄。

`docs/api_observed.md` 是專案初期以瀏覽器與 curl 取得的人工紀錄，保留作為
測試計畫預期值的原始依據，觀察工具不會更動它。

## 11. 安全性

### 11.1 原則

資訊的管制點設在「資料離開本機之處」，而不是在資料產生時就捨棄。
本機保留排查問題所需的完整資訊；會被發布或容易被分享的產出，才限制其內容。

### 11.2 各類產出的處理方式

| 產出 | 本機 | 發布或分享時 |
|---|---|---|
| 觀察紀錄 | 完整版存於 `observations_local/` | 僅公開版納入版本控制；完整版由 `.gitignore` 排除 |
| 測試報告 | 預設過濾；可用開關針對單次執行顯示完整環境資訊 | `reports/` 由 `.gitignore` 排除；CI 產出的報告一律過濾 |
| 虛擬環境、快取 | 存於專案目錄 | 由 `.gitignore` 排除 |

兩種產出採用不同的預設值，原因在於外流途徑不同：觀察紀錄只會經由版本控制
發布，以 `.gitignore` 即可管制；測試報告則常被手動轉寄或附加，`.gitignore`
無法管制這種途徑，因此採用預設過濾。

### 11.3 其他

- 專案不使用任何金鑰、帳號或密碼。
- `.env` 已列入 `.gitignore`；日後若需加入敏感設定，應以環境變數提供，
  不寫入程式或版本控制。
- 提交前以 `git status` 確認待提交清單中沒有 `observations_local/`、
  `reports/` 與 `.venv/`。

## 12. 程式碼導讀

程式碼內的註解以英文撰寫。本節以中文補充各檔案的設計理由與
程式中使用的寫法，作為閱讀程式碼時的對照。

### 12.1 各檔案的設計理由

| 檔案 | 說明 |
|---|---|
| `utils/config.py` | 設定值集中於一處。更換被測網址或調整逾時秒數時只需修改此檔，不需更動測試。 |
| `utils/api_client.py` | 所有測試都經由 `send_request` 呼叫 API。它統一補上網址、強制設定逾時，並記錄請求與回應，使失敗的測試留有可供分析的紀錄。 |
| `tests/conftest.py` | pytest 會自動載入的共用設定檔。此處用來控制報告中的環境資訊：預設只保留版本資訊，可用開關針對單次執行顯示完整資訊。 |
| `tests/test_smoke.py` | 最小的可用性檢查。它通過不代表功能正確；它失敗則代表其他測試的結果不可信，應優先處理。 |
| `tests/test_posts_positive.py` | 正確的請求應得到正確的回應。除了狀態碼，也驗證欄位、型別與內容。 |
| `tests/test_posts_boundary.py` | 缺陷常出現在範圍的邊緣。有效 id 為 1 至 100，因此測試邊緣值、邊緣外一格的值，以及格式不合的值。 |
| `tests/test_posts_negative.py` | 有問題的請求應如何被處理。其中兩項記錄的是被測對象的寬鬆行為，並非建議的設計。 |
| `tests/test_error_handling.py` | 驗證測試工具本身：被測服務無回應時，測試應明確失敗而不是停滯。 |
| `tests/test_repeat_requests.py` | 重複送出相同請求時，結果應一致。 |
| `tools/explore_api.py` | 預期值必須來自實際觀察。此工具將觀察自動化：每次執行留下帶時間的紀錄並與前次比對，使 API 行為的變更可被發現與追溯。同一次執行產生公開版與完整版兩份紀錄，分別用於發布與本機排查。 |

### 12.2 程式中使用的寫法

| 寫法 | 出現位置 | 說明 |
|---|---|---|
| Arrange、Act、Assert | 所有測試 | 測試的三段結構：準備資料、執行動作、驗證結果。段落分明，失敗時容易判斷問題出在哪一段。 |
| `@pytest.mark.smoke` | `test_smoke.py` | 為測試加上標記，之後可用 `-m smoke` 只執行帶有此標記的測試。 |
| `@pytest.mark.parametrize` | `test_posts_boundary.py` | 參數化：同一個測試函式以不同資料各執行一次。四個無效 id 的預期結果相同，故共用一個函式；每組資料在報告中仍是獨立的測試案例。 |
| `pytest.param(..., id=...)` | `test_posts_boundary.py` | 為每組參數指定報告中顯示的名稱，用來對應測試計畫的 Test ID。 |
| `pytest.raises(...)` | `test_error_handling.py` | 預期區塊內的程式會丟出指定的例外。有丟出則通過，沒有丟出則失敗。 |
| `type(x) is int` | `test_posts_positive.py` | 嚴格的型別檢查。布林值在 Python 中屬於整數的子型別，`isinstance(x, int)` 會將 `True` 判為整數，此寫法則不會。 |
| `set(post.keys()) == {...}` | `test_posts_positive.py` | 欄位名稱需完全相符：缺少或多出欄位都會失敗。 |
| `all(...)` 前先檢查筆數 | `test_posts_positive.py` | 對空清單而言 `all(...)` 恆為真，測試會錯誤地通過，因此先確認清單不為空。 |
| `response.elapsed` | `test_error_handling.py` | requests 量測的回應時間。 |
| `Path(__file__).resolve()` | `test_posts_positive.py` | 以測試檔自身的位置推算 `data/` 的路徑，使測試不受執行時所在目錄的影響。 |
| `@pytest.hookimpl(tryfirst=True)` | `conftest.py` | 掛鉤函式（hook，pytest 在特定時機自動呼叫的函式）。`tryfirst=True` 讓它先於其他外掛執行，確保在報告寫出之前完成過濾。 |
| 允許清單 | `conftest.py`、`explore_api.py` | 只允許列出的項目出現在報告或公開版紀錄中。相較於排除清單，日後新增的欄位也會被自動過濾。 |
| `os.environ.get("GITHUB_ACTIONS")` | `conftest.py` | GitHub Actions 執行時會設定此環境變數，用來判斷是否在 CI 上執行。 |
| `os.environ.get(名稱, 預設值)` | `config.py` | 讀取環境變數；未設定時使用預設值。可在不修改程式的情況下切換被測網址。 |

## 13. 持續整合（CI）

### 13.1 工作流程

`.github/workflows/tests.yml` 定義 GitHub Actions 的工作流程。

| 項目 | 設定 |
|---|---|
| 觸發時機 | 每次 push、每次 pull request，以及於 Actions 頁面手動執行 |
| 執行環境 | GitHub 提供的標準 Ubuntu 執行環境 |
| Python 版本 | 3.11 與 3.13，各自獨立執行 |
| 逾時 | 10 分鐘 |
| 權限 | 僅讀取儲存庫內容 |
| 產出 | 每個 Python 版本各一份 HTML 報告，保存 30 天 |

步驟依序為：取出程式碼、安裝指定版本的 Python、安裝相依套件、執行測試、上傳報告。
上傳步驟設定為測試失敗時仍會執行，因為失敗時正是需要報告的時候。

### 13.2 查看結果與下載報告

1. 開啟儲存庫的 Actions 頁面，選擇一次執行紀錄。
2. 綠色勾號表示全部通過，紅色叉號表示有測試未通過或執行錯誤。
3. 於頁面下方的 Artifacts 區塊下載 `test-report-python-3.11` 或
   `test-report-python-3.13`，解壓縮後以瀏覽器開啟 `report.html`。

CI 產出的報告在 GitHub 的執行環境中產生，不含任何開發者本機的資訊；
Environment 區塊一律只保留版本資訊（見第 5 節）。

### 13.3 CI 失敗的判讀

被測對象為第三方服務，CI 失敗不必然代表專案有缺陷。依第 8 節的流程分類：

| 情況 | 判讀 |
|---|---|
| 兩個 Python 版本同時失敗於連線或逾時 | 多為被測服務或網路的暫時性問題；重新執行確認 |
| 只有一個 Python 版本失敗 | 多為版本相容性問題；檢查該版本的報告 |
| 斷言失敗且可重現 | 被測對象行為變更；依 8.3 的順序處理 |
| 安裝相依套件失敗 | 環境問題；確認 `requirements.txt` 的版本於該 Python 版本可用 |

### 13.4 首次發布至 GitHub

於 GitHub 建立公開儲存庫（不勾選建立 README）後，在專案根目錄執行：

```
git init
git config user.name "顯示名稱"
git config user.email "GitHub 提供的 noreply 信箱"
git add .
git status
git commit -m "Add API test suite with pytest, HTML report and CI workflow"
git branch -M main
git remote add origin https://github.com/帳號/儲存庫名稱.git
git push -u origin main
```

注意事項：

- **提交者資訊**：提交紀錄會公開顯示 `user.name` 與 `user.email`。
  GitHub 於帳號設定的 Emails 頁面提供 noreply 信箱，可避免公開個人信箱。
  此處的 `git config` 未加 `--global`，設定只作用於本專案。
- **提交前檢查**：`git status` 列出的待提交清單中，不應出現 `.venv/`、
  `reports/` 與 `observations_local/`。若出現，先確認 `.gitignore` 存在於專案根目錄。
- **提交訊息**：使用英文祈使句，說明這次提交做了什麼。上例的意思是
  「加入 API 測試套件，含 pytest、HTML 報告與 CI 工作流程」。

推送完成後，工作流程會自動開始執行。
