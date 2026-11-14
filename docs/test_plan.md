# 測試計畫（v1.0）

- 被測對象：JSONPlaceholder `/posts`（REST API）
- Base URL：`https://jsonplaceholder.typicode.com`
- 狀態：定案。24 案的預期結果全部確定，沒有待確認項目。
- 預期值的依據：`docs/api_observed.md` 觀察 2（curl）與觀察 3（瀏覽器 `fetch`，請求編號以 # 表示）。
- 驗證紀錄：POS、BND、NEG 三組共 20 案已用 Python requests 在本機實際執行並通過（2026-11-14，Python 3.13.1），結果與瀏覽器觀察一致。ERR 與 REP 兩組共 4 案的預期值已定，執行結果見專案的測試報告。

## 變更紀錄

| 版本 | 日期 | 內容 |
|---|---|---|
| v0.1 | 2026-11-14 | 初版，19 案預期結果待確認 |
| v0.2 | 2026-11-14 | 依實際觀察填入 17 案預期結果；調整 7 個標題（BND-03 至 06、NEG-01、NEG-03、NEG-05）；NEG-04 加註複驗；POS-05 不納入 `Location` 標頭 |
| v1.0 | 2026-11-14 | ERR-01、ERR-02 依本機實測回應時間定案；NEG-04 經 Python requests 複驗後定案；新增驗證紀錄 |

## 1. 測試範圍

**測試**：`/posts` 的 GET、POST、PUT、PATCH、DELETE；查詢參數篩選；一層巢狀路徑 `/posts/{id}/comments`。

**不測（附原因）**

| 項目 | 原因 |
|---|---|
| 權限與安全（登入、token、越權） | 此 API 沒有驗證機制 |
| 資料一致性（寫入後查詢） | 寫入不保存；觀察 3 中 #8 刪除 `/posts/1` 後，#19 仍可取得 |
| 併發與負載測試 | 被測對象為第三方公開服務，未取得負載測試授權 |
| 其他資源（users、todos 等） | 第一版先把一種資源做深；是否擴充待決定 |

## 2. 優先級定義

- P0：核心讀取與寫入的基本行為錯誤，整個專案失去意義
- P1：重要但有替代流程（篩選、更新、錯誤回應）
- P2：次要或低頻情境

## 3. 測試案例

共 24 案。Automation Feasibility 全部為「可自動化」，故不另列一欄。
另有 1 個冒煙測試（`tests/test_smoke.py`）用來確認環境可用，不列入本表，所以實際執行的測試共 25 個。
Precondition 全部相同：網路可連到 Base URL，不需帳號或金鑰。

### 正向（Positive）

| Test ID | Title | Pri | Steps | Expected Result | Test Data | 依據 |
|---|---|---|---|---|---|---|
| POS-01 | 取得全部文章回傳 100 筆 | P0 | GET /posts | 200；清單長度 100 | 無 | #1 |
| POS-02 | 取得單筆文章回傳正確欄位與型別 | P0 | GET /posts/1 | 200；id 為 1；欄位恰為 userId、id、title、body；型別為整數、整數、字串、字串 | id=1 | #2 |
| POS-03 | 以 userId 篩選只回傳該使用者的文章 | P1 | GET /posts?userId=1 | 200；共 10 筆；每筆 userId 為 1 | userId=1 | #3 |
| POS-04 | 取得文章的留言且每筆 postId 正確 | P1 | GET /posts/1/comments | 200；每筆 postId 為 1 | id=1 | #4 |
| POS-05 | 新增文章回傳送出的內容與新 id | P0 | POST /posts | 201；id 為 101；title、body、userId 與送出值相同 | data/new_post.json | #5 |
| POS-06 | 完整更新文章回傳更新後內容 | P1 | PUT /posts/1 | 200；回傳內容與送出內容完全相同 | data/updated_post.json | #6 |
| POS-07 | 部分更新只改動指定欄位 | P1 | PATCH /posts/1 | 200；title 為 `patched`；userId、id、body 維持原值 | title="patched" | #7 |
| POS-08 | 刪除文章回傳成功 | P1 | DELETE /posts/1 | 200；內容為 `{}` | id=1 | #8 |
| POS-09 | 回應標頭為 JSON 格式 | P2 | GET /posts/1 | `Content-Type` 為 `application/json; charset=utf-8` | id=1 | 觀察 2、觀察 3 全部 20 筆 |

### 邊界（Boundary）

| Test ID | Title | Pri | Steps | Expected Result | Test Data | 依據 |
|---|---|---|---|---|---|---|
| BND-01 | 最小有效 id 可取得 | P1 | GET /posts/1 | 200；id 為 1 | id=1 | #2 |
| BND-02 | 最大有效 id 可取得 | P1 | GET /posts/100 | 200；id 為 100 | id=100 | #9 |
| BND-03 | 低於最小值的 id 回傳 404 與空物件 | P1 | GET /posts/0 | 404；內容為 `{}` | id=0 | #10 |
| BND-04 | 高於最大值的 id 回傳 404 與空物件 | P1 | GET /posts/101 | 404；內容為 `{}` | id=101 | #11 |
| BND-05 | 負數 id 回傳 404 與空物件 | P2 | GET /posts/-1 | 404；內容為 `{}` | id=-1 | #12 |
| BND-06 | 非數字 id 回傳 404 與空物件 | P2 | GET /posts/abc | 404；內容為 `{}` | id=abc | #13 |

### 負向（Negative）

| Test ID | Title | Pri | Steps | Expected Result | Test Data | 依據 |
|---|---|---|---|---|---|---|
| NEG-01 | 不存在的路徑回傳 404 與空物件 | P1 | GET /not-a-real-path | 404；內容為 `{}` | 無 | #14 |
| NEG-02 | 篩選無符合資料時回傳空清單 | P1 | GET /posts?userId=999 | 200；內容為空清單 `[]` | userId=999 | #15 |
| NEG-03 | 新增時送空內容仍被接受 | P2 | POST /posts，內容為 {} | 201；內容為 `{"id":101}` | {} | #16 |
| NEG-04 | 更新不存在的 id 回傳 404 與空物件 | P2 | PUT /posts/101 | 404；內容為 `{}` | id=101 | #17；Python requests 複驗相同 |
| NEG-05 | 刪除不存在的 id 仍回傳 200 | P2 | DELETE /posts/101 | 200；內容為 `{}` | id=101 | #18 |

### 錯誤處理（Error handling，驗證測試工具本身）

| Test ID | Title | Pri | Steps | Expected Result | Test Data | 依據 |
|---|---|---|---|---|---|---|
| ERR-01 | 逾時極短時 client 拋出逾時錯誤 | P1 | 以 0.001 秒逾時呼叫 GET /posts | 拋出 requests 的 Timeout，不會無限等待 | 逾時 0.001 秒 | 千分之一秒內無法完成連線，必定逾時 |
| ERR-02 | 正常請求在逾時上限內完成 | P2 | GET /posts/1 | 200；回應時間低於 10 秒 | id=1；上限 10 秒 | 本機實測：10 個測試 10.73 秒、21 個測試 20.69 秒，平均每個約 1 秒 |

### 重複請求（Repeat）

| Test ID | Title | Pri | Steps | Expected Result | Test Data | 依據 |
|---|---|---|---|---|---|---|
| REP-01 | 同一 GET 連送 3 次結果完全相同 | P1 | GET /posts/1 三次 | 三次狀態碼與內容相同 | id=1 | #2、#19 |
| REP-02 | 同一 DELETE 連送 2 次結果一致 | P2 | DELETE /posts/1 兩次 | 兩次都是 200 與 `{}` | id=1 | #8、#20 |

## 4. 需要特別說明的案例

- **NEG-03**：API 不驗證輸入，空內容仍回 201。這個測試記錄的是 API 的實際行為，不代表這是正確設計；README 會註明「真實產品應該拒絕這類請求」。
- **NEG-04 與 NEG-05**：對同一個不存在的 id，PUT 回 404、DELETE 回 200，兩者行為不一致。兩案都已用 Python requests 複驗，結果相同。
- **POS-05**：觀察到回應帶有 `Location` 標頭（指向 `/posts/101`），本案不驗證它，維持每個測試只驗證一個行為。
- **REP-01**：GET 回應多來自 Cloudflare 快取（`cf-cache-status: HIT`），這個測試驗證到的可能是快取的一致性，不一定是來源伺服器的行為。README 的限制段落會說明。
- **ERR-01、ERR-02**：數值依本機實測決定。平均每個測試約 1 秒，這個平均值包含測試工具的啟動時間，且只有兩次執行。10 秒上限是保守的安全範圍（約十倍餘裕），不是效能標準；設得太接近實際回應時間會變成不穩定測試（flaky test，時好時壞的測試）。
- **不寫斷言的標頭**：`Date`、`Age`、`CF-RAY`、`Report-To` 每次請求都可能不同；`x-ratelimit-remaining` 可能是快取當時的舊值（待確認）。

## 5. 檔案結構

```text
api-test-portfolio/
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
├── tools/explore_api.py
├── docs/
│   ├── USAGE.zh-TW.md
│   ├── test_plan.md
│   ├── api_observed.md
│   └── api_notes.md
├── reports/            (不進版控)
├── .github/workflows/tests.yml
├── requirements.txt
├── pytest.ini
├── README.md
└── README.zh-TW.md
```

暫不建立 `utils/assertions.py` 與 `data/expected_responses/`，等確實出現重複的斷言再抽出，避免過度抽象。

## 6. 命名規則

- 測試函式：`test_<被測行為>_<條件>_<預期結果>`，例如 `test_get_post_with_id_above_max_returns_404`
- 每個測試用 Arrange、Act、Assert 三段，並在文件字串標示 Test ID
