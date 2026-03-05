# -*- coding: utf-8 -*-
"""
Judicial cdcb3 sync (non-Scrapy)
- 移除 Scrapy 架構
- 加入可判別 log 前綴 [JudicialSync]
- requests.Session + Retry 防止 DNS/連線暫失
- SQL 改為參數化 (%s) + 語法修正
- 全面例外處理並落點記錄
"""

import datetime
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup
import pymssql
import logging

# ============ Logging ============
LOG_PREFIX = "[JudicialSync]"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - " + LOG_PREFIX + " %(message)s"
)
logger = logging.getLogger(__name__)


# ============ DB helpers ============
def db_connect(cfg: Dict[str, str]) -> pymssql.Connection:
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


# ============ HTTP helpers ============
def build_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=1.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
    })
    return s


# ============ Domain logic ============
class JudicialSync:
    db = {
        "server": "10.10.0.94",
        "database": "CL_Daily",
        "username": "CLUSER",
        "password": "Ucredit7607",
        "fromtb": "base_case",
        "totb": "Judicial_cdcb3",
    }

    wbinfo = {
        "query_url": "https://cdcb3.judicial.gov.tw/judbp/wkw/WHD9A01/QUERY.htm",
        "view_url": "https://cdcb3.judicial.gov.tw/judbp/wkw/WHD9A01/VIEW.htm",
        "token_url": "https://cdcb3.judicial.gov.tw/judbp/wkw/WHD9A01/V2.htm",
    }

    def __init__(self):
        self.session = build_session()
        self.conn = None
        self.cursor = None
        self.today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Start sync at {self.today_str}")

    # ---------- SQL snippets ----------
    def src_obs(self) -> int:
        """
        計算需處理數量：
        - base_case 在目標表尚未存在的
        + 目標表已存在且 update_date 距今 >= 3 個月
        """
        sql = f"""
        SELECT
          (SELECT COUNT(*)
             FROM {self.db['fromtb']} b
             LEFT JOIN [{self.db['totb']}] r ON b.ID = r.ID
             WHERE r.ID IS NULL)
          +
          (SELECT COUNT(*)
             FROM [{self.db['totb']}]
             WHERE DATEDIFF(MONTH, update_date, GETDATE()) >= 3)
        """
        safe_execute(self.cursor, sql)
        n = self.cursor.fetchone()[0]
        logger.info(f"Tasks to process (src_obs) = {n}")
        return int(n or 0)

    def dbfrom(self) -> Optional[Tuple]:
        """
        取一筆要查的身分證資料（優先：目標表沒有的，再來是 >3 個月未更新的）
        注意：OFFSET/FETCH 需要 ORDER BY，這裡使用 flg desc, rowid ASC。
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
        FROM {self.db['fromtb']} b
        LEFT JOIN [{self.db['totb']}] r ON b.ID = r.ID
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
        FROM [{self.db['totb']}]
        WHERE DATEDIFF(MONTH, update_date, GETDATE()) >= 3;

        SELECT TOP 1 *
        FROM #test
        ORDER BY flg DESC, rowid ASC;
        """
        safe_execute(self.cursor, sql)
        row = self.cursor.fetchone()
        return row

    def delete_row(self, totb: str, ID: str, rowid: str):
        sql = f"DELETE FROM [{totb}] WHERE ID=%s AND rowid=%s"
        safe_execute(self.cursor, sql, (ID, rowid))

    def exit_obs(self) -> int:
        """
        今日已處理的 ID 數（限制 5000）
        """
        sql = f"""
        SELECT COUNT(DISTINCT ID)
        FROM [{self.db['totb']}]
        WHERE CAST(update_date AS date) = CAST(GETDATE() AS date)
        """
        safe_execute(self.cursor, sql)
        n = self.cursor.fetchone()[0]
        return int(n or 0)

    def toSQL(self, docs: List[Dict[str, Any]]):
        # 參數化插入
        keys = list(docs[0].keys())
        cols = ",".join(f"[{k}]" for k in keys)
        vals = ",".join(["%s"] * len(keys))
        sql = f"INSERT INTO [{self.db['totb']}] ({cols}) VALUES ({vals})"
        data = [tuple(d[k] for k in keys) for d in docs]
        self.cursor.executemany(sql, data)

    # ---------- HTTP scraping ----------
    def get_token(self) -> Optional[str]:
        try:
            headers = {
                "Referer": self.wbinfo["token_url"],
                "Origin": "https://cdcb3.judicial.gov.tw",
            }
            r = self.session.post(self.wbinfo["token_url"], headers=headers, timeout=30)
            if r.status_code != 200:
                logger.error(f"token page status {r.status_code}")
                return None
            soup = BeautifulSoup(r.text, "lxml")
            node = soup.select_one("input[name=token]")
            if not node or not node.get("value"):
                logger.error("token not found in page.")
                return None
            return node.get("value")
        except requests.exceptions.RequestException as e:
            logger.error(f"token request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"token parse failed: {e}")
            return None

    def query_list(self, token: str, ID: str) -> Optional[Dict[str, Any]]:
        try:
            headers = {
                "Referer": self.wbinfo["token_url"],
                "Origin": "https://cdcb3.judicial.gov.tw",
            }
            data = {
                "pageNum": "1",
                "pageSize": "20",
                "crtid": "",
                "queryType": "1",
                "clnm": "",
                "clnm_roma": "",
                "idno": ID,
                "sddt_s": "",
                "sddt_e": "",
                "token": token,
                "condition": "undefined",
            }
            r = self.session.post(self.wbinfo["query_url"], headers=headers, data=data, timeout=45)
            if r.status_code != 200:
                logger.error(f"query_list status {r.status_code} for ID={ID}")
                return None
            # 介面回傳 JSON 字串，有時嵌在 HTML 中，先取文字後 loads
            try:
                payload = json.loads(r.text)
                return payload
            except json.JSONDecodeError:
                # 有時候頁面包 HTML -> 嘗試從 text 抽離
                soup = BeautifulSoup(r.text, "lxml")
                txt = soup.text.strip()
                payload = json.loads(txt)
                return payload
        except requests.exceptions.RequestException as e:
            logger.error(f"query_list request failed for ID={ID}: {e}")
            return None
        except Exception as e:
            logger.error(f"query_list parse failed for ID={ID}: {e}")
            return None

    def view_basis(self, crtid: str, filenm: str, ID: str) -> str:
        """
        讀 VIEW.htm 取得事實摘要(Basis)。若超長或失敗回空字串。
        """
        try:
            data1 = {
                "crtid": crtid,
                "filenm": filenm,
                "condition": f"法院別: 全部法院, 公告類型: 消債事件公告, 身分證字號:{ID}",
                "isDialog": "Y",
            }
            r = self.session.post(self.wbinfo["view_url"], data=data1, timeout=45)
            if r.status_code != 200:
                logger.warning(f"view_basis status {r.status_code} (crtid={crtid})")
                return ""
            soup2 = BeautifulSoup(r.text.replace("</br>", "").replace("<br/>", ""), "lxml")
            tds = soup2.find_all("td")
            if len(tds) >= 4:
                text = tds[3].get_text(separator="", strip=True)
                return text if len(text) <= 4000 else ""
            return ""
        except requests.exceptions.RequestException as e:
            logger.warning(f"view_basis request failed: {e}")
            return ""
        except Exception as e:
            logger.warning(f"view_basis parse failed: {e}")
            return ""

    # ---------- record build ----------
    @staticmethod
    def build_doc_tuple(
        ID: str, name: str, crtid: str, sys: str, crmyy: str, crmid: str, crmno: str,
        crtname: str, durdt: str, durnm: str, filenm: str, crm_text: str, owner: str,
        attachment_rmk: str, attachment_atfilenm: str, attachmentnm: str, Basis: str,
        update_date: str, note: str, filename: str
    ) -> Dict[str, Any]:
        return {
            "ID": ID,
            "Name": name,
            "crtid": crtid,
            "sys": sys,
            "crmyy": crmyy,
            "crmid": crmid,
            "crmno": crmno,
            "crtname": crtname,
            "durdt": durdt,
            "durnm": durnm,
            "filenm": filenm,
            "crm_text": crm_text,
            "owner": owner,
            "attachment_rmk": attachment_rmk,
            "attachment_atfilenm": attachment_atfilenm,
            "attachmentnm": attachmentnm,
            "Basis": Basis,
            "update_date": update_date,
            "note": note,
            "filename": filename,
        }

    # ---------- main flow ----------
    def run(self):
        try:
            # DB
            self.conn = db_connect(self.db)
            self.cursor = self.conn.cursor()
            tasks = self.src_obs()
            if tasks <= 0:
                logger.info("No tasks. Exit.")
                return

            # throttle: 每日上限
            processed_today = self.exit_obs()
            if processed_today >= 5000:
                logger.info("Daily limit (5000) reached. Exit.")
                return

            # time cutoff: 12:00:00 前運行
            now = datetime.datetime.now()
            cutoff = now.replace(hour=11, minute=59, second=59, microsecond=0)
            if now > cutoff:
                logger.info(f"Stop by time cutoff. now={now}, cutoff={cutoff}")
                return

            for _ in range(tasks):
                # 每迭代檢查每日上限與時間限制
                processed_today = self.exit_obs()
                if processed_today >= 5000:
                    logger.info("Daily limit (5000) reached. Stop loop.")
                    break

                now = datetime.datetime.now()
                if now > cutoff:
                    logger.info(f"Stop by time cutoff. now={now}, cutoff={cutoff}")
                    break

                row = self.dbfrom()
                if not row:
                    logger.info("No candidate row. Done.")
                    break

                # unpack
                # personi, ID, name, casei, type, c, m, age, flg, rowid, client_flg
                ID = str(row[1])
                name = str(row[2])
                rowid = ("" if row[9] is None else str(row[9]))
                logger.info(f"Processing ID={ID} name={name} rowid={rowid}")

                token = self.get_token()
                if not token:
                    logger.error(f"Skip ID={ID}: cannot get token.")
                    # 防止無限卡住，稍微等一下
                    time.sleep(1.0)
                    continue

                payload = self.query_list(token, ID)
                today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                docs: List[Dict[str, Any]] = []
                if not payload or "data" not in payload or "dataList" not in payload["data"]:
                    # 視為查無資料
                    logger.info(f"No dataList for ID={ID}. Insert empty-note record.")
                    if rowid:
                        self.delete_row(self.db["totb"], ID, rowid)
                    docs.append(self.build_doc_tuple(
                        ID, name, "", "", "", "", "", "", "", "", "",
                        "", "", "", "", "", "", today_str, "N", ""
                    ))
                else:
                    data_list = payload["data"]["dataList"] or []
                    if len(data_list) == 0:
                        logger.info(f"Empty dataList for ID={ID}. Insert N record.")
                        if rowid:
                            self.delete_row(self.db["totb"], ID, rowid)
                        docs.append(self.build_doc_tuple(
                            ID, name, "", "", "", "", "", "", "", "", "",
                            "", "", "", "", "", "", today_str, "N", ""
                        ))
                    else:
                        # 有資料，逐筆寫入（若目標表已有舊 rowid，先刪除）
                        if rowid:
                            self.delete_row(self.db["totb"], ID, rowid)

                        for i, rec in enumerate(data_list):
                            crtid = str(rec.get("crtid") or "")
                            sys_ = str(rec.get("sys") or "")
                            crmyy = str(rec.get("crmyy") or "")
                            crmid = str(rec.get("crmid") or "")
                            crmno = str(rec.get("crmno") or "")
                            crtname = str(rec.get("crtname") or "")
                            durdt = str(rec.get("durdt") or "")
                            durnm = str(rec.get("durnm") or "")
                            filenm = str(rec.get("filenm") or "")
                            crm_text = str(rec.get("crm_text") or "")
                            owner = str(rec.get("owner") or "")

                            # 附件資訊
                            attachment_rmk = ""
                            attachment_atfilenm = ""
                            attachmentnm = ""
                            try:
                                attach = rec.get("attachment") or []
                                if attach and isinstance(attach, list):
                                    attachment_rmk = str(attach[0].get("rmk") or "")
                                    attachment_atfilenm = str(attach[0].get("atfilenm") or "")
                                attachmentnm = str(rec.get("attachmentnm") or "")
                            except Exception:
                                pass

                            # 事實摘要（過長則留空）
                            basis = self.view_basis(crtid, filenm, ID)
                            if len(basis) > 4000:
                                basis = ""

                            filename = ""  # 如需下載 PDF 可在此實作
                            docs.append(self.build_doc_tuple(
                                ID, name, crtid, sys_, crmyy, crmid, crmno, crtname, durdt, durnm,
                                filenm, crm_text, owner, attachment_rmk, attachment_atfilenm,
                                attachmentnm, basis, today_str, "Y", filename
                            ))

                try:
                    if docs:
                        self.toSQL(docs)
                        self.conn.commit()
                        logger.info(f"ID={ID} inserted {len(docs)} row(s). Total today={self.exit_obs()}")
                except Exception as e:
                    logger.error(f"DB write failed for ID={ID}: {e}")
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    # 攜帶 rowid 的情況可能已刪除舊資料但未成功寫新資料，可標註並繼續
                    continue

                # 輕微節流
                time.sleep(0.2)

            logger.info("Sync finished.")
        finally:
            try:
                if self.cursor:
                    self.cursor.close()
                if self.conn:
                    self.conn.close()
            except Exception:
                pass


def main():
    job = JudicialSync()
    job.run()


if __name__ == "__main__":
    main()
