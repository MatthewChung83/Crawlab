import datetime
import requests
import json
import pymssql
import time
import logging

# 設置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EmployeeDataSync:
    def __init__(self):
        self.getdate = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f'員工資料同步-起始時間: {self.getdate}')

        # 資料庫連線設定（沿用你的設定）
        self.db_config = {
            'server': '10.10.0.94',
            'user': 'CLUSER',
            'password': 'Ucredit7607',
            'database': 'CL_Daily',
            'autocommit': False
        }

        # API 設定
        self.session_id = ''
        self.api_url = 'https://hr.ucs.tw/SCSRwd/api/systemobject/'
        self.business_url = 'https://hr.ucs.tw/SCSRwd/api/businessobject/'
        self.headers = {'Content-type': 'application/json'}
        
        self.dataschema = {"jobstatus": ['試用', '正職', '約聘', '留職停薪', '離職']}

    def safe_execute(self, cursor, sql, params=None, max_retry=5):
        """安全執行 SQL 語句，處理死鎖重試"""
        for i in range(max_retry):
            try:
                if params is not None:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                return True
            except pymssql.OperationalError as e:
                # 1205 = deadlock victim
                if hasattr(e, 'args') and len(e.args) > 0 and '1205' in str(e.args[0]):
                    logger.warning(f"SQL deadlock detected, retry {i+1}/{max_retry} ...")
                    time.sleep(1 + i * 0.5)
                    continue
                else:
                    logger.error(f"SQL execution error: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error in SQL execution: {e}")
                raise
        
        raise Exception("SQL Deadlock retried too many times, abort.")

    def get_database_connection(self):
        """建立資料庫連線"""
        try:
            conn = pymssql.connect(**self.db_config)
            return conn
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def get_existing_employees(self, conn):
        """取得現有員工資料"""
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT empi, name, cname, department, empstatus FROM emp')
            employees = cursor.fetchall()
            cursor.close()
            
            # 轉換為字典格式便於查詢
            emp_dict = {}
            for emp in employees:
                emp_dict[int(emp[0])] = {
                    'name': emp[1],
                    'cname': emp[2],
                    'department': emp[3],
                    'empstatus': emp[4]
                }
            return emp_dict
        except Exception as e:
            logger.error(f"Failed to get existing employees: {e}")
            raise

    def login(self):
        """登入 API 系統"""
        data = {
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
            # 用 json= 讓 requests 自動加 header 與序列化
            response = requests.post(self.api_url, json=data, headers=self.headers, timeout=60)
            response.raise_for_status()
            result = response.json()
            if result.get('Result'):
                self.session_id = result.get('SessionGuid')
                logger.info("API login successful")
                return True
            else:
                logger.error(f"Login failed: {result.get('Message')}")
                return False
        except Exception as e:
            logger.error(f"Login request failed: {e}")
            return False

    def fetch_employee_data(self):
        """從 API 取得員工資料"""
        data = {
            "Action": "Find",
            "SessionGuid": self.session_id,
            "ProgID": "HUM0020100",
            "Value": {
                "$type": "AIS.Define.TFindInputArgs, AIS.Define",
                "SelectFields": ("SYS_VIEWID,SYS_NAME,SYS_ENGNAME,TMP_DEPARTID,TMP_DEPARTNAME,"
                                 "SeparationDate,RETENTIONDATE,TMP_PROFITID,TMP_PROFITNAME,JobStatus,"
                                 "TMP_LEVELNAME,TMP_DECCOMPANYNAME,STARTDATE,BIRTHDATE,TMP_DUTYNAME,"
                                 "OFFICETEL1,IDNO"),
                "FilterItems": [
                    {
                        "$type": "AIS.Define.TFilterItem, AIS.Define",
                        "FieldName": "JobStatus",
                        "FilterValue": "0",
                        "ComparisonOperator": "NotEqual"
                    }
                ],
                "SystemFilterOptions": "Session, DataPermission, EmployeeLevel",
                "IsBuildSelectedField": "true",
                "IsBuildFlowLightSignalField": "true"
            }
        }
        
        try:
            response = requests.post(self.business_url, json=data, headers=self.headers, timeout=120)
            response.raise_for_status()
            result = response.json()
            datatable = result.get('DataTable', [])
            logger.info(f"Fetched {len(datatable)} employee records from API")
            return datatable
        except Exception as e:
            logger.error(f"Failed to fetch employee data: {e}")
            return []

    @staticmethod
    def _safe_str(v):
        return None if v in (None, '') else str(v)

    def process_employee_data(self, datatable, existing_employees):
        """處理員工資料並更新資料庫"""
        if not datatable:
            logger.warning("No employee data to process")
            return

        insert_count = 0
        update_count = 0
        error_count = 0
        
        conn = None
        cursor = None
        try:
            conn = self.get_database_connection()
            cursor = conn.cursor()

            # 預先準備 SQL（固定帶 leftdate，允許為 None）
            update_sql = """
                UPDATE emp 
                SET [name]=%s, [cname]=%s, [department]=%s, [lastupdate]=%s,
                    [costcenter]=%s, [empstatus]=%s, [JOBLEVELNAME]=%s,
                    [leftdate]=%s, [Company]=%s, [INS_DAT]=%s, [BIRTHDATE]=%s,
                    [jobname]=%s, [ext]=%s, [ID]=%s
                WHERE [empi]=%s
            """

            insert_sql = """
                INSERT INTO emp (
                  [empi], [name], [cname], [department], [costcenter],
                  [empstatus], [JOBLEVELNAME], [leftdate], [Company], [INS_DAT],
                  [BIRTHDATE], [jobname], [ext], [ID], [lastupdate]
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for raw in datatable:
                try:
                    # 正規化鍵名 -> 全大寫，避免 JobStatus vs JOBSTATUS
                    employee_data = { (k.upper() if isinstance(k, str) else k): v for k, v in raw.items() }

                    # 取欄位
                    emp_id = int(employee_data.get('SYS_VIEWID'))
                    name = self._safe_str(employee_data.get('SYS_ENGNAME'))
                    cname = self._safe_str(employee_data.get('SYS_NAME'))
                    department = self._safe_str(employee_data.get('TMP_DEPARTNAME'))
                    costcenter = self._safe_str(employee_data.get('TMP_PROFITID'))
                    joblevel = self._safe_str(employee_data.get('TMP_LEVELNAME'))
                    company = self._safe_str(employee_data.get('TMP_DECCOMPANYNAME'))
                    ins_dat = self._safe_str(employee_data.get('STARTDATE'))
                    birthdate = self._safe_str(employee_data.get('BIRTHDATE'))
                    jobname = self._safe_str(employee_data.get('TMP_DUTYNAME'))
                    ext = self._safe_str(employee_data.get('OFFICETEL1'))
                    idno = self._safe_str(employee_data.get('IDNO'))

                    # 職務狀態（1~5 對應 dataschema）
                    raw_status = employee_data.get('JOBSTATUS') or employee_data.get('JOBSTATUS'.upper())
                    try:
                        status_idx = int(raw_status)
                    except Exception:
                        status_idx = 1  # fallback: 正職
                    if 1 <= status_idx <= len(self.dataschema['jobstatus']):
                        empstatus = self.dataschema['jobstatus'][status_idx - 1]
                    else:
                        empstatus = '正職'

                    # 離職/留職停薪日期
                    leftdate = None
                    sep = self._safe_str(employee_data.get('SEPARATIONDATE'))
                    ret = self._safe_str(employee_data.get('RETENTIONDATE'))
                    if empstatus == '離職' and sep:
                        leftdate = sep[:10]
                    elif empstatus == '留職停薪' and ret:
                        leftdate = ret[:10]

                    if emp_id in existing_employees:
                        # UPDATE
                        params = (
                            name, cname, department, now_str,
                            costcenter, empstatus, joblevel,
                            leftdate, company, ins_dat, birthdate,
                            jobname, ext, idno, emp_id
                        )
                        self.safe_execute(cursor, update_sql, params)
                        update_count += 1
                    else:
                        # INSERT
                        params = (
                            emp_id, name, cname, department, costcenter,
                            empstatus, joblevel, leftdate, company, ins_dat,
                            birthdate, jobname, ext, idno, now_str
                        )
                        self.safe_execute(cursor, insert_sql, params)
                        insert_count += 1

                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing employee {raw.get('SYS_VIEWID', 'unknown')}: {e}")
                    continue
            
            # 提交交易
            conn.commit()
            logger.info(f'員工資料同步完成 - 總筆數: {update_count + insert_count}, 更新: {update_count}, 新增: {insert_count}, 錯誤: {error_count}')
            
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.error(f"Database transaction failed: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def run(self):
        """執行完整的同步流程"""
        try:
            # 1. 登入 API
            if not self.login():
                logger.error("Failed to login to API")
                return False
            
            # 2. 取得現有員工資料
            conn = self.get_database_connection()
            existing_employees = self.get_existing_employees(conn)
            conn.close()
            logger.info(f"Found {len(existing_employees)} existing employees in database")
            
            # 3. 從 API 取得員工資料
            datatable = self.fetch_employee_data()
            if not datatable:
                logger.error("No employee data retrieved from API")
                return False
            
            # 4. 處理並更新資料庫
            self.process_employee_data(datatable, existing_employees)
            
            # 5. 記錄結束時間
            end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f'員工資料同步-結束時間: {end_time}')
            
            return True
            
        except Exception as e:
            logger.error(f"Sync process failed: {e}")
            return False

def main():
    """主程式入口"""
    sync = EmployeeDataSync()
    success = sync.run()
    if success:
        logger.info("Employee data sync completed successfully")
    else:
        logger.error("Employee data sync failed")

if __name__ == "__main__":
    main()
