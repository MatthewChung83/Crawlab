def foo(num,obs):
    while num < obs:
        num = num + 1 
        yield num


def is_all_chinese(strs):
    for _char in strs:
        if not '\u4e00' <= _char <= '\u9fa5':
            return False
    return True
  
def indata(doc):
    """
    接受單筆 tuple 或多筆 list[tuple]，順序需為：
    (city_id, city, area_id, area, parcel_section_id, parcel_section, isword, updatetime)
    回傳 list[tuple] 以便 executemany。
    """
    if isinstance(doc, tuple):
        return [doc]
    elif isinstance(doc, (list, tuple)):
        return [tuple(r) for r in doc]
    else:
        raise TypeError("indata expects a tuple or a list of tuples")


def toSQL(docs, totb, server, database, username, password):
    """
    安全批次寫入到 totb（建議帶 schema，例如 'dbo.land_parcel_section_tmp'）
    docs: list[tuple]，欄位順序需與 SQL 欄位清單一致。
    """
    import pymssql
    if not docs:
        return

    col_list = """
        [city_id],
        [city],
        [area_id],
        [area],
        [parcel_section_id],
        [parcel_section],
        [isword],
        [updatetime]
    """
    sql = f"INSERT INTO {totb} ({col_list}) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"

    conn = pymssql.connect(server=server, user=username, password=password, database=database)
    try:
        with conn.cursor() as cursor:
            cursor.executemany(sql, docs)
        conn.commit()
        print(f"已插入 {len(docs)} 筆 → {totb}")
    except Exception as e:
        conn.rollback()
        print(f"插入數據時出現錯誤: {e}")
        if docs:
            print("第一筆資料：", docs[0])
        raise
    finally:
        conn.close()


def truncate_table(server, username, password, database, table):
    """
    清空指定資料表（支援 schema），例如 table='dbo.land_parcel_section_tmp'
    """
    import pymssql
    conn = pymssql.connect(server=server, user=username, password=password, database=database)
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {table};")
        conn.commit()
        print(f"已清空 {table}")
    finally:
        conn.close()


def overwrite(server, username, password, database,
              tmp_table, target_table,
              key_cols=('city_id', 'parcel_section_id'),
              update_when_matched=False):
    """
    從 tmp_table 寫入 target_table。
    - 預設只「新增」不存在的資料（與你原本邏輯一致）
    - key_cols: 用來判斷是否存在的複合鍵（預設 city_id + parcel_section_id）
    - 若 update_when_matched=True，會同步更新非鍵欄位

    欄位集合以 tmp_table 與 target_table 欄位一致為前提。
    """
    import pymssql

    # 組 MERGE 子句
    on_cond = ' AND '.join([f"T.[{k}] = S.[{k}]" for k in key_cols])

    # 非鍵欄位（要更新的欄位）
    all_cols = ['city_id','city','area_id','area','parcel_section_id','parcel_section','isword','updatetime']
    set_cols = [c for c in all_cols if c not in key_cols]

    set_clause = ', '.join([f"T.[{c}] = S.[{c}]" for c in set_cols])

    merge_sql = f"""
    MERGE {target_table} AS T
    USING {tmp_table} AS S
        ON {on_cond}
    WHEN NOT MATCHED BY TARGET THEN
        INSERT ([city_id],[city],[area_id],[area],[parcel_section_id],[parcel_section],[isword],[updatetime])
        VALUES (S.[city_id],S.[city],S.[area_id],S.[area],S.[parcel_section_id],S.[parcel_section],S.[isword],S.[updatetime])
    {"WHEN MATCHED THEN UPDATE SET " + set_clause if update_when_matched else ""}
    ;
    """

    conn = pymssql.connect(server=server, user=username, password=password, database=database)
    try:
        with conn.cursor() as cursor:
            cursor.execute(merge_sql)
        conn.commit()
        print(f"overwrite 完成：{tmp_table} → {target_table}（update_when_matched={update_when_matched}）")
    finally:
        conn.close()


def dbtest(server, username, password, database, table):
    """
    測試用：清空指定資料表
    """
    import pymssql
    conn = pymssql.connect(server=server, user=username, password=password, database=database)
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {table};")
        conn.commit()
        print(f"dbtest: 已清空 {table}")
    finally:
        conn.close()
