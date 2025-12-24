"""Proxy Manager page - Proxy scraping, testing, and management."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from ..components import VirtualGrid
from ..scaling import scaled
from ..styles import COLORS

if TYPE_CHECKING:
    from ..app import ModernTrafficBot


class ProxyManagerPage:
    """Proxy Manager page for proxy operations.

    Handles:
    - Proxy scraping from sources
    - Proxy testing/validation
    - Import/export operations
    - Protocol filtering
    - System proxy configuration
    """

    def __init__(self, app: "ModernTrafficBot"):
        """Initialize the proxy manager page.

        Args:
            app: The main application instance for shared state access.
        """
        self.app = app

        # UI widget references
        self.proxy_grid: VirtualGrid = None
        self.progress_bar: ctk.CTkProgressBar = None
        self.lbl_loaded: ctk.CTkLabel = None
        self.lbl_proto_counts: ctk.CTkLabel = None
        self.lbl_bandwidth: ctk.CTkLabel = None
        self.lbl_anon_counts: ctk.CTkLabel = None
        self.entry_test_url: ctk.CTkEntry = None
        self.entry_timeout: ctk.CTkEntry = None
        self.entry_check_threads: ctk.CTkEntry = None
        self.entry_scrape_threads: ctk.CTkEntry = None
        self.entry_system_proxy: ctk.CTkEntry = None
        self.combo_system_proxy_proto: ctk.CTkComboBox = None
        self.chk_http: ctk.CTkCheckBox = None
        self.chk_socks4: ctk.CTkCheckBox = None
        self.chk_socks5: ctk.CTkCheckBox = None
        self.chk_hide_dead: ctk.CTkCheckBox = None
        self.chk_manual_target: ctk.CTkCheckBox = None
        self.chk_proxy_for_scrape: ctk.CTkCheckBox = None
        self.chk_proxy_for_check: ctk.CTkCheckBox = None
        self.chk_export_protocol: ctk.CTkCheckBox = None
        self.btn_test: ctk.CTkButton = None
        self.btn_pause: ctk.CTkButton = None
        self.btn_test_proxy: ctk.CTkButton = None

    @property
    def settings(self) -> dict[str, Any]:
        """Access app settings."""
        return self.app.settings

    def setup(self, parent: ctk.CTkFrame) -> None:
        """Set up the proxy manager UI.

        Args:
            parent: The parent frame to build the UI in.
        """
        # Scrollable toolbar container for small screens
        tools_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        tools_scroll.pack(fill="x", pady=(0, 5))
        tools_scroll.configure(height=scaled(200))

        tools = ctk.CTkFrame(tools_scroll, fg_color=COLORS["card"])
        tools.pack(fill="x", pady=(0, 5))

        # Build UI sections
        self._setup_action_buttons(tools)
        self._setup_protocol_filters(tools)
        self._setup_stats_row(tools)
        self._setup_anonymity_row(tools)
        self._setup_test_config(tools)
        self._setup_system_proxy(tools)

        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            parent, height=scaled(10), progress_color=COLORS["accent"]
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 5))

        # Proxy grid
        self.proxy_grid = VirtualGrid(
            parent, columns=["Address", "Proto", "Country", "Status", "Ping", "Anon"]
        )
        self.proxy_grid.pack(fill="both", expand=True)

    def _setup_action_buttons(self, parent: ctk.CTkFrame) -> None:
        """Set up the action buttons row."""
        r1 = ctk.CTkFrame(parent, fg_color="transparent")
        r1.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            r1,
            text="Scrape New",
            width=scaled(100),
            command=self.app.run_scraper,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            r1,
            text="Load File",
            width=scaled(100),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.app.load_proxy_file,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            r1,
            text="Clipboard",
            width=scaled(80),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.app.import_from_clipboard,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            r1,
            text="Clear All",
            width=scaled(80),
            fg_color=COLORS["danger"],
            command=self.app.clear_proxies,
        ).pack(side="right", padx=5)

        ctk.CTkButton(
            r1,
            text="Clear Dead",
            width=scaled(80),
            fg_color=COLORS["warning"],
            command=self.app.clear_dead_proxies,
        ).pack(side="right", padx=5)

        # Export buttons frame
        self._setup_export_buttons(r1)

    def _setup_export_buttons(self, parent: ctk.CTkFrame) -> None:
        """Set up the export buttons."""
        export_frame = ctk.CTkFrame(parent, fg_color="transparent")
        export_frame.pack(side="right", padx=5)

        ctk.CTkLabel(export_frame, text="Export:", font=("Roboto", scaled(11))).pack(
            side="left", padx=(0, 3)
        )

        self.chk_export_protocol = ctk.CTkCheckBox(
            export_frame,
            text="Proto",
            width=scaled(50),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        if self.settings.get("export_with_protocol", True):
            self.chk_export_protocol.select()
        self.chk_export_protocol.pack(side="left", padx=(0, 3))

        ctk.CTkButton(
            export_frame,
            text="All",
            width=scaled(35),
            fg_color="#F39C12",
            hover_color="#D68910",
            command=lambda: self.app.export_proxies("all"),
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            export_frame,
            text="HTTP",
            width=scaled(40),
            fg_color="#3498DB",
            hover_color="#2980B9",
            command=lambda: self.app.export_proxies("http"),
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            export_frame,
            text="HTTPS",
            width=scaled(45),
            fg_color="#9B59B6",
            hover_color="#8E44AD",
            command=lambda: self.app.export_proxies("https"),
        ).pack(side="left", padx=1)

        ctk.CTkButton(
            export_frame,
            text="SOCKS",
            width=scaled(45),
            fg_color="#1ABC9C",
            hover_color="#16A085",
            command=lambda: self.app.export_proxies("socks"),
        ).pack(side="left", padx=1)

    def _setup_protocol_filters(self, parent: ctk.CTkFrame) -> None:
        """Set up the protocol filter checkboxes."""
        proto_frm = ctk.CTkFrame(parent, fg_color="transparent")
        proto_frm.pack(fill="x", padx=10, pady=5)

        self.chk_http = ctk.CTkCheckBox(
            proto_frm,
            text="HTTP/S",
            width=scaled(70),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        if self.settings.get("use_http", True):
            self.chk_http.select()
        self.chk_http.pack(side="left", padx=10)

        self.chk_socks4 = ctk.CTkCheckBox(
            proto_frm,
            text="SOCKS4",
            width=scaled(70),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        if self.settings.get("use_socks4", True):
            self.chk_socks4.select()
        self.chk_socks4.pack(side="left", padx=10)

        self.chk_socks5 = ctk.CTkCheckBox(
            proto_frm,
            text="SOCKS5",
            width=scaled(70),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        if self.settings.get("use_socks5", True):
            self.chk_socks5.select()
        self.chk_socks5.pack(side="left", padx=10)

        self.chk_hide_dead = ctk.CTkCheckBox(
            proto_frm, text="Hide Dead", width=scaled(70), fg_color=COLORS["danger"]
        )
        if self.settings.get("hide_dead", True):
            self.chk_hide_dead.select()
        self.chk_hide_dead.pack(side="right", padx=10)

    def _setup_stats_row(self, parent: ctk.CTkFrame) -> None:
        """Set up the stats display row."""
        r_counts = ctk.CTkFrame(parent, fg_color="transparent")
        r_counts.pack(fill="x", padx=10, pady=5)

        self.lbl_loaded = ctk.CTkLabel(
            r_counts, text="Total: 0", font=("Roboto", scaled(12), "bold")
        )
        self.lbl_loaded.pack(side="left", padx=5)

        self.lbl_proto_counts = ctk.CTkLabel(
            r_counts,
            text="HTTP: 0 | HTTPS: 0 | SOCKS4: 0 | SOCKS5: 0",
            text_color=COLORS["text_dim"],
            font=("Roboto", scaled(11)),
        )
        self.lbl_proto_counts.pack(side="right", padx=15)

        self.lbl_bandwidth = ctk.CTkLabel(
            r_counts,
            text="Traffic: 0.00 Mbps (0.0 MB)",
            text_color=COLORS["success"],
            font=("Roboto", scaled(11), "bold"),
        )
        self.lbl_bandwidth.pack(side="right", padx=5)

    def _setup_anonymity_row(self, parent: ctk.CTkFrame) -> None:
        """Set up the anonymity counts row."""
        r_anon = ctk.CTkFrame(parent, fg_color="transparent")
        r_anon.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(
            r_anon,
            text="Anonymity:",
            font=("Roboto", scaled(11)),
            text_color=COLORS["text_dim"],
        ).pack(side="left", padx=5)

        self.lbl_anon_counts = ctk.CTkLabel(
            r_anon,
            text="Elite: 0 | Anonymous: 0 | Transparent: 0 | Unknown: 0",
            text_color=COLORS["text_dim"],
            font=("Roboto", scaled(11)),
        )
        self.lbl_anon_counts.pack(side="left", padx=10)

    def _setup_test_config(self, parent: ctk.CTkFrame) -> None:
        """Set up the test configuration row."""
        r2 = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        r2.pack(fill="x", padx=10, pady=(0, 10))

        # Left side - Test URL
        r2_left = ctk.CTkFrame(r2, fg_color="transparent")
        r2_left.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        self.chk_manual_target = ctk.CTkCheckBox(
            r2_left,
            text="Manual:",
            width=scaled(70),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.app.toggle_manual_target,
        )
        if self.settings.get("use_manual_target", True):
            self.chk_manual_target.select()
        self.chk_manual_target.pack(side="left", padx=(0, 2))

        self.entry_test_url = ctk.CTkEntry(
            r2_left, placeholder_text="Test URL (or use validators)"
        )
        self.entry_test_url.insert(0, self.settings.get("proxy_test_url", ""))
        self.entry_test_url.pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkLabel(r2_left, text="Timeout:").pack(side="left", padx=2)
        self.entry_timeout = ctk.CTkEntry(r2_left, width=scaled(50))
        self.entry_timeout.insert(0, str(self.settings.get("proxy_timeout", 3000)))
        self.entry_timeout.pack(side="left", padx=2)

        ctk.CTkLabel(r2_left, text="Threads:").pack(side="left", padx=(5, 2))
        self.entry_check_threads = ctk.CTkEntry(r2_left, width=scaled(40))
        self.entry_check_threads.insert(
            0, str(self.settings.get("proxy_check_threads", 50))
        )
        self.entry_check_threads.pack(side="left", padx=2)

        ctk.CTkLabel(r2_left, text="Scrape:").pack(side="left", padx=(5, 2))
        self.entry_scrape_threads = ctk.CTkEntry(r2_left, width=scaled(40))
        self.entry_scrape_threads.insert(
            0, str(self.settings.get("proxy_scrape_threads", 20))
        )
        self.entry_scrape_threads.pack(side="left", padx=2)

        # Right side - Buttons
        r2_right = ctk.CTkFrame(r2, fg_color="transparent")
        r2_right.pack(side="right", padx=5, pady=5)

        self.btn_pause = ctk.CTkButton(
            r2_right,
            text="\u23f8 PAUSE",
            width=scaled(80),
            fg_color=COLORS["warning"],
            command=self.app.toggle_pause_test,
            state="disabled",
        )
        self.btn_pause.pack(side="left", padx=2)

        self.btn_test = ctk.CTkButton(
            r2_right,
            text="TEST ALL",
            width=scaled(80),
            fg_color=COLORS["success"],
            command=self.app.toggle_test,
        )
        self.btn_test.pack(side="left", padx=2)

    def _setup_system_proxy(self, parent: ctk.CTkFrame) -> None:
        """Set up the system proxy configuration row."""
        r3 = ctk.CTkFrame(parent, fg_color=COLORS["bg"])
        r3.pack(fill="x", padx=10, pady=(0, 5))

        ctk.CTkLabel(r3, text="System Proxy:").pack(side="left", padx=5)

        self.combo_system_proxy_proto = ctk.CTkComboBox(
            r3, values=["http", "socks4", "socks5"], width=scaled(80)
        )
        self.combo_system_proxy_proto.set(
            self.settings.get("system_proxy_protocol", "http")
        )
        self.combo_system_proxy_proto.pack(side="left", padx=2)

        # Right side buttons (packed first to avoid clipping)
        self.btn_test_proxy = ctk.CTkButton(
            r3,
            text="TEST",
            width=scaled(50),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            command=self.app.test_system_proxy,
        )
        self.btn_test_proxy.pack(side="right", padx=5)

        self.chk_proxy_for_check = ctk.CTkCheckBox(
            r3,
            text="Check",
            width=scaled(60),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        if self.settings.get("use_proxy_for_check", False):
            self.chk_proxy_for_check.select()
        self.chk_proxy_for_check.pack(side="right", padx=2)

        self.chk_proxy_for_scrape = ctk.CTkCheckBox(
            r3,
            text="Scrape",
            width=scaled(65),
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        if self.settings.get("use_proxy_for_scrape", False):
            self.chk_proxy_for_scrape.select()
        self.chk_proxy_for_scrape.pack(side="right", padx=2)

        # Middle - Proxy entry
        self.entry_system_proxy = ctk.CTkEntry(r3, placeholder_text="user:pass@ip:port")
        self.entry_system_proxy.insert(0, self.settings.get("system_proxy", ""))
        self.entry_system_proxy.pack(side="left", fill="x", expand=True, padx=5)
