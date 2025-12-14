import customtkinter as ctk
import threading
import time
import random
import os
import json
import urllib.request
import re
import requests
import socks
import socket
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import queue
from tkinter import filedialog
from playwright.sync_api import sync_playwright
from fake_useragent import UserAgent
import urllib3

# Suppress InsecureRequestWarning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Configuration ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


# --- Utils ---
class CTkToolTip(object):
    """
    A simple tooltip class for CustomTkinter widgets.
    """

    def __init__(self, widget, text='widget info'):
        self.wait_time = 500  # milliseconds
        self.wrap_length = 180
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.wait_time, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20

        # creates a toplevel window
        self.tw = ctk.CTkToplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))

        # Tooltip Label
        label = ctk.CTkLabel(self.tw, text=self.text, justify='left',
                             fg_color="#2b2b2b", text_color="white",
                             corner_radius=6, width=100)
        label.pack(ipadx=5, ipady=5)

        # Lift above everything
        self.tw.attributes("-topmost", True)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()


# --- Managers ---

class SettingsManager:
    def __init__(self, filename="settings.json"):
        self.filename = filename
        self.defaults = {
            "url": "https://example.com",
            "threads": "5",
            "visits": "50",
            "headless": True,
            "min_time": "15",
            "max_time": "30",
            "proxy_source": "Manual",
            "proxy_file_path": "",
            "proxy_url": "",
            "proxy_protocol": "HTTP",
            "manual_proxies": "# Example:\n# 192.168.1.1:8080\n# socks5://user:pass@host:port",
            "test_url": "http://httpbin.org/json",  # Better default for checking IP
            "test_timeout": "10",
            "test_threads": "20",
            "test_gateway": ""
        }

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    if data.get("proxy_protocol") in ["SOCKS4", "SOCKS5"]:
                        data["proxy_protocol"] = "SOCKS4/5"
                    return {**self.defaults, **data}
            except Exception as e:
                print(f"Error loading settings: {e}")
                return self.defaults
        return self.defaults

    def save(self, data):
        try:
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")


class ProxyManager:
    @staticmethod
    def load_proxies(source_type, data, default_protocol="http"):
        raw_lines = []
        error_msg = None
        effective_default_protocol = default_protocol.lower()
        if effective_default_protocol == "socks4/5":
            effective_default_protocol = "socks5"

        try:
            if source_type == "Manual":
                raw_lines = data.strip().splitlines()
            elif source_type == "File":
                if os.path.exists(data):
                    with open(data, 'r', encoding='utf-8') as f:
                        raw_lines = f.read().splitlines()
                else:
                    error_msg = f"File not found: {data}"
            elif source_type == "URL":
                if not data:
                    error_msg = "URL is empty"
                else:
                    req = urllib.request.Request(data, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        content = response.read().decode('utf-8')
                        raw_lines = content.splitlines()

        except Exception as e:
            error_msg = str(e)

        if error_msg:
            raise ValueError(error_msg)

        valid_proxies = []
        for line in raw_lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            formatted_proxy = ProxyManager.format_proxy(line, effective_default_protocol)
            if formatted_proxy:
                valid_proxies.append(formatted_proxy)

        return valid_proxies

    @staticmethod
    def format_proxy(proxy_str, default_protocol):
        if "://" in proxy_str:
            return proxy_str
        return f"{default_protocol}://{proxy_str}"


class ProxyChecker:
    @staticmethod
    def get_flag_emoji(country_code):
        if not country_code or len(country_code) != 2:
            return "🏳️"
        return chr(ord(country_code[0]) + 127397) + chr(ord(country_code[1]) + 127397)

    @staticmethod
    def check_proxy(proxy, target_url, timeout, real_ip):
        result = {
            "proxy": proxy,
            "status": "Failed",
            "speed": 0,
            "anonymity": "Unknown",
            "type": proxy.split("://")[0].upper() if "://" in proxy else "Unknown",
            "country": "Unknown",
            "country_code": "",
            "error": ""
        }

        # Setup proxies dict for requests
        proxies = {"http": proxy, "https": proxy}

        try:
            start_time = time.time()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }

            # Using verify=False to handle proxies with self-signed certs (common in free lists)
            response = requests.get(target_url, proxies=proxies, timeout=timeout, verify=False, headers=headers)
            end_time = time.time()

            result["speed"] = int((end_time - start_time) * 1000)
            result["status"] = "Active"

            # --- Advanced Data Parsing ---
            try:
                # Try parsing as JSON (works for httpbin.org/json)
                data = response.json()

                # 1. Anonymity Check
                origin_ip = data.get("origin", "").split(',')[0]  # httpbin can return multiple IPs
                response_headers = data.get("headers", {})

                via = response_headers.get("Via") or response_headers.get("via")
                forwarded = response_headers.get("X-Forwarded-For") or response_headers.get("x-forwarded-for")

                if origin_ip == real_ip:
                    result["anonymity"] = "Transparent"
                elif via or forwarded:
                    result["anonymity"] = "Anonymous"
                else:
                    result["anonymity"] = "Elite"
            except:
                # Fallback for non-JSON endpoints
                result["anonymity"] = "Active"

            # 2. Country/Geo Check (Separate simplified API call to avoid rate limiting the main attack loop)
            # We only do this if the proxy is active
            try:
                # Use the proxy to query an IP API
                # NOTE: Using ip-api.com (free, rate limited) - In production use a DB
                geo_url = "http://ip-api.com/json"
                geo_resp = requests.get(geo_url, proxies=proxies, timeout=5)
                if geo_resp.status_code == 200:
                    geo_data = geo_resp.json()
                    result["country"] = geo_data.get("country", "Unknown")
                    result["country_code"] = geo_data.get("countryCode", "")
            except:
                pass

        except requests.exceptions.ConnectTimeout:
            result["error"] = "Timeout"
        except requests.exceptions.ProxyError:
            result["error"] = "Proxy Error"
        except requests.exceptions.SSLError:
            result["error"] = "SSL Error"
        except Exception as e:
            result["error"] = str(e)

        return result

    @staticmethod
    def detect_and_check(raw_proxy, target_url, timeout, real_ip):
        if "://" in raw_proxy:
            ip_port = raw_proxy.split("://", 1)[1]
        else:
            ip_port = raw_proxy

        protocols = ["http", "https", "socks5", "socks4"]

        for proto in protocols:
            proxy_str = f"{proto}://{ip_port}"
            res = ProxyChecker.check_proxy(proxy_str, target_url, timeout, real_ip)
            if res["status"] == "Active":
                if "socks5" in proto:
                    res["type"] = "SOCKS5"
                elif "socks4" in proto:
                    res["type"] = "SOCKS4"
                elif "https" in proto:
                    res["type"] = "HTTPS"
                elif "http" in proto:
                    res["type"] = "HTTP"
                return res

        return {
            "proxy": raw_proxy,
            "status": "Failed",
            "type": "Unknown",
            "speed": 0,
            "anonymity": "-",
            "country": "-",
            "country_code": "",
            "error": "Connection failed"
        }


class TrafficBotProApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Managers
        self.settings_manager = SettingsManager()
        self.settings = self.settings_manager.load()

        # Window Setup
        self.title("Traffic Bot Pro - Traffic Automation Tool")
        self.geometry("1100x850")
        self.resizable(True, True)

        # State Variables
        self.is_running = False
        self.is_testing = False
        self.proxy_queue = queue.Queue()
        self.ua = UserAgent()
        self.success_count = 0
        self.failure_count = 0
        self.total_tasks = 0
        self.tested_proxies = []
        self.test_stats = {"tested": 0, "active": 0, "dead": 0}
        self.protocol_stats = {"http": 0, "https": 0, "socks4": 0, "socks5": 0}
        self.active_threads = 0
        self.attack_start_time = 0

        # --- Real IP Detection ---
        try:
            self.real_ip = requests.get("https://api.ipify.org", timeout=5).text
        except:
            self.real_ip = "0.0.0.0"
        # -------------------------

        # --- GUI Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Header
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.header_frame.grid(row=0, column=0, sticky="ew", columnspan=2)
        title_label = ctk.CTkLabel(self.header_frame, text="Traffic Bot Pro", font=("Roboto Medium", 20),
                                   text_color="#3B8ED0")
        title_label.pack(pady=10)

        # 2. Main Content
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # -- Sidebar --
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0, fg_color="#1a1a1a")
        self.sidebar_frame.grid(row=1, column=0, sticky="nsw")
        self.sidebar_frame.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(self.sidebar_frame, text="Navigation", font=("Roboto Medium", 16), text_color="#FFFFFF").grid(
            row=0, column=0, padx=20, pady=(20, 10))

        self.dashboard_button = ctk.CTkButton(self.sidebar_frame, text="Dashboard",
                                              command=lambda: self.show_frame("dashboard"), fg_color="#3B8ED0",
                                              hover_color="#297BB5")
        self.dashboard_button.grid(row=1, column=0, padx=20, pady=10)

        self.attack_button = ctk.CTkButton(self.sidebar_frame, text="Traffic Attack",
                                           command=lambda: self.show_frame("attack"), fg_color="#3B8ED0",
                                           hover_color="#297BB5")
        self.attack_button.grid(row=2, column=0, padx=20, pady=10)

        self.proxy_button = ctk.CTkButton(self.sidebar_frame, text="Proxy Manager",
                                          command=lambda: self.show_frame("proxy"), fg_color="#3B8ED0",
                                          hover_color="#297BB5")
        self.proxy_button.grid(row=3, column=0, padx=20, pady=10)

        self.settings_button = ctk.CTkButton(self.sidebar_frame, text="Settings",
                                             command=lambda: self.show_frame("settings"), fg_color="#3B8ED0",
                                             hover_color="#297BB5")
        self.settings_button.grid(row=4, column=0, padx=20, pady=10)

        self.status_label = ctk.CTkLabel(self.sidebar_frame, text="System: ONLINE", font=("Roboto", 10),
                                         text_color="#2CC985")
        self.status_label.grid(row=6, column=0, padx=20, pady=(10, 20), sticky="s")

        # -- Content Frames --
        self.main_content_frame = ctk.CTkFrame(self, fg_color="#1a1a1a")
        self.main_content_frame.grid(row=1, column=1, sticky="nsew", padx=20, pady=10)
        self.main_content_frame.grid_rowconfigure(0, weight=1)
        self.main_content_frame.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for name in ("dashboard", "attack", "proxy", "settings"):
            frame = ctk.CTkFrame(self.main_content_frame, fg_color="transparent")
            self.frames[name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.build_dashboard_frame()
        self.build_attack_frame()
        self.build_proxy_frame()
        self.build_settings_frame()
        self.show_frame("dashboard")

    def build_dashboard_frame(self):
        dashboard = self.frames["dashboard"]
        dashboard.grid_columnconfigure(0, weight=1)
        dashboard.grid_rowconfigure(2, weight=1)

        hud_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        hud_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        hud_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Stat Cards
        for i, (title, attr) in enumerate(
                [("Live Threads", "live_threads_label"), ("Total Proxies", "total_proxies_label"),
                 ("Requests/Sec", "rps_label")]):
            card = ctk.CTkFrame(hud_frame, fg_color="#2b2b2b")
            card.grid(row=0, column=i, padx=10, pady=5, sticky="ew")
            ctk.CTkLabel(card, text=title, font=("Roboto", 12), text_color="#999999").pack(pady=(10, 0))
            lbl = ctk.CTkLabel(card, text="0", font=("Roboto Medium", 24), text_color="#FFFFFF")
            lbl.pack(pady=(0, 10))
            setattr(self, attr, lbl)

        # --- NEW: Success Rate Card ---
        card = ctk.CTkFrame(hud_frame, fg_color="#2b2b2b")
        card.grid(row=0, column=3, padx=10, pady=5, sticky="ew")
        ctk.CTkLabel(card, text="Success Rate", font=("Roboto", 12), text_color="#999999").pack(pady=(10, 0))
        self.success_rate_label = ctk.CTkLabel(card, text="0%", font=("Roboto Medium", 24), text_color="#2CC985")
        self.success_rate_label.pack(pady=(0, 10))
        # ------------------------------

        # Dashboard Progress Section
        dash_prog_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        dash_prog_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        self.dash_status_label = ctk.CTkLabel(dash_prog_frame, text="Status: Idle", text_color="#FFFFFF", anchor="w")
        self.dash_status_label.pack(fill="x", pady=(0, 5))

        self.dash_progress_bar = ctk.CTkProgressBar(dash_prog_frame, fg_color="#2b2b2b", progress_color="#3B8ED0")
        self.dash_progress_bar.pack(fill="x")
        self.dash_progress_bar.set(0)

        # Log Console
        self.dashboard_log_console = ctk.CTkTextbox(dashboard, state="disabled", font=("Consolas", 12),
                                                    fg_color="#2b2b2b", text_color="#FFFFFF")
        self.dashboard_log_console.grid(row=2, column=0, sticky="nsew", padx=10, pady=(5, 10))

    def build_attack_frame(self):
        attack_frame = self.frames["attack"]
        attack_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(attack_frame, text="Bot Configuration", font=("Roboto Medium", 16), text_color="#FFFFFF").pack(
            pady=(15, 10))

        self.url_entry = self.create_labeled_entry(attack_frame, "Target URL:", self.settings["url"])
        self.url_entry.master.pack(fill="x", padx=10, pady=5)

        self.threads_entry = self.create_labeled_entry(attack_frame, "Concurrent Threads:", self.settings["threads"])
        self.threads_entry.master.pack(fill="x", padx=10, pady=5)

        self.visits_entry = self.create_labeled_entry(attack_frame, "Total Visits:", self.settings["visits"])
        self.visits_entry.master.pack(fill="x", padx=10, pady=5)

        # --- Proxy Protocol Selection ---
        protocol_frame = ctk.CTkFrame(attack_frame, fg_color="transparent")
        protocol_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(protocol_frame, text="Proxy Protocol:", text_color="#FFFFFF").pack(side="left", padx=(0, 10))
        self.protocol_var = ctk.StringVar(value=self.settings["proxy_protocol"])
        # Added HTTPS support
        self.protocol_menu = ctk.CTkOptionMenu(protocol_frame, values=["HTTP", "HTTPS", "SOCKS4/5"],
                                               variable=self.protocol_var)
        self.protocol_menu.pack(side="left", fill="x", expand=True)

        duration_frame = ctk.CTkFrame(attack_frame, fg_color="transparent")
        duration_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(duration_frame, text="View Duration (sec):", text_color="#FFFFFF").pack(anchor="w")
        duration_inner = ctk.CTkFrame(duration_frame, fg_color="transparent")
        duration_inner.pack(fill="x")
        self.min_time_entry = ctk.CTkEntry(duration_inner, width=80, placeholder_text="Min", fg_color="#2b2b2b",
                                           text_color="#FFFFFF")
        self.min_time_entry.pack(side="left", padx=(0, 5))
        self.min_time_entry.insert(0, self.settings["min_time"])
        self.max_time_entry = ctk.CTkEntry(duration_inner, width=80, placeholder_text="Max", fg_color="#2b2b2b",
                                           text_color="#FFFFFF")
        self.max_time_entry.pack(side="left")
        self.max_time_entry.insert(0, self.settings["max_time"])

        bot_control_frame = ctk.CTkFrame(attack_frame, fg_color="transparent")
        bot_control_frame.pack(fill="x", padx=15, pady=20)

        self.stats_label = ctk.CTkLabel(bot_control_frame, text="Progress: 0/0 | Success: 0 | Failed: 0",
                                        text_color="#FFFFFF")
        self.stats_label.pack(pady=5)
        self.progress_bar = ctk.CTkProgressBar(bot_control_frame, fg_color="#2b2b2b", progress_color="#3B8ED0")
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 10))
        self.progress_bar.set(0)

        btn_frame = ctk.CTkFrame(bot_control_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=10)
        self.start_button = ctk.CTkButton(btn_frame, text="START TRAFFIC", command=self.start_process,
                                          fg_color="#2CC985", hover_color="#229A66")
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.stop_button = ctk.CTkButton(btn_frame, text="STOP", state="disabled", command=self.stop_process,
                                         fg_color="#e74c3c", hover_color="#B83A2E")
        self.stop_button.pack(side="right", fill="x", expand=True, padx=(5, 0))

    def build_proxy_frame(self):
        proxy_frame = self.frames["proxy"]
        proxy_frame.grid_columnconfigure(0, weight=1)
        proxy_frame.grid_columnconfigure(1, weight=1)
        proxy_frame.grid_rowconfigure(1, weight=1)

        # Source
        source_frame = ctk.CTkFrame(proxy_frame, fg_color="transparent")
        source_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)

        ctk.CTkLabel(source_frame, text="Proxy Source", font=("Roboto Medium", 16), text_color="#FFFFFF").pack(
            pady=(15, 5))

        self.proxy_source_var = ctk.StringVar(value=self.settings["proxy_source"])
        self.source_seg_btn = ctk.CTkSegmentedButton(
            source_frame, values=["Manual", "File", "URL"], variable=self.proxy_source_var,
            command=self.update_proxy_ui_state
        )
        self.source_seg_btn.pack(pady=5, padx=15, fill="x")

        self.proxy_input_container = ctk.CTkFrame(source_frame, fg_color="transparent")
        self.proxy_input_container.pack(pady=5, padx=15, fill="both", expand=True)

        self.manual_textbox = ctk.CTkTextbox(self.proxy_input_container, fg_color="#2b2b2b", text_color="#FFFFFF")
        self.manual_textbox.insert("1.0", self.settings["manual_proxies"])

        self.file_input_frame = ctk.CTkFrame(self.proxy_input_container, fg_color="transparent")
        self.file_path_entry = ctk.CTkEntry(self.file_input_frame, placeholder_text="No file selected")
        self.file_path_entry.insert(0, self.settings["proxy_file_path"])
        self.file_path_entry.pack(side="left", fill="x", expand=True)
        self.browse_btn = ctk.CTkButton(self.file_input_frame, text="Browse", width=60, command=self.browse_file)
        self.browse_btn.pack(side="right", padx=(5, 0))

        self.url_input_frame = ctk.CTkFrame(self.proxy_input_container, fg_color="transparent")
        self.proxy_url_entry = ctk.CTkEntry(self.url_input_frame, placeholder_text="http://example.com/proxies.txt")
        self.proxy_url_entry.insert(0, self.settings["proxy_url"])
        self.proxy_url_entry.pack(fill="x")

        self.update_proxy_ui_state(self.settings["proxy_source"])

        # Tester
        tester_frame = ctk.CTkFrame(proxy_frame, fg_color="transparent")
        tester_frame.grid(row=0, column=1, sticky="nsew", pady=10)
        tester_frame.grid_columnconfigure((0, 1), weight=1)

        self.test_url_entry = self.create_labeled_entry(tester_frame, "Test URL:", self.settings["test_url"])
        self.test_url_entry.master.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        self.test_timeout_entry = self.create_labeled_entry(tester_frame, "Timeout (s):", self.settings["test_timeout"])
        self.test_timeout_entry.master.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.test_threads_entry = self.create_labeled_entry(tester_frame, "Threads:", self.settings["test_threads"])
        self.test_threads_entry.master.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        self.auto_detect_var = ctk.BooleanVar(value=False)
        self.auto_detect_check = ctk.CTkCheckBox(tester_frame, text="Auto-Detect Type", variable=self.auto_detect_var)
        self.auto_detect_check.grid(row=2, column=0, padx=10, pady=10)

        self.test_gateway_entry = self.create_labeled_entry(tester_frame, "Gateway:", self.settings["test_gateway"])
        self.test_gateway_entry.master.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        # Test Status Label
        self.test_status_label = ctk.CTkLabel(tester_frame, text="Tested: 0 | Active: 0 | Dead: 0", font=("Roboto", 12))
        self.test_status_label.grid(row=3, column=0, columnspan=2, pady=5)

        # Protocol Stats Labels
        self.protocol_stats_label = ctk.CTkLabel(tester_frame, text="HTTP: 0 | HTTPS: 0 | SOCKS4: 0 | SOCKS5: 0",
                                                 font=("Roboto", 11), text_color="gray")
        self.protocol_stats_label.grid(row=4, column=0, columnspan=2, pady=(0, 10))

        # Tester Logs
        self.tester_results = ctk.CTkTextbox(tester_frame, height=100, fg_color="#2b2b2b", text_color="#FFFFFF")
        self.tester_results.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        self.tester_results.insert("1.0", "Tester Logs...\n")
        self.tester_results.configure(state="disabled")

        # Results Grid
        results_frame = ctk.CTkFrame(proxy_frame, fg_color="transparent")
        results_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        results_frame.grid_columnconfigure(0, weight=1)
        results_frame.grid_rowconfigure(1, weight=1)

        controls_frame = ctk.CTkFrame(results_frame, fg_color="transparent")
        controls_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.start_test_btn = ctk.CTkButton(controls_frame, text="TEST PROXIES", command=self.start_proxy_test,
                                            fg_color="#2CC985", hover_color="#229A66")
        self.start_test_btn.grid(row=0, column=0, padx=5, sticky="ew")
        self.stop_test_btn = ctk.CTkButton(controls_frame, text="STOP", state="disabled", command=self.stop_proxy_test,
                                           fg_color="#e74c3c", hover_color="#B83A2E")
        self.stop_test_btn.grid(row=0, column=1, padx=5, sticky="ew")
        self.export_active_btn = ctk.CTkButton(controls_frame, text="EXPORT ACTIVE", command=self.export_active_proxies)
        self.export_active_btn.grid(row=0, column=2, padx=5, sticky="ew")
        self.clear_results_btn = ctk.CTkButton(controls_frame, text="CLEAR", command=self.clear_proxy_results,
                                               fg_color="#555555")
        self.clear_results_btn.grid(row=0, column=3, padx=5, sticky="ew")

        self.proxy_results_grid = ctk.CTkScrollableFrame(results_frame, label_text="Proxy Test Results")
        self.proxy_results_grid.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.proxy_results_grid.grid_columnconfigure((0, 1, 2, 3, 4, 5, 6), weight=1)  # +1 col for Country

        # --- MODIFIED HEADERS (Added Country) ---
        headers = ["IP", "Port", "Protocol", "Country", "Status", "Ping (ms)", "Anonymity"]
        for i, header in enumerate(headers):
            ctk.CTkLabel(self.proxy_results_grid, text=header, font=("Roboto Medium", 12)).grid(row=0, column=i, padx=5,
                                                                                                pady=5)

    def build_settings_frame(self):
        settings_frame = self.frames["settings"]
        ctk.CTkLabel(settings_frame, text="Global Settings", font=("Roboto Medium", 16), text_color="#FFFFFF").pack(
            pady=(15, 10))

        self.headless_var = ctk.BooleanVar(value=self.settings["headless"])
        self.headless_checkbox = ctk.CTkCheckBox(settings_frame, text="Run in Headless Mode",
                                                 variable=self.headless_var)
        self.headless_checkbox.pack(anchor="w", padx=20, pady=10)

        ctk.CTkButton(settings_frame, text="Save All Settings", command=self.save_current_settings,
                      fg_color="#2CC985").pack(pady=20)

    # --- Helper Methods ---
    def create_labeled_entry(self, parent, label_text, default_value):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(container, text=label_text, text_color="#FFFFFF").pack(anchor="w")
        entry = ctk.CTkEntry(container, fg_color="#2b2b2b", text_color="#FFFFFF")
        entry.pack(fill="x")
        entry.insert(0, str(default_value))
        return entry

    def show_frame(self, frame_name):
        self.frames[frame_name].tkraise()

    def update_proxy_ui_state(self, choice):
        for widget in self.proxy_input_container.winfo_children():
            widget.pack_forget()
        if choice == "Manual":
            self.manual_textbox.pack(fill="both", expand=True)
        elif choice == "File":
            self.file_input_frame.pack(fill="x")
        elif choice == "URL":
            self.url_input_frame.pack(fill="x")

    def browse_file(self):
        self.focus_force()
        self.update_idletasks()
        try:
            filename = filedialog.askopenfilename(
                parent=self,
                title="Select Proxy List",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
            )
            if filename:
                self.file_path_entry.delete(0, "end")
                self.file_path_entry.insert(0, filename)
        except Exception as e:
            self.log_message(f"Browse Error: {e}", "error")

    def log_message(self, message, level="info", target="bot"):
        timestamp = time.strftime("%H:%M:%S")
        colors = {"info": "white", "success": "#2CC985", "error": "#e74c3c", "warning": "#f39c12"}
        color = colors.get(level, "white")
        formatted_message = f"[{timestamp}] {message}\n"
        target_widget = self.dashboard_log_console if target == "bot" else self.tester_results

        def _update_log():
            try:
                target_widget.configure(state="normal")
                tag_name = f"color_{level}_{time.time()}_{random.randint(0, 999)}"
                target_widget.tag_config(tag_name, foreground=color)
                target_widget.insert("end", formatted_message, tag_name)
                target_widget.see("end")
                target_widget.configure(state="disabled")
            except Exception:
                pass

        self.after(0, _update_log)

    def save_current_settings(self):
        settings = {
            "url": self.url_entry.get(),
            "threads": self.threads_entry.get(),
            "visits": self.visits_entry.get(),
            "headless": self.headless_var.get(),
            "min_time": self.min_time_entry.get(),
            "max_time": self.max_time_entry.get(),
            "proxy_source": self.proxy_source_var.get(),
            "proxy_file_path": self.file_path_entry.get(),
            "proxy_url": self.proxy_url_entry.get(),
            "proxy_protocol": self.protocol_var.get(),
            "manual_proxies": self.manual_textbox.get("1.0", "end-1c"),
            "test_url": self.test_url_entry.get(),
            "test_timeout": self.test_timeout_entry.get(),
            "test_threads": self.test_threads_entry.get(),
            "test_gateway": self.test_gateway_entry.get()
        }
        self.settings_manager.save(settings)
        self.log_message("Settings saved.", "success")

    def load_proxies_common(self):
        source = self.proxy_source_var.get()
        data = ""
        if source == "Manual":
            data = self.manual_textbox.get("1.0", "end")
        elif source == "File":
            data = self.file_path_entry.get()
        elif source == "URL":
            data = self.proxy_url_entry.get()
        return ProxyManager.load_proxies(source, data, self.protocol_var.get())

    # --- MAIN BOT LOGIC ---
    def bot_task(self, task_id, url, min_time, max_time, headless_mode):
        if not self.is_running: return
        self.active_threads += 1

        proxy_data = self.get_random_proxy()
        user_agent = self.ua.random
        proxy_config = None
        proxy_log_str = "Direct Connection"

        if proxy_data:
            try:
                target_proxy = proxy_data
                scheme = "http"
                if "://" in target_proxy:
                    scheme, target_proxy = target_proxy.split("://", 1)

                proxy_config = {}
                if "@" in target_proxy:
                    auth_part, host_part = target_proxy.split("@", 1)
                    if ":" in auth_part:
                        username, password = auth_part.split(":", 1)
                        proxy_config["username"] = username
                        proxy_config["password"] = password
                    target_proxy = host_part

                proxy_config["server"] = f"{scheme}://{target_proxy}"
                proxy_log_str = f"Proxy ({scheme}) {target_proxy}"
            except Exception:
                self.log_message(f"Task {task_id}: Invalid proxy structure.", "error")
                self.failure_count += 1
                self.active_threads -= 1
                self.after(0, self.update_stats)
                return

        try:
            self.log_message(f"Task {task_id}: {proxy_log_str} -> {url}")
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=headless_mode,
                    args=["--disable-blink-features=AutomationControlled"]
                )

                context = browser.new_context(
                    user_agent=user_agent,
                    proxy=proxy_config,
                    viewport={"width": random.randint(1024, 1920), "height": random.randint(768, 1080)}
                )

                page = context.new_page()
                page.set_default_timeout(60000)

                response = page.goto(url, wait_until="domcontentloaded")

                if response and response.status < 400:
                    self.log_message(f"Task {task_id}: Page loaded. Browsing...", "success")
                    view_time = random.uniform(min_time, max_time)
                    start_time = time.time()
                    while time.time() - start_time < view_time:
                        if not self.is_running: break
                        time.sleep(1)
                    self.success_count += 1
                else:
                    self.log_message(f"Task {task_id}: Failed Status {response.status if response else 'ERR'}",
                                     "warning")
                    self.failure_count += 1

                context.close()
                browser.close()

        except Exception as e:
            self.log_message(f"Task {task_id}: Error - {str(e)[:50]}...", "error")
            self.failure_count += 1
        finally:
            self.active_threads -= 1
            self.after(0, self.update_stats)

    def get_random_proxy(self):
        if self.proxy_queue.empty(): return None
        proxy = self.proxy_queue.get()
        self.proxy_queue.put(proxy)
        return proxy

    def update_stats(self):
        completed = self.success_count + self.failure_count
        progress = completed / self.total_tasks if self.total_tasks > 0 else 0
        status_text = f"Progress: {completed}/{self.total_tasks} | Success: {self.success_count} | Failed: {self.failure_count}"
        self.progress_bar.set(progress)
        self.stats_label.configure(text=status_text)
        try:
            self.dash_progress_bar.set(progress)
            self.dash_status_label.configure(text=status_text)
        except AttributeError:
            pass

        if completed >= self.total_tasks and self.total_tasks > 0 and self.is_running:
            self.stop_process()

    def start_process(self):
        self.is_running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.dashboard_log_console.configure(state="normal")
        self.dashboard_log_console.delete("1.0", "end")
        self.dashboard_log_console.configure(state="disabled")
        self.active_threads = 0
        self.attack_start_time = time.time()
        self.monitor_dashboard()
        threading.Thread(target=self.manager_thread_target, daemon=True).start()

    def monitor_dashboard(self):
        if not self.is_running:
            return
        self.live_threads_label.configure(text=str(self.active_threads))
        elapsed = time.time() - self.attack_start_time
        total_reqs = self.success_count + self.failure_count
        if elapsed > 0:
            rps = total_reqs / elapsed
            self.rps_label.configure(text=f"{rps:.2f}")

        # --- NEW: Success Rate Logic ---
        if total_reqs > 0:
            success_rate = (self.success_count / total_reqs) * 100
            self.success_rate_label.configure(text=f"{success_rate:.1f}%")
        # -------------------------------

        self.after(500, self.monitor_dashboard)

    def stop_process(self):
        self.is_running = False
        self.after(100, lambda: self.start_button.configure(state="normal"))
        self.after(100, lambda: self.stop_button.configure(state="disabled"))

    def manager_thread_target(self):
        self.after(0, self.save_current_settings)
        url = self.url_entry.get()
        try:
            threads = int(self.threads_entry.get())
            total_visits = int(self.visits_entry.get())
            min_time = float(self.min_time_entry.get())
            max_time = float(self.max_time_entry.get())
            headless_mode = self.headless_var.get()
        except ValueError:
            self.log_message("Invalid numerical inputs.", "error")
            self.stop_process()
            return

        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            self.log_message("Invalid URL.", "error")
            self.stop_process()
            return

        self.total_tasks = total_visits
        self.success_count = 0
        self.failure_count = 0
        self.update_stats()
        self.proxy_queue = queue.Queue()
        try:
            self.log_message("Loading proxies...")
            proxies = self.load_proxies_common()
            for p in proxies: self.proxy_queue.put(p)
            self.total_proxies_label.configure(text=str(len(proxies)))
        except Exception as e:
            self.log_message(f"Proxy Load Error: {e}", "error")
            self.stop_process()
            return

        self.log_message(f"Starting {total_visits} visits with {threads} threads...")
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = []
            for i in range(total_visits):
                if not self.is_running: break
                futures.append(executor.submit(self.bot_task, i + 1, url, min_time, max_time, headless_mode))
                time.sleep(0.1)
            for f in futures:
                if not self.is_running:
                    f.cancel()
                else:
                    f.result()
        self.stop_process()

    def start_proxy_test(self):
        self.is_testing = True
        self.start_test_btn.configure(state="disabled")
        self.stop_test_btn.configure(state="normal")
        self.tester_results.configure(state="normal")
        self.tester_results.delete("1.0", "end")
        self.tester_results.configure(state="disabled")
        threading.Thread(target=self.manager_test_thread, daemon=True).start()

    def stop_proxy_test(self):
        self.is_testing = False
        self.after(100, lambda: self.start_test_btn.configure(state="normal"))
        self.after(100, lambda: self.stop_test_btn.configure(state="disabled"))

    def manager_test_thread(self):
        self.after(0, self.save_current_settings)
        original_socket = socket.socket
        try:
            target_url = self.test_url_entry.get()
            timeout = int(self.test_timeout_entry.get())
            threads = int(self.test_threads_entry.get())
            auto_detect = self.auto_detect_var.get()
            gateway = self.test_gateway_entry.get().strip()
        except ValueError:
            self.log_message("Invalid Tester Settings", "error", "tester")
            self.stop_proxy_test()
            return

        if gateway:
            try:
                if "://" not in gateway: gateway = "socks5://" + gateway
                gw_parsed = urlparse(gateway)
                proxy_type = socks.SOCKS5
                if "socks4" in gw_parsed.scheme:
                    proxy_type = socks.SOCKS4
                elif "http" in gw_parsed.scheme:
                    proxy_type = socks.HTTP
                socks.set_default_proxy(proxy_type, gw_parsed.hostname, gw_parsed.port, True, gw_parsed.username,
                                        gw_parsed.password)
                socks.monkeypatch()
                self.log_message(f"Gateway enabled: {gw_parsed.hostname}", "info", "tester")
            except Exception as e:
                self.log_message(f"Gateway Error: {e}", "error", "tester")
                self.stop_proxy_test()
                return

        try:
            proxies = self.load_proxies_common()
        except Exception as e:
            self.log_message(f"Load Error: {e}", "error", "tester")
            self.stop_proxy_test()
            return

        self.log_message(f"Testing {len(proxies)} proxies...", "info", "tester")
        self.test_stats = {"tested": 0, "active": 0, "dead": 0}
        self.protocol_stats = {"http": 0, "https": 0, "socks4": 0, "socks5": 0}
        self.tested_proxies = []
        self.update_tester_stats()
        self.clear_proxy_results()

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = []
            for p in proxies:
                if not self.is_testing: break
                futures.append(executor.submit(self.test_proxy_task, p, target_url, timeout, auto_detect))
            for f in futures:
                if not self.is_testing:
                    f.cancel()
                else:
                    f.result()

        if gateway:
            socks.set_default_proxy()
            socket.socket = original_socket

        self.log_message("Testing Finished.", "info", "tester")
        self.stop_proxy_test()

    def test_proxy_task(self, proxy, target_url, timeout, auto_detect):
        if not self.is_testing: return
        res = ProxyChecker.detect_and_check(proxy, target_url, timeout,
                                            self.real_ip) if auto_detect else ProxyChecker.check_proxy(
            proxy, target_url, timeout, self.real_ip)

        self.after(0, lambda: self.add_proxy_result_to_grid(res))

        if res["status"] == "Active":
            self.tested_proxies.append(res)
            self.test_stats["active"] += 1
            ptype = res.get("type", "HTTP").lower()
            if "socks5" in ptype:
                self.protocol_stats["socks5"] += 1
            elif "socks4" in ptype:
                self.protocol_stats["socks4"] += 1
            elif "https" in ptype:
                self.protocol_stats["https"] += 1
            else:
                self.protocol_stats["http"] += 1
        else:
            self.test_stats["dead"] += 1

        self.test_stats["tested"] += 1
        self.after(0, self.update_tester_stats)

    def add_proxy_result_to_grid(self, result):
        row_index = len(self.proxy_results_grid.winfo_children()) // 7 + 1
        try:
            ip_port = result["proxy"].split("://")[-1].split("@")[-1]
            ip, port = ip_port.split(":")
        except:
            ip, port = result["proxy"], "-"

        status_color = "#2CC985" if result["status"] == "Active" else "#e74c3c"
        country_code = result.get("country_code", "")
        flag = ProxyChecker.get_flag_emoji(country_code)

        # --- UPDATED COLUMN LIST (7 Columns) ---
        vals = [
            ip,
            port,
            result.get("type", "Unknown"),
            flag,  # Country Flag
            result["status"],
            str(result["speed"]) if result["status"] == "Active" else "-",
            result["anonymity"]
        ]

        for i, val in enumerate(vals):
            lbl = ctk.CTkLabel(self.proxy_results_grid, text=val)
            if i == 4:  # Status column
                lbl.configure(text_color=status_color)

            # Add Tooltip for Country Flag
            if i == 3:  # Country Column
                full_country_name = result.get("country", "Unknown")
                CTkToolTip(lbl, text=full_country_name)

            lbl.grid(row=row_index, column=i, padx=5, pady=2)

    def clear_proxy_results(self):
        for widget in self.proxy_results_grid.winfo_children():
            if widget.grid_info()["row"] > 0: widget.destroy()

    def update_tester_stats(self):
        self.test_status_label.configure(
            text=f"Tested: {self.test_stats['tested']} | Active: {self.test_stats['active']} | Dead: {self.test_stats['dead']}")
        p_stats = self.protocol_stats
        self.protocol_stats_label.configure(
            text=f"HTTP: {p_stats['http']} | HTTPS: {p_stats['https']} | SOCKS4: {p_stats['socks4']} | SOCKS5: {p_stats['socks5']}")

    def export_active_proxies(self):
        if not self.tested_proxies: return
        export_dir = "proxies"
        os.makedirs(export_dir, exist_ok=True)

        # Unified export for SOCKS
        grouped = {
            "http": [],
            "https": [],
            "socks": []
        }

        for p in self.tested_proxies:
            ptype = p.get("type", "HTTP").lower()
            if "socks" in ptype:  # Captures socks4, socks5, socks5h etc
                grouped["socks"].append(p["proxy"])
            elif "https" in ptype:
                grouped["https"].append(p["proxy"])
            else:
                grouped["http"].append(p["proxy"])

        for name, proxies in grouped.items():
            if proxies:
                with open(os.path.join(export_dir, f"{name}.txt"), "w") as f:
                    f.write("\n".join(proxies))

        self.log_message(f"Exported separate lists to /{export_dir}", "success", "tester")


if __name__ == "__main__":
    app = TrafficBotProApp()
    app.mainloop()