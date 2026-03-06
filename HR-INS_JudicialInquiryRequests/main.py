# -*- coding: utf-8 -*-
"""
HR-INS_JudicialInquiryRequests - Judicial inquiry crawler
司法查詢 - 消債、破產、家事監護查詢
Searches consumer debt, bankruptcy, and domestic guardianship records
"""
import os
import sys

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import (
    connect_db, get_pending_requests, mark_request_completed,
    search_consumer_debt, search_bankruptcy, search_domestic_guardianship
)
from common.logger import get_logger

# Initialize logger
logger = get_logger('HR-INS_JudicialInquiryRequests')


def process_requests():
    """Process all pending judicial inquiry requests"""
    total_processed = 0
    total_success = 0
    total_failed = 0

    logger.ctx.set_operation("connect_db")
    conn = connect_db()
    if not conn:
        logger.error("無法連接資料庫")
        return False, 0, 0, 0

    try:
        cursor = conn.cursor(as_dict=True)

        logger.ctx.set_operation("get_pending_requests")
        rows = get_pending_requests(cursor)
        logger.info(f"待處理請求數: {len(rows)}")

        if not rows:
            return True, 0, 0, 0

        for i, row in enumerate(rows, 1):
            total_processed += 1
            logger.log_progress(total_processed, len(rows), f"request_{total_processed}")

            request_id = row['RequestID']
            name = row['Name']
            idno = row['IDNumber']
            remarks = row['Remarks'] if row['Remarks'] else ""

            logger.ctx.set_data(request_id=request_id, name=name)
            logger.debug(f"處理請求: RequestID={request_id}, Name={name}, Remarks={remarks}")

            try:
                # Determine which searches to run based on Remarks
                run_consumer = "消債" in remarks
                run_bankruptcy = "破產" in remarks
                run_domestic = "家事" in remarks

                # If no specific keywords found, run ALL searches
                if not (run_consumer or run_bankruptcy or run_domestic):
                    run_consumer = True
                    run_bankruptcy = True
                    run_domestic = True
                    logger.debug("無特定篩選條件，執行所有查詢")
                else:
                    logger.debug(f"篩選條件 - 消債: {run_consumer}, 破產: {run_bankruptcy}, 家事: {run_domestic}")

                # Run searches
                if run_consumer:
                    logger.ctx.set_operation("search_consumer_debt")
                    search_consumer_debt(name, idno)
                    logger.debug("消債查詢完成")

                if run_bankruptcy:
                    logger.ctx.set_operation("search_bankruptcy")
                    search_bankruptcy(name, idno)
                    logger.debug("破產查詢完成")

                if run_domestic:
                    logger.ctx.set_operation("search_domestic_guardianship")
                    search_domestic_guardianship(name, idno)
                    logger.debug("家事監護查詢完成")

                # Mark as completed
                logger.ctx.set_operation("mark_completed")
                mark_request_completed(cursor, conn, request_id)
                logger.info(f"請求處理完成: RequestID={request_id}")

                total_success += 1
                logger.increment('records_success')

            except Exception as e:
                total_failed += 1
                logger.increment('records_failed')
                logger.warning(f"處理請求 {request_id} 時發生錯誤: {e}")

        return True, total_processed, total_success, total_failed

    except Exception as e:
        logger.log_exception(e, "資料庫處理過程發生錯誤")
        return False, total_processed, total_success, total_failed

    finally:
        conn.close()


def run():
    """Main execution function"""
    logger.task_start("司法查詢")

    try:
        success, total_processed, total_success, total_failed = process_requests()

        logger.log_stats({
            'total_processed': total_processed,
            'total_success': total_success,
            'total_failed': total_failed,
        })

        logger.task_end(success=success and (total_failed == 0))
        return success and (total_failed == 0)

    except Exception as e:
        logger.log_exception(e, "執行過程發生錯誤")
        logger.task_end(success=False)
        return False


def main():
    """Main entry point"""
    logger.info("HR-INS_JudicialInquiryRequests 司法查詢")

    try:
        success = run()
        if success:
            logger.info("查詢完成")
        else:
            logger.warning("查詢失敗")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == "__main__":
    main()
