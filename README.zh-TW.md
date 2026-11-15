# API 自動化測試作品集

[![API tests](https://github.com/alaakita-code/api-test-portfolio/actions/workflows/tests.yml/badge.svg)](https://github.com/alaakita-code/api-test-portfolio/actions/workflows/tests.yml)
[![AlaAkita Gate](https://github.com/alaakita-code/api-test-portfolio/actions/workflows/alaakita-gate.yml/badge.svg)](https://github.com/alaakita-code/api-test-portfolio/actions/workflows/alaakita-gate.yml)

本專案以 pytest 與 requests 撰寫 API 自動化測試，被測對象為 [JSONPlaceholder](https://jsonplaceholder.typicode.com) 之 `/posts` 資源。各項預期值皆可追溯至對實際 API 之觀察紀錄。

English: [README.md](README.md)

## 專案目的

本專案呈現 API 測試之設計與自動化方法：

- 先設計、後實作。每個測試皆對應[測試計畫](docs/test_plan.md)所列之案例。
- 預期值以證據為依據，取自[實際回應之紀錄](docs/api_observed.md)，而非出於假設。
- 驗證內容不以狀態碼為限，並涵蓋欄位、資料型別、內容與標頭。
- 已知限制均如實記載。

## 測試涵蓋範圍

共 25 個測試，包含 24 個測試案例及 1 個冒煙測試。

| 類別 | 數量 | 驗證內容 |
|---|---|---|
| 正向 | 9 | 正確之請求回傳預期之狀態碼、欄位、型別與內容 |
| 邊界 | 6 | 有效範圍（1 至 100）之邊界及範圍外之 id |
| 負向 | 5 | 不存在之路徑、無符合資料之篩選、空白之請求內容、不存在之 id |
| 錯誤處理 | 2 | API 回應緩慢或無回應時，測試明確失敗而非停滯 |
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

指令以 Windows PowerShell 為例，於專案根目錄執行。

```
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
```

全部通過時，最後一行之格式如下：

```
25 passed in 25.00s
```

本專案無須帳號、金鑰或資料庫。

## 測試報告

- **本機**：每次執行產生 `reports/report.html`，為可離線開啟之單一檔案。
- **CI**：工作流程於每次推送、每次合併請求及每週排程時執行，並為各 Python 版本發布一份報告，可於 [Actions 頁面](https://github.com/alaakita-code/api-test-portfolio/actions)之 Artifacts 區塊下載。
- **合併檢查**：`main` 僅接受經合併請求（pull request）之變更。合併請求須通過兩個 Python 版本之 API 測試及 AlaAkita 擋關，始得合併；擋關會確認各項變更確實發生於 `.alaakita/expect.txt` 所列之位置。

報告預設僅保留版本資訊，不含執行環境之其他細節。

## 已知限制

- 被測對象之寫入操作僅回傳模擬結果而不保存資料，故無法驗證寫入後查詢之一致性。
- 被測對象未設驗證機制，亦不驗證輸入，故權限與輸入驗證不在測試範圍內。
- 對不存在之 id，PUT 回應 404，DELETE 回應 200；測試如實記錄此行為。
- GET 回應由 CDN 快取提供，故重複請求測試所驗證者可能為快取之一致性。
- 測試依賴第三方服務；因服務中斷所致之失敗屬環境問題。
- 未包含併發與負載測試。

測試通過表示涵蓋範圍內之行為符合紀錄所載之預期，不代表被測對象無缺陷。

## 文件

- [使用手冊](docs/USAGE.zh-TW.md)：安裝、執行、設定、失敗分析流程、維護、持續整合與程式碼導讀
- [測試計畫](docs/test_plan.md)：範圍、優先級、測試案例及其依據
- [API 探索筆記](docs/api_notes.md)：探索摘要與已知限制
