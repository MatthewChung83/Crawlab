# -*- coding: utf-8 -*-
"""
TaxRefund crawler - Tax refund query using Playwright
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import ddddocr
from datetime import datetime as dt

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import *
from common.logger import get_logger

# Initialize logger
logger = get_logger('Data-TaxRefund')

# Parameters
server, database, username, password = db['server'], db['database'], db['username'], db['password']
src_tb, tar_tb = db['src_tb'], db['tar_tb']
url = wbinfo['url']
imgp = pics['imgp']


def run_playwright():
    """Main Playwright execution function"""
    logger.task_start("稅務退稅查詢")
    logger.log_db_connect(server, database, username)
    logger.info(f"目標網址: {url}")

    total_processed = 0
    total_success = 0
    total_failed = 0

    try:
        with sync_playwright() as p:
            logger.info("啟動 Chromium 瀏覽器 (headless)")
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            logger.ctx.set_operation("navigate")
            start_time = time.time()
            page.goto(url)
            elapsed = time.time() - start_time
            logger.info(f"頁面載入完成 ({elapsed:.2f}s)")

            # Wait for main input field to be available
            try:
                page.wait_for_selector("#userIdnBan", timeout=10000)
                logger.debug("主要輸入框已就緒")
            except PlaywrightTimeoutError:
                logger.error("主要輸入框未出現，頁面加載可能有問題")
                browser.close()
                logger.task_end(success=False)
                return False

            src = fromsql(server, username, password, database, src_tb)
            total_records = len(src) if hasattr(src, '__len__') else 0
            logger.info(f"待處理筆數: {total_records}")

            for record, attempt in retry_generator(src):
                psid = record['psid']
                pid = record['pid']
                total_processed += 1

                logger.log_progress(total_processed, total_records, f"psid={psid}")
                logger.ctx.set_data(psid=psid, pid=pid)
                logger.debug(f"處理: psid={psid}, pid={pid}, 嘗試第 {attempt+1} 次")

                try:
                    # Input ID number, clear field first
                    logger.ctx.set_operation("input_id")
                    page.fill('#userIdnBan', '')
                    page.fill('#userIdnBan', pid)

                    # Wait for captcha image (10s timeout)
                    logger.ctx.set_operation("get_captcha")
                    start_time = time.time()
                    captcha_element = page.wait_for_selector('etw-captcha img', timeout=10000)
                    elapsed = time.time() - start_time
                    logger.debug(f"驗證碼圖片載入 ({elapsed:.2f}s)")

                    # Screenshot captcha
                    img_bytes = captcha_element.screenshot()
                    with open(imgp, 'wb') as f:
                        f.write(img_bytes)

                    # OCR recognition
                    logger.ctx.set_operation("ocr_captcha")
                    ocr = ddddocr.DdddOcr(show_ad=False)
                    res = ocr.classification(img_bytes)
                    logger.log_captcha_attempt(attempt + 1, True, res)

                    # Fill captcha
                    page.fill('#captchaText', res)

                    # Click query button
                    logger.ctx.set_operation("submit_query")
                    start_time = time.time()
                    page.click('form#queryForm button[type="button"]')

                    # Wait for result area (max 15s)
                    page.wait_for_selector('#resultArea div table tbody tr td', timeout=15000)
                    elapsed = time.time() - start_time
                    logger.debug(f"查詢完成 ({elapsed:.2f}s)")

                    # Handle possible popup
                    try:
                        confirm_btn = page.query_selector('ngb-modal-window div.jhi-dialog div button')
                        if confirm_btn:
                            logger.warning("發現錯誤彈窗，點擊確定並重試...")
                            confirm_btn.click()
                            page.reload()
                            continue
                    except Exception:
                        pass

                    # Get result text
                    logger.ctx.set_operation("parse_result")
                    info = page.inner_text('#resultArea div table tbody tr td').replace('\n', '')
                    logger.debug(f"查詢結果: {info[:100]}..." if len(info) > 100 else f"查詢結果: {info}")

                    insertdate = dt.today().strftime("%Y/%m/%d %H:%M:%S")

                    # Update database
                    logger.ctx.set_operation("DB_update")
                    logger.ctx.set_db(server=server, database=database, table=tar_tb, operation="UPDATE")

                    updatesql(server, username, password, database, tar_tb, info, psid, pid)
                    logger.log_db_operation("UPDATE", database, tar_tb, 1)
                    logger.info(f"資料更新完成 psid={psid}, pid={pid}")

                    total_success += 1
                    logger.increment('records_success')

                    page.reload()

                except PlaywrightTimeoutError as e:
                    logger.warning(f"等待超時 psid={psid}, pid={pid}: {e}")
                    total_failed += 1
                    logger.increment('records_failed')
                    page.reload()
                    continue

                except Exception as e:
                    logger.log_exception(e, f"處理記錄時發生錯誤 psid={psid}, pid={pid}")
                    total_failed += 1
                    logger.increment('records_failed')
                    page.reload()
                    continue

            browser.close()
            logger.info("瀏覽器已關閉")

        logger.log_stats({
            'total_records': total_records,
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
    logger.info(f"來源資料表: {src_tb}")
    logger.info(f"目標資料表: {tar_tb}")

    try:
        success = run_playwright()
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
