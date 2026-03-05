# -*- coding: utf-8 -*-
"""
HR-EMP_Clockin - Employee clock-in records sync from HR API
"""
import datetime

from config import *
from etl_func import delete_records, toSQL, clockin_records_etl, login, fetch_clockin_data

# Database parameters
server, database, username, password, totb = (
    db['server'], db['database'], db['username'], db['password'], db['totb']
)

# Get today's date
getdate = str(datetime.date.today()).replace('-', '/')
print(getdate)
print(f'打卡記錄同步-起始時間: {getdate}')

# Login to API
session_id = login()

if session_id:
    # Delete existing records
    delete_records(server, username, password, database, totb)

    # Fetch clock-in data
    data = fetch_clockin_data(session_id, getdate)

    # Process each record
    for i in range(len(data)):
        record = data[i]
        update_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        docs = (
            record.get('SYS_ROWID'),
            record.get('SYS_COMPANYID'),
            record.get('TMP_DECCOMPANYID'),
            record.get('TMP_DECCOMPANYNAME'),
            record.get('TMP_DECCOMPANYENGNAME'),
            record.get('DEPARTID'),
            record.get('DEPARTID2'),
            record.get('DEPARTNAME'),
            record.get('DEPARTENGNAME'),
            record.get('SERIAL'),
            record.get('PROFITID'),
            record.get('PROFITNAME'),
            record.get('TMP_EMPLOYEEID'),
            record.get('TMP_EMPLOYEENAME'),
            record.get('TMP_WORKID'),
            record.get('TMP_WORKNAME'),
            record.get('STARTTIME'),
            record.get('ENDTIME'),
            record.get('ATTENDDATE'),
            record.get('WEEKDAY'),
            record.get('CARDNO'),
            record.get('WORKTYPE'),
            record.get('PREARRIVETIME'),
            record.get('PRELATEMINS'),
            record.get('BOVERTIME'),
            record.get('BOVERTIMESTATUS'),
            record.get('BOFFOVERTIME'),
            record.get('BOFFOVERTIMESTATUS'),
            record.get('WORKTIME'),
            record.get('WORKTIMESTATUS'),
            record.get('STATUS'),
            record.get('OFFWORKTIME'),
            record.get('OFFWORKTIMESTATUS'),
            record.get('STATUS2'),
            record.get('AOVERTIME'),
            record.get('AOVERTIMESTATUS'),
            record.get('AOFFOVERTIME'),
            record.get('AOFFOVERTIMESTATUS'),
            record.get('SWORKHOURS'),
            record.get('REALWORKMINUTES'),
            record.get('REALWORKHOURS'),
            record.get('LEAVEHOURS'),
            record.get('OFFLEAVEHOURS'),
            record.get('OVERHOURS'),
            record.get('TOTALHOURS'),
            record.get('DIFFHOURS'),
            record.get('NOTE'),
            record.get('ATTENDDATES'),
            record.get('ISTATUS'),
            record.get('ISTATUS2'),
            record.get('EMPLOYEEID'),
            record.get('WORKID'),
            record.get('DWORKTIME'),
            record.get('DOFFWORKTIME'),
            record.get('GD1'),
            record.get('GD2'),
            record.get('GD3'),
            record.get('GD4'),
            record.get('GD5'),
            record.get('GD6'),
            record.get('LEAVESTARTTIME'),
            record.get('LEAVEENDTIME'),
            record.get('LEAVENAME'),
            record.get('OVERSTARTTIME'),
            record.get('OVERENDTIME'),
            record.get('LEAVEID'),
            record.get('OVERID'),
            record.get('OVERTYPE'),
            record.get('DOOVERTYPE'),
            record.get('LATEMINS'),
            record.get('EARLYMINS'),
            record.get('FORGETTIMES'),
            record.get('VACATIONTYPEID'),
            record.get('GPSLOCATION'),
            record.get('SWNOTE'),
            record.get('GPSADDRESS'),
            record.get('GPSLOCATION2'),
            record.get('SWNOTE2'),
            record.get('GPSADDRESS2'),
            record.get('IPADDRESS'),
            record.get('IPADDRESS2'),
            record.get('SOURCETYPE'),
            record.get('SOURCETYPE2'),
            record.get('JOBCODEID'),
            record.get('JOBCODENAME'),
            record.get('JOBCODE2ID'),
            record.get('JOBCODE2NAME'),
            record.get('JOBLEVELID'),
            record.get('JOBLEVELNAME'),
            record.get('JOBRANKID'),
            record.get('JOBRANKNAME'),
            record.get('JOBTYPEID'),
            record.get('JOBTYPENAME'),
            record.get('JOBCATEGORYID'),
            record.get('JOBCATEGORYNAME'),
            record.get('HASATTENDSUM'),
            record.get('JOBSTATUS2'),
            record.get('PRELATETIMES'),
            record.get('LATETIMES'),
            record.get('EARLYTIMES'),
            update_date
        )

        clockin_result = clockin_records_etl(docs)
        toSQL(clockin_result, totb, server, database, username, password)

    print(f'打卡記錄同步完成 - 共 {len(data)} 筆')
else:
    print('登入失敗')
