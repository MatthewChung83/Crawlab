# -*- coding: utf-8 -*-
"""
HR-EMPLeavetb - Employee leave records sync from HR API
"""
import datetime

from config import *
from etl_func import delete_records, toSQL, empleave_etl, login, fetch_leave_data

# Database parameters
server, database, username, password, totb = (
    db['server'], db['database'], db['username'], db['password'], db['totb']
)

# Get today's date
getdate = str(datetime.date.today()).replace('-', '/')
print(f'請假記錄同步-起始時間: {getdate}')

# Login to API
session_id = login()

if session_id:
    # Fetch leave data
    data = fetch_leave_data(session_id, getdate)

    if data:
        # Delete existing records
        delete_records(server, username, password, database, totb)

        # Process each record
        for i in range(len(data)):
            record = data[i]
            update_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            docs = (
                record.get('LEAVETYPE'),
                record.get('SYS_COMPANYID'),
                record.get('TMP_DECCOMPANYID'),
                record.get('TMP_DECCOMPANYNAME'),
                record.get('TMP_DECCOMPANYENGNAME'),
                record.get('DEPARTID'),
                record.get('DEPARTID2'),
                record.get('DEPARTNAME'),
                record.get('DEPARTENGNAME'),
                record.get('EMPLOYEEID'),
                record.get('EMPLOYEENAME'),
                record.get('SYS_ENGNAME'),
                record.get('SEX'),
                record.get('SYS_VIEWID'),
                record.get('SYS_DATE'),
                record.get('VACATIONID'),
                record.get('VACATIONNAME'),
                record.get('VACATIONENGNAME'),
                record.get('SVACATIONID'),
                record.get('SVACATIONNAME'),
                record.get('SVACATIONENGNAME'),
                record.get('STARTDATE'),
                record.get('STARTTIME'),
                record.get('ENDDATE'),
                record.get('ENDTIME'),
                record.get('LEAVEDAYS'),
                record.get('LEAVEHOURS'),
                record.get('LEAVEMINUTES'),
                record.get('HOURWAGES'),
                record.get('LEAVEMONEY'),
                record.get('AGENTID'),
                record.get('AGENTNAME'),
                record.get('MAINNOTE'),
                record.get('SUBNOTE'),
                record.get('SYS_FLOWFORMSTATUS'),
                record.get('OFFLEAVEDAYS'),
                record.get('OFFLEAVEHOURS'),
                record.get('OFFLEAVEMINUTES'),
                record.get('REALLEAVEDAYS'),
                record.get('REALLEAVEHOURS'),
                record.get('REALLEAVEMINUTES'),
                record.get('CUTDATE'),
                record.get('SPECIALDATE'),
                record.get('STARGETNAME'),
                record.get('SENDDATE'),
                record.get('SOURCETAG'),
                record.get('OUTSIDENAME'),
                record.get('OUTSIDETEL'),
                record.get('ISLEAVE'),
                record.get('ISCOMEBACK'),
                record.get('EMPTEL'),
                record.get('RESTPLACE'),
                record.get('EMPADDRESS'),
                record.get('NOTE2'),
                record.get('PRJOECTID'),
                record.get('TMP_PRJOECTID'),
                record.get('TMP_PRJOECTNAME'),
                record.get('TMP_PRJOECTENGNAME'),
                record.get('DIRECTID'),
                record.get('TMP_DIRECTID'),
                record.get('PMANAGERID'),
                record.get('TMP_PMANAGERID'),
                record.get('APPROVER3ID'),
                record.get('TMP_APPROVER3ID'),
                record.get('APPROVER4ID'),
                record.get('TMP_APPROVER4ID'),
                record.get('GD1'),
                record.get('GD2'),
                record.get('GD3'),
                record.get('GD4'),
                record.get('GD5'),
                record.get('GD6'),
                record.get('VACATIONTYPEID'),
                record.get('VACATIONTYPENAME'),
                record.get('VACATIONTYPEENGNAME'),
                record.get('CDEPARTID'),
                record.get('CDEPARTNAME'),
                record.get('CDEPARTENGNAME'),
                getdate,
                update_date
            )

            empleave_result = empleave_etl(docs)
            toSQL(empleave_result, totb, server, database, username, password)

        print(f'請假記錄同步完成 - 共 {len(data)} 筆')
    else:
        print('無請假資料')
else:
    print('登入失敗')
