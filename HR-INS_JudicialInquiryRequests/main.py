# -*- coding: utf-8 -*-
"""
HR-INS_JudicialInquiryRequests - Judicial inquiry crawler
Searches consumer debt, bankruptcy, and domestic guardianship records
"""
from config import *
from etl_func import (
    connect_db, get_pending_requests, mark_request_completed,
    search_consumer_debt, search_bankruptcy, search_domestic_guardianship
)


def process_requests():
    """Process all pending judicial inquiry requests"""
    conn = connect_db()
    if not conn:
        return False

    try:
        cursor = conn.cursor(as_dict=True)
        rows = get_pending_requests(cursor)

        print(f"Found {len(rows)} pending requests.")

        for row in rows:
            request_id = row['RequestID']
            name = row['Name']
            idno = row['IDNumber']
            remarks = row['Remarks'] if row['Remarks'] else ""

            print(f"\nProcessing RequestID: {request_id}, Name: {name}, ID: {idno}, Remarks: {remarks}")

            try:
                # Determine which searches to run based on Remarks
                run_consumer = "消債" in remarks
                run_bankruptcy = "破產" in remarks
                run_domestic = "家事" in remarks

                # If no specific keywords found, run ALL searches
                if not (run_consumer or run_bankruptcy or run_domestic):
                    run_consumer = True
                    run_bankruptcy = True
                    run_domestic = True
                    print("No specific filters found in Remarks. Running ALL searches.")
                else:
                    print(f"Filters applied - Consumer: {run_consumer}, Bankruptcy: {run_bankruptcy}, Domestic: {run_domestic}")

                # Run searches
                if run_consumer:
                    search_consumer_debt(name, idno)
                if run_bankruptcy:
                    search_bankruptcy(name, idno)
                if run_domestic:
                    search_domestic_guardianship(name, idno)

                # Mark as completed
                mark_request_completed(cursor, conn, request_id)
                print(f"RequestID {request_id} marked as completed.")

            except Exception as e:
                print(f"Error processing RequestID {request_id}: {e}")

        return True

    except Exception as e:
        print(f"Error during database processing: {e}")
        return False

    finally:
        conn.close()


def run():
    """Main execution function"""
    return process_requests()


if __name__ == "__main__":
    run()
