# -*- coding: utf-8 -*-
"""
Judicial cdcb3 sync - 消債事件公告同步
- requests.Session + Retry 防止 DNS/連線暫失
- SQL 改為參數化 (%s) + 語法修正
- 統一 Log 模組
"""

import os
import sys
import datetime
import time
import json
from typing import Dict, Any, List, Optional

import requests
from requests.adapters import HTTPAdapter, Retry
from bs4 import BeautifulSoup

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import *
from common.logger import get_logger

# Initialize logger
logger = get_logger('Data-Judicial_cdbc3')


def build_session() -> requests.Session:
    """Build HTTP session with retry"""
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


class JudicialSync:
    def __init__(self):
        self.session = build_session()
        self.conn = None
        self.cursor = None
        self.today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.timeout = crawler['timeout']
        self.daily_limit = crawler['daily_limit']
        self.delay = crawler['delay']

    def get_token(self) -> Optional[str]:
        """Get CSRF token from page"""
        logger.ctx.set_operation("get_token")
        try:
            headers = {
                "Referer": wbinfo["token_url"],
                "Origin": "https://cdcb3.judicial.gov.tw",
            }
            start_time = time.time()
            logger.log_request("POST", wbinfo["token_url"], headers, None)

            r = self.session.post(wbinfo["token_url"], headers=headers, timeout=self.timeout)
            elapsed = time.time() - start_time

            logger.log_response(r.status_code, dict(r.headers), f"[HTML: {len(r.text)} chars]", elapsed)

            if r.status_code != 200:
                logger.error(f"token 頁面狀態碼: {r.status_code}")
                return None

            soup = BeautifulSoup(r.text, "lxml")
            node = soup.select_one("input[name=token]")
            if not node or not node.get("value"):
                logger.error("token 未找到")
                return None

            token = node.get("value")
            logger.debug(f"取得 token: {token[:20]}...")
            return token

        except requests.exceptions.RequestException as e:
            logger.log_http_error(e, wbinfo["token_url"])
            return None
        except Exception as e:
            logger.log_exception(e, "token 解析失敗")
            return None

    def query_list(self, token: str, ID: str) -> Optional[Dict[str, Any]]:
        """Query data list for ID"""
        logger.ctx.set_operation("query_list")
        logger.ctx.set_data(ID=ID)

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

            start_time = time.time()
            logger.log_request("POST", wbinfo["query_url"], headers, data)

            r = self.session.post(wbinfo["query_url"], headers=headers, data=data, timeout=self.timeout)
            elapsed = time.time() - start_time

            logger.log_response(r.status_code, dict(r.headers), r.text[:500] if len(r.text) > 500 else r.text, elapsed)

            if r.status_code != 200:
                logger.error(f"query_list 狀態碼: {r.status_code}, ID={ID}")
                return None

            try:
                payload = json.loads(r.text)
                return payload
            except json.JSONDecodeError:
                soup = BeautifulSoup(r.text, "lxml")
                txt = soup.text.strip()
                payload = json.loads(txt)
                return payload

        except requests.exceptions.RequestException as e:
            logger.log_http_error(e, wbinfo["query_url"])
            return None
        except Exception as e:
            logger.log_exception(e, f"query_list 解析失敗, ID={ID}")
            return None

    def view_basis(self, crtid: str, filenm: str, ID: str) -> str:
        """Get case basis (事實摘要)"""
        logger.ctx.set_operation("view_basis")
        try:
            data1 = {
                "crtid": crtid,
                "filenm": filenm,
                "condition": f"法院別: 全部法院, 公告類型: 消債事件公告, 身分證字號:{ID}",
                "isDialog": "Y",
            }

            start_time = time.time()
            logger.log_request("POST", wbinfo["view_url"], None, data1)

            r = self.session.post(wbinfo["view_url"], data=data1, timeout=self.timeout)
            elapsed = time.time() - start_time

            logger.log_response(r.status_code, dict(r.headers), f"[HTML: {len(r.text)} chars]", elapsed)

            if r.status_code != 200:
                logger.warning(f"view_basis 狀態碼: {r.status_code}, crtid={crtid}")
                return ""

            soup2 = BeautifulSoup(r.text.replace("</br>", "").replace("<br/>", ""), "lxml")
            tds = soup2.find_all("td")
            if len(tds) >= 4:
                text = tds[3].get_text(separator="", strip=True)
                return text if len(text) <= 4000 else ""
            return ""

        except requests.exceptions.RequestException as e:
            logger.log_http_error(e, wbinfo["view_url"])
            return ""
        except Exception as e:
            logger.warning(f"view_basis 解析失敗: {e}")
            return ""

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

    def run(self):
        """Main execution"""
        logger.task_start("消債事件公告同步 (cdbc3)")

        try:
            # DB connect
            logger.ctx.set_operation("DB_connect")
            logger.log_db_connect(db['server'], db['database'], db['username'])

            self.conn = db_connect(db)
            self.cursor = self.conn.cursor()

            tasks = src_obs(self.cursor, db['fromtb'], db['totb'])
            logger.info(f"待處理筆數: {tasks}")

            if tasks <= 0:
                logger.info("沒有待處理的任務")
                logger.task_end(success=True)
                return True

            # Check daily limit
            processed_today = exit_obs(self.cursor, db['totb'])
            if processed_today >= self.daily_limit:
                logger.info(f"已達每日上限 ({self.daily_limit})")
                logger.task_end(success=True)
                return True

            # Time cutoff: 12:00:00
            now = datetime.datetime.now()
            cutoff = now.replace(hour=11, minute=59, second=59, microsecond=0)
            if now > cutoff:
                logger.info(f"超過時間限制. now={now}, cutoff={cutoff}")
                logger.task_end(success=True)
                return True

            total_processed = 0

            for task_idx in range(tasks):
                logger.log_progress(task_idx + 1, tasks, f"task_{task_idx + 1}")

                # Check limits each iteration
                processed_today = exit_obs(self.cursor, db['totb'])
                if processed_today >= self.daily_limit:
                    logger.info(f"已達每日上限 ({self.daily_limit})")
                    break

                now = datetime.datetime.now()
                if now > cutoff:
                    logger.info(f"超過時間限制")
                    break

                row = dbfrom(self.cursor, db['fromtb'], db['totb'])
                if not row:
                    logger.info("沒有候選記錄")
                    break

                ID = str(row[1])
                name = str(row[2])
                rowid = ("" if row[9] is None else str(row[9]))

                logger.ctx.set_data(ID=ID, name=name, rowid=rowid)
                logger.info(f"處理: ID={ID}, name={name}")

                token = self.get_token()
                if not token:
                    logger.error(f"跳過 ID={ID}: 無法取得 token")
                    time.sleep(1.0)
                    continue

                payload = self.query_list(token, ID)
                today_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                docs: List[Dict[str, Any]] = []

                if not payload or "data" not in payload or "dataList" not in payload["data"]:
                    logger.info(f"ID={ID} 查無資料")
                    if rowid:
                        delete_row(self.cursor, db["totb"], ID, rowid)
                    docs.append(self.build_doc_tuple(
                        ID, name, "", "", "", "", "", "", "", "", "",
                        "", "", "", "", "", "", today_str, "N", ""
                    ))
                else:
                    data_list = payload["data"]["dataList"] or []
                    if len(data_list) == 0:
                        logger.info(f"ID={ID} dataList 為空")
                        if rowid:
                            delete_row(self.cursor, db["totb"], ID, rowid)
                        docs.append(self.build_doc_tuple(
                            ID, name, "", "", "", "", "", "", "", "", "",
                            "", "", "", "", "", "", today_str, "N", ""
                        ))
                    else:
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

                            basis = self.view_basis(crtid, filenm, ID)
                            if len(basis) > 4000:
                                basis = ""

                            docs.append(self.build_doc_tuple(
                                ID, name, crtid, sys_, crmyy, crmid, crmno, crtname, durdt, durnm,
                                filenm, crm_text, owner, attachment_rmk, attachment_atfilenm,
                                attachmentnm, basis, today_str, "Y", ""
                            ))

                try:
                    if docs:
                        logger.ctx.set_operation("DB_insert")
                        logger.ctx.set_db(server=db['server'], database=db['database'], table=db['totb'], operation="INSERT")

                        toSQL(self.cursor, db['totb'], docs)
                        self.conn.commit()

                        logger.log_db_operation("INSERT", db['database'], db['totb'], len(docs))
                        logger.increment('records_success', len(docs))
                        total_processed += len(docs)

                except Exception as e:
                    logger.log_db_error(e, "INSERT")
                    try:
                        self.conn.rollback()
                    except Exception:
                        pass
                    continue

                time.sleep(self.delay)

            logger.log_stats({
                'total_tasks': tasks,
                'total_processed': total_processed,
            })

            logger.task_end(success=True)
            return True

        except Exception as e:
            logger.log_exception(e, "執行過程發生錯誤")
            logger.task_end(success=False)
            return False

        finally:
            try:
                if self.cursor:
                    self.cursor.close()
                if self.conn:
                    self.conn.close()
                logger.info("資料庫連接已關閉")
            except Exception:
                pass


def run():
    """Main execution function"""
    job = JudicialSync()
    return job.run()


def main():
    """Main entry point"""
    logger.info(f"資料庫: {db['server']}.{db['database']}")
    logger.info(f"目標資料表: {db['totb']}")

    try:
        success = run()
        if success:
            logger.info("同步完成")
        else:
            logger.warning("同步失敗")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == "__main__":
    main()
