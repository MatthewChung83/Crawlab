# -*- coding: utf-8 -*-
"""
ETL functions for Tfasc crawler
"""
import re
import os
import time
import datetime
import requests
import pymssql
import pyodbc
import chardet
import pandas
from datetime import datetime as dt
from bs4 import BeautifulSoup
from fpdf import FPDF

from config import db, wbinfo, doc_download


# ============================================================
# Database Functions
# ============================================================

def toSQL(docs, table, server, database, username, password):
    conn_cmd = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=' + server + ';DATABASE=' + database + ';UID=' + username + ';PWD=' + password
    with pyodbc.connect(conn_cmd) as cnxn:
        cnxn.autocommit = False
        with cnxn.cursor() as cursor:
            data_keys = ','.join(docs[0].keys())
            data_symbols = ','.join(['?' for _ in range(len(docs[0].keys()))])
            insert_cmd = """INSERT INTO {} ({})
            VALUES ({})""".format(table, data_keys, data_symbols)
            data_values = [tuple(doc.values()) for doc in docs]
            cursor.executemany(insert_cmd, data_values)
            cnxn.commit()


def exist_number(number, session):
    conn = pymssql.connect(server=db['server'], user=db['username'], password=db['password'], database=db['database'])
    cursor = conn.cursor()
    script = f"""
    select count(*) from tfasc_wbt_auction_tb
    where number = '{number}' and session = '{session}'
    """
    cursor.execute(script)
    counts = cursor.fetchall()
    cursor.close()
    conn.close()
    return counts[0][0]


def exist_auction():
    conn = pymssql.connect(server=db['server'], user=db['username'], password=db['password'], database=db['database'])
    cursor = conn.cursor()
    script = f"""select distinct auction_info_i from tfasc_auction_info_owner_tb"""
    cursor.execute(script)
    qry = cursor.fetchall()
    cursor.close()
    conn.close()

    exist_number = []
    for i in range(len(qry)):
        pdf = qry[i][0]
        exist_number.append(pdf)
    return exist_number


def dedup(data, dup_number_list, pkey):
    df = pandas.DataFrame(data).fillna('')
    dedup_df = df[-df[pkey].isin(dup_number_list)]
    return [v.to_dict() for _, v in dedup_df.iterrows()]


def dbfrom_doc_download(server, username, password, database, yesterday):
    """Get document list for download"""
    conn = pymssql.connect(server=server, user=username, password=password, database=database)
    cursor = conn.cursor()

    script = f"""
    select distinct
        auc.court + '_' + replace(convert(varchar(max), auc.number), '?', '') + '_' + auc.date + '.pdf' as a,
        tf.document
    from treasure.skiptrace.dbo.auction_info_tb auc
    inner join treasure.skiptrace.dbo.wbt_tfasc_auction_tb tf
        on auc.referi = tf.rowid
    where auc.entrydate >= '{yesterday}'
    """
    cursor.execute(script)
    c_src = cursor.fetchall()

    cursor.close()
    conn.close()
    return c_src


# ============================================================
# ETL Transform Functions
# ============================================================

def auction_info_owner_tb_etl(docs):
    """Transform data for auction_info_owner_tb"""
    auction_info_owner_tb_result = []
    index = 1

    for doc in docs:
        owner_ls = [_.strip('（） │|\r') for _ in doc['owner'].split('、') if _.strip('（） │|\r')]
        for owner in owner_ls:
            auction_info_owner_tb_result.append({
                "rowid": index,
                "auction_info_i": int(doc['estate_url'].split('id=')[1]),
                "owner": re.sub(r'（|）|\(|\)', '', owner.strip('()（） │|\r')),
                "owners_org": doc['owners_org'],
            })
            index += 1
    return auction_info_owner_tb_result


def auction_info_tb_etl(docs):
    """Transform data for auction_info_tb"""
    auction_info_tb_result = []
    index = 1
    for doc in docs:
        owner_ls = [_.strip('（） │|\r') for _ in doc['owner'].split('、') if _.strip('（） │|\r')]
        for owner in owner_ls:
            auction_info_tb_result.append({
                "rowid": index,
                "court": doc['court'],
                "number": doc['number'],
                "unit": doc.get('unit', ''),
                "date": doc['投標日期'],
                "turn": doc['拍次'],
                "country": doc.get('縣市', ''),
                "town": doc.get('鄉鎮市區', ''),
                "address": doc['address'],
                "area": doc['總面積(坪)(持分)'],
                "reserve": doc['reserve'],
                "price": doc.get('最低拍賣價格', ''),
                "remark": doc['remark'],
                "owners_org": doc['owners_org'],
                "owner": re.sub(r'（|）|\(|\)', '', owner.strip('()（） │|\r')),
                "entrydate": str(dt.now())[:-3],
                "refertb": "wbt_tfasc_auction_tb",
                "referi": int(doc['estate_url'].split('id=')[1]),
                "parcel": doc['parcel'],
            })
            index += 1
    return auction_info_tb_result


def wbt_tfasc_auction_tb_etl(docs):
    """Transform data for wbt_tfasc_auction_tb"""
    wbt_tfasc_auction_tb_result = []
    index = 1
    for doc in docs:
        wbt_tfasc_auction_tb_result.append({
            "rowid": int(doc['estate_url'].split('id=')[1]),
            "session": doc['session'],
            "date": doc['拍次'],
            "number": doc['number'],
            "address": doc['address'],
            "reserve": doc['reserve'],
            "deposit": "NULL",
            "price": "NULL",
            "target": "NULL",
            "auction": "NULL",
            "remark": doc['remark'],
            "document": doc['document'],
            "entrydate": str(dt.now())[:-3],
        })
        index += 1
    return wbt_tfasc_auction_tb_result


# ============================================================
# Document Download Functions (from Data-Tfasc_Doc_Download)
# ============================================================

class PDF(FPDF):
    pass


def http_get_bytes(url, timeout=None, retries=None):
    timeout = timeout or doc_download['timeout']
    retries = retries or doc_download['retries']
    last_exc = None
    for i in range(retries + 1):
        try:
            r = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=timeout,
                stream=True,
            )
            r.raise_for_status()
            raw = r.content
            return raw, r.headers.get("Content-Type", "")
        except Exception as e:
            last_exc = e
            if i < retries:
                time.sleep(1.5 * (i + 1))
            else:
                raise last_exc


def looks_like_pdf(raw: bytes) -> bool:
    return raw[:5] == b"%PDF-"


def content_is_text(content_type: str) -> bool:
    ct = (content_type or "").lower()
    return ("text" in ct) or ("json" in ct) or ("xml" in ct)


def codecs_normalize(name: str) -> str:
    n = (name or "").lower()
    mapping = {
        "utf8": "utf-8",
        "big-5": "big5",
        "ansi_x3.4-1968": "latin1",
    }
    return mapping.get(n, n)


def bytes_to_text(raw: bytes) -> str:
    det = chardet.detect(raw)
    enc = (det.get("encoding") or "").strip()
    conf = det.get("confidence", 0)
    print(f"[INFO] chardet -> encoding={enc}, confidence={conf}")

    candidates = []

    if enc:
        if enc.lower() in ("big5", "big-5", "ansi_x3.4-1968"):
            candidates += ["big5-hkscs", "cp950", "big5"]
        else:
            candidates.append(enc)

    candidates += ["utf-8", "cp950", "big5-hkscs", "big5", "latin1"]

    tried = set()
    for codec in candidates:
        codec = codec.lower()
        if codec in tried:
            continue
        tried.add(codec)
        try:
            return raw.decode(codecs_normalize(codec), errors="strict")
        except Exception:
            continue

    fallback = codecs_normalize(enc or "utf-8")
    print(f"[WARN] all strict decodes failed, fallback with errors='replace' using {fallback}")
    return raw.decode(fallback, errors="replace")


def save_bytes(path: str, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def text_to_pdf(text: str, out_pdf: str, font_path: str = None):
    font_path = font_path or doc_download['font_path']
    if not os.path.isfile(font_path):
        raise FileNotFoundError(
            f"Font not found: {font_path}\n"
            "請確認字型檔存在，或修改 doc_download['font_path'] 指向可用的中文字型 (TTF)。"
        )

    pdf = PDF()
    pdf.add_page()
    pdf.add_font("CustomFont", "", font_path, uni=True)
    pdf.set_font("CustomFont", size=12)

    line_height = 8
    for line in text.splitlines():
        if not line.strip():
            pdf.ln(line_height)
            continue
        pdf.multi_cell(0, line_height, line)

    pdf.output(out_pdf)
    print(f"[OK] Saved PDF: {out_pdf}")


def download_document(url: str, out_pdf: str):
    """Download document and save as PDF"""
    raw, content_type = http_get_bytes(url)
    print(f"[INFO] Content-Type: {content_type}")

    if looks_like_pdf(raw) or ("application/pdf" in (content_type or "").lower()):
        os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
        save_bytes(out_pdf, raw)
        print(f"[OK] Detected PDF. Saved directly: {out_pdf}")
        return

    try:
        text = bytes_to_text(raw)
    except Exception as e:
        print(f"[WARN] decode strict failed: {e}")
        det = chardet.detect(raw)
        enc = det.get("encoding") or "utf-8"
        text = raw.decode(codecs_normalize(enc), errors="replace")

    text_to_pdf(text, out_pdf)
