# API 觀察紀錄（專案初期）

本文件記錄專案初期對被測對象所為之三次觀察，為測試計畫預期值之原始依據。
內容以實際觀察所得為限，不含推測；凡屬推論者，均明確標示。

- 被測對象：JSONPlaceholder
- Base URL：`https://jsonplaceholder.typicode.com`
- 觀察日期：2026-11-14
- 後續之觀察紀錄由 `tools/explore_api.py` 自動產生，存於 `docs/observations/`。

## 文件狀態

本文件所列之「待確認」事項，其後續處理情形如下：

| 事項 | 處理情形 |
|---|---|
| 邊界值（0、101、-1、abc）之回應 | 已於觀察 3 取得，並經自動化測試驗證 |
| 寫入類請求之實際回應 | 已於觀察 3 取得，並經自動化測試驗證 |
| 以 Python requests 送出時之回應是否與瀏覽器相同 | 已驗證。自動化測試以 Python requests 執行，結果與本文件一致 |
| `PUT /posts/101` 回應 404（僅觀察一次） | 已經自動化測試複驗，結果相同 |
| 可採用之回應時間 | 已由本機執行測試取得，詳見 `docs/api_notes.md` 之 Q10 |
| 來源伺服器未經快取之回應是否相同 | 尚待確認 |
| `x-ratelimit-remaining` 是否為快取當時之數值 | 尚待確認 |

## 觀察 1：GET /posts/999999（瀏覽器）

### 請求

| 項目 | 內容 |
|---|---|
| Method | GET |
| URL | `https://jsonplaceholder.typicode.com/posts/999999` |
| 請求次數 | 1 次（頁面導覽） |
| 請求時間 | 約 2026-11-14 07:43 UTC。頁面載入完成後所讀取之用戶端時間為 `2026-11-14T07:43:42.669Z`；請求送出時間略早於此，精確秒數未取得 |

### 測試環境

| 項目 | 內容 |
|---|---|
| 用戶端 | Chromium 核心之桌面瀏覽器（Windows x64） |
| 備註 | 本次觀察未使用 curl 或 Python requests |

### 回應

**HTTP 狀態碼**

```
404
```

來源：瀏覽器網路紀錄 `GET https://jsonplaceholder.typicode.com/posts/999999 → 404`，以及導覽計時資料 `responseStatus: 404`；兩者一致。

**回應內容（原始內容，共 2 位元組）**

```
{}
```

來源：瀏覽器網路紀錄之回應內容，與頁面文字一致；`encodedBodySize: 2`、`decodedBodySize: 2`。

**回應標頭**

本次觀察未取得完整之原始回應標頭。瀏覽器工具僅回報狀態碼與內容，未提供標頭清單。
下表為自瀏覽器間接讀取之項目，不等同原始標頭。完整標頭見觀察 2。

| 項目 | 觀察值 | 讀取方式 |
|---|---|---|
| 內容類型 | `application/json` | `document.contentType` |
| 字元編碼 | `UTF-8` | `document.characterSet` |
| 通訊協定 | `h2`（HTTP/2） | 導覽計時資料 `nextHopProtocol` |
| 載入耗時 | 940 毫秒 | 導覽計時資料 `duration`（含連線建立；僅單次量測） |

### 觀察結論

1. 對不存在之文章 id（999999）送出 GET 時，API 回應 **404**，內容為空白之 JSON 物件 `{}`。
2. 回應之內容類型為 JSON，並非 HTML 錯誤頁面。
3. 回應未含錯誤訊息欄位（如 `error`、`message`）。

### 限制

- 僅送出 1 次請求，無法據以判斷結果是否穩定，亦無法得知回應時間之正常範圍。
- 僅驗證 id=999999 一個值；其他邊界值之回應不得由本次結果推論。
- 請求由瀏覽器送出，瀏覽器會自動附加其自身之請求標頭（如 Accept、User-Agent）。
- 瀏覽器載入頁面時可能另行請求網站圖示（favicon）；本次網路紀錄以 `posts/999999` 篩選，未檢視是否存有此類額外請求。

## 觀察 2：GET /posts/999999（curl，含完整標頭）

### 請求

| 項目 | 內容 |
|---|---|
| 指令 | `curl.exe -i https://jsonplaceholder.typicode.com/posts/999999` |
| 請求時間 | 2026-11-14 07:47:14 UTC，依回應之 `Date` 標頭 |
| 用戶端 | Windows 內建之 `curl.exe`（版本未記錄） |

### 回應

以下為原始輸出。`CF-RAY` 與 `Report-To` 兩行之值屬追蹤用識別碼，已予移除；其餘內容未經修改。

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

1. 狀態碼為 **404 Not Found**，內容為 `{}`，`Content-Length` 為 2，與觀察 1（瀏覽器）一致。兩種用戶端取得相同之狀態碼與內容。
2. `Content-Type` 為 `application/json; charset=utf-8`。
3. 該回應由 Cloudflare 之快取提供，並非來源伺服器當下產生：`cf-cache-status: HIT`；`Age: 4459`（約 74 分鐘前存入快取）；`Cache-Control: max-age=43200`（12 小時）。
4. 回應帶有流量限制標頭：`x-ratelimit-limit: 3600000`、`x-ratelimit-remaining: 3599999`。
5. 來源伺服器為 Express（`x-powered-by: Express`），其前端為 Cloudflare（`Server: cloudflare`）。
6. 本次之通訊協定為 HTTP/1.1；觀察 1 之瀏覽器採用 HTTP/2。協定不同，狀態碼與內容相同。

### 對測試設計之影響

- 回應由快取提供，故「同一 GET 請求重複送出時結果相同」（REP-01）所驗證者可能為快取之一致性，未必為來源伺服器之行為。此限制應載於 README。
- 回應由快取提供，故 `x-ratelimit-remaining` 之數值可能為存入快取當時之數值，未必反映當下之剩餘額度。此為推論，尚待確認；確認前不應對該欄位設斷言。
- `Date`、`Age`、`CF-RAY`、`Report-To` 之值於每次請求皆可能不同，不宜設為固定值之斷言。

### 限制

- 僅驗證 id=999999 一個值。
- 來源伺服器未經快取之回應是否相同，尚待確認。

## 觀察 3：20 個請求（瀏覽器 fetch）

### 請求與環境

| 項目 | 內容 |
|---|---|
| 請求內容 | 與 `tools/explore_api.py` 之 `PROBES` 清單相同之 20 個請求，依序送出 |
| 請求時間 | 2026-11-14 約 07:55 至 07:57 UTC；結果讀取時間為 `2026-11-14T07:57:46.925Z` |
| 用戶端 | Chromium 核心之桌面瀏覽器（Windows x64） |
| 送出方式 | 頁面內之 `fetch`，並設定 `cache: "no-store"`（不使用瀏覽器本機快取） |
| 寫入類請求之標頭 | `Content-Type: application/json; charset=UTF-8` |
| 備註 | 本次觀察未使用 Python requests |

全部 20 個回應之 `Content-Type` 均為 `application/json; charset=utf-8`。

### 結果

「快取」欄為回應之 `cf-cache-status` 標頭。

| # | 分組 | Method | Path | 送出內容 | Status | 回應內容 | 快取 |
|---|---|---|---|---|---|---|---|
| 1 | positive | GET | /posts | 無 | 200 | 清單，100 筆；id 為 1 至 100；欄位為 userId、id、title、body | HIT |
| 2 | positive | GET | /posts/1 | 無 | 200 | 物件；欄位為 userId、id、title、body；型別依序為 number、number、string、string | HIT |
| 3 | positive | GET | /posts?userId=1 | 無 | 200 | 清單，10 筆；id 為 1 至 10；userId 均為 1 | HIT |
| 4 | positive | GET | /posts/1/comments | 無 | 200 | 清單，5 筆；postId 均為 1；欄位為 postId、id、name、email、body | HIT |
| 5 | positive | POST | /posts | `{"title":"foo","body":"bar","userId":1}` | 201 | `{"title":"foo","body":"bar","userId":1,"id":101}`；另帶 `Location: https://jsonplaceholder.typicode.com/posts/101` 標頭 | DYNAMIC |
| 6 | positive | PUT | /posts/1 | `{"id":1,"title":"t","body":"b","userId":1}` | 200 | `{"id":1,"title":"t","body":"b","userId":1}` | DYNAMIC |
| 7 | positive | PATCH | /posts/1 | `{"title":"patched"}` | 200 | title 變更為 `patched`；userId、id、body 維持原值 | DYNAMIC |
| 8 | positive | DELETE | /posts/1 | 無 | 200 | `{}` | DYNAMIC |
| 9 | boundary | GET | /posts/100 | 無 | 200 | 物件；id 為 100，userId 為 10 | HIT |
| 10 | boundary | GET | /posts/0 | 無 | 404 | `{}` | HIT |
| 11 | boundary | GET | /posts/101 | 無 | 404 | `{}` | HIT |
| 12 | boundary | GET | /posts/-1 | 無 | 404 | `{}` | HIT |
| 13 | boundary | GET | /posts/abc | 無 | 404 | `{}` | HIT |
| 14 | negative | GET | /not-a-real-path | 無 | 404 | `{}` | MISS |
| 15 | negative | GET | /posts?userId=999 | 無 | 200 | 空清單 `[]` | HIT |
| 16 | negative | POST | /posts | `{}` | 201 | `{"id":101}`；另帶指向 `/posts/101` 之 `Location` 標頭 | DYNAMIC |
| 17 | negative | PUT | /posts/101 | `{"title":"x"}` | 404 | `{}` | DYNAMIC |
| 18 | negative | DELETE | /posts/101 | 無 | 200 | `{}` | DYNAMIC |
| 19 | repeat | GET | /posts/1 | 無 | 200 | 與 #2 相同（長度同為 292 字元，內容相同） | HIT |
| 20 | repeat | DELETE | /posts/1 | 無 | 200 | `{}`，與 #8 相同 | DYNAMIC |

表內之 JSON 以單行呈現；實際回應帶有換行及兩格縮排。

`GET /posts/1` 之實際內容如下：

```json
{
  "userId": 1,
  "id": 1,
  "title": "sunt aut facere repellat provident occaecati excepturi optio reprehenderit",
  "body": "quia et suscipit\nsuscipit recusandae consequuntur expedita et cum\nreprehenderit molestiae ut ut quas totam\nnostrum rerum est autem sunt rem eveniet architecto"
}
```

### 觀察結論

1. 讀取：`/posts` 共 100 筆，有效 id 為 1 至 100；單筆資料之欄位為 userId、id（數字）及 title、body（字串）。
2. 邊界：id 為 0、101、-1、abc 時，均回應 404 與 `{}`，且未含錯誤訊息欄位。
3. 不存在之路徑回應 404 與 `{}`；篩選無符合資料時回應 200 與空清單，並非錯誤。
4. 新增：POST 回應 201，回傳送出之內容並附加 `id: 101`，且帶有 `Location` 標頭。
5. **被測對象不驗證輸入**：POST 送出空白物件 `{}` 時，仍回應 201 與 `{"id":101}`。
6. **被測對象不保存寫入結果**：#8 刪除 `/posts/1` 後，#19 仍可取得 `/posts/1`（200）；兩次 POST 均取得 id 101。
7. **對不存在之 id，PUT 與 DELETE 之行為不一致**：`PUT /posts/101` 回應 404，`DELETE /posts/101` 回應 200。
8. 同一 DELETE 請求送出兩次（#8、#20），結果相同：200 與 `{}`。
9. 快取：GET 請求多為 `HIT`（由 Cloudflare 快取提供）；POST、PUT、PATCH、DELETE 均為 `DYNAMIC`（未經快取，由來源伺服器回應）。

### 限制

- **回應時間不予採用**。所量測之耗時介於 50 毫秒至 29,258 毫秒之間，惟量測時頁面處於背景狀態，計時不具參考價值，故本文件不列示各請求之耗時。
- 各請求僅送出 1 次（#19、#20 為刻意重複者），未驗證結果於多次執行間是否穩定。
- 用戶端為瀏覽器之 `fetch`，而非 Python requests。
- 第 7 點所述之 `PUT /posts/101` 回應 404，於本次觀察僅出現 1 次。

上列限制之後續處理情形，見本文件之「文件狀態」一節。
