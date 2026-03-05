# -*- coding: utf-8 -*-
"""
ETL functions for HR-Insur_Amount - Insurance amount check and notification
"""
import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.header import Header

import requests
import pandas as pd

from config import api, mail, SALARY_THRESHOLD, WORKING_MONTHS_HIGH_SALARY, WORKING_MONTHS_LOW_SALARY


def login():
    """Login to HR API and return session ID"""
    headers = {'Content-type': 'application/json'}
    data = {
        "Action": "Login",
        "SessionGuid": "",
        "Value": {
            "$type": "AIS.Define.TLogingInputArgs, AIS.Define",
            "CompanyID": api['company_id'],
            "UserID": api['user_id'],
            "Password": api['password'],
            "LanguageID": api['language_id']
        }
    }
    data_json = json.dumps(data)
    response = requests.post(api['main_url'], data=data_json, headers=headers)
    result = response.json()

    if result.get('Result'):
        return result.get('SessionGuid')
    else:
        print(result.get('Result'), result.get('Message'))
        return None


def fetch_insurance_records(session_id):
    """Fetch insurance records from API"""
    headers = {'Content-type': 'application/json'}
    data = {
        "Action": "Find",
        "SessionGuid": session_id,
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
    response = requests.post(api['api_url'], data=data_json, headers=headers)
    result = response.json()
    print(result)
    return result.get('DataTable', [])


def get_insurance_amount(session_id, sys_id):
    """Get insurance amount for specific insurance level"""
    headers = {'Content-type': 'application/json'}
    data = {
        "SessionGuid": session_id,
        "ProgID": "INS0010100",
        "Value": {
            "$type": "AIS.Define.TExecReportInputArgs, AIS.Define",
            "FormID": sys_id,
            "SystemFilterOptions": "Default",
        }
    }
    data_json = json.dumps(data)
    response = requests.post(api['api_url'], data=data_json, headers=headers)
    result = response.json()

    target = next(
        (item for item in result.get('DataSet', {}).get('Ins0010100SUB', [])
         if item.get('INSURELEVEL') == 1),
        None
    )

    if target:
        amount = target['MONTHINSURESALARY']
        print(f"INSURELEVEL=1 的金額是 {amount}")
        return amount
    else:
        print("找不到 INSURELEVEL = 1 的資料")
        return None


def fetch_employee_data(session_id):
    """Fetch employee data for B0 job level"""
    headers = {'Content-type': 'application/json'}
    data = {
        "Action": "ExecReport",
        "SessionGuid": session_id,
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
    response = requests.post(api['api_url'], data=data_json, headers=headers)
    result = response.json()
    return result.get('DataSet', {}).get('ReportBody', [])


def filter_eligible_employees(employees):
    """Filter employees eligible for new employee bonus"""
    today = datetime.today()
    result_mail = []

    for person in employees:
        total_salary_str = person.get('TOTALSALARY', '')
        start_date_str = person.get('STARTDATE', '')

        if not total_salary_str:
            continue

        try:
            total_salary = float(total_salary_str)
        except ValueError:
            continue

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            continue

        # Calculate working months
        working_months = (today.year - start_date.year) * 12 + (today.month - start_date.month)

        # Filter based on salary and working months
        if total_salary > SALARY_THRESHOLD and working_months >= WORKING_MONTHS_HIGH_SALARY:
            result_mail.append(person)
        elif total_salary <= SALARY_THRESHOLD and working_months >= WORKING_MONTHS_LOW_SALARY:
            result_mail.append(person)

    return result_mail


def create_email_dataframe(eligible_employees):
    """Create DataFrame for email content"""
    rows = []
    for r in eligible_employees:
        rows.append({
            '姓名': r['EMPLOYEENAME'],
            '員編': r['EMPLOYEEID'],
            '組別': r['TMP_DEPARTNAME'],
            '到職日': r['STARTDATE'],
            '工作時間': r['WORKINGYEARSYMD'],
            '職等': r['JOBLEVELID'],
        })
    return pd.DataFrame(rows)


def send_notification_email(df):
    """Send notification email with employee data"""
    if len(df) == 0:
        print("沒有符合條件的人員，不發送郵件")
        return False

    message = MIMEText(df.to_html(index=False), 'html', 'utf-8')
    message['From'] = Header('DebtIntegrationSvc', 'utf-8')
    message['To'] = Header('Evita', 'utf-8')
    message['Subject'] = Header(mail['subject'], 'utf-8')

    try:
        smtp_obj = smtplib.SMTP(mail['smtp_server'])
        smtp_obj.login(mail['sender'], mail['password'])
        smtp_obj.sendmail(mail['sender'], mail['receivers'], message.as_string())
        print('郵件傳送成功')
        return True
    except smtplib.SMTPException as e:
        print(f'Error: 無法傳送郵件 - {e}')
        return False
