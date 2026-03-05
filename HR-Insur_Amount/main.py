import datetime
import time
import requests
import sys
import json



from bs4 import BeautifulSoup
from requests import Session
import pandas as pd

wbinfo = {
    'main_url':'https://hr.ucs.tw/SCSRwd/api/systemobject/',
    'api_url':'https://hr.ucs.tw/SCSRwd/api/businessobject/',
}
main_url,api_url = wbinfo['main_url'],wbinfo['api_url']

getdate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f'請假記錄同步-起始時間: {getdate}')

SenssionID=''        
headers = {'Content-type': 'application/json'}
data={
		"Action": "Login",
		"SessionGuid": "",
		"Value":{
			"$type": "AIS.Define.TLogingInputArgs, AIS.Define",
			"CompanyID": "scs164",
			"UserID": "api",
			"Password": "api$1234",
			"LanguageID": "zh-TW"			
		}
}
data_json = json.dumps(data)
response = requests.post(main_url, data=data_json, headers=headers)
result = response.json()

if result.get('Result'):
	SenssionID = result.get('SessionGuid')
else :
	print(result.get('Result'),result.get('Message'))
	
if SenssionID !="":
    data = {  
      "Action": "Find",
      "SessionGuid": SenssionID,
      "ProgID": "INS0010100",
      "Value": {
        "$type": "AIS.Define.TExecReportInputArgs, AIS.Define",
        "SelectFields": "SYS_ViewID,SYS_Name",
        "Parameters": [],
        "FilterItems": [
          {
            "$type": "AIS.Define.TFilterItem, AIS.Define",
            "FieldName": "Flag",
            "FilterValue": "1"
          }
        ],
      }
    }
    data_json = json.dumps(data)
    response = requests.post(api_url, data=data_json, headers=headers)
    result =response.json()
    print(result)
	
last_record = result['DataTable'][-1]
SYS_ID = last_record['SYS_ID']
data = {  
  "SessionGuid": SenssionID,
  "ProgID": "INS0010100",
  "Value": {
    "$type": "AIS.Define.TExecReportInputArgs, AIS.Define",
    "FormID": SYS_ID,
    "SystemFilterOptions": "Default",
  }
}
data_json = json.dumps(data)
response = requests.post(api_url, data=data_json, headers=headers)
result =response.json()
target = next((item for item in result['DataSet']['Ins0010100SUB'] if item['INSURELEVEL'] == 1), None)

# 如果有找到，就取出金額
if target:
    amount = target['MONTHINSURESALARY']
    print(f"INSURELEVEL=1 的金額是 {amount}")
else:
    print("找不到 INSURELEVEL = 1 的資料")

data = {
  "Action": "ExecReport",
  "SessionGuid": SenssionID,
  "ProgID": "RHUM002",
  "Value": {
    "$type": "AIS.Define.TExecReportInputArgs, AIS.Define",
    "UIType": "Report",
    "ReportID": "",
    "ReportTailID": "",
    "FilterItems": [
      {
        "$type": "AIS.Define.TFilterItem, AIS.Define",
        "FieldName": "ZA.SYS_CompanyID",
        "FilterValue": "SCS164"
      },
      {
        "$type": "AIS.Define.TFilterItem, AIS.Define",
        "FieldName": "ZA.JobLevelID",
        "FilterValue": "B0"
      },
      {
        "$type": "AIS.Define.TFilterItem, AIS.Define",
        "FieldName": "ZA.JobStatus",
        "FilterValue": "0",
        "ComparisonOperator": "NotEqual"
      },
      {
        "$type": "AIS.Define.TFilterItem, AIS.Define",
        "FieldName": "ZA.JobStatus",
        "FilterValue": "4",
        "ComparisonOperator": "NotEqual"
      },
      {
        "$type": "AIS.Define.TFilterItem, AIS.Define",
        "FieldName": "ZA.JobStatus",
        "FilterValue": "5",
        "ComparisonOperator": "NotEqual"
      }
    ],
    "UserFilter": ""
  }
}
data_json = json.dumps(data)
response = requests.post(api_url, data=data_json, headers=headers)
result =response.json()

from datetime import datetime
# 設定今天日期
today = datetime.today()

# 結果儲存
result_mail = []

for person in result['DataSet']['ReportBody']:
    total_salary_str = person.get('TOTALSALARY', '')
    start_date_str = person.get('STARTDATE', '')   
    # 若total_salary為空，就跳過
    if not total_salary_str:
        continue
    
    try:
        total_salary = float(total_salary_str)
    except ValueError:
        continue  # 無法轉換成數字就跳過

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M:%S')
    except ValueError:
        continue  # 日期格式錯誤就跳過

    # 計算工作月數
    working_months = (today.year - start_date.year) * 12 + (today.month - start_date.month)

    # 根據條件篩選
    if total_salary > 28590 and working_months >= 6:
        result_mail.append(person)
    elif total_salary <= 28590 and working_months >= 12:
        result_mail.append(person)

# 印出符合條件的人
#for r in result_mail:
#    print(f"姓名: {r['EMPLOYEENAME']} ,員編: {r['EMPLOYEEID']} , 組別: {r['TMP_DEPARTNAME']} , 到職日: {r['STARTDATE']} , 工作時間: {r['WORKINGYEARSYMD']}, 職等: {r['JOBLEVELNAME']}")
# 將符合條件的人員資料轉換成表格
rows = []
for r in result_mail:
    rows.append({
        '姓名': r['EMPLOYEENAME'],
        '員編': r['EMPLOYEEID'],
        '組別': r['TMP_DEPARTNAME'],
        '到職日': r['STARTDATE'],
        '工作時間': r['WORKINGYEARSYMD'],
        '職等': r['JOBLEVELID'],
    })

# 建立 DataFrame 
df = pd.DataFrame(rows)
if len(df) != 0 :
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header
    sender = 'DebtIntegrationSvc@ucs.com'
    pwd = '9C4d4d&&'
    receivers = ['DI@ucs.com','tiffany@ucs.com','evita@ucs.com'] # 接收郵件
    # 三個引數：第一個為文字內容，第二個 plain 設定文字格式，第三個 utf-8 設定編碼
    message = MIMEText(df.to_html(index=False), 'html', 'utf-8')
    message['From'] = Header('DebtIntegrationSvc', 'utf-8') # 傳送者
    message['To'] = Header('Evita', 'utf-8') # 接收者
    subject = 'HR_90348-AA新人獎金辦法'
    message['Subject'] = Header(subject, 'utf-8')
    try:
        smtpObj = smtplib.SMTP('10.10.0.159')
        #smtpObj.connect('10.10.0.159',25)
        smtpObj.login(sender,pwd)
        smtpObj.sendmail(sender, receivers, message.as_string())
        print('郵件傳送成功')
    except smtplib.SMTPException:
        print('Error: 無法傳送郵件')
        
else :
  pass