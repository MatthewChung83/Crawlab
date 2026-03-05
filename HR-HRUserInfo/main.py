# -*- coding: utf-8 -*-
"""
HR-HRUserInfo - User info sync from HR API
"""
import datetime
import urllib3

from config import *
from etl_func import (
    delete_records, toSQL, userinfo_etl,
    login, fetch_userinfo_data
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

    # Fetch user info data
    data = fetch_userinfo_data(session_id)
    if not data:
        print("❌ 無法取得使用者資料")
        return False

    # Process each record
    for item in data:
        result = userinfo_etl(item)
        toSQL(result, totb, server, database, username, password)

    enddate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'人事資料表-結束時間: {enddate}')
    return True


if __name__ == '__main__':
    run()
