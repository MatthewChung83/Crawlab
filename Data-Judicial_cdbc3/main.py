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
from typing import Dict, Any, List, Optional

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup
import logging

from config import *
from etl_func import *

# ============ Logging ============
LOG_PREFIX = "[JudicialSync]"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - " + LOG_PREFIX + " %(message)s"
)
logger = logging.getLogger(__name__)


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
    def __init__(self):
        self.session = build_session()
        self.conn = None
        self.cursor = None
        self.today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.timeout = crawler['timeout']
        self.daily_limit = crawler['daily_limit']
        self.delay = crawler['delay']
        logger.info(f"Start sync at {self.today_str}")

    # ---------- HTTP scraping ----------
    def get_token(self) -> Optional[str]:
        try:
            headers = {
                "Referer": wbinfo["token_url"],
                "Origin": "https://cdcb3.judicial.gov.tw",
            }
            r = self.session.post(wbinfo["token_url"], headers=headers, timeout=self.timeout)
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
                "Referer": wbinfo["token_url"],
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
            r = self.session.post(wbinfo["query_url"], headers=headers, data=data, timeout=self.timeout)
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
            r = self.session.post(wbinfo["view_url"], data=data1, timeout=self.timeout)
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
            self.conn = db_connect(db)
            self.cursor = self.conn.cursor()
            tasks = src_obs(self.cursor, db['fromtb'], db['totb'])
            if tasks <= 0:
                logger.info("No tasks. Exit.")
                return

            # throttle: 每日上限
            processed_today = exit_obs(self.cursor, db['totb'])
            if processed_today >= self.daily_limit:
                logger.info(f"Daily limit ({self.daily_limit}) reached. Exit.")
                return

            # time cutoff: 12:00:00 前運行
            now = datetime.datetime.now()
            cutoff = now.replace(hour=11, minute=59, second=59, microsecond=0)
            if now > cutoff:
                logger.info(f"Stop by time cutoff. now={now}, cutoff={cutoff}")
                return

            for _ in range(tasks):
                # 每迭代檢查每日上限與時間限制
                processed_today = exit_obs(self.cursor, db['totb'])
                if processed_today >= self.daily_limit:
                    logger.info(f"Daily limit ({self.daily_limit}) reached. Stop loop.")
                    break

                now = datetime.datetime.now()
                if now > cutoff:
                    logger.info(f"Stop by time cutoff. now={now}, cutoff={cutoff}")
                    break

                row = dbfrom(self.cursor, db['fromtb'], db['totb'])
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
                        delete_row(self.cursor, db["totb"], ID, rowid)
                    docs.append(self.build_doc_tuple(
                        ID, name, "", "", "", "", "", "", "", "", "",
                        "", "", "", "", "", "", today_str, "N", ""
                    ))
                else:
                    data_list = payload["data"]["dataList"] or []
                    if len(data_list) == 0:
                        logger.info(f"Empty dataList for ID={ID}. Insert N record.")
                        if rowid:
                            delete_row(self.cursor, db["totb"], ID, rowid)
                        docs.append(self.build_doc_tuple(
                            ID, name, "", "", "", "", "", "", "", "", "",
                            "", "", "", "", "", "", today_str, "N", ""
                        ))
                    else:
                        # 有資料，逐筆寫入（若目標表已有舊 rowid，先刪除）
                        if rowid:
                            delete_row(self.cursor, db["totb"], ID, rowid)

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
                        toSQL(self.cursor, db['totb'], docs)
                        self.conn.commit()
                        logger.info(f"ID={ID} inserted {len(docs)} row(s). Total today={exit_obs(self.cursor, db['totb'])}")
                except Exception as e:
                    logger.error(f"DB write failed for ID={ID}: {e}")
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    # 攜帶 rowid 的情況可能已刪除舊資料但未成功寫新資料，可標註並繼續
                    continue

                # 輕微節流
                time.sleep(self.delay)

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
    print("司法院消債事件公告同步程式")
    print("=" * 50)
    print(f"資料庫: {db['server']}.{db['database']}")
    print(f"目標資料表: {db['totb']}")

    job = JudicialSync()
    job.run()


if __name__ == "__main__":
    main()
