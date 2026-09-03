import os
import sys
import csv
import json
import time
import random
import string
import re
import threading
import queue
from colorama import Fore, Style, init
from adb_manager import ADBManager
# Initialize colorama
init(autoreset=True)

def clean_phone_number(phone_raw):
    """Strips country code +974/00974/974, spaces and dashes, returning the 8-digit number."""
    cleaned = re.sub(r'[^\d]', '', str(phone_raw).strip())
    if cleaned.startswith("00974"):
        cleaned = cleaned[5:]
    elif cleaned.startswith("974") and len(cleaned) == 11:
        cleaned = cleaned[3:]
    return cleaned

def generate_random_email():
    """Generates a random valid email address ending with @gmail.com."""
    prefixes = ["musa", "user", "karwa", "qatar", "lead", "info", "test", "account"]
    prefix = random.choice(prefixes)
    rand_num = random.randint(100000, 999999)
    rand_chars = ''.join(random.choice(string.ascii_lowercase) for _ in range(3))
    return f"{prefix}{rand_num}{rand_chars}@gmail.com"

def update_lead_status_in_input_csv(csv_file, target_phone, new_status):
    """Updates status column in input leads.csv immediately upon completing a lead."""
    if not os.path.exists(csv_file):
        return
    try:
        rows = []
        clean_target = clean_phone_number(target_phone)
        with open(csv_file, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            f.seek(0)
            if 'phone' in first_line.lower() or ',' in first_line:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    p = clean_phone_number(row.get('phone_number', ''))
                    if p == clean_target:
                        row['status'] = new_status
                    rows.append(row)
            else:
                fieldnames = ['phone_number', 'status']
                for line in f:
                    line_str = line.strip()
                    if line_str:
                        p = clean_phone_number(line_str)
                        st = new_status if p == clean_target else ''
                        rows.append({'phone_number': p, 'status': st})
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    except Exception as e:
        print(f"Error updating input csv status: {e}")

# Map of Qatar Banks and their common name variations
BANK_SYNONYMS = {
    "commercial bank of qatar": ["Commercial Bank of Qatar", "Commercial Bank", "CBQ"],
    "commercial bank": ["Commercial Bank of Qatar", "Commercial Bank", "CBQ"],
    "cbq": ["Commercial Bank of Qatar", "Commercial Bank", "CBQ"],
    "qatar national bank": ["Qatar National Bank", "QNB"],
    "qnb": ["Qatar National Bank", "QNB"],
    "doha bank": ["Doha Bank", "Doha"],
    "doha": ["Doha Bank", "Doha"],
    "qatar islamic bank": ["Qatar Islamic Bank", "QIB", "Islamic Bank"],
    "qib": ["Qatar Islamic Bank", "QIB", "Islamic Bank"],
    "masraf al rayan": ["Masraf Al Rayan", "Al Rayan", "AlRayan", "Rayan", "Masraf AlRayan"],
    "al rayan": ["Masraf Al Rayan", "Al Rayan", "AlRayan", "Rayan", "Masraf AlRayan"],
    "rayan": ["Masraf Al Rayan", "Al Rayan", "AlRayan", "Rayan", "Masraf AlRayan"],
    "dukhan bank": ["Dukhan Bank", "Dukhan", "Barwa Bank", "Barwa"],
    "dukhan": ["Dukhan Bank", "Dukhan", "Barwa Bank", "Barwa"],
    "barwa bank": ["Dukhan Bank", "Dukhan", "Barwa Bank", "Barwa"],
    "ahlibank": ["Ahlibank", "Ahli Bank", "Al Ahli Bank", "Ahli"],
    "ahli bank": ["Ahlibank", "Ahli Bank", "Al Ahli Bank", "Ahli"],
    "ahli": ["Ahlibank", "Ahli Bank", "Al Ahli Bank", "Ahli"],
    "qatar international islamic bank": ["Qatar International Islamic Bank", "QIIB", "International Islamic"],
    "qiib": ["Qatar International Islamic Bank", "QIIB", "International Islamic"],
    "lesha bank": ["Lesha Bank", "Lesha", "QFB"]
}

def get_bank_search_terms(bank_name):
    norm = str(bank_name).strip().lower()
    for key, synonyms in BANK_SYNONYMS.items():
        if key == norm or key in norm or norm in key:
            return synonyms
    return [str(bank_name).strip()]

def update_passed_and_failed_csv(clean_phone, bank, email, status, timestamp):
    """Writes lead results into passed_leads.csv or failed_leads.csv in real time."""
    target_file = "passed_leads.csv" if status in ["PASSED", "OTP_SENT"] else "failed_leads.csv"
    headers = ['phone_number', 'bank', 'email', 'status', 'timestamp']
    file_mode = 'a' if os.path.exists(target_file) and os.path.getsize(target_file) > 0 else 'w'
    try:
        with open(target_file, file_mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if file_mode == 'w':
                writer.writeheader()
            writer.writerow({
                'phone_number': clean_phone,
                'bank': bank,
                'email': email,
                'status': status,
                'timestamp': timestamp
            })
    except Exception as e:
        print(f"Error updating {target_file}: {e}")

class KarwaAutomation:
    """End-to-end Mobile Automation for Karwa Qatar Fawran Wallet Top-Up."""

    def __init__(self, config_path="config.json", device_serial=None, sync_barrier=None):
        self.config_path = config_path
        self.config = self.load_config()
        self.device_serial = device_serial
        self.sync_barrier = sync_barrier
        self.adb = ADBManager(target_ip=self.config.get("adb_target_ip"), device_serial=self.device_serial)
        
        self.debug_dir = self.config.get("debug_dir", "debug_logs")
        os.makedirs(self.debug_dir, exist_ok=True)
        
        self.package = self.config.get("app_package", "com.karwatechnologies.karwa")
        self.activity = self.config.get("app_activity", "com.karwatechnologies.karwa.MainActivity")
        self.delay = self.config.get("delay_between_steps", 1.2)
        self.timeout = self.config.get("element_timeout", 12)
        self.default_bank = self.config.get("default_bank", "Commercial Bank of Qatar")
        self.default_email = self.config.get("default_email", "musaahmad261261@gmail.com")
        self.target_bank_filter = self.config.get("target_bank_filter", "All Banks")
        self.stop_requested = False

    def sync_step(self, step_name="step"):
        """Synchronizes step execution across all connected devices so devices advance together in lockstep."""
        if hasattr(self, 'sync_barrier') and self.sync_barrier:
            try:
                self.sync_barrier.wait(timeout=25)
            except Exception:
                pass

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"{Fore.RED}Error loading config: {e}. Using defaults.{Style.RESET_ALL}")
            return {}

    def log_step(self, step_name):
        dev_prefix = f"[{self.device_serial}] " if self.device_serial else ""
        print(f"\n{Fore.CYAN}{dev_prefix}=================== STEP: {step_name} ==================={Style.RESET_ALL}")

    def setup_connection(self):
        self.log_step("Connecting to Android Device")
        if not self.adb.connect():
            self.adb.log_err("Failed to connect to device. Ensure USB debugging is authorized.")
            return False
        self.adb.wake_and_unlock()
        return True

    def reset_to_app_home(self):
        """Navigates smoothly back to Karwa App Home screen without force-stopping or closing the app."""
        self.adb.log_info("Returning to Karwa app home screen...")
        
        # 1. Dismiss soft keyboard if open
        self.adb.dismiss_keyboard()

        # 2. Press Back 3 times to exit QPAY / Fawran webview cleanly
        for _ in range(3):
            self.adb.go_back()
            time.sleep(0.15)

        # 3. Bring Karwa MainActivity to front smoothly via am start
        self.adb.start_app(self.package, self.activity)
        time.sleep(0.3)

        # 4. Tap bottom-left Home tab (0.15, 0.95) to force root Home view ("Our Services")
        self.adb.tap_ratio(0.15, 0.95)
        time.sleep(0.2)

        return True

    def wait_for_payment_webview_ready(self, timeout=20):
        """Polls rapidly until WebView progressbar spinner disappears and HTML content (customerEmail / 100.00 QAR) is rendered."""
        start = time.time()
        temp_file = os.path.join(self.debug_dir, f"temp_webview_{self.adb.clean_serial}.xml")
        
        while time.time() - start < timeout:
            dump_path = self.adb.dump_layout(temp_file)
            if dump_path and os.path.exists(dump_path):
                try:
                    with open(dump_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                    
                    has_email = ("customeremail" in content or "customer email" in content)
                    has_amount = ("100.00 qar" in content or "100.00" in content or "order:" in content)
                    has_progressbar = ("progressbar" in content)
                    
                    if (has_email or has_amount) and not has_progressbar:
                        self.adb.log_success("Payment WebView HTML content is fully loaded and ready!")
                        return True
                    elif has_email:
                        self.adb.log_success("Payment WebView email input detected in HTML hierarchy!")
                        return True
                finally:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except Exception:
                            pass
            time.sleep(0.25)
            
        self.adb.log_warn("Payment WebView ready check timed out after 20s. Proceeding with flow...")
        return False

    def run_flow_for_lead(self, phone_raw, bank_name=None, email=None):
        phone = clean_phone_number(phone_raw)
        bank = bank_name.strip() if bank_name and bank_name.strip() else self.default_bank
        
        if not email or not str(email).strip() or "@" not in str(email):
            email = generate_random_email()

        self.adb.log_info(f"Target Lead -> Mobile: {phone} | Bank: {bank} | Email: {email}")

        try:
            # ----------------------------------------------------
            # 0. Ensure screen awake & rotate Location / IP / Proxy
            # ----------------------------------------------------
            self.adb.wake_and_unlock()

            if self.config.get("rotate_location_per_lead", True):
                try:
                    self.adb.rotate_device_location()
                except Exception:
                    pass

            if self.config.get("rotate_ip_per_lead", False):
                try:
                    self.adb.rotate_ip_address()
                except Exception:
                    pass

            proxy_list = self.config.get("proxy_list", [])
            if proxy_list and isinstance(proxy_list, list) and len(proxy_list) > 0:
                import random
                chosen_proxy = random.choice(proxy_list)
                self.adb.set_http_proxy(chosen_proxy)
            elif self.config.get("http_proxy"):
                self.adb.set_http_proxy(self.config.get("http_proxy"))

            if self.config.get("clear_cache_per_lead", True):
                try:
                    self.adb.clear_app_cache(self.package)
                except Exception:
                    pass

            # ----------------------------------------------------
            # 1. Tap Account Tab (Bottom-Right 0.88, 0.95)
            # ----------------------------------------------------
            self.log_step("Navigating to Account Tab")
            account_elem = self.adb.find_element(text="Account", dump_file=None)
            if account_elem:
                self.adb.tap(account_elem['x'], account_elem['y'])
            else:
                self.adb.tap_ratio(0.88, 0.95)
            time.sleep(0.3)

            # Check and clear Transaction History trap if opened
            page_kw, _ = self.adb.wait_for_page_to_contain(["transaction", "history", "recent transactions"], timeout=0.6, poll_interval=0.2)
            if page_kw:
                self.adb.log_warn("Transaction History screen detected. Navigating back...")
                self.adb.go_back()
                time.sleep(0.2)
                self.adb.tap_ratio(0.88, 0.95)
                time.sleep(0.3)

            # ----------------------------------------------------
            # 3. Tap Wallet Item (0.20, 0.38)
            # ----------------------------------------------------
            self.log_step("Navigating to Wallet")
            wallet_elem = self.adb.find_element(text="Wallet", dump_file=None)
            if wallet_elem:
                self.adb.tap(wallet_elem['x'], wallet_elem['y'])
            else:
                self.adb.tap_ratio(0.20, 0.38)
            time.sleep(0.3)

            # ----------------------------------------------------
            # 4. Tap Top Up Wallet (0.27, 0.31)
            # ----------------------------------------------------
            self.log_step("Clicking Top Up Wallet")
            topup_elem = self.adb.find_element(text="Top Up Wallet", dump_file=None)
            if topup_elem:
                self.adb.tap(topup_elem['x'], topup_elem['y'])
            else:
                self.adb.tap_ratio(0.27, 0.31)
            time.sleep(0.3)

            # ----------------------------------------------------
            # 5. Select 100 QAR and Add Funds
            # ----------------------------------------------------
            self.log_step("Selecting 100 QAR and adding funds")
            qar_elem = self.adb.find_element(text="100 QAR", dump_file=None)
            if qar_elem:
                self.adb.tap(qar_elem['x'], qar_elem['y'])
            else:
                self.adb.tap_ratio(0.50, 0.32)
            time.sleep(0.2)

            add_btn = self.adb.find_element(text="Add funds", dump_file=None)
            if add_btn:
                self.adb.tap(add_btn['x'], add_btn['y'])
            else:
                self.adb.tap_ratio(0.50, 0.94)

            # ----------------------------------------------------
            # 6. Enter Customer Email on Payment Web View
            # ----------------------------------------------------
            self.log_step("Entering Email on Payment Web View")
            target_email = email.strip() if email and email.strip() and "@" in email else generate_random_email()

            # Synchronized Webview Ready Check: Fast device waits for slow device webview to finish loading
            self.wait_for_payment_webview_ready(timeout=25)
            self.sync_step("webview_ready")

            email_elem, _ = self.adb.wait_for_any_element([
                {"resource_id": "customerEmail"},
                {"text": "email", "fuzzy": True},
                {"class_name": "android.widget.EditText"}
            ], timeout=5, poll_interval=0.25, auto_scroll=False)

            if email_elem:
                self.adb.clear_and_type(target_email, element=email_elem, backspace_count=0)
            else:
                self.adb.clear_and_type(target_email, rx=0.50, ry=0.42, backspace_count=0)

            time.sleep(0.2)
            self.adb.dismiss_keyboard()
            time.sleep(0.2)
            self.sync_step("email_entered")

            # Click Pay button (Synchronized across all screen resolutions)
            self.log_step("Clicking Pay")
            pay_btn = self.adb.find_element(text="Pay", fuzzy=False)
            if not pay_btn or pay_btn['y'] < self.adb.screen_height * 0.35:
                # Swipe up slightly to bring Pay button into view on 720x1600 / taller screens
                self.adb.swipe_up(duration_ms=150)
                time.sleep(0.15)
                pay_btn = self.adb.find_element(text="Pay", fuzzy=False)

            if pay_btn and pay_btn['y'] > self.adb.screen_height * 0.35:
                self.adb.tap(pay_btn['x'], pay_btn['y'])
                self.adb.log_success(f"Pay button tapped at ({pay_btn['x']}, {pay_btn['y']})!")
            else:
                self.adb.log_info("Pay button element not found. Executing resolution ratio fallbacks...")
                self.adb.tap_ratio(0.50, 0.52)
                self.adb.tap_ratio(0.50, 0.58)
                self.adb.tap_ratio(0.50, 0.64)

            self.sync_step("pay_clicked")

            # DYNAMIC PAGE GUARD: Wait for QPAY Gateway screen
            gw_ready, gw_kw = self.adb.wait_for_page_to_contain([
                "fawran", "qpay", "select payment", "cardless"
            ], timeout=20, poll_interval=0.25)

            if not gw_ready:
                self.adb.tap_ratio(0.50, 0.52)
                gw_ready, gw_kw = self.adb.wait_for_page_to_contain([
                    "fawran", "qpay", "select payment", "cardless"
                ], timeout=10, poll_interval=0.25)

            self.adb.log_success(f"QPAY Gateway screen confirmed (matched '{gw_kw}')!")

            # ----------------------------------------------------
            # 7. Select Fawran in QPAY Gateway
            # ----------------------------------------------------
            self.log_step("Selecting Fawran Payment Method")
            fawran_btn = self.adb.find_element(text="Fawran", fuzzy=True)
            if fawran_btn:
                self.adb.tap(fawran_btn['x'], fawran_btn['y'])
            else:
                self.adb.tap_ratio(0.50, 0.76)

            # Wait for Fawran Details screen
            fawran_ready, f_kw = self.adb.wait_for_page_to_contain([
                "bank", "select bank", "fawranprovider", "mobile number", "aliasvalue"
            ], timeout=15, poll_interval=0.25)

            self.adb.log_success(f"Fawran Details screen confirmed ready (matched '{f_kw}')!")

            # Scroll up slightly to reveal Proceed button
            self.adb.swipe(self.adb.screen_width // 2, int(self.adb.screen_height * 0.75), 
                           self.adb.screen_width // 2, int(self.adb.screen_height * 0.50), 150)
            time.sleep(0.2)

            # Click Proceed to Payment
            self.log_step("Clicking Proceed to Payment")
            proceed_btn = self.adb.find_element(text="Proceed", fuzzy=True)
            if proceed_btn:
                self.adb.tap(proceed_btn['x'], proceed_btn['y'])
            else:
                self.adb.tap_ratio(0.50, 0.82)

            # ----------------------------------------------------
            # 8. Enter Fawran Details (Bank Provider & Mobile Number)
            # ----------------------------------------------------
            self.log_step(f"Configuring Fawran Details: Bank='{bank}', Phone='{phone}'")

            # Tap Bank Provider dropdown
            self.adb.log_info(f"Selecting bank provider: {bank}")
            provider_dropdown = self.adb.find_element(resource_id="fawranProvider", fuzzy=True)
            if provider_dropdown:
                self.adb.tap(provider_dropdown['x'], provider_dropdown['y'])
            else:
                self.adb.tap_ratio(0.50, 0.40)

            time.sleep(0.3)

            # Fast single-dump bank search
            search_terms = get_bank_search_terms(bank)
            bank_found = False

            dump_file = os.path.join(self.debug_dir, "bank_dump_pass.xml")
            dump_path = self.adb.dump_layout(dump_file)
            if dump_path:
                for term in search_terms:
                    bank_elem = self.adb.find_element_in_dump(dump_path, text=term, fuzzy=True)
                    if bank_elem:
                        self.adb.tap(bank_elem['x'], bank_elem['y'])
                        self.adb.log_success(f"Bank '{term}' selected successfully.")
                        bank_found = True
                        break

            if not bank_found:
                bank_words = [w.lower() for w in bank.replace("of", "").replace("qatar", "").replace("bank", "").split() if len(w) >= 3]
                for word in bank_words:
                    bank_elem = self.adb.find_element_in_dump(dump_path, text=word, fuzzy=True)
                    if bank_elem:
                        self.adb.tap(bank_elem['x'], bank_elem['y'])
                        self.adb.log_success(f"Bank selected via deep match '{word}'.")
                        bank_found = True
                        break

            if not bank_found:
                self.adb.tap_ratio(0.50, 0.45)

            time.sleep(0.2)

            # Enter 8-digit mobile number
            self.adb.log_info(f"Entering mobile number: {phone}")
            alias_elem, _ = self.adb.wait_for_any_element([
                {"resource_id": "aliasValue"},
                {"text": "Alias Value", "fuzzy": True},
                {"text": "Mobile Number", "fuzzy": True},
                {"class_name": "android.widget.EditText"}
            ], timeout=6, poll_interval=0.25, auto_scroll=False)

            if alias_elem:
                self.adb.clear_and_type(phone, element=alias_elem)
            else:
                self.adb.clear_and_type(phone, rx=0.57, ry=0.62)

            time.sleep(0.2)
            self.adb.dismiss_keyboard()
            time.sleep(0.2)

            # Click Continue Button (Auto-scroll & Keyboard Dismissal)
            self.log_step("Clicking Continue")
            self.adb.dismiss_keyboard()
            time.sleep(0.15)
            self.adb.swipe_up(duration_ms=150)
            time.sleep(0.15)

            continue_btn = self.adb.find_element(text="Continue", fuzzy=False)
            if continue_btn and continue_btn['y'] > self.adb.screen_height * 0.35:
                self.adb.tap(continue_btn['x'], continue_btn['y'])
                self.adb.log_success(f"Clicked Continue button at ({continue_btn['x']}, {continue_btn['y']})!")
            else:
                self.adb.log_info("Continue button element not found. Executing ratio fallbacks...")
                self.adb.tap_ratio(0.50, 0.77)
                self.adb.tap_ratio(0.50, 0.85)

            self.sync_step("continue_clicked")

            # ----------------------------------------------------
            # 9. Verify OTP / Result Status (High Speed Dynamic Polling)
            # ----------------------------------------------------
            self.log_step("Verifying OTP / Transaction Status")
            result = self.verify_otp_status(phone)
            return result

        finally:
            try:
                self.reset_to_app_home()
            except Exception:
                pass

    def verify_otp_status(self, phone):
        """Analyzes screen XML layout dynamically as soon as OTP / Failure status appears."""
        xml_dump_path = os.path.join(self.debug_dir, f"{phone}_layout.xml")
        screenshot_path = os.path.join(self.debug_dir, f"{phone}_screenshot.png")
        
        success_keywords = [
            "otp", "verification code", "resend", "enter code", "enter otp", 
            "code sent", "verify code", "approve in app", "push notification", 
            "transaction pending", "payment confirmation", "your otp", "password valid for one time"
        ]
        failure_keywords = [
            "invalid customer alias", "invalid alias", "alias invalid", "invalid customer",
            "alias does not exist", "unregistered",
            "unhandled exception", "invalid mobile", "mobile number not registered",
            "not registered", "cannot be processed", "timed out", 
            "something went wrong", "payment failed", "transaction unsuccessful", 
            "unsuccessful at issuer bank", "declined by bank", "invalid recipient",
            "fraud validation error", "2799", "validation error", "fraud"
        ]

        start_time = time.time()
        attempt = 0
        while time.time() - start_time < 15:
            attempt += 1
            dump_path = self.adb.dump_layout(xml_dump_path)
            
            if dump_path and os.path.exists(dump_path):
                try:
                    with open(dump_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                    
                    success_matches = [w for w in success_keywords if w in content]
                    failure_matches = [w for w in failure_keywords if w in content]
                    
                    if len(success_matches) > 0:
                        self.adb.take_screenshot(screenshot_path)
                        elapsed = round(time.time() - start_time, 1)
                        self.adb.log_success(f"OTP window confirmed for lead {phone} in {elapsed}s! Matches: {success_matches}")
                        return "PASSED"
                    elif len(failure_matches) > 0:
                        self.adb.take_screenshot(screenshot_path)
                        elapsed = round(time.time() - start_time, 1)
                        self.adb.log_warn(f"Failure / Fraud indicator detected for lead {phone} in {elapsed}s: {failure_matches}")
                        return "FAILED"
                except Exception:
                    pass
            
            time.sleep(0.25)

        self.adb.take_screenshot(screenshot_path)
        self.adb.log_warn(f"OTP page was NOT reached for lead {phone} after 15s. Marking as FAILED.")
        return "FAILED"




    def process_csv_file(self):
        input_csv = self.config.get("csv_input_file", "leads.csv")
        output_csv = self.config.get("csv_output_file", "leads_results.csv")
        
        if not os.path.exists(input_csv):
            self.adb.log_err(f"Input CSV '{input_csv}' not found.")
            return

        # Load existing results to support resume
        processed_leads = {}
        if os.path.exists(output_csv):
            try:
                with open(output_csv, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        p = clean_phone_number(row.get('phone_number', ''))
                        if p and row.get('status') not in ['pending', '']:
                            processed_leads[p] = row.get('status')
            except Exception as e:
                self.adb.log_warn(f"Existing results read error: {e}")

        # Read input leads
        leads = []
        try:
            with open(input_csv, 'r', newline='', encoding='utf-8') as f:
                first_line = f.readline()
                f.seek(0)
                if 'phone' in first_line.lower() or ',' in first_line:
                    reader = csv.DictReader(f)
                    for row in reader:
                        leads.append(row)
                else:
                    for line in f:
                        line_str = line.strip()
                        if line_str:
                            leads.append({'phone_number': line_str})
        except Exception as e:
            self.adb.log_err(f"Failed to read '{input_csv}': {e}")
            return

        total_leads = len(leads)
        filter_bank = str(self.target_bank_filter).strip()
        self.adb.log_info(f"Loaded {total_leads} leads from '{input_csv}'. Bank Target Filter: '{filter_bank}'")
        
        headers = ['phone_number', 'bank', 'email', 'status', 'timestamp']
        file_mode = 'a' if os.path.exists(output_csv) and os.path.getsize(output_csv) > 0 else 'w'
        
        with open(output_csv, file_mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if file_mode == 'w':
                writer.writeheader()

            for index, lead in enumerate(leads, 1):
                if self.stop_requested:
                    self.adb.log_warn("Automation stopped by user.")
                    break

                raw_phone = lead.get('phone_number', '')
                clean_phone = clean_phone_number(raw_phone)
                email = lead.get('email', '').strip()

                if not clean_phone:
                    continue

                if clean_phone in processed_leads:
                    self.adb.log_info(f"[{index}/{total_leads}] Skipping {clean_phone} (Already processed: {processed_leads[clean_phone]})")
                    continue

                lead_bank = lead.get('bank', '').strip()
                if not lead_bank:
                    if filter_bank and filter_bank.lower() not in ["all banks", "all", ""]:
                        lead_bank = filter_bank
                    else:
                        lead_bank = self.default_bank

                print(f"\n{Fore.MAGENTA}{'='*60}")
                print(f"PROCESSING LEAD {index}/{total_leads}: {clean_phone} | Bank: {lead_bank}")
                print(f"{'='*60}{Style.RESET_ALL}")

                status = "FAILED"
                try:
                    status = self.run_flow_for_lead(clean_phone, lead_bank, email)
                except Exception as e:
                    self.adb.log_err(f"Exception processing lead {clean_phone}: {e}")
                    status = "ERROR"

                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow({
                    'phone_number': clean_phone,
                    'bank': lead_bank,
                    'email': email,
                    'status': status,
                    'timestamp': timestamp
                })
                f.flush()

                # Write to passed_leads.csv or failed_leads.csv in real-time
                update_passed_and_failed_csv(clean_phone, lead_bank, email, status, timestamp)

                # Instantly update input leads.csv status so GUI shows progress immediately
                update_lead_status_in_input_csv(input_csv, clean_phone, status)

                # Trigger real-time GUI refresh callback
                if hasattr(self, 'on_lead_callback') and self.on_lead_callback:
                    try:
                        self.on_lead_callback(clean_phone, status, lead_bank, email)
                    except Exception as cb_err:
                        self.adb.log_warn(f"GUI callback warning: {cb_err}")

                if status in ["PASSED", "OTP_SENT"]:
                    print(f"{Fore.GREEN}--> RESULT: Lead {clean_phone} [PASSED - Valid Number]{Style.RESET_ALL}")
                elif status == "FAILED":
                    print(f"{Fore.RED}--> RESULT: Lead {clean_phone} [FAILED - Invalid / No OTP]{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}--> RESULT: Lead {clean_phone} [{status}]{Style.RESET_ALL}")

                time.sleep(0.2)

        self.adb.log_success(f"All leads processed! Results written to '{output_csv}'")


class MultiDeviceRunner:
    """Manages parallel multi-phone execution for lead processing across all connected Android devices."""

    def __init__(self, config_path="config.json", on_lead_callback=None, log_callback=None):
        self.config_path = config_path
        self.on_lead_callback = on_lead_callback
        self.log_callback = log_callback
        self.stop_requested = False
        self.active_runners = []
        self.file_lock = threading.Lock()

    def request_stop(self):
        self.stop_requested = True
        for runner in self.active_runners:
            runner.stop_requested = True

    def run(self):
        temp_inst = KarwaAutomation(self.config_path)
        config = temp_inst.config
        target_ip = config.get("adb_target_ip", "")
        
        devices = ADBManager.discover_all_devices(adb_path=temp_inst.adb.adb_path, target_ips=target_ip)
        
        if not devices:
            print(f"{Fore.RED}[ERROR] No connected Android devices detected. Please check USB debugging / Wi-Fi ADB.{Style.RESET_ALL}")
            if self.log_callback:
                self.log_callback("ERROR", "No connected Android devices detected.")
            return

        print(f"{Fore.GREEN}[MULTI-DEVICE] Active devices detected ({len(devices)}): {devices}{Style.RESET_ALL}")
        if self.log_callback:
            self.log_callback("SUCCESS", f"Multi-device active connection ({len(devices)}): {', '.join(devices)}")

        if len(devices) == 1:
            runner = KarwaAutomation(self.config_path, device_serial=devices[0])
            runner.on_lead_callback = self.on_lead_callback
            if self.log_callback:
                runner.adb.log_callback = self.log_callback
            self.active_runners.append(runner)
            if runner.setup_connection():
                runner.process_csv_file()
            return

        input_csv = config.get("csv_input_file", "leads.csv")
        output_csv = config.get("csv_output_file", "leads_results.csv")
        
        if not os.path.exists(input_csv):
            print(f"{Fore.RED}[ERROR] Input CSV '{input_csv}' not found.{Style.RESET_ALL}")
            return

        processed_leads = set()
        if os.path.exists(output_csv):
            try:
                with open(output_csv, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        p = clean_phone_number(row.get('phone_number', ''))
                        if p and row.get('status') not in ['pending', '']:
                            processed_leads.add(p)
            except Exception:
                pass

        lead_queue = queue.Queue()
        raw_leads = []
        try:
            with open(input_csv, 'r', newline='', encoding='utf-8') as f:
                first_line = f.readline()
                f.seek(0)
                if 'phone' in first_line.lower() or ',' in first_line:
                    reader = csv.DictReader(f)
                    for row in reader:
                        raw_leads.append(row)
                else:
                    for line in f:
                        line_str = line.strip()
                        if line_str:
                            raw_leads.append({'phone_number': line_str})
        except Exception as e:
            print(f"{Fore.RED}Error reading input CSV: {e}{Style.RESET_ALL}")
            return

        filter_bank = str(config.get("target_bank_filter", "All Banks")).strip()
        default_bank = config.get("default_bank", "Commercial Bank of Qatar")

        to_process = []
        for item in raw_leads:
            p = clean_phone_number(item.get('phone_number', ''))
            if p and p not in processed_leads:
                b = item.get('bank', '').strip()
                if not b:
                    b = filter_bank if filter_bank and filter_bank.lower() not in ["all banks", "all", ""] else default_bank
                e = item.get('email', '').strip()
                to_process.append((p, b, e))

        for item in to_process:
            lead_queue.put(item)

        total_to_do = len(to_process)
        print(f"{Fore.CYAN}[MULTI-DEVICE] Queue populated with {total_to_do} leads to process across {len(devices)} phones in parallel.{Style.RESET_ALL}")

        sync_barrier = threading.Barrier(len(devices)) if len(devices) > 1 else None

        def worker(device_serial):
            runner = KarwaAutomation(self.config_path, device_serial=device_serial, sync_barrier=sync_barrier)
            if self.log_callback:
                runner.adb.log_callback = lambda level, msg: self.log_callback(level, f"[{device_serial}] {msg}")
            
            if not runner.setup_connection():
                print(f"{Fore.RED}[{device_serial}] Connection failed. Worker exiting.{Style.RESET_ALL}")
                return

            self.active_runners.append(runner)

            while not lead_queue.empty() and not self.stop_requested and not runner.stop_requested:
                try:
                    p, b, e = lead_queue.get_nowait()
                except queue.Empty:
                    break

                print(f"\n{Fore.MAGENTA}[{device_serial}] Processing Lead: {p} | Bank: {b}{Style.RESET_ALL}")
                
                status = "FAILED"
                try:
                    status = runner.run_flow_for_lead(p, b, e)
                except Exception as ex:
                    print(f"{Fore.RED}[{device_serial}] Error processing {p}: {ex}{Style.RESET_ALL}")
                    status = "ERROR"

                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                with self.file_lock:
                    file_mode = 'a' if os.path.exists(output_csv) and os.path.getsize(output_csv) > 0 else 'w'
                    with open(output_csv, file_mode, newline='', encoding='utf-8') as out_f:
                        writer = csv.DictWriter(out_f, fieldnames=['phone_number', 'bank', 'email', 'status', 'timestamp'])
                        if file_mode == 'w':
                            writer.writeheader()
                        writer.writerow({'phone_number': p, 'bank': b, 'email': e, 'status': status, 'timestamp': timestamp})
                        out_f.flush()

                    update_passed_and_failed_csv(p, b, e, status, timestamp)
                    update_lead_status_in_input_csv(input_csv, p, status)

                    if self.on_lead_callback:
                        try:
                            self.on_lead_callback(p, status, b, e)
                        except Exception:
                            pass

                lead_queue.task_done()

        threads = []
        for dev in devices:
            t = threading.Thread(target=worker, args=(dev,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        print(f"{Fore.GREEN}[MULTI-DEVICE] All workers finished! Results written to '{output_csv}'{Style.RESET_ALL}")


if __name__ == "__main__":
    runner = MultiDeviceRunner()
    runner.run()
