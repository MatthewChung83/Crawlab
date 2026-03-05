# main_etl_land_parcel_section.py

import re
import time
import random
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

# === 你的工具函式（已換成參數化版） ===
from etl_func import indata, toSQL, truncate_table, overwrite, is_all_chinese
from config import *

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

# ===== 1) 先清空暫存表 =====
truncate_table(server, username, password, database, totb_tmp)

# ===== 2) 下載 City/Area XML =====
resp = session.get(XML_URL, timeout=20)
resp.raise_for_status()
root = parse_xml_with_encoding_fallback(resp.content)

# 取所有城市
cities = [{"city_id": c.get("ID"), "city_name": c.get("NAME")}
          for c in root.findall(".//CITY")]

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
            r = session.post(SESSION_URL, headers=headers,
                             data={"city_id": city_id, "area_id": area_id},
                             timeout=20)
            r.raise_for_status()
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
                print(f"  ✗ 放棄 city={city_id} area={area_id} err={e}")
                return []
            time.sleep(1.0 * (2 ** (attempt - 1)))  # 指數退避

# ===== 4) 全量迴圈 + 節流 + 批次寫入暫存表 =====
buffer_rows = []
nowstr = lambda: time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

print(f"總縣市數：{len(cities)}")
for ci, c in enumerate(cities, 1):
    a_list = areas_of(c["city_id"])
    print(f"[{ci}/{len(cities)}] {c['city_name']}({c['city_id']}) → 區數 {len(a_list)}")
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

        # 批次寫入暫存表
        if len(buffer_rows) >= BATCH:
            docs = indata(buffer_rows)                      # list[tuple]
            toSQL(docs, totb_tmp, server, database, username, password)
            buffer_rows = []

# 收尾：寫入殘餘批次
if buffer_rows:
    docs = indata(buffer_rows)
    toSQL(docs, totb_tmp, server, database, username, password)

# ===== 5) MERGE：從暫存表寫入正式表（只新增，不更新）=====
overwrite(
    server, username, password, database,
    tmp_table=totb_tmp,
    target_table=totb_target,
    key_cols=('city_id', 'parcel_section_id'),
    update_when_matched=False
)

print("更新完成")
