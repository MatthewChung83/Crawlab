# Crawlab + n8n 部署操作指南

## 目錄
1. [環境準備](#1-環境準備)
2. [專案部署到 Server](#2-專案部署到-server)
3. [n8n 安裝與設定](#3-n8n-安裝與設定)
4. [建立 Workflow](#4-建立-workflow)
5. [設定排程](#5-設定排程)
6. [監控與告警](#6-監控與告警)
7. [常見問題](#7-常見問題)

---

## 1. 環境準備

### 1.1 Server 需求

| 項目 | 最低需求 | 建議配置 |
|------|----------|----------|
| OS | Windows Server 2019 / Ubuntu 20.04 | Windows Server 2022 / Ubuntu 22.04 |
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 50 GB | 100 GB |
| Python | 3.11 | 3.11 |
| Node.js | 18.x | 20.x (for n8n) |

### 1.2 安裝 Python 3.11

**Windows Server:**
```powershell
# 下載 Python 3.11
# https://www.python.org/downloads/release/python-3118/

# 安裝時勾選:
# ✅ Add Python to PATH
# ✅ Install pip

# 驗證安裝
python --version
# Python 3.11.8
```

**Ubuntu:**
```bash
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11 python3.11-venv python3.11-dev
```

### 1.3 安裝 Node.js (for n8n)

**Windows Server:**
```powershell
# 下載 Node.js 20 LTS
# https://nodejs.org/

# 驗證安裝
node --version
npm --version
```

**Ubuntu:**
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

---

## 2. 專案部署到 Server

### 2.1 複製專案

**方式一：Git Clone**
```bash
cd /opt  # Linux
cd D:\   # Windows

git clone https://github.com/MatthewChung83/Crawlab.git
cd Crawlab
```

**方式二：手動複製**
```
將整個 Crawlab 資料夾複製到 Server
```

### 2.2 建立虛擬環境

**Windows:**
```powershell
cd D:\Crawlab

# 建立虛擬環境
python -m venv venv

# 啟用虛擬環境
.\venv\Scripts\Activate.ps1

# 如果遇到執行原則問題
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Linux:**
```bash
cd /opt/Crawlab

python3.11 -m venv venv
source venv/bin/activate
```

### 2.3 安裝依賴

```bash
# 確保在虛擬環境中
pip install --upgrade pip
pip install -r requirements.txt

# 安裝 Playwright 瀏覽器
playwright install chromium
playwright install-deps  # Linux only
```

### 2.4 調整路徑設定

需要修改以下檔案的路徑：

**Data-Tfasc/config.py** (Linux 路徑改為 Windows):
```python
# 原本
'output_dir': '/tmp/WBT',

# Windows 改為
'output_dir': 'D:\\Crawlab\\Data-Tfasc\\output',
```

**使用 ChromeDriver 的模組** (如果使用 Selenium):
```python
# 改為相對路徑或環境變數
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
'Drvfile': os.path.join(BASE_DIR, 'drivers', 'chromedriver.exe'),
```

### 2.5 測試專案

```bash
# 測試模組載入
python test_load.py

# 測試單一模組執行
python run_crawler.py --list
python run_crawler.py Data-Court_Auction
```

### 2.6 建立執行腳本

**Windows: run_module.bat**
```batch
@echo off
cd /d D:\Crawlab
call venv\Scripts\activate.bat
python run_crawler.py %1
```

**Linux: run_module.sh**
```bash
#!/bin/bash
cd /opt/Crawlab
source venv/bin/activate
python run_crawler.py "$1"
```

---

## 3. n8n 安裝與設定

### 3.1 安裝 n8n

**方式一：npm 全域安裝**
```bash
npm install -g n8n
```

**方式二：Docker (推薦)**
```bash
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -v D:\Crawlab:/crawlab \
  -e N8N_BASIC_AUTH_ACTIVE=true \
  -e N8N_BASIC_AUTH_USER=admin \
  -e N8N_BASIC_AUTH_PASSWORD=YourPassword123 \
  n8nio/n8n
```

**方式三：Windows Service**
```powershell
# 使用 pm2 管理
npm install -g pm2
pm2 start n8n
pm2 save
pm2 startup
```

### 3.2 啟動 n8n

```bash
# 直接啟動
n8n start

# 或背景執行
n8n start &

# 訪問 Web UI
# http://localhost:5678
```

### 3.3 n8n 環境變數設定

建立 `.env` 檔案或設定環境變數：

```env
# n8n 設定
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=YourSecurePassword

# 時區
GENERIC_TIMEZONE=Asia/Taipei
TZ=Asia/Taipei

# 執行模式
N8N_LOG_LEVEL=info
EXECUTIONS_DATA_SAVE_ON_ERROR=all
EXECUTIONS_DATA_SAVE_ON_SUCCESS=all

# Webhook URL (如果需要外部訪問)
WEBHOOK_URL=http://your-server-ip:5678/
```

---

## 4. 建立 Workflow

### 4.1 基本架構

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Schedule   │───▶│  Execute    │───▶│   Check     │───▶│   Notify    │
│  Trigger    │    │  Command    │    │   Result    │    │  (Slack/    │
│             │    │             │    │             │    │   Email)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 4.2 建立新 Workflow

1. 開啟 n8n Web UI: `http://localhost:5678`
2. 點擊 **「+ New Workflow」**
3. 命名: `Crawlab - Daily Execution`

### 4.3 新增 Schedule Trigger

1. 點擊 **「+」** 新增節點
2. 搜尋 **「Schedule Trigger」**
3. 設定:
   - **Trigger Times**: Custom (Cron)
   - **Cron Expression**: `0 2 * * *` (每日 02:00)

```
常用 Cron 表達式:
0 2 * * *     每日 02:00
0 7,19 * * *  每日 07:00 和 19:00
0 */4 * * *   每 4 小時
0 8 * * 1     每週一 08:00
```

### 4.4 新增 Execute Command 節點

1. 點擊 **「+」** 新增節點
2. 搜尋 **「Execute Command」**
3. 設定:

**Windows:**
```
Command: D:\Crawlab\venv\Scripts\python.exe
Arguments: D:\Crawlab\run_crawler.py Data-Court_Auction
```

**Linux:**
```
Command: /opt/Crawlab/venv/bin/python
Arguments: /opt/Crawlab/run_crawler.py Data-Court_Auction
```

**或使用批次檔:**
```
Command: D:\Crawlab\run_module.bat
Arguments: Data-Court_Auction
```

### 4.5 新增 IF 節點檢查結果

1. 新增 **「IF」** 節點
2. 設定條件:
   - **Value 1**: `{{ $json.stdout }}`
   - **Operation**: Contains
   - **Value 2**: `"success": true`

### 4.6 新增通知節點

**成功通知 (Slack):**
```json
{
  "channel": "#crawlab-alerts",
  "text": "✅ 爬蟲執行成功",
  "attachments": [
    {
      "color": "good",
      "fields": [
        {"title": "模組", "value": "Data-Court_Auction", "short": true},
        {"title": "時間", "value": "{{ $now.format('YYYY-MM-DD HH:mm:ss') }}", "short": true}
      ]
    }
  ]
}
```

**失敗告警 (Slack):**
```json
{
  "channel": "#crawlab-alerts",
  "text": "❌ 爬蟲執行失敗",
  "attachments": [
    {
      "color": "danger",
      "fields": [
        {"title": "模組", "value": "Data-Court_Auction", "short": true},
        {"title": "錯誤", "value": "{{ $json.stderr }}", "short": false}
      ]
    }
  ]
}
```

### 4.7 完整 Workflow JSON 範例

可直接匯入 n8n:

```json
{
  "name": "Crawlab - Data-Court_Auction",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "triggerAtHour": 2
            }
          ]
        }
      },
      "name": "Schedule Trigger",
      "type": "n8n-nodes-base.scheduleTrigger",
      "position": [250, 300]
    },
    {
      "parameters": {
        "command": "D:\\Crawlab\\venv\\Scripts\\python.exe",
        "arguments": "D:\\Crawlab\\run_crawler.py Data-Court_Auction"
      },
      "name": "Execute Crawler",
      "type": "n8n-nodes-base.executeCommand",
      "position": [450, 300]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.stdout }}",
              "operation": "contains",
              "value2": "\"success\": true"
            }
          ]
        }
      },
      "name": "Check Result",
      "type": "n8n-nodes-base.if",
      "position": [650, 300]
    }
  ],
  "connections": {
    "Schedule Trigger": {
      "main": [[{"node": "Execute Crawler", "type": "main", "index": 0}]]
    },
    "Execute Crawler": {
      "main": [[{"node": "Check Result", "type": "main", "index": 0}]]
    }
  }
}
```

---

## 5. 設定排程

### 5.1 建議排程表

| 模組類別 | 模組名稱 | 排程時間 | Cron |
|----------|----------|----------|------|
| **資料爬取** | Data-Court_Auction | 每日 02:00 | `0 2 * * *` |
| | Data-Judicial_* (4個) | 每日 02:30 | `30 2 * * *` |
| | Data-Legal_Insur | 每日 03:00 | `0 3 * * *` |
| | Data-TaxReturn | 每日 03:30 | `30 3 * * *` |
| | Data-TaxRefund | 每日 04:00 | `0 4 * * *` |
| | Data-Insurance | 每日 04:30 | `30 4 * * *` |
| | Data-Insurance_inc | 每日 05:00 | `0 5 * * *` |
| | Data-Land_Parcel_Section | 每日 05:30 | `30 5 * * *` |
| | Data-LicensePenalty | 每日 06:00 | `0 6 * * *` |
| | Data-Tfasc | 每日 06:30 | `30 6 * * *` |
| **HR 同步** | HR-EMP | 每日 07:00, 19:00 | `0 7,19 * * *` |
| | HR-EMP_Clockin | 每日 07:10, 19:10 | `10 7,19 * * *` |
| | HR-Emp_Salary | 每日 07:20 | `20 7 * * *` |
| | HR-EmpLeavetb | 每日 07:30 | `30 7 * * *` |
| | HR-HRUserInfo | 每日 07:40 | `40 7 * * *` |
| | HR-HROrgInfo | 每日 07:50 | `50 7 * * *` |
| | HR-HAMS | 每日 08:00 | `0 8 * * *` |
| | HR-INS_JudicialInquiryRequests | 每日 08:30 | `30 8 * * *` |
| | HR-Insur_Amount | 每日 09:00 | `0 9 * * *` |
| **外部整合** | OC-GoogleMap | 每週一 08:00 | `0 8 * * 1` |

### 5.2 批次執行 Workflow

建立一個主 Workflow 依序執行多個模組:

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
│ Module1 │──▶│ Module2 │──▶│ Module3 │──▶│ Summary │
└─────────┘   └─────────┘   └─────────┘   └─────────┘
```

---

## 6. 監控與告警

### 6.1 設定 Slack Webhook

1. 前往 Slack App 設定: https://api.slack.com/apps
2. 建立新 App → Incoming Webhooks → 啟用
3. 複製 Webhook URL

在 n8n 中設定:
1. 新增 **Slack** 節點
2. 設定 Webhook URL

### 6.2 設定 Email 通知

1. 新增 **Send Email** 節點
2. 設定 SMTP:
   - Host: smtp.gmail.com
   - Port: 587
   - User: your-email@gmail.com
   - Password: App Password

### 6.3 Log 監控

建立 Log 檢查 Workflow:

```
Schedule (每小時) → Read Log File → Check for Errors → Alert if Found
```

### 6.4 健康檢查

```bash
# 建立健康檢查腳本 health_check.py
python -c "
import sys
sys.path.insert(0, 'D:/Crawlab')
from common.logger import get_logger
logger = get_logger('HealthCheck')
logger.info('Health check passed')
print('{\"status\": \"healthy\"}')
"
```

---

## 7. 常見問題

### Q1: Execute Command 找不到 Python

**問題:** `'python' is not recognized`

**解決:**
```
# 使用完整路徑
Command: D:\Crawlab\venv\Scripts\python.exe
```

### Q2: 模組 Import 失敗

**問題:** `ModuleNotFoundError`

**解決:**
```bash
# 確保在虛擬環境中安裝所有依賴
cd D:\Crawlab
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Q3: Playwright 瀏覽器找不到

**問題:** `Executable doesn't exist`

**解決:**
```bash
# 安裝 Playwright 瀏覽器
.\venv\Scripts\Activate.ps1
playwright install chromium
```

### Q4: 中文亂碼

**問題:** Log 或輸出中文顯示亂碼

**解決:**
```python
# 在 run_crawler.py 開頭加入
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```

### Q5: n8n 執行超時

**問題:** 爬蟲執行時間過長導致超時

**解決:**
在 Execute Command 節點設定:
```
Timeout: 3600 (1小時)
```

### Q6: 權限問題

**問題:** 無法寫入檔案或目錄

**解決:**
```powershell
# Windows - 以系統管理員身份執行
# 或調整資料夾權限

# Linux
sudo chown -R n8n:n8n /opt/Crawlab
chmod -R 755 /opt/Crawlab
```

---

## 附錄

### A. 環境變數清單

```env
# Python
PYTHONPATH=D:\Crawlab
PYTHONIOENCODING=utf-8

# Crawlab
CRAWLAB_HOME=D:\Crawlab
CRAWLAB_LOG_LEVEL=INFO

# ChromeDriver (如果使用 Selenium)
CHROMEDRIVER_PATH=D:\Crawlab\drivers\chromedriver.exe
```

### B. 重要檔案位置

| 檔案 | 位置 | 說明 |
|------|------|------|
| 主程式入口 | `D:\Crawlab\run_crawler.py` | n8n 呼叫此檔案 |
| API Gateway | `D:\Crawlab\api_gateway.py` | REST API (選用) |
| Log 檔案 | `D:\Crawlab\logs\` | 各模組日誌 |
| 設定檔 | `D:\Crawlab\{模組}\config.py` | 各模組設定 |

### C. 快速檢查清單

- [ ] Python 3.11 已安裝
- [ ] 虛擬環境已建立並啟用
- [ ] requirements.txt 已安裝
- [ ] Playwright 瀏覽器已安裝
- [ ] 路徑設定已調整 (Data-Tfasc, ChromeDriver)
- [ ] test_load.py 全部通過
- [ ] n8n 已安裝並啟動
- [ ] Workflow 已建立並測試
- [ ] 通知管道已設定 (Slack/Email)
- [ ] 排程已啟用
