"""
Legal Insurance Automation - Final Version
使用已驗證的 crr901w/verify 和 crr201w/payment API + 資料庫整合
"""
import requests
import urllib3

# 抑制 SSL 警告 (因為 insurtech.lia-roc.org.tw 憑證有問題)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import imaplib
import email
import re
import time
import datetime
import json
import os
import base64
import socket
import io
from smb.SMBConnection import SMBConnection
from playwright.sync_api import sync_playwright
from config import db, vars
from etl_func import src_obs, dbfrom, update, foo

# SMB 配置
SMB_CONFIG = {
    'server_ip': '10.10.0.93',
    'service_name': 'UCS',
    'username': 'sqlsvc',
    'password': 'Sq1@dmin',
    'domain': 'ucs',
    'base_path': 'AM/LEGAL/@@@@@保險公會費用及發票/image/'
}

# 個資同意書 HTML
AGREEMENT_HTML = """
<div style="text-align: start">
<p><strong>蒐集之目的：</strong></p>

<ul>
  <li>人身保險（001）。</li>
  <li>法院執行業務（055）。</li>
  <li>爭議事件處理（060）。</li>
  <li>金融監督、管理與檢查（061）。</li>
  <li>履行法定義務所進行個人資料之蒐集、處理及利用（063）。</li>
  <li>契約、類似契約或其他法律關係事務（069）。</li>
  <li>資（通）訊與資料庫管理（136）。</li>
  <li>資通安全與管理（137）。</li>
  <li>其他公務機關對目的事業之監督管理（173）。</li>
  <li>其他經營合於營業登記項目或組織章程所訂之業務（181）。</li>
  <li>其他諮詢與顧問服務（182）。</li>
  <li>其他法令許可之事由或目的。</li>
</ul>

<p><strong>蒐集之個人資料類別：</strong></p>

<ul>
  <li>識別個人類【如姓名、手機門號裝置、聯絡方式、聯絡地址、電子郵件（E-mail）、供網路身分認證及申辦查詢服務之紀錄等】。</li>
  <li>政府資料中之辨識類【如身分證統一編號等】。</li>
  <li>個人描述類【如年齡、性別、出生年月日、出生地、國籍、聲音等】。</li>
</ul>

<p><strong>三、 個人資料來源：</strong></p>

<ul>
  <li>本會向　台端直接蒐集。</li>
  <li>台端自行公開或其他已合法公開。</li>
  <li>本會向第三人【如：法院、保險公司、台端之法定代理人或輔助人、本會合作夥伴(如:電信公司、設備廠商)…等】蒐集。本會向第三人蒐集資料時，可能將您的電子郵件地址(E-mail)、電話號碼、行動裝置識別碼、網際網路通訊協定(IP)位址、CookieID…等資料提供予第三人，做為資料串接識別之工具。</li>
</ul>

<p><strong>四、 個人資料利用之期間、對象、地區、方式：</strong></p>

<ol>
  <li>期間：個人資料蒐集之特定目的存續期間、依相關法令規定或契約約定之保存期間或本會因執行職務或業務所必須之保存期間。</li>
  <li>對象：本會、與本會因業務需要訂有契約關係或業務往來之機構或顾問、本會受託機構及依法有調查權機關或金融監理機關。</li>
  <li>地區：中華民國境內及依法令所為之國際傳輸。</li>
  <li>方式：符合個人資料保護相關法令以自動化機器或其他非自動化之利用方式。</li>
</ol>

<p><strong>五、 當事人得行使之權利及方式：</strong></p>

<p>依據個資法第三條規定，台端就本會保有　台端之個人資料得以書面方式，行使下列權利：</p>

<ol>
  <li>除有個資法第十條所規定之例外情形外，得向本會查詢、請求閱覽或請求製給複製本，惟本會依同法第十四條規定得酌收必要成本費用。</li>
  <li>得向本會請求補充或更正，惟依個資法施行細則第十九條規定，台端應適當釋明其原因及事實。</li>
  <li>本會如有違反個資法規定蒐集、處理或利用　台端之個人資料，依個資法第十一條第四項規定，台端得向本會請求停止蒐集。</li>
  <li>依個資法第十一條第二項規定，個人資料正確性有爭議者，得向本會請求停止處理或利用台端之個人資料。惟依該項但書規定，本會因執行業務所必須並 註明其爭議或經 台端書面同意者，不在此限。</li>
  <li>依個資法第十一條第三項規定，個人資料蒐集之特定目的消失或期限屆滿時，得向本會請求刪除、停止處理或利用 台端之個人資料。惟依該項但書規定，本會因執行業務所必須或經 台端書面同意者，不在此限。</li>
</ol>

<p><strong>六、 當事人拒絕提供個人資料所致權益之影響：</strong></p>

<p>台端得自由選擇是否提供個人資料，惟　台端若拒絕提供相關個人資料，本會將無法進行必要之審核及處理相關作業，致無法受理　台端前揭權利之行使或提供　台端相關服務。</p>

<p><strong>七、 申訴管道：</strong></p>

<p>本會服務電話：（02）2561-2144</p>
</div>
"""


def send_otp_email(email_addr):
    """發送OTP驗證碼到指定郵箱"""
    url = "https://insurtech.lia-roc.org.tw/lia-creditor-record-server/api/otp/send"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'text/plain',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        'X-Requested-With': 'XMLHttpRequest'
    }

    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            response = requests.post(url, data=email_addr, headers=headers, verify=False)

            if response.status_code == 200:
                print("✅ OTP 發送成功")
                return True

            if response.status_code == 400:
                try:
                    error_data = response.json()
                    if "驗證碼時效未到" in error_data.get("title", ""):
                        retry_count += 1
                        if retry_count < max_retries:
                            print(f"⚠️ 驗證碼時效未到，等待 60 秒... (第 {retry_count}/{max_retries} 次)")
                            for i in range(60, 0, -10):
                                print(f"   還剩 {i} 秒...")
                                time.sleep(10)
                            continue
                        else:
                            print(f"❌ 已達最大重試次數，放棄發送")
                            return False
                except:
                    pass

            print(f"❌ OTP 發送失敗，狀態碼: {response.status_code}")
            return False

        except Exception as e:
            print(f"❌ 發送 OTP 錯誤: {e}")
            return False

    return False


def get_verification_code_from_email(email_addr, email_password, max_retries=10):
    """從Gmail抓取驗證碼"""
    verification_code = ''
    retry_count = 0

    while len(verification_code) == 0 and retry_count < max_retries:
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.sock.settimeout(30)
            mail.login(email_addr, email_password)
            mail.select('inbox')

            status, messages = mail.search(None, '(UNSEEN)')
            if status != 'OK' or not messages[0]:
                status, messages = mail.search(None, 'ALL')

            if status == 'OK' and messages[0]:
                latest_email_id = messages[0].split()[-1]
                status, data = mail.fetch(latest_email_id, '(RFC822)')

                if status == 'OK':
                    msg = email.message_from_bytes(data[0][1])
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() in ["text/plain", "text/html"]:
                                try:
                                    message = part.get_payload(decode=True).decode()
                                    match = re.search(r'驗證碼為[^\d]*(\d{6})', message)
                                    if match:
                                        verification_code = match.group(1)
                                        print(f'✅ 找到驗證碼: {verification_code}')
                                        break
                                except:
                                    continue
                    else:
                        try:
                            message = msg.get_payload(decode=True).decode()
                            match = re.search(r'驗證碼為[^\d]*(\d{6})', message)
                            if match:
                                verification_code = match.group(1)
                                print(f'✅ 找到驗證碼: {verification_code}')
                        except:
                            pass

            mail.logout()

            if len(verification_code) == 0:
                retry_count += 1
                print(f"驗證碼未找到，重試 {retry_count}/{max_retries}")
                time.sleep(3)

        except Exception as e:
            print(f"郵件檢查錯誤: {e}")
            retry_count += 1
            time.sleep(3)

    return verification_code


def verify_and_submit_case(verify_code, email, name, phone, debtor_ids, legal_num, legal_court):
    """驗證OTP並提交案件資料 (使用 crr901w/verify API)"""
    url = "https://insurtech.lia-roc.org.tw/lia-creditor-record-server/api/crr901w/verify"

    try:
        verify_code_int = int(verify_code)
        print(f"✅ 驗證碼轉換成功: {verify_code_int}")
    except (ValueError, TypeError):
        print(f"❌ 驗證碼格式錯誤: {verify_code}")
        return None

    # 將身分證字串轉為陣列
    query_id_list = [id.strip() for id in debtor_ids.split(',')]

    payload = {
        "queryId": query_id_list,
        "contactName": name,
        "contactPersonPhone": phone,
        "contactEmail": email,
        "verifyCode": verify_code_int,
        "issueNo": legal_num,
        "dispatchOrg": legal_court,
        "agreementStatment": "on",
        "agreement": AGREEMENT_HTML
    }

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
        'X-Requested-With': 'XMLHttpRequest'
    }

    print(f"\n發送驗證請求到 crr901w/verify")
    print(f"  身分證: {query_id_list}")
    print(f"  案號: {legal_num}")
    print(f"  公文來源: {legal_court}")

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30, verify=False)

        print(f"回應狀態碼: {response.status_code}")

        # 提取 Token
        token = None
        auth_header = response.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.replace('Bearer ', '')
            print(f"✅ 提取到 Token: {token[:20]}...")

        # 解析 JSON
        data = json.loads(response.text)
        case_uid = data.get("caseUid")
        status_code = data.get("statusCode")

        # 檢查錯誤狀態
        if status_code == "EMAIL_VERIFY_FAIL":
            print(f"❌ 郵箱驗證失敗 (EMAIL_VERIFY_FAIL)")
            return None

        if status_code == "INSURANCE_PARTIES_ABNORMALITY":
            print(f"❌ 保險當事人異常 (INSURANCE_PARTIES_ABNORMALITY)")
            return {"error": "INSURANCE_PARTIES_ABNORMALITY"}

        if status_code == "VERIFY_FAIL":
            print(f"❌ 驗證失敗 (VERIFY_FAIL)")
            return {"error": "VERIFY_FAIL"}

        if status_code == "ISSUE_NO_INVALID":
            print(f"❌ 案號無效 (ISSUE_NO_INVALID)")
            return {"error": "ISSUE_NO_INVALID"}

        if response.status_code == 200 and case_uid:
            print(f"✅ 驗證成功，取得 caseUid: {case_uid}")
            return {"token": token, "caseUid": case_uid}
        else:
            print(f"❌ 驗證失敗")
            print(f"回應: {response.text}")
            return None

    except Exception as e:
        print(f"❌ 驗證 API 錯誤: {e}")
        return None


def submit_payment_request(token, case_uuid, name, phone, email, compiled, company, address, debtor_count):
    """提交付款請求 (使用 crr201w/payment API)"""
    url = "https://insurtech.lia-roc.org.tw/lia-creditor-record-server/api/crr201w/payment"

    payload = {
        "caseUuid": case_uuid,
        "contactPerson": name,
        "contactPersonPhone": phone,
        "contactPersonEmail": email,
        "invoiceType": "1",
        "taxIdNumber": compiled,
        "companyName": company,
        "companyAddress": address,
        "paymentType": "ATM",
        "num": debtor_count
    }

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Authorization': f'Bearer {token}'
    }

    print(f"\n提交付款請求到 crr201w/payment")
    print(f"  caseUuid: {case_uuid}")

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30, verify=False)

        print(f"回應狀態碼: {response.status_code}")

        if response.status_code == 200:
            json_response = response.json()

            if json_response.get("code") == "0":
                data = json_response.get("data", {})
                html_form = data.get("htmlForm", "")

                # 解析表單欄位
                form_fields = {}
                if html_form:
                    pattern = r'<input type="hidden" name="([^"]+)" value="([^"]*)" />'
                    matches = re.findall(pattern, html_form)
                    for name, value in matches:
                        form_fields[name] = value

                print("✅ 付款請求成功")
                return {
                    "code": json_response.get("code"),
                    "msg": json_response.get("msg"),
                    "htmlForm": html_form,
                    "formFields": form_fields,
                    "bankCode": data.get("bankCode"),
                    "account": data.get("account"),
                    "payMoney": data.get("payMoney"),
                    "atmExit": data.get("atmExit")
                }
            else:
                msg = json_response.get("msg", "")
                print(f"⚠️ {msg}")
                # 檢查是否為債務人數量比對失敗
                if "債務人數量比對失敗" in msg or "債務人比對失敗" in msg:
                    return {"msg": msg, "error": "DEBTOR_COUNT_MISMATCH"}
                return {"msg": msg}

        print(f"❌ 付款請求失敗")
        return None

    except Exception as e:
        print(f"❌ 付款 API 錯誤: {e}")
        return None


def process_ecpay_with_playwright(payment_data, case_id, file_date):
    """使用 Playwright 處理綠界金流 (步驟 5、6、7 合併)"""
    if not payment_data or not payment_data.get('formFields'):
        print("❌ 沒有表單資料")
        return None

    form_fields = payment_data['formFields']

    try:
        print("🌐 啟動 Playwright 瀏覽器...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # 步驟 5: 建立 HTML 表單並提交到綠界 V5
            print("📝 建立表單並提交到綠界...")
            form_html = '<html><body><form id="ecpay_form" method="post" action="https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5">'
            for key, value in form_fields.items():
                escaped_value = str(value).replace('"', '&quot;')
                form_html += f'<input type="hidden" name="{key}" value="{escaped_value}" />'
            form_html += '</form><script>document.getElementById("ecpay_form").submit();</script></body></html>'

            # 載入表單並等待頁面載入
            page.set_content(form_html)
            page.wait_for_load_state('networkidle', timeout=30000)

            # 確認是否成功進入付款頁面
            if '選擇支付方式' in page.title() or '綠界科技' in page.title():
                print("✅ 成功進入綠界付款頁面")
            else:
                print(f"⚠️ 頁面標題: {page.title()}")

            # 步驟 6: 選擇 ATM 付款方式
            print("🏧 選擇 ATM 付款方式...")

            # 等待 ATM 選項出現並點擊
            try:
                atm_tab = page.locator('#liATM')
                atm_tab.wait_for(state='visible', timeout=10000)
                atm_tab.click()
                print("✅ 已點擊 ATM 選項")
                time.sleep(2)  # 等待 UI 更新
            except Exception as e:
                print(f"⚠️ 點擊 ATM 選項失敗: {e}")

            # 選擇銀行 - 使用下拉選單的 value 值
            # 銀行 PaymentID 對應:
            # 10002@8@ATM_CHINATRUST = 中國信託 (822)
            # 10002@5@ATM_BOT = 台灣銀行 (004)
            # 10002@11@ATM_LAND = 台灣土地銀行 (005)
            # 10002@7@ATM_FIRST = 第一銀行 (007)
            # 10002@9@ATM_CATHAY = 國泰世華銀行 (013)
            # 10002@17@ATM_PANHSIN = 板信銀行 (118)
            BANK_PAYMENT_ID = '10002@8@ATM_CHINATRUST'  # 可在此修改銀行

            try:
                # 等待頁面穩定
                time.sleep(1)

                # 使用 select_option 選擇銀行 (下拉選單)
                select_element = page.locator('select').first
                select_element.select_option(value=BANK_PAYMENT_ID)
                print(f"✅ 已從下拉選單選擇銀行: 中國信託 (822)")
                time.sleep(1)

            except Exception as e:
                print(f"⚠️ 選擇銀行時發生問題: {e}")

            # 點擊取得繳費帳號按鈕
            try:
                submit_btn = page.locator('text=取得繳費帳號')
                if submit_btn.count() > 0:
                    submit_btn.first.click()
                    print("✅ 已點擊取得繳費帳號")
                else:
                    # 嘗試其他可能的按鈕
                    submit_btn = page.locator('.btn:has-text("取得")')
                    if submit_btn.count() > 0:
                        submit_btn.first.click()
                        print("✅ 已點擊確認按鈕")
            except Exception as e:
                print(f"⚠️ 點擊提交按鈕失敗: {e}")

            # 步驟 7: 等待 ATM 資訊頁面
            print("⏳ 等待 ATM 付款資訊頁面...")
            try:
                page.wait_for_load_state('networkidle', timeout=30000)
                time.sleep(2)  # 額外等待

                # 取得頁面內容
                html_content = page.content()

                # 檢查是否有 ATM 資訊
                if '銀行代碼' in html_content or '虛擬帳號' in html_content or 'ATM繳費帳號' in html_content:
                    print("✅ 成功取得 ATM 付款資訊")

                    # 提取 ATM 資訊 (根據綠界 ATM 結果頁面結構)
                    atm_info = {}

                    # 訂單編號 - 在 <dt>訂單編號</dt><dd> 後面
                    order_match = re.search(r'<dt>訂單編號</dt>\s*<dd>\s*([A-Za-z0-9]+)', html_content)
                    if order_match:
                        atm_info['MerchantTradeNo'] = order_match.group(1).strip()

                    # 銀行代碼 - 格式: 銀行代碼 822
                    bank_code_match = re.search(r'銀行代碼\s*(\d{3})', html_content)
                    if bank_code_match:
                        atm_info['BankCode'] = bank_code_match.group(1)

                    # 虛擬帳號 - 在 <span class="oif-hl"> 內，格式: 9251 2603 8942 8709
                    account_match = re.search(r'<span class="oif-hl">([0-9\s]+)</span>', html_content)
                    if account_match:
                        atm_info['vAccount'] = account_match.group(1).replace(' ', '').strip()

                    # 應付金額 - 格式: NT$ 350
                    amount_match = re.search(r'<dd class="o-other-total">NT\$\s*(\d+)</dd>', html_content)
                    if amount_match:
                        atm_info['TradeAmount'] = amount_match.group(1)

                    # 繳費截止時間 - 在 <dt>繳費截止時間</dt><dd> 後面
                    expire_match = re.search(r'<dt>繳費截止時間</dt>\s*<dd[^>]*>([^<]+)</dd>', html_content)
                    if expire_match:
                        atm_info['ExpireDate'] = expire_match.group(1).strip()

                    # 商品名稱 - 在商品清單區塊的 <dd class="o-pd-name"> 內 (跳過標題的「商品明細」)
                    item_match = re.search(r'<!-- 商品清單 start -->.*?<dd class="o-pd-name">\s*\n?([^<]+?)(?:<br|</dd>)', html_content, re.DOTALL)
                    if item_match:
                        atm_info['ItemName'] = item_match.group(1).strip()

                    print(f"📋 提取到的 ATM 資訊: {atm_info}")

                    # 儲存 HTML
                    temp_dir = f'./temp_{file_date}'
                    os.makedirs(temp_dir, exist_ok=True)

                    html_filename = f'{case_id}.html'
                    html_filepath = os.path.join(temp_dir, html_filename)

                    # 使用原始頁面建立可列印 HTML
                    printable_html = create_printable_html_from_response(html_content)

                    with open(html_filepath, 'w', encoding='utf-8') as f:
                        f.write(printable_html)
                    print(f"✅ 儲存暫存HTML: {html_filepath}")

                    # 使用 Playwright 直接生成 PDF
                    pdf_filename = f'{case_id}.pdf'
                    pdf_filepath = os.path.join(temp_dir, pdf_filename)

                    try:
                        page.pdf(
                            path=pdf_filepath,
                            format='A4',
                            print_background=True,
                            margin={'top': '0.5cm', 'right': '0.5cm', 'bottom': '0.5cm', 'left': '0.5cm'}
                        )
                        print(f"✅ 儲存暫存PDF: {pdf_filepath}")
                        pdf_created = True
                    except Exception as e:
                        print(f"⚠️ PDF 生成失敗: {e}")
                        pdf_created = False

                    browser.close()

                    # 上傳到 SMB
                    smb_pdf_path = None
                    if pdf_created:
                        smb_pdf_path = upload_to_smb(pdf_filepath, pdf_filename, file_date)
                        if smb_pdf_path:
                            atm_info['saved_pdf'] = smb_pdf_path
                        else:
                            atm_info['saved_pdf'] = pdf_filepath

                    smb_html_path = upload_to_smb(html_filepath, html_filename, file_date)
                    if smb_html_path:
                        atm_info['saved_html'] = smb_html_path
                    else:
                        atm_info['saved_html'] = html_filepath

                    # 清理暫存檔案
                    try:
                        if os.path.exists(html_filepath):
                            os.remove(html_filepath)
                        if os.path.exists(pdf_filepath):
                            os.remove(pdf_filepath)
                        if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                            os.rmdir(temp_dir)
                        print("✅ 已清理暫存檔案")
                    except Exception as e:
                        print(f"⚠️ 清理暫存檔案失敗: {e}")

                    return atm_info

                else:
                    print(f"❌ 未找到 ATM 資訊")

            except Exception as e:
                print(f"❌ 等待 ATM 頁面失敗: {e}")

            browser.close()

    except Exception as e:
        print(f"❌ Playwright 處理錯誤: {e}")
        import traceback
        traceback.print_exc()

    return None


def create_printable_html_from_response(html_content):
    """從ECPay HTML提取並建立可列印格式"""

    order_no_match = re.search(r'<dt>訂單編號</dt>\s*<dd>\s*([^<\s]+)', html_content)
    order_no = order_no_match.group(1).strip() if order_no_match else ''

    store_name_match = re.search(r'<dt>商店名稱</dt>\s*<dd>([^<]+)</dd>', html_content)
    store_name = store_name_match.group(1).strip() if store_name_match else ''

    payment_method_match = re.search(r'<dt>付款方式</dt>\s*<dd>([^<]+)</dd>', html_content)
    payment_method = payment_method_match.group(1).strip() if payment_method_match else ''

    item_match = re.search(r'<dd class="o-pd-name">\s*([^<]+)<br', html_content)
    item_name = item_match.group(1).strip() if item_match else ''

    amount_match = re.search(r'<dd class="o-other-total">NT\$ (\d+)</dd>', html_content)
    amount = amount_match.group(1) if amount_match else ''

    bank_code_match = re.search(r'銀行代碼 (\d+)', html_content)
    bank_code = bank_code_match.group(1) if bank_code_match else ''

    account_match = re.search(r'帳號 <span class="oif-hl">([^<]+)</span>', html_content)
    v_account = account_match.group(1).strip() if account_match else ''

    expire_match = re.search(r'<dt>繳費截止時間</dt>\s*<dd[^>]*>([^<]+)</dd>', html_content)
    expire_date = expire_match.group(1).strip() if expire_match else ''

    notes_section = re.search(r'<h4>注意事項：</h4>\s*<ul>(.*?)</ul>', html_content, re.DOTALL)
    notes_html = notes_section.group(1) if notes_section else ''

    # 獲取字體檔案的絕對路徑
    script_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(script_dir, 'NotoSansTC-Regular.ttf')

    # 方法1: 嵌入 base64 字體（最可靠，但會增加 HTML 檔案大小）
    # 方法2: 使用 file:// URL（檔案小，但需要保持字體檔案路徑）
    if os.path.exists(font_path):
        try:
            # 讀取字體檔案並轉換為 base64
            with open(font_path, 'rb') as font_file:
                font_data = base64.b64encode(font_file.read()).decode('utf-8')

            font_face = f"""
        @font-face {{
            font-family: 'Noto Sans TC';
            src: url(data:font/truetype;charset=utf-8;base64,{font_data}) format('truetype');
            font-weight: normal;
            font-style: normal;
        }}"""
            font_family = '"Noto Sans TC", "Microsoft JhengHei", Arial, sans-serif'
            print(f"✅ 已嵌入字體檔案: {font_path}")
        except Exception as e:
            print(f"⚠️ 字體檔案讀取失敗: {e}，使用系統預設字體")
            font_face = ""
            font_family = '"Microsoft JhengHei", Arial, sans-serif'
    else:
        print(f"⚠️ 字體檔案未找到: {font_path}，使用系統預設字體")
        font_face = ""
        font_family = '"Microsoft JhengHei", Arial, sans-serif'

    printable_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>ATM虛擬帳號訂單成立 - {order_no}</title>
    <style>{font_face}
        @media print {{ body {{ margin: 0; padding: 20px; }} .no-print {{ display: none !important; }} }}
        body {{ font-family: {font_family}; max-width: 900px; margin: 0 auto; padding: 20px; }}
        .provider {{ text-align: center; color: #666; font-size: 14px; margin-bottom: 10px; }}
        .content-title {{ text-align: center; color: #333; font-size: 24px; margin: 20px 0; font-weight: bold; }}
        .order-table {{ border: 1px solid #ddd; margin: 20px 0; }}
        .order-table dl {{ display: flex; padding: 15px; margin: 0; border-bottom: 1px solid #ddd; }}
        .order-table dl:last-child {{ border-bottom: none; }}
        .order-table dt {{ font-weight: bold; width: 150px; color: #333; }}
        .order-table dd {{ flex: 1; margin: 0; color: #000; }}
        .oif-hl {{ background-color: #fff3cd; padding: 3px 8px; font-weight: bold; font-size: 18px; letter-spacing: 2px; }}
        .red-text {{ color: #e73358; font-weight: bold; }}
        .o-info-2 {{ margin: 20px 0; }}
        .currency-type {{ text-align: right; color: #666; margin: 10px 0; }}
        .ot-title {{ background-color: #f5f5f5; font-weight: bold; }}
        .o-pd-name {{ flex: 1; padding: 10px; }}
        .o-pd-total {{ width: 100px; text-align: right; padding: 10px; }}
        .ot-total {{ background-color: #f8f9fa; }}
        .o-sum .o-other-name {{ flex: 1; padding: 15px; font-weight: bold; font-size: 18px; }}
        .o-sum .o-other-total {{ width: 150px; text-align: right; padding: 15px; font-weight: bold; font-size: 20px; color: #e73358; }}
        .pay-tip {{ margin: 30px 0; padding: 20px; background-color: #f8f9fa; border-left: 4px solid #007bff; }}
        .pay-tip h4 {{ margin-top: 0; color: #333; }}
        .pay-tip ul {{ margin: 10px 0; padding-left: 20px; }}
        .pay-tip li {{ margin: 8px 0; line-height: 1.6; }}
        .print-button {{ text-align: center; margin: 20px 0; padding: 15px; }}
        .print-button .btn {{ display: inline-block; padding: 12px 40px; font-size: 16px; background-color: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; }}
        .print-button .btn:hover {{ background-color: #0056b3; }}
        .red-tip {{ text-align: center; color: #e73358; font-weight: bold; margin: 20px 0; padding: 15px; border: 2px solid #e73358; background-color: #fff3f3; }}
    </style>
    <script>function PrintResultBlock() {{ window.print(); }}</script>
</head>
<body>
    <p class="provider">綠界科技提供SSL安全加密金流</p>
    <h3 class="content-title">付款資訊</h3>

    <div class="order-table o-info-1">
        <dl><dt>訂單編號</dt><dd>{order_no}</dd></dl>
        <dl><dt>商店名稱</dt><dd>{store_name}</dd></dl>
        <dl><dt>付款方式</dt><dd>{payment_method}</dd></dl>
    </div>

    <div class="o-info-2">
        <p class="currency-type">單位 Unit：新台幣 NTD</p>
        <div class="order-table">
            <dl class="ot-title">
                <dd class="o-pd-name">商品明細</dd>
                <dd class="o-pd-total">小計</dd>
            </dl>
            <dl>
                <dd class="o-pd-name">{item_name}</dd>
                <dd class="o-pd-total">{amount}</dd>
            </dl>
        </div>
        <div class="order-table ot-total">
            <dl class="o-sum">
                <dd class="o-other-name">應付金額</dd>
                <dd class="o-other-total">NT$ {amount}</dd>
            </dl>
        </div>
    </div>

    <div class="order-table o-info-1">
        <dl>
            <dt>ATM繳費帳號</dt>
            <dd>
                <p>銀行代碼 {bank_code}</p>
                <p>帳號 <span class="oif-hl">{v_account}</span></p>
            </dd>
        </dl>
        <dl>
            <dt>繳費截止時間</dt>
            <dd class="red-text">{expire_date}</dd>
        </dl>
    </div>

    <div class="pay-tip">
        <h4>注意事項：</h4>
        <ul>{notes_html}</ul>
    </div>

    <div class="print-button no-print">
        <a class="btn" onclick="PrintResultBlock();">列印本頁</a>
    </div>

    <p class="red-tip no-print">綠界科技不承作投資、賭博、虛擬貨幣等交易代理收付，勿聽從他人指示付款，有疑慮請撥打 165 或 110</p>
</body>
</html>"""

    return printable_html


def upload_to_smb(local_file_path, remote_file_name, file_date):
    """上傳檔案到 SMB 共享目錄"""
    try:
        client_machine = socket.gethostname()

        # 建立 SMB 連線 - 先嘗試 445 端口 (direct TCP)
        conn = SMBConnection(
            SMB_CONFIG['username'],
            SMB_CONFIG['password'],
            client_machine,
            SMB_CONFIG['server_ip'],
            domain=SMB_CONFIG['domain'],
            use_ntlm_v2=True,
            is_direct_tcp=True
        )

        connected = conn.connect(SMB_CONFIG['server_ip'], 445)

        if not connected:
            # 如果 445 失敗，嘗試 139 端口 (NetBIOS)
            print(f"⚠️ 445 端口連線失敗，嘗試 139 端口...")
            conn = SMBConnection(
                SMB_CONFIG['username'],
                SMB_CONFIG['password'],
                client_machine,
                SMB_CONFIG['server_ip'],
                domain=SMB_CONFIG['domain'],
                use_ntlm_v2=True,
                is_direct_tcp=False
            )
            connected = conn.connect(SMB_CONFIG['server_ip'], 139)

        if not connected:
            print(f"❌ 無法連線到 SMB 伺服器: {SMB_CONFIG['server_ip']}")
            return None

        # 建構遠端路徑: AM/LEGAL/@@@@@保險公會費用及發票/image/yyyymmdd/
        remote_dir = f"{SMB_CONFIG['base_path']}{file_date}/"

        # 嘗試建立目錄（如果不存在）
        try:
            conn.createDirectory(SMB_CONFIG['service_name'], remote_dir)
            print(f"✅ 建立 SMB 目錄: {remote_dir}")
        except:
            # 目錄可能已存在，忽略錯誤
            pass

        # 上傳檔案 - 使用 BytesIO
        remote_path = f"{remote_dir}{remote_file_name}"
        with open(local_file_path, 'rb') as f:
            file_data = f.read()

        file_obj = io.BytesIO(file_data)
        bytes_uploaded = conn.storeFile(SMB_CONFIG['service_name'], remote_path, file_obj)

        conn.close()

        print(f"✅ 檔案已上傳到 SMB: {remote_path} ({bytes_uploaded} bytes)")
        return f"\\\\{SMB_CONFIG['server_ip']}\\{SMB_CONFIG['service_name']}\\{remote_path.replace('/', chr(92))}"

    except Exception as e:
        print(f"❌ SMB 上傳失敗: {e}")
        return None


def get_atm_info_and_save(retain_result, case_id, file_date):
    """取得ATM付款資訊並儲存"""
    if not retain_result or not retain_result.get('atm_form_fields'):
        print("❌ 沒有ATM表單資料")
        return None

    # 使用傳入的 session 保持 cookie
    session = retain_result.get('session', requests.Session())

    url = "https://payment.ecpay.com.tw/PaymentRule/ATMPaymentInfo"
    form_fields = retain_result['atm_form_fields']

    from urllib.parse import urlencode
    post_data = urlencode(form_fields)

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        response = session.post(url, data=post_data, headers=headers, timeout=30)

        if response.status_code == 200:
            print("✅ 取得ATM付款資訊成功")

            atm_info = {
                'AllPayTradeNo': form_fields.get('AllPayTradeNo'),
                'MerchantTradeNo': form_fields.get('MerchantTradeNo'),
                'BankCode': form_fields.get('BankCode'),
                'vAccount': form_fields.get('vAccount'),
                'ExpireDate': form_fields.get('ExpireDate'),
                'TradeAmount': form_fields.get('TradeAmount'),
                'ItemName': form_fields.get('ItemName')
            }

            # 儲存HTML和PDF (先存本地暫存目錄)
            temp_dir = f'./temp_{file_date}'
            os.makedirs(temp_dir, exist_ok=True)

            html_filename = f'{case_id}.html'
            html_filepath = os.path.join(temp_dir, html_filename)

            pdf_filename = f'{case_id}.pdf'
            pdf_filepath = os.path.join(temp_dir, pdf_filename)

            printable_html = create_printable_html_from_response(response.text)

            # 儲存HTML (暫存)
            with open(html_filepath, 'w', encoding='utf-8') as f:
                f.write(printable_html)
            print(f"✅ 儲存暫存HTML: {html_filepath}")

            # 轉換為PDF (使用 Playwright)
            pdf_created = False
            try:
                print("📄 使用 Playwright 生成 PDF...")
                with sync_playwright() as p:
                    # 啟動 Chromium 瀏覽器
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()

                    # 將絕對路徑轉換為 file:// URL
                    file_url = f"file:///{os.path.abspath(html_filepath).replace(chr(92), '/')}"

                    # 載入 HTML
                    page.goto(file_url)
                    page.wait_for_load_state('networkidle')

                    # 生成 PDF
                    page.pdf(
                        path=pdf_filepath,
                        format='A4',
                        print_background=True,
                        margin={
                            'top': '0.5cm',
                            'right': '0.5cm',
                            'bottom': '0.5cm',
                            'left': '0.5cm'
                        }
                    )

                    browser.close()

                if os.path.exists(pdf_filepath):
                    print(f"✅ 儲存暫存PDF: {pdf_filepath}")
                    pdf_created = True
                else:
                    print("⚠️ PDF轉換失敗：檔案未產生")

            except Exception as e:
                print(f"⚠️ PDF轉換失敗: {e}")

            # 上傳 PDF 到 SMB
            smb_pdf_path = None
            if pdf_created:
                smb_pdf_path = upload_to_smb(pdf_filepath, pdf_filename, file_date)
                if smb_pdf_path:
                    atm_info['saved_pdf'] = smb_pdf_path
                else:
                    atm_info['saved_pdf'] = pdf_filepath  # 回退到本地路徑

            # 上傳 HTML 到 SMB (可選)
            smb_html_path = upload_to_smb(html_filepath, html_filename, file_date)
            if smb_html_path:
                atm_info['saved_html'] = smb_html_path
            else:
                atm_info['saved_html'] = html_filepath  # 回退到本地路徑

            # 清理暫存檔案 (可選 - 如果你想保留本地備份，註解掉以下程式碼)
            try:
                if os.path.exists(html_filepath):
                    os.remove(html_filepath)
                if os.path.exists(pdf_filepath):
                    os.remove(pdf_filepath)
                if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                    os.rmdir(temp_dir)
                print("✅ 已清理暫存檔案")
            except Exception as e:
                print(f"⚠️ 清理暫存檔案失敗: {e}")

            return atm_info

        print(f"❌ 取得ATM資訊失敗，狀態碼: {response.status_code}")
        return None

    except Exception as e:
        print(f"❌ 取得ATM資訊錯誤: {e}")
        return None


def process_single_case(case_data, today, file_date):
    """處理單一案件"""
    Casei = str(case_data[3])
    legal_num = str(case_data[5])
    legal_court = str(case_data[6])
    debtor_ids = str(case_data[7])
    Insur_Type = str(case_data[17])
    RequestDate = str(case_data[21])

    print(f"\n{'='*80}")
    print(f"處理案件: {Casei}")
    print(f"{'='*80}")

    if RequestDate != today:
        print(f"⚠️ 請求日期不符，跳過")
        return False

    # 選擇使用者
    if Insur_Type == '1':
        Name, Mail, PSD = vars['Name001'], vars['Mail001'], vars['PSD001']
        Phone, Compiled, Company, Address = vars['Phone'], vars['Compiled'], vars['Company'], vars['Address']
    elif Insur_Type == '2':
        Name, Mail, PSD = vars['Name002'], vars['Mail002'], vars['PSD002']
        Phone, Compiled, Company, Address = vars['Phone'], vars['Compiled'], vars['Company'], vars['Address']
    elif Insur_Type == '3':
        Name, Mail, PSD = vars['Name003'], vars['Mail003'], vars['PSD003']
        Phone, Compiled, Company, Address = vars['Phone'], vars['Compiled'], vars['Company'], vars['Address']
    elif Insur_Type == '5':
        Name, Mail, PSD = vars['Name005'], vars['Mail005'], vars['PSD005']
        Phone, Compiled, Company, Address = vars['Phone005'], vars['Compiled005'], vars['Company005'], vars['Address005']
    else:
        print(f"❌ 無效的保險類型: {Insur_Type}")
        return False

    print(f"使用者: {Name} ({Mail})")
    print(f"公司: {Company}")

    # 步驟 1: 發送OTP
    print("\n--- 步驟 1: 發送OTP ---")
    if not send_otp_email(Mail):
        return False

    # 步驟 2: 取得驗證碼
    print("\n--- 步驟 2: 取得驗證碼 ---")
    print("等待 15 秒...")
    time.sleep(15)
    verify_code = get_verification_code_from_email(Mail, PSD)
    if not verify_code:
        return False

    # 步驟 3: 驗證並提交案件 (crr901w/verify) - 最多重試 5 次
    print("\n--- 步驟 3: 驗證並提交案件 ---")
    max_verify_retries = 5
    verify_fail_count = 0
    verify_result = None

    for attempt in range(1, max_verify_retries + 1):
        if attempt > 1:
            print(f"\n重試第 {attempt} 次...")
            # 重新發送OTP
            if not send_otp_email(Mail):
                verify_fail_count += 1
                continue
            print("等待 15 秒...")
            time.sleep(15)
            verify_code = get_verification_code_from_email(Mail, PSD)
            if not verify_code:
                verify_fail_count += 1
                continue

        verify_result = verify_and_submit_case(verify_code, Mail, Name, Phone,
                                               debtor_ids, legal_num, legal_court)

        if not verify_result:
            verify_fail_count += 1
            continue

        # 檢查是否為保險當事人異常
        if verify_result.get('error') == 'INSURANCE_PARTIES_ABNORMALITY':
            print(f"⚠️ 保險當事人錯誤")
            update(db['server'], db['username'], db['password'], db['database'], db['totb'],
                   '保險當事人錯誤', Casei, '', '', '', '', '', '', '', '', '', 'F', today)
            return True

        # 檢查是否為案號無效
        if verify_result.get('error') == 'ISSUE_NO_INVALID':
            print(f"⚠️ 公文或案號無效")
            update(db['server'], db['username'], db['password'], db['database'], db['totb'],
                   '公文或案號無效', Casei, '', '', '', '', '', '', '', '', '', 'F', today)
            return True

        # 檢查是否為 VERIFY_FAIL
        if verify_result.get('error') == 'VERIFY_FAIL':
            verify_fail_count += 1
            print(f"⚠️ VERIFY_FAIL (第 {verify_fail_count}/{max_verify_retries} 次)")
            if verify_fail_count >= max_verify_retries:
                print(f"⚠️ 已達最大重試次數，身分證可能有誤")
                update(db['server'], db['username'], db['password'], db['database'], db['totb'],
                       '請重新確認身分證是否無誤', Casei, '', '', '', '', '', '', '', '', '', 'F', today)
                return True
            continue

        # 驗證成功，跳出迴圈
        break

    if not verify_result or verify_result.get('error'):
        return False

    token = verify_result['token']
    case_uuid = verify_result['caseUid']

    # 計算債務人數量
    debtor_count = len([id.strip() for id in debtor_ids.split(',') if id.strip()])
    print(f"債務人數量: {debtor_count}")

    # 步驟 4: 提交付款請求 (crr201w/payment)
    print("\n--- 步驟 4: 提交付款請求 ---")
    payment_data = submit_payment_request(token, case_uuid, Name, Phone, Mail,
                                         Compiled, Company, Address, debtor_count)
    if not payment_data:
        return False

    # 檢查錯誤訊息
    msg = payment_data.get('msg', '')
    error_type = payment_data.get('error', '')

    # 債務人數量比對失敗 - 回寫資料庫並設 STATUS = 'F'
    if '債務人數量比對失敗' in msg or error_type == 'DEBTOR_COUNT_MISMATCH':
        print(f"⚠️ {msg}")
        update(db['server'], db['username'], db['password'], db['database'], db['totb'],
               msg, Casei, '', '', '', '', '', '', '', '', '保險查詢費', 'F', today)
        return True

    # 查無資料
    if '查無資料' in msg or '該案' in msg:
        print(f"⚠️ {msg}")
        update(db['server'], db['username'], db['password'], db['database'], db['totb'],
               msg, Casei, '', '', '', '', '', '', '', '', '保險查詢費', 'F', today)
        return True

    # 步驟 5-7: 使用 Playwright 處理綠界付款流程
    print("\n--- 步驟 5-7: 綠界付款流程 (Playwright) ---")
    atm_info = process_ecpay_with_playwright(payment_data, Casei, file_date)
    if not atm_info:
        return False

    # 更新資料庫
    print("\n--- 更新資料庫 ---")
    update(db['server'], db['username'], db['password'], db['database'], db['totb'],
           '調閱成功', Casei, atm_info.get('MerchantTradeNo', ''),
           '中華民國人壽保險商業同業公會', 'ATM 櫃員機', atm_info.get('ItemName', ''),
           atm_info.get('BankCode', ''), atm_info.get('vAccount', ''),
           atm_info.get('ExpireDate', ''), atm_info.get('TradeAmount', ''),
           '保險查詢費', 'F', today)

    print(f"\n✅ 案件 {Casei} 處理完成！")
    return True


def main():
    """主程式"""
    print("="*80)
    print("Legal Insurance Automation - Final (crr901w + crr201w API)")
    print("="*80)

    today = datetime.datetime.now().strftime('%Y-%m-%d') #'2025-10-06' #'2026-02-22'#
    file_date = datetime.datetime.now().strftime('%Y%m%d') #'20251006'#'20260208'#'20260222'#
    print(f"執行日期: {today}")
    print(f"檔案日期: {file_date}\n")

    # 建立目錄
    os.makedirs(f'./{file_date}', exist_ok=True)

    # 取得待處理案件
    obs = src_obs(db['server'], db['username'], db['password'], db['database'],
                  db['fromtb'], db['totb'],today)

    print(f"待處理案件數: {obs}\n")

    if obs == 0:
        print("沒有待處理案件")
        return

    success_count = 0
    fail_count = 0

    while obs > 0:
        try:
            cases = dbfrom(db['server'], db['username'], db['password'],
                          db['database'], db['fromtb'], db['totb'], today)

            if not cases:
                print("查詢案件時返回空列表，重新檢查待處理數量")
                obs = src_obs(db['server'], db['username'], db['password'], db['database'],
                             db['fromtb'], db['totb'],today)
                continue

            case_data = cases[0]

            if process_single_case(case_data, today, file_date):
                success_count += 1
            else:
                fail_count += 1

            obs = src_obs(db['server'], db['username'], db['password'], db['database'],
                         db['fromtb'], db['totb'],today)

        except Exception as e:
            print(f"\n錯誤: {e}")
            fail_count += 1
            obs = src_obs(db['server'], db['username'], db['password'], db['database'],
                         db['fromtb'], db['totb'],today)

    print("\n" + "="*80)
    print(f"處理完成！成功: {success_count} | 失敗: {fail_count}")
    print("="*80)


if __name__ == "__main__":
    main()
