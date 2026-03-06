# -*- coding: utf-8 -*-
"""
HR-Insur_Amount - Insurance amount check and new employee bonus notification
保險金額檢查與新進員工通知
"""
import os
import sys
import datetime

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import (
    login, fetch_insurance_records, get_insurance_amount,
    fetch_employee_data, filter_eligible_employees,
    create_email_dataframe, send_notification_email
)
from common.logger import get_logger

# Initialize logger
logger = get_logger('HR-Insur_Amount')

# 總步驟數
TOTAL_STEPS = 6


def run():
    """Main execution function"""
    logger.task_start("保險金額檢查")

    try:
        # Step 1: Login to API
        logger.log_progress(1, TOTAL_STEPS, "api_login")
        logger.ctx.set_operation("api_login")
        session_id = login()
        if not session_id:
            logger.error("無法登入 API，終止執行")
            logger.task_end(success=False)
            return False

        logger.info("API 登入成功")

        # Step 2: Fetch insurance records
        logger.log_progress(2, TOTAL_STEPS, "fetch_insurance_records")
        logger.ctx.set_operation("fetch_insurance_records")
        insurance_records = fetch_insurance_records(session_id)
        if not insurance_records:
            logger.error("無法取得保險記錄")
            logger.task_end(success=False)
            return False

        logger.info(f"取得保險記錄: {len(insurance_records)} 筆")

        # Step 3: Get insurance amount from last record
        logger.log_progress(3, TOTAL_STEPS, "get_insurance_amount")
        logger.ctx.set_operation("get_insurance_amount")
        last_record = insurance_records[-1]
        sys_id = last_record['SYS_ID']
        logger.ctx.set_data(sys_id=sys_id)
        amount = get_insurance_amount(session_id, sys_id)
        logger.debug(f"保險金額: {amount}")

        # Step 4: Fetch employee data
        logger.log_progress(4, TOTAL_STEPS, "fetch_employee_data")
        logger.ctx.set_operation("fetch_employee_data")
        employees = fetch_employee_data(session_id)
        if not employees:
            logger.error("無法取得員工資料")
            logger.task_end(success=False)
            return False

        logger.info(f"取得員工資料: {len(employees)} 筆")

        # Step 5: Filter eligible employees
        logger.log_progress(5, TOTAL_STEPS, "filter_eligible_employees")
        logger.ctx.set_operation("filter_eligible_employees")
        eligible_employees = filter_eligible_employees(employees)
        logger.info(f"符合條件的人員數: {len(eligible_employees)}")

        # Step 6: Create DataFrame and send email
        logger.log_progress(6, TOTAL_STEPS, "send_notification")
        logger.ctx.set_operation("send_notification")
        df = create_email_dataframe(eligible_employees)
        send_notification_email(df)
        logger.info("通知郵件已發送")

        logger.log_stats({
            'total_insurance_records': len(insurance_records),
            'total_employees': len(employees),
            'eligible_employees': len(eligible_employees),
        })

        logger.task_end(success=True)
        return True

    except Exception as e:
        logger.log_exception(e, "執行過程發生錯誤")
        logger.task_end(success=False)
        return False


def main():
    """Main entry point"""
    logger.info("HR-Insur_Amount 保險金額檢查")

    try:
        success = run()
        if success:
            logger.info("檢查完成")
        else:
            logger.warning("檢查失敗")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == '__main__':
    main()
