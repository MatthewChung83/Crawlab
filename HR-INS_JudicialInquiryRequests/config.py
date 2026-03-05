# -*- coding: utf-8 -*-
"""
Configuration for HR-INS_JudicialInquiryRequests - Judicial inquiry crawler
"""

db = {
    'server': '10.10.0.94',
    'database': 'UCS_ReportDB',
    'username': 'FRUSER',
    'password': '1qaz@WSX',
}

smb = {
    'server_ip': '10.10.0.93',
    'service_name': 'UCS',
    'username': 'sqlsvc',
    'password': 'Sq1@dmin',
    'domain': 'ucs',
    'base_folder': 'HumanResourceDept/screenshot',
}

urls = {
    'consumer_debt': 'https://cdcb3.judicial.gov.tw/judbp/wkw/WHD9A01.htm',
    'bankruptcy': 'https://cdcb3.judicial.gov.tw/judbp/wkw/WHD9A01.htm',
    'domestic': 'https://domestic.judicial.gov.tw/judbp/wkw/WHD9HN01.htm',
}

# Local fallback directory
LOCAL_OUTPUT_DIR = "judicial_crawler/output"

# Font paths for screenshot header
FONT_PATHS = [
    "NotoSansTC-Regular.ttf",
    "C:\\Windows\\Fonts\\msjh.ttc",
    "C:\\Windows\\Fonts\\msjh.ttf",
    "C:\\Windows\\Fonts\\mingliu.ttc",
    "C:\\Windows\\Fonts\\simsun.ttc",
    "arial.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/usr/share/fonts/truetype/arphic/ukai.ttc",
]
