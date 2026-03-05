# -*- coding: utf-8 -*-
"""
OC-GoogleMap - OC visit case data sync to Google Maps
Exports case data to Excel, uploads via SCP, and updates Google Maps layers
"""
import datetime

from config import *
from etl_func import (
    query_oc_cases, export_to_excel,
    create_ssh_client, upload_folder_via_scp,
    update_google_map
)


def run():
    """Main execution function"""
    print(f"OC-GoogleMap 開始執行: {datetime.datetime.now()}")

    # Step 1: Export data for each OC
    print("\n=== Step 1: Exporting OC case data ===")
    excel_files = {}
    for oc_name in OC_LIST:
        print(f"Processing OC: {oc_name}")
        data = query_oc_cases(oc_name)
        excel_path = export_to_excel(data, oc_name)
        excel_files[oc_name] = excel_path

    # Step 2: Upload to remote server via SCP
    print("\n=== Step 2: Uploading files via SCP ===")
    ssh_client = create_ssh_client()
    upload_folder_via_scp(ssh_client)
    ssh_client.close()

    # Step 3: Update Google Maps for each OC
    print("\n=== Step 3: Updating Google Maps ===")
    for url, oc_name in URL_LIST:
        if oc_name in excel_files:
            update_google_map(url, oc_name, excel_files[oc_name])

    print(f"\nOC-GoogleMap 執行完成: {datetime.datetime.now()}")
    return True


if __name__ == '__main__':
    run()
