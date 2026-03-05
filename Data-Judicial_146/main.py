#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
司法院提存公告資料完整抓取程式
功能：
1. 從司法院網站抓取所有分頁提存公告資料
2. 自動解析案號 (年份、案件類型、文號)
3. 轉換日期格式 (民國年→西元年)
4. 累積儲存到MSSQL資料庫 (每天新增，不覆蓋)
5. 自動使用當天日期
6. 重複執行檢查機制
"""

import requests
import re
import time
import urllib3
import warnings
from bs4 import BeautifulSoup
from datetime import datetime

from config import *
from etl_func import *

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')


class DepositCrawler:
    def __init__(self):
        # 從 config 取得設定
        self.base_url = wbinfo['url']
        self.timeout = crawler['timeout']
        self.page_size = crawler['page_size']
        self.delay = crawler['delay']

        # Session 設定
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-TW,zh;q=0.8,en-US;q=0.5,en;q=0.3',
            'Connection': 'keep-alive',
        })

        # 資料庫連線
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
        lstoken = self.get_initial_page() or "6296572441"

        form_data = {
            'Action': 'Qeury',
            'lstoken': lstoken,
            'Q_DMDeptMainID': '',
            'Q_DTAColumn4': '',
            'Q_DTACaseNumber': '',
            'TBOXDMPostDateS': start_date,
            'TBOXDMPostDateE': end_date,
            'Q_DMTitle': '',
            'Q_DMBody': '',
            'BtnSubmit': '查詢'
        }

        try:
            if page_num == 1:
                response = self.session.post(self.base_url, data=form_data, timeout=30)
            else:
                page_url = f"https://www.judicial.gov.tw/tw/lp-143-1-{page_num}-{page_size}.html"
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
            if 'lp-143-1-' in href and '.html' in href:
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
            announcement_date = item.get('column_5', '')
            converted_date = self.convert_taiwan_to_western_date(announcement_date)

            # 建立處理後記錄
            record = {
                'ItemNumber': item.get('column_0', ''),
                'Court': item.get('column_1', ''),
                'CaseNumber': case_number,
                'CaseYear': case_info['year'],
                'CaseType': case_info['case_type'],
                'CaseFileNumber': case_info['case_number'],
                'ApplicantName': item.get('column_3', ''),
                'DocumentType': item.get('column_4', ''),
                'AnnouncementDate': converted_date,
                'AnnouncementContent': item.get('column_6', '')
            }

            processed_data.append(record)

        print(f"資料處理完成！共處理 {len(processed_data)} 筆有效記錄")
        return processed_data

    def scrape_and_save_page_data(self, start_date, end_date, page_num, total_pages):
        """抓取單頁資料並立即處理保存"""
        print(f"正在抓取第 {page_num}/{total_pages} 頁...", end=" ")

        page_results, _ = self.scrape_single_page(start_date, end_date, page_num)

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
        if insert_data(self.connection, db['totb'], processed_data):
            print(f"成功 {len(processed_data)} 筆")
            return len(processed_data)
        else:
            print("插入失敗")
            return 0

    def run_complete_process(self, start_date=None, end_date=None):
        """執行完整流程"""
        print("司法院提存公告資料完整抓取程式")
        print("=" * 60)

        # 使用當天日期如果沒有指定
        if not start_date or not end_date:
            current_date = self.get_current_taiwan_date()
            start_date = start_date or current_date
            end_date = end_date or current_date

        print(f"抓取日期範圍: {start_date} 至 {end_date}")

        # 1. 連接資料庫
        self.connection = connect_database(
            db['server'], db['username'], db['password'], db['database']
        )
        if not self.connection:
            print("資料庫連接失敗")
            return False

        try:
            # 2. 建立資料表 (如果不存在)
            if not create_table_if_not_exists(self.connection, db['totb']):
                return False

            # 3. 檢查是否已有今天的資料
            western_start = self.convert_taiwan_to_western_date(start_date.replace('/', '-'))
            western_end = self.convert_taiwan_to_western_date(end_date.replace('/', '-'))

            if check_existing_data(self.connection, db['totb'], western_start, western_end):
                print("檢測到今天已有相同日期範圍的資料，自動繼續新增...")

            # 4. 獲取第一頁以確定總頁數
            print("開始抓取司法院提存公告資料...")
            first_page_results, total_pages = self.scrape_single_page(start_date, end_date, 1)

            if not first_page_results:
                print("第一頁抓取失敗")
                return False

            total_saved = 0

            # 5. 處理第一頁
            saved_count = self.scrape_and_save_page_data(start_date, end_date, 1, total_pages)
            total_saved += saved_count

            # 6. 抓取其餘頁面
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
                    time.sleep(self.delay)

            # 7. 驗證資料
            verify_data(self.connection, db['totb'])

            print(f"\n程式執行完成！今天新增 {total_saved} 筆司法院提存公告記錄")
            return True

        finally:
            # 8. 關閉連接
            if self.connection:
                self.connection.close()
                print("資料庫連接已關閉")


def main():
    """主程式"""
    print("司法院提存公告資料抓取程式")
    print("=" * 50)
    print(f"資料庫: {db['server']}.{db['database']}")
    print(f"目標資料表: {db['totb']}")

    # 建立並執行
    crawler = DepositCrawler()

    try:
        success = crawler.run_complete_process()
        if success:
            print("\n所有操作成功完成！")
        else:
            print("\n部分操作失敗，請檢查錯誤訊息")
    except KeyboardInterrupt:
        print("\n\n使用者中斷操作")
    except Exception as e:
        print(f"\n程式執行錯誤: {e}")


if __name__ == "__main__":
    main()