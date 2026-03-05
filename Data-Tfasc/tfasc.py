#!/usr/bin/env python
# -*- coding: utf-8 -*-

from etl_function import auction_info_owner_tb_etl,auction_info_tb_etl,wbt_tfasc_auction_tb_etl
from utils import parseBulletin,parseSection
import pandas

def toSQL(docs, table , server, database, username, password):
    import pyodbc
    conn_cmd = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER='+server+';DATABASE='+database+';UID='+username+';PWD='+password
    with pyodbc.connect(conn_cmd) as cnxn:
        cnxn.autocommit = False
        with cnxn.cursor() as cursor:
            data_keys = ','.join(docs[0].keys())
            data_symbols = ','.join(['?' for _ in range(len(docs[0].keys()))])
            insert_cmd = """INSERT INTO {} ({})
            VALUES ({})""".format( table,data_keys,data_symbols )
            data_values = [tuple(doc.values()) for doc in docs]
            cursor.executemany( insert_cmd,data_values )
            cnxn.commit()

def exist_number(number,session):
    import pymssql
    conn = pymssql.connect(server='10.10.0.94', user='CLUSER', password='Ucredit7607', database='CL_Daily')
    cursor = conn.cursor()
    script = f"""
    select count(*) from tfasc_wbt_auction_tb
    where number = '{number}' and session = '{session}'
    """
    cursor.execute(script)
    counts = cursor.fetchall()
    cursor.close()
    conn.close()
    return counts[0][0]

def exist_auction():
    import pymssql
    conn = pymssql.connect(server='10.10.0.94', user='CLUSER', password='Ucredit7607', database='CL_Daily')
    cursor = conn.cursor()
    script = f"""select distinct auction_info_i from tfasc_auction_info_owner_tb"""
    cursor.execute(script)
    qry = cursor.fetchall()
    cursor.close()
    conn.close()
          
    exist_number = []        
    for i in range(len(qry)):
        pdf = qry[i][0]
        exist_number.append(pdf)
    return exist_number

def dedup(data,dup_number_list,pkey):
    df = pandas.DataFrame(data).fillna('')
    dedup_df = df[ -df[pkey].isin(dup_number_list) ]
    return [v.to_dict() for _,v in dedup_df.iterrows()]

try:
    if __name__=="__main__":
        # to SQL server
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--server', help='server')
        parser.add_argument('--database', help='database')
        parser.add_argument('--username', help='username')
        parser.add_argument('--password', help='password')
        parser.add_argument('--mode', default='prod', choices=['prod','dev'])
        args = parser.parse_args(args=[])
        server = args.server
        database = args.database
        username = args.username
        password = args.password
        mode = args.mode
        print('server: {},  database: {},  username: {},  password: {},  mode: {}'.format(server, database, username,password, mode) )
        
        print("開始解析場次資料...")
        tfasc = parseSection(mode)
        print(f"取得 {len(tfasc)} 筆場次資料")
        
        if not tfasc:
            print("沒有取得任何場次資料，程式結束")
            exit(0)
        
        print("篩選未處理的案件...")
        tfascs = []
        for t in tfasc:
            try:
                # 檢查必要欄位是否存在
                if '金服案號' not in t or 'session' not in t:
                    print(f"跳過缺少必要欄位的資料: {t}")
                    continue
                    
                if exist_number(t['金服案號'],t['session']) == 0:
                    tfascs.append(t)
            except Exception as e:
                print(f"檢查案件 {t.get('金服案號', 'unknown')} 時發生錯誤: {e}")
                continue
        
        print(f"篩選出 {len(tfascs)} 筆新案件")
        if not tfascs:
            print("沒有新的案件需要處理，程式結束")
            exit(0)

        print("開始解析公告內容...")
        result = parseBulletin(tfascs,mode)
        print(f"成功解析 {len(result)} 筆公告資料")

        if not result:
            print("沒有成功解析的資料，程式結束")
            exit(0)

        print("開始進行資料轉換...")
        auction_info_owner_data = auction_info_owner_tb_etl(result)
        auction_info_data = auction_info_tb_etl(result)
        wbt_tfasc_auction_data = wbt_tfasc_auction_tb_etl(result)    
        
        print(f"轉換結果 - 所有權人: {len(auction_info_owner_data)}, 拍賣資訊: {len(auction_info_data)}, 主表: {len(wbt_tfasc_auction_data)}")
        
        ### deduplicate
        #dup_number_list = ['109士金職九字第000145號']  # replace this
        
        print("開始寫入資料庫...")
        if len(auction_info_owner_data) > 0:
            print("寫入所有權人資料...")
            toSQL(auction_info_owner_data, 'tfasc_auction_info_owner_tb' , '10.10.0.94', 'CL_Daily', 'CLUSER', 'Ucredit7607')
        if len(auction_info_data) > 0:
            print("寫入拍賣資訊資料...")
            toSQL(auction_info_data, 'tfasc_auction_info_tb' , '10.10.0.94', 'CL_Daily', 'CLUSER', 'Ucredit7607')
        if len(wbt_tfasc_auction_data) > 0:
            print("寫入主表資料...")
            toSQL(wbt_tfasc_auction_data, 'tfasc_wbt_auction_tb' , '10.10.0.94', 'CL_Daily', 'CLUSER', 'Ucredit7607')
        
        print("程式執行完成！")
        
except Exception as e:
    print(f"程式執行過程中發生錯誤: {e}")
    import traceback
    traceback.print_exc()