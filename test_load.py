# -*- coding: utf-8 -*-
"""
Test loading all modules (check dependencies)
Uses subprocess to ensure clean environment for each module
"""
import sys
import subprocess
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

def test_module_load(module_name: str) -> tuple:
    """Test if module can be loaded using subprocess"""
    base_path = Path(__file__).parent
    module_path = base_path / module_name
    main_file = module_path / "main.py"

    if not main_file.exists():
        return False, "main.py not found"

    # Use subprocess to test in clean environment
    test_code = f'''
import sys
import os
sys.path.insert(0, r"{module_path}")
sys.path.insert(0, r"{base_path}")
os.chdir(r"{module_path}")

try:
    import main
    if hasattr(main, 'run'):
        print("OK")
    else:
        print("ERROR: No run() function")
except Exception as e:
    print(f"ERROR: {{type(e).__name__}}: {{e}}")
'''

    try:
        result = subprocess.run(
            [sys.executable, "-c", test_code],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(module_path)
        )

        output = result.stdout.strip()
        if output == "OK":
            return True, "OK"
        elif output.startswith("ERROR:"):
            return False, output[7:]
        else:
            stderr = result.stderr.strip()
            if stderr:
                # Extract last line of error
                lines = stderr.split('\n')
                for line in reversed(lines):
                    if line.strip():
                        return False, line.strip()
            return False, f"Unknown error: {output}"

    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    print("=" * 70)
    print("Testing module loading (import dependencies)")
    print("=" * 70)

    success_count = 0
    failed_count = 0
    failed_modules = []

    for module_name in MODULES:
        success, message = test_module_load(module_name)

        if success:
            print(f"[OK] {module_name}")
            success_count += 1
        else:
            print(f"[FAIL] {module_name}")
            print(f"       -> {message}")
            failed_count += 1
            failed_modules.append((module_name, message))

    print("=" * 70)
    print(f"Result: {success_count} OK, {failed_count} FAILED")
    print("=" * 70)

    if failed_modules:
        print("\nFailed modules summary:")
        for name, msg in failed_modules:
            print(f"  - {name}")

    return failed_count == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
