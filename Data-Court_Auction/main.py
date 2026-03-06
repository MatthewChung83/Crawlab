# -*- coding: utf-8 -*-
"""
Court Auction Crawler - Requests Version
Based on Data-Judicial_fam standard structure

Usage:
    python main.py                    # Use today's date
    python main.py --start_date 20240101  # Use specific date
"""

import datetime
import requests
import json
import os
import sys
import time
import argparse
import pdfplumber
from typing import List, Dict, Optional

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import db, wbinfo, crawler, crawl_types, paths
from etl_func import (
    src_obs, get_existing_pdfs, generate_id, parse_tw_date,
    normalize_text, auction_item, auction_info_item, toSQL, exit_obs
)
from common.logger import get_logger

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initialize logger
logger = get_logger('Data-Court_Auction')


class PDFReader:
    """PDF Reader for auction documents"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file = None
        logger.ctx.set_operation("PDF_open")
        logger.ctx.set_data(file_path=file_path)
        try:
            self.file = pdfplumber.open(file_path)
            logger.debug(f"PDF 開啟成功: {file_path}")
        except Exception as e:
            logger.log_exception(e, f"PDF 開啟失敗: {file_path}")
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()

    def extract_owners(self, text: str) -> List[str]:
        """Extract property owners from text"""
        if '財產所有人：' not in text:
            return []

        owner_text = text.split('財產所有人：')[-1]
        owner_text = normalize_text(owner_text)

        # Split by common separators
        separators = ['兼', '即', '、', ',', '，', ' ']
        owners = [owner_text]
        for sep in separators:
            new_owners = []
            for owner in owners:
                new_owners.extend(owner.split(sep))
            owners = new_owners

        # Clean and filter
        cleaned = []
        for owner in owners:
            owner = normalize_text(owner).strip()
            if owner and len(owner) > 1 and owner not in ['之', '及', '與', '或', '等']:
                cleaned.append(owner)

        return list(dict.fromkeys(cleaned))  # Remove duplicates

    def extract_parcels(self, table_rows: List) -> List[Dict]:
        """Extract parcel info from table"""
        parcels = []

        for row in table_rows:
            row = [normalize_text(str(cell)) if cell else '' for cell in row if cell is not None]

            if len(row) < 3:
                continue

            if row[0].isdigit() and len(row) >= 6:
                country = normalize_text(row[1]).replace('臺', '台')
                district = normalize_text(row[2]) if len(row) > 2 else ''

                parcel_parts = []
                for i, suffix in enumerate(['段', '小段', '地號']):
                    if i + 3 < len(row) and row[i + 3]:
                        part = normalize_text(row[i + 3])
                        if part:
                            parcel_parts.append(part + suffix)

                if parcel_parts:
                    parcel_name = country + district + ''.join(parcel_parts)
                    area_info = ''
                    if len(row) >= 8:
                        area_parts = [normalize_text(row[6]), normalize_text(row[7])]
                        area_info = ' x '.join(filter(None, area_parts))

                    parcel = {'parcel': parcel_name, 'area': area_info}
                    if parcel not in parcels:
                        parcels.append(parcel)

        return parcels

    def extract(self) -> List[Dict]:
        """Main extraction method"""
        if not self.file:
            return []

        owners = []
        parcels = []
        logger.ctx.set_operation("PDF_extract")

        try:
            for page in self.file.pages:
                page_text = page.extract_text() or ""
                page_text = normalize_text(page_text)

                if not owners and '財產所有人：' in page_text:
                    owners = self.extract_owners(page_text)

                tables = page.extract_tables()
                for table in tables:
                    if table:
                        page_parcels = self.extract_parcels(table)
                        parcels.extend(page_parcels)

            if not owners:
                owners = ['']
            if not parcels:
                parcels = [{'parcel': '', 'area': ''}]

            output = []
            for owner in owners:
                for parcel in parcels:
                    output.append({
                        'owner': normalize_text(owner),
                        'parcel': normalize_text(parcel.get('parcel', '')),
                        'area': normalize_text(parcel.get('area', '')),
                    })

            logger.debug(f"PDF 解析完成: owners={len(owners)}, parcels={len(parcels)}")
            return output

        except Exception as e:
            logger.log_exception(e, "PDF 內容解析失敗")
            return []


def get_date_range(start_date: str):
    """Generate query date range"""
    from dateutil import parser
    from datetime import timedelta

    date = parser.parse(start_date)
    start_date_str = f"{date.year - 1911}{date.strftime('%m')}{date.strftime('%d')}"
    end_date = date + timedelta(days=crawler['days_ahead'])
    end_date_str = f"{end_date.year - 1911}{end_date.strftime('%m')}{end_date.strftime('%d')}"
    return start_date_str, end_date_str


def get_page_data(session, page_num: int, sale_type: str, prop_type: str,
                  start_date: str, end_date: str) -> Optional[Dict]:
    """Get page data from API"""
    logger.ctx.set_operation("API_fetch_page")
    logger.ctx.set_data(page=page_num, sale_type=sale_type, prop_type=prop_type)

    form_data = {
        'crtnm': '全部',
        'proptype': prop_type,
        'saletype': sale_type,
        'sorted_column': 'A.CRMYY, A.CRMID, A.CRMNO, A.SALENO, A.ROWID',
        'sorted_type': 'ASC',
        'pageNum': str(page_num),
        'saledate1': start_date,
        'saledate2': end_date,
        'pageSize': '100',
    }

    start_time = time.time()
    try:
        logger.log_request("POST", wbinfo['url'], session.headers, form_data)

        response = session.post(
            wbinfo['url'],
            data=form_data,
            timeout=crawler['timeout'],
            verify=False
        )
        elapsed = time.time() - start_time

        logger.log_response(
            response.status_code,
            dict(response.headers),
            response.text[:500] if len(response.text) > 500 else response.text,
            elapsed
        )

        response.raise_for_status()
        return json.loads(response.text)

    except requests.exceptions.Timeout as e:
        logger.log_http_error(e, wbinfo['url'])
        logger.error(f"請求超時: page={page_num}, timeout={crawler['timeout']}s")
        return None
    except requests.exceptions.RequestException as e:
        logger.log_http_error(e, wbinfo['url'])
        return None
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失敗: {e}")
        logger.error(f"回應內容: {response.text[:500]}")
        return None
    except Exception as e:
        logger.log_exception(e, f"取得頁面資料失敗: page={page_num}")
        return None


def build_auction_info(item: Dict, sale_type: str, prop_type: str) -> Dict:
    """Build auction info from API item"""
    court = normalize_text(item.get('crtnm', ''))
    number = normalize_text(item.get('crm', '') + item.get('dptstr', ''))
    unit = normalize_text(item.get('dptstr', '')[1:-1] if len(item.get('dptstr', '')) > 2 else '')

    sale_date = item.get('saledate', '')
    if len(sale_date) >= 8:
        formatted_date = f"{sale_date[:-4]}/{sale_date[-4:-2]}/{sale_date[-2:]}"
    else:
        formatted_date = sale_date

    sale_no = item.get('saleno', '')
    date_with_turn = f"{formatted_date} 第{sale_no}拍" if sale_no else formatted_date

    address_parts = [
        item.get('hsimun', ''), item.get('ctmd', ''), item.get('budadd', ''),
        item.get('secstr', ''), item.get('area3str', ''), item.get('saleamtstr', '')
    ]
    address = normalize_text(' '.join(filter(None, address_parts)))
    country = normalize_text(' '.join(filter(None, [item.get('hsimun', ''), item.get('ctmd', '')])))

    return {
        'court': court,
        'number': number,
        'unit': unit,
        'date': date_with_turn,
        'turn': f"第{sale_no}拍" if sale_no else '',
        'reserve': normalize_text(item.get('saleamtstr', '')),
        'price': '',
        'address': address,
        'date_datetime': parse_tw_date(formatted_date),
        'country': country,
        'reserve_int': int(item.get('minprice', 0)) if item.get('minprice') else 0,
        'handover': normalize_text(item.get('checkynstr', '')),
        'vacancy': normalize_text(item.get('emptyynstr', '')),
        'target': normalize_text(item.get('batchno', '')),
        'document': f"{wbinfo['pdf_url']}?filenm={item.get('filenm')}",
        'saletype': sale_type,
        'proptype': prop_type,
        'remark': normalize_text(item.get('rmk', '')),
    }


def generate_pdf_filename(auction_info: Dict, item: Dict) -> str:
    """Generate PDF filename"""
    sale_date = item.get('saledate', '')
    sale_no = item.get('saleno', '')
    return f"{auction_info['court']}_{auction_info['number']}_{sale_date}_第{sale_no}拍.pdf"


def process_page_data(session, data_list: List[Dict], sale_type: str, prop_type: str,
                      existing_pdfs: List[str], output_dir: str) -> int:
    """Process page data and save to database"""
    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']
    totb = db['totb']
    auction_info_tb = db['auction_info_tb']

    processed_count = 0
    total_items = len(data_list)

    for idx, item in enumerate(data_list, 1):
        logger.ctx.set_progress(idx, total_items)
        logger.ctx.set_operation("process_auction_item")

        try:
            auction_info = build_auction_info(item, sale_type, prop_type)
            pdf_filename = generate_pdf_filename(auction_info, item)
            logger.ctx.set_data(
                court=auction_info['court'],
                number=auction_info['number'],
                pdf=pdf_filename
            )

            if pdf_filename in existing_pdfs:
                logger.debug(f"PDF 已存在，跳過: {pdf_filename}")
                continue

            # Generate rowid
            rowid = generate_id({
                'number': auction_info['number'],
                'date': auction_info['date']
            })
            auction_info['rowid'] = rowid
            auction_info['entrydate'] = datetime.datetime.now()

            # Save auction info
            logger.ctx.set_operation("DB_insert_auction")
            logger.ctx.set_db(server=server, database=database, table=totb, operation="INSERT")

            docs = auction_item(auction_info)
            toSQL(docs, totb, server, database, username, password)
            logger.log_db_operation("INSERT", database, totb, 1)
            logger.info(f"儲存拍賣資訊: {auction_info['court']} {auction_info['number']}")

            # Download and parse PDF
            pdf_url = auction_info['document']
            logger.ctx.set_operation("PDF_download")

            try:
                start_time = time.time()
                logger.log_request("GET", pdf_url, session.headers, None)

                response = session.get(pdf_url, timeout=crawler['pdf_timeout'], verify=False)
                elapsed = time.time() - start_time

                logger.log_response(response.status_code, dict(response.headers), f"[PDF Binary: {len(response.content)} bytes]", elapsed)
                response.raise_for_status()

                pdf_path = os.path.join(output_dir, pdf_filename)
                with open(pdf_path, 'wb') as f:
                    f.write(response.content)
                logger.debug(f"PDF 下載完成: {pdf_filename}, size={len(response.content)}")

                # Parse PDF
                logger.ctx.set_operation("PDF_parse")
                with PDFReader(pdf_path) as reader:
                    pdf_data = reader.extract()

                pdf_items_count = 0
                for pdf_item in pdf_data:
                    info_data = {
                        **pdf_item,
                        'court': auction_info['court'],
                        'number': auction_info['number'],
                        'date': auction_info['date'],
                        'country': auction_info.get('country', ''),
                        'address': auction_info.get('address', ''),
                        'refertb': totb,
                        'referi': rowid,
                        'entrydate': datetime.datetime.now(),
                    }
                    info_data['rowid'] = generate_id(info_data)

                    info_docs = auction_info_item(info_data)
                    toSQL(info_docs, auction_info_tb, server, database, username, password)
                    pdf_items_count += 1

                logger.log_db_operation("INSERT", database, auction_info_tb, pdf_items_count)
                logger.info(f"PDF 處理完成: {pdf_filename}, items={pdf_items_count}")

            except requests.exceptions.Timeout as e:
                logger.log_http_error(e, pdf_url)
                logger.warning(f"PDF 下載超時: {pdf_url}")
            except requests.exceptions.RequestException as e:
                logger.log_http_error(e, pdf_url)
            except Exception as e:
                logger.log_exception(e, f"PDF 處理失敗: {pdf_url}")

            processed_count += 1
            logger.increment('records_success')

            # Check daily limit
            exit_count = exit_obs(server, username, password, database, totb)
            if exit_count >= 10000:
                logger.warning(f"每日處理上限達成: {exit_count} >= 10000")
                logger.task_end(success=True)
                sys.exit(0)

        except Exception as e:
            logger.log_exception(e, f"處理拍賣項目失敗: item_index={idx}")
            logger.increment('records_failed')
            continue

    return processed_count


def run(start_date: str = None):
    """Main execution function"""
    if start_date is None:
        start_date = datetime.datetime.now().strftime('%Y%m%d')

    # Start task logging
    logger.task_start("法拍屋資料爬取")

    logger.info(f"查詢起始日期: {start_date}")

    # Log database config
    logger.log_db_connect(db['server'], db['database'], db['username'])

    # Setup session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    session.verify = False

    # Create output directory
    output_dir = paths['output_dir']
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"輸出目錄: {output_dir}")

    # Get existing PDFs
    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']
    totb = db['totb']

    logger.ctx.set_operation("DB_query_existing")
    obs = src_obs(server, username, password, database, totb, totb)
    logger.info(f"現有記錄數: {obs}")

    existing_pdfs = get_existing_pdfs(server, username, password, database, totb)
    logger.info(f"現有 PDF 數: {len(existing_pdfs)}")

    # Get date range
    start_date_str, end_date_str = get_date_range(start_date)
    logger.info(f"查詢日期範圍: {start_date_str} - {end_date_str}")

    total_processed = 0
    success = True

    try:
        for sale_type in crawl_types['sale_types']:
            for prop_type in crawl_types['prop_types']:
                logger.info(f"處理類型: sale_type={sale_type}, prop_type={prop_type}")
                logger.ctx.set_data(sale_type=sale_type, prop_type=prop_type)

                # Get first page
                first_page = get_page_data(session, 1, sale_type, prop_type, start_date_str, end_date_str)
                if not first_page:
                    logger.warning(f"無法取得第一頁資料: sale_type={sale_type}, prop_type={prop_type}")
                    continue

                total_num = first_page.get('pageInfo', {}).get('totalNum', 0)
                max_page = (total_num // 100) + 1
                logger.info(f"總記錄數: {total_num}, 總頁數: {max_page}")

                # Process all pages
                for page in range(1, max_page + 1):
                    logger.log_progress(page, max_page, f"page_{page}")

                    page_data = get_page_data(session, page, sale_type, prop_type, start_date_str, end_date_str)
                    if not page_data:
                        logger.warning(f"無法取得頁面資料: page={page}")
                        continue

                    processed = process_page_data(
                        session,
                        page_data.get('data', []),
                        sale_type,
                        prop_type,
                        existing_pdfs,
                        output_dir
                    )
                    total_processed += processed

                    time.sleep(crawler['delay'])

    except KeyboardInterrupt:
        logger.warning("使用者中斷執行")
        success = False
    except Exception as e:
        logger.log_exception(e, "爬蟲執行過程發生錯誤")
        success = False

    # Log final statistics
    logger.log_stats({
        'total_processed': total_processed,
        'sale_types': len(crawl_types['sale_types']),
        'prop_types': len(crawl_types['prop_types']),
    })

    logger.task_end(success=success)
    return success


def main():
    parser = argparse.ArgumentParser(description='Court Auction Crawler')
    parser.add_argument('--start_date', type=str, help='Start date (YYYYMMDD)')
    args = parser.parse_args()

    run(start_date=args.start_date)


if __name__ == '__main__':
    main()
