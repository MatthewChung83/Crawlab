# Skill: Check Modules

## Overview

This skill checks the status of all crawler modules in the Crawlab project.

## Command

```bash
python check_modules.py [options]
```

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--deps` | `-d` | Check required and optional dependencies |
| `--module NAME` | `-m NAME` | Check specific module only |
| `--verbose` | `-v` | Show detailed information |

## Usage Examples

```bash
# Check all modules
python check_modules.py

# Check dependencies
python check_modules.py --deps

# Check specific module with details
python check_modules.py -m Data-Court_Auction -v

# Combined options
python check_modules.py --deps -v
```

## Output Symbols

| Symbol | Meaning |
|--------|---------|
| `[OK]` | Standard structure (config + main + etl) |
| `[*]` | Non-standard structure (main.py only) |
| `[!]` | Has syntax errors |
| `[X]` | Module not found |

## What It Checks

### 1. Module Structure
- `config.py` - Configuration file exists
- `main.py` - Main program exists
- `etl_func.py` - ETL functions exist

### 2. Syntax Validation
- Compiles all `.py` files
- Reports syntax errors with file location

### 3. Dependencies (with `--deps`)

**Required:**
- requests - HTTP requests
- pymssql - MSSQL database
- pandas - Data processing
- beautifulsoup4 - HTML parsing
- pdfplumber - PDF parsing

**Optional:**
- playwright - Browser automation (used by OC-GoogleMap, HR-INS_JudicialInquiryRequests)
- ddddocr - OCR captcha recognition
- paramiko - SSH/SCP connections
- Pillow - Image processing

## Module Categories

### Data Series (13 modules)
| Module | Description | Dependencies |
|--------|-------------|--------------|
| Data-Court_Auction | Court auction data crawler | requests, pymssql, pdfplumber |
| Data-Tfasc | TFASC data with document download | requests, pymssql |
| Data-Legal_Insur | Legal insurance data | requests, pymssql |
| Data-Insurance | Insurance data crawler | requests, pymssql, ddddocr |
| Data-Insurance_inc | Insurance incremental data | requests, pymssql, ddddocr |
| Data-Judicial_139 | Judicial 139 system | requests, pymssql |
| Data-Judicial_146 | Judicial 146 system | requests, pymssql |
| Data-Judicial_cdbc3 | Judicial CDBC3 system | requests, pymssql |
| Data-Judicial_fam | Judicial family system | requests, pymssql |
| Data-TaxReturn | Tax return data | requests, pymssql |
| Data-TaxRefund | Tax refund data | requests, pymssql |
| Data-Land_Parcel_Section | Land parcel section data | requests, pymssql |
| Data-LicensePenalty | License penalty data | requests, pymssql |

### HR Series (9 modules)
| Module | Description | Dependencies |
|--------|-------------|--------------|
| HR-HAMS | Access control data import (mdbtools) | requests, pymssql |
| HR-EMP | Employee data sync | requests, pymssql |
| HR-EMP_Clockin | Employee clock-in sync | requests, pymssql |
| HR-Emp_Salary | Employee salary sync | requests, pymssql |
| HR-EmpLeavetb | Employee leave records | requests, pymssql |
| HR-HRUserInfo | HR user info sync | requests, pymssql |
| HR-HROrgInfo | HR organization info sync | requests, pymssql |
| HR-INS_JudicialInquiryRequests | Judicial inquiry crawler | playwright, pymssql, Pillow, pysmb |
| HR-Insur_Amount | Insurance amount notification | requests, pymssql, pandas |

### OC Series (1 module)
| Module | Description | Dependencies |
|--------|-------------|--------------|
| OC-GoogleMap | OC visit case sync to Google Maps | playwright, pymssql, pandas, paramiko |

## Standard Module Structure

All modules follow this standard structure:

```
Module/
├── config.py      # Database, API, and other configuration
├── main.py        # Main entry point with run() function
└── etl_func.py    # ETL helper functions (database, API, transform)
```

### config.py Pattern
```python
# -*- coding: utf-8 -*-
db = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'username': 'CLUSER',
    'password': '...',
}

api = {
    'main_url': 'https://...',
    'api_url': 'https://...',
}
```

### main.py Pattern
```python
# -*- coding: utf-8 -*-
from config import *
from etl_func import (...)

def run():
    """Main execution function"""
    # ... logic ...
    return True

if __name__ == '__main__':
    run()
```

### etl_func.py Pattern
```python
# -*- coding: utf-8 -*-
from config import db, api

def delete_records(...):
    """Delete records from table"""

def toSQL(docs, ...):
    """Insert records to SQL Server"""

def login():
    """Login to API and return session"""

def fetch_data(session_id):
    """Fetch data from API"""
```

## Example Output

```
============================================================
Crawlab Module Check Tool
Check time: 2026-03-05 14:14:22
============================================================

[Required Packages]
  [OK] requests: HTTP requests
  [OK] pymssql: MSSQL database connection
  [OK] pandas: Data processing
  [OK] beautifulsoup4: HTML parsing
  [OK] pdfplumber: PDF parsing

[Optional Packages]
  [OK] playwright: Browser automation
  [OK] ddddocr: OCR captcha recognition
  [OK] paramiko: SSH/SCP connections

[Module Status]

  --- Data Series (13 modules) ---
  [OK] Data-Court_Auction: [config+main+etl] (3 files)
  [OK] Data-Tfasc: [config+main+etl] (3 files)
  [OK] Data-Legal_Insur: [config+main+etl] (3 files)
  ...

  --- HR Series (9 modules) ---
  [OK] HR-HAMS: [config+main+etl] (3 files)
  [OK] HR-EMP: [config+main+etl] (3 files)
  ...

  --- OC Series (1 module) ---
  [OK] OC-GoogleMap: [config+main+etl] (3 files)

============================================================
Total: 23 modules | OK: 23 | Non-standard: 0 | Error: 0
============================================================
```

## Troubleshooting

### Module shows `[!]` (syntax error)
- Run with `-v` to see error details
- Fix the syntax error in the reported file

### Module shows `[*]` (non-standard)
- Module is missing `config.py` or `etl_func.py`
- Consider refactoring to standard structure

### Dependency shows `[X]`
- Install missing package: `pip install <package>`
- For playwright: `pip install playwright && playwright install`

## Recent Updates

- **2026-03-05**: All modules converted to standard structure (config + main + etl)
- **2026-03-05**: Selenium removed from all modules, replaced with Playwright
- **2026-03-05**: Data-Tfasc and Data-Tfasc_Doc_Download merged into single module
- **2026-03-05**: All Scrapy dependencies removed, converted to requests-based
