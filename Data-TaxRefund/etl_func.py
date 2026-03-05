# -*- coding: utf-8 -*-
"""
ETL functions for TaxRefund crawler
"""
import pymssql


def fromsql(host, user, password, database, src_tb):
    conn = pymssql.connect(host=host, user=user, password=password, database=database)
    cursor = conn.cursor(as_dict=True)
    script = f"""select * from {src_tb} where info is null and type = 'ONHAND-20240801_01' order by pid"""
    cursor.execute(script)
    sql_src = cursor.fetchall()
    cursor.close()
    conn.close()
    return sql_src


def updatesql(host, user, password, database, tar_tb, info, psid, pid):
    conn = pymssql.connect(host=host, user=user, password=password, database=database)
    cursor = conn.cursor(as_dict=True)
    script = f"""update {tar_tb} set info = '{info}' where psid = {psid} and pid = '{pid}'"""
    print(script)
    cursor.execute(script)
    conn.commit()
    cursor.close()
    conn.close()


def retry_generator(data_list):
    """
    Generator that provides data sequentially and retries on demand (max 5 retries)
    """
    max_retry = 5
    for record in data_list:
        retries = 0
        while retries < max_retry:
            yield record, retries
            retries += 1
