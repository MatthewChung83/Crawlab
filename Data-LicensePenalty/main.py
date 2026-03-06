# -*- coding: utf-8 -*-
"""
LicensePenalty crawler - Driver license penalty query
駕照違規查詢
"""
import os
import sys
import re
import time

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import *
from common.logger import get_logger

# Initialize logger
logger = get_logger('Data-LicensePenalty')

# Database and web parameters
server, database, username, password, totb1 = (
    db['server'], db['database'], db['username'], db['password'], db['totb1']
)
url, captchaImg = wbinfo['url'], wbinfo['captchaImg']
imgp = pics['imgp']


def run():
    """Main execution function"""
    logger.task_start("駕照違規查詢")
    logger.log_db_connect(server, database, username)

    total_processed = 0
    total_success = 0
    total_failed = 0
    q = 0

    try:
        # Get record count and source data
        obs = src_obs(server, username, password, database, totb1)
        logger.info(f"待處理筆數: {obs}")

        if obs == 0:
            logger.info("沒有待處理的資料")
            logger.task_end(success=True)
            return True

        src = dbfrom(server, username, password, database, totb1)
        total_records = len(src)
        logger.info(f"取得 {total_records} 筆資料")

        for i in range(total_records):
            logger.log_progress(i + 1, total_records, f"record_{i + 1}")

            try:
                ID = re.sub(r"\s+", "", src[i][3])
                birthday = ('0' + re.sub(r"\s+", "", src[i][4]).replace('/', ''))[-7:]

                logger.ctx.set_data(ID=ID)
                logger.debug(f"處理: ID={ID}, birthday={birthday}")

                # Get captcha and submit query
                logger.ctx.set_operation("query_license")
                start_time = time.time()

                resp = capcha_resp(url, captchaImg, imgp, q, ID, birthday)
                elapsed = time.time() - start_time
                logger.debug(f"查詢完成 ({elapsed:.2f}s)")

                driver_info = resp.find(class_='tb_list_std')
                driver_type, driver_status, DRvaliddate, status, updatetime = (
                    '', '', '', 'N', time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                )

                # Parse result
                logger.ctx.set_operation("parse_result")
                if driver_info:
                    if len(driver_info) == 5:
                        driver_status = resp.find('tbody').find('td').text
                        logger.debug(f"駕照狀態(簡): {driver_status}")
                    else:
                        driver_type = re.sub(r"\s+", "", driver_info.find_all('tr')[1].find_all('td')[0].text)
                        driver_status = re.sub(r"\s+", "", driver_info.find_all('tr')[1].find_all('td')[1].text)
                        DRvaliddate = re.sub(r"\s+", "", driver_info.find_all('tr')[1].find_all('td')[2].text)
                        if '死亡' in driver_status:
                            status = 'Y'
                        logger.debug(f"駕照類型: {driver_type}, 狀態: {driver_status}, 有效期: {DRvaliddate}")
                else:
                    driver_status = '查無汽機車駕照'
                    logger.debug("查無汽機車駕照")

                updatetime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

                # Update database
                logger.ctx.set_operation("DB_update")
                logger.ctx.set_db(server=server, database=database, table=totb1, operation="UPDATE")

                updateSQL(server, username, password, database, totb1, status, updatetime, ID, driver_type, driver_status, DRvaliddate)
                logger.log_db_operation("UPDATE", database, totb1, 1)
                logger.info(f"更新完成: ID={ID}, 類型={driver_type}, 狀態={driver_status}")

                total_success += 1
                total_processed += 1
                logger.increment('records_success')

                # Check exit condition
                ex_obs = exit_obs(server, username, password, database, totb1)
                if ex_obs >= 50000:
                    logger.warning(f"已達上限 ({ex_obs})，結束處理")
                    break

            except Exception as e:
                logger.log_exception(e, f"處理記錄 {i + 1} 時發生錯誤")
                total_failed += 1
                total_processed += 1
                logger.increment('records_failed')
                continue

        logger.log_stats({
            'total_records': total_records,
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
    logger.info(f"資料庫: {db['server']}.{db['database']}")
    logger.info(f"目標資料表: {totb1}")

    try:
        success = run()
        if success:
            logger.info("執行完成")
        else:
            logger.warning("執行過程有錯誤")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == "__main__":
    main()
