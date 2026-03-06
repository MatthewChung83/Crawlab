# -*- coding: utf-8 -*-
"""
Crawlab Unified Logger Module
統一 Log 模組 - 提供完整的錯誤追蹤與診斷功能

Features:
- 多層級 Log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- 自動 Stack Trace 捕獲
- HTTP 請求/回應完整記錄
- 資料庫操作追蹤
- 處理進度追蹤
- 錯誤上下文記錄
- 重試機制追蹤
- 統計資訊彙整
- 檔案 + Console 雙輸出
- JSON 格式 Log (可選)
"""

import logging
import sys
import os
import traceback
import json
import datetime
from functools import wraps
from typing import Any, Dict, Optional, Union, Callable
from pathlib import Path


class ErrorContext:
    """錯誤上下文 - 記錄錯誤發生時的完整資訊"""

    def __init__(self):
        self.current_operation: str = ""
        self.current_data: Dict[str, Any] = {}
        self.retry_count: int = 0
        self.max_retries: int = 0
        self.request_info: Dict[str, Any] = {}
        self.response_info: Dict[str, Any] = {}
        self.db_info: Dict[str, Any] = {}
        self.progress: Dict[str, Any] = {}

    def set_operation(self, operation: str):
        """設定當前操作"""
        self.current_operation = operation

    def set_data(self, **kwargs):
        """設定當前處理的資料"""
        self.current_data = kwargs

    def set_retry(self, current: int, max_retries: int):
        """設定重試資訊"""
        self.retry_count = current
        self.max_retries = max_retries

    def set_request(self, method: str = "", url: str = "",
                    headers: Dict = None, body: Any = None):
        """設定 HTTP 請求資訊"""
        self.request_info = {
            'method': method,
            'url': url,
            'headers': self._safe_headers(headers),
            'body': self._truncate(body, 2000)
        }

    def set_response(self, status_code: int = 0, headers: Dict = None,
                     body: Any = None, elapsed: float = 0):
        """設定 HTTP 回應資訊"""
        self.response_info = {
            'status_code': status_code,
            'headers': self._safe_headers(headers),
            'body': self._truncate(body, 2000),
            'elapsed_seconds': elapsed
        }

    def set_db(self, server: str = "", database: str = "",
               table: str = "", operation: str = "", rows: int = 0):
        """設定資料庫操作資訊"""
        self.db_info = {
            'server': server,
            'database': database,
            'table': table,
            'operation': operation,
            'rows_affected': rows
        }

    def set_progress(self, current: int, total: int, item: str = ""):
        """設定處理進度"""
        self.progress = {
            'current': current,
            'total': total,
            'percentage': round(current / total * 100, 2) if total > 0 else 0,
            'current_item': item
        }

    def _safe_headers(self, headers: Dict) -> Dict:
        """過濾敏感 header 資訊"""
        if not headers:
            return {}
        sensitive_keys = ['authorization', 'cookie', 'set-cookie', 'x-api-key', 'password']
        return {
            k: '***HIDDEN***' if k.lower() in sensitive_keys else v
            for k, v in dict(headers).items()
        }

    def _truncate(self, data: Any, max_len: int) -> str:
        """截斷過長的資料"""
        if data is None:
            return ""
        text = str(data)
        if len(text) > max_len:
            return text[:max_len] + f"... (truncated, total {len(text)} chars)"
        return text

    def to_dict(self) -> Dict:
        """轉換為字典格式"""
        return {
            'operation': self.current_operation,
            'data': self.current_data,
            'retry': {
                'current': self.retry_count,
                'max': self.max_retries
            } if self.max_retries > 0 else None,
            'request': self.request_info if self.request_info else None,
            'response': self.response_info if self.response_info else None,
            'db': self.db_info if self.db_info else None,
            'progress': self.progress if self.progress else None
        }

    def clear(self):
        """清除所有上下文"""
        self.__init__()


class CrawlabLogger:
    """
    Crawlab 統一 Logger

    Usage:
        from common.logger import get_logger

        logger = get_logger('Data-Insurance')

        # 基本 Log
        logger.info("開始執行")
        logger.debug("除錯訊息")
        logger.warning("警告訊息")
        logger.error("錯誤訊息")

        # 帶上下文的 Log
        logger.ctx.set_operation("fetch_data")
        logger.ctx.set_progress(1, 100, "item_001")
        logger.info("處理中...")

        # HTTP 請求追蹤
        logger.log_request("POST", url, headers, body)
        logger.log_response(resp.status_code, resp.headers, resp.text, elapsed)

        # 資料庫操作追蹤
        logger.log_db_operation("INSERT", "CL_Daily", "table_name", 100)

        # 錯誤追蹤 (自動捕獲 stack trace)
        try:
            ...
        except Exception as e:
            logger.log_exception(e, "處理資料時發生錯誤")

        # 任務統計
        logger.log_stats({
            'total_records': 1000,
            'success': 980,
            'failed': 20,
            'duration_seconds': 120
        })
    """

    _instances: Dict[str, 'CrawlabLogger'] = {}

    def __new__(cls, module_name: str, log_dir: str = None,
                json_format: bool = False, debug: bool = False):
        """單例模式 - 每個模組只有一個 logger 實例"""
        if module_name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[module_name] = instance
        return cls._instances[module_name]

    def __init__(self, module_name: str, log_dir: str = None,
                 json_format: bool = False, debug: bool = False):
        """
        初始化 Logger

        Args:
            module_name: 模組名稱 (例如: Data-Insurance)
            log_dir: Log 檔案存放目錄 (預設為模組目錄下的 logs/)
            json_format: 是否使用 JSON 格式輸出
            debug: 是否啟用 DEBUG 模式
        """
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.module_name = module_name
        self.json_format = json_format
        self.ctx = ErrorContext()
        self.start_time: Optional[datetime.datetime] = None
        self.stats: Dict[str, Any] = {}

        # 設定 Log 目錄
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            # 預設在模組目錄下建立 logs 資料夾
            self.log_dir = Path(os.getcwd()) / 'logs'

        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 建立 logger
        self.logger = logging.getLogger(f'crawlab.{module_name}')
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)
        self.logger.handlers = []  # 清除既有 handlers

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if debug else logging.INFO)

        # File Handler - 一般 Log
        today = datetime.date.today().strftime('%Y%m%d')
        log_file = self.log_dir / f'{module_name}_{today}.log'
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)

        # Error File Handler - 只記錄錯誤
        error_log_file = self.log_dir / f'{module_name}_{today}_error.log'
        error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)

        # 設定格式
        if json_format:
            formatter = JsonFormatter(module_name)
        else:
            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)

        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)

    # ========== 基本 Log 方法 ==========

    def debug(self, msg: str, **kwargs):
        """DEBUG 級別 Log"""
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        """INFO 級別 Log"""
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """WARNING 級別 Log"""
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs):
        """ERROR 級別 Log"""
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        """CRITICAL 級別 Log"""
        self._log(logging.CRITICAL, msg, **kwargs)

    def _log(self, level: int, msg: str, **kwargs):
        """內部 Log 方法"""
        extra = {'context': self.ctx.to_dict(), **kwargs}

        if self.json_format:
            self.logger.log(level, msg, extra={'extra_data': extra})
        else:
            # 如果有額外資訊，附加在訊息後面
            if kwargs:
                extra_str = ' | '.join(f'{k}={v}' for k, v in kwargs.items())
                msg = f'{msg} | {extra_str}'
            self.logger.log(level, msg)

    # ========== 任務生命週期 ==========

    def task_start(self, task_name: str = None):
        """記錄任務開始"""
        self.start_time = datetime.datetime.now()
        self.stats = {
            'task_name': task_name or self.module_name,
            'start_time': self.start_time.isoformat(),
            'records_processed': 0,
            'records_success': 0,
            'records_failed': 0,
            'errors': []
        }
        self.info(f"{'='*60}")
        self.info(f"任務開始: {task_name or self.module_name}")
        self.info(f"開始時間: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.info(f"{'='*60}")

    def task_end(self, success: bool = True):
        """記錄任務結束"""
        end_time = datetime.datetime.now()
        duration = (end_time - self.start_time).total_seconds() if self.start_time else 0

        self.stats['end_time'] = end_time.isoformat()
        self.stats['duration_seconds'] = duration
        self.stats['success'] = success

        self.info(f"{'='*60}")
        self.info(f"任務結束: {'成功' if success else '失敗'}")
        self.info(f"結束時間: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.info(f"執行時間: {duration:.2f} 秒")

        if self.stats.get('records_processed', 0) > 0:
            self.info(f"處理筆數: {self.stats['records_processed']}")
            self.info(f"成功筆數: {self.stats['records_success']}")
            self.info(f"失敗筆數: {self.stats['records_failed']}")

        if self.stats.get('errors'):
            self.warning(f"錯誤總數: {len(self.stats['errors'])}")

        self.info(f"{'='*60}")

        return self.stats

    # ========== HTTP 追蹤 ==========

    def log_request(self, method: str, url: str,
                    headers: Dict = None, body: Any = None):
        """記錄 HTTP 請求"""
        self.ctx.set_request(method, url, headers, body)
        self.debug(f"HTTP 請求: {method} {url}")
        if body and self.logger.level == logging.DEBUG:
            self.debug(f"請求內容: {self.ctx.request_info['body']}")

    def log_response(self, status_code: int, headers: Dict = None,
                     body: Any = None, elapsed: float = 0):
        """記錄 HTTP 回應"""
        self.ctx.set_response(status_code, headers, body, elapsed)

        level = logging.DEBUG if 200 <= status_code < 300 else logging.WARNING
        self.logger.log(level,
            f"HTTP 回應: {status_code} | 耗時: {elapsed:.3f}s")

        if status_code >= 400:
            self.warning(f"回應標頭: {self.ctx.response_info['headers']}")
            self.warning(f"回應內容: {self.ctx.response_info['body']}")

    def log_http_error(self, error: Exception, url: str, retry: int = 0):
        """記錄 HTTP 錯誤"""
        error_info = {
            'type': type(error).__name__,
            'message': str(error),
            'url': url,
            'retry': retry,
            'request': self.ctx.request_info,
            'response': self.ctx.response_info
        }

        self.error(f"HTTP 錯誤: {type(error).__name__}: {error}")
        self.error(f"請求 URL: {url}")

        if self.ctx.request_info:
            self.error(f"請求方法: {self.ctx.request_info.get('method', 'N/A')}")
            self.error(f"請求標頭: {self.ctx.request_info.get('headers', {})}")

        if self.ctx.response_info:
            self.error(f"回應狀態: {self.ctx.response_info.get('status_code', 'N/A')}")
            self.error(f"回應內容: {self.ctx.response_info.get('body', '')}")

        self.stats.setdefault('errors', []).append(error_info)

    # ========== 資料庫追蹤 ==========

    def log_db_connect(self, server: str, database: str, user: str = None):
        """記錄資料庫連線"""
        self.ctx.set_db(server=server, database=database)
        self.info(f"資料庫連線: {server}/{database}" +
                  (f" (user: {user})" if user else ""))

    def log_db_operation(self, operation: str, database: str,
                         table: str, rows: int = 0):
        """記錄資料庫操作"""
        self.ctx.set_db(database=database, table=table,
                        operation=operation, rows=rows)
        self.info(f"資料庫 {operation}: {database}.{table} | 影響筆數: {rows}")

    def log_db_error(self, error: Exception, operation: str = "",
                     sql: str = None):
        """記錄資料庫錯誤"""
        error_info = {
            'type': type(error).__name__,
            'message': str(error),
            'operation': operation,
            'db_info': self.ctx.db_info,
            'sql': sql[:500] if sql else None  # 截斷過長的 SQL
        }

        self.error(f"資料庫錯誤: {type(error).__name__}: {error}")
        self.error(f"操作類型: {operation}")

        if self.ctx.db_info:
            self.error(f"資料庫: {self.ctx.db_info.get('database', 'N/A')}")
            self.error(f"資料表: {self.ctx.db_info.get('table', 'N/A')}")

        if sql:
            self.error(f"SQL 語句: {sql[:500]}")

        self.stats.setdefault('errors', []).append(error_info)

    # ========== 進度追蹤 ==========

    def log_progress(self, current: int, total: int, item: str = ""):
        """記錄處理進度"""
        self.ctx.set_progress(current, total, item)
        percentage = current / total * 100 if total > 0 else 0

        # 每 10% 或特定筆數輸出一次進度
        if current == 1 or current == total or current % max(1, total // 10) == 0:
            self.info(f"處理進度: {current}/{total} ({percentage:.1f}%)" +
                     (f" | 當前: {item}" if item else ""))

    def log_batch(self, batch_num: int, batch_size: int,
                  success: int, failed: int):
        """記錄批次處理結果"""
        self.info(f"批次 {batch_num}: 大小={batch_size} | "
                 f"成功={success} | 失敗={failed}")

        self.stats['records_processed'] = self.stats.get('records_processed', 0) + batch_size
        self.stats['records_success'] = self.stats.get('records_success', 0) + success
        self.stats['records_failed'] = self.stats.get('records_failed', 0) + failed

    # ========== 重試追蹤 ==========

    def log_retry(self, attempt: int, max_attempts: int,
                  reason: str, wait_seconds: float = 0):
        """記錄重試"""
        self.ctx.set_retry(attempt, max_attempts)
        self.warning(f"重試 {attempt}/{max_attempts}: {reason}" +
                    (f" | 等待 {wait_seconds}s" if wait_seconds > 0 else ""))

    def log_retry_exhausted(self, operation: str, attempts: int):
        """記錄重試耗盡"""
        self.error(f"重試耗盡: {operation} | 已嘗試 {attempts} 次")
        self.stats.setdefault('errors', []).append({
            'type': 'RetryExhausted',
            'operation': operation,
            'attempts': attempts,
            'context': self.ctx.to_dict()
        })

    # ========== 例外追蹤 ==========

    def log_exception(self, error: Exception, message: str = "",
                      include_locals: bool = False):
        """
        記錄例外 - 包含完整 stack trace

        Args:
            error: 例外物件
            message: 額外說明訊息
            include_locals: 是否包含區域變數 (僅 DEBUG 模式)
        """
        error_info = {
            'type': type(error).__name__,
            'message': str(error),
            'description': message,
            'stack_trace': traceback.format_exc(),
            'context': self.ctx.to_dict(),
            'timestamp': datetime.datetime.now().isoformat()
        }

        self.error(f"{'='*60}")
        self.error(f"例外發生: {type(error).__name__}")
        if message:
            self.error(f"說明: {message}")
        self.error(f"錯誤訊息: {error}")
        self.error(f"----- Stack Trace -----")

        # 輸出 stack trace (每行分開)
        for line in traceback.format_exc().strip().split('\n'):
            self.error(line)

        self.error(f"----- 錯誤上下文 -----")

        if self.ctx.current_operation:
            self.error(f"當前操作: {self.ctx.current_operation}")

        if self.ctx.current_data:
            self.error(f"處理資料: {self.ctx.current_data}")

        if self.ctx.progress:
            self.error(f"處理進度: {self.ctx.progress}")

        if self.ctx.request_info:
            self.error(f"HTTP 請求: {self.ctx.request_info.get('method')} "
                      f"{self.ctx.request_info.get('url')}")

        if self.ctx.response_info:
            self.error(f"HTTP 回應: {self.ctx.response_info.get('status_code')}")

        if self.ctx.db_info:
            self.error(f"資料庫操作: {self.ctx.db_info}")

        self.error(f"{'='*60}")

        # 記錄到統計
        self.stats.setdefault('errors', []).append(error_info)
        self.stats['records_failed'] = self.stats.get('records_failed', 0) + 1

    # ========== 統計資訊 ==========

    def log_stats(self, stats: Dict[str, Any]):
        """記錄統計資訊"""
        self.info(f"----- 統計資訊 -----")
        for key, value in stats.items():
            self.info(f"{key}: {value}")
        self.stats.update(stats)

    def increment(self, key: str, value: int = 1):
        """遞增統計計數器"""
        self.stats[key] = self.stats.get(key, 0) + value

    def get_stats(self) -> Dict[str, Any]:
        """取得統計資訊"""
        return self.stats.copy()

    # ========== 驗證碼/OCR 追蹤 ==========

    def log_captcha_attempt(self, attempt: int, success: bool,
                            result: str = ""):
        """記錄驗證碼識別嘗試"""
        level = logging.DEBUG if success else logging.WARNING
        self.logger.log(level,
            f"驗證碼識別: 第 {attempt} 次 | "
            f"{'成功' if success else '失敗'}" +
            (f" | 結果: {result}" if result else ""))

    # ========== 業務邏輯追蹤 ==========

    def log_business_result(self, operation: str, result: str,
                            details: Dict = None):
        """記錄業務邏輯結果"""
        self.info(f"業務結果: {operation} | {result}")
        if details:
            for key, value in details.items():
                self.info(f"  {key}: {value}")

    def log_data_validation(self, field: str, expected: Any,
                            actual: Any, is_valid: bool):
        """記錄資料驗證結果"""
        level = logging.DEBUG if is_valid else logging.WARNING
        self.logger.log(level,
            f"資料驗證: {field} | "
            f"{'通過' if is_valid else '失敗'} | "
            f"期望: {expected} | 實際: {actual}")

    # ========== 裝飾器 ==========

    def track_function(self, func: Callable) -> Callable:
        """
        函數追蹤裝飾器 - 自動記錄函數執行

        Usage:
            @logger.track_function
            def my_function():
                ...
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            self.debug(f"函數開始: {func_name}")
            self.ctx.set_operation(func_name)

            start = datetime.datetime.now()
            try:
                result = func(*args, **kwargs)
                elapsed = (datetime.datetime.now() - start).total_seconds()
                self.debug(f"函數結束: {func_name} | 耗時: {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = (datetime.datetime.now() - start).total_seconds()
                self.log_exception(e, f"函數 {func_name} 執行失敗")
                raise
            finally:
                self.ctx.set_operation("")

        return wrapper

    def track_retry(self, max_attempts: int = 3,
                    delay: float = 1.0,
                    exceptions: tuple = (Exception,)) -> Callable:
        """
        重試追蹤裝飾器

        Usage:
            @logger.track_retry(max_attempts=3, delay=2.0)
            def fetch_data():
                ...
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                import time

                last_error = None
                for attempt in range(1, max_attempts + 1):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        last_error = e
                        if attempt < max_attempts:
                            self.log_retry(attempt, max_attempts,
                                          str(e), delay)
                            time.sleep(delay)
                        else:
                            self.log_retry_exhausted(func.__name__, attempt)

                raise last_error

            return wrapper
        return decorator


class JsonFormatter(logging.Formatter):
    """JSON 格式的 Log Formatter"""

    def __init__(self, module_name: str):
        super().__init__()
        self.module_name = module_name

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'level': record.levelname,
            'module': self.module_name,
            'message': record.getMessage(),
        }

        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False, default=str)


# ========== 便利函數 ==========

def get_logger(module_name: str, **kwargs) -> CrawlabLogger:
    """
    取得 Logger 實例

    Args:
        module_name: 模組名稱
        **kwargs: 傳遞給 CrawlabLogger 的參數
            - log_dir: Log 檔案目錄
            - json_format: 是否使用 JSON 格式
            - debug: 是否啟用 DEBUG 模式

    Returns:
        CrawlabLogger 實例

    Example:
        from common.logger import get_logger

        logger = get_logger('Data-Insurance', debug=True)
        logger.task_start()
        logger.info("開始處理")
        ...
        logger.task_end()
    """
    return CrawlabLogger(module_name, **kwargs)


# ========== 使用範例 ==========

if __name__ == '__main__':
    # 建立 logger
    logger = get_logger('TestModule', debug=True)

    # 任務開始
    logger.task_start("測試任務")

    # 設定操作上下文
    logger.ctx.set_operation("fetch_data")
    logger.ctx.set_data(id="12345", name="測試資料")

    # 基本 Log
    logger.info("這是一般訊息")
    logger.debug("這是除錯訊息")
    logger.warning("這是警告訊息")

    # HTTP 追蹤
    logger.log_request("POST", "https://api.example.com/data",
                       {"Content-Type": "application/json"},
                       {"key": "value"})
    logger.log_response(200, {"Content-Type": "application/json"},
                        '{"result": "ok"}', 0.5)

    # 資料庫追蹤
    logger.log_db_connect("10.10.0.94", "CL_Daily", "CLUSER")
    logger.log_db_operation("INSERT", "CL_Daily", "test_table", 100)

    # 進度追蹤
    for i in range(1, 11):
        logger.log_progress(i, 10, f"item_{i:03d}")

    # 例外追蹤
    try:
        raise ValueError("測試錯誤")
    except Exception as e:
        logger.log_exception(e, "測試例外捕獲")

    # 統計
    logger.log_stats({
        'total_api_calls': 50,
        'cache_hits': 10
    })

    # 任務結束
    stats = logger.task_end(success=True)
    print(f"\n最終統計: {json.dumps(stats, ensure_ascii=False, indent=2)}")
