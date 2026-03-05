# -*- coding: utf-8 -*-
"""
ETL functions for HR-EMPLeavetb - Employee leave records sync
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
            try:
                cursor.executemany(insert_cmd, data_values)
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"插入數據時出現錯誤: {e}")


def empleave_etl(doc):
    """Transform leave record data"""
    return [{
        'LEAVETYPE': doc[0],
        'SYS_COMPANYID': doc[1],
        'TMP_DECCOMPANYID': doc[2],
        'TMP_DECCOMPANYNAME': doc[3],
        'TMP_DECCOMPANYENGNAME': doc[4],
        'DEPARTID': doc[5],
        'DEPARTID2': doc[6],
        'DEPARTNAME': doc[7],
        'DEPARTENGNAME': doc[8],
        'EMPLOYEEID': doc[9],
        'EMPLOYEENAME': doc[10],
        'SYS_ENGNAME': doc[11],
        'SEX': doc[12],
        'SYS_VIEWID': doc[13],
        'SYS_DATE': doc[14],
        'VACATIONID': doc[15],
        'VACATIONNAME': doc[16],
        'VACATIONENGNAME': doc[17],
        'SVACATIONID': doc[18],
        'SVACATIONNAME': doc[19],
        'SVACATIONENGNAME': doc[20],
        'STARTDATE': doc[21],
        'STARTTIME': doc[22],
        'ENDDATE': doc[23],
        'ENDTIME': doc[24],
        'LEAVEDAYS': doc[25],
        'LEAVEHOURS': doc[26],
        'LEAVEMINUTES': doc[27],
        'HOURWAGES': doc[28],
        'LEAVEMONEY': doc[29],
        'AGENTID': doc[30],
        'AGENTNAME': doc[31],
        'MAINNOTE': doc[32],
        'SUBNOTE': doc[33],
        'SYS_FLOWFORMSTATUS': doc[34],
        'OFFLEAVEDAYS': doc[35],
        'OFFLEAVEHOURS': doc[36],
        'OFFLEAVEMINUTES': doc[37],
        'REALLEAVEDAYS': doc[38],
        'REALLEAVEHOURS': doc[39],
        'REALLEAVEMINUTES': doc[40],
        'CUTDATE': doc[41],
        'SPECIALDATE': doc[42],
        'STARGETNAME': doc[43],
        'SENDDATE': doc[44],
        'SOURCETAG': doc[45],
        'OUTSIDENAME': doc[46],
        'OUTSIDETEL': doc[47],
        'ISLEAVE': doc[48],
        'ISCOMEBACK': doc[49],
        'EMPTEL': doc[50],
        'RESTPLACE': doc[51],
        'EMPADDRESS': doc[52],
        'NOTE2': doc[53],
        'PRJOECTID': doc[54],
        'TMP_PRJOECTID': doc[55],
        'TMP_PRJOECTNAME': doc[56],
        'TMP_PRJOECTENGNAME': doc[57],
        'DIRECTID': doc[58],
        'TMP_DIRECTID': doc[59],
        'PMANAGERID': doc[60],
        'TMP_PMANAGERID': doc[61],
        'APPROVER3ID': doc[62],
        'TMP_APPROVER3ID': doc[63],
        'APPROVER4ID': doc[64],
        'TMP_APPROVER4ID': doc[65],
        'GD1': doc[66],
        'GD2': doc[67],
        'GD3': doc[68],
        'GD4': doc[69],
        'GD5': doc[70],
        'GD6': doc[71],
        'VACATIONTYPEID': doc[72],
        'VACATIONTYPENAME': doc[73],
        'VACATIONTYPEENGNAME': doc[74],
        'CDEPARTID': doc[75],
        'CDEPARTNAME': doc[76],
        'CDEPARTENGNAME': doc[77],
        'insertdate': doc[78],
        'update_date': doc[79],
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
    response = requests.post(api['main_url'], data=data_json, headers=headers)
    result = response.json()

    if result.get('Result'):
        return result.get('SessionGuid')
    else:
        print(result.get('Result'), result.get('Message'))
        return None


def fetch_leave_data(session_id, getdate):
    """Fetch leave records from API"""
    headers = {'Content-type': 'application/json'}
    data = {
        "Action": "ExecReport",
        "SessionGuid": session_id,
        "ProgID": "RATT004",
        "Value": {
            "$type": "AIS.Define.TExecReportInputArgs, AIS.Define",
            "UIType": "Report",
            "ReportID": "",
            "ReportTailID": "",
            "FilterItems": [
                {
                    "$type": "AIS.Define.TFilterItem, AIS.Define",
                    "FieldName": "A.SYS_CompanyID",
                    "FilterValue": "SCS164"
                },
                {
                    "$type": "AIS.Define.TFilterItem, AIS.Define",
                    "FieldName": "IsNull(DT.StartDate, D.StartDate)",
                    "FilterValue": getdate,
                    "ComparisonOperator": "GreaterOrEqual"
                }
            ],
            "UserFilter": ""
        }
    }
    data_json = json.dumps(data)
    response = requests.post(api['api_url'], data=data_json, headers=headers)
    result = response.json()
    return result.get('DataSet', {}).get('ReportBody', [])
