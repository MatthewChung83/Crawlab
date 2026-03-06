# -*- coding: utf-8 -*-
"""
HR-HAMS - Access control data import to SCS system
門禁刷卡資料同步
"""
import os
import sys
from datetime import datetime

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import (
    get_system_settings, read_hams_db_address, query_hams_swipedata,
    scs_login, get_non_web_swipe_person, import_swipe_data_check,
    get_card_no, sync_card_no, import_swipe_data
)
from common.logger import get_logger

# Initialize logger
logger = get_logger('HR-HAMS')


def run():
    """Main execution function"""
    logger.task_start("門禁刷卡資料同步")

    total_processed = 0
    total_imported = 0
    total_skipped = 0

    try:
        # Get system settings
        logger.ctx.set_operation("get_settings")
        settings = get_system_settings()
        logger.debug("系統設定載入完成")

        # Login to SCS system
        logger.ctx.set_operation("scs_login")
        session_id = scs_login()
        if not session_id:
            logger.error("無法登入飛騰系統，終止執行")
            logger.task_end(success=False)
            return False

        logger.info("飛騰系統登入成功")

        # Get employees who haven't used web check-in
        logger.ctx.set_operation("get_non_web_swipe")
        non_web_swipe = get_non_web_swipe_person(session_id, settings)
        logger.info(f"尚未打卡人數: {len(non_web_swipe)}")

        # Read HAMS database addresses
        logger.ctx.set_operation("read_hams_db")
        db_address, hams_address = read_hams_db_address()
        logger.debug(f"HAMS 資料庫位址: {db_address}")

        # Get swipe data from HAMS system
        logger.ctx.set_operation("query_hams_swipedata")
        hams_swipedata = query_hams_swipedata(db_address, hams_address, settings)
        hams_swipedata = [row.split(",") for row in hams_swipedata]
        logger.info(f"HAMS 刷卡資料筆數: {len(hams_swipedata)}")

        # Process each person who hasn't checked in via web
        for person in non_web_swipe:
            total_processed += 1
            logger.log_progress(total_processed, len(non_web_swipe), f"person={person}")
            logger.ctx.set_data(person=person)
            logger.debug(f"確認打卡狀態: {person} 尚未打卡")

            check = False

            for index in range(len(hams_swipedata)):
                if person in hams_swipedata[index][3]:
                    check = True

                    # Check if swipe data already imported
                    logger.ctx.set_operation("check_swipe_data")
                    swipe_data_check = import_swipe_data_check(
                        session_id, settings, person, settings['filter_value']
                    )

                    if swipe_data_check:
                        logger.debug(f"資料已存在: {person}")
                        total_skipped += 1
                    else:
                        # Check for early/late swipe records
                        swipe_data_check = import_swipe_data_check(
                            session_id, settings, person, settings['filter_value2']
                        )

                        if swipe_data_check:
                            logger.debug(f"資料已存在 (早晚班): {person}")
                            total_skipped += 1
                        else:
                            # Prepare HAMS data for import
                            hams_dict = {
                                'SwipeDate': hams_swipedata[index][0].replace("/", ""),
                                'SwipeTime': hams_swipedata[index][1].replace(":", "")[0:4] + "00",
                                'CardNO': hams_swipedata[index][2],
                                'EmpName': hams_swipedata[index][3].split('-')[0],
                                'EmpID': hams_swipedata[index][4],
                                'Note': hams_swipedata[index][5],
                            }

                            # Get card number from SCS system
                            logger.ctx.set_operation("get_card_no")
                            view_id, card_no = get_card_no(session_id, hams_dict)

                            # Skip temporary cards
                            if view_id != 'N' and card_no != 'N':
                                scs_dict = {
                                    'ViewID': view_id,
                                    'CardNO': card_no,
                                }

                                # Compare card numbers
                                if hams_dict['CardNO'] == scs_dict['CardNO']:
                                    logger.debug(f"卡號比對正確: {hams_dict['EmpName']}")
                                else:
                                    logger.warning(f"卡號比對不正確: {hams_dict['EmpName']} [漢軍:{hams_dict['CardNO']}、飛騰:{scs_dict['CardNO']}]")
                                    # Sync card number if mismatch
                                    logger.ctx.set_operation("sync_card_no")
                                    sync_card_no(session_id, hams_dict, scs_dict)

                                # Import swipe data
                                logger.ctx.set_operation("import_swipe_data")
                                import_swipe_data(session_id, hams_dict)
                                logger.info(f"匯入刷卡資料: {hams_dict['EmpName']}")
                                total_imported += 1
                                logger.increment('records_success')

            if not check:
                logger.debug(f"查詢刷卡資訊: {person} 無刷卡資訊")

        now = str(datetime.now().hour).zfill(2)
        logger.info(f"{now}點的工作已完成")

        logger.log_stats({
            'total_processed': total_processed,
            'total_imported': total_imported,
            'total_skipped': total_skipped,
        })

        logger.task_end(success=True)
        return True

    except Exception as e:
        logger.log_exception(e, "執行過程發生錯誤")
        logger.task_end(success=False)
        return False


def main():
    """Main entry point"""
    logger.info("HR-HAMS 門禁刷卡資料同步")

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
