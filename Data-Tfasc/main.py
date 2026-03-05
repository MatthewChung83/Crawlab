# -*- coding: utf-8 -*-
"""
Tfasc crawler - 金服中心拍賣資料爬取與文件下載
Integrated from Data-Tfasc and Data-Tfasc_Doc_Download
"""
import os
import sys
import datetime
import argparse
import traceback

from config import db, doc_download
from etl_func import (
    toSQL, exist_number,
    auction_info_owner_tb_etl, auction_info_tb_etl, wbt_tfasc_auction_tb_etl,
    dbfrom_doc_download, download_document
)
from utils import parseBulletin, parseSection


def run_crawler(mode='prod'):
    """Run the main auction data crawler"""
    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']

    print("開始解析場次資料...")
    tfasc = parseSection(mode)
    print(f"取得 {len(tfasc)} 筆場次資料")

    if not tfasc:
        print("沒有取得任何場次資料，程式結束")
        return

    print("篩選未處理的案件...")
    tfascs = []
    for t in tfasc:
        try:
            if '金服案號' not in t or 'session' not in t:
                print(f"跳過缺少必要欄位的資料: {t}")
                continue

            if exist_number(t['金服案號'], t['session']) == 0:
                tfascs.append(t)
        except Exception as e:
            print(f"檢查案件 {t.get('金服案號', 'unknown')} 時發生錯誤: {e}")
            continue

    print(f"篩選出 {len(tfascs)} 筆新案件")
    if not tfascs:
        print("沒有新的案件需要處理，程式結束")
        return

    print("開始解析公告內容...")
    result = parseBulletin(tfascs, mode)
    print(f"成功解析 {len(result)} 筆公告資料")

    if not result:
        print("沒有成功解析的資料，程式結束")
        return

    print("開始進行資料轉換...")
    auction_info_owner_data = auction_info_owner_tb_etl(result)
    auction_info_data = auction_info_tb_etl(result)
    wbt_tfasc_auction_data = wbt_tfasc_auction_tb_etl(result)

    print(f"轉換結果 - 所有權人: {len(auction_info_owner_data)}, 拍賣資訊: {len(auction_info_data)}, 主表: {len(wbt_tfasc_auction_data)}")

    print("開始寫入資料庫...")
    if len(auction_info_owner_data) > 0:
        print("寫入所有權人資料...")
        toSQL(auction_info_owner_data, db['auction_owner_tb'], server, database, username, password)
    if len(auction_info_data) > 0:
        print("寫入拍賣資訊資料...")
        toSQL(auction_info_data, db['auction_info_tb'], server, database, username, password)
    if len(wbt_tfasc_auction_data) > 0:
        print("寫入主表資料...")
        toSQL(wbt_tfasc_auction_data, db['wbt_auction_tb'], server, database, username, password)

    print("爬蟲執行完成！")


def run_doc_download(days_back=10):
    """Download auction documents as PDF"""
    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']
    output_dir = doc_download['output_dir']

    yesterday = datetime.date.today() + datetime.timedelta(days=-days_back)
    src_list = dbfrom_doc_download(server, username, password, database, yesterday)

    print(f"找到 {len(src_list)} 筆文件需要下載")

    for filename, url in src_list:
        full_path = os.path.join(output_dir, filename)
        try:
            download_document(url, full_path)
            print(f"已下載: {full_path}")
        except Exception as e:
            print(f"[ERROR] 下載失敗 {filename}: {e}")
            continue

    print("文件下載完成！")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Tfasc 金服中心拍賣資料爬蟲')
    parser.add_argument('--mode', default='prod', choices=['prod', 'dev'], help='執行模式')
    parser.add_argument('--action', default='crawl', choices=['crawl', 'download', 'all'],
                        help='執行動作: crawl=爬取資料, download=下載文件, all=全部執行')
    parser.add_argument('--days', type=int, default=10, help='下載文件時往回查詢的天數')
    args = parser.parse_args()

    try:
        if args.action in ['crawl', 'all']:
            run_crawler(args.mode)

        if args.action in ['download', 'all']:
            run_doc_download(args.days)

    except Exception as e:
        print(f"程式執行過程中發生錯誤: {e}")
        traceback.print_exc()
        sys.exit(1)
