# API 自動化測試作品集

[![API tests](https://github.com/alaakita-code/api-test-portfolio/actions/workflows/tests.yml/badge.svg)](https://github.com/alaakita-code/api-test-portfolio/actions/workflows/tests.yml)

以 pytest 與 requests 撰寫的 API 自動化測試，被測對象為 [JSONPlaceholder](https://jsonplaceholder.typicode.com) 的 `/posts` 資源。每一個預期值都可追溯到對實際 API 的觀察紀錄。

English: [README.md](README.md)

## 專案目的

本專案呈現 API 測試的設計與自動化方式：

- 先設計、後實作。每個測試對應[測試計畫](docs/test_plan.md)中的一個案例。
- 預期值以證據為依據，取自[實際回應的紀錄](docs/api_observed.md)，而非假設。
- 驗證內容不限於狀態碼，包含欄位、資料型別、內容與標頭。
- 已知限制如實記載。

## 測試涵蓋範圍

共 25 個測試：24 個測試案例與 1 個冒煙測試。

| 類別 | 數量 | 驗證內容 |
|---|---|---|
| 正向 | 9 | 正確的請求回傳預期的狀態碼、欄位、型別與內容 |
| 邊界 | 6 | 有效範圍（1 至 100）邊緣與範圍外的 id |
| 負向 | 5 | 不存在的路徑、無符合資料的篩選、空的請求內容、不存在的 id |
| 錯誤處理 | 2 | API 緩慢或無回應時，測試明確失敗而非停滯 |
| 重複請求 | 2 | 重複送出相同請求時結果一致 |
| 冒煙 | 1 | 環境與連線可用 |

## 技術堆疊

| 工具 | 版本 | 用途 |
|---|---|---|
| Python | 3.11、3.13 | 程式語言 |
| pytest | 9.1.1 | 測試框架 |
| requests | 2.34.2 | HTTP 用戶端 |
| pytest-html | 4.2.0 | HTML 報告 |
| GitHub Actions | - | 持續整合 |

## 快速開始

指令以 Windows 為例，於專案根目錄執行。

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest
```

全部通過時，最後一行的格式如下：

```
25 passed in 25.00s
```

不需要帳號、金鑰或資料庫。

## 測試報告

- **本機**：每次執行產生 `reports/report.html`，為可離線開啟的單一檔案。
- **CI**：每次工作流程執行會為各 Python 版本發布一份報告，可於 [Actions 頁面](https://github.com/alaakita-code/api-test-portfolio/actions)的 Artifacts 區塊下載。

## 已知限制

- 被測對象的寫入操作只回傳模擬結果、不保存資料，無法驗證寫入後查詢的一致性。
- 被測對象沒有驗證機制，也不驗證輸入，權限與輸入驗證不在測試範圍內。
- 對不存在的 id，PUT 回 404、DELETE 回 200；測試如實記錄此行為。
- GET 回應由 CDN 快取提供，重複請求測試驗證到的可能是快取的一致性。
- 測試依賴第三方服務；服務中斷造成的失敗屬於環境問題。
- 未包含併發與負載測試。

測試通過表示涵蓋範圍內的行為符合紀錄的預期，不代表被測對象沒有缺陷。

## 文件

- [使用手冊](docs/USAGE.zh-TW.md)：安裝、執行、設定、失敗分析流程、維護與程式碼導讀
- [測試計畫](docs/test_plan.md)：範圍、優先級、測試案例與依據
- [API 探索筆記](docs/api_notes.md)：探索摘要與已知限制
