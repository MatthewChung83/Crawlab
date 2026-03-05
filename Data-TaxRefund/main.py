from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import ddddocr
import io
import pymssql
from datetime import datetime as dt
import time

imgp = r'./captcha_01.jpg'

def fromsql(host, user, password, database, src_tb):
    conn = pymssql.connect(host=host, user=user, password=password, database=database)
    cursor = conn.cursor(as_dict=True)
    script = f"""select * from {src_tb} where info is null and type = 'ONHAND-20240801_01' order by pid"""
    cursor.execute(script)
    sql_src = cursor.fetchall()
    cursor.close()
    conn.close()
    return sql_src

def updatesql(host, user, password, database, tar_tb, info, psid, pid):
    conn = pymssql.connect(host=host, user=user, password=password, database=database)
    cursor = conn.cursor(as_dict=True)
    script = f"""update {tar_tb} set info = '{info}' where psid = {psid} and pid = '{pid}'"""
    print(script)
    cursor.execute(script)
    conn.commit()
    cursor.close()
    conn.close()

def retry_generator(data_list):
    """
    產生器，依序提供 data，並且在需要重試時重複提供相同資料(最大重試5次)
    """
    max_retry = 5
    for record in data_list:
        retries = 0
        while retries < max_retry:
            yield record, retries
            retries += 1

def run_playwright():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        Url = 'https://www.etax.nat.gov.tw/etwmain/etw133w1/e01'
        page.goto(Url)
        # 等待關鍵輸入框可用，避免過早操作
        try:
            page.wait_for_selector("#userIdnBan", timeout=10000)
        except PlaywrightTimeoutError:
            print("主要輸入框未出現，頁面加載可能有問題")
            browser.close()
            return
        
        src = fromsql('10.10.0.94', 'CLUSER', 'Ucredit7607', 'CL_Daily', 'taxrefundtb')

        for record, attempt in retry_generator(src):
            psid = record['psid']
            pid = record['pid']
            print(f"處理 psid={psid}, pid={pid}, 嘗試第 {attempt+1} 次")
            try:
                # 輸入身分證字號，先清空欄位
                page.fill('#userIdnBan', '')
                page.fill('#userIdnBan', pid)
                
                # 等待驗證碼圖片出現 (10秒timeout)
                captcha_element = page.wait_for_selector('etw-captcha img', timeout=10000)
                
                # 截圖驗證碼
                img_bytes = captcha_element.screenshot()
                with open(imgp, 'wb') as f:
                    f.write(img_bytes)
                
                # OCR 辨識
                ocr = ddddocr.DdddOcr()
                res = ocr.classification(img_bytes)
                print(f"OCR 輸出: {res}")
                
                # 填入驗證碼
                page.fill('#captchaText', res)
                
                # 點擊查詢按鈕（根據網頁調整 Selector）
                page.click('form#queryForm button[type="button"]')
                
                # 等待結果區塊顯示（避免硬等待，最多15秒）
                page.wait_for_selector('#resultArea div table tbody tr td', timeout=15000)
                
                # 處理可能彈窗訊息
                try:
                    confirm_btn = page.query_selector('ngb-modal-window div.jhi-dialog div button')
                    if confirm_btn:
                        print("發現錯誤彈窗，點擊確定並重試...")
                        confirm_btn.click()
                        page.reload()
                        # 這筆會在 retry_generator 再重試
                        continue
                except Exception:
                    # 無彈窗跳過
                    pass
                
                # 擷取結果文字
                info = page.inner_text('#resultArea div table tbody tr td').replace('\n', '')
                
                insertdate = dt.today().strftime("%Y/%m/%d %H:%M:%S")
                updatesql('10.10.0.94', 'CLUSER', 'Ucredit7607', 'CL_Daily', 'taxrefundtb', info, psid, pid)
                print(f"資料更新完成 psid={psid}, pid={pid} : {info} 時間：{insertdate}")
                
                page.reload()  # 下一筆前刷新頁面

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
