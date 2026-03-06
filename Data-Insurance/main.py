# -*- coding: utf-8 -*-
"""
Insurance crawler - 保險登錄查詢
"""
import os
import sys
import contextlib
import datetime
import requests
import ddddocr
import time
import xml.etree.ElementTree as ET

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import *
from common.logger import get_logger

# Initialize logger
logger = get_logger('Data-Insurance')

# 限制 onnx/dnn/blas 單執行緒
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["ORT_LOGGING_LEVEL"] = "FATAL"


# ---- suppress_stderr context manager ----
@contextlib.contextmanager
def suppress_stderr():
    with open(os.devnull, 'w') as devnull:
        old_stderr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stderr = old_stderr


# DB/網頁設定
server, database, username, password, totb, fromtb = (
    db['server'], db['database'], db['username'], db['password'], db['totb'], db['fromtb']
)

url = "https://public.liaroc.org.tw/lia-public/DIS/Servlet/RD?returnUrl=..%2F..%2FindexUsr.jsp&xml=%3C%3Fxml+version%3D%221.0%22+encoding%3D%22BIG5%22%3F%3E%3CRoot%3E%3CForm%3E%3CreturnUrl%3E..%2F..%2FindexUsr.jsp%3C%2FreturnUrl%3E%3Cxml%2F%3E%3Cfuncid%3EPGQ070++++++++++++++++++++++++%3C%2Ffuncid%3E%3CprogId%3EPGQ070S01%3C%2FprogId%3E%3C%2FForm%3E%3C%2FRoot%3E&funcid=PGQ070++++++++++++++++++++++++&progId=PGQ070S01"
captcha_url = "https://public.liaroc.org.tw/lia-public/simpleCaptcha.png"
headers = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Content-Type": "text/xml;charset=UTF-8",
    "Host": "public.liaroc.org.tw",
    "Origin": "https://public.liaroc.org.tw",
    "Referer": "https://public.liaroc.org.tw/lia-public/DIS/Servlet/RD?returnUrl=...",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
}

# 初始化 session
session = requests.Session()
session.timeout = 30


def build_payload(captcha_code, usrId, DateY, DateM, DateD):
    """建立 payload"""
    try:
        usrIdMask = usrId[:5] + "***" + usrId[-3:] if len(usrId) > 8 else usrId[:3] + "***" + usrId[-2:]
        payload = f'''<?xml version="1.0" encoding="BIG5"?>
                <Root pageIndex="1" action="dis.action.PGQ070S01.queryUserInfo">
                <Form>
                <transaction/>
                <systemDate/>
                <verifyItem/>
                <insertQuery>Y</insertQuery>
                <queryId/>
                <queryBdate/>
                <queryRegId/>
                <usrId>{usrId}</usrId>
                <usrIdMask>{usrIdMask}</usrIdMask>
                <BDate1>{DateY}</BDate1>
                <BDate1Mask>**</BDate1Mask>
                <BDate2>{DateM}</BDate2>
                <BDate3>{DateD}</BDate3>
                <captchaAnswer>{captcha_code}</captchaAnswer>
                </Form>
                </Root>
                '''
        return payload
    except Exception as e:
        logger.error(f"建立 payload 失敗 (usrId={usrId}): {e}")
        return None


def query_regno(usrId, DateY, DateM, DateD, max_retry=10):
    """查詢保險登錄號"""
    logger.ctx.set_data(usrId=usrId)
    logger.debug(f"開始查詢用戶: {usrId}, 生日: {DateY}/{DateM}/{DateD}")

    try:
        for i in range(max_retry):
            try:
                # 獲取驗證碼圖片
                logger.ctx.set_operation("get_captcha")
                captcha_response = session.get(captcha_url, verify=False, timeout=10)

                if captcha_response.status_code != 200:
                    logger.warning(f"驗證碼請求失敗，狀態碼: {captcha_response.status_code}")
                    time.sleep(2)
                    continue

                captcha_img = captcha_response.content

                # 識別驗證碼
                try:
                    with suppress_stderr():
                        captcha_code = ddddocr.DdddOcr(show_ad=False).classification(captcha_img)
                    logger.log_captcha_attempt(i + 1, True, captcha_code)
                except Exception as ocr_error:
                    logger.warning(f"OCR 識別失敗: {ocr_error}")
                    time.sleep(1)
                    continue

                # 建立 payload
                payload = build_payload(captcha_code, usrId, DateY, DateM, DateD)
                if payload is None:
                    logger.error("Payload 建立失敗")
                    return None

                # 發送請求
                logger.ctx.set_operation("query_insurance")
                try:
                    start_time = time.time()
                    resp = session.post(
                        url,
                        data=payload.encode("big5"),
                        headers=headers,
                        verify=False,
                        timeout=15
                    )
                    elapsed = time.time() - start_time

                    # 檢查是否為 500 錯誤
                    if resp.status_code == 500:
                        logger.error(f"HTTP 500 伺服器錯誤 - usrId={usrId}, 嘗試={i+1}")
                        raise SystemExit("HTTP 500 伺服器錯誤，程式正常停止")

                    if resp.status_code != 200:
                        logger.warning(f"POST 請求失敗，狀態碼: {resp.status_code}")
                        time.sleep(2)
                        continue

                except requests.exceptions.Timeout:
                    logger.warning(f"請求超時 (第 {i+1} 次)")
                    time.sleep(3)
                    continue
                except requests.exceptions.ConnectionError as conn_error:
                    logger.warning(f"連線錯誤 (第 {i+1} 次): {conn_error}")
                    time.sleep(5)
                    continue
                except requests.exceptions.RequestException as req_error:
                    logger.warning(f"請求異常 (第 {i+1} 次): {req_error}")
                    time.sleep(2)
                    continue

                # 解析回應
                logger.ctx.set_operation("parse_result")
                try:
                    result = resp.content.decode("big5", errors="ignore")

                    if "<CaptchaError>" in result:
                        logger.debug(f"{usrId} 第{i+1}次驗證碼失敗 code={captcha_code}")
                        time.sleep(1)
                        continue
                    else:
                        # 解析 XML
                        try:
                            root = ET.fromstring(result)
                            row = root.find('Row')

                            if row is None:
                                logger.debug(f"{usrId} XML 中找不到 Row 元素")
                                return None

                            regno = row.findtext('regno')
                            regFlag = row.findtext('regFlag')
                            tarrvy = row.findtext('tarrvy')
                            tarrvm = row.findtext('tarrvm')
                            tarrvd = row.findtext('tarrvd')

                            if (not regno or regno.strip() == '') and regFlag == "0" and tarrvy == "000" and tarrvm == "00" and tarrvd == "00":
                                logger.debug(f"{usrId} 未辦理登錄")
                                return "未辦理登錄"

                            result_data = {
                                "regno": regno,
                                "date": f"民國{tarrvy}年{tarrvm}月{tarrvd}日"
                            }
                            logger.debug(f"{usrId} 查詢成功: regno={regno}")
                            return result_data

                        except ET.ParseError as xml_error:
                            logger.warning(f"{usrId} XML解析錯誤: {xml_error}")
                            return None

                except UnicodeDecodeError as decode_error:
                    logger.warning(f"回應解碼錯誤: {decode_error}")
                    time.sleep(1)
                    continue

            except SystemExit:
                raise
            except Exception as loop_error:
                logger.warning(f"迴圈內錯誤 (第 {i+1} 次): {loop_error}")
                time.sleep(2)
                continue

        logger.warning(f"{usrId} 超過 {max_retry} 次重試仍失敗")
        return None

    except SystemExit:
        raise
    except Exception as main_error:
        logger.log_exception(main_error, f"query_regno 主函數錯誤 (usrId={usrId})")
        return None


def run():
    """Main execution function"""
    logger.task_start("保險登錄查詢")
    logger.log_db_connect(server, database, username)

    total_processed = 0
    total_success = 0
    total_failed = 0

    try:
        obs = src_obs(server, username, password, database, fromtb, totb)
        logger.info(f"待處理筆數: {obs}")

        if obs == 0:
            logger.info("沒有待處理的資料")
            logger.task_end(success=True)
            return True

        for i in foo(-1, obs - 1):
            total_processed += 1
            logger.log_progress(total_processed, obs, f"record_{total_processed}")

            try:
                src = dbfrom(server, username, password, database, fromtb, totb)[0]
                today = str(datetime.datetime.now())[0:-3]
                Name = src[2]
                ID = src[1]
                birthday = src[6]
                rowid = str(src[10]).replace('None', '')

                logger.ctx.set_data(ID=ID, Name=Name)
                logger.debug(f"處理用戶: {Name} (ID: {ID})")

                # 解析生日
                try:
                    bir = birthday.split('/', 2)
                    birY, birM, birD = bir[0], bir[1], bir[2]
                except Exception as birthday_error:
                    logger.warning(f"生日解析錯誤 ({birthday}): {birthday_error}")
                    total_failed += 1
                    logger.increment('records_failed')
                    continue

                # 查詢保險資訊
                message = query_regno(ID, birY, birM, birD)

                # 處理查詢結果
                if message is None:
                    note = 'N'
                    insurance_num = ''
                    logger.debug(f"{ID} 查無資料")
                elif message == "未辦理登錄":
                    note = 'N'
                    insurance_num = ''
                    logger.debug(f"{ID} 未辦理登錄")
                else:
                    insurance_num = message.get("regno", "")
                    note = 'Y' if insurance_num != '' else 'N'
                    logger.info(f"{ID} 查詢成功 regno={insurance_num}")

                # 準備資料並寫入資料庫
                logger.ctx.set_operation("DB_update")
                logger.ctx.set_db(server=server, database=database, table=totb, operation="UPDATE/INSERT")

                try:
                    docs = (Name, ID, birthday, insurance_num, today, note)
                    insurance_result = insurance(docs)

                    if len(rowid) > 0:
                        update(server, username, password, database, totb, note, ID, today, rowid, insurance_num)
                        logger.log_db_operation("UPDATE", database, totb, 1)
                    else:
                        toSQL(insurance_result, totb, server, database, username, password)
                        logger.log_db_operation("INSERT", database, totb, 1)

                    total_success += 1
                    logger.increment('records_success')

                except Exception as db_error:
                    logger.log_exception(db_error, f"資料庫操作錯誤 (ID={ID})")
                    total_failed += 1
                    logger.increment('records_failed')
                    continue

                # 檢查查詢總筆數
                try:
                    exit_o = exit_obs(server, username, password, database, totb)

                    if exit_o >= 5000:
                        logger.warning('今日查詢數已達上限 5000 筆，正常停止')
                        break

                except Exception as check_error:
                    logger.warning(f"檢查查詢數錯誤: {check_error}")

            except SystemExit as sys_exit:
                logger.warning(f"程式因 HTTP 500 錯誤正常停止: {sys_exit}")
                break
            except Exception as record_error:
                logger.log_exception(record_error, f"處理第 {total_processed} 筆資料時發生錯誤")
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

    except SystemExit:
        logger.warning("程式正常停止")
        logger.task_end(success=False)
        return False
    except Exception as e:
        logger.log_exception(e, "執行過程發生錯誤")
        logger.task_end(success=False)
        return False


def main():
    """Main entry point"""
    logger.info(f"資料庫: {db['server']}.{db['database']}")
    logger.info(f"來源表: {fromtb}")
    logger.info(f"目標表: {totb}")

    try:
        success = run()
        if success:
            logger.info("執行完成")
        else:
            logger.warning("執行過程有錯誤")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except SystemExit as e:
        logger.warning(f"程式正常結束: {e}")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == "__main__":
    main()
