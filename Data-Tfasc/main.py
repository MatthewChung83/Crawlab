# -*- coding: utf-8 -*-
"""
Tfasc crawler - 金服中心拍賣資料爬取與文件下載
Integrated from Data-Tfasc and Data-Tfasc_Doc_Download
"""
import os
import sys
import datetime
import argparse

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import db, doc_download
from etl_func import (
    toSQL, exist_number,
    auction_info_owner_tb_etl, auction_info_tb_etl, wbt_tfasc_auction_tb_etl,
    dbfrom_doc_download, download_document
)
from utils import parseBulletin, parseSection
from common.logger import get_logger

# Initialize logger
logger = get_logger('Data-Tfasc')


def run_crawler(mode='prod'):
    """Run the main auction data crawler"""
    logger.task_start("金服中心拍賣資料爬取")

    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']

    logger.log_db_connect(server, database, username)
    logger.info(f"執行模式: {mode}")

    # Parse section data
    logger.ctx.set_operation("parse_section")
    logger.info("開始解析場次資料...")

    try:
        tfasc = parseSection(mode)
        logger.info(f"取得 {len(tfasc)} 筆場次資料")
    except Exception as e:
        logger.log_exception(e, "解析場次資料失敗")
        logger.task_end(success=False)
        return False

    if not tfasc:
        logger.warning("沒有取得任何場次資料")
        logger.task_end(success=True)
        return True

    # Filter unprocessed cases
    logger.ctx.set_operation("filter_cases")
    logger.info("篩選未處理的案件...")

    tfascs = []
    total_cases = len(tfasc)
    for idx, t in enumerate(tfasc, 1):
        logger.ctx.set_progress(idx, total_cases)
        try:
            if '金服案號' not in t or 'session' not in t:
                logger.debug(f"跳過缺少必要欄位的資料: {t.get('金服案號', 'unknown')}")
                continue

            logger.ctx.set_data(case_no=t['金服案號'], session=t['session'])
            if exist_number(t['金服案號'], t['session']) == 0:
                tfascs.append(t)
        except Exception as e:
            logger.log_exception(e, f"檢查案件時發生錯誤: case_no={t.get('金服案號', 'unknown')}")
            continue

    logger.info(f"篩選出 {len(tfascs)} 筆新案件")

    if not tfascs:
        logger.info("沒有新的案件需要處理")
        logger.task_end(success=True)
        return True

    # Parse bulletin content
    logger.ctx.set_operation("parse_bulletin")
    logger.info("開始解析公告內容...")

    try:
        result = parseBulletin(tfascs, mode)
        logger.info(f"成功解析 {len(result)} 筆公告資料")
    except Exception as e:
        logger.log_exception(e, "解析公告內容失敗")
        logger.task_end(success=False)
        return False

    if not result:
        logger.warning("沒有成功解析的資料")
        logger.task_end(success=True)
        return True

    # Data transformation
    logger.ctx.set_operation("data_transform")
    logger.info("開始進行資料轉換...")

    try:
        auction_info_owner_data = auction_info_owner_tb_etl(result)
        auction_info_data = auction_info_tb_etl(result)
        wbt_tfasc_auction_data = wbt_tfasc_auction_tb_etl(result)

        logger.info(f"轉換結果 - 所有權人: {len(auction_info_owner_data)}, "
                   f"拍賣資訊: {len(auction_info_data)}, 主表: {len(wbt_tfasc_auction_data)}")
    except Exception as e:
        logger.log_exception(e, "資料轉換失敗")
        logger.task_end(success=False)
        return False

    # Write to database
    logger.ctx.set_operation("DB_insert")
    logger.info("開始寫入資料庫...")

    try:
        if len(auction_info_owner_data) > 0:
            logger.ctx.set_db(server=server, database=database,
                            table=db['auction_owner_tb'], operation="INSERT")
            toSQL(auction_info_owner_data, db['auction_owner_tb'], server, database, username, password)
            logger.log_db_operation("INSERT", database, db['auction_owner_tb'], len(auction_info_owner_data))

        if len(auction_info_data) > 0:
            logger.ctx.set_db(server=server, database=database,
                            table=db['auction_info_tb'], operation="INSERT")
            toSQL(auction_info_data, db['auction_info_tb'], server, database, username, password)
            logger.log_db_operation("INSERT", database, db['auction_info_tb'], len(auction_info_data))

        if len(wbt_tfasc_auction_data) > 0:
            logger.ctx.set_db(server=server, database=database,
                            table=db['wbt_auction_tb'], operation="INSERT")
            toSQL(wbt_tfasc_auction_data, db['wbt_auction_tb'], server, database, username, password)
            logger.log_db_operation("INSERT", database, db['wbt_auction_tb'], len(wbt_tfasc_auction_data))

    except Exception as e:
        logger.log_db_error(e, "INSERT")
        logger.task_end(success=False)
        return False

    logger.log_stats({
        'total_sections': len(tfasc),
        'new_cases': len(tfascs),
        'parsed_bulletins': len(result),
        'owner_records': len(auction_info_owner_data),
        'info_records': len(auction_info_data),
        'main_records': len(wbt_tfasc_auction_data),
    })

    logger.task_end(success=True)
    return True


def run_doc_download(days_back=10):
    """Download auction documents as PDF"""
    logger.task_start("金服中心文件下載")

    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']
    output_dir = doc_download['output_dir']

    logger.log_db_connect(server, database, username)
    logger.info(f"輸出目錄: {output_dir}")
    logger.info(f"查詢天數: {days_back} 天")

    # Get document list from database
    logger.ctx.set_operation("DB_query_documents")
    yesterday = datetime.date.today() + datetime.timedelta(days=-days_back)

    try:
        src_list = dbfrom_doc_download(server, username, password, database, yesterday)
        logger.info(f"找到 {len(src_list)} 筆文件需要下載")
    except Exception as e:
        logger.log_db_error(e, "SELECT")
        logger.task_end(success=False)
        return False

    if not src_list:
        logger.info("沒有文件需要下載")
        logger.task_end(success=True)
        return True

    # Download documents
    logger.ctx.set_operation("download_documents")
    success_count = 0
    fail_count = 0
    total_docs = len(src_list)

    for idx, (filename, url) in enumerate(src_list, 1):
        logger.log_progress(idx, total_docs, filename)
        logger.ctx.set_data(filename=filename, url=url)

        full_path = os.path.join(output_dir, filename)

        try:
            logger.log_request("GET", url, None, None)
            download_document(url, full_path)
            logger.info(f"下載成功: {filename}")
            success_count += 1
            logger.increment('records_success')
        except Exception as e:
            logger.log_exception(e, f"下載失敗: {filename}")
            fail_count += 1
            logger.increment('records_failed')
            continue

    logger.log_stats({
        'total_documents': total_docs,
        'success': success_count,
        'failed': fail_count,
    })

    logger.task_end(success=(fail_count == 0))
    return fail_count == 0


def run(mode='prod', action='all', days=10):
    """Main execution function"""
    success = True

    if action in ['crawl', 'all']:
        if not run_crawler(mode):
            success = False

    if action in ['download', 'all']:
        if not run_doc_download(days):
            success = False

    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Tfasc 金服中心拍賣資料爬蟲')
    parser.add_argument('--mode', default='prod', choices=['prod', 'dev'], help='執行模式')
    parser.add_argument('--action', default='crawl', choices=['crawl', 'download', 'all'],
                        help='執行動作: crawl=爬取資料, download=下載文件, all=全部執行')
    parser.add_argument('--days', type=int, default=10, help='下載文件時往回查詢的天數')
    args = parser.parse_args()

    try:
        success = run(mode=args.mode, action=args.action, days=args.days)
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.log_exception(e, "程式執行過程中發生錯誤")
        sys.exit(1)
