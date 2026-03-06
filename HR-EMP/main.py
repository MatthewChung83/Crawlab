# -*- coding: utf-8 -*-
"""
HR-EMP - Employee data sync from HR API to database
員工資料同步
"""
import os
import sys
import datetime

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import (
    get_database_connection, safe_execute, get_existing_employees,
    login, fetch_employee_data, safe_str, get_empstatus, get_leftdate
)
from common.logger import get_logger

# Initialize logger
logger = get_logger('HR-EMP')


def process_employee_data(datatable, existing_employees):
    """處理員工資料並更新資料庫"""
    if not datatable:
        logger.warning("No employee data to process")
        return 0, 0, 0

    insert_count = 0
    update_count = 0
    error_count = 0

    conn = None
    cursor = None
    try:
        conn = get_database_connection()
        cursor = conn.cursor()

        update_sql = """
            UPDATE emp
            SET [name]=%s, [cname]=%s, [department]=%s, [lastupdate]=%s,
                [costcenter]=%s, [empstatus]=%s, [JOBLEVELNAME]=%s,
                [leftdate]=%s, [Company]=%s, [INS_DAT]=%s, [BIRTHDATE]=%s,
                [jobname]=%s, [ext]=%s, [ID]=%s
            WHERE [empi]=%s
        """

        insert_sql = """
            INSERT INTO emp (
              [empi], [name], [cname], [department], [costcenter],
              [empstatus], [JOBLEVELNAME], [leftdate], [Company], [INS_DAT],
              [BIRTHDATE], [jobname], [ext], [ID], [lastupdate]
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_records = len(datatable)

        for idx, raw in enumerate(datatable, 1):
            try:
                logger.log_progress(idx, total_records, f"employee_{idx}")

                # 正規化鍵名 -> 全大寫
                employee_data = {(k.upper() if isinstance(k, str) else k): v for k, v in raw.items()}

                emp_id = int(employee_data.get('SYS_VIEWID'))
                name = safe_str(employee_data.get('SYS_ENGNAME'))
                cname = safe_str(employee_data.get('SYS_NAME'))
                department = safe_str(employee_data.get('TMP_DEPARTNAME'))
                costcenter = safe_str(employee_data.get('TMP_PROFITID'))
                joblevel = safe_str(employee_data.get('TMP_LEVELNAME'))
                company = safe_str(employee_data.get('TMP_DECCOMPANYNAME'))
                ins_dat = safe_str(employee_data.get('STARTDATE'))
                birthdate = safe_str(employee_data.get('BIRTHDATE'))
                jobname = safe_str(employee_data.get('TMP_DUTYNAME'))
                ext = safe_str(employee_data.get('OFFICETEL1'))
                idno = safe_str(employee_data.get('IDNO'))

                raw_status = employee_data.get('JOBSTATUS') or employee_data.get('JOBSTATUS'.upper())
                empstatus = get_empstatus(raw_status)
                leftdate = get_leftdate(empstatus, employee_data)

                logger.ctx.set_data(emp_id=emp_id, cname=cname)

                if emp_id in existing_employees:
                    logger.ctx.set_operation("update_employee")
                    params = (
                        name, cname, department, now_str,
                        costcenter, empstatus, joblevel,
                        leftdate, company, ins_dat, birthdate,
                        jobname, ext, idno, emp_id
                    )
                    safe_execute(cursor, update_sql, params)
                    update_count += 1
                    logger.increment('records_updated')
                else:
                    logger.ctx.set_operation("insert_employee")
                    params = (
                        emp_id, name, cname, department, costcenter,
                        empstatus, joblevel, leftdate, company, ins_dat,
                        birthdate, jobname, ext, idno, now_str
                    )
                    safe_execute(cursor, insert_sql, params)
                    insert_count += 1
                    logger.increment('records_inserted')

            except Exception as e:
                error_count += 1
                logger.increment('records_failed')
                logger.warning(f"Error processing employee {raw.get('SYS_VIEWID', 'unknown')}: {e}")
                continue

        conn.commit()
        logger.info(f'員工資料處理完成 - 總筆數: {update_count + insert_count}, 更新: {update_count}, 新增: {insert_count}, 錯誤: {error_count}')

        return insert_count, update_count, error_count

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.log_exception(e, "Database transaction failed")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def run():
    """執行完整的同步流程"""
    logger.task_start("員工資料同步")

    try:
        # 1. 登入 API
        logger.ctx.set_operation("api_login")
        session_id = login()
        if not session_id:
            logger.error("Failed to login to API")
            logger.task_end(success=False)
            return False

        logger.info("API 登入成功")

        # 2. 取得現有員工資料
        logger.ctx.set_operation("get_existing_employees")
        conn = get_database_connection()
        existing_employees = get_existing_employees(conn)
        conn.close()
        logger.info(f"現有員工數: {len(existing_employees)}")

        # 3. 從 API 取得員工資料
        logger.ctx.set_operation("fetch_employee_data")
        datatable = fetch_employee_data(session_id)
        if not datatable:
            logger.error("No employee data retrieved from API")
            logger.task_end(success=False)
            return False

        logger.info(f"從 API 取得員工資料: {len(datatable)} 筆")

        # 4. 處理並更新資料庫
        logger.ctx.set_operation("process_employee_data")
        insert_count, update_count, error_count = process_employee_data(datatable, existing_employees)

        logger.log_stats({
            'total_from_api': len(datatable),
            'existing_employees': len(existing_employees),
            'inserted': insert_count,
            'updated': update_count,
            'errors': error_count,
        })

        logger.task_end(success=(error_count == 0))
        return error_count == 0

    except Exception as e:
        logger.log_exception(e, "Sync process failed")
        logger.task_end(success=False)
        return False


def main():
    """Main entry point"""
    logger.info("HR-EMP 員工資料同步")

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
