# -*- coding: utf-8 -*-
"""
Configuration for Tfasc crawler (金服中心拍賣資料)
"""
import os

db = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'username': 'CLUSER',
    'password': 'Ucredit7607',
    'auction_owner_tb': 'tfasc_auction_info_owner_tb',
    'auction_info_tb': 'tfasc_auction_info_tb',
    'wbt_auction_tb': 'tfasc_wbt_auction_tb',
}

wbinfo = {
    'section_url': 'https://www.tfasc.com.tw/Product/BuzBidTime/ReadData',
    'detail_url': 'https://www.tfasc.com.tw/Product/BuzBidTime/ReadDataDetail',
    'estate_url': 'https://www.tfasc.com.tw/Product/BuzRealEstate/Detail',
}

# Document download settings
doc_download = {
    'font_path': r"NotoSansTC-Regular.ttf",
    'output_dir': '/tmp/WBT',
    'timeout': 20,
    'retries': 2,
}
