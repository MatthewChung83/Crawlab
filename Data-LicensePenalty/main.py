# -*- coding: utf-8 -*-
"""
LicensePenalty crawler - Driver license penalty query
Converted from Scrapy to requests-based architecture
"""
import re
import sys
import time

from config import *
from etl_func import *

# Database and web parameters
server, database, username, password, totb1 = (
    db['server'], db['database'], db['username'], db['password'], db['totb1']
)
url, captchaImg = wbinfo['url'], wbinfo['captchaImg']
imgp = pics['imgp']
q = 0

# Get record count and source data
obs = src_obs(server, username, password, database, totb1)
src = dbfrom(server, username, password, database, totb1)

try:
    for i in range(len(src)):
        ID = re.sub(r"\s+", "", src[i][3])
        birthday = ('0' + re.sub(r"\s+", "", src[i][4]).replace('/', ''))[-7:]

        resp = capcha_resp(url, captchaImg, imgp, q, ID, birthday)

        driver_info = resp.find(class_='tb_list_std')
        driver_type, driver_status, DRvaliddate, status, updatetime = (
            '', '', '', 'N', time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        )

        if driver_info:
            if len(driver_info) == 5:
                driver_status = resp.find('tbody').find('td').text
            else:
                driver_type = re.sub(r"\s+", "", driver_info.find_all('tr')[1].find_all('td')[0].text)
                driver_status = re.sub(r"\s+", "", driver_info.find_all('tr')[1].find_all('td')[1].text)
                DRvaliddate = re.sub(r"\s+", "", driver_info.find_all('tr')[1].find_all('td')[2].text)
                if '死亡' in driver_status:
                    status = 'Y'
        else:
            driver_status = '查無汽機車駕照'

        updatetime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        updateSQL(server, username, password, database, totb1, status, updatetime, ID, driver_type, driver_status, DRvaliddate)
        print(ID, driver_type, driver_status, DRvaliddate, status)

        ex_obs = exit_obs(server, username, password, database, totb1)
        if ex_obs >= 50000:
            sys.exit()
except:
    pass
