# Crawlab 環境需求文檔

## 推薦環境配置

### Python 版本

| 推薦程度 | Python 版本 | 說明 |
|----------|-------------|------|
| **推薦** | **Python 3.11** | 最佳相容性，所有套件都有完整支援 |
| 可用 | Python 3.10 | 大部分套件支援，但 onnxruntime 將停止支援 |
| 不建議 | Python 3.12+ | ddddocr 官方版本不支援，需使用非官方版本 |
| 不支援 | Python 3.8 以下 | 多數套件已停止支援 |

---

## 套件版本需求

### 核心 OCR 套件 (ddddocr)

| 套件 | 推薦版本 | Python 相容性 | 備註 |
|------|----------|---------------|------|
| **ddddocr** | 1.5.5 | < 3.13 | 官方穩定版 |
| ddddocr | 1.4.11 | < 3.12 | 備選版本 |
| ddddocr-unofficial | 1.6.0 | <= 3.13 | 非官方版，支援 Python 3.12/3.13 |

**ddddocr 依賴：**
```
numpy
onnxruntime>=1.16.0,<1.18.0
Pillow
opencv-python-headless
```

### ONNX Runtime 版本對照

| onnxruntime 版本 | Python 3.10 | Python 3.11 | Python 3.12 |
|------------------|-------------|-------------|-------------|
| 1.16.x | ✅ | ✅ | ❌ |
| 1.17.x | ✅ | ✅ | ✅ |
| 1.18.x+ | ⚠️ 即將停止 | ✅ | ✅ |

**建議：** 使用 `onnxruntime==1.17.3` 確保最佳相容性

---

### 網頁爬取套件

| 套件 | 推薦版本 | Python 相容性 | 用途 |
|------|----------|---------------|------|
| **requests** | >= 2.28.0 | 3.7+ | HTTP 請求 |
| **beautifulsoup4** | >= 4.11.0 | 3.7+ | HTML 解析 |
| **playwright** | >= 1.40.0 | >= 3.9 | 瀏覽器自動化 |
| selenium | >= 4.0.0 | 3.8+ | 瀏覽器自動化 (備選) |

**Playwright 安裝後需執行：**
```bash
playwright install
```

---

### 資料庫套件

| 套件 | 推薦版本 | Python 相容性 | 用途 |
|------|----------|---------------|------|
| **pymssql** | >= 2.2.8 | >= 3.9 | SQL Server 連線 |
| **pyodbc** | >= 5.0.0 | >= 3.10 | ODBC 連線 |

**pyodbc 額外需求：**
- Windows: 安裝 [ODBC Driver 17/18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- Linux: `sudo apt install unixodbc-dev`

---

### PDF 處理套件

| 套件 | 推薦版本 | Python 相容性 | 用途 |
|------|----------|---------------|------|
| **pdfplumber** | >= 0.10.0 | 3.8+ | PDF 文字擷取 |
| **fpdf** | >= 1.7.2 | 3.6+ | PDF 生成 |
| fpdf2 | >= 2.7.0 | 3.7+ | PDF 生成 (新版) |

---

### 資料處理套件

| 套件 | 推薦版本 | Python 相容性 | 用途 |
|------|----------|---------------|------|
| **pandas** | >= 1.5.0, < 2.0 | 3.8+ | 資料處理 |
| **numpy** | >= 1.21.0, < 2.0 | 3.8+ | 數值運算 |
| **Pillow** | >= 9.0.0 | 3.7+ | 圖片處理 |
| chardet | >= 5.0.0 | 3.7+ | 編碼偵測 |
| regex | >= 2022.0.0 | 3.7+ | 進階正則表達式 |

**重要：** `numpy < 2.0` 避免與 onnxruntime 衝突

---

### 網路與檔案傳輸

| 套件 | 推薦版本 | Python 相容性 | 用途 |
|------|----------|---------------|------|
| **paramiko** | >= 3.0.0 | 3.6+ | SSH/SFTP |
| **scp** | >= 0.14.0 | 3.6+ | SCP 傳輸 |
| pysmb | >= 1.2.9 | 3.6+ | SMB/CIFS |

---

## requirements.txt (完整版)

```txt
# ===== Python 3.11 推薦版本 =====

# OCR
ddddocr==1.5.5
onnxruntime==1.17.3
opencv-python-headless>=4.8.0
Pillow>=9.5.0,<11.0.0

# Web Crawling
requests>=2.31.0
beautifulsoup4>=4.12.0
playwright>=1.40.0
urllib3>=1.26.0,<3.0.0

# Database
pymssql>=2.2.8
pyodbc>=5.0.0

# PDF
pdfplumber>=0.10.0
fpdf>=1.7.2

# Data Processing
pandas>=1.5.0,<2.1.0
numpy>=1.24.0,<2.0.0
chardet>=5.0.0
regex>=2023.0.0

# File Transfer
paramiko>=3.4.0
scp>=0.14.5
pysmb>=1.2.9

# API Gateway (Optional)
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.5.0

# Utilities
python-dateutil>=2.8.0
```

---

## 模組依賴對照表

| 模組 | ddddocr | playwright | pymssql | pyodbc | paramiko | fpdf |
|------|:-------:|:----------:|:-------:|:------:|:--------:|:----:|
| Data-Court_Auction | | ✅ | ✅ | | | |
| Data-Insurance | ✅ | | ✅ | | | |
| Data-Insurance_inc | ✅ | | ✅ | | | |
| Data-Judicial_139 | | ✅ | ✅ | | | |
| Data-Judicial_146 | | ✅ | ✅ | | | |
| Data-Judicial_cdbc3 | | ✅ | ✅ | | | |
| Data-Judicial_fam | | ✅ | ✅ | | | |
| Data-Land_Parcel_Section | | ✅ | ✅ | | | |
| Data-Legal_Insur | | ✅ | ✅ | | | |
| Data-LicensePenalty | | ✅ | ✅ | | | |
| Data-TaxRefund | ✅ | | ✅ | | | |
| Data-TaxReturn | ✅ | | ✅ | | | |
| Data-Tfasc | | ✅ | ✅ | | | ✅ |
| HR-EMP | | | ✅ | | | |
| HR-EMP_Clockin | | | ✅ | | | |
| HR-Emp_Salary | | | ✅ | | | |
| HR-EmpLeavetb | | | ✅ | | | |
| HR-HAMS | | | ✅ | | | |
| HR-HROrgInfo | | | ✅ | | | |
| HR-HRUserInfo | | | ✅ | | | |
| HR-INS_JudicialInquiryRequests | | ✅ | ✅ | | | |
| HR-Insur_Amount | | | ✅ | | | |
| OC-GoogleMap | | | ✅ | | ✅ | |

---

## 安裝指令

### 方式一：完整安裝

```bash
# 建立虛擬環境
python -m venv venv

# 啟用虛擬環境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 安裝 Playwright 瀏覽器
playwright install chromium
```

### 方式二：Docker (推薦生產環境)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    unixodbc-dev \
    freetds-dev \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安裝 Playwright
RUN playwright install chromium --with-deps

COPY . .

CMD ["python", "run_crawler.py", "--help"]
```

---

## 常見問題

### Q1: ddddocr 安裝失敗
```
ImportError: cannot import name 'DdddOcr' from 'ddddocr.core'
```

**解決方案：**
1. 確認 Python 版本 <= 3.11
2. 重新安裝：`pip uninstall ddddocr && pip install ddddocr==1.5.5`
3. 或使用非官方版：`pip install ddddocr-unofficial`

### Q2: onnxruntime 與 numpy 衝突
```
numpy.core.multiarray failed to import
```

**解決方案：**
```bash
pip install numpy<2.0
pip install onnxruntime==1.17.3
```

### Q3: playwright 瀏覽器未安裝
```
playwright._impl._api_types.Error: Executable doesn't exist
```

**解決方案：**
```bash
playwright install chromium
```

### Q4: pymssql 連線失敗
```
InterfaceError: Connection to the database failed
```

**解決方案：**
- 確認 FreeTDS 已安裝 (Linux)
- 確認防火牆允許 1433 port

---

## 版本測試矩陣

| 測試環境 | Python | ddddocr | onnxruntime | playwright | 狀態 |
|----------|--------|---------|-------------|------------|------|
| Windows 11 | 3.11.8 | 1.5.5 | 1.17.3 | 1.45.0 | ✅ 通過 |
| Ubuntu 22.04 | 3.11.0 | 1.5.5 | 1.17.3 | 1.45.0 | ✅ 通過 |
| Windows Server 2019 | 3.10.11 | 1.4.11 | 1.16.3 | 1.40.0 | ✅ 通過 |

---

## 參考資源

- [ddddocr PyPI](https://pypi.org/project/ddddocr/)
- [ddddocr GitHub Issues](https://github.com/sml2h3/ddddocr/issues)
- [onnxruntime Compatibility](https://onnxruntime.ai/docs/reference/compatibility.html)
- [Playwright Python Installation](https://playwright.dev/python/docs/intro)
- [pymssql Documentation](https://pymssql.readthedocs.io/)
- [pyodbc GitHub](https://github.com/mkleehammer/pyodbc)
