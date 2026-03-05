# -*- coding: utf-8 -*-
"""
Configuration for Court Auction Crawler
"""

# Database configuration
db = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'username': 'CLUSER',
    'password': 'Ucredit7607',
    'fromtb': 'wbt_court_auction_tb',
    'totb': 'wbt_court_auction_tb',
    'auction_info_tb': 'auction_info_tb',
}

# Web info
wbinfo = {
    'url': 'https://aomp109.judicial.gov.tw/judbp/wkw/WHD1A02/QUERY.htm',
    'pdf_url': 'https://aomp109.judicial.gov.tw/judbp/wkw/WHD1A02/DO_VIEWPDF.htm',
}

# Crawler settings
crawler = {
    'delay': 0.1,           # Delay between requests (seconds)
    'timeout': 30,          # Request timeout (seconds)
    'pdf_timeout': 60,      # PDF download timeout (seconds)
    'max_retries': 3,       # Max retry count
    'days_ahead': 60,       # Days to look ahead for auctions
}

# Crawl types
crawl_types = {
    'sale_types': ['1', '4', '5'],          # 1=General, 4=Bid notice, 5=Sold price
    'prop_types': ['C52', 'C51', 'C103'],   # C52=House, C51=Land, C103=House+Land
}

# Paths
paths = {
    'output_dir': './data/',
    'log_dir': './logs/',
}
