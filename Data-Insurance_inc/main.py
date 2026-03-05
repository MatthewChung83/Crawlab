import requests
import ddddocr
import time
import xml.etree.ElementTree as ET
import sys
import re
import warnings
import logging
import os

# 完全抑制警告和 ONNX Runtime 日誌
warnings.filterwarnings("ignore")
logging.getLogger("onnxruntime").setLevel(logging.CRITICAL)
logging.getLogger().setLevel(logging.CRITICAL)

# 設定環境變數以避免 ONNX Runtime 執行緒親和性錯誤
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['ONNXRUNTIME_LOG_SEVERITY_LEVEL'] = '4'  # 4 = FATAL，只顯示致命錯誤
os.environ['ORT_LOGGING_LEVEL'] = '4'

# 重定向 stderr 以抑制 C++ 層級的錯誤訊息
class NullWriter:
    def write(self, txt): pass
    def flush(self): pass

# 暫存原始 stderr
original_stderr = sys.stderr

from config import *
from etl_func import *
from dict import *

# 移除 proxies 設定
# proxies = {
#     "http": "http://vct57:8080",
#     "https": "http://vct57:8080",
# }

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
server, database, username, password, totb1, entitytype = db['server'], db['database'], db['username'], db['password'], db['totb1'], db['entitytype']

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
    """
    使用 requests 方式查詢統編
    
    Args:
        regno: 統一編號
        max_retry: 最大重試次數（對應原來第一筆的 1000 次重試）
    
    Returns:
        tuple: (success, result_data) 
               success: bool, 是否查詢成功
               result_data: dict, 包含查詢結果資料
    """
    for i in range(max_retry):
        try:
            # 1. 取得驗證碼
            captcha_img = session.get(captcha_url, verify=False).content
            
            # 暫時重定向 stderr 以抑制 ONNX Runtime 錯誤訊息
            sys.stderr = NullWriter()
            try:
                captcha_code = ddddocr.DdddOcr().classification(captcha_img)
            finally:
                # 恢復 stderr
                sys.stderr = original_stderr
            print(f"第{i+1}次嘗試，辨識碼為：{captcha_code}")

            # 2. 準備 payload
            payload = build_payload(captcha_code, regno)
            
            # 3. 發送查詢
            resp = session.post(url, data=payload.encode("big5"), headers=headers, verify=False)
            result = resp.content.decode("big5", errors="ignore")

            # 4. 判斷是否驗證碼錯誤
            if "<CaptchaError>" in result:
                print("驗證碼錯誤，重新嘗試…")
                time.sleep(1)
                continue
            else:
                print("查詢成功！")
                
                # 5. 解析結果
                result_data = parse_query_result(result)
                return True, result_data
                
        except Exception as e:
            print(f"查詢過程發生錯誤: {e}")
            time.sleep(1)
            continue
    
    print("多次嘗試後仍失敗，請檢查流程或驗證碼辨識")
    return False, {'message': '查詢失敗'}

def parse_query_result(result):
    """
    解析查詢結果
    
    Args:
        result: API 回應的 XML 字串
    
    Returns:
        dict: 解析後的結果資料
    """
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
        print("XML 解析失敗:", e)
        print(result)
        result_data['message'] = 'XML解析錯誤'
        result_data['login_inc'] = 'XML解析錯誤'
    
    return result_data

def process_single_record(record_data, is_first_record=False):
    """
    處理單筆記錄的查詢和資料庫更新
    
    Args:
        record_data: dict, 包含 name, ID, IDN_10 等資訊
        is_first_record: bool, 是否為第一筆記錄（影響重試次數）
    """
    name = record_data['name']
    ID = record_data['ID']
    IDN_10 = record_data['IDN_10']
    
    print(f"處理記錄: ID={ID}, IDN_10={IDN_10}")
    
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
    updateSQL(server, username, password, database, totb1, entitytype, status, updatetime, ID, IDN_10, Insurance_type, login_date, login_inc)
    print(f"更新結果: {ID}, {IDN_10}, {login_date}, {login_inc}, {Insurance_type}, {status}")
    
    # 檢查今日查詢筆數限制
    exit_o = exit_obs(server, username, password, database, totb1)
    if exit_o >= 5000:
        print("今日查詢筆數已達上限 5000 筆，程式結束")
        sys.exit()

def main():
    """主程式邏輯"""
    try:
        # 取得總筆數
        obs = src_obs(server, username, password, database, totb1, entitytype)
        print(f"總共需要處理 {obs} 筆記錄")
        
        # 處理每筆記錄
        for i in range(obs):
            # 從資料庫取得待處理資料
            src = dbfrom(server, username, password, database, totb1, entitytype)
            
            if not src or len(src) == 0:
                print("沒有待處理的記錄")
                break
                
            record_data = {
                'name': src[0][1],
                'ID': src[0][2],
                'IDN_10': src[0][4]
            }
            
            # 處理記錄（第一筆記錄有特殊處理）
            is_first_record = (i == 0)
            process_single_record(record_data, is_first_record)
            
            # 每筆記錄間隔，避免請求過於頻繁
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n程式被使用者中斷")
    except Exception as e:
        print(f"程式執行錯誤: {e}")
    finally:
        print("程式執行完畢")

if __name__ == "__main__":
    main()