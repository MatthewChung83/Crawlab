# -*- coding: utf-8 -*-
"""
ETL functions for OC-GoogleMap - OC visit case data sync to Google Maps
"""
import os
import time
import datetime

import pymssql
import pandas as pd
import paramiko
from scp import SCPClient
from playwright.sync_api import sync_playwright

from config import db, ssh, google


def query_oc_cases(oc_name):
    """Query OC visit cases from database"""
    conn = pymssql.connect(
        server=db['server'],
        user=db['username'],
        password=db['password'],
        database=db['database']
    )
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
              (SQLREPORT.地址 not like '%地號%' or court2.地址 is not null)

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
        where PlanDate is not null and OC not in ('6666','8888') and SVDateTime is null and SVStatus = 'SITE VIS' and OC_Name = '{oc_name}'

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
        from #TSB where OC = '{oc_name}'
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
        from #temp2 where OC = '{oc_name}' and bank not like '%渣打%'
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
        from #temp2 where OC = '{oc_name}' and bank like '%渣打%'
    """
    cursor.execute(script)
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return result


def export_to_excel(data, oc_name):
    """Export data to Excel file"""
    columns = ['案號', '欠款金額', '優先別', '案件類型', '地址', '緯度', '經度', '動機', '案件承辦', '案件承辦分機', '執行時間']
    df = pd.DataFrame(data, columns=columns)

    output_dir = f"{ssh['local_folder']}/{oc_name}"
    os.makedirs(output_dir, exist_ok=True)

    output_path = f"{output_dir}/{oc_name}_All.xlsx"
    df.to_excel(output_path, index=False)
    print(f"Exported: {output_path}")
    return output_path


def create_ssh_client():
    """Create SSH client connection"""
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        ssh['server'],
        ssh['port'],
        ssh['username'],
        ssh['password']
    )
    return client


def upload_folder_via_scp(ssh_client):
    """Upload folder to remote server via SCP"""
    with SCPClient(ssh_client.get_transport()) as scp:
        scp.put(ssh['local_folder'], recursive=True, remote_path=ssh['remote_folder'])
    print("Upload done.")


def update_google_map(url, oc_name, excel_path):
    """Update Google Maps layer using Playwright"""
    date_str = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%Y%m%d')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        try:
            print(f"Processing: {oc_name}")
            page.goto(url)
            page.wait_for_load_state('networkidle')

            # Login - Enter email
            time.sleep(3)
            page.fill('input[name="identifier"]', google['email'])
            page.click('//*[@id="identifierNext"]/div/button/span')
            time.sleep(3)

            # Enter password
            page.wait_for_selector('input[name="Passwd"]', timeout=10000)
            time.sleep(3)
            page.fill('input[name="Passwd"]', google['password'])
            page.click('//*[@id="passwordNext"]/div/button/span')
            time.sleep(5)

            # Click edit button
            page.wait_for_load_state('networkidle')
            time.sleep(3)
            page.click('//*[@id="legendPanel"]/div/div/div[2]/div/div/div[1]/div[4]/div/div[2]/span/span')

            # Delete existing layer
            time.sleep(5)
            page.click('//*[@id="ly0-layer-status"]/span/div')
            page.click('//*[@id="ly0-layer-header"]/div[3]')
            page.click("text=刪除這個圖層")
            time.sleep(2)
            page.click('button[name="delete"]')

            # Refresh and handle alert
            page.reload()
            time.sleep(20)

            # Handle potential alert
            try:
                page.on('dialog', lambda dialog: dialog.accept())
            except:
                pass

            # Rename layer
            time.sleep(3)
            page.click("text=(未命名的圖層)")
            time.sleep(2)
            page.fill('//*[@id=":2w.contentEl"]/input', f"{oc_name}_{date_str}_All")
            time.sleep(0.5)
            page.click('button[name="save"]')
            time.sleep(0.5)

            # Import data
            time.sleep(3)
            page.click('//*[@id="ly0-layerview-import-link"]')
            time.sleep(5)

            # Find iframe and upload file
            iframe_locator = page.locator('div.fFW7wc.XKSfm-Sx9Kwc-bN97Pc iframe')
            iframe = iframe_locator.first
            frame = iframe.content_frame()

            file_input = frame.locator('input[type="file"]')
            file_input.set_input_files(excel_path)
            time.sleep(3)

            # Set latitude column
            page.click('//*[@id="upload-checkbox-5"]/span/div')
            time.sleep(0.5)
            page.click('//*[@id="upload-location-radio-5-0"]/div[2]/span[1]')
            time.sleep(0.5)

            # Set longitude column
            page.click('//*[@id="upload-checkbox-6"]/span/div')
            time.sleep(0.5)
            page.click('//*[@id="upload-location-radio-6-1"]/div/span[1]')
            time.sleep(0.5)

            # Continue
            time.sleep(3)
            page.click('/html/body/div[9]/div[3]/button[1]')

            # Select priority column
            time.sleep(3)
            page.click('//*[@id="upload-radio-3"]/div/span[1]')

            # Complete
            time.sleep(3)
            page.click('/html/body/div[7]/div[3]/button[1]')
            time.sleep(10)

            # Style settings
            time.sleep(3)
            page.click('//*[@id="ly0-layerview-stylepopup-link"]/div[2]/div')
            page.click('//*[@id="layer-style-popup"]/div[3]/div[1]')

            # Select case type column for styling
            time.sleep(3)
            try:
                page.click('//*[@id="style-by-type-selector-column-str:5qGI5Lu26aGe5Z6L"]/div')
            except:
                page.click('//*[@id="style-by-type-selector-column-double:5qGI5Lu26aGe5Z6L"]/div')

            # Close style popup
            time.sleep(3)
            page.click('//*[@id="layer-style-popup"]/div[1]')
            time.sleep(3)

            print(f"Successfully updated map for {oc_name}")

        except Exception as e:
            print(f"Error updating map for {oc_name}: {e}")

        finally:
            browser.close()
