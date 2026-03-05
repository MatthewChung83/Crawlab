# -*- coding: utf-8 -*-
"""
Configuration for TaxRefund crawler
"""

db = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'username': 'CLUSER',
    'password': 'Ucredit7607',
    'src_tb': 'taxrefundtb',
    'tar_tb': 'taxrefundtb',
}

wbinfo = {
    'url': 'https://www.etax.nat.gov.tw/etwmain/etw133w1/e01',
}

pics = {
    'imgp': r'./captcha_01.jpg',
}
