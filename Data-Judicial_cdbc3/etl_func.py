# -*- coding: utf-8 -*-
"""
ETL functions for Judicial cdcb3 Crawler
"""

import time
import logging
import pymssql
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def db_connect(cfg: Dict[str, str]) -> pymssql.Connection:
    """連接資料庫"""
    try:
        conn = pymssql.connect(
            server=cfg["server"],
            user=cfg["username"],
            password=cfg["password"],
            database=cfg["database"],
            autocommit=False,
        )
        logger.info("DB connected.")
        return conn
    except Exception as e:
        logger.error(f"DB connect failed: {e}")
        raise


def safe_execute(cursor, sql: str, params: Optional[Tuple] = None, max_retry: int = 5):
    """Deadlock(1205) 自動重試"""
    for i in range(max_retry):
        try:
            cursor.execute(sql, params or ())
            return
        except pymssql.OperationalError as e:
            if hasattr(e, "args") and e.args and "1205" in str(e.args[0]):
                logger.warning(f"Deadlock detected. retry {i+1}/{max_retry} ...")
                time.sleep(1 + i * 0.5)
                continue
            logger.error(f"SQL operational error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected SQL error: {e}")
            raise
    raise RuntimeError("SQL deadlock retried too many times, abort.")


def src_obs(cursor, fromtb: str, totb: str) -> int:
    """
    計算需處理數量：
    - base_case 在目標表尚未存在的
    + 目標表已存在且 update_date 距今 >= 3 個月
    """
    sql = f"""
    SELECT
      (SELECT COUNT(*)
         FROM {fromtb} b
         LEFT JOIN [{totb}] r ON b.ID = r.ID
         WHERE r.ID IS NULL)
      +
      (SELECT COUNT(*)
         FROM [{totb}]
         WHERE DATEDIFF(MONTH, update_date, GETDATE()) >= 3)
    """
    safe_execute(cursor, sql)
    n = cursor.fetchone()[0]
    logger.info(f"Tasks to process (src_obs) = {n}")
    return int(n or 0)


def dbfrom(cursor, fromtb: str, totb: str) -> Optional[Tuple]:
    """
    取一筆要查的身分證資料（優先：目標表沒有的，再來是 >3 個月未更新的）
    """
    sql = f"""
    IF OBJECT_ID('tempdb..#test') IS NOT NULL DROP TABLE #test;

    SELECT
        b.personi,
        b.ID,
        CAST(b.name AS NVARCHAR(200)) AS name,
        b.casei,
        b.type,
        b.c,
        b.m,
        b.age,
        b.flg,
        r.rowid,
        b.client_flg
    INTO #test
    FROM {fromtb} b
    LEFT JOIN [{totb}] r ON b.ID = r.ID
    WHERE r.ID IS NULL;

    INSERT INTO #test
    SELECT DISTINCT
        0 AS personi,
        ID,
        CAST(name AS NVARCHAR(200)) AS name,
        0 AS casei, 0 AS type, 0 AS c, 0 AS m, 0 AS age,
        '' AS flg,
        rowid,
        '1' AS client_flg
    FROM [{totb}]
    WHERE DATEDIFF(MONTH, update_date, GETDATE()) >= 3;

    SELECT TOP 1 *
    FROM #test
    ORDER BY flg DESC, rowid ASC;
    """
    safe_execute(cursor, sql)
    row = cursor.fetchone()
    return row


def delete_row(cursor, totb: str, ID: str, rowid: str):
    """刪除指定記錄"""
    sql = f"DELETE FROM [{totb}] WHERE ID=%s AND rowid=%s"
    safe_execute(cursor, sql, (ID, rowid))


def exit_obs(cursor, totb: str) -> int:
    """
    今日已處理的 ID 數
    """
    sql = f"""
    SELECT COUNT(DISTINCT ID)
    FROM [{totb}]
    WHERE CAST(update_date AS date) = CAST(GETDATE() AS date)
    """
    safe_execute(cursor, sql)
    n = cursor.fetchone()[0]
    return int(n or 0)


def toSQL(cursor, totb: str, docs: List[Dict[str, Any]]):
    """插入資料到資料庫"""
    if not docs:
        return
    keys = list(docs[0].keys())
    cols = ",".join(f"[{k}]" for k in keys)
    vals = ",".join(["%s"] * len(keys))
    sql = f"INSERT INTO [{totb}] ({cols}) VALUES ({vals})"
    data = [tuple(d[k] for k in keys) for d in docs]
    cursor.executemany(sql, data)
