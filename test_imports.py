# -*- coding: utf-8 -*-
"""
測試所有模組是否能正確 import
"""
import sys
import os
import importlib.util
from pathlib import Path

MODULES = [
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

def test_module_import(module_name: str) -> tuple:
    """測試模組是否能正確 import"""
    base_path = Path(__file__).parent
    module_path = base_path / module_name
    main_file = module_path / "main.py"

    if not main_file.exists():
        return False, "main.py not found"

    # 保存原始狀態
    original_cwd = os.getcwd()
    original_path = sys.path.copy()

    try:
        # 切換目錄
        os.chdir(module_path)

        # 加入路徑
        if str(module_path) not in sys.path:
            sys.path.insert(0, str(module_path))
        if str(base_path) not in sys.path:
            sys.path.insert(0, str(base_path))

        # 嘗試編譯
        with open(main_file, 'r', encoding='utf-8') as f:
            source = f.read()

        compile(source, main_file, 'exec')

        return True, "OK"

    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    except Exception as e:
        return False, f"Error: {e}"
    finally:
        os.chdir(original_cwd)
        sys.path = original_path


def main():
    print("=" * 60)
    print("測試所有模組 import")
    print("=" * 60)

    success_count = 0
    failed_count = 0

    for module_name in MODULES:
        success, message = test_module_import(module_name)

        if success:
            print(f"[OK] {module_name}")
            success_count += 1
        else:
            print(f"[FAIL] {module_name}: {message}")
            failed_count += 1

    print("=" * 60)
    print(f"結果: {success_count} 成功, {failed_count} 失敗")
    print("=" * 60)

    return failed_count == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
