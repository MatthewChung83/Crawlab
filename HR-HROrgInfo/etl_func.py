# -*- coding: utf-8 -*-
"""
ETL functions for HR-HROrgInfo - Organization info sync from HR API
"""
import json
import requests
import pymssql

from config import api


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


def orginfo_etl(doc):
    """Transform organization info data"""
    return [{
        'SYS_VIEWID': doc[0],
        'SYS_NAME': doc[1],
        'SYS_ENGNAME': doc[2],
        'TMP_PDEPARTID': doc[3],
        'TMP_PDEPARTNAME': doc[4],
        'TMP_PDEPARTENGNAME': doc[5],
        'SYS_ID': doc[6],
        'TMP_MANAGERID': doc[7],
        'TMP_MANAGERNAME': doc[8],
        'TMP_MANAGERENGNAME': doc[9],
    }]


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


def fetch_orginfo_data(session_id):
    """Fetch organization info data from API"""
    headers = {'Content-type': 'application/json'}
    data = {
        "Action": "Find",
        "SessionGuid": session_id,
        "ProgID": "HUM0010300",
        "Value": {
            "$type": "AIS.Define.TFindInputArgs, AIS.Define",
            "SelectCount": 500,
            "SelectFields": "SYS_VIEWID,SYS_NAME,SYS_ENGNAME,TMP_PDEPARTID,TMP_PDEPARTNAME,TMP_MANAGERID,TMP_MANAGERNAME",
            "SystemFilterOptions": "Session,DataPermission,EmployeeLevel",
            "IsBuildSelectedField": 'true',
            "IsBuildFlowLightSignalField": 'true'
        }
    }
    data_json = json.dumps(data)
    response = requests.post(api['api_url'], data=data_json, headers=headers, verify=False)
    result = response.json()
    return result.get('DataTable', [])
