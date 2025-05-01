# automationQ 自動化 Alpha 模型測試與提交工具

這是一個幫助您與 [WorldQuant BRAIN](https://www.worldquant.com/brain/) 平台互動的自動化工具，能夠批次提交 Alpha 表達式、模擬績效，並選擇是否送出高表現策略。

## 功能簡介

- 自動讀取 `alpha_list.txt` 裡的 Alpha 表達式
- 呼叫 BRAIN API 進行模擬與提交
- 將結果儲存在 `results.json`
- 自動處理憑證、錯誤提示與記錄日誌

## 專案檔案說明

| 檔案名稱           | 用途                       |
|--------------------|----------------------------|
| `main.py`          | 主程式，進行模擬與提交     |
| `alpha_list.txt`   | 要測試的 Alpha 表達式清單 |
| `credentials.txt`  | 存放登入帳號密碼的 JSON 檔 |
| `results.json`     | 儲存模擬與提交結果         |
| `requirements.txt` | Python 套件需求清單        |

## 如何執行程式

### 步驟一：準備環境

1. 安裝 Python（建議 3.8 以上）
2. 建立虛擬環境（可選）：

   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows 請改用 venv\Scripts\activate

3. 安裝套件：

   ```bash
   pip install -r requirements.txt


### 步驟二：建立必要檔案

#### credentials.txt

請建立一個 `credentials.txt`，內容格式如下（JSON 陣列）：

```json
["your_username", "your_password"]


請將 `your_username` 與 `your_password` 替換為您在 WorldQuant BRAIN 的帳號密碼。

#### alpha_list.txt

請在這個檔案內輸入您要測試的 Alpha 表達式，例如：


rank(ts_delta(close, 5))
-ts_rank(volume, 10)
log(divide(close, ts_mean(close, 5)))


### 步驟三：執行主程式

在 Terminal 執行：

```bash
python main.py


系統將會：

- 登入 WorldQuant BRAIN
- 逐一提交每個 Alpha 進行模擬
- 儲存結果到 `results.json`
- 若有任何錯誤或缺檔，會在 Terminal 顯示提示

## 小提醒

- 若 `alpha_list.txt` 不存在，程式會自動產生範例內容並停止執行，請修改完畢後再重新執行。
- 所有結果會存在 `results.json`，可自行分析或後續使用。
- 若需要提交 Alpha（而非僅模擬），請進一步修改程式碼中是否啟用 submit 功能。

