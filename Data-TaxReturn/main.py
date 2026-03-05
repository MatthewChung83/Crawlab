# Browser Driver
import re
import gc
import csv
import time
import pymssql
import numpy as np
import pandas as pd
import requests
import ddddocr
from bs4 import BeautifulSoup
from datetime import datetime as dt
from config import *
from etl_func import *


#clf = models.load_model(r'C:\Py_Project\project\Tax_Refund\model\tax_best_model.h5')
#clf = models.load_model(r'C:\Py_Project\project\Tax_Refund\model\etax_nat_query_model.h5')

server = db['server']
database = db['database']
username = db['username']
password = db['password']
entitytype = db['entitytype']
fromtb = db['fromtb']
totb = db['totb']

Apurl,imgf1,imgf2,imgp1,imgp2 = APinfo['Apurl'],APinfo['imgf1'],APinfo['imgf2'],APinfo['imgp1'],APinfo['imgp2']


max_retry = 3
while True:
    obs = src_obs(server,username,password,database,fromtb,totb,entitytype)
    if obs == 0 :
        print('finish')
        break
    
    try:
        for i in foo(-1,obs-1):
            src = dbfrom(server,username,password,database,fromtb,totb,entitytype)
            psid = src[0][0]
            pid = src[0][1]
            birthyear_tw = src[0][10]
            insertdate = dt.today().strftime("%Y/%m/%d %H:%M:%S")
            
            time.sleep(0.5)
            
            
            # 建立 OCR 與 session
            ocr = ddddocr.DdddOcr()
            session = requests.Session()
            requests.packages.urllib3.disable_warnings()

            # Step 1：取得驗證碼圖片並辨識
            captcha = session.get('https://svc.tax.nat.gov.tw/svc/ibxValidateCode', verify=False)
            code = ocr.classification(captcha.content)
            print(f"驗證碼：{code}")

            # Step 2：送出查詢
            data = {
                'tax': 'ibx',
                'idn': pid,
                'bornYr': birthyear_tw,
                'inputCode': code
            }
            post_url = 'https://svc.tax.nat.gov.tw/svc/servletirxwresult'
            response = session.post(post_url, data=data, verify=False)

            # Step 3：如查詢成功，用原始 header + session get 結果頁
            if response.status_code == 200 and '"code":0' in response.text:
                print("✅ 驗證成功，前往結果頁...")

                headers = {
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                    "accept-encoding": "gzip, deflate, br, zstd",
                    "accept-language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                    "connection": "keep-alive",
                    "referer": "https://svc.tax.nat.gov.tw/svc/IbxPaidQuery.jsp",
                    "sec-ch-ua": '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-site": "same-origin",
                    "sec-fetch-user": "?1",
                    "upgrade-insecure-requests": "1",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
                }

                result_url = 'https://svc.tax.nat.gov.tw/svc/IrxIbxResultForPc.jsp'
                result_response = session.get(result_url, headers=headers, verify=False)


                # 假設你已經從 session.get(...) 得到 result_response
                soup = BeautifulSoup(result_response.text, 'html.parser')

                # 擷取欄位
                def get_text(label):
                    tag = soup.find('label', string=label)
                    return tag.find_next_sibling(text=True).strip() if tag else ''

                
                INQCode = get_text('檔案編號：')
                Taxreturnchannel = get_text('申報方式：')
                Taxreturntplat = get_text('申報平台：')
                taxOffice = get_text('稽徵機關名稱：')
                taxOfficeAddr = get_text('稽徵機關地址：')
                taxOfficePhone =  get_text('稽徵機關電話：')
                taxreturndate =  get_text('首次申報日期：')
                

            else:
                print("❌ 查詢失敗")
                print(response.text)

                
                
            
            try:
                if '您已完成' in soup.find('fieldset').find('p').text or '稅額試算通知書檔案編號' in soup.find('fieldset').find('p').text:
                    info = soup.find('fieldset').find('p').text
                    status = 'done'
                    output = []
                    for t in soup.find('fieldset').find_all('p'):
                        output.append(t.text.replace('\n','').replace('\t','').replace('\xa0',''))
                    
                    INQCode,Taxreturnchannel,Taxreturnplat,taxreturndate,taxOffice,taxOfficeAddr,taxOfficePhone='','','','','','',''
                    for v in output:
                        if '稅額試算通知書檔案編號' in v or '檔案編號' in v:
                            INQCode = v.replace('稅額試算通知書檔案編號','').replace('檔案編號','').replace('： ','')               
                        if '申報方式' in v:
                            Taxreturnchannel = v.replace('申報方式','').replace('： ','')
                        if '申報平台' in v:
                            Taxreturnplat = v.replace('申報平台','').replace('： ','')
                        if '首次申報日期' in v:
                            taxreturndate = v.replace('首次申報日期','').replace('： ','')
                        if '完成申報時間' in v:
                            taxreturndate = v.replace('完成申報時間','').replace('： ','')
                        if '稽徵機關名稱' in v:
                            taxOffice = v.replace('稽徵機關名稱','').replace('： ','')
                        if '稽徵機關地址' in v:
                            taxOfficeAddr = v.replace('稽徵機關地址','').replace('： ','')
                        if '稽徵機關電話' in v:
                            taxOfficePhone = v.replace('稽徵機關電話','').replace('： ','')
                        if '查詢電話' in v:
                            taxOfficePhone = v[v.find('查詢電話:')+len('查詢電話:'):]
                            taxOffice = v[:v.find('查詢電話')]
                else :

                    info = soup.find('fieldset').find('p').text
                    
                    status = 'done'
                    INQCode,Taxreturnchannel,Taxreturnplat,taxreturndate,taxOffice,taxOfficeAddr,taxOfficePhone = '','','','','','',''
            except:
                print('A')    
                #soup = BeautifulSoup(driver.page_source,'html.parser')
                if '您已完成' in soup.find_all('fieldset')[1].find('p').text or '稅額試算通知書檔案編號' in soup.find_all('fieldset')[1].find('p').text:
                    info = soup.find_all('fieldset')[1].find('p').text
                    
                    status = 'done'
                    output = []
                    for t in soup.find_all('fieldset')[1].find_all('p'):
                        output.append(t.text.replace('\n','').replace('\t','').replace('\xa0',''))
                        
                    INQCode,Taxreturnchannel,Taxreturnplat,taxreturndate,taxOffice,taxOfficeAddr,taxOfficePhone='','','','','','',''
                    for v in output:
                        if '稅額試算通知書檔案編號' in v or '檔案編號' in v:
                            INQCode = v.replace('稅額試算通知書檔案編號','').replace('檔案編號','').replace('： ','')               
                        if '申報方式' in v:
                            Taxreturnchannel = v.replace('申報方式','').replace('： ','')
                        if '申報平台' in v:
                            Taxreturnplat = v.replace('申報平台','').replace('： ','')
                        if '首次申報日期' in v:
                            taxreturndate = v.replace('首次申報日期','').replace('： ','')
                        if '完成申報時間' in v:
                            taxreturndate = v.replace('完成申報時間','').replace('： ','')
                        if '稽徵機關名稱' in v:
                            taxOffice = v.replace('稽徵機關名稱','').replace('： ','')
                        if '稽徵機關地址' in v:
                            taxOfficeAddr = v.replace('稽徵機關地址','').replace('： ','')
                        if '稽徵機關電話' in v:
                            taxOfficePhone = v.replace('稽徵機關電話','').replace('： ','')
                        if '查詢電話' in v:
                            taxOfficePhone = v[v.find('查詢電話:')+len('查詢電話:'):]
                            taxOffice = v[:v.find('查詢電話')]
                else :

                    info = soup.find_all('fieldset')[1].find('p').text
                    
                    status = 'done'
                    INQCode,Taxreturnchannel,Taxreturnplat,taxreturndate,taxOffice,taxOfficeAddr,taxOfficePhone = '','','','','','',''
                
            
            updatesql(server,username,password,database,status,info,INQCode,Taxreturnchannel,Taxreturnplat,taxreturndate,taxOffice,taxOfficeAddr,taxOfficePhone,entitytype,psid,pid,insertdate)
            
    except Exception as e:
        print('restart')
        time.sleep(2)