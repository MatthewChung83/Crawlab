import datetime
import requests
import json
import pymssql
import time
import logging
from typing import Dict, Any, List

# ========= Logging 設定 =========
LOG_PREFIX = "[EmpSalarySync]"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - " + LOG_PREFIX + " %(message)s"
)
logger = logging.getLogger(__name__)

# ========= Deadlock 安全執行 =========
def safe_execute(cursor, sql: str, params: tuple = None, max_retry: int = 5):
    for i in range(max_retry):
        try:
            if params is not None:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return
        except pymssql.OperationalError as e:
            # SQL Server deadlock victim = 1205
            if hasattr(e, "args") and len(e.args) > 0 and "1205" in str(e.args[0]):
                logger.warning(f"SQL deadlock detected, retry {i+1}/{max_retry} ...")
                time.sleep(1 + i * 0.5)
                continue
            raise
        except Exception as e:
            logger.error(f"Unexpected SQL error: {e}")
            raise
    raise Exception("SQL Deadlock retried too many times, abort.")

class EmpSalarySync:
    def __init__(self):
        self.start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"員工薪資資料同步 - 起始時間: {self.start_time}")

        # 資料庫連線設定
        self.db_config = {
            "server": "10.10.0.94",
            "user": "CLUSER",
            "password": "Ucredit7607",
            "database": "CL_Daily",
            "autocommit": False
        }

        # API 設定
        self.session_id = ""
        self.sys_url = "https://hr.ucs.tw/SCSRwd/api/systemobject/"
        self.biz_url = "https://hr.ucs.tw/SCSRwd/api/businessobject/"
        self.headers = {"Content-type": "application/json"}

        # 執行時用變數
        self.conn = None
        self.cursor = None
        self.salary_rows: List[Dict[str, Any]] = []

    # ===== DB 連線 =====
    def get_db_conn(self):
        try:
            self.conn = pymssql.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            logger.info("資料庫連線成功")
        except Exception as e:
            logger.error(f"資料庫連線失敗: {e}")
            raise

    # ===== 抓現有 emp 主檔 empi 清單（加速存在判斷）=====
    def get_existing_emp_ids(self) -> set:
        try:
            self.cursor.execute("SELECT empi FROM emp")
            rows = self.cursor.fetchall()
            existed = {int(r[0]) for r in rows if r[0] is not None}
            logger.info(f"現有 emp 筆數: {len(existed)}")
            return existed
        except Exception as e:
            logger.error(f"讀取現有 emp 失敗: {e}")
            raise

    # ===== 登入 HR API =====
    def login(self) -> bool:
        payload = {
            "Action": "Login",
            "SessionGuid": "",
            "Value": {
                "$type": "AIS.Define.TLogingInputArgs, AIS.Define",
                "CompanyID": "scs164",
                "UserID": "api",
                "Password": "api$1234",
                "LanguageID": "zh-TW"
            }
        }
        try:
            resp = requests.post(self.sys_url, json=payload, headers=self.headers, timeout=60)
            resp.raise_for_status()
            result = resp.json()
            if result.get("Result"):
                self.session_id = result.get("SessionGuid", "")
                logger.info("API 登入成功")
                return True
            logger.error(f"API 登入失敗: {result.get('Message')}")
            return False
        except Exception as e:
            logger.error(f"API 登入請求失敗: {e}")
            return False

    # ===== 取得薪資資料（報表 RHUM002）=====
    def fetch_salary_data(self) -> bool:
        payload = {
            "Action": "ExecReport",
            "SessionGuid": self.session_id,
            "ProgID": "RHUM002",
            "Value": {
                "$type": "AIS.Define.TFindInputArgs, AIS.Define",
                "SelectFields": "SYS_ID,SYS_COMPANYID,EMPLOYEEID,TOTALSALARY,EMPLOYEEENGNAME,EMPLOYEENAME,TMP_DEPARTNAME,TMP_PROFITID",
                "FilterItems": [],
                "SystemFilterOptions": "Session, DataPermission, EmployeeLevel",
                "IsBuildSelectedField": "true",
                "IsBuildFlowLightSignalField": "true"
            }
        }
        try:
            resp = requests.post(self.biz_url, json=payload, headers=self.headers, timeout=120)
            resp.raise_for_status()
            result = resp.json()
            # 報表資料通常在 DataSet.ReportBody
            self.salary_rows = (result.get("DataSet", {}) or {}).get("ReportBody", []) or []
            logger.info(f"從 API 取得薪資筆數: {len(self.salary_rows)}")
            return True
        except Exception as e:
            logger.error(f"取得薪資資料失敗: {e}")
            return False

    # ===== 主處理：比對、更新或新增 =====
    def process(self):
        if not self.salary_rows:
            logger.warning("沒有可處理的薪資資料")
            return

        update_sql = """
            UPDATE emp
            SET [BaseSalary]=%s, [lastupdate]=%s
            WHERE [empi]=%s
        """
        insert_sql = """
            INSERT INTO emp (
                [empi], [name], [cname], [department], [costcenter],
                [BaseSalary], [lastupdate]
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        insert_count = 0
        update_count = 0
        error_count = 0

        try:
            existed = self.get_existing_emp_ids()

            for r in self.salary_rows:
                try:
                    # 避免大小寫差異，統一 key
                    row = { (k.upper() if isinstance(k, str) else k): v for k, v in r.items() }
                    emp_id_raw = row.get("EMPLOYEEID")
                    if emp_id_raw is None or str(emp_id_raw).strip() == "":
                        logger.warning(f"略過一筆無 EMPLOYEEID 的資料: {row}")
                        continue

                    empi = int(emp_id_raw)
                    salary = row.get("TOTALSALARY")
                    # 其餘欄位（INSERT 需要）
                    engname = row.get("EMPLOYEEENGNAME") or None
                    cname = row.get("EMPLOYEENAME") or None
                    dept = row.get("TMP_DEPARTNAME") or None
                    costcenter = row.get("TMP_PROFITID") or None

                    if empi in existed:
                        params = (salary, now_str, empi)
                        safe_execute(self.cursor, update_sql, params)
                        update_count += 1
                    else:
                        params = (empi, engname, cname, dept, costcenter, salary, now_str)
                        safe_execute(self.cursor, insert_sql, params)
                        insert_count += 1

                except Exception as e:
                    error_count += 1
                    logger.error(f"處理 EMPLOYEEID={r.get('EMPLOYEEID')} 發生錯誤: {e}")

            self.conn.commit()
            logger.info(f"薪資資料同步完成｜總筆數={insert_count + update_count}, 更新={update_count}, 新增={insert_count}, 錯誤={error_count}")

        except Exception as e:
            try:
                if self.conn:
                    self.conn.rollback()
            except Exception:
                pass
            logger.error(f"薪資資料處理失敗，已回滾：{e}")
            raise

    def run(self):
        try:
            if not self.login():
                logger.error("終止：API 無法登入")
                return False

            self.get_db_conn()

            if not self.fetch_salary_data():
                logger.error("終止：無法取得薪資資料")
                return False

            self.process()
            end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"員工薪資資料同步 - 結束時間: {end_time}")
            return True
        except Exception as e:
            logger.error(f"同步流程失敗：{e}")
            return False
        finally:
            try:
                if self.cursor:
                    self.cursor.close()
                if self.conn:
                    self.conn.close()
            except Exception:
                pass

def main():
    sync = EmpSalarySync()
    ok = sync.run()
    if ok:
        logger.info("任務完成")
    else:
        logger.error("任務失敗")

if __name__ == "__main__":
    main()
