# -*- coding: utf-8 -*-
"""
ETL Functions for Court Auction Crawler
"""

import pymssql
import hashlib
import unicodedata
import re
from datetime import datetime
from typing import List, Dict, Optional


def src_obs(server, username, password, database, fromtb, totb):
    """Get count of records to process"""
    conn = pymssql.connect(server=server, user=username, password=password, database=database)
    cursor = conn.cursor()
    script = f"""
    SELECT COUNT(*) FROM (
        SELECT DISTINCT CONCAT(court,'_',number,'_',REPLACE(REPLACE(date,' ','_'),'/',''),'.pdf') as pdf_name
        FROM {totb}
    ) t
    """
    cursor.execute(script)
    obs = cursor.fetchall()
    cursor.close()
    conn.close()
    return list(obs[0])[0]


def get_existing_pdfs(server, username, password, database, totb):
    """Get list of existing PDF files from database"""
    try:
        conn = pymssql.connect(server=server, user=username, password=password, database=database)
        cursor = conn.cursor()
        script = f"""
        SELECT DISTINCT CONCAT(court,'_',number,'_',REPLACE(REPLACE(date,' ','_'),'/',''),'.pdf')
        FROM {totb}
        """
        cursor.execute(script)
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r[0] for r in results]
    except Exception as e:
        print(f"Error getting existing PDFs: {e}")
        return []


def generate_id(data: Dict) -> str:
    """Generate unique ID from data"""
    key_fields = ['court', 'number', 'date', 'owner', 'parcel']
    id_string = ''

    for field in key_fields:
        if field in data and data[field]:
            id_string += str(data[field])

    if not id_string:
        id_string = str(data)

    return hashlib.md5(id_string.encode('utf-8')).hexdigest()


def parse_tw_date(date_str: str) -> Optional[datetime]:
    """Parse Taiwan date format (ROC year)"""
    try:
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                year = int(parts[0]) + 1911 if int(parts[0]) < 1000 else int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                return datetime(year, month, day)
    except:
        pass
    return None


def normalize_text(text: str) -> str:
    """Normalize text - remove full-width characters and symbols"""
    if not text:
        return ""

    # Unicode normalization
    text = unicodedata.normalize('NFKC', text)

    # Full-width to half-width replacements
    replacements = {
        ',': ',', '.': '.', ';': ';', ':': ':',
        '?': '?', '!': '!', '"': '"', '"': '"',
        '(': '(', ')': ')', '[': '[', ']': ']',
        '{': '{', '}': '}', '<': '<', '>': '>',
        '、': ',', '‧': '.', '·': '.', '•': '.',
        '─': '-', '━': '-', '－': '-', '—': '-',
        '　': ' ', '\u3000': ' ', '\xa0': ' ',
    }

    for full_char, half_char in replacements.items():
        text = text.replace(full_char, half_char)

    # Remove control characters
    text = re.sub(r'[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202f]', '', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def auction_item(doc):
    """Build auction item dict"""
    return [{
        'rowid': doc.get('rowid', ''),
        'court': doc.get('court', ''),
        'number': doc.get('number', ''),
        'unit': doc.get('unit', ''),
        'date': doc.get('date', ''),
        'turn': doc.get('turn', ''),
        'country': doc.get('country', ''),
        'address': doc.get('address', ''),
        'reserve': doc.get('reserve', ''),
        'price': doc.get('price', ''),
        'handover': doc.get('handover', ''),
        'vacancy': doc.get('vacancy', ''),
        'target': doc.get('target', ''),
        'document': doc.get('document', ''),
        'remark': doc.get('remark', ''),
        'saletype': doc.get('saletype', ''),
        'proptype': doc.get('proptype', ''),
        'reserve_int': doc.get('reserve_int', 0),
        'date_datetime': doc.get('date_datetime'),
        'entrydate': doc.get('entrydate', datetime.now()),
    }]


def auction_info_item(doc):
    """Build auction info item dict"""
    return [{
        'rowid': doc.get('rowid', ''),
        'court': doc.get('court', ''),
        'number': doc.get('number', ''),
        'date': doc.get('date', ''),
        'country': doc.get('country', ''),
        'address': doc.get('address', ''),
        'owner': doc.get('owner', ''),
        'parcel': doc.get('parcel', ''),
        'area': doc.get('area', ''),
        'remark': doc.get('remark', ''),
        'refertb': doc.get('refertb', 'wbt_court_auction_tb'),
        'referi': doc.get('referi', ''),
        'entrydate': doc.get('entrydate', datetime.now()),
    }]


def toSQL(docs, totb, server, database, username, password):
    """Insert data to SQL database"""
    if not docs:
        return

    with pymssql.connect(server=server, user=username, password=password, database=database) as conn:
        with conn.cursor() as cursor:
            # Filter out None values and convert datetime
            for doc in docs:
                for key, val in doc.items():
                    if isinstance(val, datetime):
                        doc[key] = val.strftime("%Y/%m/%d %H:%M:%S")
                    elif val is None:
                        doc[key] = ''

            data_keys = ','.join(docs[0].keys())
            data_symbols = ','.join(['%s' for _ in docs[0].keys()])
            insert_cmd = f"INSERT INTO {totb} ({data_keys}) VALUES ({data_symbols})"
            data_values = [tuple(doc.values()) for doc in docs]
            cursor.executemany(insert_cmd, data_values)
        conn.commit()


def check_exists(server, username, password, database, totb, rowid):
    """Check if record already exists"""
    try:
        conn = pymssql.connect(server=server, user=username, password=password, database=database)
        cursor = conn.cursor()
        script = f"SELECT COUNT(*) FROM {totb} WHERE rowid = '{rowid}'"
        cursor.execute(script)
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] > 0
    except:
        return False


def exit_obs(server, username, password, database, totb):
    """Get count of records processed today"""
    conn = pymssql.connect(server=server, user=username, password=password, database=database)
    cursor = conn.cursor()
    script = f"""
    SELECT COUNT(DISTINCT rowid)
    FROM [{totb}]
    WHERE entrydate >= CONVERT(VARCHAR(10), GETDATE(), 111)
    """
    cursor.execute(script)
    obs = cursor.fetchall()
    cursor.close()
    conn.close()
    return list(obs[0])[0]
