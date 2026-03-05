#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
司法院資料完整抓取程式
功能：
1. 從司法院網站抓取所有分頁公告資料
2. 自動解析案號 (年份、案件類型、文號)
3. 轉換日期格式 (民國年→西元年)
4. 累積儲存到MSSQL資料庫 (每天新增，不覆蓋)
5. 自動使用當天日期
6. 重複執行檢查機制
"""

import requests
import json
import pymssql
import pandas as pd
import re
import time
import urllib3
import warnings
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

class JudicialComplete:
    def __init__(self, server_name='10.10.0.94', database_name='CL_Daily',
                 use_windows_auth=True, username=None, password=None):
        # 網站設定
        self.base_url = "https://www.judicial.gov.tw/tw/lp-139-1.html"
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Connection': 'keep-alive',
        })

        # 資料庫設定
        self.server_name = server_name
        self.database_name = database_name
        self.use_windows_auth = use_windows_auth
        self.username = username
        self.password = password
        self.connection = None

        # 案號解析正則表達式
        self.case_pattern = r'(\d+)年(?:度)?(\w+)字第(\w+)號'

    def get_current_taiwan_date(self):
        """獲取當前民國年日期"""
        now = datetime.now()
        taiwan_year = now.year - 1911
        return f"{taiwan_year}/{now.month:02d}/{now.day:02d}"

    def convert_taiwan_to_western_date(self, taiwan_date):
        """民國年轉西元年"""
        if not taiwan_date or not isinstance(taiwan_date, str):
            return taiwan_date

        try:
            match = re.match(r'(\d+)-(\d+)-(\d+)', taiwan_date.strip())
            if match:
                taiwan_year = int(match.group(1))
                month = match.group(2).zfill(2)
                day = match.group(3).zfill(2)
                western_year = taiwan_year + 1911
                return f"{western_year}-{month}-{day}"
            return taiwan_date
        except Exception:
            return taiwan_date

    def parse_case_number(self, case_number):
        """解析案號"""
        if not case_number:
            return {'year': '', 'case_type': '', 'case_number': '', 'original': case_number or ''}

        case_number = case_number.strip()
        match = re.match(self.case_pattern, case_number)

        if match:
            year = match.group(1)
            case_type = match.group(2)
            number = match.group(3)

            # 去除案件類型中的"度"
            if case_type.endswith('度'):
                case_type = case_type[:-1]

            return {
                'year': year,
                'case_type': case_type,
                'case_number': number,
                'original': case_number
            }
        else:
            # 備用解析
            year_match = re.search(r'(\d+)年', case_number)
            type_match = re.search(r'(\w+)字', case_number)
            number_match = re.search(r'第(\w+)號', case_number)

            year = year_match.group(1) if year_match else ''
            case_type = type_match.group(1) if type_match else ''
            number = number_match.group(1) if number_match else ''

            if case_type.endswith('度'):
                case_type = case_type[:-1]

            return {
                'year': year,
                'case_type': case_type,
                'case_number': number,
                'original': case_number
            }

    def get_initial_page(self):
        """獲取初始頁面token"""
        try:
            response = self.session.get(self.base_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            token_input = soup.find('input', {'name': 'lstoken'})

            return token_input.get('value') if token_input else None
        except Exception as e:
            print(f"獲取初始頁面失敗: {e}")
            return None

    def scrape_single_page(self, start_date, end_date, page_num=1, page_size=20):
        """抓取單頁資料"""
        lstoken = self.get_initial_page() or "1749801548"

        form_data = {
            'Action': 'Query',
            'lstoken': lstoken,
            'Q_DMDeptMainID': '',
            'TBOXDMPostDateS': start_date,
            'TBOXDMPostDateE': end_date,
            'Q_DTACaseNumber': '',
            'Q_DMTitle': '',
            'Q_DTACatCode1': '',
            'Q_DTAColumn4': '',
            'Q_DMCatCode': '',
            'Q_DMBody': '',
            'BtnSubmit': '查詢'
        }

        try:
            if page_num == 1:
                response = self.session.post(self.base_url, data=form_data, timeout=30)
            else:
                page_url = f"https://www.judicial.gov.tw/tw/lp-139-1-{page_num}-{page_size}.html"
                response = self.session.get(page_url, timeout=30)

            response.raise_for_status()
            return self.parse_page_results(response.text)

        except Exception as e:
            print(f"第 {page_num} 頁抓取失敗: {e}")
            return [], 1

    def parse_page_results(self, html_content):
        """解析頁面結果"""
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []
        max_page = 1

        # 解析資料表格
        result_rows = soup.find_all('tr')
        for row in result_rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) > 1:
                row_data = {}
                for i, cell in enumerate(cells):
                    text = cell.get_text(strip=True)
                    if text:
                        row_data[f'column_{i}'] = text
                if row_data:
                    results.append(row_data)

        # 解析分頁資訊
        pagination_links = soup.find_all('a', href=True)
        for link in pagination_links:
            href = link.get('href', '')
            if 'lp-139-1-' in href and '.html' in href:
                try:
                    parts = href.split('-')
                    if len(parts) >= 4:
                        page_num = int(parts[3])
                        max_page = max(max_page, page_num)
                except:
                    continue

        # 也檢查數字連結
        for link in soup.find_all('a'):
            text = link.get_text(strip=True)
            if text.isdigit():
                try:
                    page_num = int(text)
                    max_page = max(max_page, page_num)
                except:
                    continue

        print(f"本頁找到 {len(results)} 筆記錄，總頁數: {max_page}")
        return results, max_page

    def scrape_all_data(self, start_date=None, end_date=None):
        """抓取所有資料"""
        # 使用當天日期如果沒有指定
        if not start_date or not end_date:
            current_date = self.get_current_taiwan_date()
            start_date = start_date or current_date
            end_date = end_date or current_date

        print(f"抓取日期範圍: {start_date} 至 {end_date}")
        print("開始抓取司法院公告資料...")

        all_results = []

        # 獲取第一頁
        first_page_results, total_pages = self.scrape_single_page(start_date, end_date, 1, 20)

        if not first_page_results:
            print("第一頁抓取失敗")
            return []

        # 去除表頭
        if first_page_results and first_page_results[0].get('column_0') == '項次':
            first_page_results = first_page_results[1:]

        all_results.extend(first_page_results)
        print(f"第一頁: {len(first_page_results)} 筆記錄")

        # 抓取其餘頁面
        if total_pages > 1:
            print(f"總共 {total_pages} 頁，開始抓取剩餘頁面...")

            for page_num in range(2, total_pages + 1):
                print(f"正在抓取第 {page_num}/{total_pages} 頁...", end=" ")

                page_results, _ = self.scrape_single_page(start_date, end_date, page_num, 20)

                if page_results:
                    # 去除表頭
                    if page_results and page_results[0].get('column_0') == '項次':
                        page_results = page_results[1:]
                    all_results.extend(page_results)
                    print(f"成功 {len(page_results)} 筆")
                else:
                    print("失敗")

                # 進度顯示
                if page_num % 5 == 0:
                    progress = (page_num / total_pages) * 100
                    print(f"   進度: {progress:.1f}% | 已收集: {len(all_results)} 筆")

                # 延迟避免請求過快
                time.sleep(1)

        print(f"\\n資料抓取完成！總共獲得 {len(all_results)} 筆記錄")
        return all_results

    def scrape_and_save_page_data(self, start_date, end_date, page_num, total_pages):
        """抓取單頁資料並立即處理保存"""
        print(f"正在抓取第 {page_num}/{total_pages} 頁...", end=" ")

        page_results, _ = self.scrape_single_page(start_date, end_date, page_num, 20)

        if not page_results:
            print("失敗")
            return 0

        # 去除表頭
        if page_results and page_results[0].get('column_0') == '項次':
            page_results = page_results[1:]

        if not page_results:
            print("無有效資料")
            return 0

        # 立即處理資料
        processed_data = self.process_data(page_results)
        if not processed_data:
            print("處理失敗")
            return 0

        # 立即插入資料庫
        if self.insert_data(processed_data):
            print(f"成功 {len(processed_data)} 筆")
            return len(processed_data)
        else:
            print("插入失敗")
            return 0

    def scrape_all_data_with_immediate_save(self, start_date=None, end_date=None):
        """抓取所有資料並逐頁保存"""
        # 使用當天日期如果沒有指定
        if not start_date or not end_date:
            current_date = self.get_current_taiwan_date()
            start_date = start_date or current_date
            end_date = end_date or current_date

        print(f"抓取日期範圍: {start_date} 至 {end_date}")
        print("開始抓取司法院公告資料...")

        total_saved = 0

        # 獲取第一頁以確定總頁數
        first_page_results, total_pages = self.scrape_single_page(start_date, end_date, 1, 20)

        if not first_page_results:
            print("第一頁抓取失敗")
            return 0

        # 處理第一頁
        saved_count = self.scrape_and_save_page_data(start_date, end_date, 1, total_pages)
        total_saved += saved_count

        # 抓取其餘頁面
        if total_pages > 1:
            print(f"總共 {total_pages} 頁，開始抓取剩餘頁面...")

            for page_num in range(2, total_pages + 1):
                saved_count = self.scrape_and_save_page_data(start_date, end_date, page_num, total_pages)
                total_saved += saved_count

                # 進度顯示
                if page_num % 5 == 0:
                    progress = (page_num / total_pages) * 100
                    print(f"   進度: {progress:.1f}% | 已儲存: {total_saved} 筆")

                # 延迟避免請求過快
                time.sleep(1)

        print(f"\\n資料抓取完成！總共儲存 {total_saved} 筆記錄")
        return total_saved

    def process_data(self, raw_data):
        """處理原始資料"""
        processed_data = []

        print(f"正在處理 {len(raw_data)} 筆原始資料...")

        for item in raw_data:
            # 跳過表頭
            if item.get('column_0') == '項次':
                continue

            # 解析案號
            case_number = item.get('column_2', '')
            case_info = self.parse_case_number(case_number)

            # 轉換日期
            announcement_date = item.get('column_6', '')
            converted_date = self.convert_taiwan_to_western_date(announcement_date)

            # 建立處理後記錄
            record = {
                'ItemNumber': item.get('column_0', ''),
                'Court': item.get('column_1', ''),
                'CaseNumber': case_number,
                'CaseYear': case_info['year'],
                'CaseType': case_info['case_type'],
                'CaseFileNumber': case_info['case_number'],
                'RecipientName': item.get('column_3', ''),
                'DomesticForeign': item.get('column_4', ''),
                'DocumentType': item.get('column_5', ''),
                'AnnouncementDate': converted_date,
                'CaseCategory': item.get('column_7', ''),
                'AnnouncementContent': item.get('column_8', '')
            }

            processed_data.append(record)

        print(f"資料處理完成！共處理 {len(processed_data)} 筆有效記錄")
        return processed_data

    def connect_database(self):
        """連接資料庫"""
        try:
            if self.use_windows_auth:
                # Windows Authentication 需要額外配置，這裡使用 SQL Server 認證
                self.connection = pymssql.connect(
                    server=self.server_name,
                    database=self.database_name,
                    user=self.username or 'sa',
                    password=self.password or '',
                    timeout=30,
                    login_timeout=30
                )
            else:
                self.connection = pymssql.connect(
                    server=self.server_name,
                    database=self.database_name,
                    user=self.username,
                    password=self.password,
                    timeout=30,
                    login_timeout=30
                )

            print(f"成功連接到資料庫 {self.server_name}.{self.database_name}")
            return True

        except Exception as e:
            print(f"資料庫連接失敗: {e}")
            return False

    def create_table_if_not_exists(self, table_name="JudicialAnnouncements"):
        """如果資料表不存在則建立"""
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()

            # 檢查表是否存在
            check_sql = f"""
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = '{table_name}'
            """
            cursor.execute(check_sql)
            table_exists = cursor.fetchone()[0] > 0

            if table_exists:
                print(f"資料表 '{table_name}' 已存在，將累積新資料")
                return True

            # 建立新表
            create_sql = f"""
            CREATE TABLE {table_name} (
                ID INT IDENTITY(1,1) PRIMARY KEY,
                ItemNumber NVARCHAR(50),
                Court NVARCHAR(200),
                CaseNumber NVARCHAR(200),
                CaseYear NVARCHAR(10),
                CaseType NVARCHAR(50),
                CaseFileNumber NVARCHAR(50),
                RecipientName NVARCHAR(500),
                DomesticForeign NVARCHAR(50),
                DocumentType NVARCHAR(500),
                AnnouncementDate NVARCHAR(20),
                CaseCategory NVARCHAR(100),
                AnnouncementContent NVARCHAR(2000),
                CreatedDate DATETIME DEFAULT GETDATE(),
                ImportDate DATE DEFAULT CONVERT(DATE, GETDATE())
            );
            """

            cursor.execute(create_sql)
            self.connection.commit()
            print(f"資料表 '{table_name}' 建立成功")
            return True

        except Exception as e:
            print(f"建立資料表失敗: {e}")
            return False

    def check_existing_data(self, start_date, end_date, table_name="JudicialAnnouncements"):
        """檢查是否已有今天的資料"""
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()

            # 轉換民國年日期為西元年
            western_start = self.convert_taiwan_to_western_date(start_date.replace('/', '-'))
            western_end = self.convert_taiwan_to_western_date(end_date.replace('/', '-'))

            check_sql = f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE ImportDate = CONVERT(DATE, GETDATE())
            AND AnnouncementDate BETWEEN %s AND %s
            """

            cursor.execute(check_sql, (western_start, western_end))
            count = cursor.fetchone()[0]

            if count > 0:
                print(f"警告: 今天已有 {count} 筆相同日期範圍的資料")
                return True

            return False

        except Exception as e:
            print(f"警告: 檢查現有資料時發生錯誤: {e}")
            return False

    def check_duplicate_record(self, case_number, recipient_name, announcement_date, table_name="JudicialAnnouncements"):
        """檢查是否為重複記錄"""
        if not self.connection:
            return False

        try:
            cursor = self.connection.cursor()
            check_sql = f"""
            SELECT COUNT(*)
            FROM {table_name}
            WHERE CaseNumber = %s AND RecipientName = %s AND AnnouncementDate = %s
            """

            cursor.execute(check_sql, (case_number, recipient_name, announcement_date))
            count = cursor.fetchone()[0]
            return count > 0

        except Exception as e:
            print(f"檢查重複記錄時發生錯誤: {e}")
            return False

    def insert_data(self, processed_data, table_name="JudicialAnnouncements"):
        """插入資料到資料庫"""
        if not self.connection or not processed_data:
            return False

        try:
            cursor = self.connection.cursor()

            insert_sql = f"""
            INSERT INTO {table_name} (
                ItemNumber, Court, CaseNumber, CaseYear, CaseType, CaseFileNumber,
                RecipientName, DomesticForeign, DocumentType, AnnouncementDate,
                CaseCategory, AnnouncementContent
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            # 準備批量插入資料，過濾重複記錄
            batch_data = []
            duplicate_count = 0

            for record in processed_data:
                # 檢查是否重複
                if self.check_duplicate_record(record['CaseNumber'], record['RecipientName'], record['AnnouncementDate'], table_name):
                    duplicate_count += 1
                    continue

                batch_data.append((
                    record['ItemNumber'], record['Court'], record['CaseNumber'],
                    record['CaseYear'], record['CaseType'], record['CaseFileNumber'],
                    record['RecipientName'], record['DomesticForeign'], record['DocumentType'],
                    record['AnnouncementDate'], record['CaseCategory'], record['AnnouncementContent']
                ))

            # 插入非重複記錄
            for record_data in batch_data:
                cursor.execute(insert_sql, record_data)
            self.connection.commit()

            if duplicate_count > 0:
                print(f"跳過 {duplicate_count} 筆重複記錄")
            print(f"成功插入 {len(batch_data)} 筆新記錄到資料庫")
            return True

        except Exception as e:
            print(f"資料插入失敗: {e}")
            self.connection.rollback()
            return False

    def verify_data(self, table_name="JudicialAnnouncements"):
        """驗證資料庫資料"""
        if not self.connection:
            return

        try:
            cursor = self.connection.cursor()

            # 查詢總數
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_count = cursor.fetchone()[0]
            print(f"資料庫總記錄數: {total_count}")

            # 查詢今天新增的記錄數
            cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE ImportDate = CONVERT(DATE, GETDATE())")
            today_count = cursor.fetchone()[0]
            print(f"今天新增記錄數: {today_count}")

            # 查詢最新5筆記錄
            cursor.execute(f"SELECT TOP 5 Court, CaseYear, CaseType, CaseFileNumber, ImportDate FROM {table_name} ORDER BY ID DESC")
            sample_records = cursor.fetchall()

            if sample_records:
                print("\\n最新5筆記錄:")
                for i, record in enumerate(sample_records, 1):
                    print(f"   {i}. {record[0]} | {record[1]}年{record[2]}字第{record[3]}號 | {record[4]}")

        except Exception as e:
            print(f"資料驗證失敗: {e}")

    def close_connection(self):
        """關閉資料庫連接"""
        if self.connection:
            self.connection.close()
            print("資料庫連接已關閉")

    def run_complete_process(self, start_date=None, end_date=None):
        """執行完整流程"""
        print("司法院資料完整抓取程式")
        print("=" * 60)

        # 使用當天日期如果沒有指定
        if not start_date or not end_date:
            current_date = self.get_current_taiwan_date()
            start_date = start_date or current_date
            end_date = end_date or current_date

        # 1. 連接資料庫
        if not self.connect_database():
            print("資料庫連接失敗")
            return False

        try:
            # 2. 建立資料表 (如果不存在)
            if not self.create_table_if_not_exists():
                return False

            # 3. 檢查是否已有今天的資料
            if self.check_existing_data(start_date, end_date):
                print("檢測到今天已有相同日期範圍的資料，自動繼續新增...")
                # 自動繼續執行，不詢問用戶

            # 4. 抓取資料並逐頁保存
            total_saved = self.scrape_all_data_with_immediate_save('2025-11-21', '2025-11-23')
            if total_saved == 0:
                print("沒有成功保存任何資料")
                return False

            # 5. 驗證資料
            self.verify_data()

            print("\\n程式執行完成！")
            print(f"今天新增 {total_saved} 筆司法院公告記錄")

            return True

        finally:
            # 8. 關閉連接
            self.close_connection()

def main():
    """主程式"""
    print("司法院公告資料抓取程式")
    print("=" * 50)

    # 資料庫設定 - 請根據您的環境修改
    DB_CONFIG = {
        'server_name': '10.10.0.94',
        'database_name': 'CL_Daily',
        'use_windows_auth': False,
        'username': 'CLUSER',
        'password': 'Ucredit7607'
    }

    print(f"資料庫: {DB_CONFIG['server_name']}.{DB_CONFIG['database_name']}")
    print(f"驗證方式: {'Windows' if DB_CONFIG['use_windows_auth'] else 'SQL Server'}")

    # 建立並執行
    scraper = JudicialComplete(**DB_CONFIG)

    try:
        success = scraper.run_complete_process()
        if success:
            print("\\n所有操作成功完成！")
        else:
            print("\\n部分操作失敗，請檢查錯誤訊息")
    except KeyboardInterrupt:
        print("\\n\\n使用者中斷操作")
    except Exception as e:
        print(f"\\n程式執行錯誤: {e}")

if __name__ == "__main__":
    main()