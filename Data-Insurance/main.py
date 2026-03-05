# -*- coding: utf-8 -*-
"""
Created on Wed Apr 27 14:29:31 2022
@author: admin
"""
import os
import sys
import contextlib
import datetime
import requests
import ddddocr
import time
import xml.etree.ElementTree as ET
import logging
from config import *
from etl_func import *


# 設置日誌系統
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crawlab_debug.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

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
try:
    server, database, username, password, totb, fromtb = db['server'], db['database'], db['username'], db['password'], db['totb'], db['fromtb']
    logger.info(f"資料庫配置載入成功: server={server}, database={database}")
except Exception as e:
    logger.error(f"資料庫配置載入失敗: {e}")
    sys.exit(1)

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
try:
    session = requests.Session()
    session.timeout = 30  # 設置超時時間
    logger.info("HTTP Session 初始化成功")
except Exception as e:
    logger.error(f"HTTP Session 初始化失敗: {e}")
    sys.exit(1)

# 建立 payload
def build_payload(captcha_code, usrId, DateY, DateM, DateD):
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

# 查詢主程式 - 改進版
def query_regno(usrId, DateY, DateM, DateD, max_retry=10):
    logger.info(f"開始查詢用戶: {usrId}, 生日: {DateY}/{DateM}/{DateD}")
    
    try:
        for i in range(max_retry):
            try:
                # 獲取驗證碼圖片
                logger.debug(f"第 {i+1} 次嘗試獲取驗證碼")
                captcha_response = session.get(captcha_url, verify=False, timeout=10)
                
                if captcha_response.status_code != 200:
                    logger.warning(f"驗證碼請求失敗，狀態碼: {captcha_response.status_code}")
                    time.sleep(2)
                    continue
                
                captcha_img = captcha_response.content
                logger.debug(f"驗證碼圖片大小: {len(captcha_img)} bytes")
                
                # 識別驗證碼
                try:
                    with suppress_stderr():
                        captcha_code = ddddocr.DdddOcr().classification(captcha_img)
                    logger.debug(f"識別驗證碼: {captcha_code}")
                except Exception as ocr_error:
                    logger.error(f"OCR 識別失敗: {ocr_error}")
                    time.sleep(1)
                    continue
                
                # 建立 payload
                payload = build_payload(captcha_code, usrId, DateY, DateM, DateD)
                if payload is None:
                    logger.error("Payload 建立失敗")
                    return None
                
                # 發送請求
                try:
                    resp = session.post(
                        url, 
                        data=payload.encode("big5"), 
                        headers=headers, 
                        verify=False, 
                        timeout=15
                    )
                    logger.debug(f"POST 請求狀態碼: {resp.status_code}")
                    
                    # 檢查是否為 500 錯誤
                    if resp.status_code == 500:
                        logger.error("=" * 80)
                        logger.error("遇到 HTTP 500 伺服器內部錯誤 - 程式正常停止執行")
                        logger.error("=" * 80)
                        logger.error(f"請求 URL: {url}")
                        logger.error(f"用戶 ID: {usrId}")
                        logger.error(f"生日: {DateY}/{DateM}/{DateD}")
                        logger.error(f"驗證碼: {captcha_code}")
                        logger.error(f"嘗試次數: {i+1}/{max_retry}")
                        logger.error(f"時間: {datetime.datetime.now()}")
                        logger.error(f"回應標頭: {dict(resp.headers)}")
                        try:
                            response_text = resp.content.decode("big5", errors="ignore")
                            logger.error(f"回應內容 (前1000字元): {response_text[:1000]}")
                        except:
                            logger.error(f"回應內容 (原始): {resp.content[:1000]}")
                        logger.error("=" * 80)
                        
                        # 印出 500 錯誤訊息到控制台
                        print("\n" + "=" * 80)
                        print("⚠️  HTTP 500 伺服器錯誤 - 程式正常停止")
                        print("=" * 80)
                        print(f"🔍 錯誤詳情:")
                        print(f"   用戶 ID: {usrId}")
                        print(f"   生日: {DateY}/{DateM}/{DateD}")
                        print(f"   驗證碼: {captcha_code}")
                        print(f"   嘗試次數: {i+1}")
                        print(f"   時間: {datetime.datetime.now()}")
                        print(f"   狀態碼: {resp.status_code}")
                        print(f"   URL: {url}")
                        try:
                            error_response = resp.content.decode("big5", errors="ignore")
                            print(f"   伺服器回應: {error_response[:500]}...")
                        except:
                            print(f"   伺服器回應 (無法解碼): {resp.content[:200]}...")
                        print("=" * 80)
                        print("✅ 程式已正常結束")
                        
                        # 拋出自定義異常來觸發正常退出
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
                except requests.exceptions.HTTPError as http_error:
                    # 特別處理 HTTP 錯誤
                    if "500" in str(http_error):
                        logger.error("=" * 80)
                        logger.error("HTTP 500 錯誤異常捕獲 - 程式正常停止執行")
                        logger.error("=" * 80)
                        logger.error(f"HTTP 錯誤: {http_error}")
                        logger.error(f"用戶 ID: {usrId}")
                        logger.error(f"嘗試次數: {i+1}")
                        print(f"\n⚠️  HTTP 500 異常錯誤: {http_error}")
                        print("✅ 程式已正常結束")
                        raise SystemExit("HTTP 500 異常錯誤，程式正常停止")
                    else:
                        logger.warning(f"HTTP 錯誤 (第 {i+1} 次): {http_error}")
                        time.sleep(2)
                        continue
                except requests.exceptions.RequestException as req_error:
                    logger.error(f"請求異常 (第 {i+1} 次): {req_error}")
                    time.sleep(2)
                    continue
                
                # 解析回應
                try:
                    result = resp.content.decode("big5", errors="ignore")
                    logger.debug(f"回應內容長度: {len(result)} 字元")
                    
                    if "<CaptchaError>" in result:
                        logger.info(f"{usrId} 第{i+1}次驗證碼失敗 code={captcha_code}")
                        time.sleep(1)
                        continue
                    else:
                        # 解析 XML
                        try:
                            root = ET.fromstring(result)
                            row = root.find('Row')
                            
                            if row is None:
                                logger.info(f"{usrId} XML 中找不到 Row 元素")
                                return None
                            
                            regno = row.findtext('regno')
                            regFlag = row.findtext('regFlag')
                            tarrvy = row.findtext('tarrvy')
                            tarrvm = row.findtext('tarrvm')
                            tarrvd = row.findtext('tarrvd')
                            
                            logger.debug(f"解析結果: regno={regno}, regFlag={regFlag}, tarrvy={tarrvy}, tarrvm={tarrvm}, tarrvd={tarrvd}")
                            
                            if (not regno or regno.strip() == '') and regFlag == "0" and tarrvy == "000" and tarrvm == "00" and tarrvd == "00":
                                logger.info(f"{usrId} 未辦理登錄")
                                return "未辦理登錄"
                            
                            result_data = {
                                "regno": regno,
                                "date": f"民國{tarrvy}年{tarrvm}月{tarrvd}日"
                            }
                            logger.info(f"{usrId} 查詢成功: {result_data}")
                            return result_data
                            
                        except ET.ParseError as xml_error:
                            logger.error(f"{usrId} XML解析錯誤: {xml_error}")
                            logger.debug(f"原始回應內容: {result[:500]}...")  # 只顯示前500字元
                            return None
                        except Exception as parse_error:
                            logger.error(f"{usrId} 解析過程錯誤: {parse_error}")
                            return None
                        
                        break  # 成功處理，跳出迴圈
                        
                except UnicodeDecodeError as decode_error:
                    logger.error(f"回應解碼錯誤: {decode_error}")
                    time.sleep(1)
                    continue
                except Exception as response_error:
                    logger.error(f"回應處理錯誤: {response_error}")
                    time.sleep(1)
                    continue
                    
            except Exception as loop_error:
                logger.error(f"迴圈內錯誤 (第 {i+1} 次): {loop_error}", exc_info=True)
                time.sleep(2)
                continue
        
        else:
            logger.error(f"{usrId} 超過 {max_retry} 次重試仍失敗")
            return None
            
    except Exception as main_error:
        logger.error(f"query_regno 主函數錯誤 (usrId={usrId}): {main_error}", exc_info=True)
        return None

# ==== 主程式執行部分 ====
def main():
    logger.info("程式開始執行")
    
    try:
        # 獲取資料庫觀察數
        obs = src_obs(server, username, password, database, fromtb, totb)
        logger.info(f"總共需要處理 {obs} 筆資料")
        
        for i in foo(-1, obs-1):
            try:
                logger.info(f"處理第 {i+1} 筆資料")
                
                # 從資料庫獲取資料
                src = dbfrom(server, username, password, database, fromtb, totb)[0]
                today = str(datetime.datetime.now())[0:-3]
                Name = src[2]
                ID = src[1]
                birthday = src[6]
                rowid = str(src[10]).replace('None','')
                
                logger.info(f"處理用戶: {Name} (ID: {ID})")
                
                # 解析生日
                try:
                    bir = birthday.split('/', 2)
                    birY, birM, birD = bir[0], bir[1], bir[2]
                    logger.debug(f"生日解析: {birY}/{birM}/{birD}")
                except Exception as birthday_error:
                    logger.error(f"生日解析錯誤 ({birthday}): {birthday_error}")
                    continue
                
                # 查詢保險資訊
                message = query_regno(ID, birY, birM, birD)
                
                # 處理查詢結果
                if message is None:
                    note = 'N'
                    insurance_num = ''
                    logger.info(f"{ID} 查無資料")
                    
                elif message == "未辦理登錄":
                    note = 'N'
                    insurance_num = ''
                    logger.info(f"{ID} 未辦理登錄")
                    
                else:
                    insurance_num = message.get("regno", "")
                    note = 'Y' if insurance_num != '' else 'N'
                    logger.info(f"{ID} 查詢成功 regno={insurance_num} date={message.get('date')}")
                
                # 準備資料並寫入資料庫
                try:
                    docs = (Name, ID, birthday, insurance_num, today, note)
                    insurance_result = insurance(docs)
                    
                    if len(rowid) > 0:
                        update(server, username, password, database, totb, note, ID, today, rowid, insurance_num)
                        logger.debug(f"更新現有記錄: rowid={rowid}")
                    else:
                        toSQL(insurance_result, totb, server, database, username, password)
                        logger.debug("插入新記錄")
                        
                except Exception as db_error:
                    logger.error(f"資料庫操作錯誤 (ID={ID}): {db_error}")
                    continue
                
                # 檢查查詢總筆數
                try:
                    exit_o = exit_obs(server, username, password, database, totb)
                    current_processed = src_obs(server, username, password, database, fromtb, totb)
                    
                    logger.info(f"已查詢 {current_processed} 筆")
                    
                    if exit_o >= 5000:
                        logger.warning('今日查詢數已達上限 5000 筆，正常停止。')
                        print('✅ 今日查詢數已達上限 5000 筆，程式正常結束。')
                        try:
                            driver.close()
                        except:
                            pass
                        return  # 正常退出而不是 sys.exit()
                        
                except Exception as check_error:
                    logger.error(f"檢查查詢數錯誤: {check_error}")
                    
            except SystemExit as sys_exit:
                # 捕獲 HTTP 500 錯誤引起的 SystemExit
                logger.info(f"程式因 HTTP 500 錯誤正常停止: {sys_exit}")
                return  # 正常退出
            except Exception as record_error:
                logger.error(f"處理第 {i+1} 筆資料時發生錯誤: {record_error}", exc_info=True)
                continue
                
    except SystemExit as sys_exit:
        # 捕獲最外層的 SystemExit
        logger.info(f"程式正常停止: {sys_exit}")
        return
    except Exception as main_error:
        logger.error(f"主程式執行錯誤: {main_error}", exc_info=True)
        raise  # 重新拋出異常
    
    logger.info("程式執行完成")

if __name__ == "__main__":
    try:
        main()
        print("✅ 程式執行完成")
    except SystemExit as e:
        print(f"✅ 程式正常結束: {e}")
    except Exception as e:
        print(f"❌ 程式執行錯誤: {e}")
        logger.error(f"程式執行錯誤: {e}", exc_info=True)