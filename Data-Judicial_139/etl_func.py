# -*- coding: utf-8 -*-
"""
ETL functions for Judicial 139 Crawler
"""

import pymssql


def connect_database(server, username, password, database):
    """連接資料庫"""
    try:
        conn = pymssql.connect(
            server=server,
            database=database,
            user=username,
            password=password,
            timeout=30,
            login_timeout=30
        )
        print(f"成功連接到資料庫 {server}.{database}")
        return conn
    except Exception as e:
        print(f"資料庫連接失敗: {e}")
        return None


def create_table_if_not_exists(conn, table_name):
    """如果資料表不存在則建立"""
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        # 檢查表是否存在
        check_sql = f"""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_NAME = '{table_name}'
        """
        cursor.execute(check_sql)
        table_exists = cursor.fetchone()[0] > 0

        if table_exists:
            print(f"資料表 '{table_name}' 已存在，將累積新資料")
            cursor.close()
            return True

        # 建立新表
        create_sql = f"""
        CREATE TABLE {table_name} (
            ID INT IDENTITY(1,1) PRIMARY KEY,
            ItemNumber NVARCHAR(50),
            Court NVARCHAR(200),
            CaseNumber NVARCHAR(200),
            CaseYear NVARCHAR(10),
            CaseType NVARCHAR(50),
            CaseFileNumber NVARCHAR(50),
            RecipientName NVARCHAR(500),
            DomesticForeign NVARCHAR(50),
            DocumentType NVARCHAR(500),
            AnnouncementDate NVARCHAR(20),
            CaseCategory NVARCHAR(100),
            AnnouncementContent NVARCHAR(2000),
            CreatedDate DATETIME DEFAULT GETDATE(),
            ImportDate DATE DEFAULT CONVERT(DATE, GETDATE())
        );
        """

        cursor.execute(create_sql)
        conn.commit()
        cursor.close()
        print(f"資料表 '{table_name}' 建立成功")
        return True

    except Exception as e:
        print(f"建立資料表失敗: {e}")
        return False


def check_existing_data(conn, table_name, western_start, western_end):
    """檢查是否已有今天的資料"""
    if not conn:
        return False

    try:
        cursor = conn.cursor()

        check_sql = f"""
        SELECT COUNT(*)
        FROM {table_name}
        WHERE ImportDate = CONVERT(DATE, GETDATE())
        AND AnnouncementDate BETWEEN %s AND %s
        """

        cursor.execute(check_sql, (western_start, western_end))
        count = cursor.fetchone()[0]
        cursor.close()

        if count > 0:
            print(f"警告: 今天已有 {count} 筆相同日期範圍的資料")
            return True

        return False

    except Exception as e:
        print(f"警告: 檢查現有資料時發生錯誤: {e}")
        return False


def check_duplicate_record(conn, table_name, case_number, recipient_name, announcement_date):
    """檢查是否為重複記錄"""
    if not conn:
        return False

    try:
        cursor = conn.cursor()
        check_sql = f"""
        SELECT COUNT(*)
        FROM {table_name}
        WHERE CaseNumber = %s AND RecipientName = %s AND AnnouncementDate = %s
        """

        cursor.execute(check_sql, (case_number, recipient_name, announcement_date))
        count = cursor.fetchone()[0]
        cursor.close()
        return count > 0

    except Exception as e:
        print(f"檢查重複記錄時發生錯誤: {e}")
        return False


def insert_data(conn, table_name, processed_data):
    """插入資料到資料庫"""
    if not conn or not processed_data:
        return False

    try:
        cursor = conn.cursor()

        insert_sql = f"""
        INSERT INTO {table_name} (
            ItemNumber, Court, CaseNumber, CaseYear, CaseType, CaseFileNumber,
            RecipientName, DomesticForeign, DocumentType, AnnouncementDate,
            CaseCategory, AnnouncementContent
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # 準備批量插入資料，過濾重複記錄
        batch_data = []
        duplicate_count = 0

        for record in processed_data:
            # 檢查是否重複
            if check_duplicate_record(conn, table_name, record['CaseNumber'], record['RecipientName'], record['AnnouncementDate']):
                duplicate_count += 1
                continue

            batch_data.append((
                record['ItemNumber'], record['Court'], record['CaseNumber'],
                record['CaseYear'], record['CaseType'], record['CaseFileNumber'],
                record['RecipientName'], record['DomesticForeign'], record['DocumentType'],
                record['AnnouncementDate'], record['CaseCategory'], record['AnnouncementContent']
            ))

        # 插入非重複記錄
        for record_data in batch_data:
            cursor.execute(insert_sql, record_data)
        conn.commit()
        cursor.close()

        if duplicate_count > 0:
            print(f"跳過 {duplicate_count} 筆重複記錄")
        print(f"成功插入 {len(batch_data)} 筆新記錄到資料庫")
        return True

    except Exception as e:
        print(f"資料插入失敗: {e}")
        conn.rollback()
        return False


def verify_data(conn, table_name):
    """驗證資料庫資料"""
    if not conn:
        return

    try:
        cursor = conn.cursor()

        # 查詢總數
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_count = cursor.fetchone()[0]
        print(f"資料庫總記錄數: {total_count}")

        # 查詢今天新增的記錄數
        cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE ImportDate = CONVERT(DATE, GETDATE())")
        today_count = cursor.fetchone()[0]
        print(f"今天新增記錄數: {today_count}")

        # 查詢最新5筆記錄
        cursor.execute(f"SELECT TOP 5 Court, CaseYear, CaseType, CaseFileNumber, ImportDate FROM {table_name} ORDER BY ID DESC")
        sample_records = cursor.fetchall()

        if sample_records:
            print("\n最新5筆記錄:")
            for i, record in enumerate(sample_records, 1):
                print(f"   {i}. {record[0]} | {record[1]}年{record[2]}字第{record[3]}號 | {record[4]}")

        cursor.close()

    except Exception as e:
        print(f"資料驗證失敗: {e}")


def exit_obs(conn, table_name):
    """取得今日已處理筆數"""
    if not conn:
        return 0

    try:
        cursor = conn.cursor()
        script = f"""
        SELECT COUNT(*)
        FROM [{table_name}]
        WHERE ImportDate = CONVERT(DATE, GETDATE())
        """
        cursor.execute(script)
        obs = cursor.fetchall()
        cursor.close()
        return list(obs[0])[0]
    except Exception as e:
        print(f"查詢今日筆數失敗: {e}")
        return 0
