# -*- coding: utf-8 -*-
"""
Created on Wed Feb  1 09:30:39 2023

@author: admin
"""
import pandas as pd
import paramiko
from scp import SCPClient
import os
import io
import time 
import calendar
import requests
import paramiko
from PIL import Image
from bs4 import BeautifulSoup
from selenium import webdriver
import selenium.common.exceptions
import pandas as pd
import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.expected_conditions import alert_is_present
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoAlertPresentException

db = {
    'server': '10.10.0.94',
    'database': 'CL_Daily',
    'username': 'CLUSER',
    'password': 'Ucredit7607',
}

server,database,username,password= db['server'],db['database'],db['username'],db['password']
oc_list = ['ALEXY','ANDERSON','KEVIN4584','JACKYH','JASON4703','JULIAN','SCOTT4162','SIMONSH','SPANELY','WHITE5082']

def All(server,username,password,database,i):
    import pymssql
    conn = pymssql.connect(server=server, user=username, password=password, database = database)
    cursor = conn.cursor()
    script = f"""
    --SingleVisit
        select 
        CONVERT(varchar(100), GETDATE(), 23) as Data_date,
        SV_NO as no,
        SV_NO as CaseI,
        SV_Person_Name as CM_Name,
        '台新國際商業銀行股份有限公司' as Bank,
        Amount_TTL as Debt_AMT,
        Case when Case_Type like '%急件%' then '4' else '5' end as PrioritySV,
        'New' as SV_Type,
        '台新單項委外案件' as Case_Type,
        CONVERT(varchar(100), SV_PreCompletion_Date, 23) as prioritydate,
        SUBSTRING(ZipCode_GIS,1,3) as ZIP,
        City_GIS as City,
        Town_GIS as Town,
        Address,
        Longitude,
        Latitude,
        SV_Time_Period as Memo,
        Case when Case_Type is null then '' else Case_Type end as Priority,
        '' as Objective,
        UCS_AC_YN as Motivation,
        OC as ocempi,
        OC_EName as OC,
        Undertaker_Name as AA,
        Contact_Number as AA_contact,
        case when Status is null and SV_Plan_Date is not null then CONVERT(varchar(100), SV_Plan_Date, 23) else '' end as cesv_TIME,
        case when Status is null and SV_Plan_Date is not null then DATEDIFF(D,CONVERT(varchar(100), GETDATE(), 23),CONVERT(varchar(100), SV_Plan_Date, 23)) else '' end as countdown,
        SV_Finish_Date,
        Status
        into #SingleVisit
        from [OCAP].[dbo].[TSB_SVCaseMain] 
		where status = 'SITE VIS' and SV_Finish_Date is null

        select 
        convert(varchar(10),getdate()+1,111) as Data_date,
        SQLREPORT.no,
        SQLREPORT.案號,
        SQLREPORT.姓名,
        Bank = SQLREPORT.銀行別,
        SQLREPORT.大金,
        PrioritySV = case when SQLREPORT.Priority = 'J,自動派訪名單' then '14' else SQLREPORT.優先別 end,
        SV_Type = SQLREPORT.外訪種類,
        SQLREPORT.prioritydate,
        SQLREPORT.zip,
        City = SQLREPORT.縣市,
        Town = SQLREPORT.鄉鎮市區,
        address = SQLREPORT.地址,
        SQLREPORT.經度,
        SQLREPORT.緯度,
        Memo = SQLREPORT.備註,
        SQLREPORT.Priority,
        Objective = SQLREPORT.目的,
        Motivation = SQLREPORT.動機,
        OC = SQLREPORT.外訪員,
        AA = SQLREPORT.案件承辦,
        AA_contact = SQLREPORT.案件承辦分機,
        SQLREPORT.[預計外訪日/支援法務執行日],
        SQLREPORT.外訪確認,
        SQLREPORT.外訪確認日,
        SQLREPORT.addressi,
        SQLREPORT.BranchType,
        SQLREPORT.外訪對象,
        case when SQLREPORT.緯度 is null then 
            ( case when court2.緯度 is null then court.緯度
                    else court2.緯度 end)
        	else SQLREPORT.緯度 end as Latitude_r,
        case when SQLREPORT.經度 is null then 
            ( case when court2.經度 is null then court.經度
                    else court2.經度 end)
        	else SQLREPORT.經度 end as Longitude_r
        	,
        case when 目的 like '%執行時間%' then 
            convert(varchar(10),SUBSTRING(目的,patindex('%執行時間%',目的)+5,patindex('%執行時間%',目的)+9) )
            else '' end as cesv_TIME 
        
        into #temp1
        from [treasure].[skiptrace].[dbo].[SVTb_PrioritySV_LIST] SQLREPORT
        left join  (select distinct 動機,緯度,經度
                   from LOCATION_COURT
                  where 動機 <>'') as court on SQLREPORT.動機=court.動機
        left join (select distinct 地址, 緯度, 經度
                   from LOCATION_COURT )as court2 on SQLREPORT.地址=court2.地址
        where 
              (SQLREPORT.地址 not like '%地號%' or court2.地址 is not null)             /*排除異常址(地號)案件*/
        
        
        /*=======因併入台新單委，重新調整外訪優先等級，並考量CESV案件分拆執行日為圖層日期即第二碼為A、非圖層日為B=======*/
        /*=======新增案件類型：UCS自購案件、原業務案件=======*/

        select distinct
        Data_Date,
        convert(varchar(80),no)as no,
        CaseI = convert(varchar(80),[案號]),
        CM_Name = [姓名],
        Bank ,
        Debt_AMT = [大金],
		PrioritySV_Adj = PrioritySV,
        SV_Type,
        case when Bank like '%台灣之星%' then 'UCS自購案件'
             else '原業務案件' end as Case_Type,
        prioritydate,
        ZIP,
        City,
        Town,
        Address,
        Latitude_r as Latitude,
        Longitude_r as Longitude,
        Memo,
        Priority,
        Objective,
        Motivation,
        SUBSTRING(OC,1,4) as ocempi,
        SUBSTRING(OC,6,20) as OC,
        AA,
        AA_contact,
        cesv_TIME,
        '' as countdown
        into #temp2
        from #temp1
        where Latitude_r <> '' and Latitude_r  <> 0
        -- drop table #temp2
        /*=====================TSB單委案件等級給定，並考量分拆排訪日為圖層日期即第二碼為A、非圖層日為B=====================*/
        /*=======計算案件截至到期日天數=======*/
        
        select 
        convert(varchar(10),getdate()+1,111) as Data_date,
        convert(varchar(80),no) as no,
        CaseI,
        CM_Name,
        Bank,
        Debt_AMT,
        case when PrioritySV='4' then 
                   (case when cesv_TIME <> '' and cesv_TIME<=convert(varchar(10),getdate()+1,23)
        		    then '4A'  else '4B' end)
             when PrioritySV='5' then 
                  ( case when cesv_TIME <> '' and cesv_TIME<=convert(varchar(10),getdate()+1,23)
        		    then '5A'  else '5B' end)
             else PrioritySV end as PrioritySV_Adj,
        SV_Type,
        Case_Type,
        prioritydate,
        ZIP,
        City,
        Town,
        Address,
        Latitude,
        Longitude,
        Memo,
        Priority,
        Objective,
        Motivation,
        ocempi,
        OC,
        AA,
        AA_contact,
        cesv_TIME,
        case when cesv_TIME = '' then '尚未排訪案件'
		else convert(varchar(10),datediff(day,convert(varchar(10),getdate()+1,111),dateadd(day,1,cesv_TIME)))end as  countdown
		--Status
        into #TSB
        from #SingleVisit
        where status = 'SITE VIS' and SV_Finish_Date is null
        

		select 
		CaseI,
		Balance,
		'1',
		'中租單項委外',
		address,
		Latitude,
        Longitude,
		'',
		AA,
		Ext,
		PlanDate
		from OCAP.dbo.CL_SVCaseMain 
		where PlanDate is not null and OC not in ('6666','8888') and SVDateTime is null and SVStatus = 'SITE VIS' and OC_Name = '{i}'
        
        union all
        select 
            Convert(Varchar(100),CaseI),
            Debt_AMT,
            '2',
            Case_Type,
            Address,
            Latitude,
            Longitude,
            Motivation,
            AA,
            AA_contact,
            cesv_TIME 
        from #TSB where OC = '{i}'
        union all
        select 
            Convert(Varchar(100),CaseI),
            Debt_AMT,
            '3',
            '聯合案件',
            Address,
            Latitude,
            Longitude,
            Motivation,
            AA,
            AA_contact,
            cesv_TIME 
        from #temp2 where OC = '{i}' and bank not like '%渣打%'
        union all
        select 
            Convert(Varchar(100),CaseI),
            Debt_AMT,
            '4',
            '渣打案件',
            Address,
            Latitude,
            Longitude,
            Motivation,
            AA,
            AA_contact,
            cesv_TIME 
        from #temp2 where OC = '{i}' and bank like '%渣打%'
    """    
    cursor.execute(script)
    c_src = cursor.fetchall()
    cursor.close()
    conn.close()
    return c_src
  
def create_ssh_client(server, port, user, password):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(server, port, user, password)
    return client

def upload_folder(ssh_client, local_path, remote_path):
    with SCPClient(ssh_client.get_transport()) as scp:
        scp.put(local_path, recursive=True, remote_path=remote_path)

for i in oc_list:
    
    print(i)
    #All
    excel = All(server,username,password,database,i)
    result = pd.DataFrame(excel,columns=['案號','欠款金額','優先別','案件類型','地址','緯度','經度','動機','案件承辦','案件承辦分機','執行時間'])
    result.to_excel(rf'/tmp/OCMAP/{i}/{i}_All.xlsx',index=False)


# 設定參數
server = '10.10.0.66'
port = 22
user = 'uicts'
password = 'Ucs@28289788'
local_folder = '/tmp/OCMAP'
remote_folder = '/home/uicts/cash'
ssh = create_ssh_client(server, port, user, password)
upload_folder(ssh, local_folder, remote_folder)
ssh.close()

print("Upload done.")

urll = [
        #'https://accounts.google.com/v3/signin/identifier?dsh=S-117041837%3A1675754453002914&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fmid%3D1hmxln_fpFmOIOcM7Y7zupuVuXaa1lqg%26usp%3Dsharing&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fmid%3D1hmxln_fpFmOIOcM7Y7zupuVuXaa1lqg%26usp%3Dsharing&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin&ifkv=AWnogHdDbBKTojejGlAp3jKJS8LSsA1qpR9wDWIFiD7Zk0il1v48aRoAzffjDexSUK33EWjkkJNJ'+','+'ANDERSON',
       'https://accounts.google.com/v3/signin/identifier?dsh=S-1593203054%3A1681712270285015&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1uYIgPtwrNX2S7zqsKhw6Ryj_3kjqWUw%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1uYIgPtwrNX2S7zqsKhw6Ryj_3kjqWUw%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7T6aNN_tYqzul15RPFNc8W25AGqbOmKeKdf3L2cgEg413d7oqUAtB4PMa0BzyMTLa1iI1MRkQ&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'ALEXY',
       'https://accounts.google.com/v3/signin/identifier?dsh=S655048351%3A1681711320362031&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1qblXja7GTajvC4B282yFr8Xw9XPi26E%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1qblXja7GTajvC4B282yFr8Xw9XPi26E%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7R_rfrdycglT3XenTu7AKFfPXLEiY2Bx2awTQB_-O7l0_1FOurkuZXk9BwT_q80EmtCQeUu1Q&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'ANDERSON',
       'https://accounts.google.com/v3/signin/identifier?dsh=S-234206541%3A1681711357745882&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1zhUvtlOXuzHbdAePLMLG6hcQsZTXWeg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1zhUvtlOXuzHbdAePLMLG6hcQsZTXWeg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7QGizQqGu1ufOj2OkCJ8gzd7PCHiCKaYrhuY8_zgKpTZPO4LeHttY0SQvJ76I9_NRSIbQOfwQ&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'BEN4423',
       'https://accounts.google.com/v3/signin/identifier?dsh=S1275321292%3A1681711409025665&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1wrFPoRKpm2Ldj2hzrbIh3aGf3A2mwUU%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1wrFPoRKpm2Ldj2hzrbIh3aGf3A2mwUU%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TDXRLFPjFpl1wVS4eo79b22-W4jH3XS3DJr09TGjBFSt7OnnzbMbEuL7elvIyX-XhMZgE3&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'KEVIN4584',
       'https://accounts.google.com/v3/signin/identifier?dsh=S1242336415%3A1681711438748969&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1MQwYjQuvQ7qjl4VYym8_aTOl5APqBzA%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1MQwYjQuvQ7qjl4VYym8_aTOl5APqBzA%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7QSFjDh2Q0o5AjbjzRRCWDVE7MQPjpxZeg1yPtLwj2jyUuAV0Dom5yFHWCIiaeY5zdN3JMixw&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'JACKYH',
       'https://accounts.google.com/v3/signin/identifier?dsh=S386651260%3A1681711519884945&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11bK3P3DlFTIc3GQHyNY0Yo7Kf5e8fHk%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11bK3P3DlFTIc3GQHyNY0Yo7Kf5e8fHk%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7RCssIJynCbGUnLhQih0CJ0FT-CwwEFXxJYacYsOsrLdKzrob_rWJhsLt3nwuXZOxK53aDrRQ&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'JASON4703',
       'https://accounts.google.com/v3/signin/identifier?dsh=S1224916245%3A1681711553453460&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1IcBH4h2YkL9HBqzWFkqBIy7Qm6CTh6o%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1IcBH4h2YkL9HBqzWFkqBIy7Qm6CTh6o%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7SIsu2PSmBMPcx3MyxQvTc4gH3HB1tCc8PNoD3TYAm5dLwRlrQdSboxJSr3RgGZRNzN-av0eA&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'JULIAN',
       'https://accounts.google.com/v3/signin/identifier?dsh=S83959985%3A1681711596526038&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11gvbigwoSC6U_Y7z0446IiqHje9FT34%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11gvbigwoSC6U_Y7z0446IiqHje9FT34%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TFQdAK4N0FyXqg0Un8xer3exnIhaVGZTSlPV3FRFVwxC_VYNqY8lEVLQzXKXCFgO8ryE4J9A&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'SCOTT4162',
       'https://accounts.google.com/v3/signin/identifier?dsh=S-872058158%3A1681711634509817&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1VFjbRpmUbUL0xGeat1d9ISw4YvJIvCg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1VFjbRpmUbUL0xGeat1d9ISw4YvJIvCg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TVZsuRtUMX90I7YNdvAxVhQdtvLBge9YW_9XORTvZgXw55JzXV8foUdrZG1oXZI0DtJqv9PA&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'SIMONSH',
       'https://accounts.google.com/v3/signin/identifier?dsh=S-855169725%3A1681711726026711&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1n1cC11Z989d_MgiYGFKsf3uYc4rmGLY%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1n1cC11Z989d_MgiYGFKsf3uYc4rmGLY%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TEnaEzsAO2L0OFX-GzKMeFFPSD4KDneY5cvcnhl42DB2RvbnEDxAh8lOl58rcjfgao97th&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'SPANELY',
       'https://accounts.google.com/v3/signin/identifier?dsh=S319449056%3A1681711664643096&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D17-3hm4jUFmZ9yAwU5273uhkMzBhcVRQ%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D17-3hm4jUFmZ9yAwU5273uhkMzBhcVRQ%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7QvTP5wsn10jaX4xiO_Krwor5vdZe7YIBwx9GaIbXcLHt2UkoJv5hMyYYI1paOJSAWpcoeMyA&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'+','+'WHITE5082',
       ]

date = str(datetime.datetime.now() + datetime.timedelta(days=1)).replace('-','')[0:9]
  

for uri in urll:
    print(uri.split(','))
    
    url = uri.split(',')[0]
    name = uri.split(',')[1]
    All = f"{local_folder}/{name}/{name}_All.xlsx"
 
    
    id = '10773016@gm.scu.edu.tw'
    
    password = '0000007740'
    
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--headless=chrome")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    chrome_options.binary_location = "/chrome/chrome-linux64/chrome"
    service = Service("/chrome/chromedriver")
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_window_size(1920, 1080)

    
    
    driver.get(url)
    n = driver.window_handles
    driver.switch_to.window (n[0])

    #輸入帳號
    
    time.sleep(3)
    driver.find_element(By.NAME,'identifier').send_keys(id)
            
    #下一步
    driver.find_element(By.XPATH,'//*[@id="identifierNext"]/div/button/span').click()
    time.sleep(3)
    
    #輸入密碼
    
            
    time.sleep(3)
    driver.find_element(By.NAME,'Passwd').send_keys(password)
           
       
    
    #下一步
    driver.find_element(By.XPATH,'//*[@id="passwordNext"]/div/button/span').click()
    
    
    
    #編輯
    
    time.sleep(3)
    driver.find_element(By.XPATH,'//*[@id="legendPanel"]/div/div/div[2]/div/div/div[1]/div[4]/div/div[2]/span/span').click()
 
    
    #點選圖層(UCS)選項
    #刪除這個圖層(UCS)
    
    time.sleep(5)
    driver.find_element(By.XPATH,'//*[@id="ly0-layer-status"]/span/div').click()
    driver.find_element(By.XPATH,'//*[@id="ly0-layer-header"]/div[3]').click()
    driver.find_element(By.XPATH,"//*[text()='刪除這個圖層']").click()
    time.sleep(2)
    #pyautogui.press('enter')
    driver.find_element(By.NAME,'delete').click()
           
   
    
    #更改名稱
    driver.refresh()
    time.sleep(20)
    time.sleep(0.5)
    try:
        # 等待 alert 出現
        WebDriverWait(driver, 10).until(EC.alert_is_present())

        alert = driver.switch_to.alert
        print("Alert text:", alert.text)  # 可印出彈窗文字
        alert.accept()  # 按下「重新載入」
    except NoAlertPresentException:
        print("沒有出現 alert 彈窗")
    time.sleep(0.5)     
    
    
    time.sleep(3)
    driver.find_element(By.XPATH,"//*[text()='(未命名的圖層)']").click()
    time.sleep(2)
    driver.find_element(By.XPATH, '//*[@id=":2w.contentEl"]/input').send_keys(name+'_'+date+'_All')
    #pyautogui.typewrite(name+'_'+date+'_All')
    time.sleep(0.5)
    driver.find_element(By.NAME,'save').click()
    time.sleep(0.5)
            
    
    
    #匯入資料
    
    time.sleep(3)
    driver.find_element(By.XPATH,'//*[@id="ly0-layerview-import-link"]').click()
    time.sleep(5)
    soup = BeautifulSoup(driver.page_source,'html.parser')
    time.sleep(2)
    matching_iframes = soup.select('div.fFW7wc.XKSfm-Sx9Kwc-bN97Pc iframe')
    # 遍歷找到的所有元素
    for iframe in matching_iframes:
        iframe_id = iframe.get('id')
        print(iframe_id)
    iframe = driver.find_element(By.XPATH,'//iframe[@id='+"'"+iframe_id+"'"+']')
    driver.switch_to.frame(iframe)
    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="file"]'))
    )
    element.send_keys(All)
    driver.switch_to.default_content()
    
    driver.switch_to.default_content()
    #緯度
    #經度
    
    time.sleep(3)
    driver.find_element(By.XPATH,'//*[@id="upload-checkbox-5"]/span/div').click()
    time.sleep(0.5)
    driver.find_element(By.XPATH,'//*[@id="upload-location-radio-5-0"]/div[2]/span[1]').click()
    time.sleep(0.5)
    
    time.sleep(3)
    driver.find_element(By.XPATH,'//*[@id="upload-checkbox-6"]/span/div').click()
    time.sleep(0.5)
    driver.find_element(By.XPATH,'//*[@id="upload-location-radio-6-1"]/div/span[1]').click()
    time.sleep(0.5)
            
    #繼續
    time.sleep(3)
    driver.find_element(By.XPATH,'/html/body/div[9]/div[3]/button[1]').click()
    #優先別
    time.sleep(3)
    driver.find_element(By.XPATH,'//*[@id="upload-radio-3"]/div/span[1]').click()
    #完成
    time.sleep(3)
    driver.find_element(By.XPATH,'/html/body/div[7]/div[3]/button[1]').click()
           
    time.sleep(10)
    #設計
    time.sleep(3)
    driver.find_element(By.XPATH,'//*[@id="ly0-layerview-stylepopup-link"]/div[2]/div').click()
    driver.find_element(By.XPATH,'//*//*[@id="layer-style-popup"]/div[3]/div[1]').click()
    #優先別
    time.sleep(3)
    try:
        driver.find_element(By.XPATH,'//*[@id="style-by-type-selector-column-str:5qGI5Lu26aGe5Z6L"]/div').click()
    except:
        driver.find_element(By.XPATH,'//*[@id="style-by-type-selector-column-double:5qGI5Lu26aGe5Z6L"]/div').click()
    #關閉畫面
    time.sleep(3)
    driver.find_element(By.XPATH,'//*[@id="layer-style-popup"]/div[1]').click()
    time.sleep(3)
      
    
    r = driver.find_element(By.XPATH,'//*[@id="ly0-layer-items-container"]').text

    
              
    

