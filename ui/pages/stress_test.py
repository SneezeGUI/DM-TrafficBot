"""Stress Test page - Authorized security testing interface."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from ..components import DraggableSash
from ..scaling import scaled
from ..styles import COLORS

if TYPE_CHECKING:
    from ..app import ModernTrafficBot


class StressTestPage:
    """Stress Test page for authorized load testing.

    Handles:
    - Attack type selection (HTTP Flood, Slowloris, RUDY, Randomized)
    - Thread/duration/RPS configuration
    - Real-time stats monitoring
    - Test control (start/stop/pause)
    """

    def __init__(self, app: "ModernTrafficBot"):
        """Initialize the stress test page.

        Args:
            app: The main application instance for shared state access.
        """
        self.app = app

        # UI widget references
        self.stress_stat_labels: dict[str, ctk.CTkLabel] = {}
        self.stress_entry_url: ctk.CTkEntry = None
        self.stress_attack_type: ctk.CTkComboBox = None
        self.stress_method: ctk.CTkComboBox = None
        self.stress_proxy_count_label: ctk.CTkLabel = None
        self.stress_slider_threads: ctk.CTkSlider = None
        self.stress_slider_duration: ctk.CTkSlider = None
        self.stress_slider_rps: ctk.CTkSlider = None
        self.stress_lbl_threads: ctk.CTkLabel = None
        self.stress_lbl_duration: ctk.CTkLabel = None
        self.stress_lbl_rps: ctk.CTkLabel = None
        self.btn_stress_start: ctk.CTkButton = None
        self.btn_stress_pause: ctk.CTkButton = None
        self.btn_stress_reset: ctk.CTkButton = None
        self.stress_log_box: ctk.CTkTextbox = None

        # Internal state
        self._stress_config_height = scaled(300)
        self._stress_config_min = scaled(150)
        self._stress_log_min = scaled(80)

    @property
    def settings(self) -> dict[str, Any]:
        """Access app settings."""
        return self.app.settings

    def setup(self, parent: ctk.CTkFrame) -> None:
        """Set up the stress test UI.

        Args:
            parent: The parent frame to build the UI in.
        """
        parent.grid_rowconfigure(0, weight=0)  # Scrollable config
        parent.grid_rowconfigure(1, weight=0)  # Draggable sash
        parent.grid_rowconfigure(2, weight=1)  # Log expands
        parent.grid_columnconfigure(0, weight=1)

        # Scrollable container for config
        config_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        config_scroll.grid(row=0, column=0, sticky="nsew", pady=(0, 0))
        config_scroll.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=0, minsize=self._stress_config_height)

        # Draggable sash
        def on_sash_drag(delta):
            new_height = self._stress_config_height + delta
            parent_height = parent.winfo_height()
            max_config = parent_height - self._stress_log_min - scaled(10)
            new_height = max(self._stress_config_min, min(new_height, max_config))
            if new_height != self._stress_config_height:
                self._stress_config_height = new_height
                parent.grid_rowconfigure(
                    0, weight=0, minsize=int(self._stress_config_height)
                )

        sash = DraggableSash(
            parent,
            on_drag=on_sash_drag,
            min_above=self._stress_config_min,
            min_below=self._stress_log_min,
        )
        sash.grid(row=1, column=0, sticky="ew", pady=(0, 0))

        # Build UI sections
        self._setup_warning_banner(config_scroll)
        self._setup_stats_row(config_scroll)
        self._setup_config_card(config_scroll)
        self._setup_activity_log(parent)

    def _setup_warning_banner(self, parent: ctk.CTkFrame) -> None:
        """Set up the warning banner."""
        warning_frame = ctk.CTkFrame(parent, fg_color="#8B0000")
        warning_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            warning_frame,
            text="\u26a0\ufe0f  FOR AUTHORIZED SECURITY TESTING ONLY - TEST YOUR OWN SERVERS  \u26a0\ufe0f",
            font=("Roboto", 12, "bold"),
            text_color="white",
        ).pack(pady=8)

    def _setup_stats_row(self, parent: ctk.CTkFrame) -> None:
        """Set up the stats display row."""
        stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 8))
        stats_frame.grid_columnconfigure(
            (0, 1, 2, 3, 4, 5), weight=1, uniform="stress_stats"
        )

        stat_configs = [
            ("requests", "Requests", COLORS["text"]),
            ("success", "Success", COLORS["success"]),
            ("failed", "Failed", COLORS["danger"]),
            ("rps", "RPS", COLORS["accent"]),
            ("latency", "Latency", COLORS["warning"]),
            ("proxies", "Proxies", COLORS["text"]),
        ]
        for col, (key, title, color) in enumerate(stat_configs):
            card = ctk.CTkFrame(stats_frame, fg_color=COLORS["card"])
            card.grid(row=0, column=col, sticky="nsew", padx=2, pady=2)
            ctk.CTkLabel(
                card, text=title, font=("Roboto", 9), text_color=COLORS["text_dim"]
            ).pack(pady=(6, 1))
            lbl = ctk.CTkLabel(
                card, text="0", font=("Roboto", 16, "bold"), text_color=color
            )
            lbl.pack(pady=(0, 6))
            self.stress_stat_labels[key] = lbl

    def _setup_config_card(self, parent: ctk.CTkFrame) -> None:
        """Set up the configuration card."""
        cfg_frame = ctk.CTkFrame(parent, fg_color=COLORS["card"])
        cfg_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            cfg_frame, text="Stress Test Configuration", font=("Roboto", 14, "bold")
        ).pack(anchor="w", padx=20, pady=15)

        # Target URL
        self._setup_target_row(cfg_frame)

        # Attack type & method
        self._setup_type_row(cfg_frame)

        # Sliders
        self._setup_sliders(cfg_frame)

        # Buttons
        self._setup_buttons(cfg_frame)

    def _setup_target_row(self, parent: ctk.CTkFrame) -> None:
        """Set up the target URL row."""
        target_row = ctk.CTkFrame(parent, fg_color="transparent")
        target_row.pack(fill="x", padx=20, pady=(0, 10))

        self.stress_entry_url = ctk.CTkEntry(
            target_row,
            placeholder_text="http://your-server.com/test",
            height=scaled(32),
        )
        self.stress_entry_url.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkLabel(
            target_row,
            text="HTTP Only",
            font=("Roboto", 10),
            text_color=COLORS["warning"],
        ).pack(side="right")

    def _setup_type_row(self, parent: ctk.CTkFrame) -> None:
        """Set up the attack type and method row."""
        type_row = ctk.CTkFrame(parent, fg_color="transparent")
        type_row.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(type_row, text="Attack:", font=("Roboto", scaled(12))).pack(
            side="left", padx=(0, 5)
        )
        self.stress_attack_type = ctk.CTkComboBox(
            type_row,
            values=["HTTP Flood", "Slowloris", "RUDY", "Randomized"],
            width=scaled(130),
            state="readonly",
        )
        self.stress_attack_type.set("HTTP Flood")
        self.stress_attack_type.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(type_row, text="Method:", font=("Roboto", scaled(12))).pack(
            side="left", padx=(0, 5)
        )
        self.stress_method = ctk.CTkComboBox(
            type_row,
            values=["GET", "POST", "HEAD", "PUT", "DELETE"],
            width=scaled(80),
            state="readonly",
        )
        self.stress_method.set("GET")
        self.stress_method.pack(side="left", padx=(0, 20))

        self.stress_proxy_count_label = ctk.CTkLabel(
            type_row,
            text="HTTP Proxies: 0",
            font=("Roboto", 11),
            text_color=COLORS["accent"],
        )
        self.stress_proxy_count_label.pack(side="right")

    def _setup_sliders(self, parent: ctk.CTkFrame) -> None:
        """Set up the configuration sliders."""
        slider_row = ctk.CTkFrame(parent, fg_color="transparent")
        slider_row.pack(fill="x", padx=15, pady=10)
        slider_row.grid_columnconfigure((0, 1, 2), weight=1)

        # Threads slider
        t_frame = ctk.CTkFrame(slider_row, fg_color="transparent")
        t_frame.grid(row=0, column=0, sticky="nsew", padx=5)
        self.stress_lbl_threads = ctk.CTkLabel(t_frame, text="Threads: 100")
        self.stress_lbl_threads.pack(anchor="w")
        self.stress_slider_threads = ctk.CTkSlider(
            t_frame,
            from_=10,
            to=1000,
            number_of_steps=99,
            command=lambda v: self.stress_lbl_threads.configure(
                text=f"Threads: {int(v)}"
            ),
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
        )
        self.stress_slider_threads.set(100)
        self.stress_slider_threads.pack(fill="x", pady=5)

        # Duration slider
        d_frame = ctk.CTkFrame(slider_row, fg_color="transparent")
        d_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        self.stress_lbl_duration = ctk.CTkLabel(d_frame, text="Duration: 60s")
        self.stress_lbl_duration.pack(anchor="w")
        self.stress_slider_duration = ctk.CTkSlider(
            d_frame,
            from_=10,
            to=300,
            number_of_steps=29,
            command=lambda v: self.stress_lbl_duration.configure(
                text=f"Duration: {int(v)}s"
            ),
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
        )
        self.stress_slider_duration.set(60)
        self.stress_slider_duration.pack(fill="x", pady=5)

        # RPS Limit slider
        r_frame = ctk.CTkFrame(slider_row, fg_color="transparent")
        r_frame.grid(row=0, column=2, sticky="nsew", padx=5)
        self.stress_lbl_rps = ctk.CTkLabel(r_frame, text="RPS Limit: Unlimited")
        self.stress_lbl_rps.pack(anchor="w")
        self.stress_slider_rps = ctk.CTkSlider(
            r_frame,
            from_=0,
            to=10000,
            number_of_steps=100,
            command=self.update_rps_label,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
        )
        self.stress_slider_rps.set(0)
        self.stress_slider_rps.pack(fill="x", pady=5)

    def _setup_buttons(self, parent: ctk.CTkFrame) -> None:
        """Set up the control buttons."""
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=20)

        self.btn_stress_start = ctk.CTkButton(
            btn_row,
            text="\U0001f680 START STRESS TEST",
            height=scaled(40),
            fg_color=COLORS["success"],
            font=("Roboto", scaled(13), "bold"),
            command=self.app.toggle_stress_test,
        )
        self.btn_stress_start.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_stress_pause = ctk.CTkButton(
            btn_row,
            text="\u23f8 PAUSE",
            height=scaled(40),
            fg_color=COLORS["warning"],
            font=("Roboto", scaled(11), "bold"),
            width=scaled(90),
            command=self.app.toggle_stress_pause,
        )
        self.btn_stress_pause.pack(side="left", padx=(0, 10))

        self.btn_stress_reset = ctk.CTkButton(
            btn_row,
            text="RESET",
            height=scaled(40),
            fg_color=COLORS["card"],
            font=("Roboto", scaled(11), "bold"),
            width=scaled(70),
            command=self.app.reset_stress_stats,
        )
        self.btn_stress_reset.pack(side="right")

    def _setup_activity_log(self, parent: ctk.CTkFrame) -> None:
        """Set up the activity log panel."""
        log_frame = ctk.CTkFrame(parent, fg_color="transparent")
        log_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        log_frame.grid_rowconfigure(1, weight=1, minsize=self._stress_log_min)
        log_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_frame,
            text="Stress Test Log",
            font=("Roboto", scaled(11)),
            text_color=COLORS["text_dim"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.stress_log_box = ctk.CTkTextbox(log_frame, fg_color=COLORS["card"])
        self.stress_log_box.grid(row=1, column=0, sticky="nsew")

    # Event handlers

    def update_rps_label(self, value) -> None:
        """Update RPS limit label."""
        v = int(value)
        if v == 0:
            self.stress_lbl_rps.configure(text="RPS Limit: Unlimited")
        else:
            self.stress_lbl_rps.configure(text=f"RPS Limit: {v}")

    def log(self, message: str) -> None:
        """Log a message to the stress test log box."""
        import time

        timestamp = time.strftime("%H:%M:%S")
        self.stress_log_box.insert("end", f"[{timestamp}] {message}\n")
        self.stress_log_box.see("end")

    def update_proxy_count(self) -> None:
        """Update the HTTP proxy count label."""
        if hasattr(self.app, "proxy_grid"):
            all_active = self.app.proxy_grid.get_active_objects()
            http_count = sum(
                1 for p in all_active if p.get("type", "").upper() == "HTTP"
            )
            self.stress_proxy_count_label.configure(
                text=f"HTTP Proxies: {http_count:,}"
            )
