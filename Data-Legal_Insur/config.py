# -*- coding: utf-8 -*-
"""
Configuration file for Legal Insurance System
"""

# Database configuration
db = {
    'server': '10.10.0.94',
    'database': 'UCS_ReportDB',
    'username': 'CLUSER',
    'password': 'Ucredit7607',
    'fromtb': 'INS_Legal_Insurtech',
    'totb': 'INS_Legal_Insurtech',
}

# Web information
wbinfo = {
    'url': 'https://insurtech.lia-roc.org.tw/crr/index.html',
}

# User accounts (multiple users based on insurance type)
vars = {
    'Name001': '錢先生',
    'Mail001': 'yizhenchen2021@gmail.com',
    'PSD001': 'qdhl xbua ukpb ilab',

    'Name002': '楊先生',
    'Mail002': 'shiyachen2021@gmail.com',
    'PSD002': 'fljv adqi sfap mfnn',

    'Name003': '黃小姐',
    'Mail003': 'xuelinglee2021@gmail.com',
    'PSD003': 'mxcu urzi kpkd obpy',

    'Name005': '楊先生',
    'Mail005': 'shiyachen2021@gmail.com',
    'PSD005': 'fljv adqi sfap mfnn',

    # 類型 1, 2, 3 使用的公司資訊
    'Phone': '0228289788',
    'Compiled': '23756020',
    'Company': '聯合財信資產管理股份有限公司',
    'Address': '台北市北投區裕民六路2號3樓',

    # 類型 5 使用的公司資訊
    'Phone005': '0228289788',
    'Compiled005': '86928561',
    'Company005': '安泰商業銀行股份有限公司',
    'Address005': '台北市松山區復興北路337號4樓'
}

# API endpoints
api_endpoints = {
    'otp_send': 'https://insurtech.lia-roc.org.tw/lia-creditor-record-server/api/otp/send',
    'crr901w_verify': 'https://insurtech.lia-roc.org.tw/lia-creditor-record-server/api/crr901w/verify',
    'payment_charge': 'https://insurtech.lia-roc.org.tw/lia-creditor-record-server/api/payment/charge',
    'ecpay_v5': 'https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5',
    'retain_payment': 'https://payment.ecpay.com.tw/Cashier/RetainPaymentType',
    'atm_info': 'https://payment.ecpay.com.tw/PaymentRule/ATMPaymentInfo',
}
