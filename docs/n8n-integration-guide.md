# Crawlab + n8n 整合指南

## 專案概覽

### 現有爬蟲模組 (23 個)

| 類別 | 模組名稱 | 功能說明 |
|------|----------|----------|
| **資料爬取** | Data-Court_Auction | 法拍屋資料爬取 |
| | Data-Insurance | 保險資料查詢 |
| | Data-Insurance_inc | 保險公司資料查詢 |
| | Data-Judicial_139 | 司法院 139 查詢 |
| | Data-Judicial_146 | 司法院 146 查詢 |
| | Data-Judicial_cdbc3 | 司法院消債查詢 |
| | Data-Judicial_fam | 司法院家事查詢 |
| | Data-Land_Parcel_Section | 地籍資料查詢 |
| | Data-Legal_Insur | 法定保險資料查詢 |
| | Data-LicensePenalty | 證照處分查詢 |
| | Data-TaxRefund | 退稅查詢 |
| | Data-TaxReturn | 綜合所得稅申報查詢 |
| | Data-Tfasc | 金融聯合徵信中心查詢 |
| **HR 系統** | HR-EMP | 員工資料同步 |
| | HR-EMP_Clockin | 打卡資料同步 |
| | HR-Emp_Salary | 薪資資料同步 |
| | HR-EmpLeavetb | 請假資料同步 |
| | HR-HAMS | HAMS 系統整合 |
| | HR-HROrgInfo | 組織資料同步 |
| | HR-HRUserInfo | 使用者資料同步 |
| | HR-INS_JudicialInquiryRequests | 司法查詢請求處理 |
| | HR-Insur_Amount | 保險金額檢查 |
| **外部整合** | OC-GoogleMap | Google Maps 資料同步 |

### 共用模組

| 模組 | 說明 |
|------|------|
| `common/logger.py` | 統一 Log 模組 |

---

## 架構設計

### 方案一：n8n 直接呼叫 Python 腳本 (推薦)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   n8n       │────▶│   Python    │────▶│  Database   │
│  Workflow   │     │  Crawlers   │     │  / API      │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       │                   ▼
       │            ┌─────────────┐
       │            │    Logs     │
       │            │  (JSON)     │
       └───────────▶└─────────────┘
```

**優點：**
- 簡單直接
- 不需修改現有程式碼
- 可直接讀取 Log 檔案

### 方案二：n8n + API Gateway

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   n8n       │────▶│   FastAPI   │────▶│   Python    │
│  Workflow   │     │   Gateway   │     │  Crawlers   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│  Webhook    │     │    Logs     │
│  Callback   │     │  + Status   │
└─────────────┘     └─────────────┘
```

**優點：**
- 更好的錯誤處理
- 即時狀態回報
- 可擴展性高

---

## 實作步驟

### 第一階段：基礎整合

#### 1.1 建立執行腳本

建立 `run_crawler.py` 作為 n8n 呼叫的入口：

```python
# run_crawler.py
import sys
import json
import importlib
from pathlib import Path

def run_module(module_name: str) -> dict:
    """執行指定的爬蟲模組"""
    result = {
        "module": module_name,
        "success": False,
        "message": "",
        "log_file": ""
    }

    try:
        # 動態載入模組
        module_path = Path(__file__).parent / module_name
        sys.path.insert(0, str(module_path))

        # 載入 main 模組
        main = importlib.import_module("main")

        # 執行
        success = main.run()

        result["success"] = success
        result["message"] = "執行完成" if success else "執行失敗"
        result["log_file"] = f"logs/{module_name}.log"

    except Exception as e:
        result["message"] = str(e)

    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "請指定模組名稱"}))
        sys.exit(1)

    module_name = sys.argv[1]
    result = run_module(module_name)
    print(json.dumps(result, ensure_ascii=False))
```

#### 1.2 n8n Execute Command Node 設定

```json
{
  "command": "python",
  "arguments": "D:\\Crawlab\\run_crawler.py {{ $json.module_name }}"
}
```

#### 1.3 n8n Workflow 範例

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Schedule   │───▶│   Execute    │───▶│    Check     │
│   Trigger    │    │   Command    │    │    Result    │
│  (每日 8:00) │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                           ┌───────────────────┼───────────────────┐
                           ▼                   ▼                   ▼
                    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
                    │   Success    │    │    Fail      │    │    Log       │
                    │   通知       │    │    告警      │    │    儲存      │
                    └──────────────┘    └──────────────┘    └──────────────┘
```

---

### 第二階段：API Gateway (進階)

#### 2.1 建立 FastAPI Server

```python
# api_gateway.py
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional
import subprocess
import json
import uuid
from datetime import datetime

app = FastAPI(title="Crawlab API Gateway")

# 任務狀態儲存
tasks = {}

class TaskRequest(BaseModel):
    module: str
    callback_url: Optional[str] = None

class TaskStatus(BaseModel):
    task_id: str
    module: str
    status: str  # pending, running, success, failed
    start_time: str
    end_time: Optional[str] = None
    result: Optional[dict] = None

@app.post("/api/v1/tasks")
async def create_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """建立新的爬蟲任務"""
    task_id = str(uuid.uuid4())

    tasks[task_id] = TaskStatus(
        task_id=task_id,
        module=request.module,
        status="pending",
        start_time=datetime.now().isoformat()
    )

    # 背景執行
    background_tasks.add_task(
        run_crawler_task,
        task_id,
        request.module,
        request.callback_url
    )

    return {"task_id": task_id, "status": "pending"}

@app.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查詢任務狀態"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

@app.get("/api/v1/modules")
async def list_modules():
    """列出所有可用模組"""
    return {
        "modules": [
            "Data-Court_Auction",
            "Data-Insurance",
            "Data-Insurance_inc",
            "Data-Judicial_139",
            "Data-Judicial_146",
            "Data-Judicial_cdbc3",
            "Data-Judicial_fam",
            "Data-Land_Parcel_Section",
            "Data-Legal_Insur",
            "Data-LicensePenalty",
            "Data-TaxRefund",
            "Data-TaxReturn",
            "Data-Tfasc",
            "HR-EMP",
            "HR-EMP_Clockin",
            "HR-Emp_Salary",
            "HR-EmpLeavetb",
            "HR-HAMS",
            "HR-HROrgInfo",
            "HR-HRUserInfo",
            "HR-INS_JudicialInquiryRequests",
            "HR-Insur_Amount",
            "OC-GoogleMap"
        ]
    }

async def run_crawler_task(task_id: str, module: str, callback_url: str = None):
    """背景執行爬蟲任務"""
    tasks[task_id].status = "running"

    try:
        result = subprocess.run(
            ["python", f"D:\\Crawlab\\run_crawler.py", module],
            capture_output=True,
            text=True,
            timeout=3600  # 1 小時超時
        )

        output = json.loads(result.stdout) if result.stdout else {}

        tasks[task_id].status = "success" if output.get("success") else "failed"
        tasks[task_id].result = output
        tasks[task_id].end_time = datetime.now().isoformat()

        # 回呼通知
        if callback_url:
            import requests
            requests.post(callback_url, json=tasks[task_id].dict())

    except Exception as e:
        tasks[task_id].status = "failed"
        tasks[task_id].result = {"error": str(e)}
        tasks[task_id].end_time = datetime.now().isoformat()
```

#### 2.2 啟動 API Server

```bash
# 安裝依賴
pip install fastapi uvicorn

# 啟動服務
uvicorn api_gateway:app --host 0.0.0.0 --port 8000
```

#### 2.3 n8n HTTP Request Node 設定

**建立任務：**
```json
{
  "method": "POST",
  "url": "http://localhost:8000/api/v1/tasks",
  "body": {
    "module": "{{ $json.module_name }}",
    "callback_url": "{{ $json.webhook_url }}"
  }
}
```

**查詢狀態：**
```json
{
  "method": "GET",
  "url": "http://localhost:8000/api/v1/tasks/{{ $json.task_id }}"
}
```

---

### 第三階段：監控與告警

#### 3.1 Log 監控結構

現有 Logger 已支援 JSON 格式輸出，可直接用於監控：

```json
{
  "timestamp": "2024-01-15T08:30:00",
  "level": "INFO",
  "module": "Data-TaxReturn",
  "operation": "query_tax",
  "message": "處理完成",
  "stats": {
    "total_processed": 100,
    "total_success": 98,
    "total_failed": 2
  }
}
```

#### 3.2 n8n 告警 Workflow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Read Log   │───▶│   Parse      │───▶│   Filter     │
│   File       │    │   JSON       │    │   Errors     │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │   Send       │
                                        │   Alert      │
                                        │  (Slack/     │
                                        │   Email)     │
                                        └──────────────┘
```

#### 3.3 Slack 告警範例

```json
{
  "channel": "#crawlab-alerts",
  "text": "⚠️ 爬蟲執行失敗",
  "attachments": [
    {
      "color": "danger",
      "fields": [
        {"title": "模組", "value": "{{ $json.module }}", "short": true},
        {"title": "時間", "value": "{{ $json.timestamp }}", "short": true},
        {"title": "錯誤", "value": "{{ $json.error }}"}
      ]
    }
  ]
}
```

---

## 排程建議

### 依據模組特性排程

| 模組類別 | 建議排程 | 備註 |
|----------|----------|------|
| Data-* (資料爬取) | 每日 02:00-06:00 | 離峰時段執行 |
| HR-* (HR 同步) | 每日 07:00, 19:00 | 上下班前同步 |
| OC-GoogleMap | 每日 08:00 | 營業時間前更新 |

### n8n Cron 設定範例

```
# 每日 02:00 執行資料爬取
0 2 * * *

# 每日 07:00 和 19:00 執行 HR 同步
0 7,19 * * *

# 每週一 08:00 執行 Google Maps 同步
0 8 * * 1
```

---

## 錯誤處理策略

### 重試機制

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Execute    │───▶│   Check      │───▶│   Retry?     │
│   Crawler    │    │   Result     │    │   < 3 次     │
└──────────────┘    └──────────────┘    └──────────────┘
                                               │
                           ┌───────────────────┤
                           ▼                   ▼
                    ┌──────────────┐    ┌──────────────┐
                    │    Yes       │    │    No        │
                    │   Wait 5min  │    │   Alert      │
                    │   Retry      │    │              │
                    └──────────────┘    └──────────────┘
```

### n8n Error Workflow

1. 捕獲錯誤
2. 記錄到資料庫
3. 發送告警
4. 決定是否重試

---

## 部署清單

### 環境需求

- [ ] Python 3.10+
- [ ] n8n (Docker 或本地安裝)
- [ ] 資料庫連線設定 (各模組 config.py)
- [ ] API 憑證設定

### 檔案清單

```
D:\Crawlab\
├── common/
│   ├── __init__.py
│   └── logger.py          # 統一 Log 模組
├── run_crawler.py          # [待建立] n8n 呼叫入口
├── api_gateway.py          # [待建立] API Gateway
├── requirements.txt        # [待建立] Python 依賴
├── docs/
│   └── n8n-integration-guide.md  # 本文件
├── Data-*/                 # 資料爬取模組
├── HR-*/                   # HR 同步模組
└── OC-*/                   # 外部整合模組
```

### 下一步行動

1. **建立 `run_crawler.py`** - 統一執行入口
2. **建立 `requirements.txt`** - 整合所有依賴
3. **設定 n8n** - 建立基本 Workflow
4. **測試執行** - 驗證單一模組
5. **建立監控** - 設定告警通知
6. **(選用) 建立 API Gateway** - 進階整合

---

## 附錄

### A. 常用 n8n Nodes

| Node 類型 | 用途 |
|-----------|------|
| Schedule Trigger | 定時觸發 |
| Execute Command | 執行 Python 腳本 |
| HTTP Request | 呼叫 API |
| IF | 條件判斷 |
| Slack / Email | 通知 |
| Read Binary File | 讀取 Log 檔案 |

### B. Logger API 參考

```python
from common.logger import get_logger

logger = get_logger('Module-Name')

# 基本操作
logger.task_start("任務名稱")
logger.task_end(success=True)

# 進度追蹤
logger.log_progress(current, total, "step_name")

# HTTP 追蹤
logger.log_request("POST", url, headers, data)
logger.log_response(status_code, headers, body, elapsed)

# 資料庫追蹤
logger.log_db_connect(server, database, username)
logger.log_db_operation("INSERT", database, table, count)

# 錯誤處理
logger.log_exception(exception, "錯誤說明")

# 統計
logger.log_stats({"key": value})
```

### C. 聯絡資訊

如有問題，請聯繫開發團隊。
