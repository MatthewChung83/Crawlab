# -*- coding: utf-8 -*-
"""
Land Parcel Section crawler - 地段小段資料同步
"""
import os
import sys
import re
import time
import random
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl_func import indata, toSQL, truncate_table, overwrite, is_all_chinese
from config import *
from common.logger import get_logger

# Initialize logger
logger = get_logger('Data-Land_Parcel_Section')

# ---- DB 設定 ----
server, database, username, password = (
    db["server"], db["database"], db["username"], db["password"]
)
# 暫存表 / 正式表（建議帶 schema）
totb_tmp = "dbo.land_parcel_section_tmp"
totb_target = "dbo.land_parcel_section"

# ---- 站台 URL ----
BASE = "https://ep.land.nat.gov.tw"
XML_URL = f"{BASE}/js/CityAREACharNew.xml"
SESSION_URL = f"{BASE}/EpaperDoc/GetSessionDetail2"
REFERER = f"{BASE}/EpaperApply/RVA_Input2"

# ---- 參數 ----
BATCH = 500                                  # 批次寫入量
SLEEP_MIN, SLEEP_MAX = 0.3, 0.8              # 每次呼叫 API 的節流時間區間(秒)


def run():
    """Main execution function"""
    logger.task_start("地段小段資料同步")
    logger.log_db_connect(server, database, username)

    # ===== requests session + retries =====
    session = requests.Session()
    retries = Retry(
        total=4, backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=["GET", "POST"]
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    })

    # ===== XML parse helper（處理 Big5 等多位元編碼） =====
    def parse_xml_with_encoding_fallback(data: bytes) -> ET.Element:
        try:
            return ET.fromstring(data)
        except Exception:
            pass
        m = re.search(br'encoding=["\']([^"\']+)["\']', data[:256], re.I)
        enc = m.group(1).decode("ascii", "ignore") if m else "big5"
        text = data.decode(enc, errors="replace")
        text_wo_decl = re.sub(r'^\s*<\?xml[^>]*\?>', "", text, flags=re.I)
        return ET.fromstring(text_wo_decl.encode("utf-8"))

    try:
        # ===== 1) 先清空暫存表 =====
        logger.ctx.set_operation("truncate_tmp")
        logger.ctx.set_db(server=server, database=database, table=totb_tmp, operation="TRUNCATE")
        truncate_table(server, username, password, database, totb_tmp)
        logger.log_db_operation("TRUNCATE", database, totb_tmp, 0)

        # ===== 2) 下載 City/Area XML =====
        logger.ctx.set_operation("fetch_xml")
        start_time = time.time()
        logger.log_request("GET", XML_URL, None, None)

        resp = session.get(XML_URL, timeout=20)
        resp.raise_for_status()
        elapsed = time.time() - start_time

        logger.log_response(resp.status_code, dict(resp.headers), f"[XML: {len(resp.content)} bytes]", elapsed)

        root = parse_xml_with_encoding_fallback(resp.content)

        # 取所有城市
        cities = [{"city_id": c.get("ID"), "city_name": c.get("NAME")}
                  for c in root.findall(".//CITY")]
        logger.info(f"總縣市數：{len(cities)}")

        def areas_of(city_id: str):
            node = root.find(f".//CITY[@ID='{city_id}']/AREA")
            if node is None:
                return []
            return [{"area_id": a.get("ID"), "area_name": (a.text or '').strip()}
                    for a in node.findall(".//AREA")]

        # ===== 3) 呼叫段小段 API（回 HTML 片段） =====
        def fetch_sessions(city_id: str, area_id: str):
            headers = {
                "Origin": BASE,
                "Referer": REFERER,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            for attempt in range(1, 4):
                try:
                    start_time = time.time()
                    r = session.post(SESSION_URL, headers=headers,
                                     data={"city_id": city_id, "area_id": area_id},
                                     timeout=20)
                    r.raise_for_status()
                    elapsed = time.time() - start_time

                    soup = BeautifulSoup(r.text, "html.parser")
                    items = []
                    for div in soup.select(".session_list .session_name"):
                        items.append({
                            "ldcd": div.get("id"),
                            "ln": div.get("title"),
                            "s_name": div.get("name"),
                            "label": div.get_text(strip=True),
                        })
                    return items
                except Exception as e:
                    if attempt >= 3:
                        logger.warning(f"放棄 city={city_id} area={area_id} err={e}")
                        return []
                    time.sleep(1.0 * (2 ** (attempt - 1)))  # 指數退避

        # ===== 4) 全量迴圈 + 節流 + 批次寫入暫存表 =====
        buffer_rows = []
        nowstr = lambda: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        total_items = 0
        total_batches = 0

        for ci, c in enumerate(cities, 1):
            a_list = areas_of(c["city_id"])
            logger.log_progress(ci, len(cities), f"{c['city_name']}")
            logger.debug(f"[{ci}/{len(cities)}] {c['city_name']}({c['city_id']}) → 區數 {len(a_list)}")

            logger.ctx.set_operation("fetch_sessions")
            for aj, a in enumerate(a_list, 1):
                # 節流
                time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

                items = fetch_sessions(c["city_id"], a["area_id"])
                for it in items:
                    s_name = (it["s_name"] or "").replace('𠯿', '鹽')
                    isword = is_all_chinese(s_name)
                    row = (
                        c["city_id"],               # city_id
                        c["city_name"],             # city
                        a["area_id"],               # area_id
                        a["area_name"],             # area
                        it["ldcd"],                 # parcel_section_id
                        s_name,                     # parcel_section
                        isword,                     # isword
                        nowstr(),                   # updatetime
                    )
                    buffer_rows.append(row)
                    total_items += 1

                # 批次寫入暫存表
                if len(buffer_rows) >= BATCH:
                    logger.ctx.set_operation("batch_insert")
                    logger.ctx.set_db(server=server, database=database, table=totb_tmp, operation="INSERT")

                    docs = indata(buffer_rows)
                    toSQL(docs, totb_tmp, server, database, username, password)
                    total_batches += 1
                    logger.debug(f"批次寫入 {len(buffer_rows)} 筆 (batch #{total_batches})")
                    buffer_rows = []

        # 收尾：寫入殘餘批次
        if buffer_rows:
            logger.ctx.set_operation("batch_insert_final")
            logger.ctx.set_db(server=server, database=database, table=totb_tmp, operation="INSERT")

            docs = indata(buffer_rows)
            toSQL(docs, totb_tmp, server, database, username, password)
            total_batches += 1
            logger.debug(f"最終批次寫入 {len(buffer_rows)} 筆")

        logger.info(f"暫存表寫入完成: 共 {total_items} 筆, {total_batches} 批次")

        # ===== 5) MERGE：從暫存表寫入正式表（只新增，不更新）=====
        logger.ctx.set_operation("merge_table")
        logger.ctx.set_db(server=server, database=database, table=totb_target, operation="MERGE")

        overwrite(
            server, username, password, database,
            tmp_table=totb_tmp,
            target_table=totb_target,
            key_cols=('city_id', 'parcel_section_id'),
            update_when_matched=False
        )
        logger.log_db_operation("MERGE", database, totb_target, total_items)

        logger.log_stats({
            'total_cities': len(cities),
            'total_items': total_items,
            'total_batches': total_batches,
        })

        logger.info("更新完成")
        logger.task_end(success=True)
        return True

    except Exception as e:
        logger.log_exception(e, "執行過程發生錯誤")
        logger.task_end(success=False)
        return False


def main():
    """Main entry point"""
    logger.info(f"資料庫: {db['server']}.{db['database']}")
    logger.info(f"暫存表: {totb_tmp}")
    logger.info(f"目標表: {totb_target}")

    try:
        success = run()
        if success:
            logger.info("同步完成")
        else:
            logger.warning("同步失敗")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == "__main__":
    main()
