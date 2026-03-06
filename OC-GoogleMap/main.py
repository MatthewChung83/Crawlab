# -*- coding: utf-8 -*-
"""
OC-GoogleMap - OC visit case data sync to Google Maps
OC 案件資料同步至 Google Maps
Exports case data to Excel, uploads via SCP, and updates Google Maps layers
"""
import os
import sys
import datetime

# Add parent directory to path for common module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import *
from etl_func import (
    query_oc_cases, export_to_excel,
    create_ssh_client, upload_folder_via_scp,
    update_google_map
)
from common.logger import get_logger

# Initialize logger
logger = get_logger('OC-GoogleMap')


def run():
    """Main execution function"""
    logger.task_start("OC 案件資料同步至 Google Maps")

    total_oc = 0
    total_success = 0
    total_failed = 0

    try:
        # Step 1: Export data for each OC
        logger.ctx.set_operation("export_excel")
        logger.info("Step 1: 匯出 OC 案件資料")

        excel_files = {}
        for i, oc_name in enumerate(OC_LIST, 1):
            total_oc += 1
            logger.log_progress(i, len(OC_LIST), f"oc_{oc_name}")
            logger.ctx.set_data(oc_name=oc_name)

            try:
                logger.debug(f"處理 OC: {oc_name}")
                data = query_oc_cases(oc_name)
                excel_path = export_to_excel(data, oc_name)
                excel_files[oc_name] = excel_path
                logger.debug(f"匯出完成: {excel_path}")
                logger.increment('oc_exported')
            except Exception as e:
                logger.warning(f"匯出 {oc_name} 時發生錯誤: {e}")

        logger.info(f"匯出完成: {len(excel_files)}/{len(OC_LIST)} 個 OC")

        # Step 2: Upload to remote server via SCP
        logger.ctx.set_operation("upload_scp")
        logger.info("Step 2: 上傳檔案至遠端伺服器")

        try:
            ssh_client = create_ssh_client()
            upload_folder_via_scp(ssh_client)
            ssh_client.close()
            logger.info("SCP 上傳完成")
        except Exception as e:
            logger.log_exception(e, "SCP 上傳失敗")
            logger.task_end(success=False)
            return False

        # Step 3: Update Google Maps for each OC
        logger.ctx.set_operation("update_google_map")
        logger.info("Step 3: 更新 Google Maps")

        for i, (url, oc_name) in enumerate(URL_LIST, 1):
            logger.log_progress(i, len(URL_LIST), f"map_{oc_name}")
            logger.ctx.set_data(oc_name=oc_name, url=url)

            if oc_name in excel_files:
                try:
                    update_google_map(url, oc_name, excel_files[oc_name])
                    total_success += 1
                    logger.increment('maps_updated')
                    logger.debug(f"Google Maps 更新完成: {oc_name}")
                except Exception as e:
                    total_failed += 1
                    logger.increment('maps_failed')
                    logger.warning(f"更新 {oc_name} Google Maps 時發生錯誤: {e}")
            else:
                logger.debug(f"跳過 {oc_name}: 無匯出檔案")

        logger.log_stats({
            'total_oc': total_oc,
            'excel_exported': len(excel_files),
            'maps_updated': total_success,
            'maps_failed': total_failed,
        })

        logger.task_end(success=(total_failed == 0))
        return total_failed == 0

    except Exception as e:
        logger.log_exception(e, "執行過程發生錯誤")
        logger.task_end(success=False)
        return False


def main():
    """Main entry point"""
    logger.info("OC-GoogleMap OC 案件資料同步")

    try:
        success = run()
        if success:
            logger.info("同步完成")
        else:
            logger.warning("同步過程有錯誤")
    except KeyboardInterrupt:
        logger.warning("使用者中斷操作")
    except Exception as e:
        logger.log_exception(e, "程式執行錯誤")


if __name__ == '__main__':
    main()
