# -*- coding: utf-8 -*-
"""
Configuration for Judicial 139 Crawler
"""

# Database configuration
db = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'username': 'CLUSER',
    'password': 'Ucredit7607',
    'totb': 'JudicialAnnouncements',
}

# Web info
wbinfo = {
    'url': 'https://www.judicial.gov.tw/tw/lp-139-1.html',
}

# Crawler settings
crawler = {
    'timeout': 30,          # Request timeout (seconds)
    'page_size': 20,        # Records per page
    'delay': 1,             # Delay between requests (seconds)
}
