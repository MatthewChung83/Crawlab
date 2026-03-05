# -*- coding: utf-8 -*-
"""
HR-Insur_Amount - Insurance amount check and new employee bonus notification
"""
import datetime

from config import *
from etl_func import (
    login, fetch_insurance_records, get_insurance_amount,
    fetch_employee_data, filter_eligible_employees,
    create_email_dataframe, send_notification_email
)


def run():
    """Main execution function"""
    getdate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'保險金額檢查-起始時間: {getdate}')

    # Login to API
    session_id = login()
    if not session_id:
        print("❌ 無法登入 API，終止執行")
        return False

    # Fetch insurance records
    insurance_records = fetch_insurance_records(session_id)
    if not insurance_records:
        print("❌ 無法取得保險記錄")
        return False

    # Get insurance amount from last record
    last_record = insurance_records[-1]
    sys_id = last_record['SYS_ID']
    amount = get_insurance_amount(session_id, sys_id)

    # Fetch employee data
    employees = fetch_employee_data(session_id)
    if not employees:
        print("❌ 無法取得員工資料")
        return False

    # Filter eligible employees
    eligible_employees = filter_eligible_employees(employees)
    print(f"符合條件的人員數: {len(eligible_employees)}")

    # Create DataFrame and send email
    df = create_email_dataframe(eligible_employees)
    send_notification_email(df)

    enddate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'保險金額檢查-結束時間: {enddate}')
    return True


if __name__ == '__main__':
    run()
