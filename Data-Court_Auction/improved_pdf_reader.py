#!/usr/bin/env python3
"""
改進版 PDF 解析器
特點:
1. 更精準的文字標準化處理
2. 去除全形字元和符號
3. 改善所有權人和地號解析邏輯
4. 更好的錯誤處理
"""

import pdfplumber
import re
import unicodedata
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ImprovedPDFReader:
    """改進版 PDF 讀取器"""
    
    def __init__(self, file_path: str):
        """初始化 PDF 讀取器
        
        Args:
            file_path: PDF 檔案路徑
        """
        self.file_path = file_path
        self.file = None
        
        try:
            self.file = pdfplumber.open(file_path)
        except Exception as e:
            logger.error(f"開啟PDF檔案失敗: {e}")
            raise
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()
    
    def normalize_text(self, text: str) -> str:
        """標準化文字，去除全形字元和符號
        
        Args:
            text: 原始文字
            
        Returns:
            標準化後的文字
        """
        if not text:
            return ""
            
        # Unicode 正規化 (NFKC: 相容性分解後重新組合)
        text = unicodedata.normalize('NFKC', text)
        
        # 全形轉半形的更精確處理
        replacements = {
            # 標點符號
            '，': ',',
            '。': '.',
            '；': ';',
            '：': ':',
            '？': '?',
            '！': '!',
            '「': '"',
            '」': '"',
            '『': '"',
            '』': '"',
            '（': '(',
            '）': ')',
            '［': '[',
            '］': ']',
            '｛': '{',
            '｝': '}',
            '＜': '<',
            '＞': '>',
            
            # 常用符號
            '、': ',',
            '‧': '.',
            '·': '.',
            '•': '.',
            '◦': '.',
            '∙': '.',
            
            # 破折號和連字號
            '─': '-',
            '━': '-',
            '－': '-',
            '—': '-',
            '–': '-',
            
            # 空白字元
            '　': ' ',  # 全形空白
            '\u3000': ' ',  # 全形空白
            '\xa0': ' ',  # 不換行空白
            '\u2000': ' ',  # en quad
            '\u2001': ' ',  # em quad
            '\u2002': ' ',  # en space
            '\u2003': ' ',  # em space
            '\u2004': ' ',  # three-per-em space
            '\u2005': ' ',  # four-per-em space
            '\u2006': ' ',  # six-per-em space
            '\u2007': ' ',  # figure space
            '\u2008': ' ',  # punctuation space
            '\u2009': ' ',  # thin space
            '\u200a': ' ',  # hair space
            '\u202f': ' ',  # narrow no-break space
            '\u205f': ' ',  # medium mathematical space
        }
        
        for full_char, half_char in replacements.items():
            text = text.replace(full_char, half_char)
        
        # 移除控制字元和格式字元
        text = re.sub(r'[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202f]', '', text)
        
        # 標準化連續空白和換行
        text = re.sub(r'\s+', ' ', text)
        
        # 移除行首行尾空白
        text = text.strip()
        
        return text
    
    def extract_owners_improved(self, text: str) -> List[str]:
        """改進版所有權人提取
        
        Args:
            text: 包含所有權人資訊的文字
            
        Returns:
            所有權人清單
        """
        if '財產所有人：' not in text:
            return []
        
        # 提取所有權人部分
        owner_text = text.split('財產所有人：')[-1]
        
        # 標準化文字
        owner_text = self.normalize_text(owner_text)
        
        # 移除常見的描述詞和符號
        remove_patterns = [
            r'權利範圍[^,，]*',
            r'應有[^,，]*',
            r'均為[^,，]*',
            r'之繼承人',
            r'繼承人',
            r'之遺產管理人',
            r'遺產管理人',
            r'之限定繼承人',
            r'限定繼承人',
            r'之有限責任繼承人',
            r'有限責任繼承人',
            r'之律師',
            r'律師',
            r'之清算管理人',
            r'清算管理人',
            r'原名[^,，]*',
            r'歿',
            r'\d+分之\d+',
            r'[0-9]+\/[0-9]+',
        ]
        
        for pattern in remove_patterns:
            owner_text = re.sub(pattern, '', owner_text, flags=re.IGNORECASE)
        
        # 使用多種分隔符號分割
        separators = ['兼', '即', '、', ',', '，', ' ', ':', '：', '。', '.', ';', '；']
        
        # 逐個使用分隔符號
        owners = [owner_text]
        for sep in separators:
            new_owners = []
            for owner in owners:
                new_owners.extend(owner.split(sep))
            owners = new_owners
        
        # 清理和過濾結果
        cleaned_owners = []
        for owner in owners:
            owner = self.normalize_text(owner)
            
            # 過濾掉無效的項目
            if (owner and 
                len(owner.strip()) > 1 and 
                not re.match(r'^[\d\s\-\/]+$', owner) and  # 純數字或符號
                not owner.startswith('第') and
                not owner.endswith('拍') and
                owner not in ['之', '及', '與', '或', '等']):
                cleaned_owners.append(owner.strip())
        
        # 去重並保持順序
        unique_owners = []
        seen = set()
        for owner in cleaned_owners:
            if owner not in seen:
                unique_owners.append(owner)
                seen.add(owner)
        
        return unique_owners
    
    def extract_parcels_improved(self, table_rows: List[List]) -> List[Dict]:
        """改進版地號提取
        
        Args:
            table_rows: 表格行資料
            
        Returns:
            地號資訊清單
        """
        parcels = []
        parcels_tmp = []
        
        for row in table_rows:
            # 過濾掉 None 值
            row = [self.normalize_text(str(cell)) if cell else '' for cell in row if cell is not None]
            
            if len(row) < 3:
                continue
            
            # 檢查是否為地號資料行 (第一欄為數字)
            if row[0].isdigit() and len(row) > 2:
                if '----------' not in row[2] and '、' not in row[2]:
                    # 標準格式: ['1', '新北市', '淡水區', '坪頂', '', '248', '1.12', '1分之1', '70,000元']
                    if len(row) >= 6:
                        country = self.normalize_text(row[1]).replace('臺', '台')
                        district = self.normalize_text(row[2]) if len(row) > 2 else ''
                        
                        # 組合地段資訊
                        parcel_parts = []
                        for i, suffix in enumerate(['段', '小段', '地號']):
                            if i + 3 < len(row) and row[i + 3]:
                                part = self.normalize_text(row[i + 3])
                                if part:
                                    parcel_parts.append(part + suffix)
                        
                        if parcel_parts:
                            parcel_name = country + district + ''.join(parcel_parts)
                            
                            # 面積資訊
                            area_info = ''
                            if len(row) >= 8:
                                area_parts = [self.normalize_text(row[6]), self.normalize_text(row[7])]
                                area_info = ' x '.join(filter(None, area_parts))
                            
                            parcel = {
                                'parcel': parcel_name,
                                'area': area_info
                            }
                            
                            if parcel not in parcels:
                                parcels.append(parcel)
                else:
                    # 複雜格式處理
                    if len(row) >= 3:
                        parcel_text = self.normalize_text(row[2])
                        
                        # 分割地址和地號
                        if '--------------' in parcel_text:
                            parcel_part = parcel_text.split('--------------')[0]
                        else:
                            parcel_part = parcel_text
                        
                        # 處理多個地號 (用、分隔)
                        if '、' in parcel_part:
                            self._process_multiple_parcels(parcel_part, parcels_tmp)
                        else:
                            if parcel_part.strip():
                                parcels_tmp.append({'parcel': parcel_part.strip()})
        
        # 如果標準格式沒有資料，使用備用格式
        if not parcels and parcels_tmp:
            parcels = parcels_tmp
        
        return parcels
    
    def _process_multiple_parcels(self, parcel_text: str, parcels_list: List[Dict]):
        """處理多個地號的情況"""
        parts = parcel_text.split('、')
        
        if len(parts) < 2:
            return
        
        # 第一個地號 (完整地址)
        first_parcel = parts[0] + '地號'
        if first_parcel not in [p['parcel'] for p in parcels_list]:
            parcels_list.append({'parcel': first_parcel})
        
        # 找出共同前綴 (通常是地段名稱)
        common_prefix = ''
        if '段' in parts[0]:
            common_prefix = parts[0].split('段')[0] + '段'
        
        # 處理後續地號
        for part in parts[1:]:
            part = part.strip()
            if part:
                if '地號' in part:
                    full_parcel = common_prefix + part if common_prefix else part
                else:
                    full_parcel = common_prefix + part + '地號' if common_prefix else part + '地號'
                
                if full_parcel not in [p['parcel'] for p in parcels_list]:
                    parcels_list.append({'parcel': full_parcel})
    
    def extract(self) -> List[Dict]:
        """主要提取方法
        
        Returns:
            提取的資料清單
        """
        if not self.file:
            logger.error("PDF檔案未正確開啟")
            return []
        
        owners = []
        parcels = []
        remarks = []
        
        try:
            for page_num, page in enumerate(self.file.pages, 1):
                logger.debug(f"處理第 {page_num} 頁")
                
                # 提取文字內容
                page_text = page.extract_text() or ""
                page_text = self.normalize_text(page_text)
                
                # 提取所有權人 (如果還沒找到)
                if not owners and '財產所有人：' in page_text:
                    owners = self.extract_owners_improved(page_text)
                    logger.debug(f"找到 {len(owners)} 個所有權人: {owners}")
                
                # 提取表格資料
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        # 提取地號資訊
                        page_parcels = self.extract_parcels_improved(table)
                        parcels.extend(page_parcels)
                        
                        # 提取備註資訊
                        for row in table:
                            if row and len(row) > 1:
                                # 檢查是否為備註行
                                if (isinstance(row[1], str) and 
                                    len(row[1]) > 10 and 
                                    any(keyword in row[1] for keyword in ['鋼筋', '混凝土', '層', '面積'])):
                                    
                                    remark = self.normalize_text(row[1].replace('\n', ''))
                                    if remark and remark not in remarks:
                                        remarks.append(remark)
            
            logger.debug(f"解析完成: {len(owners)} 個所有權人, {len(parcels)} 個地號")
            
            # 組合結果
            output = []
            
            # 如果沒有找到所有權人，至少產生一個空的項目
            if not owners:
                owners = ['']
            
            # 如果沒有找到地號，至少產生一個空的項目
            if not parcels:
                parcels = [{'parcel': '', 'area': ''}]
            
            # 產生笛卡爾積
            for owner in owners:
                for parcel in parcels:
                    output.append({
                        'owner': self.normalize_text(owner),
                        'parcel': self.normalize_text(parcel.get('parcel', '')),
                        'area': self.normalize_text(parcel.get('area', '')),
                        'remark': '; '.join(remarks) if remarks else ''
                    })
            
            return output
            
        except Exception as e:
            logger.error(f"PDF內容提取失敗: {e}")
            return []


# 向後相容的類別名稱
class PDFReader(ImprovedPDFReader):
    """向後相容的類別名稱"""
    pass


def test_pdf_reader(pdf_path: str):
    """測試 PDF 讀取器"""
    try:
        with ImprovedPDFReader(pdf_path) as reader:
            results = reader.extract()
            
            print(f"解析結果:")
            print(f"總共 {len(results)} 筆資料")
            
            for i, item in enumerate(results, 1):
                print(f"\n第 {i} 筆:")
                for key, value in item.items():
                    print(f"  {key}: {value}")
                    
    except Exception as e:
        print(f"測試失敗: {e}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        test_pdf_reader(sys.argv[1])
    else:
        print("使用方法: python improved_pdf_reader.py <PDF檔案路徑>")