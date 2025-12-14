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
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import queue
from tkinter import filedialog
from playwright.sync_api import sync_playwright
from fake_useragent import UserAgent
import urllib3
import pycountry
import math

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
        try:
            if not self.widget.winfo_exists():
                return
        except Exception:
            return

        x = y = 0
        x, y, cx, cy = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20

        self.tw = ctk.CTkToplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))

        label = ctk.CTkLabel(self.tw, text=self.text, justify='left',
                             fg_color="#2b2b2b", text_color="white",
                             corner_radius=6, width=100)
        label.pack(ipadx=5, ipady=5)
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
            "test_url": "http://httpbin.org/json",
            "test_timeout": "10",
            "test_threads": "20",
            "test_gateway": "",
            "scraper_sources": "sources.txt"
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


class ProxyScraper:
    @staticmethod
    def scrape(sources_file="sources.txt"):
        proxies = set()
        logs = []

        if not os.path.exists(sources_file):
            with open(sources_file, "w") as f:
                f.write("https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt\n")
                f.write(
                    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all&ssl=all&anonymity=all\n")
            logs.append(f"Created default {sources_file}")

        try:
            with open(sources_file, "r") as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except Exception as e:
            return [], [f"Error reading sources: {e}"]

        if not urls:
            return [], ["No sources found in sources.txt"]

        proxy_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b")

        def fetch_url(url):
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    found = set()
                    try:
                        data = resp.json()

                        def get_val(item, keys):
                            for k in keys:
                                if k in item: return item[k]
                                if k.lower() in item: return item[k.lower()]
                                if k.capitalize() in item: return item[k.capitalize()]
                            return None

                        items = []
                        if isinstance(data, dict) and "data" in data:
                            items = data["data"]
                        elif isinstance(data, list):
                            items = data

                        for item in items:
                            if isinstance(item, dict):
                                ip = get_val(item, ["ip", "Ip", "IP"])
                                port = get_val(item, ["port", "Port", "PORT"])
                                if ip and port:
                                    found.add(f"{ip}:{port}")
                    except ValueError:
                        pass

                    found.update(proxy_pattern.findall(resp.text))
                    count = len(found)
                    return list(found), f"Fetched {count} from {url}"
                return [], f"Failed {url} (Status {resp.status_code})"
            except Exception as e:
                return [], f"Error {url}: {str(e)[:30]}"

        with ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(fetch_url, urls)

        for found_list, log_msg in results:
            proxies.update(found_list)
            logs.append(log_msg)

        return list(proxies), logs


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
    def get_country_data(country_code):
        if not country_code or len(country_code) != 2:
            return "Unknown", "🏳️"
        try:
            country = pycountry.countries.get(alpha_2=country_code.upper())
            name = country.name if country else "Unknown"
        except:
            name = "Unknown"
        flag = chr(ord(country_code[0].upper()) + 127397) + chr(ord(country_code[1].upper()) + 127397)
        return name, flag

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
        proxies = {"http": proxy, "https": proxy}
        try:
            start_time = time.time()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(target_url, proxies=proxies, timeout=timeout, verify=False, headers=headers)
            end_time = time.time()
            result["speed"] = int((end_time - start_time) * 1000)
            result["status"] = "Active"
            try:
                data = response.json()
                origin_ip = data.get("origin", "").split(',')[0]
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
                result["anonymity"] = "Active"
            try:
                geo_url = "http://ip-api.com/json"
                geo_resp = requests.get(geo_url, proxies=proxies, timeout=5)
                if geo_resp.status_code == 200:
                    geo_data = geo_resp.json()
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
        self.is_scraping = False
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

        # --- OPTIMIZATION: Results Buffer & Virtual Grid ---
        self.proxy_results_buffer = []
        self.grid_widgets_pool = []  # Stores reusable widget rows
        self.GRID_POOL_SIZE = 30  # Only draw this many rows ever
        # -----------------------------------

        try:
            self.real_ip = requests.get("https://api.ipify.org", timeout=5).text
        except:
            self.real_ip = "0.0.0.0"

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

        # Start UI Refresh Loop
        self.update_results_grid_loop()

    def build_dashboard_frame(self):
        dashboard = self.frames["dashboard"]
        dashboard.grid_columnconfigure(0, weight=1)
        dashboard.grid_rowconfigure(2, weight=1)

        hud_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        hud_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        hud_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        for i, (title, attr) in enumerate(
                [("Live Threads", "live_threads_label"), ("Total Proxies", "total_proxies_label"),
                 ("Requests/Sec", "rps_label")]):
            card = ctk.CTkFrame(hud_frame, fg_color="#2b2b2b")
            card.grid(row=0, column=i, padx=10, pady=5, sticky="ew")
            ctk.CTkLabel(card, text=title, font=("Roboto", 12), text_color="#999999").pack(pady=(10, 0))
            lbl = ctk.CTkLabel(card, text="0", font=("Roboto Medium", 24), text_color="#FFFFFF")
            lbl.pack(pady=(0, 10))
            setattr(self, attr, lbl)

        card = ctk.CTkFrame(hud_frame, fg_color="#2b2b2b")
        card.grid(row=0, column=3, padx=10, pady=5, sticky="ew")
        ctk.CTkLabel(card, text="Success Rate", font=("Roboto", 12), text_color="#999999").pack(pady=(10, 0))
        self.success_rate_label = ctk.CTkLabel(card, text="0%", font=("Roboto Medium", 24), text_color="#2CC985")
        self.success_rate_label.pack(pady=(0, 10))

        dash_prog_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        dash_prog_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 10))

        self.dash_status_label = ctk.CTkLabel(dash_prog_frame, text="Status: Idle", text_color="#FFFFFF", anchor="w")
        self.dash_status_label.pack(fill="x", pady=(0, 5))

        self.dash_progress_bar = ctk.CTkProgressBar(dash_prog_frame, fg_color="#2b2b2b", progress_color="#3B8ED0")
        self.dash_progress_bar.pack(fill="x")
        self.dash_progress_bar.set(0)

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

        protocol_frame = ctk.CTkFrame(attack_frame, fg_color="transparent")
        protocol_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(protocol_frame, text="Proxy Protocol:", text_color="#FFFFFF").pack(side="left", padx=(0, 10))
        self.protocol_var = ctk.StringVar(value=self.settings["proxy_protocol"])
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

        # --- SCRAPER SECTION ---
        scraper_frame = ctk.CTkFrame(source_frame, fg_color="transparent")
        scraper_frame.pack(fill="x", padx=15, pady=5)

        self.scrape_source_entry = ctk.CTkEntry(scraper_frame, placeholder_text="sources.txt")
        self.scrape_source_entry.insert(0, self.settings.get("scraper_sources", "sources.txt"))
        self.scrape_source_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.scrape_btn = ctk.CTkButton(scraper_frame, text="SCRAPE PROXIES", command=self.start_scraping,
                                        fg_color="#E67E22", hover_color="#D35400", width=120)
        self.scrape_btn.pack(side="right")
        # -----------------------

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

        # FLUID GRID: Configure columns with weights
        self.proxy_results_grid = ctk.CTkFrame(results_frame, fg_color="transparent")
        self.proxy_results_grid.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        # Configure grid columns (7 columns) to be responsive
        for i in range(7):
            self.proxy_results_grid.grid_columnconfigure(i, weight=1)

        # --- HEADERS ---
        headers = ["IP", "Port", "Protocol", "Country", "Status", "Ping (ms)", "Anonymity"]
        for i, header in enumerate(headers):
            ctk.CTkLabel(self.proxy_results_grid, text=header, font=("Roboto Medium", 12)).grid(row=0, column=i, padx=5,
                                                                                                pady=5, sticky="ew")
        # --- INITIALIZE WIDGET POOL ---
        # Create empty labels once and reuse them
        self.grid_widgets_pool = []
        for row in range(self.GRID_POOL_SIZE):
            row_widgets = []
            for col in range(7):
                lbl = ctk.CTkLabel(self.proxy_results_grid, text="", height=20)
                # We do NOT grid them yet or we grid them and hide them?
                # Better to grid them and leave text empty
                lbl.grid(row=row + 1, column=col, padx=2, pady=1, sticky="ew")
                row_widgets.append(lbl)
            self.grid_widgets_pool.append(row_widgets)

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
                if not target_widget.winfo_exists(): return
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
            "test_gateway": self.test_gateway_entry.get(),
            "scraper_sources": self.scrape_source_entry.get()
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

    # --- SCRAPING LOGIC ---
    def start_scraping(self):
        if self.is_scraping: return
        self.is_scraping = True
        self.scrape_btn.configure(state="disabled", text="SCRAPING...")
        threading.Thread(target=self.run_scraper, daemon=True).start()

    def run_scraper(self):
        source_file = self.scrape_source_entry.get()
        self.log_message(f"Starting scrape from {source_file}...", "info", "tester")

        proxies, logs = ProxyScraper.scrape(source_file)

        for log in logs:
            self.log_message(log, "info", "tester")

        if proxies:
            count = len(proxies)
            proxies_str = "\n".join(proxies)

            if count > 5000:
                save_path = "scraped_proxies.txt"
                try:
                    with open(save_path, "w") as f:
                        f.write(proxies_str)

                    def _update_ui_large():
                        self.file_path_entry.delete(0, "end")
                        self.file_path_entry.insert(0, os.path.abspath(save_path))
                        self.proxy_source_var.set("File")
                        self.source_seg_btn.set("File")
                        self.update_proxy_ui_state("File")
                        self.scrape_btn.configure(state="normal", text="SCRAPE PROXIES")
                        self.is_scraping = False
                        self.log_message(f"Success! {count} proxies saved to {save_path}", "success", "tester")
                        self.log_message("Switched mode to 'File' to prevent GUI lag.", "warning", "tester")

                    self.after(0, _update_ui_large)
                except Exception as e:
                    self.log_message(f"Error saving scrape file: {e}", "error", "tester")
                    self.is_scraping = False
            else:
                def _update_ui_small():
                    self.manual_textbox.delete("1.0", "end")
                    self.manual_textbox.insert("1.0", proxies_str)
                    self.proxy_source_var.set("Manual")
                    self.source_seg_btn.set("Manual")
                    self.update_proxy_ui_state("Manual")
                    self.scrape_btn.configure(state="normal", text="SCRAPE PROXIES")
                    self.is_scraping = False
                    self.log_message(f"Scraped {count} proxies. Added to Manual list.", "success", "tester")

                self.after(0, _update_ui_small)
        else:
            self.after(0, lambda: self.scrape_btn.configure(state="normal", text="SCRAPE PROXIES"))
            self.is_scraping = False
            self.log_message("No proxies found.", "warning", "tester")

    # --- MAIN BOT LOGIC (OPTIMIZED: PERSISTENT BROWSERS) ---
    def bot_worker_thread(self, thread_id, url, visits_per_thread, min_time, max_time, headless_mode):
        """
        Runs one persistent browser for multiple visits.
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=headless_mode,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                self.log_message(f"Thread {thread_id}: Browser launched.", "info")

                for i in range(visits_per_thread):
                    if not self.is_running: break

                    # Get Proxy
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
                            proxy_log_str = f"Proxy {target_proxy}"
                        except Exception:
                            pass  # Skip bad proxy setup

                    # Create Context
                    try:
                        context = browser.new_context(
                            user_agent=user_agent,
                            proxy=proxy_config,
                            viewport={"width": random.randint(1024, 1920), "height": random.randint(768, 1080)}
                        )
                        page = context.new_page()
                        page.set_default_timeout(60000)

                        self.log_message(f"T{thread_id}: Visiting {url} via {proxy_log_str}")
                        response = page.goto(url, wait_until="domcontentloaded")

                        if response and response.status < 400:
                            self.success_count += 1
                            view_time = random.uniform(min_time, max_time)
                            time.sleep(view_time)
                        else:
                            self.failure_count += 1

                        context.close()
                    except Exception as e:
                        self.log_message(f"T{thread_id} Error: {str(e)[:40]}", "error")
                        self.failure_count += 1

                    self.active_threads = threading.active_count() - 1  # Approx
                    self.after(0, self.update_stats)

                browser.close()
                self.log_message(f"Thread {thread_id}: Browser closed.", "info")

        except Exception as e:
            self.log_message(f"Thread {thread_id} Critical Error: {e}", "error")

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

        if total_reqs > 0:
            success_rate = (self.success_count / total_reqs) * 100
            self.success_rate_label.configure(text=f"{success_rate:.1f}%")

        self.after(500, self.monitor_dashboard)

    def stop_process(self):
        self.is_running = False
        self.after(100, lambda: self.start_button.configure(state="normal"))
        self.after(100, lambda: self.stop_button.configure(state="disabled"))

    def manager_thread_target(self):
        self.after(0, self.save_current_settings)
        url = self.url_entry.get()
        try:
            thread_count = int(self.threads_entry.get())
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

        self.log_message(f"Starting {total_visits} visits with {thread_count} persistent threads...")

        # Distribute work
        visits_per_thread = math.ceil(total_visits / thread_count)

        with ThreadPoolExecutor(max_workers=thread_count) as executor:
            futures = []
            for i in range(thread_count):
                if not self.is_running: break
                futures.append(executor.submit(
                    self.bot_worker_thread, i + 1, url, visits_per_thread, min_time, max_time, headless_mode
                ))
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
        # Clear buffer
        self.proxy_results_buffer = []
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

        # OPTIMIZATION: Don't update grid individually. Buffer it.
        self.proxy_results_buffer.append(res)

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

    # --- OPTIMIZATION: BATCH UI UPDATER (RECYCLING WIDGETS) ---
    def update_results_grid_loop(self):
        """
        Periodically checks the buffer and updates the UI in chunks.
        Prevents locking the main thread.
        """
        if self.proxy_results_buffer:
            # We only show the latest N items that fit in the pool
            # Take the *newest* items from the buffer if it's overflowing
            # Actually, to simulate a log, we insert at top or bottom?
            # Let's just process chunks.

            chunk = self.proxy_results_buffer[:5]  # Update 5 rows per tick
            del self.proxy_results_buffer[:5]

            for res in chunk:
                self.add_proxy_result_to_grid_optimized(res)

        # Run every 50ms - faster updates, smaller chunks
        self.after(50, self.update_results_grid_loop)

    def add_proxy_result_to_grid_optimized(self, result):
        # We don't create widgets. We shift data.
        # Implementation: We need a data structure for the view.
        # But for simplicity in this specific "Log" view, we can:
        # 1. Pop the last row of widgets (bottom)
        # 2. Move it to the top (row 1)
        # 3. Re-configure its text
        # 4. Shift all other rows down? No, that's slow (re-grid).

        # Better: Just write to the NEXT available slot in the circular buffer
        # But the user wants a scrolling list.

        # "Shift" Logic:
        # Move internal data, then redraw?
        # Actually, let's just stick to "Insert at Top" logic but REUSE the widgets.
        # Un-grid the last row. Grid it at row 1. Increment everyone else's row? No.

        # FASTEST: Just update the text of the existing widgets to match a "data list".
        # We need a list of recent results.
        if not hasattr(self, "view_data_list"):
            self.view_data_list = []

        self.view_data_list.insert(0, result)
        if len(self.view_data_list) > self.GRID_POOL_SIZE:
            self.view_data_list.pop()

        # Now update the widgets to match view_data_list
        for i, res in enumerate(self.view_data_list):
            row_widgets = self.grid_widgets_pool[i]

            ip_port = res["proxy"].split("://")[-1].split("@")[-1]
            try:
                ip, port = ip_port.split(":")
            except:
                ip, port = res["proxy"], "-"

            country_code = res.get("country_code", "")
            full_country_name, flag = ProxyChecker.get_country_data(country_code)

            status_color = "#2CC985" if res["status"] == "Active" else "#e74c3c"

            vals = [
                ip, port, res.get("type", "Unknown"), flag,
                res["status"], str(res["speed"]) if res["status"] == "Active" else "-",
                res["anonymity"]
            ]

            # Update the row widgets
            for col_idx, widget in enumerate(row_widgets):
                widget.configure(text=vals[col_idx])
                if col_idx == 4:  # Status
                    widget.configure(text_color=status_color)
                else:
                    widget.configure(text_color="#FFFFFF")  # Reset color

                if col_idx == 3:  # Country tooltip
                    CTkToolTip(widget, text=full_country_name)

    def clear_proxy_results(self):
        # Clear buffer and view list
        self.proxy_results_buffer = []
        self.view_data_list = []

        # Clear text on all widgets
        for row in self.grid_widgets_pool:
            for widget in row:
                widget.configure(text="")

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

        grouped = {
            "http": [],
            "https": [],
            "socks": []
        }

        for p in self.tested_proxies:
            ptype = p.get("type", "HTTP").lower()
            if "socks" in ptype:
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