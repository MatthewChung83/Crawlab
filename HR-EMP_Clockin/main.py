# -*- coding: utf-8 -*-
"""
HR-EMP_Clockin - Employee clock-in records sync from HR API
員工打卡記錄同步
"""
import os
import sys
import datetime

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import delete_records, toSQL, clockin_records_etl, login, fetch_clockin_data
from common.logger import get_logger

# Initialize logger
logger = get_logger('HR-EMP_Clockin')

# Database parameters
server, database, username, password, totb = (
    db['server'], db['database'], db['username'], db['password'], db['totb']
)


def run():
    """Main execution function"""
    logger.task_start("員工打卡記錄同步")

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

        # Delete existing records
        logger.ctx.set_operation("delete_records")
        logger.ctx.set_db(server=server, database=database, table=totb, operation="DELETE")
        delete_records(server, username, password, database, totb)
        logger.log_db_operation("DELETE", database, totb, 0)

        # Fetch clock-in data
        logger.ctx.set_operation("fetch_clockin_data")
        data = fetch_clockin_data(session_id, getdate)
        logger.info(f"取得打卡資料: {len(data)} 筆")

        if not data:
            logger.info("沒有打卡資料需要同步")
            logger.task_end(success=True)
            return True

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
                    record.get('SYS_ROWID'),
                    record.get('SYS_COMPANYID'),
                    record.get('TMP_DECCOMPANYID'),
                    record.get('TMP_DECCOMPANYNAME'),
                    record.get('TMP_DECCOMPANYENGNAME'),
                    record.get('DEPARTID'),
                    record.get('DEPARTID2'),
                    record.get('DEPARTNAME'),
                    record.get('DEPARTENGNAME'),
                    record.get('SERIAL'),
                    record.get('PROFITID'),
                    record.get('PROFITNAME'),
                    record.get('TMP_EMPLOYEEID'),
                    record.get('TMP_EMPLOYEENAME'),
                    record.get('TMP_WORKID'),
                    record.get('TMP_WORKNAME'),
                    record.get('STARTTIME'),
                    record.get('ENDTIME'),
                    record.get('ATTENDDATE'),
                    record.get('WEEKDAY'),
                    record.get('CARDNO'),
                    record.get('WORKTYPE'),
                    record.get('PREARRIVETIME'),
                    record.get('PRELATEMINS'),
                    record.get('BOVERTIME'),
                    record.get('BOVERTIMESTATUS'),
                    record.get('BOFFOVERTIME'),
                    record.get('BOFFOVERTIMESTATUS'),
                    record.get('WORKTIME'),
                    record.get('WORKTIMESTATUS'),
                    record.get('STATUS'),
                    record.get('OFFWORKTIME'),
                    record.get('OFFWORKTIMESTATUS'),
                    record.get('STATUS2'),
                    record.get('AOVERTIME'),
                    record.get('AOVERTIMESTATUS'),
                    record.get('AOFFOVERTIME'),
                    record.get('AOFFOVERTIMESTATUS'),
                    record.get('SWORKHOURS'),
                    record.get('REALWORKMINUTES'),
                    record.get('REALWORKHOURS'),
                    record.get('LEAVEHOURS'),
                    record.get('OFFLEAVEHOURS'),
                    record.get('OVERHOURS'),
                    record.get('TOTALHOURS'),
                    record.get('DIFFHOURS'),
                    record.get('NOTE'),
                    record.get('ATTENDDATES'),
                    record.get('ISTATUS'),
                    record.get('ISTATUS2'),
                    record.get('EMPLOYEEID'),
                    record.get('WORKID'),
                    record.get('DWORKTIME'),
                    record.get('DOFFWORKTIME'),
                    record.get('GD1'),
                    record.get('GD2'),
                    record.get('GD3'),
                    record.get('GD4'),
                    record.get('GD5'),
                    record.get('GD6'),
                    record.get('LEAVESTARTTIME'),
                    record.get('LEAVEENDTIME'),
                    record.get('LEAVENAME'),
                    record.get('OVERSTARTTIME'),
                    record.get('OVERENDTIME'),
                    record.get('LEAVEID'),
                    record.get('OVERID'),
                    record.get('OVERTYPE'),
                    record.get('DOOVERTYPE'),
                    record.get('LATEMINS'),
                    record.get('EARLYMINS'),
                    record.get('FORGETTIMES'),
                    record.get('VACATIONTYPEID'),
                    record.get('GPSLOCATION'),
                    record.get('SWNOTE'),
                    record.get('GPSADDRESS'),
                    record.get('GPSLOCATION2'),
                    record.get('SWNOTE2'),
                    record.get('GPSADDRESS2'),
                    record.get('IPADDRESS'),
                    record.get('IPADDRESS2'),
                    record.get('SOURCETYPE'),
                    record.get('SOURCETYPE2'),
                    record.get('JOBCODEID'),
                    record.get('JOBCODENAME'),
                    record.get('JOBCODE2ID'),
                    record.get('JOBCODE2NAME'),
                    record.get('JOBLEVELID'),
                    record.get('JOBLEVELNAME'),
                    record.get('JOBRANKID'),
                    record.get('JOBRANKNAME'),
                    record.get('JOBTYPEID'),
                    record.get('JOBTYPENAME'),
                    record.get('JOBCATEGORYID'),
                    record.get('JOBCATEGORYNAME'),
                    record.get('HASATTENDSUM'),
                    record.get('JOBSTATUS2'),
                    record.get('PRELATETIMES'),
                    record.get('LATETIMES'),
                    record.get('EARLYTIMES'),
                    update_date
                )

                clockin_result = clockin_records_etl(docs)
                toSQL(clockin_result, totb, server, database, username, password)
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
    logger.info("HR-EMP_Clockin 員工打卡記錄同步")

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
