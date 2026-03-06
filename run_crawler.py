# -*- coding: utf-8 -*-
"""
Crawlab Runner - n8n 統一呼叫入口
用於從 n8n 或其他自動化工具執行爬蟲模組
"""
import sys
import json
import importlib.util
import os
from pathlib import Path
from datetime import datetime


# 可用模組列表
AVAILABLE_MODULES = [
    "Data-Court_Auction",
    "Data-Insurance",
    "Data-Insurance_inc",
    "Data-Judicial_139",
    "Data-Judicial_146",
    "Data-Judicial_cdbc3",
    "Data-Judicial_fam",
    "Data-Land_Parcel_Section",
    "Data-Legal_Insur",
    "Data-LicensePenalty",
    "Data-TaxRefund",
    "Data-TaxReturn",
    "Data-Tfasc",
    "HR-EMP",
    "HR-EMP_Clockin",
    "HR-Emp_Salary",
    "HR-EmpLeavetb",
    "HR-HAMS",
    "HR-HROrgInfo",
    "HR-HRUserInfo",
    "HR-INS_JudicialInquiryRequests",
    "HR-Insur_Amount",
    "OC-GoogleMap",
]


def run_module(module_name: str) -> dict:
    """
    執行指定的爬蟲模組

    Args:
        module_name: 模組名稱 (例如: Data-TaxReturn)

    Returns:
        dict: 執行結果
            - module: 模組名稱
            - success: 是否成功
            - message: 訊息
            - start_time: 開始時間
            - end_time: 結束時間
            - duration_seconds: 執行時間 (秒)
            - log_file: Log 檔案路徑
    """
    start_time = datetime.now()

    result = {
        "module": module_name,
        "success": False,
        "message": "",
        "start_time": start_time.isoformat(),
        "end_time": "",
        "duration_seconds": 0,
        "log_file": ""
    }

    # 檢查模組是否存在
    if module_name not in AVAILABLE_MODULES:
        result["message"] = f"模組不存在: {module_name}"
        result["end_time"] = datetime.now().isoformat()
        return result

    base_path = Path(__file__).parent
    module_path = base_path / module_name

    if not module_path.exists():
        result["message"] = f"模組目錄不存在: {module_path}"
        result["end_time"] = datetime.now().isoformat()
        return result

    main_file = module_path / "main.py"
    if not main_file.exists():
        result["message"] = f"main.py 不存在: {main_file}"
        result["end_time"] = datetime.now().isoformat()
        return result

    try:
        # 切換工作目錄到模組目錄
        original_cwd = os.getcwd()
        os.chdir(module_path)

        # 動態載入模組
        spec = importlib.util.spec_from_file_location("main", main_file)
        module = importlib.util.module_from_spec(spec)

        # 將模組目錄加入 path
        if str(module_path) not in sys.path:
            sys.path.insert(0, str(module_path))

        # 執行模組
        spec.loader.exec_module(module)

        # 呼叫 run() 函數
        if hasattr(module, 'run'):
            success = module.run()
            result["success"] = bool(success)
            result["message"] = "執行完成" if success else "執行失敗"
        else:
            result["message"] = "模組沒有 run() 函數"

        # 恢復工作目錄
        os.chdir(original_cwd)

        # Log 檔案路徑
        log_file = base_path / "logs" / f"{module_name}.log"
        if log_file.exists():
            result["log_file"] = str(log_file)

    except Exception as e:
        result["message"] = f"執行錯誤: {str(e)}"
        import traceback
        result["traceback"] = traceback.format_exc()

    finally:
        end_time = datetime.now()
        result["end_time"] = end_time.isoformat()
        result["duration_seconds"] = (end_time - start_time).total_seconds()

    return result


def list_modules() -> dict:
    """列出所有可用模組"""
    base_path = Path(__file__).parent
    available = []
    unavailable = []

    for module_name in AVAILABLE_MODULES:
        module_path = base_path / module_name
        main_file = module_path / "main.py"

        if main_file.exists():
            available.append(module_name)
        else:
            unavailable.append(module_name)

    return {
        "available": available,
        "unavailable": unavailable,
        "total": len(AVAILABLE_MODULES)
    }


def print_help():
    """顯示使用說明"""
    help_text = """
Crawlab Runner - n8n 統一呼叫入口

使用方式:
    python run_crawler.py <module_name>     執行指定模組
    python run_crawler.py --list            列出所有模組
    python run_crawler.py --help            顯示此說明

範例:
    python run_crawler.py Data-TaxReturn
    python run_crawler.py HR-EMP
    python run_crawler.py --list

可用模組:
"""
    print(help_text)
    for module in AVAILABLE_MODULES:
        print(f"    {module}")


def main():
    """主程式入口"""
    if len(sys.argv) < 2:
        print(json.dumps({"error": "請指定模組名稱，使用 --help 查看說明"}, ensure_ascii=False))
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--help" or arg == "-h":
        print_help()
        sys.exit(0)

    if arg == "--list" or arg == "-l":
        result = list_modules()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    # 執行模組
    result = run_module(arg)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 回傳適當的 exit code
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
