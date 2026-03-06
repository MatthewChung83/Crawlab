# -*- coding: utf-8 -*-
"""
HR-EMP_Salary - Employee salary data sync from HR API
員工薪資資料同步
"""
import os
import sys
import datetime

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import (
    safe_execute, get_db_connection, get_existing_emp_ids,
    login, fetch_salary_data
)
from common.logger import get_logger

# Initialize logger
logger = get_logger('HR-Emp_Salary')


def process_salary_data(salary_rows, cursor, conn):
    """Process salary data and update database"""
    if not salary_rows:
        logger.warning("沒有可處理的薪資資料")
        return 0, 0, 0

    update_sql = """
        UPDATE emp
        SET [BaseSalary]=%s, [lastupdate]=%s
        WHERE [empi]=%s
    """
    insert_sql = """
        INSERT INTO emp (
            [empi], [name], [cname], [department], [costcenter],
            [BaseSalary], [lastupdate]
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    insert_count = 0
    update_count = 0
    error_count = 0
    total_records = len(salary_rows)

    try:
        existed = get_existing_emp_ids(cursor)
        logger.info(f"現有員工數: {len(existed)}")

        for idx, r in enumerate(salary_rows, 1):
            logger.log_progress(idx, total_records, f"salary_{idx}")

            try:
                row = {(k.upper() if isinstance(k, str) else k): v for k, v in r.items()}
                emp_id_raw = row.get("EMPLOYEEID")
                if emp_id_raw is None or str(emp_id_raw).strip() == "":
                    logger.warning(f"略過一筆無 EMPLOYEEID 的資料")
                    continue

                empi = int(emp_id_raw)
                salary = row.get("TOTALSALARY")
                engname = row.get("EMPLOYEEENGNAME") or None
                cname = row.get("EMPLOYEENAME") or None
                dept = row.get("TMP_DEPARTNAME") or None
                costcenter = row.get("TMP_PROFITID") or None

                logger.ctx.set_data(empi=empi, cname=cname)

                if empi in existed:
                    logger.ctx.set_operation("update_salary")
                    params = (salary, now_str, empi)
                    safe_execute(cursor, update_sql, params)
                    update_count += 1
                    logger.increment('records_updated')
                else:
                    logger.ctx.set_operation("insert_salary")
                    params = (empi, engname, cname, dept, costcenter, salary, now_str)
                    safe_execute(cursor, insert_sql, params)
                    insert_count += 1
                    logger.increment('records_inserted')

            except Exception as e:
                error_count += 1
                logger.increment('records_failed')
                logger.warning(f"處理 EMPLOYEEID={r.get('EMPLOYEEID')} 發生錯誤: {e}")

        conn.commit()
        logger.info(f"薪資資料處理完成 - 總筆數: {insert_count + update_count}, 更新: {update_count}, 新增: {insert_count}, 錯誤: {error_count}")

        return insert_count, update_count, error_count

    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        logger.log_exception(e, "薪資資料處理失敗，已回滾")
        raise


def run():
    """Run the sync process"""
    logger.task_start("員工薪資資料同步")

    conn = None
    cursor = None

    try:
        # Login to API
        logger.ctx.set_operation("api_login")
        session_id = login()
        if not session_id:
            logger.error("API 無法登入")
            logger.task_end(success=False)
            return False

        logger.info("API 登入成功")

        # Get database connection
        logger.ctx.set_operation("db_connect")
        conn = get_db_connection()
        cursor = conn.cursor()
        logger.debug("資料庫連線成功")

        # Fetch salary data
        logger.ctx.set_operation("fetch_salary_data")
        salary_rows = fetch_salary_data(session_id)
        if not salary_rows:
            logger.error("無法取得薪資資料")
            logger.task_end(success=False)
            return False

        logger.info(f"取得薪資資料: {len(salary_rows)} 筆")

        # Process data
        logger.ctx.set_operation("process_salary_data")
        insert_count, update_count, error_count = process_salary_data(salary_rows, cursor, conn)

        logger.log_stats({
            'total_from_api': len(salary_rows),
            'inserted': insert_count,
            'updated': update_count,
            'errors': error_count,
        })

        logger.task_end(success=(error_count == 0))
        return error_count == 0

    except Exception as e:
        logger.log_exception(e, "同步流程失敗")
        logger.task_end(success=False)
        return False

    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception:
            pass


def main():
    """Main entry point"""
    logger.info("HR-Emp_Salary 員工薪資資料同步")

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


if __name__ == "__main__":
    main()
