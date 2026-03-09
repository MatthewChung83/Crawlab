# Crawlab + n8n Docker 完整部署指南

## 目錄
1. [系統架構](#1-系統架構)
2. [連線資訊總覽](#2-連線資訊總覽)
3. [Docker 環境設定](#3-docker-環境設定)
4. [Crawlab 容器化](#4-crawlab-容器化)
5. [n8n 與 Crawlab 串接](#5-n8n-與-crawlab-串接)
6. [Workflow 詳細設計](#6-workflow-詳細設計)
7. [Port 與防火牆設定](#7-port-與防火牆設定)

---

## 1. 系統架構

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Host                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │   n8n       │───▶│  Crawlab    │───▶│  Playwright │          │
│  │  Container  │    │  Container  │    │  (內建)     │          │
│  │  Port:5678  │    │  Port:8000  │    │             │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
│         │                  │                                     │
└─────────│──────────────────│─────────────────────────────────────┘
          │                  │
          │     ┌────────────┼────────────────────┐
          │     │            │                    │
          ▼     ▼            ▼                    ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  SQL Server  │  │  SMB Server  │  │  SSH Server  │
    │  10.10.0.94  │  │  10.10.0.93  │  │  10.10.0.66  │
    │  Port:1433   │  │  Port:445    │  │  Port:22     │
    └──────────────┘  └──────────────┘  └──────────────┘
          │
          │     ┌────────────────────────────────────┐
          │     │          外部網站                   │
          │     │  - 司法院 (judicial.gov.tw)        │
          │     │  - 壽險公會 (liaroc.org.tw)        │
          │     │  - 財政部 (etax.nat.gov.tw)        │
          │     │  - 金服中心 (tfasc.com.tw)         │
          │     │  - HR系統 (hr.ucs.tw)              │
          │     └────────────────────────────────────┘
```

---

## 2. 連線資訊總覽

### 2.1 資料庫連線 (SQL Server)

| 伺服器 | Port | 用途 | 使用模組 |
|--------|------|------|----------|
| **10.10.0.94** | **1433** | 主要資料庫 | 幾乎所有模組 |

**資料庫帳號:**

| Database | Username | Password | 使用模組 |
|----------|----------|----------|----------|
| CL_Daily | CLUSER | Ucredit7607 | Data-Court_Auction, Data-Tfasc, OC-GoogleMap |
| UCS_ReportDB | CLUSER | Ucredit7607 | Data-Legal_Insur |
| UCS_ReportDB | FRUSER | 1qaz@WSX | HR-INS_JudicialInquiryRequests |
| CL_Daily | CLUSER | Ucredit7607 | Data-Insurance, Data-Insurance_inc |
| CL_Daily | CLUSER | Ucredit7607 | Data-Judicial_* (4個), Data-Land_Parcel_Section |
| CL_Daily | CLUSER | Ucredit7607 | Data-TaxReturn, Data-TaxRefund, Data-LicensePenalty |
| UCS_HRMS | CLUSER | Ucredit7607 | HR-EMP, HR-EMP_Clockin, HR-Emp_Salary |
| UCS_HRMS | CLUSER | Ucredit7607 | HR-EmpLeavetb, HR-HRUserInfo, HR-HROrgInfo |

### 2.2 SMB 檔案伺服器 (Windows AD)

| 伺服器 | Port | 帳號 | Domain | 使用模組 |
|--------|------|------|--------|----------|
| **10.10.0.93** | **445** (SMB) / **139** (NetBIOS) | sqlsvc | ucs | Data-Legal_Insur |
| **10.10.0.93** | **445** / **139** | sqlsvc | ucs | HR-INS_JudicialInquiryRequests |

**SMB 連線詳細:**
```
伺服器: 10.10.0.93
共享名稱: UCS
帳號: sqlsvc
密碼: Sq1@dmin
Domain: ucs
認證方式: NTLM v2
```

### 2.3 SSH/SCP 伺服器

| 伺服器 | Port | 帳號 | 使用模組 |
|--------|------|------|----------|
| **10.10.0.66** | **22** | uicts | OC-GoogleMap |

**SSH 連線詳細:**
```
伺服器: 10.10.0.66
Port: 22
帳號: uicts
密碼: Ucs@28289788
本地資料夾: /tmp/OCMAP
遠端資料夾: /home/uicts/cash
```

### 2.4 外部 API / 網站

| 類別 | 網站 | Port | 使用模組 |
|------|------|------|----------|
| **司法院** | cdcb3.judicial.gov.tw | 443 | Data-Judicial_cdbc3 |
| | domestic.judicial.gov.tw | 443 | Data-Judicial_fam |
| | www.judicial.gov.tw | 443 | Data-Judicial_139, Data-Judicial_146 |
| | aomp109.judicial.gov.tw | 443 | Data-Court_Auction |
| **壽險公會** | public.liaroc.org.tw | 443 | Data-Insurance, Data-Insurance_inc |
| | insurtech.lia-roc.org.tw | 443 | Data-Legal_Insur |
| **財政部** | etax.nat.gov.tw | 443 | Data-TaxRefund |
| | svc.tax.nat.gov.tw | 443 | Data-TaxReturn |
| **金服中心** | www.tfasc.com.tw | 443 | Data-Tfasc |
| **地政** | ep.land.nat.gov.tw | 443 | Data-Land_Parcel_Section |
| **監理站** | www.mvdis.gov.tw | 443 | Data-LicensePenalty |
| **HR系統** | hr.ucs.tw | 443 | HR-EMP, HR-EMP_Clockin, HR-Emp_Salary |
| | | | HR-EmpLeavetb, HR-HRUserInfo, HR-HROrgInfo |
| | | | HR-HAMS, HR-Insur_Amount |
| **綠界支付** | payment.ecpay.com.tw | 443 | Data-Legal_Insur |
| **SMTP** | 10.10.0.159 | 25 | HR-Insur_Amount (郵件通知) |

### 2.5 模組連線總覽表

| 模組 | DB (1433) | SMB (445) | SSH (22) | 外部網站 (443) |
|------|:---------:|:---------:|:--------:|:--------------:|
| Data-Court_Auction | ✅ 10.10.0.94 | | | ✅ judicial.gov.tw |
| Data-Insurance | ✅ 10.10.0.94 | | | ✅ liaroc.org.tw |
| Data-Insurance_inc | ✅ 10.10.0.94 | | | ✅ liaroc.org.tw |
| Data-Judicial_139 | ✅ 10.10.0.94 | | | ✅ judicial.gov.tw |
| Data-Judicial_146 | ✅ 10.10.0.94 | | | ✅ judicial.gov.tw |
| Data-Judicial_cdbc3 | ✅ 10.10.0.94 | | | ✅ judicial.gov.tw |
| Data-Judicial_fam | ✅ 10.10.0.94 | | | ✅ judicial.gov.tw |
| Data-Land_Parcel_Section | ✅ 10.10.0.94 | | | ✅ land.nat.gov.tw |
| Data-Legal_Insur | ✅ 10.10.0.94 | ✅ 10.10.0.93 | | ✅ lia-roc.org.tw, ecpay |
| Data-LicensePenalty | ✅ 10.10.0.94 | | | ✅ mvdis.gov.tw |
| Data-TaxRefund | ✅ 10.10.0.94 | | | ✅ etax.nat.gov.tw |
| Data-TaxReturn | ✅ 10.10.0.94 | | | ✅ tax.nat.gov.tw |
| Data-Tfasc | ✅ 10.10.0.94 | | | ✅ tfasc.com.tw |
| HR-EMP | ✅ 10.10.0.94 | | | ✅ hr.ucs.tw |
| HR-EMP_Clockin | ✅ 10.10.0.94 | | | ✅ hr.ucs.tw |
| HR-Emp_Salary | ✅ 10.10.0.94 | | | ✅ hr.ucs.tw |
| HR-EmpLeavetb | ✅ 10.10.0.94 | | | ✅ hr.ucs.tw |
| HR-HAMS | | | | ✅ hr.ucs.tw |
| HR-HROrgInfo | ✅ 10.10.0.94 | | | ✅ hr.ucs.tw |
| HR-HRUserInfo | ✅ 10.10.0.94 | | | ✅ hr.ucs.tw |
| HR-INS_JudicialInquiryRequests | ✅ 10.10.0.94 | ✅ 10.10.0.93 | | ✅ judicial.gov.tw |
| HR-Insur_Amount | | | | ✅ hr.ucs.tw |
| OC-GoogleMap | ✅ 10.10.0.94 | | ✅ 10.10.0.66 | ✅ google.com |

---

## 3. Docker 環境設定

### 3.1 目錄結構

```
/opt/docker/
├── docker-compose.yml          # 主要 compose 檔
├── n8n/
│   └── data/                   # n8n 資料持久化
├── crawlab/
│   ├── Dockerfile              # Crawlab 映像檔
│   ├── app/                    # Crawlab 專案 (從 Git clone)
│   ├── logs/                   # Log 持久化
│   └── output/                 # 輸出檔案持久化
└── .env                        # 環境變數
```

### 3.2 建立 .env 檔案

```bash
# /opt/docker/.env

# n8n 設定
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=YourSecurePassword123

# 時區
TZ=Asia/Taipei
GENERIC_TIMEZONE=Asia/Taipei

# Crawlab API 設定
CRAWLAB_API_PORT=8000

# 資料庫連線 (可選，用於環境變數覆蓋)
DB_SERVER=10.10.0.94
DB_PORT=1433
SMB_SERVER=10.10.0.93
SMB_PORT=445
SSH_SERVER=10.10.0.66
SSH_PORT=22
```

### 3.3 建立 Crawlab Dockerfile

```dockerfile
# /opt/docker/crawlab/Dockerfile

FROM python:3.11-slim

LABEL maintainer="your-email@example.com"

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    # SQL Server ODBC
    unixodbc-dev \
    freetds-dev \
    # SMB
    smbclient \
    # 中文字型
    fonts-noto-cjk \
    # 其他工具
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements
COPY app/requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 安裝 Playwright 及瀏覽器
RUN pip install playwright && \
    playwright install chromium && \
    playwright install-deps

# 複製專案
COPY app/ .

# 建立輸出目錄
RUN mkdir -p /app/logs /app/output

# 設定環境變數
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8
ENV TZ=Asia/Taipei

# 暴露 API 端口
EXPOSE 8000

# 預設執行 API Gateway
CMD ["uvicorn", "api_gateway:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.4 建立 docker-compose.yml

```yaml
# /opt/docker/docker-compose.yml

version: '3.8'

services:
  # ============================================
  # n8n - 工作流程自動化平台
  # ============================================
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=${N8N_BASIC_AUTH_ACTIVE}
      - N8N_BASIC_AUTH_USER=${N8N_BASIC_AUTH_USER}
      - N8N_BASIC_AUTH_PASSWORD=${N8N_BASIC_AUTH_PASSWORD}
      - GENERIC_TIMEZONE=${TZ}
      - TZ=${TZ}
      - N8N_LOG_LEVEL=info
      - EXECUTIONS_DATA_SAVE_ON_ERROR=all
      - EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
      # Webhook URL (外部訪問)
      - WEBHOOK_URL=http://your-server-ip:5678/
    volumes:
      - ./n8n/data:/home/node/.n8n
    networks:
      - crawlab-network
    depends_on:
      - crawlab

  # ============================================
  # Crawlab - 爬蟲執行環境
  # ============================================
  crawlab:
    build:
      context: ./crawlab
      dockerfile: Dockerfile
    container_name: crawlab
    restart: always
    ports:
      - "8000:8000"
    environment:
      - TZ=${TZ}
      - PYTHONUNBUFFERED=1
      - PYTHONIOENCODING=utf-8
    volumes:
      # 專案程式碼 (開發時可用 bind mount)
      - ./crawlab/app:/app
      # Log 持久化
      - ./crawlab/logs:/app/logs
      # 輸出檔案持久化
      - ./crawlab/output:/app/output
    networks:
      - crawlab-network
    # 健康檢查
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  crawlab-network:
    driver: bridge
```

### 3.5 部署步驟

```bash
# 1. 建立目錄結構
mkdir -p /opt/docker/{n8n/data,crawlab/{app,logs,output}}

# 2. Clone 專案到 crawlab/app
cd /opt/docker/crawlab
git clone https://github.com/MatthewChung83/Crawlab.git app

# 3. 建立 .env 檔案
cd /opt/docker
cat > .env << 'EOF'
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=YourSecurePassword123
TZ=Asia/Taipei
GENERIC_TIMEZONE=Asia/Taipei
CRAWLAB_API_PORT=8000
EOF

# 4. 複製 Dockerfile
cp crawlab/app/Dockerfile crawlab/Dockerfile
# (或手動建立上面的 Dockerfile)

# 5. 建立並啟動容器
docker-compose up -d --build

# 6. 檢查狀態
docker-compose ps
docker-compose logs -f
```

---

## 4. Crawlab 容器化

### 4.1 API Gateway 端點

Crawlab 容器啟動後，API Gateway 提供以下端點：

| 方法 | 端點 | 說明 |
|------|------|------|
| GET | `/api/v1/health` | 健康檢查 |
| GET | `/api/v1/modules` | 列出所有模組 |
| POST | `/api/v1/tasks` | 建立任務 |
| GET | `/api/v1/tasks/{task_id}` | 查詢任務狀態 |
| GET | `/api/v1/tasks` | 列出所有任務 |
| GET | `/api/v1/logs/{module}` | 取得模組 Log |

### 4.2 測試 API

```bash
# 健康檢查
curl http://localhost:8000/api/v1/health

# 列出模組
curl http://localhost:8000/api/v1/modules

# 建立任務
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"module": "Data-Court_Auction"}'

# 查詢任務狀態
curl http://localhost:8000/api/v1/tasks/{task_id}
```

---

## 5. n8n 與 Crawlab 串接

### 5.1 在 n8n 中建立 HTTP Request 節點

**建立任務:**

```
Method: POST
URL: http://crawlab:8000/api/v1/tasks
Headers:
  Content-Type: application/json
Body (JSON):
{
  "module": "Data-Court_Auction",
  "callback_url": "http://n8n:5678/webhook/crawlab-callback"
}
```

> **注意:** 在 Docker 網路中，使用 container name (`crawlab`) 而非 IP

### 5.2 建立完整 Workflow

#### Step 1: Schedule Trigger
```json
{
  "parameters": {
    "rule": {
      "interval": [
        {
          "field": "cronExpression",
          "expression": "0 2 * * *"
        }
      ]
    }
  },
  "name": "每日 02:00 觸發",
  "type": "n8n-nodes-base.scheduleTrigger"
}
```

#### Step 2: HTTP Request - 建立任務
```json
{
  "parameters": {
    "method": "POST",
    "url": "http://crawlab:8000/api/v1/tasks",
    "sendBody": true,
    "bodyParameters": {
      "parameters": [
        {
          "name": "module",
          "value": "Data-Court_Auction"
        }
      ]
    },
    "options": {}
  },
  "name": "執行爬蟲",
  "type": "n8n-nodes-base.httpRequest"
}
```

#### Step 3: Wait - 等待執行
```json
{
  "parameters": {
    "amount": 30,
    "unit": "seconds"
  },
  "name": "等待 30 秒",
  "type": "n8n-nodes-base.wait"
}
```

#### Step 4: HTTP Request - 查詢狀態
```json
{
  "parameters": {
    "url": "=http://crawlab:8000/api/v1/tasks/{{ $json.task_id }}",
    "options": {}
  },
  "name": "查詢狀態",
  "type": "n8n-nodes-base.httpRequest"
}
```

#### Step 5: IF - 檢查是否完成
```json
{
  "parameters": {
    "conditions": {
      "string": [
        {
          "value1": "={{ $json.status }}",
          "operation": "equals",
          "value2": "success"
        }
      ]
    }
  },
  "name": "是否成功",
  "type": "n8n-nodes-base.if"
}
```

#### Step 6: Loop - 輪詢直到完成
如果任務還在執行中 (status = "running")，回到 Step 3 等待

### 5.3 完整 Workflow JSON (可直接匯入)

```json
{
  "name": "Crawlab - Data-Court_Auction",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [{"field": "cronExpression", "expression": "0 2 * * *"}]
        }
      },
      "name": "Schedule",
      "type": "n8n-nodes-base.scheduleTrigger",
      "position": [250, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "http://crawlab:8000/api/v1/tasks",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={\"module\": \"Data-Court_Auction\"}"
      },
      "name": "Create Task",
      "type": "n8n-nodes-base.httpRequest",
      "position": [450, 300]
    },
    {
      "parameters": {
        "amount": 30,
        "unit": "seconds"
      },
      "name": "Wait",
      "type": "n8n-nodes-base.wait",
      "position": [650, 300]
    },
    {
      "parameters": {
        "url": "=http://crawlab:8000/api/v1/tasks/{{ $('Create Task').item.json.task_id }}"
      },
      "name": "Check Status",
      "type": "n8n-nodes-base.httpRequest",
      "position": [850, 300]
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.status }}",
              "operation": "equals",
              "value2": "success"
            }
          ]
        }
      },
      "name": "IF Success",
      "type": "n8n-nodes-base.if",
      "position": [1050, 300]
    },
    {
      "parameters": {
        "channel": "#crawlab-alerts",
        "text": "=✅ 爬蟲執行成功\n模組: Data-Court_Auction\n時間: {{ $now.format('YYYY-MM-DD HH:mm:ss') }}"
      },
      "name": "Slack Success",
      "type": "n8n-nodes-base.slack",
      "position": [1250, 200]
    },
    {
      "parameters": {
        "channel": "#crawlab-alerts",
        "text": "=❌ 爬蟲執行失敗\n模組: Data-Court_Auction\n錯誤: {{ $json.result.error || $json.result.message }}"
      },
      "name": "Slack Failed",
      "type": "n8n-nodes-base.slack",
      "position": [1250, 400]
    }
  ],
  "connections": {
    "Schedule": {"main": [[{"node": "Create Task", "type": "main", "index": 0}]]},
    "Create Task": {"main": [[{"node": "Wait", "type": "main", "index": 0}]]},
    "Wait": {"main": [[{"node": "Check Status", "type": "main", "index": 0}]]},
    "Check Status": {"main": [[{"node": "IF Success", "type": "main", "index": 0}]]},
    "IF Success": {
      "main": [
        [{"node": "Slack Success", "type": "main", "index": 0}],
        [{"node": "Slack Failed", "type": "main", "index": 0}]
      ]
    }
  }
}
```

---

## 6. Workflow 詳細設計

### 6.1 單一模組 Workflow

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Schedule │──▶│  Create  │──▶│   Wait   │──▶│  Check   │──▶│  Notify  │
│ Trigger  │   │   Task   │   │  30 sec  │   │  Status  │   │          │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
                                   ▲              │
                                   │   running    │
                                   └──────────────┘
```

### 6.2 批次執行 Workflow (多模組)

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ Schedule │──▶│  Split   │──▶│  For     │──▶│  Summary │
│ Trigger  │   │  Modules │   │  Each    │   │  Report  │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              ┌──────────┐  ┌──────────┐  ┌──────────┐
              │ Module 1 │  │ Module 2 │  │ Module N │
              └──────────┘  └──────────┘  └──────────┘
```

### 6.3 依類別分組的建議 Workflow

**Workflow 1: Data 爬蟲 (每日 02:00-06:00)**
```
模組: Data-Court_Auction, Data-Judicial_*, Data-Legal_Insur,
      Data-Insurance, Data-TaxReturn, Data-TaxRefund, etc.
排程: 0 2 * * * (02:00 開始，每個模組間隔 30 分鐘)
```

**Workflow 2: HR 同步 (每日 07:00, 19:00)**
```
模組: HR-EMP, HR-EMP_Clockin, HR-Emp_Salary, HR-EmpLeavetb,
      HR-HRUserInfo, HR-HROrgInfo, HR-HAMS, HR-Insur_Amount
排程: 0 7,19 * * *
```

**Workflow 3: 外部整合 (每週一)**
```
模組: OC-GoogleMap
排程: 0 8 * * 1
```

---

## 7. Port 與防火牆設定

### 7.1 Docker Host 需要開放的 Port

| Port | 協議 | 說明 | 來源 |
|------|------|------|------|
| **5678** | TCP | n8n Web UI | 管理人員 IP |
| **8000** | TCP | Crawlab API | n8n (內部) |

### 7.2 Docker Host 需要連出的 Port

| 目標 | Port | 協議 | 說明 |
|------|------|------|------|
| 10.10.0.94 | 1433 | TCP | SQL Server |
| 10.10.0.93 | 445 | TCP | SMB (CIFS) |
| 10.10.0.93 | 139 | TCP | NetBIOS (備用) |
| 10.10.0.66 | 22 | TCP | SSH/SCP |
| 10.10.0.159 | 25 | TCP | SMTP |
| *.gov.tw | 443 | TCP | 政府網站 |
| *.com.tw | 443 | TCP | 商業網站 |
| hr.ucs.tw | 443 | TCP | HR 系統 |

### 7.3 Linux 防火牆設定 (firewalld)

```bash
# 開放 n8n Web UI
sudo firewall-cmd --permanent --add-port=5678/tcp

# 開放 Crawlab API (如需外部訪問)
sudo firewall-cmd --permanent --add-port=8000/tcp

# 套用設定
sudo firewall-cmd --reload

# 檢查
sudo firewall-cmd --list-ports
```

### 7.4 Windows 防火牆設定

```powershell
# 開放 n8n
New-NetFirewallRule -DisplayName "n8n Web UI" -Direction Inbound -Port 5678 -Protocol TCP -Action Allow

# 開放 Crawlab API
New-NetFirewallRule -DisplayName "Crawlab API" -Direction Inbound -Port 8000 -Protocol TCP -Action Allow
```

### 7.5 Docker 網路檢查

```bash
# 檢查容器網路
docker network ls
docker network inspect crawlab-network

# 測試容器間連線
docker exec -it n8n ping crawlab
docker exec -it crawlab ping n8n

# 測試外部連線 (從 crawlab 容器)
docker exec -it crawlab ping 10.10.0.94
docker exec -it crawlab nc -zv 10.10.0.94 1433
docker exec -it crawlab nc -zv 10.10.0.93 445
```

---

## 附錄

### A. 快速啟動命令

```bash
# 啟動所有服務
docker-compose up -d

# 查看狀態
docker-compose ps

# 查看 Log
docker-compose logs -f

# 重新建置 Crawlab
docker-compose build crawlab
docker-compose up -d crawlab

# 進入 Crawlab 容器
docker exec -it crawlab bash

# 手動執行模組
docker exec -it crawlab python run_crawler.py Data-Court_Auction

# 停止所有服務
docker-compose down
```

### B. 疑難排解

```bash
# 檢查 Crawlab API 是否正常
curl http://localhost:8000/api/v1/health

# 檢查 n8n 是否正常
curl http://localhost:5678/healthz

# 檢查容器 Log
docker logs crawlab --tail 100
docker logs n8n --tail 100

# 檢查網路連線
docker exec -it crawlab python -c "
import pymssql
conn = pymssql.connect('10.10.0.94', 'CLUSER', 'Ucredit7607', 'CL_Daily')
print('DB 連線成功')
conn.close()
"
```

### C. 完整 Port 總覽

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Port 總覽                                    │
├─────────────────────────────────────────────────────────────────────┤
│  Docker Host                                                         │
│  ├── 5678 (TCP) ← n8n Web UI                                        │
│  └── 8000 (TCP) ← Crawlab API                                       │
├─────────────────────────────────────────────────────────────────────┤
│  內部連線 (Outbound)                                                 │
│  ├── 10.10.0.94:1433 (TCP) → SQL Server                             │
│  ├── 10.10.0.93:445 (TCP)  → SMB File Server                        │
│  ├── 10.10.0.93:139 (TCP)  → NetBIOS (備用)                         │
│  ├── 10.10.0.66:22 (TCP)   → SSH Server                             │
│  └── 10.10.0.159:25 (TCP)  → SMTP Server                            │
├─────────────────────────────────────────────────────────────────────┤
│  外部連線 (Outbound)                                                 │
│  └── *:443 (TCP) → HTTPS (政府/商業網站)                             │
└─────────────────────────────────────────────────────────────────────┘
```
