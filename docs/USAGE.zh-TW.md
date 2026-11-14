# 使用手冊

本手冊說明 API 自動化測試專案之環境需求、安裝、執行、報告判讀、失敗分析流程、
維護方式與持續整合設定。指令以 Windows PowerShell 為例，皆於專案根目錄執行。

## 1. 概述

| 項目 | 內容 |
|---|---|
| 被測對象 | JSONPlaceholder 之 `/posts` 資源（REST API） |
| 測試類型 | API 功能測試：正向、邊界、負向、錯誤處理、重複請求 |
| 測試數量 | 25 個（24 個測試案例及 1 個冒煙測試） |
| 技術堆疊 | Python、pytest、requests、pytest-html、GitHub Actions |
| 產出 | 單一檔案之 HTML 測試報告 |
| 測試依據 | `docs/test_plan.md`；預期值源自 `docs/api_observed.md` 所載之實際觀察 |

被測對象之寫入操作（POST、PUT、PATCH、DELETE）僅回傳模擬結果而不保存資料，
故各測試之間無狀態相依，得單獨執行或以任意順序執行。

## 2. 環境需求

| 項目 | 需求 |
|---|---|
| Python | 3.11 以上。本機於 3.13.1 驗證；CI 於 3.11 與 3.13 驗證（見第 13 節） |
| 作業系統 | 本機於 Windows 驗證；CI 於 Ubuntu 驗證 |
| 網路 | 須可連線至 `https://jsonplaceholder.typicode.com` |
| 相依套件 | 詳見 `requirements.txt`，版本皆已鎖定 |

## 3. 安裝

```
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

第一行建立專案專用之虛擬環境（virtual environment，與系統 Python 隔離之獨立環境）；
第二行於該環境安裝相依套件。兩者之影響範圍僅限於專案目錄，移除 `.venv` 目錄即可還原。

本手冊之指令一律以 `.\.venv\Scripts\python.exe` 呼叫虛擬環境內之直譯器，其理由如下：

- 無須先行啟用環境，可避免 PowerShell 執行原則阻擋啟用腳本。
- 路徑以 `.\` 起始，明確指定為目前目錄下之檔案；若檔案不存在，
  PowerShell 將回報路徑錯誤，而不致誤判為模組名稱。

## 4. 執行

| 目的 | 指令 |
|---|---|
| 執行全部測試 | `.\.venv\Scripts\python.exe -m pytest` |
| 僅執行冒煙測試 | `.\.venv\Scripts\python.exe -m pytest -m smoke` |
| 執行單一檔案 | `.\.venv\Scripts\python.exe -m pytest tests/test_posts_positive.py` |
| 依名稱關鍵字篩選 | `.\.venv\Scripts\python.exe -m pytest -k delete` |
| 顯示各測試之名稱與結果 | `.\.venv\Scripts\python.exe -m pytest -v` |

全部通過時，終端機最後一行之格式如下，秒數依網路狀況而異：

```
25 passed in 25.00s
```

結束代碼（exit code）為 0 表示全部通過；非 0 表示有測試未通過或發生執行錯誤。
此代碼可供 CI 作為品質閘門之判斷依據。

## 5. 測試報告

每次執行後，報告輸出至 `reports/report.html`。該報告為單一檔案，可離線開啟。

| 區塊 | 內容 |
|---|---|
| Environment | Python、套件與外掛之版本 |
| Summary | 測試總數、執行時間，以及通過、失敗、略過等各狀態之數量 |
| Results | 各測試之結果與耗時；展開後可檢視該測試之執行紀錄 |

Environment 區塊預設僅保留版本資訊。執行環境之其他資訊（作業系統細節、
環境變數所含路徑）由 `tests/conftest.py` 於報告產生前移除。測試報告常被附加於
工單或轉寄他人，故採「預設過濾」之原則。

排查本機環境問題而需完整環境資訊時，得針對單次執行啟用：

```
$env:REPORT_FULL_ENVIRONMENT = "1"
.\.venv\Scripts\python.exe -m pytest
Remove-Item Env:REPORT_FULL_ENVIRONMENT
```

| 情形 | 說明 |
|---|---|
| 啟用後 | Environment 區塊顯示完整資訊，並新增 `Report scope` 一列，標示該報告僅供本機使用，不得對外提供 |
| 第三行指令 | 移除開關，其後之執行恢復預設過濾 |
| 於 CI 環境 | 開關無效。CI 產出之報告一律過濾，以防因誤設開關而發布完整資訊 |

`reports/` 已列入 `.gitignore`，不納入版本控制。

## 6. 專案結構

| 位置 | 職責 |
|---|---|
| `README.md`、`README.zh-TW.md` | 專案說明（英文、繁體中文） |
| `.github/workflows/tests.yml` | CI 工作流程：自動執行測試並發布報告 |
| `.gitattributes` | 換行格式之設定（見 7.4） |
| `tests/test_smoke.py` | 冒煙測試：驗證環境與連線可用 |
| `tests/test_posts_positive.py` | 正向測試 9 個（POS-01 至 POS-09） |
| `tests/test_posts_boundary.py` | 邊界測試 6 個（BND-01 至 BND-06） |
| `tests/test_posts_negative.py` | 負向測試 5 個（NEG-01 至 NEG-05） |
| `tests/test_error_handling.py` | 錯誤處理測試 2 個（ERR-01、ERR-02） |
| `tests/test_repeat_requests.py` | 重複請求測試 2 個（REP-01、REP-02） |
| `tests/conftest.py` | pytest 共用設定：報告環境資訊之過濾與開關 |
| `utils/config.py` | 設定值：被測對象網址、逾時秒數 |
| `utils/api_client.py` | 請求封裝：統一網址、逾時與請求紀錄 |
| `data/` | 測試資料 |
| `tools/explore_api.py` | 觀察工具：記錄 API 之實際回應並與前次比對；不屬於測試 |
| `docs/test_plan.md` | 測試計畫：範圍、優先級、測試案例及其依據 |
| `docs/api_observed.md` | 專案初期之觀察紀錄，為測試計畫預期值之原始依據 |
| `docs/api_notes.md` | 探索摘要與已知限制 |
| `docs/observations/` | 觀察工具之公開版輸出：各次執行之紀錄與總清單 |
| `observations_local/` | 觀察工具之完整版輸出，僅供本機排查，不納入版本控制 |

設計原則如下：

- 測試、測試資料、共用工具與設定各自分離。
- 每個測試僅驗證單一行為，並採 Arrange、Act、Assert 結構。
- 測試名稱之格式為「被測行為、條件、預期結果」。
- 測試函式之說明文字標示對應之 Test ID，可追溯至測試計畫。

程式碼內之說明與註解一律以英文撰寫；中文之輔助說明集中於第 12 節。

## 7. 設定

### 7.1 可調整之設定值

| 設定 | 位置 | 預設值 | 說明 |
|---|---|---|---|
| `BASE_URL` | `utils/config.py` | `https://jsonplaceholder.typicode.com` | 得以環境變數 `API_BASE_URL` 覆寫 |
| `TIMEOUT_SECONDS` | `utils/config.py` | 10 | 單一請求之逾時上限（秒） |

逾時上限依實測結果訂定：單一測試約需 1 秒，故保留約十倍之餘裕。
此值係基於穩定性考量之上限，並非效能驗收標準。

### 7.2 pytest.ini

| 設定 | 作用 |
|---|---|
| `pythonpath = .` | 將專案根目錄加入匯入路徑 |
| `testpaths = tests` | 限定測試蒐集範圍 |
| `addopts` 之 `-ra` | 於結尾列出未通過測試之摘要 |
| `addopts` 之 `--html`、`--self-contained-html` | 產生單一檔案之 HTML 報告 |
| `log_level = INFO` | 擷取請求與回應紀錄，供失敗分析使用 |
| `markers` | 登記 `smoke` 標記 |

### 7.3 編碼注意事項

`requirements.txt`、`pytest.ini` 與 `.gitignore` 之註解僅使用英文。
於預設編碼非 UTF-8 之 Windows 環境，套件安裝工具讀取含中文之設定檔時
可能發生解碼錯誤，故相關說明集中於本節。

### 7.4 換行格式

`.gitattributes` 設定文字檔一律以 LF 作為換行格式。Windows 預設採用 CRLF，
Linux 與 macOS 採用 LF；統一格式後，各作業系統所取得之檔案內容一致，
`git add` 時亦不再出現換行格式轉換之警告。

## 8. 失敗分析流程

測試失敗時，應先判定失敗原因之類別，再決定處置方式，不得逕行修改斷言。

### 8.1 判斷步驟

1. 執行冒煙測試：`.\.venv\Scripts\python.exe -m pytest -m smoke`
2. 冒煙測試失敗：應優先檢查環境，包括網路、被測服務之可用性與 `BASE_URL`。
3. 冒煙測試通過：問題出於個別測試，應依報告所載之請求與回應紀錄對照下表。

### 8.2 失敗分類

| 現象 | 分類 | 處置 |
|---|---|---|
| `ConnectionError`、`Timeout` | 環境問題或暫時性問題 | 重新執行；若可重現，確認被測服務之狀態 |
| 狀態碼與預期不符 | API 行為與預期不符 | 重新觀察並更新紀錄，依 8.3 之順序修訂 |
| 筆數、欄位或型別與預期不符 | 被測資料或 API 行為變更 | 同上 |
| `ModuleNotFoundError` | 環境問題 | 確認使用虛擬環境之直譯器，並重新安裝相依套件 |
| `FileNotFoundError` 指向 `data/` | 測試資料問題 | 確認測試資料檔存在且未經更動 |
| 同一測試之結果不穩定 | 暫時性問題或測試腳本問題 | 記錄重現條件並查明原因；不得逕行略過 |
| 僅於特定環境失敗 | 測試腳本問題或環境差異 | 比對各環境之錯誤訊息，檢視測試是否隱含對環境之假設 |

### 8.3 修訂順序

確認 API 行為已變更時，應依下列順序處理，以維持可追溯性：

1. 執行 `tools/explore_api.py` 取得新的觀察紀錄（見 10.3）。
2. 更新 `docs/test_plan.md` 之預期結果與變更紀錄。
3. 修改測試程式。
4. 重新執行全部測試並確認結果。

### 8.4 原則

- 不得為使測試通過而刪除、放寬或註解斷言。
- 測試通過僅表示涵蓋範圍內之行為符合預期，不等同被測對象無缺陷。
- 本機通過不等同其他環境亦通過；跨環境之驗證由 CI 執行（見第 13 節）。

## 9. 已知限制

- 被測對象不保存寫入結果，故無法驗證寫入後查詢之資料一致性。
- 被測對象未設驗證機制，亦不驗證輸入，故權限與輸入驗證不在測試範圍內。
- 對不存在之 id，PUT 回應 404，DELETE 回應 200，兩者行為不一致；
  測試如實記錄此行為（NEG-04、NEG-05）。
- GET 回應多由 CDN 快取提供，故重複請求測試（REP-01）所驗證者
  可能為快取之一致性，而非來源伺服器之行為。
- 測試依賴第三方服務之可用性；因服務中斷所致之失敗屬環境問題。
- 未包含併發與負載測試。

完整之範圍說明詳見 `docs/test_plan.md` 第 1 節。

## 10. 維護

### 10.1 新增測試案例

1. 於 `docs/test_plan.md` 新增案例，並指定 Test ID、優先級與預期結果。
2. 預期結果須有觀察依據；若無，應先於 `tools/explore_api.py` 之 `PROBES`
   加入對應之請求並執行，以取得實際回應之紀錄（見 10.3）。
3. 於對應之測試檔新增測試函式，並於說明文字標示 Test ID。
4. 執行全部測試，確認既有測試未受影響。

### 10.2 更新相依套件

修改 `requirements.txt` 所載版本後，應重新安裝並執行全部測試以確認相容性。
版本應維持鎖定，以確保執行結果可重現。

### 10.3 API 觀察紀錄

`tools/explore_api.py` 用於記錄被測對象之實際回應。該工具僅進行觀察，
不判定通過或失敗，適用於撰寫新測試之前，或疑有 API 行為變更之時。

```
.\.venv\Scripts\python.exe tools/explore_api.py
```

每次執行同時產生兩份紀錄，既有紀錄不予覆寫。

**公開版**：位於 `docs/observations/`，納入版本控制。

| 檔案 | 內容 |
|---|---|
| `observed_<日期>_<時間>.md` | 該次執行之紀錄：執行資訊、與前次之差異、摘要表、各請求之明細 |
| `observed_<日期>_<時間>.json` | 相同資料之結構化版本，供下次執行比對使用 |
| `INDEX.md` | 總清單：每次執行一列，並連結至明細檔 |

**完整版**：位於 `observations_local/`，已列入 `.gitignore`，不納入版本控制。

| 檔案 | 內容 |
|---|---|
| `observed_<日期>_<時間>_full.md` | 排查問題所需之完整資料 |
| `INDEX.md` | 總清單：每次執行一列，含 UTC 與本機時間 |

兩份紀錄之差異如下：

| 項目 | 公開版 | 完整版 |
|---|---|---|
| 回應標頭 | 僅 `Content-Type`、`Cache-Control`、`cf-cache-status`、`Location` | 全部，含 `CF-RAY` 等可供服務提供者追查之識別碼 |
| 請求失敗時 | 僅錯誤類型 | 錯誤類型及完整錯誤訊息 |
| 回應內容 | 逾 1000 字元即予截斷 | 完整 |
| 時間 | UTC | UTC 與本機時間 |
| 執行環境 | Python 與 requests 之版本 | 另含作業系統資訊 |

檔名所載時間為 UTC（世界協調時間）。

**差異比對**：工具自動讀取前一次之公開版紀錄，逐一比對各請求之狀態碼與回應結構。
首次執行之結果作為基準；其後若有差異，將列示於終端機輸出、明細檔與總清單。
回應時間每次執行皆不相同，故不列入比對。

**出現差異時**：不得逕行修改測試，應依 8.3 之修訂順序處理。
如需追查原因，可查閱同一時間之完整版紀錄。

`docs/api_observed.md` 為專案初期以瀏覽器與 curl 取得之人工紀錄，保留作為
測試計畫預期值之原始依據；觀察工具不會更動該檔。

## 11. 安全性

### 11.1 原則

資訊之管制點設於「資料離開本機之處」，而非於資料產生時即予捨棄。
本機保留排查問題所需之完整資訊；僅對將發布或易於對外提供之產出限制其內容。

### 11.2 各類產出之處理方式

| 產出 | 本機 | 發布或對外提供時 |
|---|---|---|
| 觀察紀錄 | 完整版存於 `observations_local/` | 僅公開版納入版本控制；完整版由 `.gitignore` 排除 |
| 測試報告 | 預設過濾；得以開關針對單次執行顯示完整環境資訊 | `reports/` 由 `.gitignore` 排除；CI 產出之報告一律過濾 |
| 虛擬環境、快取 | 存於專案目錄 | 由 `.gitignore` 排除 |

兩類產出採用不同之預設值，係因外流途徑有別：觀察紀錄僅經由版本控制發布，
以 `.gitignore` 即可管制；測試報告則常經人工轉寄或附加，`.gitignore`
無從管制此一途徑，故採預設過濾。

### 11.3 其他事項

- 本專案不使用任何金鑰、帳號或密碼。
- `.env` 已列入 `.gitignore`；日後如需加入敏感設定，應以環境變數提供，
  不得寫入程式或納入版本控制。
- 提交前應以 `git status` 確認待提交清單未包含 `observations_local/`、
  `reports/` 與 `.venv/`。

## 12. 程式碼導讀

程式碼內之註解以英文撰寫。本節以中文補充各檔案之設計理由與程式所採用之寫法，
供閱讀程式碼時對照。

### 12.1 各檔案之設計理由

| 檔案 | 說明 |
|---|---|
| `utils/config.py` | 設定值集中於一處。更換被測網址或調整逾時秒數時，僅須修改此檔，無須更動測試。 |
| `utils/api_client.py` | 所有測試皆經由 `send_request` 呼叫 API。該函式統一附加網址、強制設定逾時，並記錄請求與回應，使失敗之測試留有可供分析之紀錄。 |
| `tests/conftest.py` | pytest 自動載入之共用設定檔，用於控制報告所載之環境資訊：預設僅保留版本資訊，並得以開關針對單次執行顯示完整資訊。 |
| `tests/test_smoke.py` | 最小範圍之可用性檢查。其通過不代表功能正確；其失敗則表示其餘測試之結果不可採信，應優先處理。 |
| `tests/test_posts_positive.py` | 驗證正確之請求取得正確之回應。除狀態碼外，並驗證欄位、型別與內容。 |
| `tests/test_posts_boundary.py` | 缺陷常見於範圍之邊界。有效 id 為 1 至 100，故測試邊界值、邊界外相鄰之值，以及格式不符之值。 |
| `tests/test_posts_negative.py` | 驗證不正確之請求如何被處理。其中兩項所記錄者為被測對象之寬鬆行為，並非建議之設計。 |
| `tests/test_error_handling.py` | 驗證測試工具本身：被測服務無回應時，測試應明確失敗，而非停滯。 |
| `tests/test_repeat_requests.py` | 驗證重複送出相同請求時結果一致。 |
| `tools/explore_api.py` | 預期值須源自實際觀察。本工具將觀察作業自動化：每次執行皆留存附時間戳記之紀錄，並與前次比對，使 API 行為之變更得以察覺並追溯。同一次執行產生公開版與完整版兩份紀錄，分別供發布與本機排查之用。 |

### 12.2 程式所採用之寫法

| 寫法 | 出現位置 | 說明 |
|---|---|---|
| Arrange、Act、Assert | 所有測試 | 測試之三段式結構：準備資料、執行動作、驗證結果。段落分明，失敗時易於判定問題所在之階段。 |
| `@pytest.mark.smoke` | `test_smoke.py` | 為測試加註標記，其後得以 `-m smoke` 僅執行具此標記之測試。 |
| `@pytest.mark.parametrize` | `test_posts_boundary.py` | 參數化：同一測試函式以不同資料各執行一次。四個無效 id 之預期結果相同，故共用一個函式；各組資料於報告中仍為獨立之測試案例。 |
| `pytest.param(..., id=...)` | `test_posts_boundary.py` | 為各組參數指定報告所顯示之名稱，以對應測試計畫之 Test ID。 |
| `pytest.raises(...)` | `test_error_handling.py` | 預期區塊內之程式將拋出指定之例外。拋出則通過，未拋出則失敗。 |
| `timeout=(連線, 讀取)` | `test_error_handling.py` | requests 之逾時得分別指定連線與讀取兩階段。ERR-01 採用極短之讀取逾時，其結果不受執行環境之網路組態影響（詳見測試計畫第 4 節）。 |
| `type(x) is int` | `test_posts_positive.py` | 嚴格之型別檢查。布林值於 Python 屬整數之子型別，`isinstance(x, int)` 會將 `True` 判定為整數；本寫法則不會。 |
| `set(post.keys()) == {...}` | `test_posts_positive.py` | 欄位名稱須完全相符：缺少或多出欄位皆判定為失敗。 |
| `all(...)` 之前先檢查筆數 | `test_posts_positive.py` | 對空清單而言，`all(...)` 恆為真，將導致測試誤判為通過，故先行確認清單不為空。 |
| `response.elapsed` | `test_error_handling.py` | requests 所量測之回應時間。 |
| `Path(__file__).resolve()` | `test_posts_positive.py` | 以測試檔自身之位置推算 `data/` 之路徑，使測試不受執行時所在目錄影響。 |
| `@pytest.hookimpl(tryfirst=True)` | `conftest.py` | 掛鉤函式（hook，pytest 於特定時機自動呼叫之函式）。`tryfirst=True` 使其先於其他外掛執行，以確保於報告輸出前完成過濾。 |
| 允許清單 | `conftest.py`、`explore_api.py` | 僅允許清單所列項目出現於報告或公開版紀錄。相較於排除清單，日後新增之欄位亦將自動過濾。 |
| `os.environ.get("GITHUB_ACTIONS")` | `conftest.py` | GitHub Actions 於執行時設定此環境變數，據以判斷是否於 CI 環境執行。 |
| `os.environ.get(名稱, 預設值)` | `config.py` | 讀取環境變數；未設定時採用預設值。藉此可於不修改程式之情形下切換被測網址。 |

## 13. 持續整合（CI）

### 13.1 工作流程

`.github/workflows/tests.yml` 定義 GitHub Actions 之工作流程。

| 項目 | 設定 |
|---|---|
| 觸發時機 | 每次 push、每次 pull request、每週排程，以及於 Actions 頁面手動執行 |
| 排程時間 | 每週日 18:17 UTC，即臺灣時間每週一 02:17 |
| 執行環境 | GitHub 提供之標準 Ubuntu 執行環境 |
| Python 版本 | 3.11 與 3.13，各自獨立執行 |
| 逾時 | 10 分鐘 |
| 權限 | 僅讀取儲存庫內容 |
| 產出 | 各 Python 版本一份 HTML 報告，保存 30 天 |

步驟依序為：取出程式碼、安裝指定版本之 Python、安裝相依套件、執行測試、上傳報告。
上傳步驟設定為測試失敗時仍予執行，因測試失敗時尤其需要報告以供分析。

排程之目的，在於程式碼未變更時仍定期執行測試，以察覺被測對象行為之變更。
排程相關之注意事項如下：

- 排程時間以 UTC 設定，且實際啟動時間可能延後。
- 公開儲存庫若連續 60 日無任何活動，GitHub 將自動停用排程；
  須於 Actions 頁面重新啟用，或推送新的提交。
- 排程執行失敗時，README 之狀態徽章將顯示為失敗，直至下一次執行成功為止。
  判讀方式見 13.3。

### 13.2 檢視結果與下載報告

1. 開啟儲存庫之 Actions 頁面，選取一次執行紀錄。
2. 綠色勾號表示全部通過；紅色叉號表示有測試未通過或發生執行錯誤。
3. 於頁面下方之 Artifacts 區塊下載 `test-report-python-3.11` 或
   `test-report-python-3.13`，解壓縮後以瀏覽器開啟 `report.html`。

CI 產出之報告係於 GitHub 之執行環境產生，不含開發者本機之任何資訊；
Environment 區塊一律僅保留版本資訊（見第 5 節）。

### 13.3 CI 失敗之判讀

被測對象為第三方服務，CI 失敗未必表示專案存有缺陷，應依第 8 節之流程分類。

| 情形 | 判讀 |
|---|---|
| 各 Python 版本同時失敗於連線或逾時 | 多屬被測服務或網路之暫時性問題；應重新執行以資確認 |
| 僅單一 Python 版本失敗 | 多屬版本相容性問題；應檢視該版本之報告 |
| 本機通過而 CI 失敗 | 測試可能隱含對執行環境之假設；應比對錯誤訊息並檢視測試設計 |
| 斷言失敗且可重現 | 被測對象行為變更；應依 8.3 之順序處理 |
| 安裝相依套件失敗 | 環境問題；應確認 `requirements.txt` 所載版本於該 Python 版本可用 |

「本機通過而 CI 失敗」之實例及其根因分析，載於 `docs/test_plan.md` 第 4 節之 ERR-01 修訂紀錄。

### 13.4 首次發布至 GitHub

於 GitHub 建立公開儲存庫，且不勾選建立 README、`.gitignore` 與授權條款，
其後於專案根目錄執行：

```
git init
git config user.name "顯示名稱"
git config user.email "GitHub 提供之 noreply 信箱"
git add .
git status
git commit -m "Add API test suite with pytest, HTML report and CI workflow"
git branch -M main
git remote add origin https://github.com/帳號/儲存庫名稱.git
git push -u origin main
```

注意事項如下：

- **提交者資訊**：提交紀錄將公開顯示 `user.name` 與 `user.email`。
  GitHub 於帳號設定之 Emails 頁面提供 noreply 信箱，可避免公開個人信箱。
  此處之 `git config` 未加 `--global`，其設定僅作用於本專案。
- **提交前檢查**：`git status` 所列之待提交清單不應包含 `.venv/`、
  `reports/` 與 `observations_local/`。若有出現，應先確認 `.gitignore` 存在於專案根目錄。
- **提交訊息**：以一行摘要說明該次提交之變更內容。本專案之提交訊息以英文撰寫，
  並以動詞原形起始（如 Add、Fix、Update），與 Git 之通用慣例一致。

推送完成後，工作流程即自動執行。
