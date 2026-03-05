#!/usr/bin/env python3
"""
配置檔案 - 改進版法院拍賣爬蟲
"""

# 資料庫配置
DB_CONFIG = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'user': 'CLUSER',
    'password': 'Ucredit7607'
}

# 路徑配置
PATHS = {
    'output_dir': './data/',
    'log_dir': './logs/',
}

# 爬蟲配置
CRAWLER_CONFIG = {
    'delay_between_requests': 0.1,  # 請求間隔 (秒)
    'request_timeout': 30,          # 請求超時 (秒)
    'pdf_download_timeout': 60,     # PDF下載超時 (秒)
    'max_retries': 3,               # 最大重試次數
}

# 資料表名稱
TABLE_NAMES = {
    'wbt_court_auction_tb': 'wbt_court_auction_tb',
    'auction_info_tb': 'auction_info_tb',
}

# 爬取類型配置
CRAWL_TYPES = {
    'sale_types': ['1', '4', '5'],           # 1=一般程序, 4=應買公告, 5=拍定價格
    'prop_types': ['C52', 'C51', 'C103'],    # C52=房屋, C51=土地, C103=房屋+土地
}

# API URLs
API_URLS = {
    'base_url': 'https://aomp109.judicial.gov.tw',
    'query_url': 'https://aomp109.judicial.gov.tw/judbp/wkw/WHD1A02/QUERY.htm',
    'pdf_base_url': 'https://aomp109.judicial.gov.tw/judbp/wkw/WHD1A02/DO_VIEWPDF.htm',
}