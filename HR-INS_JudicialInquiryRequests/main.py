from playwright.sync_api import sync_playwright
import time
import os
import io
from datetime import datetime
import pymssql
from smb.SMBConnection import SMBConnection
import socket
from PIL import Image, ImageDraw, ImageFont

class JudicialCrawler:
    def __init__(self):
        # Local fallback directory
        self.local_output_dir = "judicial_crawler/output"
        if not os.path.exists(self.local_output_dir):
            os.makedirs(self.local_output_dir)

    def _add_browser_header(self, img_bytes, url, title="Judicial Inquiry System"):
        """
        Adds a Chrome-like browser header to the screenshot using PIL.
        """
        try:
            # Open the screenshot
            screenshot = Image.open(io.BytesIO(img_bytes))
            width, height = screenshot.size
            
            # Header dimensions and colors
            header_height = 80
            bg_color = "#dee1e6"
            tab_bg_color = "#ffffff"
            url_bg_color = "#f1f3f4"
            text_color = "#3c4043"
            border_color = "#dadce0"
            
            # Create new image with extra height for header
            new_img = Image.new('RGB', (width, height + header_height), bg_color)
            draw = ImageDraw.Draw(new_img)
            
            # Draw Tab Bar
            tab_height = 34
            tab_width = 240
            draw.rounded_rectangle([(8, 8), (8 + tab_width, 8 + tab_height)], radius=8, fill=tab_bg_color, corners=(True, True, False, False))
            
            # Draw Title Text (Simple approximation)
            font = None
            # Try to load a Chinese-compatible font (Windows & Linux)
            possible_fonts = [
                "NotoSansTC-Regular.ttf",          # Local file (Cross-platform)
                # Windows
                "C:\\Windows\\Fonts\\msjh.ttc",   # Microsoft JhengHei
                "C:\\Windows\\Fonts\\msjh.ttf",
                "C:\\Windows\\Fonts\\mingliu.ttc", # MingLiU
                "C:\\Windows\\Fonts\\simsun.ttc",  # SimSun
                "arial.ttf",
                # Linux (Common paths for Chinese fonts)
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
                "/usr/share/fonts/truetype/arphic/uming.ttc",
                "/usr/share/fonts/truetype/arphic/ukai.ttc"
            ]
            
            for f_path in possible_fonts:
                try:
                    font = ImageFont.truetype(f_path, 12)
                    break
                except:
                    continue
            
            if font is None:
                font = ImageFont.load_default()
            
            draw.text((20, 18), title[:30], fill=text_color, font=font)
            draw.text((230, 18), "x", fill=text_color, font=font) # Close button mock
            
            # Draw Navigation Bar
            nav_y = 8 + tab_height
            draw.rectangle([(0, nav_y), (width, header_height)], fill="#ffffff")
            draw.line([(0, header_height-1), (width, header_height-1)], fill=border_color)
            
            # Draw Icons (Circles as placeholders for simplicity or draw simple shapes)
            # Back
            draw.text((15, nav_y + 12), "<", fill=text_color, font=font)
            # Forward
            draw.text((45, nav_y + 12), ">", fill=text_color, font=font)
            # Refresh
            draw.text((75, nav_y + 12), "R", fill=text_color, font=font)
            
            # Draw Address Bar
            address_bar_x = 110
            address_bar_w = width - 160
            address_bar_h = 28
            address_bar_y = nav_y + 6
            draw.rounded_rectangle([(address_bar_x, address_bar_y), (address_bar_x + address_bar_w, address_bar_y + address_bar_h)], radius=14, fill=url_bg_color)
            
            # Draw URL
            draw.text((address_bar_x + 15, address_bar_y + 7), f"🔒 {url}", fill=text_color, font=font)
            
            # Paste original screenshot
            new_img.paste(screenshot, (0, header_height))
            
            # Save to bytes
            output = io.BytesIO()
            new_img.save(output, format='PNG')
            return output.getvalue()
            
        except Exception as e:
            print(f"Error adding browser header: {e}")
            return img_bytes

    def save_screenshot(self, page, filename, full_page=False):
        """
        Takes a screenshot and attempts to save it to the SMB share.
        Falls back to local storage if SMB fails.
        If full_page is True, captures the entire page.
        """
        try:
            url = page.url
            title = page.title()
            
            # 1. Capture screenshot to memory
            if full_page:
                # Get full page dimensions
                dimensions = page.evaluate('''() => {
                    return {
                        width: document.documentElement.clientWidth,
                        height: document.documentElement.scrollHeight
                    }
                }''')
                
                # Capture only half of the height
                clip = {
                    'x': 0,
                    'y': 0,
                    'width': dimensions['width'],
                    'height': int(dimensions['height'] / 2)
                }
                img_bytes = page.screenshot(clip=clip)
            else:
                img_bytes = page.screenshot()
            
            # 2. Add Browser Header
            img_bytes = self._add_browser_header(img_bytes, url, title)
            
            # 3. Define SMB details
            server_ip = '10.10.0.93'
            service_name = 'UCS' # Share name
            username = 'sqlsvc'
            password = 'Sq1@dmin'
            domain = 'ucs'
            client_machine = socket.gethostname()
            
            today = datetime.now().strftime('%Y%m%d')
            # Path relative to Share: HumanResourceDept/screenshot/{today}
            # Note: pysmb uses forward slashes usually
            target_folder = f"HumanResourceDept/screenshot/{today}"
            target_path = f"{target_folder}/{filename}"

            # 3. Connect to SMB
            conn = SMBConnection(username, password, client_machine, server_ip, domain=domain, use_ntlm_v2=True, is_direct_tcp=True)
            connected = conn.connect(server_ip, 445)
            
            if not connected:
                # Try port 139 if 445 fails
                conn = SMBConnection(username, password, client_machine, server_ip, domain=domain, use_ntlm_v2=True, is_direct_tcp=False)
                connected = conn.connect(server_ip, 139)

            if connected:
                # 4. Create Directory (if not exists)
                # We assume HumanResourceDept/screenshot exists. We try to create the date folder.
                try:
                    conn.createDirectory(service_name, target_folder)
                except Exception:
                    # Likely already exists or parent missing. We ignore for now and try upload.
                    pass

                # 5. Upload File
                # storeFile takes a file-like object
                file_obj = io.BytesIO(img_bytes)
                conn.storeFile(service_name, target_path, file_obj)
                conn.close()
                
                windows_path = target_path.replace('/', '\\')
                print(f"Screenshot saved to SMB: \\\\{server_ip}\\{service_name}\\{windows_path}")
                return

            else:
                print("Failed to connect to SMB server.")

        except Exception as e:
            print(f"SMB Upload Error: {e}")

        # 6. Fallback to Local
        try:
            local_path = os.path.join(self.local_output_dir, filename)
            if full_page:
                # Get full page dimensions
                dimensions = page.evaluate('''() => {
                    return {
                        width: document.documentElement.clientWidth,
                        height: document.documentElement.scrollHeight
                    }
                }''')
                
                # Capture only half of the height
                clip = {
                    'x': 0,
                    'y': 0,
                    'width': dimensions['width'],
                    'height': int(dimensions['height'] / 2)
                }
                page.screenshot(path=local_path, clip=clip)
            else:
                page.screenshot(path=local_path)
            print(f"Screenshot saved locally (Fallback): {local_path}")
        except Exception as e:
            print(f"Local Save Error: {e}")

    def connect_db(self):
        print("Connecting to MSSQL Database...")
        try:
            conn = pymssql.connect(
                server='10.10.0.94',
                user='FRUSER',
                password='1qaz@WSX',
                database='UCS_ReportDB'
            )
            print("Connected to database successfully.")
            return conn
        except Exception as e:
            print(f"Database connection failed: {e}")
            return None

    def process_requests(self):
        conn = self.connect_db()
        if not conn:
            return

        try:
            cursor = conn.cursor(as_dict=True)
            # Fetch pending requests
            cursor.execute("SELECT RequestID, Name, IDNumber, Remarks FROM INS_JudicialInquiryRequests WHERE IsCompleted = 0")
            rows = cursor.fetchall()
            
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
                    
                    # If no specific keywords are found, default to running ALL searches
                    if not (run_consumer or run_bankruptcy or run_domestic):
                        run_consumer = True
                        run_bankruptcy = True
                        run_domestic = True
                        print("No specific filters found in Remarks. Running ALL searches.")
                    else:
                        print(f"Filters applied - Consumer: {run_consumer}, Bankruptcy: {run_bankruptcy}, Domestic: {run_domestic}")

                    # Run searches
                    if run_consumer:
                        self.search_consumer_debt(name, idno)
                    if run_bankruptcy:
                        self.search_bankruptcy(name, idno)
                    if run_domestic:
                        self.search_domestic_guardianship(name, idno)
                    
                    # Update status to Completed (1)
                    update_sql = "UPDATE INS_JudicialInquiryRequests SET IsCompleted = 1, CompletedDate = GETDATE() WHERE RequestID = %s"
                    cursor.execute(update_sql, (request_id,))
                    conn.commit()
                    print(f"RequestID {request_id} marked as completed.")
                    
                except Exception as e:
                    print(f"Error processing RequestID {request_id}: {e}")
                    
        except Exception as e:
            print(f"Error during database processing: {e}")
        finally:
            conn.close()

    def search_consumer_debt(self, name, idno):
        print(f"\n--- Searching Consumer Debt for {name} ({idno}) ---")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            url = "https://cdcb3.judicial.gov.tw/judbp/wkw/WHD9A01.htm"
            print(f"Navigating to {url}...")
            page.goto(url)
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
            # Screenshot After - capture the full page
            self.save_screenshot(page, f"{name}_消債.png", full_page=True)
            
            content = frame_v2.content()
            if "查無資料" in content:
                print("Result: No data found.")
            else:
                rows = frame_v2.locator('#allTable tr').count()
                print(f"Result: Found {rows} rows (approx).")

            browser.close()

    def search_bankruptcy(self, name, idno):
        print(f"\n--- Searching Bankruptcy for {name} ({idno}) ---")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            url = "https://cdcb3.judicial.gov.tw/judbp/wkw/WHD9A01.htm"
            print(f"Navigating to {url}...")
            page.goto(url)
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
            # Screenshot After - capture the full page
            self.save_screenshot(page, f"{name}_破產.png", full_page=True)
            
            content = frame_v2.content()
            if "查無資料" in content:
                print("Result: No data found.")
            else:
                rows = frame_v2.locator('#allTable tr').count()
                print(f"Result: Found {rows} rows (approx).")

            browser.close()

    def search_domestic_guardianship(self, name, idno):
        print(f"\n--- Searching Domestic Guardianship for {name} ({idno}) ---")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            url = "https://domestic.judicial.gov.tw/judbp/wkw/WHD9HN01.htm"
            print(f"Navigating to {url}...")
            page.goto(url)
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
            # Screenshot After - capture the full page
            self.save_screenshot(page, f"{name}_家事.png", full_page=True)
            
            content = frame_v2.content()
            if "查無資料" in content:
                print("Result: No data found.")
            else:
                rows = frame_v2.locator('#allTable tr').count()
                print(f"Result: Found {rows} rows (approx).")

            browser.close()

def main():
    crawler = JudicialCrawler()
    crawler.process_requests()

if __name__ == "__main__":
    main()
