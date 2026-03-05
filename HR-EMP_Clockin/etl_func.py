# -*- coding: utf-8 -*-
"""
ETL functions for HR-EMP_Clockin - Employee clock-in records sync
"""
import json
import requests
import pymssql

from config import db, api


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
    with pymssql.connect(server=server, user=username, password=password, database=database) as cnxn:
        cnxn.autocommit(False)
        with cnxn.cursor() as cursor:
            data_keys = ','.join(docs[0].keys())
            data_symbols = ','.join(['%s' for _ in range(len(docs[0].keys()))])
            insert_cmd = f"INSERT INTO {totb} ({data_keys}) VALUES ({data_symbols})"
            data_values = [tuple(doc.values()) for doc in docs]
            cursor.executemany(insert_cmd, data_values)
            cnxn.commit()


def clockin_records_etl(doc):
    """Transform clock-in record data"""
    return [{
        'SYS_ROWID': doc[0],
        'SYS_COMPANYID': doc[1],
        'TMP_DECCOMPANYID': doc[2],
        'TMP_DECCOMPANYNAME': doc[3],
        'TMP_DECCOMPANYENGNAME': doc[4],
        'DEPARTID': doc[5],
        'DEPARTID2': doc[6],
        'DEPARTNAME': doc[7],
        'DEPARTENGNAME': doc[8],
        'SERIAL': doc[9],
        'PROFITID': doc[10],
        'PROFITNAME': doc[11],
        'TMP_EMPLOYEEID': doc[12],
        'TMP_EMPLOYEENAME': doc[13],
        'TMP_WORKID': doc[14],
        'TMP_WORKNAME': doc[15],
        'STARTTIME': doc[16],
        'ENDTIME': doc[17],
        'ATTENDDATE': doc[18],
        'WEEKDAY': doc[19],
        'CARDNO': doc[20],
        'WORKTYPE': doc[21],
        'PREARRIVETIME': doc[22],
        'PRELATEMINS': doc[23],
        'BOVERTIME': doc[24],
        'BOVERTIMESTATUS': doc[25],
        'BOFFOVERTIME': doc[26],
        'BOFFOVERTIMESTATUS': doc[27],
        'WORKTIME': doc[28],
        'WORKTIMESTATUS': doc[29],
        'STATUS': doc[30],
        'OFFWORKTIME': doc[31],
        'OFFWORKTIMESTATUS': doc[32],
        'STATUS2': doc[33],
        'AOVERTIME': doc[34],
        'AOVERTIMESTATUS': doc[35],
        'AOFFOVERTIME': doc[36],
        'AOFFOVERTIMESTATUS': doc[37],
        'SWORKHOURS': doc[38],
        'REALWORKMINUTES': doc[39],
        'REALWORKHOURS': doc[40],
        'LEAVEHOURS': doc[41],
        'OFFLEAVEHOURS': doc[42],
        'OVERHOURS': doc[43],
        'TOTALHOURS': doc[44],
        'DIFFHOURS': doc[45],
        'NOTE': doc[46],
        'ATTENDDATES': doc[47],
        'ISTATUS': doc[48],
        'ISTATUS2': doc[49],
        'EMPLOYEEID': doc[50],
        'WORKID': doc[51],
        'DWORKTIME': doc[52],
        'DOFFWORKTIME': doc[53],
        'GD1': doc[54],
        'GD2': doc[55],
        'GD3': doc[56],
        'GD4': doc[57],
        'GD5': doc[58],
        'GD6': doc[59],
        'LEAVESTARTTIME': doc[60],
        'LEAVEENDTIME': doc[61],
        'LEAVENAME': doc[62],
        'OVERSTARTTIME': doc[63],
        'OVERENDTIME': doc[64],
        'LEAVEID': doc[65],
        'OVERID': doc[66],
        'OVERTYPE': doc[67],
        'DOOVERTYPE': doc[68],
        'LATEMINS': doc[69],
        'EARLYMINS': doc[70],
        'FORGETTIMES': doc[71],
        'VACATIONTYPEID': doc[72],
        'GPSLOCATION': doc[73],
        'SWNOTE': doc[74],
        'GPSADDRESS': doc[75],
        'GPSLOCATION2': doc[76],
        'SWNOTE2': doc[77],
        'GPSADDRESS2': doc[78],
        'IPADDRESS': doc[79],
        'IPADDRESS2': doc[80],
        'SOURCETYPE': doc[81],
        'SOURCETYPE2': doc[82],
        'JOBCODEID': doc[83],
        'JOBCODENAME': doc[84],
        'JOBCODE2ID': doc[85],
        'JOBCODE2NAME': doc[86],
        'JOBLEVELID': doc[87],
        'JOBLEVELNAME': doc[88],
        'JOBRANKID': doc[89],
        'JOBRANKNAME': doc[90],
        'JOBTYPEID': doc[91],
        'JOBTYPENAME': doc[92],
        'JOBCATEGORYID': doc[93],
        'JOBCATEGORYNAME': doc[94],
        'HASATTENDSUM': doc[95],
        'JOBSTATUS2': doc[96],
        'PRELATETIMES': doc[97],
        'LATETIMES': doc[98],
        'EARLYTIMES': doc[99],
        'insertdate': doc[100],
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


def fetch_clockin_data(session_id, getdate):
    """Fetch clock-in records from API"""
    headers = {'Content-type': 'application/json'}
    data = {
        "Action": "ExecReport",
        "SessionGuid": session_id,
        "ProgID": "RATT017",
        "Value": {
            "$type": "AIS.Define.TExecReportInputArgs, AIS.Define",
            "UIType": "Report",
            "ReportID": "",
            "ReportTailID": "",
            "FilterItems": [
                {
                    "$type": "AIS.Define.TFilterItem, AIS.Define",
                    "FieldName": "@COMPANYID",
                    "FilterValue": "SCS164"
                },
                {
                    "$type": "AIS.Define.TFilterItem, AIS.Define",
                    "FieldName": "@STARTDATE",
                    "FilterValue": getdate
                },
                {
                    "$type": "AIS.Define.TFilterItem, AIS.Define",
                    "FieldName": "@ENDDATE",
                    "FilterValue": getdate
                }
            ],
            "UserFilter": ""
        }
    }
    data_json = json.dumps(data)
    response = requests.post(api['api_url'], data=data_json, headers=headers)
    result = response.json()
    return result.get('DataSet', {}).get('ReportBody', [])
