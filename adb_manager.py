import os
import sys
import re
import time
import zipfile
import urllib.request
import subprocess
import xml.etree.ElementTree as ET
from colorama import Fore, Style, init

# Initialize colorama for colored terminal output
init(autoreset=True)

class ADBManager:
    """Professional ADB Automation Manager for Android Device Control."""
    
    def __init__(self, target_ip=None, local_dir="platform-tools-bin"):
        self.target_ip = target_ip
        self.local_dir = os.path.abspath(local_dir)
        self.adb_path = "adb"
        self.device_serial = None
        self.screen_width = 1080
        self.screen_height = 2340
        
        self.log_callback = None
        self.log_info("Initializing ADB Manager...")
        self._setup_adb()

    def log_info(self, msg):
        print(f"{Fore.BLUE}[INFO]{Style.RESET_ALL} {msg}")
        if self.log_callback:
            self.log_callback("INFO", msg)

    def log_success(self, msg):
        print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} {msg}")
        if self.log_callback:
            self.log_callback("SUCCESS", msg)

    def log_warn(self, msg):
        print(f"{Fore.YELLOW}[WARN]{Style.RESET_ALL} {msg}")
        if self.log_callback:
            self.log_callback("WARN", msg)

    def log_err(self, msg):
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} {msg}")
        if self.log_callback:
            self.log_callback("ERROR", msg)

    def _setup_adb(self):
        """Checks for ADB or downloads platform-tools automatically if not found."""
        if self._check_adb_executable("adb"):
            self.adb_path = "adb"
            self.log_success("ADB detected in system PATH.")
            return

        local_adb = os.path.join(self.local_dir, "platform-tools", "adb.exe")
        if os.path.exists(local_adb):
            self.adb_path = local_adb
            self.log_success(f"ADB detected locally at: {local_adb}")
            return

        self.log_warn("ADB not found. Starting automatic download of Android Platform-Tools...")
        try:
            os.makedirs(self.local_dir, exist_ok=True)
            zip_path = os.path.join(self.local_dir, "platform-tools.zip")
            url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
            
            self.log_info(f"Downloading from {url}...")
            urllib.request.urlretrieve(url, zip_path)
            self.log_info("Extracting ZIP archive...")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.local_dir)
                
            os.remove(zip_path)
            
            if os.path.exists(local_adb):
                self.adb_path = local_adb
                self.log_success(f"ADB configured successfully at: {local_adb}")
            else:
                raise FileNotFoundError("adb.exe was not found in extracted folder.")
        except Exception as e:
            self.log_err(f"Failed to set up ADB automatically: {e}")
            sys.exit(1)

    def _check_adb_executable(self, adb_cmd):
        try:
            subprocess.run([adb_cmd, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception:
            return False

    def run_cmd(self, args, timeout=15):
        """Runs an ADB command targeting the active device serial."""
        cmd = [self.adb_path]
        if self.device_serial:
            cmd.extend(["-s", self.device_serial])
        elif self.target_ip and args and args[0] not in ["connect", "devices"]:
            cmd.extend(["-s", self.target_ip])
        cmd.extend(args)
        
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            self.log_err(f"Command timed out: {' '.join(cmd)}")
            return "", "Timeout", -1
        except Exception as e:
            self.log_err(f"Command execution error: {e}")
            return "", str(e), -1

    def connect(self):
        """Discovers and connects to the target USB or wireless device."""
        if self.target_ip and str(self.target_ip).count('.') >= 3 and len(str(self.target_ip).strip()) >= 7:
            self.log_info(f"Connecting to wireless target: {self.target_ip}...")
            out, err, code = self.run_cmd(["connect", self.target_ip], timeout=3)
            self.log_info(f"Connect status: {out}")

        raw_cmd = [self.adb_path, "devices"]
        try:
            res = subprocess.run(raw_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            lines = res.stdout.strip().split("\n")[1:]
            devices = []
            for line in lines:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        devices.append((parts[0], parts[1]))
            
            if not devices:
                self.log_err("No connected Android devices detected.")
                self.log_info("Please ensure USB debugging is ENABLED and phone is connected.")
                return False

            self.log_info(f"Connected devices detected: {devices}")
            for serial, state in devices:
                if state == "device":
                    if self.target_ip and serial == self.target_ip:
                        self.device_serial = serial
                        break
                    elif not self.target_ip:
                        self.device_serial = serial
                        self.log_info(f"Targeting active device: {serial}")
                        break
            
            if not self.device_serial and devices:
                self.device_serial = devices[0][0]
                self.log_warn(f"Targeting first available device: {self.device_serial} (State: {devices[0][1]})")

            size = self.get_screen_size()
            if size:
                self.screen_width, self.screen_height = size
                self.log_success(f"Device resolution: {self.screen_width}x{self.screen_height}")

            self.log_success(f"Device connection verified [{self.device_serial}].")
            return True
        except Exception as e:
            self.log_err(f"Error establishing device connection: {e}")
            return False

    def get_screen_size(self):
        """Returns device screen resolution (width, height)."""
        out, err, code = self.run_cmd(["shell", "wm", "size"])
        match = re.search(r'(\d+)\s*x\s*(\d+)', out)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None

    def start_app(self, package, activity=None):
        """Launches the target application package/activity."""
        self.log_info(f"Launching app: {package}")
        if activity:
            self.run_cmd(["shell", "am", "start", "-n", f"{package}/{activity}"])
        else:
            self.run_cmd(["shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"])

    def stop_app(self, package):
        """Force stops the target app."""
        self.log_info(f"Closing app: {package}")
        self.run_cmd(["shell", "am", "force-stop", package])
        time.sleep(1)

    def tap(self, x, y):
        """Taps screen coordinate (x, y)."""
        self.run_cmd(["shell", "input", "tap", str(int(x)), str(int(y))])

    def tap_ratio(self, rx, ry):
        """Taps screen using percentage of resolution (0.0 to 1.0)."""
        x = int(self.screen_width * rx)
        y = int(self.screen_height * ry)
        self.tap(x, y)

    def swipe(self, x1, y1, x2, y2, duration_ms=300):
        """Performs a touch swipe gesture."""
        self.run_cmd(["shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms))])

    def wake_and_unlock(self):
        """Wakes the screen and unlocks device if locked."""
        self.run_cmd(["shell", "input", "keyevent", "224"])  # KEYCODE_WAKEUP
        time.sleep(0.3)
        self.run_cmd(["shell", "wm", "dismiss-keyguard"])
        time.sleep(0.3)

    def go_back(self):
        """Presses Android Back key."""
        self.key_event(4)  # KEYCODE_BACK
        time.sleep(0.5)

    def swipe_up(self, duration_ms=300):
        """Swipes up the screen to scroll down."""
        cx = self.screen_width // 2
        y1 = int(self.screen_height * 0.75)
        y2 = int(self.screen_height * 0.40)
        self.swipe(cx, y1, cx, y2, duration_ms)

    def key_event(self, key_code):
        """Sends an Android KEYCODE event."""
        self.run_cmd(["shell", "input", "keyevent", str(key_code)])

    def rotate_device_location(self, lat_range=(25.1500, 25.3800), lon_range=(51.4200, 51.5600)):
        """Spoofs/rotates device GPS coordinates randomly within Qatar region."""
        import random
        lat = round(random.uniform(lat_range[0], lat_range[1]), 6)
        lon = round(random.uniform(lon_range[0], lon_range[1]), 6)
        self.log_info(f"Rotating device GPS location to Qatar: Lat {lat}, Lon {lon}...")
        
        self.run_cmd(["shell", "cmd", "location", "set-location", "--latitude", str(lat), "--longitude", str(lon)])
        self.run_cmd(["shell", "settings", "put", "secure", "location_mode", "3"])
        self.run_cmd(["shell", "am", "broadcast", "-a", "android.intent.action.LOCATION_CHANGED",
                      "--ef", "latitude", str(lat), "--ef", "longitude", str(lon)])
        self.log_success(f"Device GPS location updated -> Lat: {lat}, Lon: {lon}")
        return lat, lon

    def rotate_ip_address(self, pause_sec=3):
        """Toggles Airplane mode via ADB to force new IP allocation from cellular network."""
        self.log_info("Rotating mobile IP address via Airplane mode toggle...")
        
        self.run_cmd(["shell", "cmd", "connectivity", "airplane-mode", "enable"])
        self.run_cmd(["shell", "settings", "put", "global", "airplane_mode_on", "1"])
        self.run_cmd(["shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "true"])
        time.sleep(pause_sec)
        
        self.run_cmd(["shell", "cmd", "connectivity", "airplane-mode", "disable"])
        self.run_cmd(["shell", "settings", "put", "global", "airplane_mode_on", "0"])
        self.run_cmd(["shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "false"])
        
        self.log_info("Waiting for mobile data network re-connection...")
        time.sleep(4)
        self.log_success("Mobile IP rotated successfully!")
        return True

    def set_http_proxy(self, proxy_str):
        """Configures or clears HTTP proxy on device."""
        if not proxy_str or str(proxy_str).strip().lower() in ["none", "", "clear", "false"]:
            self.log_info("Clearing device HTTP proxy...")
            self.run_cmd(["shell", "settings", "delete", "global", "http_proxy"])
            self.run_cmd(["shell", "settings", "delete", "global", "global_http_proxy_host"])
            self.run_cmd(["shell", "settings", "delete", "global", "global_http_proxy_port"])
            self.log_success("HTTP Proxy cleared.")
        else:
            p = str(proxy_str).strip()
            self.log_info(f"Setting device HTTP proxy: {p}...")
            self.run_cmd(["shell", "settings", "put", "global", "http_proxy", p])
            self.log_success(f"Device HTTP proxy configured: {p}")

    def clear_app_cache(self, package="com.karwatechnologies.karwa"):
        """Clears app temporary cache files safely without closing or restarting the app."""
        self.log_info(f"Trimming temporary cache for '{package}'...")
        self.run_cmd(["shell", "pm", "trim-caches", "50M"])
        self.run_cmd(["shell", "rm", "-rf", f"/sdcard/Android/data/{package}/cache/*"])
        self.log_success("Application cache trimmed safely (App stays open).")
        return True

    def dismiss_keyboard(self):
        """Hides on-screen soft keyboard if visible."""
        self.key_event(111)  # KEYCODE_ESCAPE
        time.sleep(0.3)

    def _escape_adb_text(self, text):
        escaped = ""
        for char in str(text):
            if char == ' ':
                escaped += '%s'
            elif char in ['&', '<', '>', '|', ';', '(', ')', '$', '*', "'", '"', '`', '\\', '?', '[', ']', '{', '}']:
                escaped += '\\' + char
            else:
                escaped += char
        return escaped

    def input_text(self, text):
        """Inputs string text via ADB with robust character escaping."""
        escaped = self._escape_adb_text(text)
        self.run_cmd(["shell", "input", "text", escaped])

    def clear_field(self, count=25):
        """Clears text in active input field by moving cursor to end and sending backspaces."""
        self.key_event(123)  # KEYCODE_MOVE_END
        for _ in range(count):
            self.key_event(67)  # KEYCODE_DEL
        time.sleep(0.2)

    def clear_and_type(self, text, element=None, rx=None, ry=None, backspace_count=0):
        """Focuses field, clears pre-existing text if requested, and types fresh text directly."""
        if element:
            self.tap(element['x'], element['y'])
        elif rx is not None and ry is not None:
            self.tap_ratio(rx, ry)
        time.sleep(0.5)
        if backspace_count > 0:
            self.clear_field(backspace_count)
        self.input_text(str(text))
        time.sleep(0.5)

    def dump_layout(self, local_path="temp_dump.xml"):
        """Dumps UI hierarchy XML and pulls it to local PC."""
        remote_path = "/sdcard/window_dump.xml"
        out, err, code = self.run_cmd(["shell", "uiautomator", "dump", remote_path], timeout=6)
        if code != 0 or "error" in out.lower() or "error" in err.lower():
            self.run_cmd(["shell", "pkill", "-f", "uiautomator"], timeout=3)
            return None
        out, err, code = self.run_cmd(["pull", remote_path, local_path], timeout=5)
        if code == 0 and os.path.exists(local_path):
            return local_path
        return None

    def take_screenshot(self, local_path="screenshot.png"):
        """Captures device screenshot and pulls it to local PC."""
        remote_path = "/sdcard/screen.png"
        self.run_cmd(["shell", "screencap", "-p", remote_path])
        out, err, code = self.run_cmd(["pull", remote_path, local_path])
        if code == 0 and os.path.exists(local_path):
            return local_path
        return None

    def parse_bounds(self, bounds_str):
        match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
        if match:
            return [int(x) for x in match.groups()]
        return None

    def find_element_in_dump(self, xml_path, text=None, resource_id=None, content_desc=None, class_name=None, fuzzy=False):
        """Searches an existing local XML layout dump file without re-dumping via ADB."""
        if not xml_path or not os.path.exists(xml_path):
            return None
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            for elem in root.iter('node'):
                elem_text = elem.get('text', '').strip()
                elem_id = elem.get('resource-id', '').strip()
                elem_desc = elem.get('content-desc', '').strip()
                elem_class = elem.get('class', '').strip()
                elem_bounds = elem.get('bounds', '').strip()
                
                match = True
                
                if text is not None:
                    if fuzzy:
                        if text.lower() not in elem_text.lower() and text.lower() not in elem_desc.lower():
                            match = False
                    else:
                        if text.lower() != elem_text.lower() and text.lower() != elem_desc.lower():
                            match = False
                
                if resource_id is not None:
                    if fuzzy:
                        if resource_id.lower() not in elem_id.lower():
                            match = False
                    else:
                        if resource_id != elem_id:
                            match = False
                            
                if content_desc is not None:
                    if fuzzy:
                        if content_desc.lower() not in elem_desc.lower():
                            match = False
                    else:
                        if content_desc != elem_desc:
                            match = False
                            
                if class_name is not None:
                    if class_name.lower() not in elem_class.lower():
                        match = False
                
                if match and (text is not None or resource_id is not None or content_desc is not None or class_name is not None):
                    bounds = self.parse_bounds(elem_bounds)
                    if bounds:
                        x1, y1, x2, y2 = bounds
                        if x2 <= x1 or y2 <= y1:
                            continue
                        cx = (x1 + x2) // 2
                        cy = (y1 + y2) // 2
                        return {
                            "text": elem_text,
                            "resource_id": elem_id,
                            "content_desc": elem_desc,
                            "class": elem_class,
                            "bounds": bounds,
                            "x": cx,
                            "y": cy
                        }
        except Exception as e:
            self.log_err(f"Layout parsing error: {e}")
        return None

    def find_element(self, text=None, resource_id=None, content_desc=None, class_name=None, fuzzy=False, dump_file=None):
        """Analyzes UI XML structure to locate elements matching text/id/class."""
        temp_file = dump_file or os.path.join("debug_logs", "temp_ui_dump.xml")
        xml_path = self.dump_layout(temp_file)
        if not xml_path:
            return None
        
        try:
            return self.find_element_in_dump(xml_path, text=text, resource_id=resource_id, content_desc=content_desc, class_name=class_name, fuzzy=fuzzy)
        finally:
            if os.path.exists(temp_file) and not dump_file:
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
        return None

    def wait_for_element(self, text=None, resource_id=None, content_desc=None, class_name=None, fuzzy=False, timeout=12, auto_scroll=False):
        """Polls for element, scrolling down if not found initially when auto_scroll is True."""
        spec = {"text": text, "resource_id": resource_id, "content_desc": content_desc, "class_name": class_name, "fuzzy": fuzzy}
        elem, _ = self.wait_for_any_element([spec], timeout=timeout, auto_scroll=auto_scroll)
        return elem

    def wait_and_click(self, text=None, resource_id=None, content_desc=None, class_name=None, fuzzy=False, timeout=12, step_delay=0.2, auto_scroll=False):
        """Waits for element, scrolling if needed to bring into view, and clicks it."""
        elem = self.wait_for_element(text=text, resource_id=resource_id, content_desc=content_desc, class_name=class_name, fuzzy=fuzzy, timeout=timeout, auto_scroll=auto_scroll)
        if elem:
            label = elem['text'] or elem['resource_id'] or elem['content_desc'] or elem['class']
            self.log_info(f"Clicking element '{label}' at ({elem['x']}, {elem['y']})")
            self.tap(elem['x'], elem['y'])
            if step_delay > 0:
                time.sleep(step_delay)
            return True
        return False

    def wait_for_any_element(self, element_specs, timeout=15, poll_interval=0.3, auto_scroll=False):
        """Polls for any element in specs rapidly. Auto-scrolls down if not found after initial checks when auto_scroll is True."""
        start = time.time()
        temp_file = os.path.join("debug_logs", "temp_poll_dump.xml")
        scrolled = False

        while time.time() - start < timeout:
            dump_file = self.dump_layout(temp_file)
            if dump_file:
                try:
                    for spec in element_specs:
                        elem = self.find_element_in_dump(
                            dump_file,
                            text=spec.get("text"),
                            resource_id=spec.get("resource_id"),
                            content_desc=spec.get("content_desc"),
                            class_name=spec.get("class_name"),
                            fuzzy=spec.get("fuzzy", False)
                        )
                        if elem:
                            return elem, spec
                finally:
                    if os.path.exists(temp_file):
                        try:
                            os.remove(temp_file)
                        except Exception:
                            pass

            # Auto-scroll feature: Only if explicitly enabled and not found after 2.5s
            if auto_scroll and not scrolled and (time.time() - start > 2.5):
                self.log_info("Element not visible on current screen view. Scrolling down to locate button...")
                self.swipe_up(duration_ms=300)
                scrolled = True
                time.sleep(0.4)

            time.sleep(poll_interval)
        return None, None

    def wait_for_page_to_contain(self, keywords, timeout=15, poll_interval=0.3, local_path="temp_page_dump.xml"):
        """Polls UI layout dump until any of the given keywords exist in the page hierarchy."""
        start = time.time()
        if isinstance(keywords, str):
            keywords = [keywords]
        keywords_lower = [k.lower() for k in keywords]
        
        while time.time() - start < timeout:
            dump_file = self.dump_layout(local_path)
            if dump_file and os.path.exists(dump_file):
                try:
                    with open(dump_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                    for kw in keywords_lower:
                        if kw in content:
                            if os.path.exists(dump_file):
                                os.remove(dump_file)
                            return kw, content
                except Exception:
                    pass
                finally:
                    if os.path.exists(dump_file):
                        try:
                            os.remove(dump_file)
                        except Exception:
                            pass
            time.sleep(poll_interval)
        return None, None


