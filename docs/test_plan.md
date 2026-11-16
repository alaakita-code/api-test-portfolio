# 測試計畫（v1.5）

- 被測對象：JSONPlaceholder `/posts`（REST API）
- Base URL：`https://jsonplaceholder.typicode.com`
- 狀態：定案。24 個測試案例之預期結果均已確定，無待確認項目。
- 預期值之依據：`docs/api_observed.md` 之觀察 2（curl）與觀察 3（瀏覽器 `fetch`）。本文件以「#」加編號表示觀察 3 之請求編號。
- 驗證紀錄：全部 24 個測試案例及 1 個冒煙測試，已以 Python requests 於 CI（Ubuntu，Python 3.11 與 3.13）執行並通過（2026-11-14）。另於本機（Windows，Python 3.13.1）執行最終版本，25 個測試全數通過（25 passed in 24.14s，2026-11-14）。每週排程已於 2026-11-16（臺灣時間 06:56）執行，Python 3.11 與 3.13 均通過。執行結果與瀏覽器觀察一致。觀察工具（`tools/explore_api.py`）已於 2026-11-16 執行兩次（UTC 09:44:13、16:45:51），各 20 個請求，兩次之狀態碼與回應結構一致，且 20 個請求之狀態碼與結構均與本計畫相符；唯一差異見第 7 節。CI 之追溯對照（Python 3.11）結果為：計畫 24 項、已實作 24 項、通過 24 項、未通過 0 項，另有 1 個未標示 Test ID 之測試（冒煙測試）。
- 備註：第 4.3 節所述之 `Location` 標頭，於觀察工具之紀錄中未出現，原因待確認，詳見第 7 節。

## 變更紀錄

| 版本 | 日期 | 內容 |
|---|---|---|
| v0.1 | 2026-11-14 | 初版；19 個測試案例之預期結果待確認 |
| v0.2 | 2026-11-14 | 依實際觀察填入 17 個測試案例之預期結果；調整 7 個標題（BND-03 至 BND-06、NEG-01、NEG-03、NEG-05）；NEG-04 加註須複驗；POS-05 不納入 `Location` 標頭 |
| v1.0 | 2026-11-14 | ERR-01、ERR-02 依本機實測之回應時間定案；NEG-04 經 Python requests 複驗後定案；新增驗證紀錄 |
| v1.1 | 2026-11-14 | 修訂 ERR-01：由極短之連線逾時改為極短之讀取逾時，原因詳見第 4 節 |
| v1.2 | 2026-11-14 | 全文改以正式書面語撰寫；更新驗證紀錄，納入 CI 之執行結果。測試案例之內容未變更 |
| v1.3 | 2026-11-14 | 驗證紀錄補入最終版本之本機執行結果（25 passed）。測試案例之內容未變更 |
| v1.4 | 2026-11-16 | 驗證紀錄補入每週排程之首次執行結果。測試案例之內容未變更 |
| v1.5 | 2026-11-17 | 驗證紀錄補入觀察工具之兩次執行結果與追溯對照結果；第 4.3 節加註與觀察工具紀錄之差異；第 5 節檔案結構補列新增之目錄與工作流程；第 6 節補列 Test ID 之標示位置；新增第 7 節。測試案例之內容未變更 |

## 1. 測試範圍

**納入範圍**：`/posts` 之 GET、POST、PUT、PATCH、DELETE；查詢參數篩選；一層巢狀路徑 `/posts/{id}/comments`。

**不納入範圍**

| 項目 | 原因 |
|---|---|
| 權限與安全性（登入、token、越權存取） | 被測對象未設驗證機制 |
| 資料一致性（寫入後查詢） | 被測對象不保存寫入結果。觀察 3 之 #8 刪除 `/posts/1` 後，#19 仍可取得該筆資料 |
| 併發與負載測試 | 被測對象為第三方公開服務，未取得負載測試之授權 |
| 其他資源（users、todos 等） | 本版聚焦於單一資源之完整涵蓋；是否擴充另行決定 |

## 2. 優先級定義

- P0：核心讀取與寫入之基本行為。此類行為錯誤時，其餘測試結果即不具意義。
- P1：重要行為，惟存有替代流程（篩選、更新、錯誤回應）。
- P2：次要或低頻情境。

## 3. 測試案例

共 24 個測試案例。各案例之自動化可行性（Automation Feasibility）均為「可自動化」，故不另列欄位。
另有 1 個冒煙測試（`tests/test_smoke.py`）用於確認環境可用，不列入本表；實際執行之測試共 25 個。
各案例之前置條件（Precondition）相同：網路可連線至 Base URL，無須帳號或金鑰。

### 正向（Positive）

| Test ID | Title | Pri | Steps | Expected Result | Test Data | 依據 |
|---|---|---|---|---|---|---|
| POS-01 | 取得全部文章時回傳 100 筆 | P0 | GET /posts | 200；清單長度為 100 | 無 | #1 |
| POS-02 | 取得單筆文章時回傳正確之欄位與型別 | P0 | GET /posts/1 | 200；id 為 1；欄位恰為 userId、id、title、body；型別依序為整數、整數、字串、字串 | id=1 | #2 |
| POS-03 | 以 userId 篩選時僅回傳該使用者之文章 | P1 | GET /posts?userId=1 | 200；共 10 筆；各筆之 userId 均為 1 | userId=1 | #3 |
| POS-04 | 取得文章之留言時各筆 postId 正確 | P1 | GET /posts/1/comments | 200；各筆之 postId 均為 1 | id=1 | #4 |
| POS-05 | 新增文章時回傳送出之內容及新 id | P0 | POST /posts | 201；id 為 101；title、body、userId 與送出值相同 | data/new_post.json | #5 |
| POS-06 | 完整更新文章時回傳更新後之內容 | P1 | PUT /posts/1 | 200；回傳內容與送出內容完全相同 | data/updated_post.json | #6 |
| POS-07 | 部分更新時僅變更指定欄位 | P1 | PATCH /posts/1 | 200；title 為 `patched`；userId、id、body 維持原值 | title="patched" | #7 |
| POS-08 | 刪除文章時回傳成功 | P1 | DELETE /posts/1 | 200；內容為 `{}` | id=1 | #8 |
| POS-09 | 回應標頭宣告為 JSON 格式 | P2 | GET /posts/1 | `Content-Type` 為 `application/json; charset=utf-8` | id=1 | 觀察 2；觀察 3 全部 20 筆 |

### 邊界（Boundary）

| Test ID | Title | Pri | Steps | Expected Result | Test Data | 依據 |
|---|---|---|---|---|---|---|
| BND-01 | 最小有效 id 可取得 | P1 | GET /posts/1 | 200；id 為 1 | id=1 | #2 |
| BND-02 | 最大有效 id 可取得 | P1 | GET /posts/100 | 200；id 為 100 | id=100 | #9 |
| BND-03 | 低於最小值之 id 回傳 404 與空物件 | P1 | GET /posts/0 | 404；內容為 `{}` | id=0 | #10 |
| BND-04 | 高於最大值之 id 回傳 404 與空物件 | P1 | GET /posts/101 | 404；內容為 `{}` | id=101 | #11 |
| BND-05 | 負數 id 回傳 404 與空物件 | P2 | GET /posts/-1 | 404；內容為 `{}` | id=-1 | #12 |
| BND-06 | 非數字 id 回傳 404 與空物件 | P2 | GET /posts/abc | 404；內容為 `{}` | id=abc | #13 |

### 負向（Negative）

| Test ID | Title | Pri | Steps | Expected Result | Test Data | 依據 |
|---|---|---|---|---|---|---|
| NEG-01 | 不存在之路徑回傳 404 與空物件 | P1 | GET /not-a-real-path | 404；內容為 `{}` | 無 | #14 |
| NEG-02 | 篩選無符合資料時回傳空清單 | P1 | GET /posts?userId=999 | 200；內容為空清單 `[]` | userId=999 | #15 |
| NEG-03 | 新增時送出空白內容仍獲接受 | P2 | POST /posts，內容為 {} | 201；內容為 `{"id":101}` | {} | #16 |
| NEG-04 | 更新不存在之 id 時回傳 404 與空物件 | P2 | PUT /posts/101 | 404；內容為 `{}` | id=101 | #17；經 Python requests 複驗，結果相同 |
| NEG-05 | 刪除不存在之 id 時仍回傳 200 | P2 | DELETE /posts/101 | 200；內容為 `{}` | id=101 | #18 |

### 錯誤處理（Error handling，驗證測試工具本身）

| Test ID | Title | Pri | Steps | Expected Result | Test Data | 依據 |
|---|---|---|---|---|---|---|
| ERR-01 | 回應未於時限內送達時，用戶端拋出逾時錯誤 | P1 | 以正常之連線逾時及 0.0001 秒之讀取逾時呼叫 GET /posts | 拋出 requests 之 Timeout，不致無限等待 | 連線逾時 10 秒；讀取逾時 0.0001 秒 | 連線建立後，遠端伺服器無法於萬分之一秒內回應，故必然逾時 |
| ERR-02 | 正常請求於逾時上限內完成 | P2 | GET /posts/1 | 200；回應時間低於 10 秒 | id=1；上限 10 秒 | 本機實測：10 個測試耗時 10.73 秒、21 個測試耗時 20.69 秒，平均每個約 1 秒 |

### 重複請求（Repeat）

| Test ID | Title | Pri | Steps | Expected Result | Test Data | 依據 |
|---|---|---|---|---|---|---|
| REP-01 | 同一 GET 請求連續送出 3 次時結果完全相同 | P1 | 連續送出 GET /posts/1 三次 | 三次之狀態碼與內容均相同 | id=1 | #2、#19 |
| REP-02 | 同一 DELETE 請求連續送出 2 次時結果一致 | P2 | 連續送出 DELETE /posts/1 兩次 | 兩次均為 200 與 `{}` | id=1 | #8、#20 |

## 4. 個別案例之說明

### 4.1 NEG-03

被測對象不驗證輸入，送出空白內容仍回應 201。本案例所記錄者為被測對象之實際行為，並不表示該行為屬正確之設計；正式產品應拒絕此類請求。此限制已載於 README。

### 4.2 NEG-04 與 NEG-05

對同一不存在之 id，PUT 回應 404，DELETE 回應 200，兩者行為不一致。兩案例均已以 Python requests 複驗，結果相同。

### 4.3 POS-05

觀察結果顯示回應帶有 `Location` 標頭（指向 `/posts/101`）。本案例不驗證該標頭，以維持每個測試僅驗證單一行為之原則。

與觀察工具紀錄之差異見第 7 節；該節之結果不影響本案例之預期值，因本案例未驗證該標頭。

### 4.4 REP-01

GET 回應多由 Cloudflare 快取提供（`cf-cache-status: HIT`），故本案例所驗證者可能為快取之一致性，未必為來源伺服器之行為。此限制已載於 README。

### 4.5 ERR-01 之修訂（v1.1）

**失敗現象**：原設計以 0.001 秒之整體逾時呼叫 API，並預期必然取得逾時錯誤。該設計於本機（Windows）通過，惟於 CI（GitHub 之 Linux 執行環境）失敗。兩個 Python 版本均取得 `ConnectionError`，訊息為 `[Errno 101] Network is unreachable`；其餘 24 個測試通過。

**分類**：測試腳本問題。同一次執行中，其餘 24 個測試均成功連線，足認被測對象與 CI 之網路均屬正常。

**最可能之根因**：連線逾時極短時，用戶端依序嘗試主機之各個位址，並回報最後一次嘗試之錯誤。於無 IPv6 路由之環境，最後一次嘗試（IPv6）立即以「網路無法連線」失敗，故取得者為連線錯誤，而非逾時錯誤。此項判斷係依錯誤訊息所為之推論，信心程度為中高；未直接檢視執行環境之網路設定。

**原設計之錯誤假設**：「逾時時間夠短，即必然取得逾時錯誤。」實際上，結果取決於執行環境之網路組態。

**修訂內容**：改採讀取逾時。連線以正常時限建立（與其餘測試相同），其後要求回應於 0.0001 秒內送達。讀取逾時於連線建立後始生效，不受位址嘗試順序影響。

**驗證結果**：修訂後之測試於 CI（Python 3.11 與 3.13）通過。修訂後之本機執行結果：25 個測試全數通過（25 passed in 24.14s，2026-11-14）。

**未採用之方案**：使測試同時接受逾時錯誤與連線錯誤。此方案將放寬斷言，使測試於網路中斷時亦通過，致無法證明逾時設定確實有效，故不予採用。

### 4.6 ERR-01 與 ERR-02 之數值

數值依本機實測結果訂定。平均每個測試約需 1 秒；此平均值包含測試工具之啟動時間，且僅有兩次執行之樣本。10 秒之上限為保守之安全範圍（約十倍餘裕），並非效能標準。上限若過於接近實際回應時間，將形成不穩定之測試（flaky test，即結果時而通過、時而失敗之測試）。

### 4.7 不設斷言之標頭

`Date`、`Age`、`CF-RAY`、`Report-To` 之值於每次請求皆可能不同，故不設斷言。`x-ratelimit-remaining` 之值可能為存入快取當時之數值，未必反映當下之剩餘額度；此點尚待確認，故亦不設斷言。

## 5. 檔案結構

```text
api-test-portfolio/
├── .alaakita/
├── .github/workflows/
│   ├── tests.yml
│   └── alaakita-gate.yml
├── tests/
│   ├── conftest.py
│   ├── test_smoke.py
│   ├── test_posts_positive.py
│   ├── test_posts_boundary.py
│   ├── test_posts_negative.py
│   ├── test_error_handling.py
│   └── test_repeat_requests.py
├── utils/
│   ├── api_client.py
│   └── config.py
├── data/
│   ├── new_post.json
│   └── updated_post.json
├── tools/
│   ├── explore_api.py
│   ├── traceability/
│   └── alaakita/
├── docs/
│   ├── USAGE.zh-TW.md
│   ├── test_plan.md
│   ├── api_observed.md
│   ├── api_notes.md
│   └── observations/
├── reports/                 （不納入版本控制）
├── observations_local/      （不納入版本控制）
├── requirements.txt
├── pytest.ini
├── README.md
└── README.zh-TW.md
```

本專案暫不建立 `utils/assertions.py` 與 `data/expected_responses/`。俟斷言確有重複時再行抽出，以避免過度抽象。

## 6. 命名規則

- 測試函式之名稱格式為 `test_<被測行為>_<條件>_<預期結果>`，例如 `test_get_post_with_valid_id_returns_expected_fields_and_types`。
- 每個測試採 Arrange、Act、Assert 三段式結構，並於說明文字標示對應之 Test ID。
- Test ID 須標示於測試函式說明文字之第一行（可標示範圍），或參數化案例之 `pytest.param(..., id="BND-03-...")`，追溯工具依此二處讀取。

## 7. 觀察工具紀錄與測試計畫之對照

依據：`docs/observations/` 所載 2026-11-16 之兩次執行紀錄（公開版）。

| 項目 | 測試計畫之記載 | 觀察工具之紀錄 | 狀態 |
|---|---|---|---|
| 20 個請求之狀態碼 | 見第 3 節各案例之預期結果 | 兩次執行均與計畫相符 | 已核對 |
| 20 個請求之回應結構 | 見第 3 節各案例之預期結果 | 兩次執行均與計畫相符 | 已核對 |
| 兩次執行之間 | - | 狀態碼與結構無差異 | 已核對；API 行為變更時之差異列示功能尚未被觸發，未經實際驗證 |
| POST /posts（#5）之 `Location` 標頭 | 第 4.3 節：觀察結果顯示回應帶有 `Location` 標頭 | 兩次執行之公開版紀錄均未出現 `Location` | 待確認 |

`Location` 標頭之差異：計畫之記載取自 curl 與瀏覽器之觀察；觀察工具以 Python requests 發出請求，並以允許清單記錄標頭。
可能原因有二：該標頭於 requests 之回應中實際不存在；或標頭名稱之大小寫於比對時未對應。兩者均未經驗證，原因待確認。
本項不影響任何測試，因現有測試未驗證 `Location`。第 4.3 節之原文維持不變。待以唯讀方式重新觀察後再決定是否修訂該節。
