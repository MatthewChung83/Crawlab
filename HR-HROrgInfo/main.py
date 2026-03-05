# -*- coding: utf-8 -*-
"""
HR-HROrgInfo - Organization info sync from HR API
"""
import datetime
import urllib3

from config import *
from etl_func import (
    delete_records, toSQL, orginfo_etl,
    login, fetch_orginfo_data
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def run():
    """Main execution function"""
    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']
    totb = db['totb']

    getdate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'人事資料表-起始時間: {getdate}')

    # Clear existing data
    delete_records(server, username, password, database, totb)

    # Login to API
    session_id = login()
    if not session_id:
        print("❌ 無法登入 API，終止執行")
        return False

    # Fetch organization data
    data = fetch_orginfo_data(session_id)
    if not data:
        print("❌ 無法取得組織資料")
        return False

    # Process each record
    for item in data:
        docs = (
            item.get('SYS_VIEWID'),
            item.get('SYS_NAME'),
            item.get('SYS_ENGNAME'),
            item.get('TMP_PDEPARTID'),
            item.get('TMP_PDEPARTNAME'),
            item.get('TMP_PDEPARTENGNAME'),
            item.get('SYS_ID'),
            item.get('TMP_MANAGERID'),
            item.get('TMP_MANAGERNAME'),
            item.get('TMP_MANAGERENGNAME'),
        )
        result = orginfo_etl(docs)
        toSQL(result, totb, server, database, username, password)

    enddate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'人事資料表-結束時間: {enddate}')
    return True


if __name__ == '__main__':
    run()
