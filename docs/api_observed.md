# Observed API behaviour

本檔只記錄實際觀察到的結果，不含推測。

## 觀察 1：GET /posts/999999

### 請求

| 項目 | 內容 |
|---|---|
| Method | GET |
| URL | `https://jsonplaceholder.typicode.com/posts/999999` |
| 請求次數 | 1 次（頁面導覽） |
| 請求時間 | 約 2026-11-14 15:43（台北時間，UTC+8）。頁面載入完成後讀到的用戶端時間為 `2026-11-14T07:43:42.669Z`，請求送出時間略早於此，精確秒數未取得 |

### 測試環境

| 項目 | 內容 |
|---|---|
| 送出位置 | 使用者電腦（Windows x64）上 Claude 桌面版的內建瀏覽器 |
| 用戶端 | Chromium 核心的桌面瀏覽器（完整版本字串已移除） |
| 不是用 | curl 或 Python requests（兩者在可用環境中皆被網路允許清單擋下） |

### 回應

**HTTP status code**

```
404
```

來源：瀏覽器網路紀錄 `GET https://jsonplaceholder.typicode.com/posts/999999 → 404`，以及導覽計時資料 `responseStatus: 404`，兩者一致。

**Response body（原始內容，共 2 位元組）**

```
{}
```

來源：瀏覽器網路紀錄的回應內容，與頁面文字一致；`encodedBodySize: 2`、`decodedBodySize: 2`。

**Headers**

完整的原始 response headers **未取得**。瀏覽器工具只回報狀態碼與內容，沒有提供標頭清單。以下是能從瀏覽器間接讀到的項目，不等於原始標頭：

| 項目 | 觀察值 | 讀取方式 |
|---|---|---|
| 內容類型 | `application/json` | `document.contentType` |
| 字元編碼 | `UTF-8` | `document.characterSet` |
| 通訊協定 | `h2`（HTTP/2） | 導覽計時資料 `nextHopProtocol` |
| 載入耗時 | 940 毫秒 | 導覽計時資料 `duration`（含連線建立，僅單次量測） |

### 觀察結論

1. 對不存在的文章 id（999999）送出 GET，API 回傳 **404**，內容為空的 JSON 物件 `{}`。
2. 回應內容類型為 JSON，不是 HTML 錯誤頁。
3. 回應中沒有錯誤訊息欄位（沒有 `error`、`message` 之類的欄位）。

### 限制與尚未確認的事項

- 只送了 1 次請求，無法說明結果是否穩定或回應時間的正常範圍。
- 這次只驗證了 id=999999。`/posts/0`、`/posts/101`、`/posts/-1`、`/posts/abc` 是否同樣回 404 與 `{}`，**待確認**，不能由本次結果推論。
- 完整 response headers：本次未取得，已由「觀察 2」補上。
- 請求由瀏覽器送出，瀏覽器會自動加上自己的 request headers（例如 Accept、User-Agent）；用 Python requests 送出時回應是否完全相同，**待確認**。
- 瀏覽器載入頁面時可能另外自動請求網站圖示（favicon）；本次網路紀錄以 `posts/999999` 篩選，未檢查是否有這類額外請求。

## 觀察 2：GET /posts/999999（curl，含完整 headers）

### 請求

| 項目 | 內容 |
|---|---|
| 指令 | `curl.exe -i https://jsonplaceholder.typicode.com/posts/999999` |
| 請求時間 | 2026-11-14 15:47:14（台北時間，UTC+8），依回應的 `Date` 標頭 `Sat, 14 Nov 2026 07:47:14 GMT` 換算 |
| 執行者 | 使用者本人，於自己的 Windows 電腦、`api-test-portfolio` 目錄下執行 |
| 用戶端 | Windows 內建 `curl.exe`（版本未記錄） |

### 回應（原始輸出；僅 `CF-RAY` 與 `Report-To` 兩行的值已移除，其餘未修改）

```
HTTP/1.1 404 Not Found
Date: Sat, 14 Nov 2026 07:47:14 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 2
Connection: keep-alive
access-control-allow-credentials: true
Cache-Control: max-age=43200
etag: W/"2-vyGp6PvFo4RvsFtPoIWeCReyIC8"
expires: -1
pragma: no-cache
vary: Origin, Accept-Encoding
x-content-type-options: nosniff
x-powered-by: Express
x-ratelimit-limit: 3600000
x-ratelimit-remaining: 3599999
x-ratelimit-reset: 1794639619
Nel: {"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}
Age: 4459
cf-cache-status: HIT
Report-To: [已移除]
Server: cloudflare
CF-RAY: [已移除]
alt-svc: h3=":443"; ma=86400

{}
```

### 觀察結論

1. 狀態碼 **404 Not Found**、內容 `{}`、`Content-Length: 2`，與觀察 1（瀏覽器）一致。兩種用戶端得到相同的狀態碼與內容。
2. `Content-Type` 為 `application/json; charset=utf-8`。
3. 這個回應來自 Cloudflare 的快取，不是來源伺服器當下產生的：`cf-cache-status: HIT`，`Age: 4459`（約 74 分鐘前存入快取），`Cache-Control: max-age=43200`（12 小時）。
4. 回應帶有流量限制標頭：`x-ratelimit-limit: 3600000`、`x-ratelimit-remaining: 3599999`。
5. 來源伺服器為 Express（`x-powered-by: Express`），前方為 Cloudflare（`Server: cloudflare`）。
6. 協定為 HTTP/1.1；觀察 1 的瀏覽器使用 HTTP/2。協定不同，狀態碼與內容相同。

### 對測試設計的影響（僅列出，尚未修改任何測試）

- 因為回應來自快取，「同一 GET 重複送出結果相同」（REP-01）驗證到的可能是快取的一致性，不一定是來源伺服器的行為。README 的限制段落應說明這點。
- 因為回應來自快取，`x-ratelimit-remaining` 的數值可能也是存入快取當時的值，不代表目前的剩餘額度。此推論**待確認**，在確認前不應對這個欄位寫斷言。
- `Date`、`Age`、`CF-RAY`、`Report-To` 每次請求都可能不同，不適合寫成固定值的斷言。

### 限制

- 仍只驗證了 id=999999 一個值；其他邊界值（0、101、-1、abc）**待確認**。
- POST、PUT、PATCH、DELETE 的實際回應**待確認**。
- 來源伺服器未經快取的回應是否相同，**待確認**。

## 觀察 3：探索腳本的 20 個請求

### 請求與環境

| 項目 | 內容 |
|---|---|
| 請求內容 | 與 `tools/explore_api.py` 的 `PROBES` 清單相同的 20 個請求，依序送出 |
| 請求時間 | 2026-11-14 約 15:55–15:57（台北時間，UTC+8）；結果讀取時間 `2026-11-14T07:57:46.925Z` |
| 送出位置 | 使用者電腦（Windows x64）上 Claude 桌面版的內建瀏覽器 |
| 送出方式 | 頁面內的 `fetch`，設定 `cache: "no-store"`（不使用瀏覽器本機快取） |
| 寫入類請求的標頭 | `Content-Type: application/json; charset=UTF-8` |
| 用戶端 | Chromium 核心的桌面瀏覽器（完整版本字串已移除） |
| 不是用 | Python requests。`explore_api.py` 本身尚未被執行過 |

所有 20 個回應的 `Content-Type` 都是 `application/json; charset=utf-8`。

### 結果

「快取」欄是回應的 `cf-cache-status` 標頭。

| # | 分組 | Method | Path | 送出內容 | Status | 回應內容 | 快取 |
|---|---|---|---|---|---|---|---|
| 1 | positive | GET | /posts | 無 | 200 | 清單，100 筆；id 由 1 到 100；欄位 userId、id、title、body | HIT |
| 2 | positive | GET | /posts/1 | 無 | 200 | 物件；欄位 userId、id、title、body；型別 number、number、string、string | HIT |
| 3 | positive | GET | /posts?userId=1 | 無 | 200 | 清單，10 筆；id 由 1 到 10；userId 全部為 1 | HIT |
| 4 | positive | GET | /posts/1/comments | 無 | 200 | 清單，5 筆；postId 全部為 1；欄位 postId、id、name、email、body | HIT |
| 5 | positive | POST | /posts | `{"title":"foo","body":"bar","userId":1}` | 201 | `{"title":"foo","body":"bar","userId":1,"id":101}`；另有 `Location: https://jsonplaceholder.typicode.com/posts/101` 標頭 | DYNAMIC |
| 6 | positive | PUT | /posts/1 | `{"id":1,"title":"t","body":"b","userId":1}` | 200 | `{"id":1,"title":"t","body":"b","userId":1}` | DYNAMIC |
| 7 | positive | PATCH | /posts/1 | `{"title":"patched"}` | 200 | title 變為 `patched`；userId、id、body 維持原值 | DYNAMIC |
| 8 | positive | DELETE | /posts/1 | 無 | 200 | `{}` | DYNAMIC |
| 9 | boundary | GET | /posts/100 | 無 | 200 | 物件；id 為 100，userId 為 10 | HIT |
| 10 | boundary | GET | /posts/0 | 無 | 404 | `{}` | HIT |
| 11 | boundary | GET | /posts/101 | 無 | 404 | `{}` | HIT |
| 12 | boundary | GET | /posts/-1 | 無 | 404 | `{}` | HIT |
| 13 | boundary | GET | /posts/abc | 無 | 404 | `{}` | HIT |
| 14 | negative | GET | /not-a-real-path | 無 | 404 | `{}` | MISS |
| 15 | negative | GET | /posts?userId=999 | 無 | 200 | 空清單 `[]` | HIT |
| 16 | negative | POST | /posts | `{}` | 201 | `{"id":101}`；另有 `Location` 標頭指向 `/posts/101` | DYNAMIC |
| 17 | negative | PUT | /posts/101 | `{"title":"x"}` | 404 | `{}` | DYNAMIC |
| 18 | negative | DELETE | /posts/101 | 無 | 200 | `{}` | DYNAMIC |
| 19 | repeat | GET | /posts/1 | 無 | 200 | 與 #2 相同（長度同為 292 字元，內容相同） | HIT |
| 20 | repeat | DELETE | /posts/1 | 無 | 200 | `{}`，與 #8 相同 | DYNAMIC |

回應內容中的 JSON 在本表以單行呈現；實際回應帶有換行與兩格縮排。

`GET /posts/1` 的實際內容：

```json
{
  "userId": 1,
  "id": 1,
  "title": "sunt aut facere repellat provident occaecati excepturi optio reprehenderit",
  "body": "quia et suscipit\nsuscipit recusandae consequuntur expedita et cum\nreprehenderit molestiae ut ut quas totam\nnostrum rerum est autem sunt rem eveniet architecto"
}
```

### 觀察結論

1. 讀取類：`/posts` 共 100 筆，有效 id 為 1 到 100；單筆欄位為 userId、id（數字）與 title、body（字串）。
2. 邊界：id 為 0、101、-1、abc 時都回 404 與 `{}`，沒有錯誤訊息欄位。
3. 不存在的路徑回 404 與 `{}`；篩選無符合資料時回 200 與空清單，不是錯誤。
4. 新增：POST 回 201，回傳送出的內容加上 `id: 101`，並帶 `Location` 標頭。
5. **API 不驗證輸入**：POST 送空物件 `{}` 仍回 201 與 `{"id":101}`。
6. **寫入不保存**：#8 刪除 `/posts/1` 之後，#19 仍能取得 `/posts/1`（200）；兩次 POST 都得到 id 101。
7. **不存在的 id，PUT 與 DELETE 行為不一致**：`PUT /posts/101` 回 404，`DELETE /posts/101` 回 200。
8. 同一 DELETE 送兩次（#8、#20）結果相同：200 與 `{}`。
9. 快取：GET 請求多為 `HIT`（來自 Cloudflare 快取）；POST、PUT、PATCH、DELETE 都是 `DYNAMIC`（未經快取，由來源伺服器回應）。

### 限制

- **回應時間不可採用**。量到的耗時從 50 毫秒到 29,258 毫秒不等，但當時瀏覽器面板是隱藏狀態，背景頁面的計時不準，所以本檔不列出各請求耗時。逾時設定所需的回應時間（Q10）仍**待確認**。
- 每個請求只送 1 次（#19、#20 為刻意重複），未驗證結果是否每次穩定。
- 用戶端是瀏覽器 `fetch`，不是 Python requests。觀察 1、2 顯示瀏覽器與 curl 對同一請求得到相同狀態碼與內容，但其餘 19 個請求未用 curl 或 requests 交叉驗證，**待確認**。
- 第 7 點的 `PUT /posts/101 → 404` 只觀察到 1 次。
