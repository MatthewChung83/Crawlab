# -*- coding: utf-8 -*-
"""
HR-EMP_Salary - Employee salary data sync from HR API
"""
import datetime
import logging

from config import *
from etl_func import (
    safe_execute, get_db_connection, get_existing_emp_ids,
    login, fetch_salary_data
)

# Logging setup
LOG_PREFIX = "[EmpSalarySync]"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - " + LOG_PREFIX + " %(message)s"
)
logger = logging.getLogger(__name__)


def process_salary_data(salary_rows, cursor, conn):
    """Process salary data and update database"""
    if not salary_rows:
        logger.warning("沒有可處理的薪資資料")
        return

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

    try:
        existed = get_existing_emp_ids(cursor)

        for r in salary_rows:
            try:
                row = {(k.upper() if isinstance(k, str) else k): v for k, v in r.items()}
                emp_id_raw = row.get("EMPLOYEEID")
                if emp_id_raw is None or str(emp_id_raw).strip() == "":
                    logger.warning(f"略過一筆無 EMPLOYEEID 的資料: {row}")
                    continue

                empi = int(emp_id_raw)
                salary = row.get("TOTALSALARY")
                engname = row.get("EMPLOYEEENGNAME") or None
                cname = row.get("EMPLOYEENAME") or None
                dept = row.get("TMP_DEPARTNAME") or None
                costcenter = row.get("TMP_PROFITID") or None

                if empi in existed:
                    params = (salary, now_str, empi)
                    safe_execute(cursor, update_sql, params)
                    update_count += 1
                else:
                    params = (empi, engname, cname, dept, costcenter, salary, now_str)
                    safe_execute(cursor, insert_sql, params)
                    insert_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"處理 EMPLOYEEID={r.get('EMPLOYEEID')} 發生錯誤: {e}")

        conn.commit()
        logger.info(f"薪資資料同步完成｜總筆數={insert_count + update_count}, 更新={update_count}, 新增={insert_count}, 錯誤={error_count}")

    except Exception as e:
        try:
            if conn:
                conn.rollback()
        except Exception:
            pass
        logger.error(f"薪資資料處理失敗，已回滾：{e}")
        raise


def run():
    """Run the sync process"""
    start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"員工薪資資料同步 - 起始時間: {start_time}")

    conn = None
    cursor = None

    try:
        # Login to API
        session_id = login()
        if not session_id:
            logger.error("終止：API 無法登入")
            return False

        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch salary data
        salary_rows = fetch_salary_data(session_id)
        if not salary_rows:
            logger.error("終止：無法取得薪資資料")
            return False

        # Process data
        process_salary_data(salary_rows, cursor, conn)

        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"員工薪資資料同步 - 結束時間: {end_time}")
        return True

    except Exception as e:
        logger.error(f"同步流程失敗：{e}")
        return False

    finally:
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    ok = run()
    if ok:
        logger.info("任務完成")
    else:
        logger.error("任務失敗")
