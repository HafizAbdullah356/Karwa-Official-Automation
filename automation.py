import os
import sys
import csv
import json
import time
import random
import string
import re
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
                fieldnames = list(reader.fieldnames or ['phone_number', 'email'])
                if 'status' not in fieldnames:
                    fieldnames.append('status')
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

    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.adb = ADBManager(target_ip=self.config.get("adb_target_ip"))
        
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

    def load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"{Fore.RED}Error loading config: {e}. Using defaults.{Style.RESET_ALL}")
            return {}

    def log_step(self, step_name):
        print(f"\n{Fore.CYAN}=================== STEP: {step_name} ==================={Style.RESET_ALL}")

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
        
        # 1. Check if already on Home screen
        if self.adb.find_element(text="Account") or self.adb.find_element(text="Our Services"):
            self.adb.log_success("Already on Karwa App home screen.")
            return True

        # Dismiss soft keyboard if open
        self.adb.dismiss_keyboard()

        # 2. Try clicking top-left back button (ivBack) to exit WebView / Payment screen in 1 click
        iv_back = self.adb.find_element(resource_id="ivBack", fuzzy=True)
        if iv_back:
            self.adb.log_info(f"Clicking top-left Back button (ivBack) at ({iv_back['x']}, {iv_back['y']})...")
            self.adb.tap(iv_back['x'], iv_back['y'])
            time.sleep(1.0)
            if self.adb.find_element(text="Account") or self.adb.find_element(text="Our Services"):
                self.adb.log_success("Successfully returned to Home screen via top-left Back button.")
                return True

        # 3. Try tapping Account tab (bottom-right) directly to reset view 
        self.adb.log_info("Tapping Account tab (bottom-right) to exit sub-screen...")
        self.adb.tap_ratio(0.88, 0.95)
        time.sleep(1.0)
        if self.adb.find_element(text="Account") or self.adb.find_element(text="Our Services"):
            self.adb.log_success("Successfully returned to Home screen via Account tab tap.")
            return True

        # 4. Fallback: Press Android Back key up to 2 times
        for i in range(2):
            self.adb.log_info(f"Pressing Back key [{i+1}/2]...")
            self.adb.go_back()
            time.sleep(0.8)

            dialog_btn = self.adb.find_element(text="Yes") or self.adb.find_element(text="OK") or self.adb.find_element(text="Cancel")
            if dialog_btn:
                self.adb.tap(dialog_btn['x'], dialog_btn['y'])
                time.sleep(0.5)

            if self.adb.find_element(text="Account") or self.adb.find_element(text="Our Services"):
                self.adb.log_success("Returned to Home screen.")
                return True

        # 5. Final fallback: Bring Karwa MainActivity to front smoothly
        self.adb.log_info("Bringing Karwa MainActivity to front...")
        self.adb.start_app(self.package, self.activity)
        time.sleep(1.0)
        return True

    def wait_for_payment_webview_ready(self, timeout=45):
        """Polls until WebView progressbar spinner disappears and HTML content (customerEmail / 100.00 QAR) is rendered."""
        start = time.time()
        temp_file = os.path.join(self.debug_dir, "temp_webview_dump.xml")
        
        while time.time() - start < timeout:
            dump_path = self.adb.dump_layout(temp_file)
            if dump_path:
                try:
                    with open(dump_path, 'r', encoding='utf-8') as f:
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
            time.sleep(0.8)
            
        self.adb.log_warn("Payment WebView ready check timed out after 45s.")
        return False

    def run_flow_for_lead(self, phone_raw, bank_name=None, email=None):
        phone = clean_phone_number(phone_raw)
        bank = bank_name.strip() if bank_name and bank_name.strip() else self.default_bank
        
        # Always generate a unique random @gmail.com email if email is not explicitly provided in lead
        if not email or not str(email).strip() or "@" not in str(email):
            email = generate_random_email()

        self.adb.log_info(f"Target Lead -> Mobile: {phone} (Raw: {phone_raw}) | Bank: {bank} | Email: {email}")

        try:
            # ----------------------------------------------------
            # 0. Ensure screen awake & rotate Location / IP / Proxy
            # ----------------------------------------------------
            self.adb.wake_and_unlock()

            if self.config.get("rotate_location_per_lead", True):
                self.log_step("Rotating Device Location (Qatar GPS)")
                try:
                    self.adb.rotate_device_location()
                except Exception as loc_err:
                    self.adb.log_warn(f"Location rotation warning: {loc_err}")

            if self.config.get("rotate_ip_per_lead", False):
                self.log_step("Rotating Device IP (Airplane Mode Reset)")
                try:
                    self.adb.rotate_ip_address()
                except Exception as ip_err:
                    self.adb.log_warn(f"IP rotation warning: {ip_err}")

            proxy_list = self.config.get("proxy_list", [])
            if proxy_list and isinstance(proxy_list, list) and len(proxy_list) > 0:
                import random
                chosen_proxy = random.choice(proxy_list)
                self.log_step(f"Setting Device Proxy: {chosen_proxy}")
                self.adb.set_http_proxy(chosen_proxy)
            elif self.config.get("http_proxy"):
                self.adb.set_http_proxy(self.config.get("http_proxy"))

            if self.config.get("clear_cache_per_lead", True):
                self.log_step("Clearing Application & WebView Cache")
                try:
                    self.adb.clear_app_cache(self.package)
                except Exception as cache_err:
                    self.adb.log_warn(f"Cache clear warning: {cache_err}")

            # ----------------------------------------------------
            # 1. Ensure App Home Screen is Active (App stays open!)
            # ----------------------------------------------------
            self.log_step("Navigating to App Home Screen")
            self.reset_to_app_home()
            time.sleep(self.delay)

            # ----------------------------------------------------
            # 2. Tap Account Tab (Bottom-Right)
            # ----------------------------------------------------
            self.log_step("Navigating to Account Tab")
            if not self.adb.wait_and_click(text="Account", timeout=self.timeout, step_delay=0.5):
                self.adb.log_warn("Account element not found by text. Clicking bottom-right ratio.")
                self.adb.tap_ratio(0.88, 0.95)

            # SMART WAIT: Wait for Account screen / Wallet option to render before proceeding!
            wallet_indicator, _ = self.adb.wait_for_any_element([
                {"text": "Wallet"},
                {"text": "My Wallet", "fuzzy": True},
                {"text": "Top Up", "fuzzy": True}
            ], timeout=12)
            if not wallet_indicator:
                self.adb.log_warn("Account page wallet indicator not detected yet, retrying click...")
                self.adb.tap_ratio(0.88, 0.95)
                wallet_indicator, _ = self.adb.wait_for_any_element([{"text": "Wallet"}, {"text": "My Wallet", "fuzzy": True}], timeout=5)

            # ----------------------------------------------------
            # 3. Tap Wallet Item
            # ----------------------------------------------------
            self.log_step("Navigating to Wallet")
            if not self.adb.wait_and_click(text="Wallet", timeout=self.timeout, step_delay=0.5):
                self.adb.log_warn("Wallet text element not found. Clicking ratio position.")
                self.adb.tap_ratio(0.20, 0.39)

            # SMART WAIT: Wait for Wallet screen (Top Up Wallet) to load before proceeding!
            topup_indicator, _ = self.adb.wait_for_any_element([
                {"text": "Top Up Wallet"},
                {"text": "Top Up", "fuzzy": True},
                {"text": "Add Money", "fuzzy": True}
            ], timeout=12)
            if not topup_indicator:
                self.adb.log_warn("Top Up Wallet indicator not detected yet, retrying ratio tap...")
                self.adb.tap_ratio(0.20, 0.39)
                topup_indicator, _ = self.adb.wait_for_any_element([{"text": "Top Up Wallet"}, {"text": "Top Up", "fuzzy": True}], timeout=5)

            # ----------------------------------------------------
            # 4. Tap Top Up Wallet
            # ----------------------------------------------------
            self.log_step("Clicking Top Up Wallet")
            if not self.adb.wait_and_click(text="Top Up Wallet", timeout=self.timeout, step_delay=0.5):
                self.adb.log_warn("Top Up Wallet not found by text. Clicking top-up card ratio.")
                self.adb.tap_ratio(0.27, 0.31)

            # SMART WAIT: Wait for Top Up screen (100 QAR / Amount options / Add funds) to load!
            amount_indicator, _ = self.adb.wait_for_any_element([
                {"text": "100 QAR"},
                {"text": "Add funds"},
                {"text": "QAR", "fuzzy": True}
            ], timeout=12)
            if not amount_indicator:
                self.adb.log_warn("Amount selection screen not detected, retrying top-up card tap...")
                self.adb.tap_ratio(0.27, 0.31)
                amount_indicator, _ = self.adb.wait_for_any_element([{"text": "100 QAR"}, {"text": "Add funds"}], timeout=5)

            # ----------------------------------------------------
            # 5. Select 100 QAR and Add Funds
            # ----------------------------------------------------
            self.log_step("Selecting 100 QAR and adding funds")
            if not self.adb.wait_and_click(text="100 QAR", timeout=8, step_delay=0.5):
                self.adb.log_warn("100 QAR option not found by text. Clicking ratio.")
                self.adb.tap_ratio(0.50, 0.32)
                time.sleep(0.5)

            if not self.adb.wait_and_click(text="Add funds", timeout=8, step_delay=0.5):
                self.adb.log_warn("Add funds button not found. Clicking bottom button ratio.")
                self.adb.tap_ratio(0.50, 0.94)

            # ----------------------------------------------------
            # 6. Enter Customer Email on Payment Web View
            # ----------------------------------------------------
            self.log_step("Entering Email on Payment Web View")
            target_email = email.strip() if email and email.strip() and "@" in email else generate_random_email()

            self.adb.log_info(f"Targeting customer email: {target_email}")
            
            # DYNAMIC WAIT: Wait for ProgressBar to disappear and HTML form (customerEmail / 100.00 QAR) to load!
            if not self.wait_for_payment_webview_ready(timeout=45):
                self.adb.log_warn("Payment WebView HTML loading delayed. Retrying Add funds button tap...")
                self.adb.tap_ratio(0.50, 0.94)
                self.wait_for_payment_webview_ready(timeout=20)

            # DYNAMIC ELEMENT SEARCH: Search for email element without auto-scroll
            email_elem, _ = self.adb.wait_for_any_element([
                {"resource_id": "customerEmail"},
                {"text": "email", "fuzzy": True},
                {"class_name": "android.widget.EditText"}
            ], timeout=5, poll_interval=0.5, auto_scroll=False)

            if email_elem:
                self.adb.log_info(f"Focusing email input at ({email_elem['x']}, {email_elem['y']})...")
                self.adb.clear_and_type(target_email, element=email_elem, backspace_count=0)
            else:
                self.adb.log_info("Tapping center position of email input box (0.50, 0.42)...")
                self.adb.clear_and_type(target_email, rx=0.50, ry=0.42, backspace_count=0)

            time.sleep(0.5)

            # DYNAMIC VERIFICATION: Check if email field needs re-tap
            verify_kw, _ = self.adb.wait_for_page_to_contain([
                "customer email is required", "valid email"
            ], timeout=1.5)

            if verify_kw:
                self.adb.log_warn("Email field missing text. Re-focusing and re-entering email...")
                self.adb.tap_ratio(0.50, 0.42)
                time.sleep(0.4)
                self.adb.input_text(target_email)
                time.sleep(0.5)

            self.adb.dismiss_keyboard()
            time.sleep(0.5)

            # Click Pay button (auto_scroll=False so it doesn't swipe away)
            self.log_step("Clicking Pay")
            pay_btn, _ = self.adb.wait_for_any_element([
                {"text": "Pay", "class_name": "android.widget.Button"},
                {"text": "Pay", "fuzzy": True}
            ], timeout=8, auto_scroll=False)

            if pay_btn:
                self.adb.tap(pay_btn['x'], pay_btn['y'])
            else:
                self.adb.log_warn("Pay button not found by text. Tapping Pay button ratio (0.50, 0.52).")
                self.adb.tap_ratio(0.50, 0.52)

            # DYNAMIC PAGE GUARD: Poll up to 45s for QPAY Gateway screen to load!
            gw_ready, gw_kw = self.adb.wait_for_page_to_contain([
                "fawran", "qpay", "select payment", "cardless"
            ], timeout=45, poll_interval=0.5)

            if not gw_ready:
                self.adb.log_warn("QPAY Gateway screen loading delayed. Retrying Pay tap...")
                self.adb.tap_ratio(0.50, 0.52)
                gw_ready, gw_kw = self.adb.wait_for_page_to_contain([
                    "fawran", "qpay", "select payment", "cardless"
                ], timeout=20, poll_interval=0.5)

            self.adb.log_success(f"QPAY Gateway screen confirmed (matched '{gw_kw}')!")

            # ----------------------------------------------------
            # 7. Select Fawran in QPAY Gateway
            # ----------------------------------------------------
            self.log_step("Selecting Fawran Payment Method")
            
            fawran_btn, _ = self.adb.wait_for_any_element([
                {"text": "Fawran", "class_name": "android.widget.Button"},
                {"text": "Fawran", "fuzzy": True},
                {"content_desc": "Fawran", "fuzzy": True}
            ], timeout=20)

            if fawran_btn:
                self.adb.tap(fawran_btn['x'], fawran_btn['y'])
            else:
                self.adb.log_warn("Fawran button not found by XML. Tapping Cardless/Fawran ratio.")
                self.adb.tap_ratio(0.50, 0.76)

            # DYNAMIC WAIT: Wait up to 35s for Fawran Details screen (Bank selection / Mobile input) to load!
            fawran_ready, f_kw = self.adb.wait_for_page_to_contain([
                "bank", "select bank", "fawranprovider", "mobile number", "aliasvalue"
            ], timeout=35, poll_interval=0.5)

            self.adb.log_success(f"Fawran Details screen confirmed ready (matched '{f_kw}')!")

            time.sleep(0.8)

            # Small scroll up to ensure Proceed to Payment is visible and clickable
            self.adb.swipe(self.adb.screen_width // 2, int(self.adb.screen_height * 0.75), 
                           self.adb.screen_width // 2, int(self.adb.screen_height * 0.50), 300)
            time.sleep(0.5)

            # Click Proceed to Payment
            self.log_step("Clicking Proceed to Payment")
            proceed_btn, _ = self.adb.wait_for_any_element([
                {"text": "Proceed to Payment", "class_name": "android.widget.Button"},
                {"text": "Proceed to Payment", "fuzzy": True},
                {"text": "Proceed", "fuzzy": True}
            ], timeout=10)

            if proceed_btn:
                self.adb.tap(proceed_btn['x'], proceed_btn['y'])
            else:
                self.adb.log_warn("Proceed to Payment button not found. Tapping bottom ratio.")
                self.adb.tap_ratio(0.50, 0.82)

            # STRICT PAGE GUARD: Wait up to 20s to confirm Fawran Details screen before proceeding to Step 8!
            fawran_page_kw, _ = self.adb.wait_for_page_to_contain([
                "aliasvalue", "fawranprovider", "select a provider", "mobile number", "enter fawran details"
            ], timeout=20)

            if not fawran_page_kw:
                self.adb.log_warn("Fawran Details screen not detected after Proceed tap. Retrying Proceed ratio tap...")
                self.adb.tap_ratio(0.50, 0.82)
                fawran_page_kw, _ = self.adb.wait_for_page_to_contain([
                    "aliasvalue", "fawranprovider", "select a provider", "mobile number", "enter fawran details"
                ], timeout=10)

            # ----------------------------------------------------
            # 8. Enter Fawran Details (Bank Provider & Mobile Number)
            # ----------------------------------------------------
            self.log_step(f"Configuring Fawran Details: Bank='{bank}', Phone='{phone}'")

            # Select Bank Provider
            self.adb.log_info(f"Selecting bank provider: {bank}")
            provider_dropdown, _ = self.adb.wait_for_any_element([
                {"resource_id": "fawranProvider"},
                {"text": "Select a provider", "fuzzy": True},
                {"text": "provider", "fuzzy": True}
            ], timeout=15)

            if provider_dropdown:
                self.adb.tap(provider_dropdown['x'], provider_dropdown['y'])
            else:
                self.adb.log_warn("Provider dropdown element not found by XML. Tapping ratio position.")
                self.adb.tap_ratio(0.50, 0.40)

            # SMART WAIT: Wait for dropdown list/options to render in XML
            time.sleep(1.2)

            # Fast single-dump bank search & multi-pass scroll
            search_terms = get_bank_search_terms(bank)
            bank_found = False

            for scroll_pass in range(4):
                dump_file = os.path.join(self.debug_dir, f"bank_dump_pass{scroll_pass}.xml")
                dump_path = self.adb.dump_layout(dump_file)
                if dump_path:
                    for term in search_terms:
                        bank_elem = self.adb.find_element_in_dump(dump_path, text=term, fuzzy=True)
                        if bank_elem:
                            self.adb.tap(bank_elem['x'], bank_elem['y'])
                            self.adb.log_success(f"Bank '{term}' selected successfully (Pass {scroll_pass + 1}).")
                            bank_found = True
                            break

                if bank_found:
                    break

                if scroll_pass < 3:
                    self.adb.log_info(f"Bank '{bank}' (terms: {search_terms}) not visible in dropdown. Scrolling list (Attempt {scroll_pass + 1})...")
                    cx = self.adb.screen_width // 2
                    y_start = int(self.adb.screen_height * 0.65)
                    y_end = int(self.adb.screen_height * 0.40)
                    self.adb.swipe(cx, y_start, cx, y_end, 300)
                    time.sleep(0.8)

            if not bank_found:
                # Deep fuzzy check for core bank keywords (e.g. "doha", "rayan", "dukhan", "islamic", "ahli", "qiib")
                bank_words = [w.lower() for w in bank.replace("of", "").replace("qatar", "").replace("bank", "").split() if len(w) >= 3]
                self.adb.log_info(f"Attempting deep keyword search for bank: {bank_words}")
                for word in bank_words:
                    bank_elem = self.adb.find_element(text=word, fuzzy=True)
                    if bank_elem:
                        self.adb.tap(bank_elem['x'], bank_elem['y'])
                        self.adb.log_success(f"Bank selected via deep fuzzy match for '{word}' at ({bank_elem['x']}, {bank_elem['y']}).")
                        bank_found = True
                        break

            if not bank_found:
                self.adb.log_warn(f"Bank '{bank}' not matched in list. Tapping default dropdown item position.")
                self.adb.tap_ratio(0.50, 0.45)

            # MANDATORY SCREEN STABILIZATION PAUSE: Allow Web View to dismiss popup and re-render aliasValue
            self.adb.log_info("Waiting for Fawran Details screen to stabilize after bank selection...")
            time.sleep(2.0)

            # Dynamic Smart Poll for 8-digit mobile number input (aliasValue)
            self.adb.log_info(f"Entering mobile number: {phone}")
            alias_elem, _ = self.adb.wait_for_any_element([
                {"resource_id": "aliasValue"},
                {"text": "Alias Value", "fuzzy": True},
                {"text": "Mobile Number", "fuzzy": True},
                {"class_name": "android.widget.EditText"}
            ], timeout=20, poll_interval=0.5)

            if alias_elem:
                self.adb.log_success(f"Located alias input field at ({alias_elem['x']}, {alias_elem['y']})")
                self.adb.clear_and_type(phone, element=alias_elem)
            else:
                # STRICT RE-CHECK: Poll page for keywords before attempting ratio fallback tap
                self.adb.log_warn("Alias input box not matched by ID on first pass. Polling page for screen confirmation...")
                confirm_kw, _ = self.adb.wait_for_page_to_contain([
                    "aliasvalue", "mobile number", "enter fawran details"
                ], timeout=15)
                if confirm_kw:
                    self.adb.log_warn("Fawran Details screen confirmed. Using ratio input for mobile number.")
                    self.adb.clear_and_type(phone, rx=0.57, ry=0.62)
                else:
                    self.adb.log_err("Screen desynchronized from Fawran details. Unable to input phone number safely.")

            time.sleep(0.5)
            self.adb.dismiss_keyboard()
            time.sleep(0.5)

            # Click Continue Button
            self.log_step("Clicking Continue")
            continue_btn, _ = self.adb.wait_for_any_element([
                {"text": "Continue", "class_name": "android.widget.Button"},
                {"text": "Continue", "fuzzy": True}
            ], timeout=12)

            if continue_btn:
                self.adb.tap(continue_btn['x'], continue_btn['y'])
            else:
                self.adb.log_warn("Continue button not found by XML. Tapping Continue ratio.")
                self.adb.tap_ratio(0.50, 0.77)

            # ----------------------------------------------------
            # 9. Verify OTP / Result Status
            # ----------------------------------------------------
            self.log_step("Verifying OTP / Transaction Status")
            result = self.verify_otp_status(phone)
            return result

        finally:
            # ----------------------------------------------------
            # Clean up: Return to App Home screen for NEXT lead (App stays open!)
            # ----------------------------------------------------
            try:
                self.reset_to_app_home()
            except Exception:
                pass

    def verify_otp_status(self, phone):
        """Analyzes screen XML layout and saves debug screenshots to verify OTP transmission."""
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

        # Smart poll screen over up to 25 seconds (checking every 1.5 seconds)
        start_time = time.time()
        attempt = 0
        while time.time() - start_time < 25:
            attempt += 1
            time.sleep(1.5)
            self.adb.dump_layout(xml_dump_path)
            self.adb.take_screenshot(screenshot_path)
            
            if os.path.exists(xml_dump_path):
                with open(xml_dump_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                
                success_matches = [w for w in success_keywords if w in content]
                failure_matches = [w for w in failure_keywords if w in content]
                
                elapsed = int(time.time() - start_time)
                self.adb.log_info(f"Screen Analysis [Check {attempt} | {elapsed}s] -> Success: {success_matches} | Failure: {failure_matches}")

                if len(success_matches) > 0:
                    self.adb.log_success(f"OTP window confirmed for lead {phone}! Matches: {success_matches}")
                    return "PASSED"
                elif len(failure_matches) > 0:
                    self.adb.log_warn(f"Failure / Fraud indicator detected for lead {phone}: {failure_matches}")
                    return "FAILED"

        # If OTP page was not detected after smart waiting, mark as FAILED (Invalid/No OTP page)
        self.adb.log_warn(f"OTP page was NOT reached for lead {phone} after 25s smart wait. Marking as FAILED. Saved screenshot to {screenshot_path}")
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

                time.sleep(1)

        self.adb.log_success(f"All leads processed! Results written to '{output_csv}'")


if __name__ == "__main__":
    runner = KarwaAutomation()
    if runner.setup_connection():
        runner.process_csv_file()
    else:
        print(f"{Fore.RED}Please connect your device with USB Debugging enabled.{Style.RESET_ALL}")
