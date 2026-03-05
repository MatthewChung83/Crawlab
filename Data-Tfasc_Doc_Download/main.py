import os
import sys
import time
import datetime
import requests
import pymssql
import chardet
from fpdf import FPDF
from pathlib import Path

# ==== 設定區 ====
FONT_PATH = r"NotoSansTC-Regular.ttf"   # 請放一個支援中文的 TTF
OUT_PUT_DIR = '/tmp/WBT'
TIMEOUT = 20
RETRIES = 2
server = "10.10.0.94"
database = "CL_Daily"
username = "CLUSER"
password = "Ucredit7607"
# ==============

class PDF(FPDF):
    pass

def http_get_bytes(url, timeout=TIMEOUT, retries=RETRIES):
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
    # PDF 都是以 %PDF- 開頭
    return raw[:5] == b"%PDF-"

def content_is_text(content_type: str) -> bool:
    ct = (content_type or "").lower()
    return ("text" in ct) or ("json" in ct) or ("xml" in ct)

def bytes_to_text(raw: bytes) -> str:
    # 先用 chardet 偵測
    det = chardet.detect(raw)
    enc = (det.get("encoding") or "").strip()
    conf = det.get("confidence", 0)
    print(f"[INFO] chardet -> encoding={enc}, confidence={conf}")

    # 主要與備援嘗試清單
    candidates = []

    if enc:
        if enc.lower() in ("big5", "big-5", "ansi_x3.4-1968"):  # 後者是偶爾的誤判
            # 針對繁中常見編碼，給一組保險候選
            candidates += ["big5-hkscs", "cp950", "big5"]
        else:
            candidates.append(enc)

    # 常見備援
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

    # 全部失敗就保底，用偵測編碼或 utf-8，但以 replace 兜住
    fallback = codecs_normalize(enc or "utf-8")
    print(f"[WARN] all strict decodes failed, fallback with errors='replace' using {fallback}")
    return raw.decode(fallback, errors="replace")

def codecs_normalize(name: str) -> str:
    """
    將某些系統差異的名稱統一化。
    """
    n = (name or "").lower()
    mapping = {
        "utf8": "utf-8",
        "big-5": "big5",
        "ansi_x3.4-1968": "latin1",   # chardet 偶爾誤判成 ASCII 的老名稱
    }
    return mapping.get(n, n)

def save_bytes(path: str, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

def text_to_pdf(text: str, out_pdf: str, font_path: str = FONT_PATH):
    if not os.path.isfile(font_path):
        raise FileNotFoundError(
            f"Font not found: {font_path}\n"
            "請確認字型檔存在，或修改 FONT_PATH 指向可用的中文字型 (TTF)。"
        )

    pdf = PDF()
    pdf.add_page()
    # 重要：中文要 uni=True 才能正確嵌入字型與顯示
    pdf.add_font("CustomFont", "", font_path, uni=True)
    pdf.set_font("CustomFont", size=12)

    # 用 multi_cell 自動換行，避免自行硬切字導致半形/全形分裂
    line_height = 8
    for line in text.splitlines():
        if not line.strip():
            pdf.ln(line_height)
            continue
        pdf.multi_cell(0, line_height, line)

    pdf.output(out_pdf)
    print(f"[OK] Saved PDF: {out_pdf}")

def main(url: str, out_pdf: str):
    raw, content_type = http_get_bytes(url)
    print(f"[INFO] Content-Type: {content_type}")

    if looks_like_pdf(raw) or ("application/pdf" in (content_type or "").lower()):
        # 直接輸出 PDF
        os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
        save_bytes(out_pdf, raw)
        print(f"[OK] Detected PDF. Saved directly: {out_pdf}")
        return

    # 若標示是文字，或未標示但不像 PDF，就嘗試解碼為文字
    try:
        text = bytes_to_text(raw)
    except Exception as e:
        # 仍無法穩定解碼 -> 最後嘗試以替換模式解
        print(f"[WARN] decode strict failed: {e}")
        det = chardet.detect(raw)
        enc = det.get("encoding") or "utf-8"
        text = raw.decode(codecs_normalize(enc), errors="replace")

    # 產生 PDF
    text_to_pdf(text, out_pdf)


def dbfrom(server, username, password, database, yesterday):
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







if __name__ == "__main__":
    
    yesterday = datetime.date.today() + datetime.timedelta(days=-10)
    src_list = dbfrom(server, username, password, database, yesterday)
    for filename, url in src_list:
        full_path = os.path.join(OUT_PUT_DIR, filename)
        try:
            main(url, full_path)
            print(full_path)
        except Exception as e:
            #print(f"[ERROR] {e}")
            sys.exit(1)
