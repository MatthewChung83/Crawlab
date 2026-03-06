# -*- coding: utf-8 -*-
"""
Insurance_inc crawler - 保險登錄機構查詢
"""
import os
import sys
import requests
import ddddocr
import time
import xml.etree.ElementTree as ET
import warnings
import logging

# 完全抑制警告和 ONNX Runtime 日誌
warnings.filterwarnings("ignore")
logging.getLogger("onnxruntime").setLevel(logging.CRITICAL)

# 設定環境變數以避免 ONNX Runtime 執行緒親和性錯誤
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['ONNXRUNTIME_LOG_SEVERITY_LEVEL'] = '4'
os.environ['ORT_LOGGING_LEVEL'] = '4'

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import *
from common.logger import get_logger

# Initialize logger
logger = get_logger('Data-Insurance_inc')

# 重定向 stderr 以抑制 C++ 層級的錯誤訊息
class NullWriter:
    def write(self, txt): pass
    def flush(self): pass

# 暫存原始 stderr
original_stderr = sys.stderr

# Session 和 URL 設定
session = requests.Session()
url = "https://public.liaroc.org.tw/lia-public/DIS/Servlet/RD"
captcha_url = "https://public.liaroc.org.tw/lia-public/simpleCaptcha.png"

headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Content-Type": "text/xml;charset=UTF-8",
    "Host": "public.liaroc.org.tw",
    "Origin": "https://public.liaroc.org.tw",
    "Referer": "https://public.liaroc.org.tw/lia-public/DIS/Servlet/RD?returnUrl=..%2F..%2FindexUsr.jsp&xml=%3C%3Fxml+version%3D%221.0%22+encoding%3D%22BIG5%22%3F%3E%3CRoot%3E%3CForm%3E%3CreturnUrl%3E..%2F..%2FindexUsr.jsp%3C%2FreturnUrl%3E%3Cxml%2F%3E%3Cfuncid%3EPGQ010++++++++++++++++++++++++%3C%2Ffuncid%3E%3CprogId%3EPGQ010S01%3C%2FprogId%3E%3C%2FForm%3E%3C%2FRoot%3E&funcid=PGQ010++++++++++++++++++++++++&progId=PGQ010S01",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
}

# 從原始設定檔讀取資料庫設定
server, database, username, password, totb1, entitytype = (
    db['server'], db['database'], db['username'], db['password'], db['totb1'], db['entitytype']
)


def build_payload(captcha_code, regno):
    """建構查詢用的 XML payload"""
    return f'''<?xml version="1.0" encoding="BIG5"?>
            <Root pageIndex="1" action="dis.action.PGQ010S01.queryUserInfo">
            <Form>
            <transaction/>
            <systemDate/>
            <verifyItem/>
            <insertQuery>Y</insertQuery>
            <queryId/>
            <queryBdate/>
            <queryRegId/>
            <regNo>{regno}</regNo>
            <regNoMask>{regno[:4]}***{regno[-3:]}</regNoMask>
            <captchaAnswer>{captcha_code}</captchaAnswer>
            </Form>
            </Root>
            '''


def query_regno_requests(regno, max_retry=1000):
    """使用 requests 方式查詢統編"""
    logger.ctx.set_data(regno=regno)

    for i in range(max_retry):
        try:
            # 1. 取得驗證碼
            logger.ctx.set_operation("get_captcha")
            captcha_img = session.get(captcha_url, verify=False).content

            # 暫時重定向 stderr 以抑制 ONNX Runtime 錯誤訊息
            sys.stderr = NullWriter()
            try:
                captcha_code = ddddocr.DdddOcr(show_ad=False).classification(captcha_img)
            finally:
                sys.stderr = original_stderr

            logger.log_captcha_attempt(i + 1, True, captcha_code)

            # 2. 準備 payload
            payload = build_payload(captcha_code, regno)

            # 3. 發送查詢
            logger.ctx.set_operation("query_insurance")
            start_time = time.time()
            resp = session.post(url, data=payload.encode("big5"), headers=headers, verify=False)
            elapsed = time.time() - start_time

            result = resp.content.decode("big5", errors="ignore")

            # 4. 判斷是否驗證碼錯誤
            if "<CaptchaError>" in result:
                logger.debug(f"驗證碼錯誤 (第 {i+1} 次)")
                time.sleep(1)
                continue
            else:
                logger.debug(f"查詢成功 ({elapsed:.2f}s)")

                # 5. 解析結果
                result_data = parse_query_result(result)
                return True, result_data

        except Exception as e:
            logger.warning(f"查詢過程發生錯誤 (第 {i+1} 次): {e}")
            time.sleep(1)
            continue

    logger.warning(f"超過 {max_retry} 次重試仍失敗")
    return False, {'message': '查詢失敗'}


def parse_query_result(result):
    """解析查詢結果"""
    result_data = {
        'login_date': '',
        'login_inc': '',
        'Insurance_type': '',
        'status': 'N',
        'message': ''
    }

    # 檢查是否查無資料
    if '查無資料' in result:
        result_data['message'] = '查無資料'
        result_data['login_inc'] = '查無資料'
        return result_data

    try:
        # 解析 XML
        root = ET.fromstring(result)
        row = root.find('Row')

        if row is not None:
            # 提取基本資料
            regno = row.find('regno').text if row.find('regno') is not None else ''
            tarrvy = row.find('tarrvy').text if row.find('tarrvy') is not None else ''
            tarrvm = row.find('tarrvm').text if row.find('tarrvm') is not None else ''
            tarrvd = row.find('tarrvd').text if row.find('tarrvd') is not None else ''
            regUnit = row.find('regUnit').text if row.find('regUnit') is not None else ''
            regnstatus = row.find('regnstatus').text if row.find('regnstatus') is not None else ''

            # 組合登錄日期
            if tarrvy and tarrvm and tarrvd:
                result_data['login_date'] = f"民國{tarrvy}年{tarrvm}月{tarrvd}日"

            # 設定 login_inc (登錄機構)
            if regUnit and regUnit.strip():
                result_data['login_inc'] = regUnit.strip()
            else:
                result_data['login_inc'] = '未辦理登錄'

            # 判斷狀態：如果註銷或未辦理登錄則為 N，否則為 Y
            if '註銷' in regnstatus or '停職' in regnstatus:
                result_data['status'] = 'N'
            elif result_data['login_inc'] != '未辦理登錄' and result_data['login_date']:
                result_data['status'] = 'Y'
            else:
                result_data['status'] = 'N'

            # 串接保險種類資訊 (kindA~kindZ)
            insurance_types = []
            kind_fields = ['kindA', 'kindB', 'kindC', 'kindD', 'kindE', 'kindF', 'kindG', 'kindH', 'kindI', 'kindZ']

            for kind_field in kind_fields:
                kind_node = row.find(kind_field)
                if kind_node is not None and kind_node.text and kind_node.text.strip():
                    insurance_types.append(kind_node.text.strip())

            # 將所有保險種類用適當的分隔符串接
            if insurance_types:
                result_data['Insurance_type'] = '、'.join(insurance_types)
            else:
                result_data['Insurance_type'] = ''

        else:
            # 查詢成功但沒有資料
            result_data['login_inc'] = '未辦理登錄'
            result_data['message'] = '查詢成功，但沒有找到資料'

    except Exception as e:
        logger.warning(f"XML 解析失敗: {e}")
        result_data['message'] = 'XML解析錯誤'
        result_data['login_inc'] = 'XML解析錯誤'

    return result_data


def process_single_record(record_data, is_first_record=False):
    """處理單筆記錄的查詢和資料庫更新"""
    name = record_data['name']
    ID = record_data['ID']
    IDN_10 = record_data['IDN_10']

    logger.ctx.set_data(ID=ID, IDN_10=IDN_10)
    logger.debug(f"處理記錄: ID={ID}, IDN_10={IDN_10}")

    # 根據是否為第一筆記錄決定重試次數
    max_retry = 1000 if is_first_record else 10

    # 執行查詢
    success, result_data = query_regno_requests(IDN_10, max_retry)

    # 準備資料庫更新資料
    updatetime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    login_date = result_data['login_date']
    login_inc = result_data['login_inc']
    Insurance_type = result_data['Insurance_type']
    status = result_data['status']

    # 更新資料庫
    logger.ctx.set_operation("DB_update")
    logger.ctx.set_db(server=server, database=database, table=totb1, operation="UPDATE")

    updateSQL(server, username, password, database, totb1, entitytype, status, updatetime, ID, IDN_10, Insurance_type, login_date, login_inc)
    logger.log_db_operation("UPDATE", database, totb1, 1)
    logger.info(f"更新完成: ID={ID}, 機構={login_inc}, 狀態={status}")

    # 檢查今日查詢筆數限制
    exit_o = exit_obs(server, username, password, database, totb1)
    if exit_o >= 5000:
        logger.warning("今日查詢筆數已達上限 5000 筆")
        return False

    return True


def run():
    """Main execution function"""
    logger.task_start("保險登錄機構查詢")
    logger.log_db_connect(server, database, username)

    total_processed = 0
    total_success = 0
    total_failed = 0

    try:
        obs = src_obs(server, username, password, database, totb1, entitytype)
        logger.info(f"待處理筆數: {obs}")

        if obs == 0:
            logger.info("沒有待處理的資料")
            logger.task_end(success=True)
            return True

        for i in range(obs):
            total_processed += 1
            logger.log_progress(total_processed, obs, f"record_{total_processed}")

            try:
                # 從資料庫取得待處理資料
                src = dbfrom(server, username, password, database, totb1, entitytype)

                if not src or len(src) == 0:
                    logger.info("沒有待處理的記錄")
                    break

                record_data = {
                    'name': src[0][1],
                    'ID': src[0][2],
                    'IDN_10': src[0][4]
                }

                # 處理記錄（第一筆記錄有特殊處理）
                is_first_record = (i == 0)
                if process_single_record(record_data, is_first_record):
                    total_success += 1
                    logger.increment('records_success')
                else:
                    # 達到上限，跳出迴圈
                    break

                # 每筆記錄間隔，避免請求過於頻繁
                time.sleep(2)

            except Exception as e:
                logger.log_exception(e, f"處理第 {total_processed} 筆資料時發生錯誤")
                total_failed += 1
                logger.increment('records_failed')
                continue

        logger.log_stats({
            'total_processed': total_processed,
            'total_success': total_success,
            'total_failed': total_failed,
        })

        logger.task_end(success=(total_failed == 0))
        return total_failed == 0

    except Exception as e:
        logger.log_exception(e, "執行過程發生錯誤")
        logger.task_end(success=False)
        return False


def main():
    """Main entry point"""
    logger.info(f"資料庫: {db['server']}.{db['database']}")
    logger.info(f"目標表: {totb1}")

    try:
        success = run()
        if success:
            logger.info("執行完成")
        else:
            logger.warning("執行過程有錯誤")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == "__main__":
    main()
