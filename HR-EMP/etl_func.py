# -*- coding: utf-8 -*-
"""
ETL functions for HR-EMP employee data sync
"""
import time
import logging
import pymssql
import requests

from config import db, api, dataschema

logger = logging.getLogger(__name__)


def get_database_connection():
    """建立資料庫連線"""
    try:
        conn = pymssql.connect(
            server=db['server'],
            user=db['username'],
            password=db['password'],
            database=db['database'],
            autocommit=db['autocommit']
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


def safe_execute(cursor, sql, params=None, max_retry=5):
    """安全執行 SQL 語句，處理死鎖重試"""
    for i in range(max_retry):
        try:
            if params is not None:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return True
        except pymssql.OperationalError as e:
            if hasattr(e, 'args') and len(e.args) > 0 and '1205' in str(e.args[0]):
                logger.warning(f"SQL deadlock detected, retry {i+1}/{max_retry} ...")
                time.sleep(1 + i * 0.5)
                continue
            else:
                logger.error(f"SQL execution error: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error in SQL execution: {e}")
            raise

    raise Exception("SQL Deadlock retried too many times, abort.")


def get_existing_employees(conn):
    """取得現有員工資料"""
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT empi, name, cname, department, empstatus FROM emp')
        employees = cursor.fetchall()
        cursor.close()

        emp_dict = {}
        for emp in employees:
            emp_dict[int(emp[0])] = {
                'name': emp[1],
                'cname': emp[2],
                'department': emp[3],
                'empstatus': emp[4]
            }
        return emp_dict
    except Exception as e:
        logger.error(f"Failed to get existing employees: {e}")
        raise


def login():
    """登入 API 系統"""
    data = {
        "Action": "Login",
        "SessionGuid": "",
        "Value": {
            "$type": "AIS.Define.TLogingInputArgs, AIS.Define",
            "CompanyID": api['company_id'],
            "UserID": api['user_id'],
            "Password": api['password'],
            "LanguageID": api['language_id']
        }
    }

    headers = {'Content-type': 'application/json'}

    try:
        response = requests.post(api['system_url'], json=data, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
        if result.get('Result'):
            session_id = result.get('SessionGuid')
            logger.info("API login successful")
            return session_id
        else:
            logger.error(f"Login failed: {result.get('Message')}")
            return None
    except Exception as e:
        logger.error(f"Login request failed: {e}")
        return None


def fetch_employee_data(session_id):
    """從 API 取得員工資料"""
    data = {
        "Action": "Find",
        "SessionGuid": session_id,
        "ProgID": "HUM0020100",
        "Value": {
            "$type": "AIS.Define.TFindInputArgs, AIS.Define",
            "SelectFields": ("SYS_VIEWID,SYS_NAME,SYS_ENGNAME,TMP_DEPARTID,TMP_DEPARTNAME,"
                             "SeparationDate,RETENTIONDATE,TMP_PROFITID,TMP_PROFITNAME,JobStatus,"
                             "TMP_LEVELNAME,TMP_DECCOMPANYNAME,STARTDATE,BIRTHDATE,TMP_DUTYNAME,"
                             "OFFICETEL1,IDNO"),
            "FilterItems": [
                {
                    "$type": "AIS.Define.TFilterItem, AIS.Define",
                    "FieldName": "JobStatus",
                    "FilterValue": "0",
                    "ComparisonOperator": "NotEqual"
                }
            ],
            "SystemFilterOptions": "Session, DataPermission, EmployeeLevel",
            "IsBuildSelectedField": "true",
            "IsBuildFlowLightSignalField": "true"
        }
    }

    headers = {'Content-type': 'application/json'}

    try:
        response = requests.post(api['business_url'], json=data, headers=headers, timeout=120)
        response.raise_for_status()
        result = response.json()
        datatable = result.get('DataTable', [])
        logger.info(f"Fetched {len(datatable)} employee records from API")
        return datatable
    except Exception as e:
        logger.error(f"Failed to fetch employee data: {e}")
        return []


def safe_str(v):
    """安全轉換為字串"""
    return None if v in (None, '') else str(v)


def get_empstatus(raw_status):
    """取得員工狀態"""
    try:
        status_idx = int(raw_status)
    except Exception:
        status_idx = 1
    if 1 <= status_idx <= len(dataschema['jobstatus']):
        return dataschema['jobstatus'][status_idx - 1]
    return '正職'


def get_leftdate(empstatus, employee_data):
    """取得離職/留職停薪日期"""
    leftdate = None
    sep = safe_str(employee_data.get('SEPARATIONDATE'))
    ret = safe_str(employee_data.get('RETENTIONDATE'))
    if empstatus == '離職' and sep:
        leftdate = sep[:10]
    elif empstatus == '留職停薪' and ret:
        leftdate = ret[:10]
    return leftdate
