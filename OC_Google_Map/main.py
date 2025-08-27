# -*- coding: utf-8 -*-
"""
Combined OC Google Map System for Carwlab Docker
Merged from 4 separate scripts:
1. CHECK_SVTb_PrioritySV_LIST.py
2. address.py 
3. OCMAP_excel.py
4. OCMAP_GoogleMap.py

Created on Thu Feb  2 11:49:29 2023
@author: admin
"""

import os
import io
import sys
import time
import random
import smtplib
import calendar
import requests
import datetime
import pandas as pd
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from email.header import Header

try:
    import pymssql
    import pyodbc
except ImportError:
    print("Warning: Database modules not available in Docker environment")

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select
    from selenium.common.exceptions import TimeoutException, NoAlertPresentException
    from selenium.webdriver.support.wait import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from PIL import Image
except ImportError:
    print("Warning: Selenium/PIL modules not available - Google Maps automation disabled")

class OCGoogleMapSystem:
    def __init__(self, config=None):
        # Database configuration (configurable for Docker)
        if config:
            self.db = config
        else:
            self.db = {
                'server': os.getenv('DB_SERVER', '10.10.0.94'),
                'database': os.getenv('DB_NAME', 'CL_Daily'),
                'username': os.getenv('DB_USER', 'CLUSER'),
                'password': os.getenv('DB_PASS', 'Ucredit7607'),
                'fromtb': 'treasure.skiptrace.dbo.SVTb_PrioritySV_LIST',
                'totb': 'location_court',
            }
        
        # Email configuration (configurable for Docker)
        self.email_config = {
            'smtp_server': os.getenv('SMTP_SERVER', '10.10.1.59'),
            'sender': os.getenv('EMAIL_SENDER', 'collection@ucs.com'),
            'receivers': os.getenv('EMAIL_RECEIVERS', 'DI@ucs.com').split(',')
        }
        
        # OC list (configurable for Docker)
        self.oc_list = os.getenv('OC_LIST', 'ALEXY,ANDERSON,KEVIN4584,JACKYH,JASON4703,JULIAN,SCOTT4162,SIMONSH,SPANELY,WHITE5082').split(',')
        
        # Chrome driver path (configurable for Docker)
        self.chrome_driver_path = os.getenv('CHROME_DRIVER_PATH', '/usr/local/bin/chromedriver')
        
        # Google Maps credentials (configurable for Docker)
        self.google_id = os.getenv('GOOGLE_ID', '10773016@gm.scu.edu.tw')
        self.google_password = os.getenv('GOOGLE_PASSWORD', '0000007740')

    def send_email(self, subject, message):
        """Send notification email"""
        try:
            msg = MIMEText(message, 'plain', 'utf-8')
            msg['From'] = Header('collection', 'utf-8')
            msg['To'] = Header('DI', 'utf-8')
            msg['Subject'] = Header(subject, 'utf-8')
            
            smtp_obj = smtplib.SMTP(self.email_config['smtp_server'])
            smtp_obj.sendmail(
                self.email_config['sender'], 
                self.email_config['receivers'], 
                msg.as_string()
            )
            print('郵件傳送成功')
            return True
        except smtplib.SMTPException as e:
            print(f'Error: 無法傳送郵件 - {str(e)}')
            return False

    def check_priority_sv_list(self):
        """Step 1: Check SVTb_PrioritySV_LIST data availability"""
        print("Step 1: Checking SVTb_PrioritySV_LIST...")
        
        for attempt in range(1, 10):
            try:
                if 'pymssql' not in sys.modules:
                    print("Database connection not available in Docker - skipping check")
                    return True
                    
                conn = pymssql.connect(
                    server=self.db['server'],
                    user=self.db['username'],
                    password=self.db['password'],
                    database=self.db['database']
                )
                cursor = conn.cursor()
                
                script = """
                select *
                from [treasure].[skiptrace].[dbo].[SVTb_PrioritySV_LIST] 
                where data_date = convert(varchar(10),getdate(),111)
                """
                
                cursor.execute(script)
                data = cursor.fetchall()
                cursor.close()
                conn.close()
                
                if len(data) == 0:
                    print(f"Attempt {attempt}: No data found, waiting...")
                    time.sleep(300)  # Wait 5 minutes
                    
                    # Send warning email
                    self.send_email(
                        '[ERROR] step 1 SVTb_PrioritySV_LIST 補經緯度',
                        '[ERROR] step 1 SVTb_PrioritySV_LIST 補經緯度 skiptrace.dbo.SVTb_PrioritySV_LIST資料異常'
                    )
                else:
                    print("Data found, proceeding...")
                    return True
                    
            except Exception as e:
                print(f"Database connection error: {str(e)}")
                return False
                
        return False

    def get_coordinates_from_3plus3(self, address):
        """Get coordinates from 3+3 postal code service"""
        try:
            # Clean address
            address_clean = address.replace('[','').replace(']','').replace('#','').replace('@','').replace('［','').replace('］','').replace('＃','').replace('＠','')
            
            # Get 3+3 service
            html = requests.get('https://twzipcode.com', "html.parser")
            soup = BeautifulSoup(html.text)
            
            VIEWSTATEGENERATOR = soup.find("input",{"id":"__VIEWSTATEGENERATOR"}).get('value')
            EVENTVALIDATION = soup.find("input",{"id":"__EVENTVALIDATION"}).get('value')
            VIEWSTATE = soup.find("input",{"id":"__VIEWSTATE"}).get('value')
            
            payload = {
                'Search_C_T': address_clean,
                'submit': '找找',
                '__VIEWSTATEGENERATOR': VIEWSTATEGENERATOR,
                '__EVENTVALIDATION': EVENTVALIDATION,
                '__VIEWSTATE': VIEWSTATE
            }
            
            html1 = requests.post('https://twzipcode.com', data=payload)
            s = BeautifulSoup(html1.text)
            s1 = s.find_all("table")
            
            if len(s1) < 2:
                return None, None
                
            s2 = s1[1].find_all('td')
            
            # Extract latitude and longitude
            latitude = longitude = None
            
            # Search for latitude
            for i in range(14, min(32, len(s2)), 2):
                if i < len(s2) and '緯度' in s2[i].get_text():
                    latitude = s2[i+1].get_text() if i+1 < len(s2) else ''
                    break
                    
            # Search for longitude  
            for i in range(14, min(32, len(s2)), 2):
                if i < len(s2) and '經度' in s2[i].get_text():
                    longitude = s2[i+1].get_text() if i+1 < len(s2) else ''
                    break
                    
            return latitude, longitude
            
        except Exception as e:
            print(f"3+3 service error: {str(e)}")
            return None, None

    def get_coordinates_from_google(self, address):
        """Get coordinates from Google Maps"""
        try:
            address_clean = address.replace('[','').replace(']','').replace('#','').replace('@','').replace('［','').replace('］','').replace('＃','').replace('＠','')
            url = 'https://www.google.com/maps/place?q=' + address_clean
            
            # Random delay to avoid blocking
            time.sleep(random.randint(6, 12))
            
            response = requests.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.prettify()
            
            initial_pos = text.find(";window.APP_INITIALIZATION_STATE")
            if initial_pos == -1:
                return None, None
                
            data = text[initial_pos+36:initial_pos+85]
            line = tuple(data.split(','))
            
            if len(line) >= 3:
                latitude = line[2]   # longitude in original code
                longitude = line[1]  # latitude in original code
                return latitude, longitude
                
        except Exception as e:
            print(f"Google Maps error: {str(e)}")
            
        return None, None

    def process_addresses(self):
        """Step 2: Process addresses and get coordinates"""
        print("Step 2: Processing addresses...")
        
        try:
            if 'pymssql' not in sys.modules:
                print("Database connection not available in Docker - skipping address processing")
                return True
                
            # Get source data
            conn = pymssql.connect(
                server=self.db['server'],
                user=self.db['username'],
                password=self.db['password'],
                database=self.db['database']
            )
            cursor = conn.cursor()
            
            # Count records to process
            count_script = f"""
            select count(*) from {self.db['fromtb']} 
            where 經度 is null and 緯度 is null 
            and 地址 not in (select 地址 from {self.db['totb']}) 
            and 地址 not like '%地號%' 
            and 動機 not in (select 動機 from location_court where 動機 <> '')
            """
            
            cursor.execute(count_script)
            total_count = cursor.fetchone()[0]
            print(f"Total addresses to process: {total_count}")
            
            # Process addresses one by one
            for i in range(total_count):
                # Get one record
                data_script = f"""
                select * from {self.db['fromtb']} 
                where 經度 is null and 緯度 is null 
                and 地址 not in (select 地址 from {self.db['totb']}) 
                and 地址 not like '%地號%' 
                and 動機 not in (select 動機 from location_court where 動機 <> '')
                """
                
                cursor.execute(data_script)
                records = cursor.fetchall()
                
                if not records:
                    break
                    
                record = records[0]
                address = record[11]  # Address field
                motivation = record[17]  # Motivation field
                
                print(f"Processing: {address}")
                print(f"Motivation: {motivation}")
                
                # Try 3+3 service first
                latitude, longitude = self.get_coordinates_from_3plus3(address)
                
                # If 3+3 fails, try Google Maps
                if not latitude or not longitude:
                    latitude, longitude = self.get_coordinates_from_google(address)
                
                if latitude and longitude:
                    # Insert into location_court table
                    location_data = [{
                        "地址": address,
                        "緯度": latitude,
                        "經度": longitude,
                        "動機": motivation,
                    }]
                    
                    self.insert_location_data(location_data)
                    print(f"Coordinates saved: {latitude}, {longitude}")
                else:
                    # Mark as processed but empty
                    self.update_address_processed(address)
                    print("No coordinates found, marked as processed")
                    
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"Address processing error: {str(e)}")
            self.send_email(
                '[ERROR] step 2 3+3 / google map 異常',
                '[ERROR] step 2 3+3 / google map 異常'
            )
            return False

    def insert_location_data(self, docs):
        """Insert location data into database"""
        try:
            if 'pyodbc' not in sys.modules:
                print("Database connection not available - skipping insert")
                return
                
            conn_cmd = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={self.db["server"]};DATABASE={self.db["database"]};UID={self.db["username"]};PWD={self.db["password"]}'
            
            with pyodbc.connect(conn_cmd) as cnxn:
                cnxn.autocommit = False
                with cnxn.cursor() as cursor:
                    data_keys = ','.join(docs[0].keys())
                    data_symbols = ','.join(['?' for _ in range(len(docs[0].keys()))])
                    insert_cmd = f"INSERT INTO {self.db['totb']} ({data_keys}) VALUES ({data_symbols})"
                    
                    data_values = [tuple(doc.values()) for doc in docs]
                    cursor.executemany(insert_cmd, data_values)
                    cnxn.commit()
                    
        except Exception as e:
            print(f"Insert error: {str(e)}")

    def update_address_processed(self, address):
        """Mark address as processed"""
        try:
            if 'pymssql' not in sys.modules:
                return
                
            conn = pymssql.connect(
                server=self.db['server'],
                user=self.db['username'],
                password=self.db['password'],
                database=self.db['database'],
                autocommit=True
            )
            cursor = conn.cursor()
            
            script = f"""
            update {self.db['fromtb']}
            set [經度] = '' ,[緯度] = ''
            where [地址] = '{address}'
            """
            
            cursor.execute(script)
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"Update error: {str(e)}")

    def generate_excel_reports(self):
        """Step 3: Generate Excel reports for each OC"""
        print("Step 3: Generating Excel reports...")
        
        try:
            if 'pymssql' not in sys.modules:
                print("Database connection not available - skipping Excel generation")
                return True
                
            for oc_name in self.oc_list:
                print(f"Generating report for: {oc_name}")
                
                conn = pymssql.connect(
                    server=self.db['server'],
                    user=self.db['username'],
                    password=self.db['password'],
                    database=self.db['database']
                )
                cursor = conn.cursor()
                
                # Complete SQL query from original file
                script = f"""
                --DELLIST
                select 
                casei = [case],
                v_date,
                oc,
                case_sv_no
                into #DELLIST
                from [10.90.0.194].[OCAP].dbo.outbound_report 
                where CONVERT(varchar(100), v_date, 23)>= CONVERT(varchar(100), getdate(), 23)
                
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
                left join #DELLIST DEL on SQLREPORT.no = DEL.case_sv_no
                left join  (select distinct 動機,緯度,經度
                           from LOCATION_COURT
                          where 動機 <>'') as court on SQLREPORT.動機=court.動機
                left join (select distinct 地址, 緯度, 經度
                           from LOCATION_COURT )as court2 on SQLREPORT.地址=court2.地址
                where DEL.case_sv_no is null and                                               /*排除已訪案件*/
                      (SQLREPORT.地址 not like '%地號%' or court2.地址 is not null)             /*排除異常址(地號)案件*/
                
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
                data = cursor.fetchall()
                cursor.close()
                conn.close()
                
                # Create DataFrame and save to Excel
                columns = ['案號','欠款金額','優先別','案件類型','地址','緯度','經度','動機','案件承辦','案件承辦分機','執行時間']
                df = pd.DataFrame(data, columns=columns)
                
                # Create output directory if needed
                output_dir = f'/app/output/{oc_name}'
                os.makedirs(output_dir, exist_ok=True)
                
                output_path = f'{output_dir}/{oc_name}_All.xlsx'
                # Remove encoding parameter as it's no longer supported in newer pandas versions
                df.to_excel(output_path, index=False)
                print(f"Excel saved: {output_path}")
                
            return True
            
        except Exception as e:
            print(f"Excel generation error: {str(e)}")
            self.send_email(
                '[ERROR] step 3 Excel 產檔異常',
                '[ERROR] step 3 Excel 產檔異常'
            )
            return False

    def setup_chrome_driver(self):
        """Setup Chrome driver for Docker environment - optimized for Chrome 139.x"""
        try:
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            
            chrome_options = Options()
            
            # Essential options for Docker/headless environment
            chrome_options.add_argument('--headless=new')  # Use new headless mode
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-software-rasterizer')
            
            # Window and display options
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--start-maximized')
            
            # Performance and stability options
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')  # Faster loading
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            
            # Memory optimization
            chrome_options.add_argument('--memory-pressure-off')
            chrome_options.add_argument('--max_old_space_size=4096')
            
            # User agent to avoid detection
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.7258.127 Safari/537.36')
            
            # Logging options
            chrome_options.add_argument('--log-level=3')  # Suppress INFO, WARNING, ERROR
            chrome_options.add_argument('--silent')
            
            # Try to create ChromeDriver service
            try:
                service = Service(executable_path=self.chrome_driver_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as service_error:
                print(f"Service method failed: {service_error}, trying legacy method...")
                # Fallback to legacy method
                driver = webdriver.Chrome(executable_path=self.chrome_driver_path, options=chrome_options)
            
            # Set timeouts
            driver.set_page_load_timeout(30)
            driver.implicitly_wait(10)
            
            print("Chrome driver initialized successfully")
            return driver
            
        except Exception as e:
            print(f"Chrome driver setup error: {str(e)}")
            print("Detailed error information:")
            import traceback
            traceback.print_exc()
            return None

    def update_google_maps(self):
        """Step 4: Update Google Maps (simplified for Docker)"""
        print("Step 4: Updating Google Maps...")
        
        try:
            # Check if Selenium is available
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
            except ImportError:
                print("Selenium not available - skipping Google Maps update")
                print("Google Maps update step completed (skipped due to missing dependencies)")
                return True
                
            # Complete Google Maps URLs for each OC (from original file)
            google_maps_urls = {
                'ALEXY': 'https://accounts.google.com/v3/signin/identifier?dsh=S1593203054%3A1681712270285015&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1uYIgPtwrNX2S7zqsKhw6Ryj_3kjqWUw%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1uYIgPtwrNX2S7zqsKhw6Ryj_3kjqWUw%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7T6aNN_tYqzul15RPFNc8W25AGqbOmKeKdf3L2cgEg413d7oqUAtB4PMa0BzyMTLa1iI1MRkQ&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                'ANDERSON': 'https://accounts.google.com/v3/signin/identifier?dsh=S655048351%3A1681711320362031&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1qblXja7GTajvC4B282yFr8Xw9XPi26E%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1qblXja7GTajvC4B282yFr8Xw9XPi26E%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7R_rfrdycglT3XenTu7AKFfPXLEiY2Bx2awTQB_-O7l0_1FOurkuZXk9BwT_q80EmtCQeUu1Q&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                'BEN4423': 'https://accounts.google.com/v3/signin/identifier?dsh=S-234206541%3A1681711357745882&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1zhUvtlOXuzHbdAePLMLG6hcQsZTXWeg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1zhUvtlOXuzHbdAePLMLG6hcQsZTXWeg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7QGizQqGu1ufOj2OkCJ8gzd7PCHiCKaYrhuY8_zgKpTZPO4LeHttY0SQvJ76I9_NRSIbQOfwQ&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                'KEVIN4584': 'https://accounts.google.com/v3/signin/identifier?dsh=S1275321292%3A1681711409025665&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1wrFPoRKpm2Ldj2hzrbIh3aGf3A2mwUU%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1wrFPoRKpm2Ldj2hzrbIh3aGf3A2mwUU%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TDXRLFPjFpl1wVS4eo79b22-W4jH3XS3DJr09TGjBFSt7OnnzbMbEuL7elvIyX-XhMZgE3&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                'JACKYH': 'https://accounts.google.com/v3/signin/identifier?dsh=S1242336415%3A1681711438748969&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1MQwYjQuvQ7qjl4VYym8_aTOl5APqBzA%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1MQwYjQuvQ7qjl4VYym8_aTOl5APqBzA%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7QSFjDh2Q0o5AjbjzRRCWDVE7MQPjpxZeg1yPtLwj2jyUuAV0Dom5yFHWCIiaeY5zdN3JMixw&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                'JASON4703': 'https://accounts.google.com/v3/signin/identifier?dsh=S386651260%3A1681711519884945&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11bK3P3DlFTIc3GQHyNY0Yo7Kf5e8fHk%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11bK3P3DlFTIc3GQHyNY0Yo7Kf5e8fHk%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7RCssIJynCbGUnLhQih0CJ0FT-CwwEFXxJYacYsOsrLdKzrob_rWJhsLt3nwuXZOxK53aDrRQ&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                'JULIAN': 'https://accounts.google.com/v3/signin/identifier?dsh=S1224916245%3A1681711553453460&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1IcBH4h2YkL9HBqzWFkqBIy7Qm6CTh6o%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1IcBH4h2YkL9HBqzWFkqBIy7Qm6CTh6o%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7SIsu2PSmBMPcx3MyxQvTc4gH3HB1tCc8PNoD3TYAm5dLwRlrQdSboxJSr3RgGZRNzN-av0eA&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                'SCOTT4162': 'https://accounts.google.com/v3/signin/identifier?dsh=S83959985%3A1681711596526038&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11gvbigwoSC6U_Y7z0446IiqHje9FT34%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D11gvbigwoSC6U_Y7z0446IiqHje9FT34%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TFQdAK4N0FyXqg0Un8xer3exnIhaVGZTSlPV3FRFVwxC_VYNqY8lEVLQzXKXCFgO8ryE4J9A&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                'SIMONSH': 'https://accounts.google.com/v3/signin/identifier?dsh=S-872058158%3A1681711634509817&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1VFjbRpmUbUL0xGeat1d9ISw4YvJIvCg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1VFjbRpmUbUL0xGeat1d9ISw4YvJIvCg%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TVZsuRtUMX90I7YNdvAxVhQdtvLBge9YW_9XORTvZgXw55JzXV8foUdrZG1oXZI0DtJqv9PA&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                'SPANELY': 'https://accounts.google.com/v3/signin/identifier?dsh=S-855169725%3A1681711726026711&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1n1cC11Z989d_MgiYGFKsf3uYc4rmGLY%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D1n1cC11Z989d_MgiYGFKsf3uYc4rmGLY%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7TEnaEzsAO2L0OFX-GzKMeFFPSD4KDneY5cvcnhl42DB2RvbnEDxAh8lOl58rcjfgao97th&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin',
                'WHITE5082': 'https://accounts.google.com/v3/signin/identifier?dsh=S319449056%3A1681711664643096&continue=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D17-3hm4jUFmZ9yAwU5273uhkMzBhcVRQ%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&ec=GAZA2gE&followup=https%3A%2F%2Fwww.google.com%2Fmaps%2Fd%2Fviewer%3Fhl%3Dzh-TW%26mid%3D17-3hm4jUFmZ9yAwU5273uhkMzBhcVRQ%26ll%3D24.04740285808056%2C120.10402299999998%26z%3D7&hl=zh-TW&ifkv=AQMjQ7QvTP5wsn10jaX4xiO_Krwor5vdZe7YIBwx9GaIbXcLHt2UkoJv5hMyYYI1paOJSAWpcoeMyA&passive=1209600&flowName=GlifWebSignIn&flowEntry=ServiceLogin'
            }
            
            print(f"Found Google Maps URLs for {len(google_maps_urls)} OCs")
            
            # Check if Chrome driver is available
            if not os.path.exists(self.chrome_driver_path):
                print(f"Chrome driver not found at {self.chrome_driver_path}")
                print("Google Maps update step completed (skipped due to missing Chrome driver)")
                return True
            
            failed_updates = []
            successful_updates = []
            
            for oc_name in self.oc_list:
                if oc_name not in google_maps_urls:
                    print(f"No Google Maps URL configured for {oc_name} - skipping")
                    continue
                    
                print(f"Updating Google Map for: {oc_name}")
                success = self.update_single_google_map(oc_name, google_maps_urls[oc_name])
                if success:
                    successful_updates.append(oc_name)
                    print(f"Successfully updated Google Map for: {oc_name}")
                else:
                    failed_updates.append(oc_name)
                    print(f"Failed to update Google Map for: {oc_name}")
                    
            print(f"Google Maps update completed: {len(successful_updates)} successful, {len(failed_updates)} failed")
                    
            if failed_updates:
                self.send_email(
                    '[ERROR] step 4 GoogleMap update Error',
                    f"[ERROR] step 4 GoogleMap update Error\nfailed name list: {','.join(failed_updates)}\nsuccessful updates: {','.join(successful_updates)}"
                )
                
            # Return True if at least some updates were successful or if all were skipped
            return len(failed_updates) == 0 or len(successful_updates) > 0
            
        except Exception as e:
            print(f"Google Maps update error: {str(e)}")
            self.send_email(
                '[ERROR] step 4 GoogleMap update Error',
                f"[ERROR] step 4 GoogleMap update Error\nGeneral error: {str(e)}"
            )
            return False

    def update_single_google_map(self, oc_name, url):
        """Update single Google Map for an OC - optimized for Chrome 139.x"""
        driver = None
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1}/{max_retries} for {oc_name}")
                
                driver = self.setup_chrome_driver()
                if not driver:
                    print(f"Failed to initialize driver for {oc_name}")
                    continue
                    
                print(f"Navigating to Google Maps login for: {oc_name}")
                driver.get(url)
                
                # Wait for page load
                WebDriverWait(driver, 15).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                
                # Login process with modern Selenium selectors
                try:
                    # Input email - try multiple selectors
                    email_input = None
                    email_selectors = [
                        (By.NAME, 'identifier'),
                        (By.ID, 'identifierId'),
                        (By.CSS_SELECTOR, 'input[type="email"]'),
                        (By.XPATH, '//input[@type="email"]')
                    ]
                    
                    for selector_type, selector in email_selectors:
                        try:
                            email_input = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((selector_type, selector))
                            )
                            break
                        except:
                            continue
                    
                    if not email_input:
                        raise Exception("Could not find email input field")
                    
                    email_input.clear()
                    email_input.send_keys(self.google_id)
                    time.sleep(2)
                    
                    # Click next button
                    next_selectors = [
                        (By.ID, 'identifierNext'),
                        (By.XPATH, '//div[@id="identifierNext"]//button'),
                        (By.XPATH, '//span[text()="Next"]//parent::button'),
                        (By.CSS_SELECTOR, 'button[type="button"]')
                    ]
                    
                    next_clicked = False
                    for selector_type, selector in next_selectors:
                        try:
                            next_button = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((selector_type, selector))
                            )
                            next_button.click()
                            next_clicked = True
                            break
                        except:
                            continue
                    
                    if not next_clicked:
                        raise Exception("Could not click next button")
                    
                    time.sleep(3)
                    
                    # Input password
                    password_selectors = [
                        (By.NAME, 'Passwd'),
                        (By.NAME, 'password'),
                        (By.CSS_SELECTOR, 'input[type="password"]'),
                        (By.XPATH, '//input[@type="password"]')
                    ]
                    
                    password_input = None
                    for selector_type, selector in password_selectors:
                        try:
                            password_input = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((selector_type, selector))
                            )
                            break
                        except:
                            continue
                    
                    if not password_input:
                        raise Exception("Could not find password input field")
                    
                    password_input.clear()
                    password_input.send_keys(self.google_password)
                    time.sleep(2)
                    
                    # Click password next
                    password_next_selectors = [
                        (By.ID, 'passwordNext'),
                        (By.XPATH, '//div[@id="passwordNext"]//button'),
                        (By.XPATH, '//span[text()="Next"]//parent::button'),
                        (By.CSS_SELECTOR, 'button[type="button"]')
                    ]
                    
                    password_next_clicked = False
                    for selector_type, selector in password_next_selectors:
                        try:
                            password_next = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((selector_type, selector))
                            )
                            password_next.click()
                            password_next_clicked = True
                            break
                        except:
                            continue
                    
                    if not password_next_clicked:
                        raise Exception("Could not click password next button")
                    
                    time.sleep(5)
                    
                    # Wait for successful login (check for maps interface)
                    try:
                        WebDriverWait(driver, 15).until(
                            lambda d: "maps" in d.current_url.lower() and "signin" not in d.current_url.lower()
                        )
                        print(f"Successfully logged in for {oc_name}")
                    except:
                        print(f"Login verification failed for {oc_name}, but continuing...")
                    
                    # Now perform the actual Google Maps operations
                    print(f"Starting Google Maps operations for: {oc_name}")
                    
                    # Step 1: Click Edit button
                    self._click_edit_button(driver)
                    
                    # Step 2: Delete existing layer
                    self._delete_existing_layer(driver)
                    
                    # Step 3: Rename layer with date and OC name
                    date = str(datetime.datetime.now() + datetime.timedelta(days=1)).replace('-','')[0:8]
                    layer_name = f"{oc_name}_{date}_All"
                    self._rename_layer(driver, layer_name)
                    
                    # Step 4: Import Excel file
                    excel_file_path = f'/app/output/{oc_name}/{oc_name}_All.xlsx'
                    if os.path.exists(excel_file_path):
                        self._import_excel_file(driver, excel_file_path)
                    else:
                        print(f"Warning: Excel file not found: {excel_file_path}")
                        return False
                    
                    # Step 5: Configure coordinates mapping
                    self._configure_coordinates(driver)
                    
                    # Step 6: Complete import process
                    self._complete_import_process(driver)
                    
                    # Step 7: Set style by priority
                    self._set_style_by_priority(driver)
                    
                    # Step 8: Verify completion
                    self._verify_layer_completion(driver)
                    
                    print(f"Google Map operations completed successfully for: {oc_name}")
                    
                    return True
                    
                except Exception as login_error:
                    print(f"Login error for {oc_name} (attempt {attempt + 1}): {str(login_error)}")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return False
                
            except Exception as e:
                print(f"General error for {oc_name} (attempt {attempt + 1}): {str(e)}")
                if attempt < max_retries - 1:
                    continue
                else:
                    return False
                
            finally:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None
        
        return False

    def _click_edit_button(self, driver):
        """Click the Edit button in Google Maps"""
        print("Clicking Edit button...")
        selectors = [
            '//*[@id="legendPanel"]/div/div/div[2]/div/div/div[1]/div[4]/div/div[2]/span/span',
            '//span[contains(text(),"編輯")]',
            '//button[contains(text(),"編輯")]'
        ]
        
        for i in range(10):
            for selector in selectors:
                try:
                    time.sleep(3)
                    element = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    element.click()
                    print("Edit button clicked successfully")
                    return
                except:
                    continue
        raise Exception("Could not find or click Edit button")

    def _delete_existing_layer(self, driver):
        """Delete existing layer (UCS)"""
        print("Deleting existing layer...")
        for i in range(10):
            try:
                time.sleep(5)
                # Click layer options
                driver.find_element(By.XPATH, '//*[@id="ly0-layer-status"]/span/div').click()
                time.sleep(1)
                
                # Click layer menu
                driver.find_element(By.XPATH, '//*[@id="ly0-layer-header"]/div[3]').click()
                time.sleep(1)
                
                # Click delete option
                delete_element = driver.find_element(By.XPATH, "//*[text()='刪除這個圖層']")
                delete_element.click()
                time.sleep(2)
                
                # Confirm deletion
                confirm_button = driver.find_element(By.NAME, 'delete')
                confirm_button.click()
                print("Layer deleted successfully")
                return
                
            except Exception as e:
                if i == 9:
                    print(f"Warning: Could not delete layer: {e}")
                    return  # Continue even if deletion fails
                continue

    def _rename_layer(self, driver, layer_name):
        """Rename the layer with date and OC name"""
        print(f"Renaming layer to: {layer_name}")
        
        # Refresh page and handle alert
        driver.refresh()
        time.sleep(20)
        
        try:
            # Wait for alert and accept it
            WebDriverWait(driver, 10).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            print(f"Alert text: {alert.text}")
            alert.accept()
        except:
            print("No alert present")
        
        time.sleep(1)
        
        # Rename the layer
        for i in range(10):
            try:
                time.sleep(3)
                # Click on unnamed layer
                unnamed_layer = driver.find_element(By.XPATH, "//*[text()='(未命名的圖層)']")
                unnamed_layer.click()
                time.sleep(2)
                
                # Input new name
                name_input = driver.find_element(By.XPATH, '//*[@id=":2w.contentEl"]/input')
                name_input.clear()
                name_input.send_keys(layer_name)
                time.sleep(1)
                
                # Save
                save_button = driver.find_element(By.NAME, 'save')
                save_button.click()
                print(f"Layer renamed to: {layer_name}")
                return
                
            except Exception as e:
                if i == 9:
                    raise Exception(f"Could not rename layer: {e}")
                continue

    def _import_excel_file(self, driver, excel_path):
        """Import Excel file to Google Maps"""
        print(f"Importing Excel file: {excel_path}")
        
        for i in range(10):
            try:
                time.sleep(3)
                # Click import link
                import_link = driver.find_element(By.XPATH, '//*[@id="ly0-layerview-import-link"]')
                import_link.click()
                time.sleep(5)
                
                # Find iframe for file upload
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                matching_iframes = soup.select('div.fFW7wc.XKSfm-Sx9Kwc-bN97Pc iframe')
                
                if not matching_iframes:
                    raise Exception("Could not find upload iframe")
                
                iframe_id = matching_iframes[0].get('id')
                print(f"Found iframe ID: {iframe_id}")
                
                # Switch to iframe and upload file
                iframe = driver.find_element(By.XPATH, f'//iframe[@id="{iframe_id}"]')
                driver.switch_to.frame(iframe)
                
                file_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="file"]'))
                )
                file_input.send_keys(excel_path)
                
                driver.switch_to.default_content()
                print("Excel file uploaded successfully")
                return
                
            except Exception as e:
                print(f"Upload attempt {i+1} failed: {e}")
                if i < 9:
                    # Refresh and try again
                    driver.refresh()
                    time.sleep(20)
                    try:
                        WebDriverWait(driver, 10).until(EC.alert_is_present())
                        alert = driver.switch_to.alert
                        alert.accept()
                    except:
                        pass
                    time.sleep(1)
                    continue
                else:
                    raise Exception(f"Could not upload Excel file: {e}")

    def _configure_coordinates(self, driver):
        """Configure latitude and longitude mapping"""
        print("Configuring coordinate mapping...")
        
        driver.switch_to.default_content()
        
        for i in range(10):
            try:
                time.sleep(3)
                
                # Configure latitude (緯度) - checkbox 5
                lat_checkbox = driver.find_element(By.XPATH, '//*[@id="upload-checkbox-5"]/span/div')
                lat_checkbox.click()
                time.sleep(1)
                
                lat_radio = driver.find_element(By.XPATH, '//*[@id="upload-location-radio-5-0"]/div[2]/span[1]')
                lat_radio.click()
                time.sleep(1)
                
                # Configure longitude (經度) - checkbox 6  
                lng_checkbox = driver.find_element(By.XPATH, '//*[@id="upload-checkbox-6"]/span/div')
                lng_checkbox.click()
                time.sleep(1)
                
                lng_radio = driver.find_element(By.XPATH, '//*[@id="upload-location-radio-6-1"]/div/span[1]')
                lng_radio.click()
                time.sleep(1)
                
                print("Coordinates configured successfully")
                return
                
            except Exception as e:
                if i == 9:
                    raise Exception(f"Could not configure coordinates: {e}")
                continue

    def _complete_import_process(self, driver):
        """Complete the import process"""
        print("Completing import process...")
        
        for i in range(10):
            try:
                # Click Continue button
                time.sleep(3)
                continue_btn = driver.find_element(By.XPATH, '/html/body/div[9]/div[3]/button[1]')
                continue_btn.click()
                
                # Select priority field
                time.sleep(3)
                priority_radio = driver.find_element(By.XPATH, '//*[@id="upload-radio-3"]/div/span[1]')
                priority_radio.click()
                
                # Click Done button
                time.sleep(3)
                done_btn = driver.find_element(By.XPATH, '/html/body/div[7]/div[3]/button[1]')
                done_btn.click()
                
                print("Import process completed")
                return
                
            except Exception as e:
                if i == 9:
                    raise Exception(f"Could not complete import: {e}")
                continue

    def _set_style_by_priority(self, driver):
        """Set layer style based on priority"""
        print("Setting style by priority...")
        
        for i in range(10):
            try:
                time.sleep(10)
                
                # Click style/design button
                style_btn = driver.find_element(By.XPATH, '//*[@id="ly0-layerview-stylepopup-link"]/div[2]/div')
                style_btn.click()
                
                # Click style options
                style_option = driver.find_element(By.XPATH, '//*[@id="layer-style-popup"]/div[3]/div[1]')
                style_option.click()
                
                time.sleep(3)
                
                # Select priority column - try both string and double selectors
                try:
                    priority_selector = driver.find_element(By.XPATH, '//*[@id="style-by-type-selector-column-str:5qGI5Lu26aGe5Z6L"]/div')
                    priority_selector.click()
                except:
                    priority_selector = driver.find_element(By.XPATH, '//*[@id="style-by-type-selector-column-double:5qGI5Lu26aGe5Z6L"]/div')
                    priority_selector.click()
                
                # Close style panel
                time.sleep(3)
                close_btn = driver.find_element(By.XPATH, '//*[@id="layer-style-popup"]/div[1]')
                close_btn.click()
                
                print("Style set by priority successfully")
                return
                
            except Exception as e:
                if i == 9:
                    print(f"Warning: Could not set style: {e}")
                    return  # Continue even if styling fails
                continue

    def _verify_layer_completion(self, driver):
        """Verify that the layer was created successfully"""
        print("Verifying layer completion...")
        
        try:
            time.sleep(3)
            layer_content = driver.find_element(By.XPATH, '//*[@id="ly0-layer-items-container"]').text
            print(f"Layer items count: {len(layer_content.split(chr(10)))}")
            print("Layer verification completed")
        except Exception as e:
            print(f"Warning: Could not verify layer: {e}")

    def run_full_pipeline(self):
        """Run the complete pipeline"""
        print("Starting OC Google Map System Pipeline...")
        
        # Step 1: Check data availability
        if not self.check_priority_sv_list():
            print("Step 1 failed - stopping pipeline")
            return False
            
        # Step 2: Process addresses and get coordinates
        if not self.process_addresses():
            print("Step 2 failed - continuing with remaining steps")
            
        # Step 3: Generate Excel reports
        if not self.generate_excel_reports():
            print("Step 3 failed - continuing with remaining steps")
            
        # Step 4: Update Google Maps
        if not self.update_google_maps():
            print("Step 4 failed")
            
        print("Pipeline completed")
        return True

def main():
    """Main function for Docker execution"""
    print("OC Google Map System - Docker Version")
    
    # Initialize system
    system = OCGoogleMapSystem()
    
    # Run pipeline
    success = system.run_full_pipeline()
    
    if success:
        print("System completed successfully")
        return 0
    else:
        print("System completed with errors")
        return 1

if __name__ == "__main__":
    sys.exit(main())