# -*- coding: utf-8 -*-
"""
TaxReturn crawler - 綜合所得稅申報查詢
"""
import os
import sys
import re
import gc
import time
import requests
import ddddocr
from bs4 import BeautifulSoup
from datetime import datetime as dt

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import *
from common.logger import get_logger

# Initialize logger
logger = get_logger('Data-TaxReturn')

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()


def run():
    """Main execution function"""
    logger.task_start("綜合所得稅申報查詢")

    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']
    entitytype = db['entitytype']
    fromtb = db['fromtb']
    totb = db['totb']

    Apurl = APinfo['Apurl']

    logger.log_db_connect(server, database, username)

    try:
        while True:
            obs = src_obs(server, username, password, database, fromtb, totb, entitytype)
            logger.info(f"待處理筆數: {obs}")

            if obs == 0:
                logger.info("沒有待處理的資料")
                break

            src = dbfrom(server, username, password, database, fromtb, totb, entitytype)
            total_records = len(src) if hasattr(src, '__len__') else 1

            for i in range(total_records):
                logger.log_progress(i + 1, total_records, f"record_{i + 1}")

                try:
                    record = src[i] if hasattr(src, '__getitem__') else src
                    psid = record[0]
                    pid = record[1]
                    birthyear_tw = record[10]
                    insertdate = dt.today().strftime("%Y/%m/%d %H:%M:%S")

                    logger.ctx.set_data(psid=psid, pid=pid)
                    logger.debug(f"處理: psid={psid}, pid={pid}")

                    time.sleep(0.5)

                    # 建立 OCR 與 session
                    ocr = ddddocr.DdddOcr(show_ad=False)
                    session = requests.Session()

                    # Step 1：取得驗證碼圖片並辨識
                    logger.ctx.set_operation("get_captcha")
                    captcha_url = 'https://svc.tax.nat.gov.tw/svc/ibxValidateCode'

                    start_time = time.time()
                    logger.log_request("GET", captcha_url, None, None)

                    captcha = session.get(captcha_url, verify=False, timeout=30)
                    elapsed = time.time() - start_time

                    logger.log_response(captcha.status_code, dict(captcha.headers), f"[Image: {len(captcha.content)} bytes]", elapsed)

                    code = ocr.classification(captcha.content)
                    logger.log_captcha_attempt(1, True, code)

                    # Step 2：送出查詢
                    logger.ctx.set_operation("query_tax")
                    data = {
                        'tax': 'ibx',
                        'idn': pid,
                        'bornYr': birthyear_tw,
                        'inputCode': code
                    }
                    post_url = 'https://svc.tax.nat.gov.tw/svc/servletirxwresult'

                    start_time = time.time()
                    logger.log_request("POST", post_url, None, data)

                    response = session.post(post_url, data=data, verify=False, timeout=30)
                    elapsed = time.time() - start_time

                    logger.log_response(response.status_code, dict(response.headers), response.text[:200] if len(response.text) > 200 else response.text, elapsed)

                    # Step 3：如查詢成功，取得結果頁
                    if response.status_code == 200 and '"code":0' in response.text:
                        logger.info("驗證成功，前往結果頁...")

                        headers = {
                            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "referer": "https://svc.tax.nat.gov.tw/svc/IbxPaidQuery.jsp",
                            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        }

                        result_url = 'https://svc.tax.nat.gov.tw/svc/IrxIbxResultForPc.jsp'

                        logger.ctx.set_operation("get_result")
                        start_time = time.time()
                        logger.log_request("GET", result_url, headers, None)

                        result_response = session.get(result_url, headers=headers, verify=False, timeout=30)
                        elapsed = time.time() - start_time

                        logger.log_response(result_response.status_code, dict(result_response.headers), f"[HTML: {len(result_response.text)} chars]", elapsed)

                        soup = BeautifulSoup(result_response.text, 'html.parser')

                        # 擷取欄位
                        def get_text(label):
                            tag = soup.find('label', string=label)
                            return tag.find_next_sibling(text=True).strip() if tag else ''

                        INQCode = get_text('檔案編號：')
                        Taxreturnchannel = get_text('申報方式：')
                        Taxreturntplat = get_text('申報平台：')
                        taxOffice = get_text('稽徵機關名稱：')
                        taxOfficeAddr = get_text('稽徵機關地址：')
                        taxOfficePhone = get_text('稽徵機關電話：')
                        taxreturndate = get_text('首次申報日期：')

                    else:
                        logger.warning(f"查詢失敗: {response.text[:200]}")
                        soup = None

                    # 解析結果
                    logger.ctx.set_operation("parse_result")
                    status = 'done'
                    info = ''
                    INQCode = ''
                    Taxreturnchannel = ''
                    Taxreturnplat = ''
                    taxreturndate = ''
                    taxOffice = ''
                    taxOfficeAddr = ''
                    taxOfficePhone = ''

                    try:
                        if soup and soup.find('fieldset'):
                            fieldset = soup.find('fieldset')
                            p_tag = fieldset.find('p')

                            if p_tag and ('您已完成' in p_tag.text or '稅額試算通知書檔案編號' in p_tag.text):
                                info = p_tag.text
                                output = []
                                for t in fieldset.find_all('p'):
                                    output.append(t.text.replace('\n', '').replace('\t', '').replace('\xa0', ''))

                                for v in output:
                                    if '稅額試算通知書檔案編號' in v or '檔案編號' in v:
                                        INQCode = v.replace('稅額試算通知書檔案編號', '').replace('檔案編號', '').replace('： ', '')
                                    if '申報方式' in v:
                                        Taxreturnchannel = v.replace('申報方式', '').replace('： ', '')
                                    if '申報平台' in v:
                                        Taxreturnplat = v.replace('申報平台', '').replace('： ', '')
                                    if '首次申報日期' in v:
                                        taxreturndate = v.replace('首次申報日期', '').replace('： ', '')
                                    if '完成申報時間' in v:
                                        taxreturndate = v.replace('完成申報時間', '').replace('： ', '')
                                    if '稽徵機關名稱' in v:
                                        taxOffice = v.replace('稽徵機關名稱', '').replace('： ', '')
                                    if '稽徵機關地址' in v:
                                        taxOfficeAddr = v.replace('稽徵機關地址', '').replace('： ', '')
                                    if '稽徵機關電話' in v:
                                        taxOfficePhone = v.replace('稽徵機關電話', '').replace('： ', '')
                                    if '查詢電話' in v:
                                        taxOfficePhone = v[v.find('查詢電話:') + len('查詢電話:'):]
                                        taxOffice = v[:v.find('查詢電話')]
                            else:
                                info = p_tag.text if p_tag else ''

                    except Exception as parse_err:
                        logger.debug(f"第一次解析失敗，嘗試備用解析: {parse_err}")
                        try:
                            if soup and len(soup.find_all('fieldset')) > 1:
                                fieldset = soup.find_all('fieldset')[1]
                                p_tag = fieldset.find('p')

                                if p_tag and ('您已完成' in p_tag.text or '稅額試算通知書檔案編號' in p_tag.text):
                                    info = p_tag.text
                                    output = []
                                    for t in fieldset.find_all('p'):
                                        output.append(t.text.replace('\n', '').replace('\t', '').replace('\xa0', ''))

                                    for v in output:
                                        if '稅額試算通知書檔案編號' in v or '檔案編號' in v:
                                            INQCode = v.replace('稅額試算通知書檔案編號', '').replace('檔案編號', '').replace('： ', '')
                                        if '申報方式' in v:
                                            Taxreturnchannel = v.replace('申報方式', '').replace('： ', '')
                                        if '申報平台' in v:
                                            Taxreturnplat = v.replace('申報平台', '').replace('： ', '')
                                        if '首次申報日期' in v:
                                            taxreturndate = v.replace('首次申報日期', '').replace('： ', '')
                                        if '完成申報時間' in v:
                                            taxreturndate = v.replace('完成申報時間', '').replace('： ', '')
                                        if '稽徵機關名稱' in v:
                                            taxOffice = v.replace('稽徵機關名稱', '').replace('： ', '')
                                        if '稽徵機關地址' in v:
                                            taxOfficeAddr = v.replace('稽徵機關地址', '').replace('： ', '')
                                        if '稽徵機關電話' in v:
                                            taxOfficePhone = v.replace('稽徵機關電話', '').replace('： ', '')
                                        if '查詢電話' in v:
                                            taxOfficePhone = v[v.find('查詢電話:') + len('查詢電話:'):]
                                            taxOffice = v[:v.find('查詢電話')]
                                else:
                                    info = p_tag.text if p_tag else ''
                        except Exception as e2:
                            logger.warning(f"備用解析也失敗: {e2}")

                    # 更新資料庫
                    logger.ctx.set_operation("DB_update")
                    logger.ctx.set_db(server=server, database=database, table=totb, operation="UPDATE")

                    updatesql(server, username, password, database, status, info, INQCode, Taxreturnchannel,
                              Taxreturnplat, taxreturndate, taxOffice, taxOfficeAddr, taxOfficePhone,
                              entitytype, psid, pid, insertdate)

                    logger.log_db_operation("UPDATE", database, totb, 1)
                    logger.info(f"更新完成: psid={psid}, INQCode={INQCode}")
                    logger.increment('records_success')

                except Exception as e:
                    logger.log_exception(e, f"處理記錄時發生錯誤")
                    logger.increment('records_failed')
                    time.sleep(2)
                    continue

            # 完成一輪後重新檢查
            break

        logger.log_stats({
            'total_processed': total_records,
        })

        logger.task_end(success=True)
        return True

    except Exception as e:
        logger.log_exception(e, "執行過程發生錯誤")
        logger.task_end(success=False)
        return False


def main():
    """Main entry point"""
    logger.info(f"資料庫: {db['server']}.{db['database']}")
    logger.info(f"目標資料表: {db['totb']}")

    try:
        success = run()
        if success:
            logger.info("執行完成")
        else:
            logger.warning("執行失敗")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == "__main__":
    main()
