################################
# Author: Ping
# Description: 門禁資料匯入飛騰系統
# Date: 2023-09-11
# LastEditTime: 2024-03-05
################################
from requests import get, post
from datetime import datetime, timedelta
from json import dumps
import urllib3
import subprocess
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
################################
# FilterValue說明
# 0:無法辨識
# 1:上班前加班上班(提早於上班時間前30分鐘以上打卡)
# 2:上班前加班下班(晚於下班時間後30分鐘以上打卡)
# 4:上班
# 5:下班
# 7:加班上班
# 8:加班下班
################################


class System():
    def __init__(self):
        ################################
        # 依照排程執行時間
        # 晚上10點至隔日0點執行下班卡匯入(刷卡紀錄最後一筆)
        # 其餘時間執行上班卡匯入(刷卡紀錄第一筆)
        ################################
        if datetime.now().hour >= 22:
        #if datetime.now().hour < 22:
            self.today = datetime.now().strftime("%Y/%m/%d")
            #self.today = "2026/01/21"
            self.FilterValue = "5"
            self.work = "DESC"
            self.FilterValue2 = "2"
        elif datetime.now().hour == 0:
            self.today = (datetime.now()-timedelta(days=1)
                          ).strftime("%Y/%m/%d")
            self.FilterValue = "5"
            self.work = "DESC"
            self.FilterValue2 = "2"
        else:
            self.today = datetime.now().strftime("%Y/%m/%d")
            #self.today = "2026/01/14"
            self.FilterValue = "4"
            self.work = "ASC"
            self.FilterValue2 = "1"
    #寫Log
    #def writeLog(self, logstr):
    #    today = self.today.replace("/", "")
    #    swipedata = f"\\\\unt15\IT\Script\Log\HAMS_to_SCS\Import_SwipeData\{today}.txt"
    #    now = datetime.now().strftime("%Y/%m/%d,%H:%M:%S")
    #    with open(swipedata, 'a', encoding="big5", errors='ignore') as w:
    #        w.write(f"{now},{logstr}\n")

import subprocess
from datetime import datetime

#漢軍門禁系統
class HAMS():
    def __init__(self):
        """初始化，讀取 Access 資料庫 (`.mdb`) 位址"""
        file_path = "./HAMS_db_address.txt"  # 你的 `.mdb` 路徑設定檔
        with open(file_path, "r", encoding="utf-8") as r:
            txtContent = r.readlines()
        
        self.db_address = txtContent[0].strip()
        self.hams_address = txtContent[1].strip()
        self.card_data = []
        self.swipe_data = []
        self.today = MAIN_System.today

    def query_HAMSdb_swipedata(self):
        """使用 mdbtools 讀取 `.mdb` 資料，並取得每位員工的第一筆或最後一筆刷卡紀錄"""
        try:
            today_date = MAIN_System.today  # 取得今天日期
            command = ["mdb-export", self.db_address, "PubEvent"]
            output = subprocess.run(command, capture_output=True, text=True)

            pub_events = []
            is_first_row = True
            for row in output.stdout.strip().split("\n"):
                columns = row.split(",")
                if is_first_row:
                    is_first_row = False
                    continue

                raw_event_date = columns[2].strip().strip('"')

                # **確認 `eventDate` 是否為有效日期**
                try:
                    event_date = datetime.strptime(raw_event_date, "%Y/%m/%d").strftime("%Y/%m/%d")
                except ValueError:
                    print(f"⚠️ 無法解析 eventDate: {repr(columns[2])}，跳過此行")
                    continue  
                
                if event_date == today_date:  # 只篩選今天的刷卡資料
                    pub_events.append(columns)

            # 匯出 `Emp` 資料
            command = ["mdb-export", self.hams_address, "Emp"]
            output = subprocess.run(command, capture_output=True, text=True)

            emp_data = {}
            is_first_row = True  
            for row in output.stdout.strip().split("\n"):
                columns = row.split(",")
                if is_first_row:
                    is_first_row = False
                    continue
                emp_data[columns[1]] = columns  

            # **合併資料**
            joined_data = []
            for event in pub_events:
                person_id = event[6]  # `personID`
                if person_id in emp_data:
                    emp = emp_data[person_id]
                    joined_data.append((
                        event[2].strip().strip('"'),  # 刷卡日期
                        event[3].strip().strip('"'),  # 刷卡時間
                        event[5].strip().strip('"'),  # 員工卡號
                        event[22].strip().strip('"'),  # 員工姓名
                        emp[3].strip().strip('"'),    # 員工 ID
                        event[11].strip().strip('"')   # 裝置名稱
                    ))
            #print(joined_data)
            #print(self.today,MAIN_System.FilterValue)
            #if MAIN_System.FilterValue == "5" and self.today =='2025/08/29':
            #joined_data.append(('2026/03/05', '08:59:59', '3931813486',  '鍾孟修', '5043',''))

            # **按照「員工姓名」分組，取得第一筆或最後一筆**
            employee_swipes = {}
            for record in joined_data:
                emp_name = record[3]  # 員工姓名
                if emp_name not in employee_swipes:
                    employee_swipes[emp_name] = record  # 設定第一筆資料
                else:
                    # **根據設定選擇 第一筆 / 最後一筆**
                    if MAIN_System.work == "ASC":  # 取第一筆（最早的刷卡）
                        if record[1] < employee_swipes[emp_name][1]:
                            employee_swipes[emp_name] = record
                    else:  # `work == "DESC"` 取最後一筆（最晚的刷卡）
                        if record[1] > employee_swipes[emp_name][1]:
                            employee_swipes[emp_name] = record

            # 轉成列表格式
            selected_records = [",".join(employee_swipes[name]) for name in employee_swipes]

            print(f"✅ 依員工姓名分組的刷卡紀錄 (依設定選擇第一/最後一筆): {selected_records}")  # Debug 用
            return selected_records  # 回傳符合格式的資料

        except Exception as e:
            print(f"❌ [漢軍] 透過 mdbtools 取得刷卡資料發生錯誤! [{e}]")
            return []



#飛騰系統
class SCS():
    #登入取得SessionGuid，用於後續API操作
    def __init__(self, user='IT1600', pw='23756020'):
        self.api_url = "https://hr.ucs.tw/SCSRwd/api/businessobject/"
        self.SenssionID = ''
        url = 'https://hr.ucs.tw/SCSRwd/api/systemobject/'
        headers = {'Content-type': 'application/json'}
        data = {
            "Action": "Login",
            "Value": {
                "$type": "AIS.Define.TLogingInputArgs, AIS.Define",
                "CompanyID": "scs164",
                "UserID": user,
                "Password": pw,
                "LanguageID": "zh-TW"
            }
        }
        data_json = dumps(data)
        response = post(url, data=data_json, headers=headers, verify=False)
        result = response.json()
        if result['SessionGuid']:
            self.SenssionID = result['SessionGuid']
            #MAIN_System.writeLog(f"連接飛騰系統,成功!")
            print(f"連接飛騰系統,成功!")
        else:
            self.SenssionID = None
            #MAIN_System.writeLog(
            #    f"連接飛騰系統,失敗!'err: ',{result.get('Result')},{result.get('Message')}")
            print(f"連接飛騰系統,失敗!'err: ',{result.get('Result')},{result.get('Message')}")

    #重複的語法寫成一個function叫用，這個function不寫也可以
    def result(self, json_data):
        response = get(self.api_url, json=json_data, verify=False)
        response_json = response.json()
        data = response_json['DataTable']
        return data

    ################################
    # JobStatus說明
    # 0:未就職
    # 1:試用
    # 2:正式
    # 3:約聘
    # 4:留職停薪
    # 5:離職
    ################################
    #取得在職狀態介於1~3之人員
    def get_empTable(self):
        try:
            json_data = {
                "Action": "Find",
                "SessionGuid": self.SenssionID,
                "ProgID": "HUM0020100",
                "Value": {
                    "$type": "AIS.Define.TFindInputArgs, AIS.Define",
                    "SelectFields": "SYS_VIEWID,SYS_NAME,SYS_ENGNAME,TMP_DEPARTID,TMP_DEPARTNAME,SeparationDate",
                    "Parameters": [],
                    "FilterItems": [
                        {
                            "$type": "AIS.Define.TFilterItem, AIS.Define",
                            "FieldName": "JobStatus",#詳見"JobStatus說明"
                            "FilterValue": "1,3",
                            "ComparisonOperator": "Between"
                        }
                    ],
                    "SystemFilterOptions": "Default",
                    "IsBuildSelectedField": True,
                    "IsBuildFlowLightSignalField": True
                }
            }
            data = self.result(json_data)
            empTable = []
            for i in range(len(data)):
                empTable.append(data[i]['SYS_NAME'])
            return empTable
        except Exception as e:
            #MAIN_System.writeLog(f"[飛騰]查詢員工資料,發生錯誤![{e}]")
            print(f"[飛騰]查詢員工資料,發生錯誤![{e}]")

    #取得使用網頁打卡之人員
    def get_webSwipePerson(self):
        try:
            json_data = {
                "Action": "Find",
                "SessionGuid": self.SenssionID,
                "ProgID": "ATT0021501",
                "Value": {
                    "$type": "AIS.Define.TFindInputArgs, AIS.Define",
                    "SelectFields": "*",
                    "Parameters": [],
                    "FilterItems": [
                        {
                            "$type": "AIS.Define.TFilterItem, AIS.Define",
                            "FieldName": "DUTYSTATUS",
                            "FilterValue": MAIN_System.FilterValue
                        },
                        {
                            "$type": "AIS.Define.TFilterItem, AIS.Define",
                            "FieldName": "SwipeTime",
                            "FilterValue": MAIN_System.today
                        }
                    ],
                    "SystemFilterOptions": "All",
                    "IsBuildVirtualField": True
                }
            }
            data = self.result(json_data)
            webswipe_person = []
            for i in range(0, len(data)):
                if (data[i]['TMP_EMPLOYEENAME'] not in webswipe_person):
                    webswipe_person.append(data[i]['TMP_EMPLOYEENAME'])
                    webswipe_person.append(data[i]['SWIPETIME'])
            return webswipe_person
        except Exception as e:
            #MAIN_System.writeLog(f"[飛騰]查詢打卡狀態,發生錯誤![{e}]")
            print(f"[飛騰]查詢打卡狀態,發生錯誤![{e}]")

    #透過[所有在職之員工]扣掉[已使用網頁打卡之員工]，計算得出[未使用網頁打卡之員工]
    def get_non_webSwipePerson(self):
        empTable = self.get_empTable()
        #print(empTable)
        webSwipePerson = self.get_webSwipePerson()
        #print(webSwipePerson)
        if (MAIN_System.FilterValue == "4" or MAIN_System.FilterValue2 == "1"):
            status = "上"
        elif (MAIN_System.FilterValue == "5" or MAIN_System.FilterValue2 == "2"):
            status = "下"
        for i in range(0, len(webSwipePerson), 2):
            empTable.remove(webSwipePerson[i])
            print(f"[飛騰]確認打卡狀態,{webSwipePerson[i]},已打卡{status}班[{webSwipePerson[i+1]}]")
        return empTable
    ################################
    # SourceType說明
    # 0:刷卡檔轉入
    # 1:資料庫對接
    # 2:線上補卡單
    # 3:Web刷卡
    # 4:App刷卡
    # 5:自行新增
    # 6:其他
    ################################
    #檢查是否已經匯入過刷卡資料
    def import_swipeDataCheck(self, FilterValue):
        try:
            if (FilterValue == '2' or FilterValue == '5'):
                return None
            else:
                json_data = {
                    "Action": "Find",
                    "SessionGuid": self.SenssionID,
                    "ProgID": "ATT0021500",
                    "Value": {
                        "$type": "AIS.Define.TFindInputArgs, AIS.Define",
                        "SelectFields": "*",
                        "Parameters": [],
                        "FilterItems": [
                            {  # 刷卡日期
                                "$type": "AIS.Define.TFilterItem, AIS.Define",
                                "FieldName": "SWIPEDATE",
                                "FilterValue": MAIN_System.today
                            },
                            {  # 刷卡檔轉入
                                "$type": "AIS.Define.TFilterItem, AIS.Define",
                                "FieldName": "SourceType",#詳見"SourceType說明"
                                "FilterValue": "0"
                            },
                            {  # 上/下班
                                "$type": "AIS.Define.TFilterItem, AIS.Define",
                                "FieldName": "DUTYSTATUS",
                                "FilterValue": FilterValue
                            },
                            {  # 人員姓名
                                "$type": "AIS.Define.TFilterItem, AIS.Define",
                                "FieldName": "TMP_EmployeeName",
                                "FilterValue": person
                            }
                        ],
                        "SystemFilterOptions": "All",
                        "IsBuildVirtualField": True
                    }
                }
                data = self.result(json_data)
                return data
        except Exception as e:
            #MAIN_System.writeLog(f"[飛騰]檢查匯入資料,{person}:發生錯誤![{e}]")
            print(f"[飛騰]檢查匯入資料,{person}:發生錯誤![{e}]")
            return None
        
    #取得飛騰系統內員工的卡號，並排出員工編號9開頭的卡號(為臨時卡)
    def get_cardNO(self):
        try:
            if hamsdict['EmpID'][0] != '9':
                json_data = {
                    "Action": "Find",
                    "SessionGuid": self.SenssionID,
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
                                "FilterValue": hamsdict['EmpID']
                            }
                        ],
                        "SystemFilterOptions": "Default",
                        "IsBuildSelectedField": True,
                        "IsBuildFlowLightSignalField": True
                    }
                }
                data = self.result(json_data)
                return data[0]['SYS_VIEWID'], data[0]['CARDNO']
            #臨時卡回傳字串N，怕使用None會有問題
            else:
                return 'N', 'N'
        except Exception as e:
            print(f"[飛騰]查詢員工卡號,{hamsdict['EmpName']}:發生錯誤![{e}]")
            return 'N', 'N'

    #同步卡號，將漢軍系統的卡號資訊同步之飛騰系統
    def sync_cardNO(self):
        try:
            json_data = {
                "Action": "Import",
                "SessionGuid": self.SenssionID,
                "ProgID": "ATT0021150",
                "Value": {
                    "$type": "AIS.Define.TSaveInputArgs, AIS.Define",
                    "DataSet": {
                        "ATT0021150": [
                            {
                                "SYS_VIEWID": scsdict['ViewID'],
                                "UserNo": hamsdict['EmpID'],
                                "TMP_EMPLOYEENAME": hamsdict['EmpName'],
                                "ISSIGN": True,
                                "CARDNO": hamsdict['CardNO'],
                                "NOTE": ""
                            }
                        ]
                    },
                }
            }
            get(self.api_url, json=json_data, verify=False)
            #MAIN_System.writeLog(f"[系統]同步卡號資訊,{hamsdict['EmpName']},卡號:{scsdict['CardNO']} 更新為 {hamsdict['CardNO']}")
            print( f"[系統]同步卡號資訊,{hamsdict['EmpName']},卡號:{scsdict['CardNO']} 更新為 {hamsdict['CardNO']}")
        except Exception as e:
            #MAIN_System.writeLog(f"[系統]同步卡號資訊,{hamsdict['EmpName']},發生錯誤![{e}]")
            print(f"[系統]同步卡號資訊,{hamsdict['EmpName']},發生錯誤![{e}]")
    #匯入刷卡資料
    def import_swipeData(self):
        try:
            json_data = {
                "Action": "ExecFunc",
                "SessionGuid": self.SenssionID,
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
                                    "EmployeeID": hamsdict['EmpID'],
                                    "CardNO": hamsdict['CardNO'],
                                    "SwipeDate": hamsdict['SwipeDate'],
                                    "SwipeTime": hamsdict['SwipeTime'],
                                    "Note": hamsdict['Note'],
                                }
                            ]
                        }
                    ]
                }
            }
            r=get(self.api_url, json=json_data, verify=False)
            print(r.json())
            print(f"[系統]匯入刷卡資料,{hamsdict['EmpName']},{hamsdict}")
        except Exception as e:
            print(f"[系統]匯入刷卡資料,{hamsdict['EmpName']}:發生錯誤![{e}]")


if __name__ == '__main__':
    #實作物件
    MAIN_System = System()
    SCS_System = SCS()
    HAMS_System = HAMS()
    #取得未使用網頁打卡之人員
    NON_WEBSWIPE = SCS_System.get_non_webSwipePerson()
    #從漢軍系統取得刷卡資料
    HAMS_SWIPEDATA = HAMS_System.query_HAMSdb_swipedata()
    HAMS_SWIPEDATA = [row.split(",") for row in HAMS_SWIPEDATA]
    #NON_WEBSWIPE = ["鍾孟修"]
    #逐一確認
    for person in NON_WEBSWIPE:
        #print(NON_WEBSWIPE)
        #MAIN_System.writeLog(f"[飛騰]確認打卡狀態,{person},尚未打卡")
        print(f"[飛騰]確認打卡狀態,{person},尚未打卡")
        #此物件用於識別有沒有刷卡資訊使用，若沒有打卡也沒有刷卡，則判斷為未上班
        check = False
        for index in range(0, len(HAMS_SWIPEDATA)):
            if (person in HAMS_SWIPEDATA[index][3]) :
                check = True
                #檢查是否已有匯入的刷卡紀錄
                
                swipeDataCheck = SCS_System.import_swipeDataCheck(MAIN_System.FilterValue)
                
               
                #如果有資料
                if swipeDataCheck : #and swipeDataCheck[0]['CARDNO'] != '3931813486'
                    swipedict = {
                        'SWIPEDATE': swipeDataCheck[0]['SWIPEDATE'],
                        'SWIPETIME': swipeDataCheck[0]['SWIPETIME'],
                        'CARDNO': swipeDataCheck[0]['CARDNO'],
                        'TMP_EMPLOYEENAME': swipeDataCheck[0]['TMP_EMPLOYEENAME'],
                        'TMP_EMPLOYEEID': swipeDataCheck[0]['TMP_EMPLOYEEID'],
                        'NOTE': swipeDataCheck[0]['NOTE'],
                    }
                    print(f"資料已存在!,{swipedict}")
                #如果沒有資料
                else:
                    #檢查是否有早於上班時間或晚於下班時間的刷卡紀錄(識別不同，詳見"FilterValue說明")
                    swipeDataCheck = SCS_System.import_swipeDataCheck(
                        MAIN_System.FilterValue2)
                    #如果有資料
                    if swipeDataCheck :
                        swipedict = {
                            'SWIPEDATE': swipeDataCheck[0]['SWIPEDATE'],
                            'SWIPETIME': swipeDataCheck[0]['SWIPETIME'],
                            'CARDNO': swipeDataCheck[0]['CARDNO'],
                            'TMP_EMPLOYEENAME': swipeDataCheck[0]['TMP_EMPLOYEENAME'],
                            'TMP_EMPLOYEEID': swipeDataCheck[0]['TMP_EMPLOYEEID'],
                            'NOTE': swipeDataCheck[0]['NOTE'],
                        }
                        print(f"資料已存在!,{swipedict}")
                    #如果沒有資料
                    else:
                        hamsdict = {
                            'SwipeDate': HAMS_SWIPEDATA[index][0].replace("/", ""),
                            'SwipeTime': HAMS_SWIPEDATA[index][1].replace(":", "")[0:4]+"00",#注意秒數不列入資料，故統一為0
                            'CardNO': HAMS_SWIPEDATA[index][2],
                            'EmpName': HAMS_SWIPEDATA[index][3].split('-')[0],
                            'EmpID': HAMS_SWIPEDATA[index][4],
                            'Note': HAMS_SWIPEDATA[index][5],
                        }
                        #取得飛騰系統的卡號
                        CardNO = SCS_System.get_cardNO()
                        #如果不是臨時卡才執行
                        if (CardNO[0] != 'N' and CardNO[1] != 'N'):
                            scsdict = {
                                'ViewID': CardNO[0],
                                'CardNO': CardNO[1],
                            }
                            #比對卡號
                            if (hamsdict['CardNO'] == scsdict['CardNO']):
                                print(f"[系統]比對卡號資料,{hamsdict['EmpName']},正確![漢軍:{hamsdict['CardNO']}、飛騰:{scsdict['CardNO']}]")
                            else:
                                print(f"[系統]比對卡號資料,{hamsdict['EmpName']},不正確![漢軍:{hamsdict['CardNO']}、飛騰:{scsdict['CardNO']}]")
                                #如果卡號不一致，則同步卡號
                                SCS_System.sync_cardNO()
                            #匯入刷卡資料
                            SCS_System.import_swipeData()
        if (not check):
            #MAIN_System.writeLog(f"[漢軍]查詢刷卡資訊,{person},無刷卡資訊")
            print(f"[漢軍]查詢刷卡資訊,{person},無刷卡資訊")
    now = str(datetime.now().hour).zfill(2)
    #MAIN_System.writeLog(
    #    f"[系統]{now}點的工作已完成!--------------------------------------------------------")
    print(f"[系統]{now}點的工作已完成!--------------------------------------------------------")
    exit(0)
    