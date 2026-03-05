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
import logging
import argparse
import pdfplumber
from typing import List, Dict, Optional

from config import db, wbinfo, crawler, crawl_types, paths
from etl_func import (
    src_obs, get_existing_pdfs, generate_id, parse_tw_date,
    normalize_text, auction_item, auction_info_item, toSQL, exit_obs
)

# Disable SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('court_auction.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PDFReader:
    """PDF Reader for auction documents"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file = None
        try:
            self.file = pdfplumber.open(file_path)
        except Exception as e:
            logger.error(f"Failed to open PDF: {e}")
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

            return output

        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
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

    try:
        response = session.post(
            wbinfo['url'],
            data=form_data,
            timeout=crawler['timeout'],
            verify=False
        )
        response.raise_for_status()
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Failed to get page {page_num}: {e}")
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

    for item in data_list:
        try:
            auction_info = build_auction_info(item, sale_type, prop_type)
            pdf_filename = generate_pdf_filename(auction_info, item)

            if pdf_filename in existing_pdfs:
                logger.debug(f"PDF exists, skip: {pdf_filename}")
                continue

            # Generate rowid
            rowid = generate_id({
                'number': auction_info['number'],
                'date': auction_info['date']
            })
            auction_info['rowid'] = rowid
            auction_info['entrydate'] = datetime.datetime.now()

            # Save auction info
            docs = auction_item(auction_info)
            toSQL(docs, totb, server, database, username, password)
            logger.info(f"Saved auction: {auction_info['court']} {auction_info['number']}")

            # Download and parse PDF
            pdf_url = auction_info['document']
            try:
                response = session.get(pdf_url, timeout=crawler['pdf_timeout'], verify=False)
                response.raise_for_status()

                pdf_path = os.path.join(output_dir, pdf_filename)
                with open(pdf_path, 'wb') as f:
                    f.write(response.content)

                # Parse PDF
                with PDFReader(pdf_path) as reader:
                    pdf_data = reader.extract()

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

                logger.info(f"Processed PDF: {pdf_filename}")

            except Exception as e:
                logger.error(f"Failed to process PDF ({pdf_url}): {e}")

            processed_count += 1

            # Check daily limit
            exit_count = exit_obs(server, username, password, database, totb)
            if exit_count >= 10000:
                logger.info("Daily limit reached, stopping")
                sys.exit(0)

        except Exception as e:
            logger.error(f"Failed to process item: {e}")
            continue

    return processed_count


def main():
    parser = argparse.ArgumentParser(description='Court Auction Crawler')
    parser.add_argument('--start_date', type=str, help='Start date (YYYYMMDD)')
    args = parser.parse_args()

    start_date = args.start_date or datetime.datetime.now().strftime('%Y%m%d')

    logger.info(f"Starting crawler, date: {start_date}")

    # Setup session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    session.verify = False

    # Create output directory
    output_dir = paths['output_dir']
    os.makedirs(output_dir, exist_ok=True)

    # Get existing PDFs
    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']
    totb = db['totb']

    obs = src_obs(server, username, password, database, totb, totb)
    logger.info(f"Existing records: {obs}")

    existing_pdfs = get_existing_pdfs(server, username, password, database, totb)
    logger.info(f"Existing PDFs: {len(existing_pdfs)}")

    # Get date range
    start_date_str, end_date_str = get_date_range(start_date)
    logger.info(f"Date range: {start_date_str} - {end_date_str}")

    total_processed = 0

    try:
        for sale_type in crawl_types['sale_types']:
            for prop_type in crawl_types['prop_types']:
                logger.info(f"Processing sale_type: {sale_type}, prop_type: {prop_type}")

                # Get first page
                first_page = get_page_data(session, 1, sale_type, prop_type, start_date_str, end_date_str)
                if not first_page:
                    continue

                total_num = first_page.get('pageInfo', {}).get('totalNum', 0)
                max_page = (total_num // 100) + 1
                logger.info(f"Total: {total_num} records, {max_page} pages")

                # Process all pages
                for page in range(1, max_page + 1):
                    page_data = get_page_data(session, page, sale_type, prop_type, start_date_str, end_date_str)
                    if not page_data:
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
        logger.info("User interrupted")
    except Exception as e:
        logger.error(f"Error: {e}")

    logger.info(f"Completed, total processed: {total_processed}")


if __name__ == '__main__':
    main()
