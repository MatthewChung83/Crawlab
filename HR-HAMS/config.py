# -*- coding: utf-8 -*-
"""
Configuration for HR-HAMS - Access control data import to SCS system
"""

db = {
    'hams_db_file': './HAMS_db_address.txt',
}

api = {
    'main_url': 'https://hr.ucs.tw/SCSRwd/api/systemobject/',
    'api_url': 'https://hr.ucs.tw/SCSRwd/api/businessobject/',
    'company_id': 'scs164',
    'default_user': 'IT1600',
    'default_password': '23756020',
    'language_id': 'zh-TW',
}

# FilterValue說明
# 0:無法辨識
# 1:上班前加班上班(提早於上班時間前30分鐘以上打卡)
# 2:上班前加班下班(晚於下班時間後30分鐘以上打卡)
# 4:上班
# 5:下班
# 7:加班上班
# 8:加班下班

# JobStatus說明
# 0:未就職
# 1:試用
# 2:正式
# 3:約聘
# 4:留職停薪
# 5:離職

# SourceType說明
# 0:刷卡檔轉入
# 1:資料庫對接
# 2:線上補卡單
# 3:Web刷卡
# 4:App刷卡
# 5:自行新增
# 6:其他
