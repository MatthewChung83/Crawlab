#!/usr/bin/env python3
"""
法院拍賣爬蟲 - 不使用 Scrapy 框架版本
改進版本特點:
1. 使用 requests 替代 Scrapy
2. 改善 PDF 解析精準度 (去除全形字元、符號)
3. 只儲存到資料庫，不產生 CSV
4. 更好的錯誤處理和日誌記錄
"""

import requests
import json
import logging
import re
import tempfile
import os
import glob
from datetime import datetime, timedelta
from dateutil import parser
import pymssql
import time
from typing import List, Dict, Any, Optional
import unicodedata

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('court_auction.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CourtAuctionCrawler:
    """法院拍賣資訊爬蟲"""
    
    def __init__(self, start_date: str = None):
        """初始化爬蟲
        
        Args:
            start_date: 爬蟲開始日期，格式: YYYYMMDD，預設為今天
        """
        self.start_date = start_date or f"{datetime.now().year}{datetime.now().strftime('%m')}{datetime.now().strftime('%d')}"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # 匯入配置
        try:
            from config import DB_CONFIG, PATHS, CRAWLER_CONFIG
            self.db_config = DB_CONFIG
            self.output_dir = PATHS['output_dir']
            self.crawler_config = CRAWLER_CONFIG
        except ImportError:
            # 如果無法匯入配置檔案，使用預設值
            self.db_config = {
                'server': '10.10.0.94',
                'database': 'CL_Daily',
                'user': 'CLUSER',
                'password': 'Ucredit7607'
            }
            self.output_dir = './data/'
            self.crawler_config = {
                'delay_between_requests': 0.1,
                'request_timeout': 30,
                'pdf_download_timeout': 60,
                'max_retries': 3
            }
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 取得已存在的PDF檔案清單
        self.existing_pdfs = self._get_existing_pdfs()
        
        logger.info(f"爬蟲初始化完成，開始日期: {self.start_date}")
    
    def _get_existing_pdfs(self) -> List[str]:
        """從資料庫查詢已存在的PDF檔案清單"""
        try:
            conn = pymssql.connect(**self.db_config)
            cursor = conn.cursor()
            
            query = """
            SELECT DISTINCT CONCAT(court,'_',number,'_',REPLACE(REPLACE(date,' ','_'),'/',''),'.pdf') 
            FROM wbt_court_auction_tb
            """
            cursor.execute(query)
            results = cursor.fetchall()
            
            existing_pdfs = [result[0] for result in results]
            cursor.close()
            conn.close()
            
            logger.info(f"找到 {len(existing_pdfs)} 個已存在的PDF檔案")
            return existing_pdfs
            
        except Exception as e:
            logger.error(f"查詢現有PDF檔案失敗: {e}")
            return []
    
    def _normalize_text(self, text: str) -> str:
        """標準化文字，去除全形字元和符號
        
        Args:
            text: 原始文字
            
        Returns:
            標準化後的文字
        """
        if not text:
            return text
            
        # 全形轉半形
        text = unicodedata.normalize('NFKC', text)
        
        # 移除常見的無用符號和空白字元
        text = re.sub(r'[　\u3000\xa0\u2000-\u200f\u2028-\u202f]', ' ', text)  # 各種空白字元
        text = re.sub(r'[‧•·]', '', text)  # 中點符號
        text = re.sub(r'[─━─]', '-', text)  # 破折號標準化
        text = re.sub(r'[（）()]', lambda m: '(' if m.group() in '（(' else ')', text)  # 括號標準化
        text = re.sub(r'[，,]', ',', text)  # 逗號標準化
        text = re.sub(r'[。．]', '.', text)  # 句號標準化
        text = re.sub(r'[：:]', ':', text)  # 冒號標準化
        text = re.sub(r'[；;]', ';', text)  # 分號標準化
        
        # 移除多餘空白
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _generate_date_range(self) -> tuple:
        """產生查詢的日期範圍"""
        date = parser.parse(self.start_date)
        start_date_str = f"{date.year-1911}{date.strftime('%m')}{date.strftime('%d')}"
        end_date = date + timedelta(days=60)
        end_date_str = f"{end_date.year-1911}{end_date.strftime('%m')}{end_date.strftime('%d')}"
        return start_date_str, end_date_str
    
    def crawl_auction_data(self):
        """主要爬蟲流程"""
        logger.info("開始爬取法院拍賣資料")
        
        start_date_str, end_date_str = self._generate_date_range()
        
        # 拍賣類型: 1=一般程序, 4=應買公告, 5=拍定價格
        sale_types = ['1', '4', '5']
        # 物件類型: C52=房屋, C51=土地, C103=房屋+土地
        prop_types = ['C52', 'C51', 'C103']
        
        total_processed = 0
        
        for sale_type in sale_types:
            for prop_type in prop_types:
                logger.info(f"處理拍賣類型: {sale_type}, 物件類型: {prop_type}")
                
                # 先取得第一頁以獲得總頁數
                first_page_data = self._get_page_data(1, sale_type, prop_type, start_date_str, end_date_str)
                if not first_page_data:
                    continue
                
                total_num = first_page_data.get('pageInfo', {}).get('totalNum', 0)
                max_page = (total_num // 100) + 1
                
                logger.info(f"總共 {total_num} 筆資料, {max_page} 頁")
                
                # 處理所有頁面
                for page in range(1, max_page + 1):
                    page_data = self._get_page_data(page, sale_type, prop_type, start_date_str, end_date_str)
                    if not page_data:
                        continue
                    
                    processed = self._process_page_data(page_data.get('data', []), sale_type, prop_type)
                    total_processed += processed
                    
                    # 避免過度頻繁請求
                    time.sleep(self.crawler_config['delay_between_requests'])
        
        logger.info(f"爬取完成，總共處理 {total_processed} 筆資料")
    
    def _get_page_data(self, page_num: int, sale_type: str, prop_type: str, 
                       start_date: str, end_date: str) -> Optional[Dict]:
        """取得指定頁面的資料"""
        
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
            response = self.session.post(
                'https://aomp109.judicial.gov.tw/judbp/wkw/WHD1A02/QUERY.htm',
                data=form_data,
                timeout=30
            )
            response.raise_for_status()
            
            data = json.loads(response.text)
            return data
            
        except Exception as e:
            logger.error(f"取得頁面資料失敗 (頁面 {page_num}): {e}")
            return None
    
    def _process_page_data(self, data_list: List[Dict], sale_type: str, prop_type: str) -> int:
        """處理頁面資料"""
        processed_count = 0
        
        for item in data_list:
            try:
                # 建構基本資訊
                auction_info = self._build_auction_info(item, sale_type, prop_type)
                
                # 檢查PDF是否已存在
                pdf_filename = self._generate_pdf_filename(auction_info, item)
                if pdf_filename in self.existing_pdfs:
                    logger.debug(f"PDF已存在，跳過: {pdf_filename}")
                    continue
                
                # 儲存拍賣資訊到資料庫
                self._save_auction_info(auction_info)
                
                # 下載並解析PDF
                pdf_url = f"https://aomp109.judicial.gov.tw/judbp/wkw/WHD1A02/DO_VIEWPDF.htm?filenm={item.get('filenm')}"
                self._download_and_parse_pdf(pdf_url, auction_info, item)
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"處理資料項目失敗: {e}")
                continue
        
        return processed_count
    
    def _build_auction_info(self, item: Dict, sale_type: str, prop_type: str) -> Dict:
        """建構拍賣資訊"""
        # 標準化文字
        court = self._normalize_text(item.get('crtnm', ''))
        number = self._normalize_text(item.get('crm', '') + item.get('dptstr', ''))
        unit = self._normalize_text(item.get('dptstr', '')[1:-1] if len(item.get('dptstr', '')) > 2 else '')
        
        # 日期處理
        sale_date = item.get('saledate', '')
        if len(sale_date) >= 8:
            formatted_date = f"{sale_date[:-4]}/{sale_date[-4:-2]}/{sale_date[-2:]}"
        else:
            formatted_date = sale_date
        
        sale_no = item.get('saleno', '')
        date_with_turn = f"{formatted_date} 第{sale_no}拍" if sale_no else formatted_date
        
        # 地址處理
        address_parts = [
            item.get('hsimun', ''),
            item.get('ctmd', ''),
            item.get('budadd', ''),
            item.get('secstr', ''),
            item.get('area3str', ''),
            item.get('saleamtstr', '')
        ]
        address = self._normalize_text(' '.join(filter(None, address_parts)))
        
        country = self._normalize_text(' '.join(filter(None, [item.get('hsimun', ''), item.get('ctmd', '')])))
        
        return {
            'court': court,
            'number': number,
            'unit': unit,
            'date': date_with_turn,
            'turn': f"第{sale_no}拍" if sale_no else '',
            'reserve': self._normalize_text(item.get('saleamtstr', '')),
            'price': '',
            'address': address,
            'date_datetime': self._parse_tw_date(formatted_date),
            'country': country,
            'reserve_int': int(item.get('minprice', 0)) if item.get('minprice') else 0,
            'handover': self._normalize_text(item.get('checkynstr', '')),
            'vacancy': self._normalize_text(item.get('emptyynstr', '')),
            'target': self._normalize_text(item.get('batchno', '')),
            'document': f"https://aomp109.judicial.gov.tw/judbp/wkw/WHD1A02/DO_VIEWPDF.htm?filenm={item.get('filenm')}",
            'saletype': sale_type,
            'proptype': prop_type,
            'remark': self._normalize_text(item.get('rmk', '')),
            'type': 'wbt_court_auction_tb'
        }
    
    def _parse_tw_date(self, date_str: str) -> Optional[datetime]:
        """解析台灣日期格式"""
        try:
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    year = int(parts[0]) + 1911 if int(parts[0]) < 1000 else int(parts[0])
                    month = int(parts[1])
                    day = int(parts[2])
                    return datetime(year, month, day)
        except:
            pass
        return None
    
    def _generate_pdf_filename(self, auction_info: Dict, item: Dict) -> str:
        """產生PDF檔案名稱"""
        sale_date = item.get('saledate', '')
        sale_no = item.get('saleno', '')
        return f"{auction_info['court']}_{auction_info['number']}_{sale_date}_第{sale_no}拍.pdf"
    
    def _save_auction_info(self, auction_info: Dict):
        """儲存拍賣資訊到資料庫"""
        try:
            conn = pymssql.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 產生唯一ID
            rowid = self._generate_id({
                'number': auction_info['number'],
                'date': auction_info['date']
            })
            
            auction_info['rowid'] = rowid
            auction_info['entrydate'] = datetime.now()
            
            # 移除type欄位
            auction_data = {k: v for k, v in auction_info.items() if k != 'type'}
            
            # 建立INSERT語句
            columns = ','.join(auction_data.keys())
            placeholders = ','.join(['%s'] * len(auction_data))
            values = list(auction_data.values())
            
            insert_query = f"INSERT INTO wbt_court_auction_tb ({columns}) VALUES ({placeholders})"
            
            cursor.execute(insert_query, values)
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.debug(f"成功儲存拍賣資訊: {auction_info['court']} {auction_info['number']}")
            
        except Exception as e:
            logger.error(f"儲存拍賣資訊失敗: {e}")
    
    def _download_and_parse_pdf(self, pdf_url: str, auction_info: Dict, item: Dict):
        """下載並解析PDF"""
        try:
            # 下載PDF
            response = self.session.get(pdf_url, timeout=60)
            response.raise_for_status()
            
            # 儲存PDF到暫存檔案
            pdf_filename = self._generate_pdf_filename(auction_info, item)
            pdf_path = os.path.join(self.output_dir, pdf_filename)
            
            with open(pdf_path, 'wb') as f:
                f.write(response.body)
            
            # 解析PDF內容
            pdf_data = self._parse_pdf_with_improved_accuracy(pdf_path)
            
            # 儲存解析結果
            for data_item in pdf_data:
                self._save_pdf_data(data_item, auction_info)
            
            logger.info(f"成功處理PDF: {pdf_filename}")
            
        except Exception as e:
            logger.error(f"處理PDF失敗 ({pdf_url}): {e}")
    
    def _parse_pdf_with_improved_accuracy(self, pdf_path: str) -> List[Dict]:
        """使用改進的精準度解析PDF"""
        try:
            with ImprovedPDFReader(pdf_path) as pdf_reader:
                raw_data = pdf_reader.extract()
            
            # 對解析結果進行文字標準化
            improved_data = []
            for item in raw_data:
                improved_item = {}
                for key, value in item.items():
                    if isinstance(value, str):
                        improved_item[key] = self._normalize_text(value)
                    else:
                        improved_item[key] = value
                improved_data.append(improved_item)
            
            return improved_data
            
        except Exception as e:
            logger.error(f"PDF解析失敗: {e}")
            return []
    
    def _save_pdf_data(self, pdf_data: Dict, auction_info: Dict):
        """儲存PDF解析資料到資料庫"""
        try:
            conn = pymssql.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 合併資料
            combined_data = {
                **pdf_data,
                'court': auction_info['court'],
                'number': auction_info['number'],
                'date': auction_info['date'],
                'country': auction_info.get('country', ''),
                'refertb': 'wbt_court_auction_tb',
                'type': 'auction_info_tb',
                'referi': auction_info['rowid'],
                'entrydate': datetime.now()
            }
            
            # 產生唯一ID
            combined_data['rowid'] = self._generate_id(combined_data)
            
            # 移除type欄位
            save_data = {k: v for k, v in combined_data.items() if k != 'type'}
            
            # 建立INSERT語句
            columns = ','.join(save_data.keys())
            placeholders = ','.join(['%s'] * len(save_data))
            values = list(save_data.values())
            
            insert_query = f"INSERT INTO auction_info_tb ({columns}) VALUES ({placeholders})"
            
            cursor.execute(insert_query, values)
            conn.commit()
            cursor.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"儲存PDF資料失敗: {e}")
    
    def _generate_id(self, data: Dict) -> str:
        """產生唯一ID"""
        import hashlib
        
        # 使用關鍵欄位產生ID
        key_fields = ['court', 'number', 'date', 'owner', 'parcel']
        id_string = ''
        
        for field in key_fields:
            if field in data and data[field]:
                id_string += str(data[field])
        
        if not id_string:
            id_string = str(data)
        
        return hashlib.md5(id_string.encode('utf-8')).hexdigest()


def main():
    """主程式入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='法院拍賣資訊爬蟲')
    parser.add_argument('--start_date', type=str, help='開始日期 (YYYYMMDD格式)')
    
    args = parser.parse_args()
    
    try:
        crawler = CourtAuctionCrawler(start_date=args.start_date)
        crawler.crawl_auction_data()
        
    except KeyboardInterrupt:
        logger.info("使用者中斷程式執行")
    except Exception as e:
        logger.error(f"程式執行錯誤: {e}")


if __name__ == '__main__':
    main()