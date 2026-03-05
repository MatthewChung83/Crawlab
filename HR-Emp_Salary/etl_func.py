# -*- coding: utf-8 -*-
"""
ETL functions for HR-EMP_Salary - Employee salary data sync
"""
import time
import logging
import pymssql
import requests

from config import db, api

logger = logging.getLogger(__name__)


def safe_execute(cursor, sql, params=None, max_retry=5):
    """Execute SQL with deadlock retry"""
    for i in range(max_retry):
        try:
            if params is not None:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return
        except pymssql.OperationalError as e:
            if hasattr(e, "args") and len(e.args) > 0 and "1205" in str(e.args[0]):
                logger.warning(f"SQL deadlock detected, retry {i+1}/{max_retry} ...")
                time.sleep(1 + i * 0.5)
                continue
            raise
        except Exception as e:
            logger.error(f"Unexpected SQL error: {e}")
            raise
    raise Exception("SQL Deadlock retried too many times, abort.")


def get_db_connection():
    """Get database connection"""
    try:
        conn = pymssql.connect(
            server=db['server'],
            user=db['username'],
            password=db['password'],
            database=db['database'],
            autocommit=db['autocommit']
        )
        logger.info("資料庫連線成功")
        return conn
    except Exception as e:
        logger.error(f"資料庫連線失敗: {e}")
        raise


def get_existing_emp_ids(cursor):
    """Get existing employee IDs from database"""
    try:
        cursor.execute("SELECT empi FROM emp")
        rows = cursor.fetchall()
        existed = {int(r[0]) for r in rows if r[0] is not None}
        logger.info(f"現有 emp 筆數: {len(existed)}")
        return existed
    except Exception as e:
        logger.error(f"讀取現有 emp 失敗: {e}")
        raise


def login():
    """Login to HR API and return session ID"""
    payload = {
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
    headers = {"Content-type": "application/json"}

    try:
        resp = requests.post(api['sys_url'], json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        if result.get("Result"):
            session_id = result.get("SessionGuid", "")
            logger.info("API 登入成功")
            return session_id
        logger.error(f"API 登入失敗: {result.get('Message')}")
        return None
    except Exception as e:
        logger.error(f"API 登入請求失敗: {e}")
        return None


def fetch_salary_data(session_id):
    """Fetch salary data from HR API"""
    payload = {
        "Action": "ExecReport",
        "SessionGuid": session_id,
        "ProgID": "RHUM002",
        "Value": {
            "$type": "AIS.Define.TFindInputArgs, AIS.Define",
            "SelectFields": "SYS_ID,SYS_COMPANYID,EMPLOYEEID,TOTALSALARY,EMPLOYEEENGNAME,EMPLOYEENAME,TMP_DEPARTNAME,TMP_PROFITID",
            "FilterItems": [],
            "SystemFilterOptions": "Session, DataPermission, EmployeeLevel",
            "IsBuildSelectedField": "true",
            "IsBuildFlowLightSignalField": "true"
        }
    }
    headers = {"Content-type": "application/json"}

    try:
        resp = requests.post(api['biz_url'], json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        salary_rows = (result.get("DataSet", {}) or {}).get("ReportBody", []) or []
        logger.info(f"從 API 取得薪資筆數: {len(salary_rows)}")
        return salary_rows
    except Exception as e:
        logger.error(f"取得薪資資料失敗: {e}")
        return []
