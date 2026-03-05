# -*- coding: utf-8 -*-
"""
HR-HAMS - Access control data import to SCS system
"""
from datetime import datetime

from config import *
from etl_func import (
    get_system_settings, read_hams_db_address, query_hams_swipedata,
    scs_login, get_non_web_swipe_person, import_swipe_data_check,
    get_card_no, sync_card_no, import_swipe_data
)


def run():
    """Main execution function"""
    # Get system settings
    settings = get_system_settings()

    # Login to SCS system
    session_id = scs_login()
    if not session_id:
        print("❌ 無法登入飛騰系統，終止執行")
        return False

    # Get employees who haven't used web check-in
    non_web_swipe = get_non_web_swipe_person(session_id, settings)

    # Read HAMS database addresses
    db_address, hams_address = read_hams_db_address()

    # Get swipe data from HAMS system
    hams_swipedata = query_hams_swipedata(db_address, hams_address, settings)
    hams_swipedata = [row.split(",") for row in hams_swipedata]

    # Process each person who hasn't checked in via web
    for person in non_web_swipe:
        print(f"[飛騰]確認打卡狀態,{person},尚未打卡")
        check = False

        for index in range(len(hams_swipedata)):
            if person in hams_swipedata[index][3]:
                check = True

                # Check if swipe data already imported
                swipe_data_check = import_swipe_data_check(
                    session_id, settings, person, settings['filter_value']
                )

                if swipe_data_check:
                    swipedict = {
                        'SWIPEDATE': swipe_data_check[0]['SWIPEDATE'],
                        'SWIPETIME': swipe_data_check[0]['SWIPETIME'],
                        'CARDNO': swipe_data_check[0]['CARDNO'],
                        'TMP_EMPLOYEENAME': swipe_data_check[0]['TMP_EMPLOYEENAME'],
                        'TMP_EMPLOYEEID': swipe_data_check[0]['TMP_EMPLOYEEID'],
                        'NOTE': swipe_data_check[0]['NOTE'],
                    }
                    print(f"資料已存在!,{swipedict}")
                else:
                    # Check for early/late swipe records
                    swipe_data_check = import_swipe_data_check(
                        session_id, settings, person, settings['filter_value2']
                    )

                    if swipe_data_check:
                        swipedict = {
                            'SWIPEDATE': swipe_data_check[0]['SWIPEDATE'],
                            'SWIPETIME': swipe_data_check[0]['SWIPETIME'],
                            'CARDNO': swipe_data_check[0]['CARDNO'],
                            'TMP_EMPLOYEENAME': swipe_data_check[0]['TMP_EMPLOYEENAME'],
                            'TMP_EMPLOYEEID': swipe_data_check[0]['TMP_EMPLOYEEID'],
                            'NOTE': swipe_data_check[0]['NOTE'],
                        }
                        print(f"資料已存在!,{swipedict}")
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
                        view_id, card_no = get_card_no(session_id, hams_dict)

                        # Skip temporary cards
                        if view_id != 'N' and card_no != 'N':
                            scs_dict = {
                                'ViewID': view_id,
                                'CardNO': card_no,
                            }

                            # Compare card numbers
                            if hams_dict['CardNO'] == scs_dict['CardNO']:
                                print(f"[系統]比對卡號資料,{hams_dict['EmpName']},正確![漢軍:{hams_dict['CardNO']}、飛騰:{scs_dict['CardNO']}]")
                            else:
                                print(f"[系統]比對卡號資料,{hams_dict['EmpName']},不正確![漢軍:{hams_dict['CardNO']}、飛騰:{scs_dict['CardNO']}]")
                                # Sync card number if mismatch
                                sync_card_no(session_id, hams_dict, scs_dict)

                            # Import swipe data
                            import_swipe_data(session_id, hams_dict)

        if not check:
            print(f"[漢軍]查詢刷卡資訊,{person},無刷卡資訊")

    now = str(datetime.now().hour).zfill(2)
    print(f"[系統]{now}點的工作已完成!--------------------------------------------------------")
    return True


if __name__ == '__main__':
    run()
