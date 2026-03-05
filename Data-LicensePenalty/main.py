import datetime
datetime_dt = datetime.datetime.today()# 獲得當地時間
datetime_str = datetime_dt.strftime("%Y/%m/%d")  # 格式化日期

import scrapy
from LicensePenalty.items import LicensepenaltyItem


class LicensePenaltySpider(scrapy.Spider):
    name = "LicensePenalty"

    db = {
        # 資料回寫主機之資訊
        'server': '10.10.0.94',
        'database': 'CL_Daily',
        'username': 'CLUSER',
        'password': 'Ucredit7607',
        
        # 監理所駕照查詢主檔
        'totb1':'LicensePenalty',
        
        # 名單編號
        'entitytype':'UCS'+'_'+datetime_str.replace('/',''),
    }

    wbinfo = {
        # post url
        'url':'https://www.mvdis.gov.tw/m3-emv-vil/vil/driverLicensePenalty',

        # captcha url
        'captchaImg':'https://www.mvdis.gov.tw/m3-emv-vil/captchaImg.jpg',
    }

    pics = {
        # captcha path
        'imgp' : r'./valcode.png'
    }
    def foo(num,obs):
        while num < obs:
            num = num + 1 
            yield num

    def src_obs(server,username,password,database,totb1):
        import pymssql
        conn = pymssql.connect(server=server, user=username, password=password, database = database)
        cursor = conn.cursor()
        script = f"""
        
        select (select count(*)
        from [dbo].[{totb1}]
        where (status is null) and birthday is not null )
        +
        (select count(*) from [{totb1}] 
        where (select DATEDIFF(mm, updatetime, getdate()))> = 3 and status <> 'Y' and birthday is not null)
        """    
        cursor.execute(script)
        obs = cursor.fetchall()
        cursor.close()
        conn.close()
        return list(obs[0])[0]

    def dbfrom(server,username,password,database,totb1):
        import pymssql
        conn = pymssql.connect(server=server, user=username, password=password, database = database)
        cursor = conn.cursor()
        script = f"""
        select *
        into #test
        from [dbo].[{totb1}] as a
        where (status is null) and birthday is not null 
        insert into #test
        select  *
        from [{totb1}]
        where (select DATEDIFF(mm, updatetime, getdate()))> = 3 and status <> 'Y' and birthday is not null
        
        select * from #test
        order by entitytype desc
        --offset 0 row fetch next 1 rows only
        """
        cursor.execute(script)
        c_src = cursor.fetchall()
        cursor.close()
        conn.close()
        return c_src

    def updateSQL(server,username,password,database,totb1,status,updatetime,ID,driver_type,driver_status,DRvaliddate):
        import pymssql
        conn = pymssql.connect(server=server, user=username, password=password, database = database)
        cursor = conn.cursor()
        
        script = f"""
        update [dbo].[{totb1}]
        set driver_type = '{driver_type}', driver_status = '{driver_status}', DRvaliddate = '{DRvaliddate}',status = '{status}', updatetime = '{updatetime}'
        where ID = '{ID}'
        """
        
        cursor.execute(script)
        conn.commit()
        cursor.close()
        conn.close()
        
    def exit_obs(server,username,password,database,totb1):
        import pymssql
        conn = pymssql.connect(server=server, user=username, password=password, database = database)
        cursor = conn.cursor()
        script = f"""
        select count (distinct ID)
        from [{totb1}]
        where  updatetime > = convert(varchar(10),getdate(),111)
        """    
        cursor.execute(script)
        obs = cursor.fetchall()
        cursor.close()
        conn.close()
        return list(obs[0])[0]

    def capcha_resp(url,captchaImg,imgp,q,ID,birthday):
    # url:Post網址
    # captchaImg:辨識碼網址
    # imgp:辨識碼本機儲存路徑
    # q:辨識迭代次數
    # ID:Post-form data的ID欄位
    # birthday:Post-form data的出生日期欄位

        from bs4 import BeautifulSoup
        import requests
        import ddddocr
        
        while q < 100:
            # 取辨識碼並儲存至Local
            session = requests.session()
            respimg = session.get(captchaImg)
            img = open(imgp, 'wb')
            img.write(respimg.content)
            img.close()
            
            # 執行辨識作業
            ocr = ddddocr.DdddOcr()
            with open(imgp, 'rb') as f:
                img_bytes = f.read()
                res = ocr.classification(img_bytes)
            
            # post API then get result
            data = {
                'stage': 'natural',
                'method': 'queryResult',
                'uid': f'{ID}',
                'birthday': f'{birthday}',
                'validateStr': f'{res}',
            }
            
            resp = session.post(url,data=data)
            soup = BeautifulSoup(resp.text,"lxml")
            
            # 判斷辨識碼是否正確辨別
            if soup.find_all('span',string = '驗證碼輸入錯誤') and '200' not in resp:
                session.close()
                q =+ 1
                print('驗證碼輸入錯誤')
            else:
                session.close()
                result = soup
                return result
                q = 100


    from bs4 import BeautifulSoup
    import requests
    import ddddocr
    import time
    import re
    import sys
    
    # 宣告資料庫、網站、迭代...等參數
    server,database,username,password,totb1 = db['server'],db['database'],db['username'],db['password'],db['totb1']
    url,captchaImg = wbinfo['url'],wbinfo['captchaImg']
    imgp = pics['imgp']
    q = 0

    # 取名單數量
    obs = src_obs(server,username,password,database,totb1)
    src = dbfrom(server,username,password,database,totb1)
    try:
        for i in range(len(src)):

            # 逐筆取庫內資料
            

            ID = re.sub(r"\s+", "", src[i][3])
            birthday = ('0'+re.sub(r"\s+", "", src[i][4]).replace('/',''))[-7:]

            resp = capcha_resp(url,captchaImg,imgp,q,ID,birthday)

            # 判斷查找結果之分類依據
            driver_info = resp.find(class_ = 'tb_list_std')
            # 查回相關資訊給定預設值
            driver_type,driver_status,DRvaliddate,status,updatetime = '','','','N',(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
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
            
            # 更新查回結果至資料庫
            updatetime = (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
            updateSQL(server,username,password,database,totb1,status,updatetime,ID,driver_type,driver_status,DRvaliddate)
            print(ID,driver_type,driver_status,DRvaliddate,status)
            ex_obs = exit_obs(server,username,password,database,totb1)
            if ex_obs >= 50000:
                sys.exit()
            else:
                pass
    except:
        pass
        
        