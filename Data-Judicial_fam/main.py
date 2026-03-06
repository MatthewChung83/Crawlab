# -*- coding: utf-8 -*-
"""
司法院家事公告爬蟲
- 家事事件公告資料抓取
- 統一 Log 模組
"""

import os
import sys
import datetime
import requests
import json
import re
import time
import urllib

from bs4 import BeautifulSoup
from urllib.parse import urlencode

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import *
from common.logger import get_logger

# Initialize logger
logger = get_logger('Data-Judicial_fam')


def run():
    """Main execution function"""
    logger.task_start("家事事件公告同步")

    server = db['server']
    database = db['database']
    username = db['username']
    password = db['password']
    fromtb = db['fromtb']
    totb = db['totb']
    url = wbinfo['url']
    url1 = wbinfo['url1']

    logger.log_db_connect(server, database, username)

    try:
        obs = src_obs(server, username, password, database, fromtb, totb)
        logger.info(f"待處理筆數: {obs}")

        if obs <= 0:
            logger.info("沒有待處理的資料")
            logger.task_end(success=True)
            return True

        src = dbfrom(server, username, password, database, fromtb, totb)
        total_records = len(src)
        logger.info(f"取得 {total_records} 筆資料")

        total_processed = 0
        total_success = 0
        total_failed = 0

        for i in range(total_records):
            logger.log_progress(i + 1, total_records, f"record_{i + 1}")

            try:
                today = str(datetime.datetime.now())[0:-3]
                ID = src[i][1]
                name = re.sub(r'[^\u4e00-\u9fffA-Za-z0-9\s]', '', src[i][2])
                rowid = str(src[i][9]).replace('None', '')

                logger.ctx.set_data(ID=ID, name=name, rowid=rowid)
                logger.debug(f"處理: ID={ID}, name={name}")

                # Create session and get token
                req_session = requests.Session()
                headers = {
                    'Host': 'domestic.judicial.gov.tw',
                    'Origin': 'https://domestic.judicial.gov.tw',
                    'Referer': 'https://domestic.judicial.gov.tw/judbp/wkw/WHD9HN01/V2.htm',
                }

                set_token_url = 'https://domestic.judicial.gov.tw/judbp/wkw/WHD9HN01/V2.htm'

                logger.ctx.set_operation("get_token")
                start_time = time.time()
                logger.log_request("POST", set_token_url, headers, None)

                token_resp = req_session.post(set_token_url, headers=headers, timeout=30)
                elapsed = time.time() - start_time

                logger.log_response(token_resp.status_code, dict(token_resp.headers), f"[HTML: {len(token_resp.text)} chars]", elapsed)

                token = BeautifulSoup(token_resp.text, 'lxml').select('input[name=token]')[0]['value']
                logger.debug(f"取得 token: {token[:20]}...")

                # Query data
                data = {
                    'crtid': '',
                    'kdid': '',
                    'clnm': name,
                    'clnm_roma': '',
                    'idno': ID,
                    'sddt_s': '',
                    'sddt_e': '',
                    'token': token,
                    'condition': '法院別: 全部法院, 類別: 全部, 身分證字號: ' + ID
                }

                logger.ctx.set_operation("query_data")
                start_time = time.time()
                logger.log_request("POST", url, headers, data)

                resp = req_session.post(url, headers=headers, data=data, timeout=30)
                elapsed = time.time() - start_time

                logger.log_response(resp.status_code, dict(resp.headers), resp.text[:500] if len(resp.text) > 500 else resp.text, elapsed)

                soup = BeautifulSoup(resp.text, "lxml")

                try:
                    d = json.loads(soup.text)
                    res = d['data']['dataList']
                except:
                    res = ''
                    pass

                if len(res) == 0:
                    # No data found
                    logger.info(f"ID={ID} 查無資料")

                    announcement = ''
                    post_date = ''
                    register_no = ''
                    keynote = ''
                    Basis = ''
                    Matters = ''
                    update_date = today
                    note = 'N'
                    item = ''
                    flag = '查無資料'
                    note2 = {"status": "", "Death_date": ""}
                    note2 = json.dumps(note2, ensure_ascii=False)

                    docs = (name, ID, announcement, post_date, register_no, keynote, Basis, Matters, update_date, note, flag, note2)
                    judicial_result = judicial(docs)

                    logger.ctx.set_operation("DB_insert")
                    logger.ctx.set_db(server=server, database=database, table=totb, operation="INSERT")

                    if len(rowid) == 0:
                        toSQL(judicial_result, totb, server, database, username, password)
                        logger.log_db_operation("INSERT", database, totb, 1)
                    else:
                        delete(server, username, password, database, totb, note, ID, rowid, register_no, flag)
                        toSQL(judicial_result, totb, server, database, username, password)
                        logger.log_db_operation("DELETE+INSERT", database, totb, 1)

                    total_success += 1
                    logger.increment('records_success')

                    # Check daily limit
                    exit_o = exit_obs(server, username, password, database, totb)
                    if exit_o >= 10000:
                        logger.warning(f"已達每日上限 ({exit_o})")
                        break

                else:
                    # Data found - process each record
                    logger.info(f"ID={ID} 找到 {len(res)} 筆資料")
                    d = json.loads(soup.text)
                    f = d['data']['dataList']

                    for j in range(len(f)):
                        crtid = f[j]['crtid']
                        filenm = f[j]['filenm']
                        durcd = f[j]['durcd']
                        seqno = f[j]['seqno']
                        item = f[j]['item']

                        data1 = {
                            'crtid': crtid,
                            'filenm': str(filenm).replace('None', ''),
                            'durcd': str(durcd).replace('None', ''),
                            'condition': '法院別: 全部法院, 類別: 全部, 當事人: ' + name + ', 身分證字號: ' + ID,
                            'seqno': str(seqno).replace('None', ''),
                            'isDialog': 'Y',
                        }

                        logger.ctx.set_operation("view_detail")
                        start_time = time.time()
                        logger.log_request("POST", url1, headers, data1)

                        resp = req_session.post(url1, data=data1, timeout=30)
                        elapsed = time.time() - start_time

                        logger.log_response(resp.status_code, dict(resp.headers), f"[HTML: {len(resp.text)} chars]", elapsed)

                        soup = BeautifulSoup(resp.text.replace('</br>', '').replace('<br/>', ''), "xml")
                        soup1 = soup.findAll('td')

                        try:
                            text = soup1[3].text.replace('\t\t\t例', '例')
                        except:
                            text = ''
                            pass

                        # Determine item type
                        if '遺產管理人' in item:
                            item = '遺產管理人'
                            note = 'Y'
                        elif '遺產清冊' in item:
                            item = '陳報遺產清冊'
                            note = 'Y'
                        elif '拋棄繼承' in item:
                            item = '拋棄繼承'
                            note = 'Y'
                        else:
                            item = item
                            note = 'N'

                        # Extract fields
                        try:
                            announcement = re.search(r'例稿名稱：(.*)', text, re.M | re.I).group().replace(' ', '').replace('\n', '').replace('─', '').replace('┼', '').replace('┌', '').replace('├', '').replace('┬', '').replace('┤', '').replace('┐', '').replace('│', '').replace('┤', '').replace('┘', '').replace('└', '').replace('　', '')
                        except:
                            announcement = ''
                            pass

                        try:
                            post_date = re.search(r'發文日期：(.*)', text, re.M | re.I).group().replace(' ', '').replace('\n', '').replace('─', '').replace('┼', '').replace('┌', '').replace('├', '').replace('┬', '').replace('┤', '').replace('┐', '').replace('│', '').replace('┤', '').replace('┘', '').replace('└', '').replace('　', '')
                        except:
                            post_date = ''
                            pass

                        try:
                            register_no = re.search(r'發文字號：(.*)', text, re.M | re.I).group().replace(' ', '').replace('\n', '').replace('─', '').replace('┼', '').replace('┌', '').replace('├', '').replace('┬', '').replace('┤', '').replace('┐', '').replace('│', '').replace('┤', '').replace('┘', '').replace('└', '').replace('　', '')
                        except:
                            register_no = ''
                            pass

                        try:
                            keynote = re.search(r'主[\s]*旨：(.*)', text, re.M | re.I).group().replace(' ', '').replace('\n', '').replace('─', '').replace('┼', '').replace('┌', '').replace('├', '').replace('┬', '').replace('┤', '').replace('┐', '').replace('│', '').replace('┤', '').replace('┘', '').replace('└', '').replace('　', '')
                        except:
                            keynote = ''
                            pass

                        Basis = ''
                        Matters = text.replace('\u3000', '').replace('┌', '').replace('─', '').replace('┬', '').replace('│', '').replace('┼', '').replace('├', '').replace('┤', '').replace('─', '').replace('└', '').replace('┴', '').replace('┘', '').replace(' ', '').replace('\n', '').replace(' ', '').replace('　', '')
                        update_date = today

                        # Check death status
                        name1 = Matters[Matters.rfind('被繼承人'):Matters.rfind('被繼承人') + 10]
                        name2 = Matters[Matters.find('被繼承人'):Matters.find('被繼承人') + 10]

                        if name in name1:
                            if '死亡' in Matters.replace(' ', '').replace('\n', '').replace(' ', ''):
                                Matters = Matters.replace(' ', '').replace('\n', '').replace(' ', '')
                                data_1 = Matters[Matters.rfind('死亡') - 10:Matters.rfind('死亡')].replace('，', '').replace('國', '').replace('民', '').replace('號', '').replace('於', '').replace(')', '').replace('(', '').replace('）', '').replace('（', '').replace('宣', '').replace('告', '').replace('、', '').replace('生', '').replace('死', '').replace('亡', '')
                                if '年' in data_1 and '月' in data_1:
                                    note2 = {"status": "死亡", "Death_date": data_1}
                                    note2 = json.dumps(note2, ensure_ascii=False)
                                else:
                                    note2 = {"status": "死亡", "Death_date": ""}
                                    note2 = json.dumps(note2, ensure_ascii=False)
                            else:
                                note2 = {"status": "死亡", "Death_date": ""}
                                note2 = json.dumps(note2, ensure_ascii=False)
                        elif name in name2:
                            if '死亡' in Matters.replace(' ', '').replace('\n', '').replace(' ', ''):
                                Matters = Matters.replace(' ', '').replace('\n', '').replace(' ', '')
                                data_1 = Matters[Matters.rfind('死亡') - 10:Matters.rfind('死亡')].replace('，', '').replace('國', '').replace('民', '').replace('號', '').replace('於', '').replace(')', '').replace('(', '').replace('）', '').replace('（', '').replace('宣', '').replace('告', '').replace('、', '').replace('生', '').replace('死', '').replace('亡', '')
                                if '年' in data_1 and '月' in data_1:
                                    note2 = {"status": "死亡", "Death_date": data_1}
                                    note2 = json.dumps(note2, ensure_ascii=False)
                                else:
                                    note2 = {"status": "死亡", "Death_date": ""}
                                    note2 = json.dumps(note2, ensure_ascii=False)
                            else:
                                note2 = {"status": "死亡", "Death_date": ""}
                                note2 = json.dumps(note2, ensure_ascii=False)
                        else:
                            note2 = {"status": "", "Death_date": ""}
                            note2 = json.dumps(note2, ensure_ascii=False)

                        Matters = Matters[:4000]
                        docs = (name, ID, announcement, post_date, register_no, keynote, Basis, Matters, update_date, note, item, note2)
                        judicial_result = judicial(docs)

                        logger.ctx.set_operation("DB_insert")
                        logger.ctx.set_db(server=server, database=database, table=totb, operation="INSERT")

                        if len(rowid) == 0:
                            toSQL(judicial_result, totb, server, database, username, password)
                            logger.log_db_operation("INSERT", database, totb, 1)
                        else:
                            delete(server, username, password, database, totb, note, ID, rowid, register_no, item)
                            toSQL(judicial_result, totb, server, database, username, password)
                            logger.log_db_operation("DELETE+INSERT", database, totb, 1)

                        total_success += 1
                        logger.increment('records_success')

                        # Check daily limit
                        exit_o = exit_obs(server, username, password, database, totb)
                        if exit_o >= 10000:
                            logger.warning(f"已達每日上限 ({exit_o})")
                            break

                total_processed += 1

            except Exception as e:
                logger.log_exception(e, f"處理記錄 {i + 1} 時發生錯誤")
                total_failed += 1
                logger.increment('records_failed')
                time.sleep(10)
                continue

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
    logger.info(f"目標資料表: {db['totb']}")

    try:
        success = run()
        if success:
            logger.info("同步完成")
        else:
            logger.warning("部分處理失敗")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == "__main__":
    main()
