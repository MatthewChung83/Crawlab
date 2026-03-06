# -*- coding: utf-8 -*-
"""
HR-HRUserInfo - User info sync from HR API
人事資料同步
"""
import os
import sys
import datetime
import urllib3

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import (
    delete_records, toSQL, userinfo_etl,
    login, fetch_userinfo_data
)
from common.logger import get_logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize logger
logger = get_logger('HR-HRUserInfo')


def run():
    """Main execution function"""
    logger.task_start("人事資料同步")

    total_processed = 0
    total_success = 0
    total_failed = 0

    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']
    totb = db['totb']

    try:
        # Clear existing data
        logger.ctx.set_operation("delete_records")
        logger.ctx.set_db(server=server, database=database, table=totb, operation="DELETE")
        delete_records(server, username, password, database, totb)
        logger.log_db_operation("DELETE", database, totb, 0)

        # Login to API
        logger.ctx.set_operation("api_login")
        session_id = login()
        if not session_id:
            logger.error("無法登入 API，終止執行")
            logger.task_end(success=False)
            return False

        logger.info("API 登入成功")

        # Fetch user info data
        logger.ctx.set_operation("fetch_userinfo_data")
        data = fetch_userinfo_data(session_id)
        if not data:
            logger.error("無法取得使用者資料")
            logger.task_end(success=False)
            return False

        logger.info(f"取得人事資料: {len(data)} 筆")

        # Process each record
        logger.ctx.set_operation("process_records")
        logger.ctx.set_db(server=server, database=database, table=totb, operation="INSERT")

        for i, item in enumerate(data, 1):
            total_processed += 1
            logger.log_progress(total_processed, len(data), f"record_{total_processed}")

            try:
                result = userinfo_etl(item)
                toSQL(result, totb, server, database, username, password)
                total_success += 1
                logger.increment('records_success')
            except Exception as e:
                total_failed += 1
                logger.increment('records_failed')
                logger.warning(f"處理記錄 {i} 時發生錯誤: {e}")
                continue

        logger.log_db_operation("INSERT", database, totb, total_success)

        logger.log_stats({
            'total_records': len(data),
            'total_processed': total_processed,
            'total_success': total_success,
            'total_failed': total_failed,
        })

        logger.task_end(success=(total_failed == 0))
        return total_failed == 0

    except Exception as e:
        logger.log_exception(e, "執行過程發生錯誤")
        logger.task_end(success=False)
        return False


def main():
    """Main entry point"""
    logger.info("HR-HRUserInfo 人事資料同步")

    try:
        success = run()
        if success:
            logger.info("同步完成")
        else:
            logger.warning("同步失敗")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == '__main__':
    main()
