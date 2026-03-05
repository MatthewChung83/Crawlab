# -*- coding: utf-8 -*-
"""
ETL functions for HR-HRUserInfo - User info sync from HR API
"""
import json
import requests
import pymssql

from config import api, USER_FIELDS


def delete_records(server, username, password, database, totb):
    """Delete all records from table"""
    conn = pymssql.connect(server=server, user=username, password=password, database=database)
    cursor = conn.cursor()
    script = f"DELETE FROM [{totb}]"
    cursor.execute(script)
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


def userinfo_etl(data_item):
    """Transform user info data using field mapping"""
    return [{field: data_item.get(field) for field in USER_FIELDS}]


def login():
    """Login to HR API and return session ID"""
    headers = {'Content-type': 'application/json'}
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
    data_json = json.dumps(data)
    response = requests.post(api['main_url'], data=data_json, headers=headers, verify=False)
    result = response.json()

    if result.get('Result'):
        return result.get('SessionGuid')
    else:
        print(result.get('Result'), result.get('Message'))
        return None


def fetch_userinfo_data(session_id):
    """Fetch user info data from API"""
    headers = {'Content-type': 'application/json'}
    data = {
        "Action": "ExecReport",
        "SessionGuid": session_id,
        "ProgID": "RHUM002",
        "Value": {
            "$type": "AIS.Define.TExecReportInputArgs, AIS.Define",
            "UIType": "Report",
            "ReportID": "",
            "ReportTailID": "",
            "FilterItems": "",
            "UserFilter": ""
        }
    }
    data_json = json.dumps(data)
    response = requests.post(api['api_url'], data=data_json, headers=headers, verify=False)
    result = response.json()
    return result.get('DataSet', {}).get('ReportBody', [])
