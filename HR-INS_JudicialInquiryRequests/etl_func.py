# -*- coding: utf-8 -*-
"""
ETL functions for HR-INS_JudicialInquiryRequests - Judicial inquiry crawler
"""
import os
import io
import time
import socket
from datetime import datetime

import pymssql
from PIL import Image, ImageDraw, ImageFont
from smb.SMBConnection import SMBConnection
from playwright.sync_api import sync_playwright

from config import db, smb, urls, LOCAL_OUTPUT_DIR, FONT_PATHS


def ensure_output_dir():
    """Ensure local output directory exists"""
    if not os.path.exists(LOCAL_OUTPUT_DIR):
        os.makedirs(LOCAL_OUTPUT_DIR)


def connect_db():
    """Connect to MSSQL Database"""
    print("Connecting to MSSQL Database...")
    try:
        conn = pymssql.connect(
            server=db['server'],
            user=db['username'],
            password=db['password'],
            database=db['database']
        )
        print("Connected to database successfully.")
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None


def get_pending_requests(cursor):
    """Fetch pending requests from database"""
    cursor.execute(
        "SELECT RequestID, Name, IDNumber, Remarks "
        "FROM INS_JudicialInquiryRequests WHERE IsCompleted = 0"
    )
    return cursor.fetchall()


def mark_request_completed(cursor, conn, request_id):
    """Mark a request as completed"""
    update_sql = (
        "UPDATE INS_JudicialInquiryRequests "
        "SET IsCompleted = 1, CompletedDate = GETDATE() "
        "WHERE RequestID = %s"
    )
    cursor.execute(update_sql, (request_id,))
    conn.commit()


def load_font():
    """Load a compatible font for Chinese text"""
    for f_path in FONT_PATHS:
        try:
            return ImageFont.truetype(f_path, 12)
        except:
            continue
    return ImageFont.load_default()


def add_browser_header(img_bytes, url, title="Judicial Inquiry System"):
    """Adds a Chrome-like browser header to the screenshot using PIL"""
    try:
        screenshot = Image.open(io.BytesIO(img_bytes))
        width, height = screenshot.size

        header_height = 80
        bg_color = "#dee1e6"
        tab_bg_color = "#ffffff"
        url_bg_color = "#f1f3f4"
        text_color = "#3c4043"
        border_color = "#dadce0"

        new_img = Image.new('RGB', (width, height + header_height), bg_color)
        draw = ImageDraw.Draw(new_img)

        # Draw Tab Bar
        tab_height = 34
        tab_width = 240
        draw.rounded_rectangle(
            [(8, 8), (8 + tab_width, 8 + tab_height)],
            radius=8, fill=tab_bg_color, corners=(True, True, False, False)
        )

        font = load_font()
        draw.text((20, 18), title[:30], fill=text_color, font=font)
        draw.text((230, 18), "x", fill=text_color, font=font)

        # Draw Navigation Bar
        nav_y = 8 + tab_height
        draw.rectangle([(0, nav_y), (width, header_height)], fill="#ffffff")
        draw.line([(0, header_height - 1), (width, header_height - 1)], fill=border_color)

        draw.text((15, nav_y + 12), "<", fill=text_color, font=font)
        draw.text((45, nav_y + 12), ">", fill=text_color, font=font)
        draw.text((75, nav_y + 12), "R", fill=text_color, font=font)

        # Draw Address Bar
        address_bar_x = 110
        address_bar_w = width - 160
        address_bar_h = 28
        address_bar_y = nav_y + 6
        draw.rounded_rectangle(
            [(address_bar_x, address_bar_y),
             (address_bar_x + address_bar_w, address_bar_y + address_bar_h)],
            radius=14, fill=url_bg_color
        )
        draw.text((address_bar_x + 15, address_bar_y + 7), f"🔒 {url}", fill=text_color, font=font)

        new_img.paste(screenshot, (0, header_height))

        output = io.BytesIO()
        new_img.save(output, format='PNG')
        return output.getvalue()

    except Exception as e:
        print(f"Error adding browser header: {e}")
        return img_bytes


def save_screenshot_to_smb(img_bytes, filename):
    """Save screenshot to SMB share"""
    try:
        client_machine = socket.gethostname()
        today = datetime.now().strftime('%Y%m%d')
        target_folder = f"{smb['base_folder']}/{today}"
        target_path = f"{target_folder}/{filename}"

        conn = SMBConnection(
            smb['username'], smb['password'],
            client_machine, smb['server_ip'],
            domain=smb['domain'], use_ntlm_v2=True, is_direct_tcp=True
        )
        connected = conn.connect(smb['server_ip'], 445)

        if not connected:
            conn = SMBConnection(
                smb['username'], smb['password'],
                client_machine, smb['server_ip'],
                domain=smb['domain'], use_ntlm_v2=True, is_direct_tcp=False
            )
            connected = conn.connect(smb['server_ip'], 139)

        if connected:
            try:
                conn.createDirectory(smb['service_name'], target_folder)
            except:
                pass

            file_obj = io.BytesIO(img_bytes)
            conn.storeFile(smb['service_name'], target_path, file_obj)
            conn.close()

            windows_path = target_path.replace('/', '\\')
            print(f"Screenshot saved to SMB: \\\\{smb['server_ip']}\\{smb['service_name']}\\{windows_path}")
            return True

        print("Failed to connect to SMB server.")
        return False

    except Exception as e:
        print(f"SMB Upload Error: {e}")
        return False


def save_screenshot(page, filename, full_page=False):
    """Takes a screenshot and saves it to SMB or local fallback"""
    try:
        url = page.url
        title = page.title()

        if full_page:
            dimensions = page.evaluate('''() => {
                return {
                    width: document.documentElement.clientWidth,
                    height: document.documentElement.scrollHeight
                }
            }''')
            clip = {
                'x': 0, 'y': 0,
                'width': dimensions['width'],
                'height': int(dimensions['height'] / 2)
            }
            img_bytes = page.screenshot(clip=clip)
        else:
            img_bytes = page.screenshot()

        img_bytes = add_browser_header(img_bytes, url, title)

        if save_screenshot_to_smb(img_bytes, filename):
            return

    except Exception as e:
        print(f"Screenshot Error: {e}")

    # Fallback to local
    try:
        ensure_output_dir()
        local_path = os.path.join(LOCAL_OUTPUT_DIR, filename)
        with open(local_path, 'wb') as f:
            f.write(img_bytes)
        print(f"Screenshot saved locally (Fallback): {local_path}")
    except Exception as e:
        print(f"Local Save Error: {e}")


def search_consumer_debt(name, idno):
    """Search consumer debt records"""
    print(f"\n--- Searching Consumer Debt for {name} ({idno}) ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Navigating to {urls['consumer_debt']}...")
        page.goto(urls['consumer_debt'])
        page.wait_for_load_state('networkidle')

        frame_v1 = page.frame(name="v1")
        if not frame_v1:
            print("Frame 'v1' not found.")
            browser.close()
            return

        print("Filling form...")
        frame_v1.fill('input[name="clnm"]', name)
        frame_v1.fill('input[name="idno"]', idno)

        print("Submitting query...")
        frame_v1.click('button:has-text("查詢")')

        time.sleep(2)
        page.wait_for_load_state('networkidle')

        frame_v2 = page.frame(name="v2")
        try:
            frame_v2.wait_for_selector('#allTable', timeout=10000)
            print("Results loaded.")
        except:
            print("Timeout waiting for results table.")

        print("Waiting 3 seconds before screenshot...")
        time.sleep(3)
        save_screenshot(page, f"{name}_消債.png", full_page=True)

        content = frame_v2.content()
        if "查無資料" in content:
            print("Result: No data found.")
        else:
            rows = frame_v2.locator('#allTable tr').count()
            print(f"Result: Found {rows} rows (approx).")

        browser.close()


def search_bankruptcy(name, idno):
    """Search bankruptcy records"""
    print(f"\n--- Searching Bankruptcy for {name} ({idno}) ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Navigating to {urls['bankruptcy']}...")
        page.goto(urls['bankruptcy'])
        page.wait_for_load_state('networkidle')

        frame_v1 = page.frame(name="v1")
        if not frame_v1:
            print("Frame 'v1' not found.")
            browser.close()
            return

        print("Filling form...")
        frame_v1.check('input[value="2"]')
        frame_v1.fill('input[name="clnm"]', name)
        frame_v1.fill('input[name="idno"]', idno)

        print("Submitting query...")
        frame_v1.click('button:has-text("查詢")')

        time.sleep(2)
        page.wait_for_load_state('networkidle')

        frame_v2 = page.frame(name="v2")
        try:
            frame_v2.wait_for_selector('#allTable', timeout=10000)
            print("Results loaded.")
        except:
            print("Timeout waiting for results table.")

        print("Waiting 3 seconds before screenshot...")
        time.sleep(3)
        save_screenshot(page, f"{name}_破產.png", full_page=True)

        content = frame_v2.content()
        if "查無資料" in content:
            print("Result: No data found.")
        else:
            rows = frame_v2.locator('#allTable tr').count()
            print(f"Result: Found {rows} rows (approx).")

        browser.close()


def search_domestic_guardianship(name, idno):
    """Search domestic guardianship records"""
    print(f"\n--- Searching Domestic Guardianship for {name} ({idno}) ---")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Navigating to {urls['domestic']}...")
        page.goto(urls['domestic'])
        page.wait_for_load_state('networkidle')

        frame_v1 = page.frame(name="v1")
        if not frame_v1:
            print("Frame 'v1' not found.")
            browser.close()
            return

        print("Filling form...")
        print("Selecting category '02' (監護輔助宣告)...")
        try:
            frame_v1.wait_for_selector('select[name="kdid"]', timeout=10000)
            frame_v1.select_option('select[name="kdid"]', '02')
            print("Category '02' selected.")
        except Exception as e:
            print(f"Error selecting category '02': {e}")
            print("Proceeding with text inputs only (might affect results).")

        frame_v1.fill('input[name="clnm"]', name)
        frame_v1.fill('input[name="idno"]', idno)

        print("Submitting query...")
        frame_v1.click('button:has-text("查詢")')

        time.sleep(2)
        page.wait_for_load_state('networkidle')

        frame_v2 = page.frame(name="v2")
        try:
            frame_v2.wait_for_selector('#allTable', timeout=10000)
            print("Results loaded.")
        except:
            print("Timeout waiting for results table.")

        print("Waiting 3 seconds before screenshot...")
        time.sleep(3)
        save_screenshot(page, f"{name}_家事.png", full_page=True)

        content = frame_v2.content()
        if "查無資料" in content:
            print("Result: No data found.")
        else:
            rows = frame_v2.locator('#allTable tr').count()
            print(f"Result: Found {rows} rows (approx).")

        browser.close()
