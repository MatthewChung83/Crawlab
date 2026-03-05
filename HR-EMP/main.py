# -*- coding: utf-8 -*-
"""
HR-EMP - Employee data sync from HR API to database
"""
import datetime
import logging

from config import *
from etl_func import (
    get_database_connection, safe_execute, get_existing_employees,
    login, fetch_employee_data, safe_str, get_empstatus, get_leftdate
)

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def process_employee_data(datatable, existing_employees):
    """處理員工資料並更新資料庫"""
    if not datatable:
        logger.warning("No employee data to process")
        return

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

        for raw in datatable:
            try:
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

                if emp_id in existing_employees:
                    params = (
                        name, cname, department, now_str,
                        costcenter, empstatus, joblevel,
                        leftdate, company, ins_dat, birthdate,
                        jobname, ext, idno, emp_id
                    )
                    safe_execute(cursor, update_sql, params)
                    update_count += 1
                else:
                    params = (
                        emp_id, name, cname, department, costcenter,
                        empstatus, joblevel, leftdate, company, ins_dat,
                        birthdate, jobname, ext, idno, now_str
                    )
                    safe_execute(cursor, insert_sql, params)
                    insert_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"Error processing employee {raw.get('SYS_VIEWID', 'unknown')}: {e}")
                continue

        conn.commit()
        logger.info(f'員工資料同步完成 - 總筆數: {update_count + insert_count}, 更新: {update_count}, 新增: {insert_count}, 錯誤: {error_count}')

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error(f"Database transaction failed: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def run():
    """執行完整的同步流程"""
    getdate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f'員工資料同步-起始時間: {getdate}')

    try:
        # 1. 登入 API
        session_id = login()
        if not session_id:
            logger.error("Failed to login to API")
            return False

        # 2. 取得現有員工資料
        conn = get_database_connection()
        existing_employees = get_existing_employees(conn)
        conn.close()
        logger.info(f"Found {len(existing_employees)} existing employees in database")

        # 3. 從 API 取得員工資料
        datatable = fetch_employee_data(session_id)
        if not datatable:
            logger.error("No employee data retrieved from API")
            return False

        # 4. 處理並更新資料庫
        process_employee_data(datatable, existing_employees)

        # 5. 記錄結束時間
        end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f'員工資料同步-結束時間: {end_time}')

        return True

    except Exception as e:
        logger.error(f"Sync process failed: {e}")
        return False


if __name__ == "__main__":
    success = run()
    if success:
        logger.info("Employee data sync completed successfully")
    else:
        logger.error("Employee data sync failed")
