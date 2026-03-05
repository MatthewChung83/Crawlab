# -*- coding: utf-8 -*-
"""
Configuration for HR-Insur_Amount - Insurance amount check and notification
"""

api = {
    'main_url': 'https://hr.ucs.tw/SCSRwd/api/systemobject/',
    'api_url': 'https://hr.ucs.tw/SCSRwd/api/businessobject/',
    'company_id': 'scs164',
    'user_id': 'api',
    'password': 'api$1234',
    'language_id': 'zh-TW',
}

mail = {
    'smtp_server': '10.10.0.159',
    'sender': 'DebtIntegrationSvc@ucs.com',
    'password': '9C4d4d&&',
    'receivers': ['DI@ucs.com', 'tiffany@ucs.com', 'evita@ucs.com'],
    'subject': 'HR_90348-AA新人獎金辦法',
}

# Threshold for salary and working months
SALARY_THRESHOLD = 28590
WORKING_MONTHS_HIGH_SALARY = 6
WORKING_MONTHS_LOW_SALARY = 12
