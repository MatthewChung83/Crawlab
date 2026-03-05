# Crawlab - Data Crawler System

Crawlab is a modular data crawling and ETL system for judicial, tax, HR, and insurance data.

## Project Structure

```
Crawlab/
├── check_modules.py          # Module check tool
├── Data-Court_Auction/       # Court auction data
├── Data-Tfasc/               # TFASC auction system (includes doc download)
├── Data-Legal_Insur/         # Legal insurance
├── Data-Insurance/           # Insurance data
├── Data-Insurance_inc/       # Insurance incremental data
├── Data-Judicial_*/          # Judicial data (139, 146, cdbc3, fam)
├── Data-TaxReturn/           # Tax return data
├── Data-TaxRefund/           # Tax refund data
├── Data-Land_Parcel_Section/ # Land parcel data
├── Data-LicensePenalty/      # License penalty data
├── HR-*/                     # HR modules (HAMS, EMP, etc.)
└── OC-GoogleMap/             # Google Map integration
```

## Standard Module Structure

All modules follow this standard structure:

```
Module/
├── config.py      # Configuration (DB, API URLs, settings)
├── main.py        # Main program logic with run() function
└── etl_func.py    # ETL functions (extract, transform, load)
```

## Quick Start

### 1. Check All Modules

```bash
python check_modules.py
```

### 2. Check Dependencies

```bash
python check_modules.py --deps
```

### 3. Check Specific Module

```bash
python check_modules.py -m Data-Court_Auction -v
```

### 4. Run a Crawler

```bash
cd Data-Court_Auction
python main.py
python main.py --start_date 20240101
```

## Module Check Tool

The `check_modules.py` tool provides:

- **Syntax checking** - Validates all Python files
- **Structure checking** - Verifies config/main/etl files exist
- **Dependency checking** - Confirms required packages installed

### Output Legend

| Symbol | Meaning |
|--------|---------|
| `[OK]` | Standard structure (config + main + etl) |
| `[*]`  | Non-standard (only main.py) |
| `[!]`  | Has syntax errors |
| `[X]`  | Module not found |

## Required Dependencies

| Package | Description |
|---------|-------------|
| requests | HTTP requests |
| pymssql | MSSQL database connection |
| pandas | Data processing |
| beautifulsoup4 | HTML parsing |
| pdfplumber | PDF parsing |

### Optional Dependencies

| Package | Description | Used By |
|---------|-------------|---------|
| playwright | Browser automation | OC-GoogleMap, HR-INS_JudicialInquiryRequests |
| ddddocr | OCR captcha recognition | Data-Insurance, Data-Insurance_inc |
| paramiko | SSH/SCP connections | OC-GoogleMap |
| Pillow | Image processing | HR-INS_JudicialInquiryRequests |
| pysmb | SMB file sharing | HR-INS_JudicialInquiryRequests |

## Database Configuration

All modules connect to:

- **Server**: 10.10.0.94
- **Database**: CL_Daily / UCS_ETL / UCS_ReportDB
- **User**: CLUSER / FRUSER

## Module Status

### Data Series (13 modules)

| Module | Structure | Description |
|--------|-----------|-------------|
| Data-Court_Auction | config+main+etl | Court auction crawler with PDF parsing |
| Data-Tfasc | config+main+etl | TFASC auction system with document download |
| Data-Legal_Insur | config+main+etl | Legal insurance data |
| Data-Insurance | config+main+etl | Insurance data with OCR |
| Data-Insurance_inc | config+main+etl | Incremental insurance data |
| Data-Judicial_139 | config+main+etl | Judicial data (139 system) |
| Data-Judicial_146 | config+main+etl | Judicial data (146 system) |
| Data-Judicial_cdbc3 | config+main+etl | Judicial data (cdbc3 system) |
| Data-Judicial_fam | config+main+etl | Family judicial cases |
| Data-TaxReturn | config+main+etl | Tax return data |
| Data-TaxRefund | config+main+etl | Tax refund data |
| Data-Land_Parcel_Section | config+main+etl | Land parcel data |
| Data-LicensePenalty | config+main+etl | License penalty data |

### HR Series (9 modules)

| Module | Structure | Description |
|--------|-----------|-------------|
| HR-HAMS | config+main+etl | Access control data import (mdbtools) |
| HR-EMP | config+main+etl | Employee basic data sync |
| HR-EMP_Clockin | config+main+etl | Employee clock-in sync |
| HR-Emp_Salary | config+main+etl | Employee salary sync |
| HR-EmpLeavetb | config+main+etl | Employee leave records |
| HR-HRUserInfo | config+main+etl | HR user info sync |
| HR-HROrgInfo | config+main+etl | HR organization info sync |
| HR-INS_JudicialInquiryRequests | config+main+etl | Judicial inquiry crawler (Playwright) |
| HR-Insur_Amount | config+main+etl | Insurance amount notification |

### OC Series (1 module)

| Module | Structure | Description |
|--------|-----------|-------------|
| OC-GoogleMap | config+main+etl | OC visit case sync to Google Maps (Playwright) |

## Development

### Adding a New Module

1. Create folder: `Data-NewModule/` or `HR-NewModule/`
2. Create standard files:
   - `config.py` - Database and API configuration
   - `main.py` - Main crawler logic with `run()` function
   - `etl_func.py` - ETL helper functions
3. Add module name to `MODULES` list in `check_modules.py`
4. Run `python check_modules.py -m NewModule -v` to verify

### Standard config.py Template

```python
# -*- coding: utf-8 -*-
"""
Configuration for Module-Name
"""

db = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'username': 'CLUSER',
    'password': 'Ucredit7607',
    'totb': 'target_table',
}

api = {
    'url': 'https://example.com/api',
    'user': 'api_user',
    'password': 'api_password',
}
```

### Standard main.py Template

```python
# -*- coding: utf-8 -*-
"""
Module-Name - Description
"""
import datetime

from config import *
from etl_func import (
    function1, function2, function3
)


def run():
    """Main execution function"""
    print(f"開始執行: {datetime.datetime.now()}")

    # Your logic here

    print(f"執行完成: {datetime.datetime.now()}")
    return True


if __name__ == '__main__':
    run()
```

### Standard etl_func.py Template

```python
# -*- coding: utf-8 -*-
"""
ETL functions for Module-Name
"""
import pymssql
import requests

from config import db, api


def delete_records(server, username, password, database, totb):
    """Delete all records from table"""
    conn = pymssql.connect(server=server, user=username, password=password, database=database)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM [{totb}]")
    conn.commit()
    cursor.close()
    conn.close()


def toSQL(docs, totb, server, database, username, password):
    """Insert records to SQL Server"""
    with pymssql.connect(server=server, user=username, password=password, database=database) as conn:
        conn.autocommit(False)
        with conn.cursor() as cursor:
            data_keys = ','.join(docs[0].keys())
            data_symbols = ','.join(['%s' for _ in range(len(docs[0].keys()))])
            insert_cmd = f"INSERT INTO {totb} ({data_keys}) VALUES ({data_symbols})"
            data_values = [tuple(doc.values()) for doc in docs]
            cursor.executemany(insert_cmd, data_values)
            conn.commit()


def login():
    """Login to API and return session ID"""
    response = requests.post(api['url'], json={...})
    return response.json().get('SessionGuid')


def fetch_data(session_id):
    """Fetch data from API"""
    response = requests.get(api['url'], json={...})
    return response.json().get('DataTable', [])
```

## Recent Updates

- **2026-03-05**: All 23 modules converted to standard structure (config + main + etl)
- **2026-03-05**: Selenium removed from all modules, replaced with Playwright
- **2026-03-05**: Data-Tfasc and Data-Tfasc_Doc_Download merged into single module
- **2026-03-05**: All Scrapy dependencies removed, converted to requests-based architecture
