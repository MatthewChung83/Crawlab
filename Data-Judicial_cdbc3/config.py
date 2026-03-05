# -*- coding: utf-8 -*-
"""
Configuration for Judicial cdcb3 Crawler
"""

# Database configuration
db = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'username': 'CLUSER',
    'password': 'Ucredit7607',
    'fromtb': 'base_case',
    'totb': 'Judicial_cdcb3',
}

# Web info
wbinfo = {
    'query_url': 'https://cdcb3.judicial.gov.tw/judbp/wkw/WHD9A01/QUERY.htm',
    'view_url': 'https://cdcb3.judicial.gov.tw/judbp/wkw/WHD9A01/VIEW.htm',
    'token_url': 'https://cdcb3.judicial.gov.tw/judbp/wkw/WHD9A01/V2.htm',
}

# Crawler settings
crawler = {
    'timeout': 45,          # Request timeout (seconds)
    'daily_limit': 5000,    # Daily processing limit
    'delay': 0.2,           # Delay between requests (seconds)
}
