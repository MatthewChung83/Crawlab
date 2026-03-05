# -*- coding: utf-8 -*-
"""
Configuration for LicensePenalty crawler
"""
import datetime

datetime_dt = datetime.datetime.today()
datetime_str = datetime_dt.strftime("%Y/%m/%d")

db = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'username': 'CLUSER',
    'password': 'Ucredit7607',
    'totb1': 'LicensePenalty',
    'entitytype': 'UCS_' + datetime_str.replace('/', ''),
}

wbinfo = {
    'url': 'https://www.mvdis.gov.tw/m3-emv-vil/vil/driverLicensePenalty',
    'captchaImg': 'https://www.mvdis.gov.tw/m3-emv-vil/captchaImg.jpg',
}

pics = {
    'imgp': r'./valcode.png'
}
