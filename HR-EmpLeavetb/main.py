# -*- coding: utf-8 -*-
"""
HR-EMPLeavetb - Employee leave records sync from HR API
員工請假記錄同步
"""
import os
import sys
import datetime

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import delete_records, toSQL, empleave_etl, login, fetch_leave_data
from common.logger import get_logger

# Initialize logger
logger = get_logger('HR-EmpLeavetb')

# Database parameters
server, database, username, password, totb = (
    db['server'], db['database'], db['username'], db['password'], db['totb']
)


def run():
    """Main execution function"""
    logger.task_start("員工請假記錄同步")

    total_processed = 0
    total_success = 0
    total_failed = 0

    try:
        # Get today's date
        getdate = str(datetime.date.today()).replace('-', '/')
        logger.info(f"同步日期: {getdate}")

        # Login to API
        logger.ctx.set_operation("api_login")
        session_id = login()

        if not session_id:
            logger.error("API 登入失敗")
            logger.task_end(success=False)
            return False

        logger.info("API 登入成功")

        # Fetch leave data
        logger.ctx.set_operation("fetch_leave_data")
        data = fetch_leave_data(session_id, getdate)

        if not data:
            logger.info("沒有請假資料需要同步")
            logger.task_end(success=True)
            return True

        logger.info(f"取得請假資料: {len(data)} 筆")

        # Delete existing records
        logger.ctx.set_operation("delete_records")
        logger.ctx.set_db(server=server, database=database, table=totb, operation="DELETE")
        delete_records(server, username, password, database, totb)
        logger.log_db_operation("DELETE", database, totb, 0)

        # Process each record
        logger.ctx.set_operation("process_records")
        logger.ctx.set_db(server=server, database=database, table=totb, operation="INSERT")

        for i in range(len(data)):
            total_processed += 1
            logger.log_progress(total_processed, len(data), f"record_{total_processed}")

            try:
                record = data[i]
                update_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                docs = (
                    record.get('LEAVETYPE'),
                    record.get('SYS_COMPANYID'),
                    record.get('TMP_DECCOMPANYID'),
                    record.get('TMP_DECCOMPANYNAME'),
                    record.get('TMP_DECCOMPANYENGNAME'),
                    record.get('DEPARTID'),
                    record.get('DEPARTID2'),
                    record.get('DEPARTNAME'),
                    record.get('DEPARTENGNAME'),
                    record.get('EMPLOYEEID'),
                    record.get('EMPLOYEENAME'),
                    record.get('SYS_ENGNAME'),
                    record.get('SEX'),
                    record.get('SYS_VIEWID'),
                    record.get('SYS_DATE'),
                    record.get('VACATIONID'),
                    record.get('VACATIONNAME'),
                    record.get('VACATIONENGNAME'),
                    record.get('SVACATIONID'),
                    record.get('SVACATIONNAME'),
                    record.get('SVACATIONENGNAME'),
                    record.get('STARTDATE'),
                    record.get('STARTTIME'),
                    record.get('ENDDATE'),
                    record.get('ENDTIME'),
                    record.get('LEAVEDAYS'),
                    record.get('LEAVEHOURS'),
                    record.get('LEAVEMINUTES'),
                    record.get('HOURWAGES'),
                    record.get('LEAVEMONEY'),
                    record.get('AGENTID'),
                    record.get('AGENTNAME'),
                    record.get('MAINNOTE'),
                    record.get('SUBNOTE'),
                    record.get('SYS_FLOWFORMSTATUS'),
                    record.get('OFFLEAVEDAYS'),
                    record.get('OFFLEAVEHOURS'),
                    record.get('OFFLEAVEMINUTES'),
                    record.get('REALLEAVEDAYS'),
                    record.get('REALLEAVEHOURS'),
                    record.get('REALLEAVEMINUTES'),
                    record.get('CUTDATE'),
                    record.get('SPECIALDATE'),
                    record.get('STARGETNAME'),
                    record.get('SENDDATE'),
                    record.get('SOURCETAG'),
                    record.get('OUTSIDENAME'),
                    record.get('OUTSIDETEL'),
                    record.get('ISLEAVE'),
                    record.get('ISCOMEBACK'),
                    record.get('EMPTEL'),
                    record.get('RESTPLACE'),
                    record.get('EMPADDRESS'),
                    record.get('NOTE2'),
                    record.get('PRJOECTID'),
                    record.get('TMP_PRJOECTID'),
                    record.get('TMP_PRJOECTNAME'),
                    record.get('TMP_PRJOECTENGNAME'),
                    record.get('DIRECTID'),
                    record.get('TMP_DIRECTID'),
                    record.get('PMANAGERID'),
                    record.get('TMP_PMANAGERID'),
                    record.get('APPROVER3ID'),
                    record.get('TMP_APPROVER3ID'),
                    record.get('APPROVER4ID'),
                    record.get('TMP_APPROVER4ID'),
                    record.get('GD1'),
                    record.get('GD2'),
                    record.get('GD3'),
                    record.get('GD4'),
                    record.get('GD5'),
                    record.get('GD6'),
                    record.get('VACATIONTYPEID'),
                    record.get('VACATIONTYPENAME'),
                    record.get('VACATIONTYPEENGNAME'),
                    record.get('CDEPARTID'),
                    record.get('CDEPARTNAME'),
                    record.get('CDEPARTENGNAME'),
                    getdate,
                    update_date
                )

                empleave_result = empleave_etl(docs)
                toSQL(empleave_result, totb, server, database, username, password)
                total_success += 1
                logger.increment('records_success')

            except Exception as e:
                total_failed += 1
                logger.increment('records_failed')
                logger.warning(f"處理記錄 {i+1} 時發生錯誤: {e}")
                continue

        logger.log_db_operation("INSERT", database, totb, total_success)

        logger.log_stats({
            'sync_date': getdate,
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
    logger.info("HR-EmpLeavetb 員工請假記錄同步")

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
