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

import os
import sys
import requests
import re
import time
import urllib3
import warnings
from bs4 import BeautifulSoup
from datetime import datetime

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import *
from common.logger import get_logger

# Initialize logger
logger = get_logger('Data-Judicial_146')

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

            if case_type.endswith('度'):
                case_type = case_type[:-1]

            return {
                'year': year,
                'case_type': case_type,
                'case_number': number,
                'original': case_number
            }
        else:
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
        logger.ctx.set_operation("get_token")
        try:
            start_time = time.time()
            logger.log_request("GET", self.base_url, self.session.headers, None)

            response = self.session.get(self.base_url)
            elapsed = time.time() - start_time

            logger.log_response(response.status_code, dict(response.headers), f"[HTML: {len(response.text)} chars]", elapsed)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            token_input = soup.find('input', {'name': 'lstoken'})

            token = token_input.get('value') if token_input else None
            if token:
                logger.debug(f"取得 token: {token[:20]}...")
            else:
                logger.warning("未找到 token")
            return token
        except Exception as e:
            logger.log_exception(e, "獲取初始頁面失敗")
            return None

    def scrape_single_page(self, start_date, end_date, page_num=1, page_size=20):
        """抓取單頁資料"""
        logger.ctx.set_operation("scrape_page")
        logger.ctx.set_data(page=page_num, start_date=start_date, end_date=end_date)

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
            start_time = time.time()
            if page_num == 1:
                logger.log_request("POST", self.base_url, self.session.headers, form_data)
                response = self.session.post(self.base_url, data=form_data, timeout=30)
            else:
                page_url = f"https://www.judicial.gov.tw/tw/lp-143-1-{page_num}-{page_size}.html"
                logger.log_request("GET", page_url, self.session.headers, None)
                response = self.session.get(page_url, timeout=30)

            elapsed = time.time() - start_time
            logger.log_response(response.status_code, dict(response.headers), f"[HTML: {len(response.text)} chars]", elapsed)

            response.raise_for_status()
            return self.parse_page_results(response.text)

        except requests.exceptions.Timeout as e:
            logger.log_http_error(e, self.base_url)
            logger.error(f"第 {page_num} 頁請求超時")
            return [], 1
        except requests.exceptions.RequestException as e:
            logger.log_http_error(e, self.base_url)
            return [], 1
        except Exception as e:
            logger.log_exception(e, f"第 {page_num} 頁抓取失敗")
            return [], 1

    def parse_page_results(self, html_content):
        """解析頁面結果"""
        soup = BeautifulSoup(html_content, 'html.parser')
        results = []
        max_page = 1

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

        for link in soup.find_all('a'):
            text = link.get_text(strip=True)
            if text.isdigit():
                try:
                    page_num = int(text)
                    max_page = max(max_page, page_num)
                except:
                    continue

        logger.debug(f"本頁找到 {len(results)} 筆記錄，總頁數: {max_page}")
        return results, max_page

    def process_data(self, raw_data):
        """處理原始資料"""
        processed_data = []

        logger.debug(f"正在處理 {len(raw_data)} 筆原始資料...")

        for item in raw_data:
            if item.get('column_0') == '項次':
                continue

            case_number = item.get('column_2', '')
            case_info = self.parse_case_number(case_number)

            announcement_date = item.get('column_5', '')
            converted_date = self.convert_taiwan_to_western_date(announcement_date)

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

        logger.debug(f"資料處理完成！共處理 {len(processed_data)} 筆有效記錄")
        return processed_data

    def scrape_and_save_page_data(self, start_date, end_date, page_num, total_pages):
        """抓取單頁資料並立即處理保存"""
        logger.log_progress(page_num, total_pages, f"page_{page_num}")

        page_results, _ = self.scrape_single_page(start_date, end_date, page_num)

        if not page_results:
            logger.warning(f"第 {page_num} 頁無資料")
            return 0

        if page_results and page_results[0].get('column_0') == '項次':
            page_results = page_results[1:]

        if not page_results:
            logger.debug(f"第 {page_num} 頁無有效資料")
            return 0

        processed_data = self.process_data(page_results)
        if not processed_data:
            logger.warning(f"第 {page_num} 頁處理失敗")
            return 0

        logger.ctx.set_operation("DB_insert")
        logger.ctx.set_db(server=db['server'], database=db['database'], table=db['totb'], operation="INSERT")

        if insert_data(self.connection, db['totb'], processed_data):
            logger.log_db_operation("INSERT", db['database'], db['totb'], len(processed_data))
            logger.increment('records_success', len(processed_data))
            return len(processed_data)
        else:
            logger.error(f"第 {page_num} 頁資料插入失敗")
            logger.increment('records_failed', len(processed_data))
            return 0

    def run_complete_process(self, start_date=None, end_date=None):
        """執行完整流程"""
        logger.task_start("司法院提存公告資料抓取 (146)")

        if not start_date or not end_date:
            current_date = self.get_current_taiwan_date()
            start_date = start_date or current_date
            end_date = end_date or current_date

        logger.info(f"抓取日期範圍: {start_date} 至 {end_date}")

        logger.ctx.set_operation("DB_connect")
        logger.log_db_connect(db['server'], db['database'], db['username'])

        self.connection = connect_database(
            db['server'], db['username'], db['password'], db['database']
        )
        if not self.connection:
            logger.error("資料庫連接失敗")
            logger.task_end(success=False)
            return False

        try:
            if not create_table_if_not_exists(self.connection, db['totb']):
                logger.error("建立資料表失敗")
                logger.task_end(success=False)
                return False

            western_start = self.convert_taiwan_to_western_date(start_date.replace('/', '-'))
            western_end = self.convert_taiwan_to_western_date(end_date.replace('/', '-'))

            if check_existing_data(self.connection, db['totb'], western_start, western_end):
                logger.info("檢測到今天已有相同日期範圍的資料，自動繼續新增...")

            logger.info("開始抓取司法院提存公告資料...")
            first_page_results, total_pages = self.scrape_single_page(start_date, end_date, 1)

            if not first_page_results:
                logger.error("第一頁抓取失敗")
                logger.task_end(success=False)
                return False

            logger.info(f"總頁數: {total_pages}")
            total_saved = 0

            saved_count = self.scrape_and_save_page_data(start_date, end_date, 1, total_pages)
            total_saved += saved_count

            if total_pages > 1:
                logger.info(f"開始抓取剩餘 {total_pages - 1} 頁...")

                for page_num in range(2, total_pages + 1):
                    saved_count = self.scrape_and_save_page_data(start_date, end_date, page_num, total_pages)
                    total_saved += saved_count

                    time.sleep(self.delay)

            verify_data(self.connection, db['totb'])

            logger.log_stats({
                'total_pages': total_pages,
                'total_saved': total_saved,
            })

            logger.task_end(success=True)
            return True

        except Exception as e:
            logger.log_exception(e, "執行過程發生錯誤")
            logger.task_end(success=False)
            return False

        finally:
            if self.connection:
                self.connection.close()
                logger.info("資料庫連接已關閉")


def run(start_date=None, end_date=None):
    """Main execution function"""
    crawler = DepositCrawler()
    return crawler.run_complete_process(start_date, end_date)


def main():
    """主程式"""
    logger.info(f"資料庫: {db['server']}.{db['database']}")
    logger.info(f"目標資料表: {db['totb']}")

    try:
        success = run()
        if success:
            logger.info("所有操作成功完成！")
        else:
            logger.warning("部分操作失敗，請檢查錯誤訊息")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == "__main__":
    main()
