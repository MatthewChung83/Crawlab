# -*- coding: utf-8 -*-
"""
ETL functions for HR-HAMS - Access control data import
"""
import subprocess
from datetime import datetime, timedelta
from json import dumps
from requests import get, post
import urllib3

from config import db, api

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_system_settings():
    """Get system settings based on current time"""
    # 晚上10點至隔日0點執行下班卡匯入(刷卡紀錄最後一筆)
    # 其餘時間執行上班卡匯入(刷卡紀錄第一筆)
    if datetime.now().hour >= 22:
        today = datetime.now().strftime("%Y/%m/%d")
        filter_value = "5"
        work = "DESC"
        filter_value2 = "2"
    elif datetime.now().hour == 0:
        today = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
        filter_value = "5"
        work = "DESC"
        filter_value2 = "2"
    else:
        today = datetime.now().strftime("%Y/%m/%d")
        filter_value = "4"
        work = "ASC"
        filter_value2 = "1"

    return {
        'today': today,
        'filter_value': filter_value,
        'work': work,
        'filter_value2': filter_value2
    }


def read_hams_db_address():
    """Read HAMS database address from config file"""
    file_path = db['hams_db_file']
    with open(file_path, "r", encoding="utf-8") as r:
        txt_content = r.readlines()
    return txt_content[0].strip(), txt_content[1].strip()


def query_hams_swipedata(db_address, hams_address, settings):
    """Query swipe data from HAMS Access database using mdbtools"""
    try:
        today_date = settings['today']
        command = ["mdb-export", db_address, "PubEvent"]
        output = subprocess.run(command, capture_output=True, text=True)

        pub_events = []
        is_first_row = True
        for row in output.stdout.strip().split("\n"):
            columns = row.split(",")
            if is_first_row:
                is_first_row = False
                continue

            raw_event_date = columns[2].strip().strip('"')

            try:
                event_date = datetime.strptime(raw_event_date, "%Y/%m/%d").strftime("%Y/%m/%d")
            except ValueError:
                print(f"⚠️ 無法解析 eventDate: {repr(columns[2])}，跳過此行")
                continue

            if event_date == today_date:
                pub_events.append(columns)

        # 匯出 Emp 資料
        command = ["mdb-export", hams_address, "Emp"]
        output = subprocess.run(command, capture_output=True, text=True)

        emp_data = {}
        is_first_row = True
        for row in output.stdout.strip().split("\n"):
            columns = row.split(",")
            if is_first_row:
                is_first_row = False
                continue
            emp_data[columns[1]] = columns

        # 合併資料
        joined_data = []
        for event in pub_events:
            person_id = event[6]
            if person_id in emp_data:
                emp = emp_data[person_id]
                joined_data.append((
                    event[2].strip().strip('"'),
                    event[3].strip().strip('"'),
                    event[5].strip().strip('"'),
                    event[22].strip().strip('"'),
                    emp[3].strip().strip('"'),
                    event[11].strip().strip('"')
                ))

        # 按照「員工姓名」分組，取得第一筆或最後一筆
        employee_swipes = {}
        for record in joined_data:
            emp_name = record[3]
            if emp_name not in employee_swipes:
                employee_swipes[emp_name] = record
            else:
                if settings['work'] == "ASC":
                    if record[1] < employee_swipes[emp_name][1]:
                        employee_swipes[emp_name] = record
                else:
                    if record[1] > employee_swipes[emp_name][1]:
                        employee_swipes[emp_name] = record

        selected_records = [",".join(employee_swipes[name]) for name in employee_swipes]
        print(f"✅ 依員工姓名分組的刷卡紀錄: {selected_records}")
        return selected_records

    except Exception as e:
        print(f"❌ [漢軍] 透過 mdbtools 取得刷卡資料發生錯誤! [{e}]")
        return []


def scs_login(user=None, pw=None):
    """Login to SCS system and return session ID"""
    user = user or api['default_user']
    pw = pw or api['default_password']

    headers = {'Content-type': 'application/json'}
    data = {
        "Action": "Login",
        "Value": {
            "$type": "AIS.Define.TLogingInputArgs, AIS.Define",
            "CompanyID": api['company_id'],
            "UserID": user,
            "Password": pw,
            "LanguageID": api['language_id']
        }
    }
    data_json = dumps(data)
    response = post(api['main_url'], data=data_json, headers=headers, verify=False)
    result = response.json()

    if result.get('SessionGuid'):
        print(f"連接飛騰系統,成功!")
        return result['SessionGuid']
    else:
        print(f"連接飛騰系統,失敗! err: {result.get('Result')},{result.get('Message')}")
        return None


def scs_api_request(session_id, json_data):
    """Make API request to SCS system"""
    response = get(api['api_url'], json=json_data, verify=False)
    return response.json().get('DataTable', [])


def get_emp_table(session_id):
    """Get employee table from SCS"""
    try:
        json_data = {
            "Action": "Find",
            "SessionGuid": session_id,
            "ProgID": "HUM0020100",
            "Value": {
                "$type": "AIS.Define.TFindInputArgs, AIS.Define",
                "SelectFields": "SYS_VIEWID,SYS_NAME,SYS_ENGNAME,TMP_DEPARTID,TMP_DEPARTNAME,SeparationDate",
                "Parameters": [],
                "FilterItems": [
                    {
                        "$type": "AIS.Define.TFilterItem, AIS.Define",
                        "FieldName": "JobStatus",
                        "FilterValue": "1,3",
                        "ComparisonOperator": "Between"
                    }
                ],
                "SystemFilterOptions": "Default",
                "IsBuildSelectedField": True,
                "IsBuildFlowLightSignalField": True
            }
        }
        data = scs_api_request(session_id, json_data)
        return [d['SYS_NAME'] for d in data]
    except Exception as e:
        print(f"[飛騰]查詢員工資料,發生錯誤![{e}]")
        return []


def get_web_swipe_person(session_id, settings):
    """Get employees who used web check-in"""
    try:
        json_data = {
            "Action": "Find",
            "SessionGuid": session_id,
            "ProgID": "ATT0021501",
            "Value": {
                "$type": "AIS.Define.TFindInputArgs, AIS.Define",
                "SelectFields": "*",
                "Parameters": [],
                "FilterItems": [
                    {
                        "$type": "AIS.Define.TFilterItem, AIS.Define",
                        "FieldName": "DUTYSTATUS",
                        "FilterValue": settings['filter_value']
                    },
                    {
                        "$type": "AIS.Define.TFilterItem, AIS.Define",
                        "FieldName": "SwipeTime",
                        "FilterValue": settings['today']
                    }
                ],
                "SystemFilterOptions": "All",
                "IsBuildVirtualField": True
            }
        }
        data = scs_api_request(session_id, json_data)
        webswipe_person = []
        for d in data:
            if d['TMP_EMPLOYEENAME'] not in webswipe_person:
                webswipe_person.append(d['TMP_EMPLOYEENAME'])
                webswipe_person.append(d['SWIPETIME'])
        return webswipe_person
    except Exception as e:
        print(f"[飛騰]查詢打卡狀態,發生錯誤![{e}]")
        return []


def get_non_web_swipe_person(session_id, settings):
    """Get employees who haven't used web check-in"""
    emp_table = get_emp_table(session_id)
    web_swipe_person = get_web_swipe_person(session_id, settings)

    status = "上" if settings['filter_value'] in ("4", "1") else "下"

    for i in range(0, len(web_swipe_person), 2):
        if web_swipe_person[i] in emp_table:
            emp_table.remove(web_swipe_person[i])
            print(f"[飛騰]確認打卡狀態,{web_swipe_person[i]},已打卡{status}班[{web_swipe_person[i+1]}]")

    return emp_table


def import_swipe_data_check(session_id, settings, person, filter_value):
    """Check if swipe data already imported"""
    try:
        if filter_value in ('2', '5'):
            return None

        json_data = {
            "Action": "Find",
            "SessionGuid": session_id,
            "ProgID": "ATT0021500",
            "Value": {
                "$type": "AIS.Define.TFindInputArgs, AIS.Define",
                "SelectFields": "*",
                "Parameters": [],
                "FilterItems": [
                    {
                        "$type": "AIS.Define.TFilterItem, AIS.Define",
                        "FieldName": "SWIPEDATE",
                        "FilterValue": settings['today']
                    },
                    {
                        "$type": "AIS.Define.TFilterItem, AIS.Define",
                        "FieldName": "SourceType",
                        "FilterValue": "0"
                    },
                    {
                        "$type": "AIS.Define.TFilterItem, AIS.Define",
                        "FieldName": "DUTYSTATUS",
                        "FilterValue": filter_value
                    },
                    {
                        "$type": "AIS.Define.TFilterItem, AIS.Define",
                        "FieldName": "TMP_EmployeeName",
                        "FilterValue": person
                    }
                ],
                "SystemFilterOptions": "All",
                "IsBuildVirtualField": True
            }
        }
        return scs_api_request(session_id, json_data)
    except Exception as e:
        print(f"[飛騰]檢查匯入資料,{person}:發生錯誤![{e}]")
        return None


def get_card_no(session_id, hams_dict):
    """Get card number from SCS system"""
    try:
        if hams_dict['EmpID'][0] == '9':
            return 'N', 'N'

        json_data = {
            "Action": "Find",
            "SessionGuid": session_id,
            "ProgID": "ATT0021150",
            "Value": {
                "$type": "AIS.Define.TFindInputArgs, AIS.Define",
                "SelectFields": "SYS_ViewID,TMP_EmployeeID,TMP_EmployeeName,CARDNO",
                "Parameters": [],
                "FilterItems": [
                    {
                        "$type": "AIS.Define.TFilterItem, AIS.Define",
                        "FieldName": "SYS_COMPANYID",
                        "FilterValue": "SCS164"
                    },
                    {
                        "$type": "AIS.Define.TFilterItem, AIS.Define",
                        "FieldName": "TMP_EmployeeID",
                        "FilterValue": hams_dict['EmpID']
                    }
                ],
                "SystemFilterOptions": "Default",
                "IsBuildSelectedField": True,
                "IsBuildFlowLightSignalField": True
            }
        }
        data = scs_api_request(session_id, json_data)
        return data[0]['SYS_VIEWID'], data[0]['CARDNO']
    except Exception as e:
        print(f"[飛騰]查詢員工卡號,{hams_dict['EmpName']}:發生錯誤![{e}]")
        return 'N', 'N'


def sync_card_no(session_id, hams_dict, scs_dict):
    """Sync card number to SCS system"""
    try:
        json_data = {
            "Action": "Import",
            "SessionGuid": session_id,
            "ProgID": "ATT0021150",
            "Value": {
                "$type": "AIS.Define.TSaveInputArgs, AIS.Define",
                "DataSet": {
                    "ATT0021150": [
                        {
                            "SYS_VIEWID": scs_dict['ViewID'],
                            "UserNo": hams_dict['EmpID'],
                            "TMP_EMPLOYEENAME": hams_dict['EmpName'],
                            "ISSIGN": True,
                            "CARDNO": hams_dict['CardNO'],
                            "NOTE": ""
                        }
                    ]
                },
            }
        }
        get(api['api_url'], json=json_data, verify=False)
        print(f"[系統]同步卡號資訊,{hams_dict['EmpName']},卡號:{scs_dict['CardNO']} 更新為 {hams_dict['CardNO']}")
    except Exception as e:
        print(f"[系統]同步卡號資訊,{hams_dict['EmpName']},發生錯誤![{e}]")


def import_swipe_data(session_id, hams_dict):
    """Import swipe data to SCS system"""
    try:
        json_data = {
            "Action": "ExecFunc",
            "SessionGuid": session_id,
            "ProgID": "ATT0021400",
            "Value": {
                "$type": "AIS.Define.TExecFuncInputArgs, AIS.Define",
                "FuncID": "ImportSwipeData_WS_JSON",
                "Parameters": [
                    {
                        "$type": "AIS.Define.TParameter, AIS.Define",
                        "Name": "ImportSwipeTable",
                        "Value": [
                            {
                                "EmployeeID": hams_dict['EmpID'],
                                "CardNO": hams_dict['CardNO'],
                                "SwipeDate": hams_dict['SwipeDate'],
                                "SwipeTime": hams_dict['SwipeTime'],
                                "Note": hams_dict['Note'],
                            }
                        ]
                    }
                ]
            }
        }
        r = get(api['api_url'], json=json_data, verify=False)
        print(r.json())
        print(f"[系統]匯入刷卡資料,{hams_dict['EmpName']},{hams_dict}")
    except Exception as e:
        print(f"[系統]匯入刷卡資料,{hams_dict['EmpName']}:發生錯誤![{e}]")
