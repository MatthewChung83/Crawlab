# -*- coding: utf-8 -*-
"""
TaxRefund crawler - Tax refund query using Playwright
"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import ddddocr
from datetime import datetime as dt

from config import *
from etl_func import *

# Parameters
server, database, username, password = db['server'], db['database'], db['username'], db['password']
src_tb, tar_tb = db['src_tb'], db['tar_tb']
url = wbinfo['url']
imgp = pics['imgp']


def run_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)

        # Wait for main input field to be available
        try:
            page.wait_for_selector("#userIdnBan", timeout=10000)
        except PlaywrightTimeoutError:
            print("主要輸入框未出現，頁面加載可能有問題")
            browser.close()
            return

        src = fromsql(server, username, password, database, src_tb)

        for record, attempt in retry_generator(src):
            psid = record['psid']
            pid = record['pid']
            print(f"處理 psid={psid}, pid={pid}, 嘗試第 {attempt+1} 次")
            try:
                # Input ID number, clear field first
                page.fill('#userIdnBan', '')
                page.fill('#userIdnBan', pid)

                # Wait for captcha image (10s timeout)
                captcha_element = page.wait_for_selector('etw-captcha img', timeout=10000)

                # Screenshot captcha
                img_bytes = captcha_element.screenshot()
                with open(imgp, 'wb') as f:
                    f.write(img_bytes)

                # OCR recognition
                ocr = ddddocr.DdddOcr()
                res = ocr.classification(img_bytes)
                print(f"OCR 輸出: {res}")

                # Fill captcha
                page.fill('#captchaText', res)

                # Click query button
                page.click('form#queryForm button[type="button"]')

                # Wait for result area (max 15s)
                page.wait_for_selector('#resultArea div table tbody tr td', timeout=15000)

                # Handle possible popup
                try:
                    confirm_btn = page.query_selector('ngb-modal-window div.jhi-dialog div button')
                    if confirm_btn:
                        print("發現錯誤彈窗，點擊確定並重試...")
                        confirm_btn.click()
                        page.reload()
                        continue
                except Exception:
                    pass

                # Get result text
                info = page.inner_text('#resultArea div table tbody tr td').replace('\n', '')

                insertdate = dt.today().strftime("%Y/%m/%d %H:%M:%S")
                updatesql(server, username, password, database, tar_tb, info, psid, pid)
                print(f"資料更新完成 psid={psid}, pid={pid} : {info} 時間：{insertdate}")

                page.reload()

            except PlaywrightTimeoutError as e:
                print(f"等待超時，重試 psid={psid}, pid={pid}: {e}")
                page.reload()
                continue

            except Exception as e:
                print(f"未知錯誤 psid={psid}, pid={pid}: {e}")
                page.reload()
                continue

        browser.close()


if __name__ == "__main__":
    run_playwright()
