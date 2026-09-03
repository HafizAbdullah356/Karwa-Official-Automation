import os
import sys
import csv
import json
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
# pyrefly: ignore [missing-import]
import customtkinter as ctk

from automation import KarwaAutomation, clean_phone_number
from adb_manager import ADBManager

# Set CustomTkinter theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Color Palette for Karwa Official Automation (Teal / Cyan Dark Theme)
COLOR_BG = "#07222B"
COLOR_HEADER_BG = "#0C2E3A"
COLOR_CARD_BG = "#113A49"
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_MUTED = "#80B3BD"
COLOR_CYAN_ACCENT = "#00D2D3"
COLOR_TEAL_ACCENT = "#008B9B"

COLOR_VALID = "#00E6A5"
COLOR_FAILED = "#FF5252"
COLOR_PENDING = "#FFB703"

COLOR_BTN_START = "#00A896"
COLOR_BTN_START_HOVER = "#028090"
COLOR_BTN_STOP = "#E63946"
COLOR_BTN_STOP_HOVER = "#C52838"
COLOR_BTN_CLEAR = "#D97706"
COLOR_BTN_CLEAR_HOVER = "#B45309"
COLOR_BTN_NEUTRAL = "#1B4958"
COLOR_BTN_NEUTRAL_HOVER = "#143843"

class KarwaOfficialGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("KARWA OFFICIAL AUTOMATION - Fawran Wallet")
        self.geometry("1100x750")
        self.minsize(950, 650)
        self.configure(fg_color=COLOR_BG)

        # Automation runner instance and thread
        self.runner = None
        self.worker_thread = None
        self.is_running = False

        # Build UI layout
        self._create_header()
        self._create_action_bar()
        self._create_stats_bar()
        self._create_tab_view()

        # Load initial data
        self.load_config()
        self.refresh_adb_status()
        self.reload_leads_table()
        self.reload_results_table()

    def _create_header(self):
        """Header section with title, device status, and wireless ADB input."""
        header_frame = ctk.CTkFrame(self, fg_color=COLOR_HEADER_BG, corner_radius=12)
        header_frame.pack(fill="x", padx=15, pady=(15, 5))

        # Title
        title_label = ctk.CTkLabel(
            header_frame, 
            text="🚗 KARWA OFFICIAL AUTOMATION", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=COLOR_CYAN_ACCENT
        )
        title_label.pack(side="left", padx=15, pady=12)

        # Wireless ADB Entry & Connect
        self.ip_entry = ctk.CTkEntry(
            header_frame, 
            placeholder_text="Wireless IP (e.g. 192.168.0.101:5555)",
            width=230,
            fg_color="#082630",
            border_color=COLOR_TEAL_ACCENT,
            text_color="#FFFFFF"
        )
        self.ip_entry.pack(side="right", padx=(5, 15), pady=12)

        connect_btn = ctk.CTkButton(
            header_frame, 
            text="Connect IP", 
            width=90, 
            fg_color=COLOR_TEAL_ACCENT, 
            hover_color="#006B7B",
            text_color="#FFFFFF",
            command=self.connect_wireless_ip
        )
        connect_btn.pack(side="right", padx=5, pady=12)

        # Device Status Indicator
        self.status_badge = ctk.CTkLabel(
            header_frame, 
            text="🔴 Disconnected", 
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#1B4958",
            text_color="#FF5252",
            corner_radius=6,
            padx=10,
            pady=4
        )
        self.status_badge.pack(side="right", padx=10, pady=12)

        refresh_btn = ctk.CTkButton(
            header_frame, 
            text="🔄 Refresh ADB", 
            width=110, 
            fg_color=COLOR_BTN_NEUTRAL, 
            hover_color=COLOR_BTN_NEUTRAL_HOVER,
            command=self.refresh_adb_status
        )
        refresh_btn.pack(side="right", padx=5, pady=12)

    def _create_action_bar(self):
        """Action bar with Start, Stop, Bank Filter, Clear buttons."""
        action_frame = ctk.CTkFrame(self, fg_color="transparent")
        action_frame.pack(fill="x", padx=15, pady=5)

        self.btn_start = ctk.CTkButton(
            action_frame, 
            text="▶ START AUTOMATION", 
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_BTN_START, 
            hover_color=COLOR_BTN_START_HOVER,
            height=40,
            command=self.start_automation
        )
        self.btn_start.pack(side="left", padx=(0, 5), expand=True, fill="x")

        self.btn_stop = ctk.CTkButton(
            action_frame, 
            text="⏹ STOP", 
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=COLOR_BTN_STOP, 
            hover_color=COLOR_BTN_STOP_HOVER,
            height=40,
            state="disabled",
            command=self.stop_automation
        )
        self.btn_stop.pack(side="left", padx=5, expand=True, fill="x")

        # Target Selected Bank Dropdown
        lbl_filter = ctk.CTkLabel(
            action_frame, 
            text="🏦 Selected Bank:", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_CYAN_ACCENT
        )
        lbl_filter.pack(side="left", padx=(8, 3))

        self.combo_target_bank = ctk.CTkComboBox(
            action_frame, 
            values=[
                "Commercial Bank of Qatar", "Qatar National Bank", 
                "Doha Bank", "Qatar Islamic Bank", "Masraf Al Rayan", 
                "Dukhan Bank", "Ahlibank", "Qatar International Islamic Bank", "Lesha Bank"
            ], 
            width=220,
            height=40,
            fg_color="#082630", 
            border_color=COLOR_TEAL_ACCENT, 
            button_color=COLOR_TEAL_ACCENT
        )
        self.combo_target_bank.set("Commercial Bank of Qatar")
        self.combo_target_bank.pack(side="left", padx=5)

        btn_clear_res = ctk.CTkButton(
            action_frame, 
            text="🗑 Clear Results", 
            font=ctk.CTkFont(size=13),
            fg_color=COLOR_BTN_CLEAR, 
            hover_color=COLOR_BTN_CLEAR_HOVER,
            height=40,
            command=self.clear_results_history
        )
        btn_clear_res.pack(side="left", padx=5, expand=True, fill="x")

        btn_reload = ctk.CTkButton(
            action_frame, 
            text="📂 Reload Data", 
            font=ctk.CTkFont(size=13),
            fg_color=COLOR_BTN_NEUTRAL, 
            hover_color=COLOR_BTN_NEUTRAL_HOVER,
            height=40,
            command=self.reload_all
        )
        btn_reload.pack(side="left", padx=(5, 0), expand=True, fill="x")

    def _create_stats_bar(self):
        """Stats summary cards and progress bar."""
        stats_frame = ctk.CTkFrame(self, fg_color=COLOR_HEADER_BG, corner_radius=12)
        stats_frame.pack(fill="x", padx=15, pady=5)

        # Cards Frame
        cards_layout = ctk.CTkFrame(stats_frame, fg_color="transparent")
        cards_layout.pack(fill="x", padx=10, pady=(10, 5))

        # Stat Card 1: Total Leads
        self.card_total = self._build_stat_card(cards_layout, "TOTAL LEADS", "0", COLOR_CYAN_ACCENT)
        self.card_total.pack(side="left", expand=True, fill="x", padx=5)

        # Stat Card 2: OTP Sent (Valid)
        self.card_valid = self._build_stat_card(cards_layout, "OTP SENT (VALID)", "0", COLOR_VALID)
        self.card_valid.pack(side="left", expand=True, fill="x", padx=5)

        # Stat Card 3: Failed / Invalid
        self.card_failed = self._build_stat_card(cards_layout, "FAILED / INVALID", "0", COLOR_FAILED)
        self.card_failed.pack(side="left", expand=True, fill="x", padx=5)

        # Stat Card 4: Pending
        self.card_pending = self._build_stat_card(cards_layout, "PENDING", "0", COLOR_PENDING)
        self.card_pending.pack(side="left", expand=True, fill="x", padx=5)

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(stats_frame, height=10, progress_color=COLOR_BTN_START)
        self.progress_bar.pack(fill="x", padx=15, pady=(5, 10))
        self.progress_bar.set(0.0)

    def _build_stat_card(self, parent, title, initial_val, color):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD_BG, corner_radius=8)
        lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLOR_TEXT_MUTED)
        lbl_title.pack(anchor="w", padx=10, pady=(8, 2))
        lbl_val = ctk.CTkLabel(card, text=initial_val, font=ctk.CTkFont(size=20, weight="bold"), text_color=color)
        lbl_val.pack(anchor="w", padx=10, pady=(0, 8))
        card.val_label = lbl_val
        return card

    def _create_tab_view(self):
        """Main Tabview containing Leads Table, Live Logs, Results, and Settings."""
        self.tabview = ctk.CTkTabview(
            self, 
            corner_radius=12,
            fg_color=COLOR_HEADER_BG,
            segmented_button_fg_color="#092832",
            segmented_button_selected_color=COLOR_TEAL_ACCENT,
            segmented_button_selected_hover_color="#006B7B"
        )
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(5, 15))

        self.tab_leads = self.tabview.add("📊 Leads List (leads.csv)")
        self.tab_logs = self.tabview.add("📟 Real-Time Logs")
        self.tab_results = self.tabview.add("📋 Results (leads_results.csv)")
        self.tab_settings = self.tabview.add("⚙ Settings")

        self._build_leads_tab()
        self._build_logs_tab()
        self._build_results_tab()
        self._build_settings_tab()

    # -------------------------------------------------------------------
    # TAB 1: LEADS CSV MANAGEMENT
    # -------------------------------------------------------------------
    def _build_leads_tab(self):
        # Top input controls to add lead
        input_frame = ctk.CTkFrame(self.tab_leads, fg_color="transparent")
        input_frame.pack(fill="x", pady=5)

        self.ent_phone = ctk.CTkEntry(
            input_frame, 
            placeholder_text="Mobile Number (e.g. 33516015)", 
            width=250,
            fg_color="#082630",
            border_color=COLOR_TEAL_ACCENT
        )
        self.ent_phone.pack(side="left", padx=5)

        btn_add = ctk.CTkButton(input_frame, text="+ Add Lead", fg_color=COLOR_BTN_START, hover_color=COLOR_BTN_START_HOVER, width=110, command=self.add_lead_entry)
        btn_add.pack(side="left", padx=5)

        btn_del = ctk.CTkButton(input_frame, text="Delete Selected", fg_color=COLOR_BTN_STOP, hover_color=COLOR_BTN_STOP_HOVER, width=120, command=self.delete_selected_lead)
        btn_del.pack(side="right", padx=5)

        # Treeview Table for Leads
        tree_frame = ctk.CTkFrame(self.tab_leads, fg_color="#092832")
        tree_frame.pack(fill="both", expand=True, pady=5)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#092832", foreground="#E0F2F1", fieldbackground="#092832", rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=COLOR_CARD_BG, foreground=COLOR_CYAN_ACCENT, font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[("selected", COLOR_TEAL_ACCENT)])

        columns = ("phone", "email", "status")
        self.tree_leads = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        
        self.tree_leads.heading("phone", text="Phone Number")
        self.tree_leads.heading("email", text="Email")
        self.tree_leads.heading("status", text="Status")

        self.tree_leads.column("phone", width=200, anchor="center")
        self.tree_leads.column("email", width=300, anchor="w")
        self.tree_leads.column("status", width=150, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_leads.yview)
        self.tree_leads.configure(yscrollcommand=scrollbar.set)

        self.tree_leads.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def reload_leads_table(self):
        for item in self.tree_leads.get_children():
            self.tree_leads.delete(item)

        leads_file = "leads.csv"
        total = 0
        if os.path.exists(leads_file):
            try:
                with open(leads_file, 'r', encoding='utf-8') as f:
                    first_line = f.readline()
                    f.seek(0)
                    if 'phone' in first_line.lower() or ',' in first_line:
                        reader = csv.DictReader(f)
                        for row in reader:
                            total += 1
                            st = row.get('status') or 'pending'
                            self.tree_leads.insert("", "end", values=(
                                row.get('phone_number', ''),
                                row.get('email', ''),
                                st
                            ))
                    else:
                        for line in f:
                            p = line.strip()
                            if p:
                                total += 1
                                self.tree_leads.insert("", "end", values=(p, '', 'pending'))
            except Exception as e:
                self.log_gui("ERROR", f"Failed to read leads.csv: {e}")

        self.card_total.val_label.configure(text=str(total))
        self.update_stats_summary()

    def add_lead_entry(self):
        phone = self.ent_phone.get().strip()
        if not phone:
            messagebox.showwarning("Missing Input", "Please enter a valid mobile number.")
            return

        clean = clean_phone_number(phone)
        leads_file = "leads.csv"
        file_exists = os.path.exists(leads_file) and os.path.getsize(leads_file) > 0

        with open(leads_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['phone_number', 'email', 'status'])
            writer.writerow([clean, '', 'pending'])

        self.ent_phone.delete(0, 'end')
        self.reload_leads_table()

    def delete_selected_lead(self):
        selected = self.tree_leads.selection()
        if not selected:
            return
        
        item = self.tree_leads.item(selected[0])
        phone_to_del = item['values'][0]

        leads_file = "leads.csv"
        rows = []
        if os.path.exists(leads_file):
            with open(leads_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if str(row.get('phone_number')).strip() != str(phone_to_del).strip():
                        rows.append(row)

        with open(leads_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['phone_number', 'email', 'status'])
            writer.writeheader()
            writer.writerows(rows)

        self.reload_leads_table()

    # -------------------------------------------------------------------
    # TAB 2: REAL-TIME LOG CONSOLE
    # -------------------------------------------------------------------
    def _build_logs_tab(self):
        log_frame = ctk.CTkFrame(self.tab_logs, fg_color="transparent")
        log_frame.pack(fill="both", expand=True)

        self.log_text = ctk.CTkTextbox(
            log_frame, 
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#04181F", 
            text_color="#00D2D3"
        )
        self.log_text.pack(fill="both", expand=True, pady=(0, 5))

        btn_clear_log = ctk.CTkButton(
            log_frame, 
            text="Clear Console Log", 
            fg_color=COLOR_BTN_NEUTRAL, 
            hover_color=COLOR_BTN_NEUTRAL_HOVER,
            width=150,
            command=lambda: self.log_text.delete("1.0", "end")
        )
        btn_clear_log.pack(anchor="e")

    def log_gui(self, level, msg):
        """Thread-safe logging to GUI console text widget."""
        def append():
            timestamp = time.strftime("%H:%M:%S")
            prefix = f"[{timestamp}] [{level}] "
            
            self.log_text.insert("end", prefix + str(msg) + "\n")
            self.log_text.see("end")

            # Check if log relates to lead result updates
            if "RESULT:" in msg or "OTP window confirmed" in msg or "Failure" in msg or "Skipping" in msg:
                self.after(500, self.reload_results_table)

        self.after(0, append)

    # -------------------------------------------------------------------
    # TAB 3: RESULTS MANAGEMENT (leads_results.csv)
    # -------------------------------------------------------------------
    def _build_results_tab(self):
        # Action bar for export buttons
        btn_frame = ctk.CTkFrame(self.tab_results, fg_color="transparent")
        btn_frame.pack(fill="x", pady=5)

        lbl_res = ctk.CTkLabel(btn_frame, text="📋 Execution Results History", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLOR_CYAN_ACCENT)
        lbl_res.pack(side="left", padx=5)

        btn_exp_passed = ctk.CTkButton(
            btn_frame, 
            text="📥 Export Passed CSV", 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_VALID, 
            text_color="#000000",
            hover_color="#00C48C",
            width=160,
            command=self.export_passed_csv
        )
        btn_exp_passed.pack(side="right", padx=5)

        btn_exp_failed = ctk.CTkButton(
            btn_frame, 
            text="📥 Export Failed CSV", 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLOR_FAILED, 
            text_color="#FFFFFF",
            hover_color="#D32F2F",
            width=160,
            command=self.export_failed_csv
        )
        btn_exp_failed.pack(side="right", padx=5)

        tree_frame = ctk.CTkFrame(self.tab_results, fg_color="#092832")
        tree_frame.pack(fill="both", expand=True, pady=5)

        columns = ("phone", "bank", "email", "status", "timestamp")
        self.tree_results = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        self.tree_results.heading("phone", text="Phone Number")
        self.tree_results.heading("bank", text="Bank Provider")
        self.tree_results.heading("email", text="Customer Email")
        self.tree_results.heading("status", text="Result Status")
        self.tree_results.heading("timestamp", text="Processed Time")

        self.tree_results.column("phone", width=130, anchor="center")
        self.tree_results.column("bank", width=220, anchor="w")
        self.tree_results.column("email", width=220, anchor="w")
        self.tree_results.column("status", width=160, anchor="center")
        self.tree_results.column("timestamp", width=160, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_results.yview)
        self.tree_results.configure(yscrollcommand=scrollbar.set)

        self.tree_results.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def export_passed_csv(self):
        passed_file = "passed_leads.csv"
        if not os.path.exists(passed_file) or os.path.getsize(passed_file) <= 0:
            messagebox.showinfo("No Passed Leads", "No passed leads (OTP Sent) recorded yet.")
            return
        
        dest = filedialog.asksaveasfilename(
            title="Export Passed Leads CSV",
            initialfile="passed_leads.csv",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if dest:
            try:
                import shutil
                shutil.copyfile(passed_file, dest)
                messagebox.showinfo("Export Successful", f"Passed leads exported successfully to:\n{dest}")
                self.log_gui("SUCCESS", f"Passed leads exported to {dest}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export passed leads: {e}")

    def export_failed_csv(self):
        failed_file = "failed_leads.csv"
        if not os.path.exists(failed_file) or os.path.getsize(failed_file) <= 0:
            messagebox.showinfo("No Failed Leads", "No failed leads recorded yet.")
            return
        
        dest = filedialog.asksaveasfilename(
            title="Export Failed Leads CSV",
            initialfile="failed_leads.csv",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        if dest:
            try:
                import shutil
                shutil.copyfile(failed_file, dest)
                messagebox.showinfo("Export Successful", f"Failed leads exported successfully to:\n{dest}")
                self.log_gui("SUCCESS", f"Failed leads exported to {dest}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export failed leads: {e}")

    def reload_results_table(self):
        for item in self.tree_results.get_children():
            self.tree_results.delete(item)

        results_file = "leads_results.csv"
        valid_count = 0
        failed_count = 0

        if os.path.exists(results_file):
            try:
                with open(results_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        st = str(row.get('status', 'FAILED')).strip()
                        display_st = "FAILED / INVALID"
                        
                        if st in ["PASSED", "OTP_SENT"]:
                            valid_count += 1
                            display_st = "PASSED"
                        else:
                            failed_count += 1
                            display_st = "FAILED"

                        self.tree_results.insert("", "end", values=(
                            row.get('phone_number', ''),
                            row.get('bank', ''),
                            row.get('email', ''),
                            display_st,
                            row.get('timestamp', '')
                        ))
            except Exception:
                pass

        self.card_valid.val_label.configure(text=str(valid_count))
        self.card_failed.val_label.configure(text=str(failed_count))
        self.update_stats_summary()

    def update_stats_summary(self):
        total_leads = int(self.card_total.val_label.cget("text") or "0")
        valid_leads = int(self.card_valid.val_label.cget("text") or "0")
        failed_leads = int(self.card_failed.val_label.cget("text") or "0")

        processed = valid_leads + failed_leads
        pending = max(0, total_leads - processed)
        self.card_pending.val_label.configure(text=str(pending))

        if total_leads > 0:
            ratio = processed / float(total_leads)
            self.progress_bar.set(ratio)
        else:
            self.progress_bar.set(0.0)

    def clear_results_history(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all execution results in leads_results.csv?"):
            for fname in ["leads_results.csv", "passed_leads.csv", "failed_leads.csv"]:
                if os.path.exists(fname):
                    with open(fname, 'w', newline='', encoding='utf-8') as f:
                        f.write("phone_number,bank,email,status,timestamp\n")
            self.reload_results_table()
            self.log_gui("INFO", "Results history cleared cleanly.")

    # -------------------------------------------------------------------
    # TAB 4: CONFIGURATION & SETTINGS
    # -------------------------------------------------------------------
    def _build_settings_tab(self):
        container = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # Default Bank
        lbl_bank = ctk.CTkLabel(container, text="Default Bank Provider:", font=ctk.CTkFont(weight="bold"), text_color=COLOR_TEXT_PRIMARY)
        lbl_bank.pack(anchor="w", pady=(10, 2))
        self.cfg_bank = ctk.CTkComboBox(container, values=[
            "Commercial Bank of Qatar", "Qatar National Bank", "Doha Bank", 
            "Qatar Islamic Bank", "Masraf Al Rayan", "Dukhan Bank", 
            "Ahlibank", "Qatar International Islamic Bank"
        ], width=350, fg_color="#082630", border_color=COLOR_TEAL_ACCENT, button_color=COLOR_TEAL_ACCENT)
        self.cfg_bank.pack(anchor="w", pady=(0, 10))

        # Default Email
        lbl_email = ctk.CTkLabel(container, text="Default Customer Email:", font=ctk.CTkFont(weight="bold"), text_color=COLOR_TEXT_PRIMARY)
        lbl_email.pack(anchor="w", pady=(10, 2))
        self.cfg_email = ctk.CTkEntry(container, width=350, fg_color="#082630", border_color=COLOR_TEAL_ACCENT)
        self.cfg_email.pack(anchor="w", pady=(0, 10))

        # Location Rotation Checkbox
        self.var_loc = ctk.BooleanVar(value=True)
        self.chk_loc = ctk.CTkCheckBox(container, text="🌐 Rotate Device GPS Location (Qatar Area per lead)", variable=self.var_loc, text_color=COLOR_TEXT_PRIMARY)
        self.chk_loc.pack(anchor="w", pady=(10, 5))

        # IP Rotation Checkbox
        self.var_ip = ctk.BooleanVar(value=False)
        self.chk_ip = ctk.CTkCheckBox(container, text="🔄 Rotate Mobile IP (Airplane Mode Reset per lead)", variable=self.var_ip, text_color=COLOR_TEXT_PRIMARY)
        self.chk_ip.pack(anchor="w", pady=(5, 5))

        # Clear Cache Checkbox
        self.var_cache = ctk.BooleanVar(value=True)
        self.chk_cache = ctk.CTkCheckBox(container, text="🧹 Clear App & WebView Cache (Auto per lead)", variable=self.var_cache, text_color=COLOR_TEXT_PRIMARY)
        self.chk_cache.pack(anchor="w", pady=(5, 10))

        # HTTP Proxy Setting
        lbl_proxy = ctk.CTkLabel(container, text="HTTP Proxy (Optional - e.g. 192.168.1.50:8080 or leave blank):", font=ctk.CTkFont(weight="bold"), text_color=COLOR_TEXT_PRIMARY)
        lbl_proxy.pack(anchor="w", pady=(10, 2))
        self.cfg_proxy = ctk.CTkEntry(container, width=350, fg_color="#082630", border_color=COLOR_TEAL_ACCENT, placeholder_text="ip:port or leave empty")
        self.cfg_proxy.pack(anchor="w", pady=(0, 10))

        # Step Delay
        lbl_delay = ctk.CTkLabel(container, text="Step Delay (seconds):", font=ctk.CTkFont(weight="bold"), text_color=COLOR_TEXT_PRIMARY)
        lbl_delay.pack(anchor="w", pady=(10, 2))
        self.cfg_delay = ctk.CTkEntry(container, width=150, fg_color="#082630", border_color=COLOR_TEAL_ACCENT)
        self.cfg_delay.pack(anchor="w", pady=(0, 10))

        # Save Button
        btn_save_cfg = ctk.CTkButton(container, text="💾 Save Configuration", fg_color=COLOR_BTN_START, hover_color=COLOR_BTN_START_HOVER, command=self.save_config)
        btn_save_cfg.pack(anchor="w", pady=20)

    def load_config(self):
        cfg_file = "config.json"
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    ip = data.get("adb_target_ip", "")
                    self.ip_entry.delete(0, 'end')
                    self.ip_entry.insert(0, ip)

                    self.cfg_bank.set(data.get("default_bank", "Commercial Bank of Qatar"))
                    self.combo_target_bank.set(data.get("target_bank_filter", "All Banks"))
                    
                    self.cfg_email.delete(0, 'end')
                    self.cfg_email.insert(0, data.get("default_email", "musaahmad261261@gmail.com"))

                    self.cfg_delay.delete(0, 'end')
                    self.cfg_delay.insert(0, str(data.get("delay_between_steps", 1.2)))

                    self.var_loc.set(data.get("rotate_location_per_lead", True))
                    self.var_ip.set(data.get("rotate_ip_per_lead", False))
                    self.var_cache.set(data.get("clear_cache_per_lead", True))

                    self.cfg_proxy.delete(0, 'end')
                    self.cfg_proxy.insert(0, data.get("http_proxy", ""))
            except Exception:
                pass

    def save_config(self):
        cfg_file = "config.json"
        data = {}
        if os.path.exists(cfg_file):
            try:
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception:
                pass

        data["adb_target_ip"] = self.ip_entry.get().strip()
        data["default_bank"] = self.cfg_bank.get().strip()
        data["target_bank_filter"] = self.combo_target_bank.get().strip()
        data["default_email"] = self.cfg_email.get().strip()
        data["rotate_location_per_lead"] = bool(self.var_loc.get())
        data["rotate_ip_per_lead"] = bool(self.var_ip.get())
        data["clear_cache_per_lead"] = bool(self.var_cache.get())
        data["http_proxy"] = self.cfg_proxy.get().strip()
        try:
            data["delay_between_steps"] = float(self.cfg_delay.get().strip())
        except ValueError:
            data["delay_between_steps"] = 1.2
        except ValueError:
            data["delay_between_steps"] = 1.2

        with open(cfg_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        messagebox.showinfo("Saved", "Configuration updated successfully!")
        self.log_gui("INFO", "Configuration saved to config.json")

    # -------------------------------------------------------------------
    # ADB & AUTOMATION WORKER THREAD LOGIC
    # -------------------------------------------------------------------
    def refresh_adb_status(self):
        """Checks ADB device connectivity and updates badge."""
        def check():
            target_ip = self.ip_entry.get().strip()
            adb = ADBManager(target_ip=target_ip if target_ip else None)
            
            res = adb.run_cmd(["devices"])
            output = res[0]

            lines = output.strip().split("\n")[1:] if "\n" in output else []
            devices = [line.split()[0] for line in lines if line.strip() and "device" in line]

            def update_ui():
                if devices:
                    serial = devices[0]
                    self.status_badge.configure(
                        text=f"🟢 Connected [{serial}]", 
                        fg_color="#0A4234", 
                        text_color="#00E6A5"
                    )
                    self.log_gui("SUCCESS", f"ADB Device connected: {serial}")
                else:
                    self.status_badge.configure(
                        text="🔴 Disconnected", 
                        fg_color="#1B4958", 
                        text_color="#FF5252"
                    )
                    self.log_gui("WARN", "No active ADB device detected. Ensure USB Debugging is ON.")

            self.after(0, update_ui)

        threading.Thread(target=check, daemon=True).start()

    def connect_wireless_ip(self):
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showwarning("Missing IP", "Please enter target IP:Port for wireless debugging.")
            return

        def task():
            self.save_config()
            self.log_gui("INFO", f"Attempting wireless connection to {ip}...")
            adb = ADBManager(target_ip=ip)
            adb.connect()
            self.refresh_adb_status()

        threading.Thread(target=task, daemon=True).start()

    def handle_lead_completed(self, phone, status, bank, email):
        """Instant real-time update triggered as soon as each single lead finishes."""
        def update():
            self.reload_leads_table()
            self.reload_results_table()
        self.after(0, update)

    def start_automation(self):
        if self.is_running:
            return

        self.save_config()
        self.is_running = True
        self.btn_start.configure(state="disabled", fg_color=COLOR_BTN_NEUTRAL)
        self.btn_stop.configure(state="normal", fg_color=COLOR_BTN_STOP)
        self.tabview.set("📟 Real-Time Logs")

        target_bank = self.combo_target_bank.get().strip()

        def worker():
            try:
                self.runner = KarwaAutomation()
                self.runner.target_bank_filter = target_bank
                # Attach GUI logging & real-time result hooks
                self.runner.adb.log_callback = self.log_gui
                self.runner.on_lead_callback = self.handle_lead_completed
                
                if self.runner.setup_connection():
                    self.log_gui("INFO", f"Starting automated CSV processing loop [Target Bank Filter: '{target_bank}']...")
                    self.runner.process_csv_file()
                else:
                    self.log_gui("ERROR", "Connection setup failed. Please authorize ADB on phone.")
            except Exception as e:
                self.log_gui("ERROR", f"Automation execution error: {e}")
            finally:
                def reset_buttons():
                    self.is_running = False
                    self.btn_start.configure(state="normal", fg_color=COLOR_BTN_START)
                    self.btn_stop.configure(state="disabled", fg_color=COLOR_BTN_NEUTRAL)
                    self.reload_all()
                    self.log_gui("INFO", "Automation thread finished.")

                self.after(0, reset_buttons)

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()

    def stop_automation(self):
        if self.runner:
            self.log_gui("WARN", "Stopping automation after current step...")
            self.runner.stop_requested = True
        self.btn_stop.configure(state="disabled")

    def reload_all(self):
        self.reload_leads_table()
        self.reload_results_table()
        self.refresh_adb_status()


if __name__ == "__main__":
    app = KarwaOfficialGUI()
    app.mainloop()
