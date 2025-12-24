"""Dashboard page - Traffic campaign configuration and monitoring."""

from typing import TYPE_CHECKING, Any

import customtkinter as ctk

from ..components import DraggableSash
from ..scaling import scaled
from ..styles import COLORS

if TYPE_CHECKING:
    from ..app import ModernTrafficBot


class DashboardPage:
    """Dashboard page for traffic campaign control.

    Handles:
    - Campaign configuration (URL, threads, duration)
    - Engine mode selection (curl/browser)
    - Burst mode settings
    - Real-time stats display
    - Activity logging
    """

    def __init__(self, app: "ModernTrafficBot"):
        """Initialize the dashboard page.

        Args:
            app: The main application instance for shared state access.
        """
        self.app = app

        # UI widget references (populated during setup)
        self.lbl_stats: dict[str, ctk.CTkLabel] = {}
        self.entry_url: ctk.CTkEntry = None
        self.mode_selector: ctk.CTkSegmentedButton = None
        self.slider_threads: ctk.CTkSlider = None
        self.slider_view_min: ctk.CTkSlider = None
        self.slider_view_max: ctk.CTkSlider = None
        self.slider_burst_size: ctk.CTkSlider = None
        self.slider_burst_sleep: ctk.CTkSlider = None
        self.lbl_threads: ctk.CTkLabel = None
        self.lbl_viewtime: ctk.CTkLabel = None
        self.lbl_burst: ctk.CTkLabel = None
        self.chk_burst_mode: ctk.CTkCheckBox = None
        self.btn_attack: ctk.CTkButton = None
        self.btn_reset: ctk.CTkButton = None
        self.browser_stats_frame: ctk.CTkFrame = None
        self.lbl_browser_type: ctk.CTkLabel = None
        self.lbl_browser_contexts: ctk.CTkLabel = None
        self.lbl_captcha_stats: ctk.CTkLabel = None
        self.lbl_balance_2captcha: ctk.CTkLabel = None
        self.lbl_balance_anticaptcha: ctk.CTkLabel = None
        self.lbl_protection_stats: ctk.CTkLabel = None
        self.lbl_protection_event: ctk.CTkLabel = None
        self.log_box: ctk.CTkTextbox = None

        # Internal state
        self._config_height = scaled(280)
        self._config_min = scaled(150)
        self._log_min = scaled(80)

    @property
    def settings(self) -> dict[str, Any]:
        """Access app settings."""
        return self.app.settings

    def setup(self, parent: ctk.CTkFrame) -> None:
        """Set up the dashboard UI.

        Args:
            parent: The parent frame to build the UI in.
        """
        # Use grid for scalable layout with draggable sash
        parent.grid_rowconfigure(0, weight=0)  # Scrollable config area
        parent.grid_rowconfigure(1, weight=0)  # Draggable sash
        parent.grid_rowconfigure(2, weight=1)  # Activity log expands
        parent.grid_columnconfigure(0, weight=1)

        # Scrollable container for config (enables scroll on small screens)
        config_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        config_scroll.grid(row=0, column=0, sticky="nsew", pady=(0, 0))
        config_scroll.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=0, minsize=self._config_height)

        # Draggable sash between config and log
        def on_sash_drag(delta):
            new_height = self._config_height + delta
            parent_height = parent.winfo_height()
            max_config = parent_height - self._log_min - scaled(10)
            new_height = max(self._config_min, min(new_height, max_config))
            if new_height != self._config_height:
                self._config_height = new_height
                parent.grid_rowconfigure(0, weight=0, minsize=int(self._config_height))

        sash = DraggableSash(
            parent,
            on_drag=on_sash_drag,
            min_above=self._config_min,
            min_below=self._log_min,
        )
        sash.grid(row=1, column=0, sticky="ew", pady=(0, 0))

        # Build UI sections
        self._setup_stats_row(config_scroll)
        self._setup_config_card(config_scroll)
        self._setup_browser_stats(config_scroll)
        self._setup_activity_log(parent)

        # Initial visibility state
        self._update_browser_stats_visibility()

    def _setup_stats_row(self, parent: ctk.CTkFrame) -> None:
        """Set up the primary stats display row."""
        stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 8))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="stats")

        stat_configs = [
            ("req", "Requests", COLORS["text"]),
            ("success", "Success", COLORS["success"]),
            ("fail", "Failed", COLORS["danger"]),
            ("proxies", "Proxies", COLORS["accent"]),
        ]
        for col, (key, title, color) in enumerate(stat_configs):
            card = ctk.CTkFrame(stats_frame, fg_color=COLORS["card"])
            card.grid(row=0, column=col, sticky="nsew", padx=3, pady=2)
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                card, text=title, font=("Roboto", 10), text_color=COLORS["text_dim"]
            ).pack(pady=(8, 2))
            lbl = ctk.CTkLabel(
                card, text="0", font=("Roboto", 22, "bold"), text_color=color
            )
            lbl.pack(pady=(0, 8))
            self.lbl_stats[key] = lbl

    def _setup_config_card(self, parent: ctk.CTkFrame) -> None:
        """Set up the main configuration card."""
        cfg_frame = ctk.CTkFrame(parent, fg_color=COLORS["card"])
        cfg_frame.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(
            cfg_frame, text="Attack Configuration", font=("Roboto", 14, "bold")
        ).pack(anchor="w", padx=20, pady=15)

        # Target URL
        self.entry_url = ctk.CTkEntry(
            cfg_frame, placeholder_text="https://target.com", height=scaled(32)
        )
        self.entry_url.pack(fill="x", padx=20, pady=(0, 10))
        self.entry_url.insert(0, self.settings.get("target_url", ""))

        # Engine Mode Selector
        self._setup_engine_selector(cfg_frame)

        # Sliders
        self._setup_sliders(cfg_frame)

        # Button Row
        self._setup_buttons(cfg_frame)

    def _setup_engine_selector(self, parent: ctk.CTkFrame) -> None:
        """Set up the engine mode selector."""
        mode_frame = ctk.CTkFrame(parent, fg_color="transparent")
        mode_frame.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(mode_frame, text="Engine:", font=("Roboto", 12)).pack(
            side="left", padx=(0, 10)
        )

        self.mode_selector = ctk.CTkSegmentedButton(
            mode_frame,
            values=["Fast (curl)", "Browser (stealth)"],
            command=self.on_mode_change,
            font=("Roboto", 11),
            fg_color=COLORS["card"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
        )
        current_mode = self.settings.get("engine_mode", "curl")
        self.mode_selector.set(
            "Fast (curl)" if current_mode == "curl" else "Browser (stealth)"
        )
        self.mode_selector.pack(side="left", fill="x", expand=True)

    def _setup_sliders(self, parent: ctk.CTkFrame) -> None:
        """Set up the configuration sliders."""
        slider_row = ctk.CTkFrame(parent, fg_color="transparent")
        slider_row.pack(fill="x", padx=15, pady=10)
        slider_row.grid_columnconfigure(0, weight=2)  # Threads
        slider_row.grid_columnconfigure(1, weight=3)  # Duration
        slider_row.grid_columnconfigure(2, weight=3)  # Burst mode

        # Threads slider
        self._setup_threads_slider(slider_row)

        # Duration sliders
        self._setup_duration_sliders(slider_row)

        # Burst mode controls
        self._setup_burst_controls(slider_row)

    def _setup_threads_slider(self, parent: ctk.CTkFrame) -> None:
        """Set up the threads slider."""
        t_frame = ctk.CTkFrame(parent, fg_color="transparent")
        t_frame.grid(row=0, column=0, sticky="nsew", padx=5)

        self.lbl_threads = ctk.CTkLabel(
            t_frame, text=f"Threads: {self.settings.get('threads', 5)}"
        )
        self.lbl_threads.pack(anchor="w")

        self.slider_threads = ctk.CTkSlider(
            t_frame,
            from_=1,
            to=100,
            number_of_steps=99,
            command=self.update_thread_lbl,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
        )
        self.slider_threads.set(self.settings.get("threads", 5))
        self.slider_threads.pack(fill="x", pady=5)

    def _setup_duration_sliders(self, parent: ctk.CTkFrame) -> None:
        """Set up the view duration sliders."""
        v_frame = ctk.CTkFrame(parent, fg_color="transparent")
        v_frame.grid(row=0, column=1, sticky="nsew", padx=5)

        self.lbl_viewtime = ctk.CTkLabel(
            v_frame,
            text=f"Duration: {self.settings.get('viewtime_min', 5)}s - {self.settings.get('viewtime_max', 10)}s",
        )
        self.lbl_viewtime.pack(anchor="w")

        duration_sliders = ctk.CTkFrame(v_frame, fg_color="transparent")
        duration_sliders.pack(fill="x")
        duration_sliders.grid_columnconfigure((0, 1), weight=1)

        # Min slider
        min_frame = ctk.CTkFrame(duration_sliders, fg_color="transparent")
        min_frame.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkLabel(min_frame, text="Min:", font=("Roboto", 10)).pack(anchor="w")
        self.slider_view_min = ctk.CTkSlider(
            min_frame,
            from_=1,
            to=60,
            number_of_steps=59,
            command=self.update_view_lbl,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
        )
        self.slider_view_min.set(self.settings.get("viewtime_min", 5))
        self.slider_view_min.pack(fill="x", pady=2)

        # Max slider
        max_frame = ctk.CTkFrame(duration_sliders, fg_color="transparent")
        max_frame.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ctk.CTkLabel(max_frame, text="Max:", font=("Roboto", 10)).pack(anchor="w")
        self.slider_view_max = ctk.CTkSlider(
            max_frame,
            from_=1,
            to=60,
            number_of_steps=59,
            command=self.update_view_lbl,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
        )
        self.slider_view_max.set(self.settings.get("viewtime_max", 10))
        self.slider_view_max.pack(fill="x", pady=2)

    def _setup_burst_controls(self, parent: ctk.CTkFrame) -> None:
        """Set up the burst mode controls."""
        burst_frame = ctk.CTkFrame(parent, fg_color="transparent")
        burst_frame.grid(row=0, column=2, sticky="nsew", padx=5)

        # Burst enable checkbox and label
        burst_header = ctk.CTkFrame(burst_frame, fg_color="transparent")
        burst_header.pack(fill="x")
        self.chk_burst_mode = ctk.CTkCheckBox(
            burst_header,
            text="",
            width=scaled(20),
            command=self.on_burst_toggle,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
        )
        self.chk_burst_mode.pack(side="left")
        if self.settings.get("burst_mode", False):
            self.chk_burst_mode.select()

        self.lbl_burst = ctk.CTkLabel(
            burst_header,
            text=f"Burst: {self.settings.get('burst_requests', 10)} req, "
            f"{self.settings.get('burst_sleep_min', 2)}-{self.settings.get('burst_sleep_max', 5)}s sleep",
        )
        self.lbl_burst.pack(side="left", padx=(2, 0))

        # Burst size and sleep sliders
        burst_sliders = ctk.CTkFrame(burst_frame, fg_color="transparent")
        burst_sliders.pack(fill="x")
        burst_sliders.grid_columnconfigure((0, 1), weight=1)

        # Burst size
        size_frame = ctk.CTkFrame(burst_sliders, fg_color="transparent")
        size_frame.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ctk.CTkLabel(size_frame, text="Requests:", font=("Roboto", scaled(10))).pack(
            anchor="w"
        )
        self.slider_burst_size = ctk.CTkSlider(
            size_frame,
            from_=5,
            to=50,
            number_of_steps=45,
            command=self.update_burst_lbl,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
        )
        self.slider_burst_size.set(self.settings.get("burst_requests", 10))
        self.slider_burst_size.pack(fill="x", pady=2)

        # Sleep duration
        sleep_frame = ctk.CTkFrame(burst_sliders, fg_color="transparent")
        sleep_frame.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ctk.CTkLabel(sleep_frame, text="Sleep (s):", font=("Roboto", scaled(10))).pack(
            anchor="w"
        )
        self.slider_burst_sleep = ctk.CTkSlider(
            sleep_frame,
            from_=1,
            to=30,
            number_of_steps=29,
            command=self.update_burst_lbl,
            button_color=COLORS["accent"],
            button_hover_color=COLORS["accent_hover"],
        )
        self.slider_burst_sleep.set(self.settings.get("burst_sleep_max", 5))
        self.slider_burst_sleep.pack(fill="x", pady=2)

    def _setup_buttons(self, parent: ctk.CTkFrame) -> None:
        """Set up the control buttons."""
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=20)

        self.btn_attack = ctk.CTkButton(
            btn_row,
            text="START CAMPAIGN",
            height=scaled(40),
            fg_color=COLORS["success"],
            font=("Roboto", scaled(13), "bold"),
            command=self.app.toggle_attack,
        )
        self.btn_attack.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_reset = ctk.CTkButton(
            btn_row,
            text="RESET",
            height=scaled(40),
            fg_color=COLORS["warning"],
            font=("Roboto", scaled(11), "bold"),
            width=scaled(70),
            command=self.app.reset_stats,
        )
        self.btn_reset.pack(side="right")

    def _setup_browser_stats(self, parent: ctk.CTkFrame) -> None:
        """Set up the browser stats panel (shown only in browser mode)."""
        self.browser_stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.browser_stats_frame.pack(fill="x", pady=(0, 8))
        self.browser_stats_frame.grid_columnconfigure(
            (0, 1, 2), weight=1, uniform="bstats"
        )

        # Browser Info Card
        browser_card = ctk.CTkFrame(self.browser_stats_frame, fg_color=COLORS["card"])
        browser_card.grid(row=0, column=0, sticky="nsew", padx=3, pady=2)
        ctk.CTkLabel(
            browser_card,
            text="Browser",
            font=("Roboto", 10),
            text_color=COLORS["text_dim"],
        ).pack(pady=(8, 2))
        self.lbl_browser_type = ctk.CTkLabel(
            browser_card,
            text="--",
            font=("Roboto", 16, "bold"),
            text_color=COLORS["accent"],
        )
        self.lbl_browser_type.pack(pady=(0, 2))
        self.lbl_browser_contexts = ctk.CTkLabel(
            browser_card,
            text="Contexts: 0/0",
            font=("Roboto", 10),
            text_color=COLORS["text_dim"],
        )
        self.lbl_browser_contexts.pack(pady=(0, 8))

        # Captcha Stats Card
        captcha_card = ctk.CTkFrame(self.browser_stats_frame, fg_color=COLORS["card"])
        captcha_card.grid(row=0, column=1, sticky="nsew", padx=3, pady=2)
        ctk.CTkLabel(
            captcha_card,
            text="Captcha (\u2713/\u2717/\u22ef)",
            font=("Roboto", 10),
            text_color=COLORS["text_dim"],
        ).pack(pady=(8, 2))
        self.lbl_captcha_stats = ctk.CTkLabel(
            captcha_card,
            text="0 / 0 / 0",
            font=("Roboto", 16, "bold"),
            text_color=COLORS["success"],
        )
        self.lbl_captcha_stats.pack(pady=(0, 4))

        # Balance labels
        balance_frame = ctk.CTkFrame(captcha_card, fg_color="transparent")
        balance_frame.pack(fill="x", padx=10, pady=(0, 8))
        balance_frame.grid_columnconfigure((0, 1), weight=1)

        self.lbl_balance_2captcha = ctk.CTkLabel(
            balance_frame,
            text="2Cap: --",
            font=("Roboto", 10),
            text_color=COLORS["text_dim"],
        )
        self.lbl_balance_2captcha.grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.lbl_balance_anticaptcha = ctk.CTkLabel(
            balance_frame,
            text="Anti: --",
            font=("Roboto", 10),
            text_color=COLORS["text_dim"],
        )
        self.lbl_balance_anticaptcha.grid(row=0, column=1, sticky="e", padx=(5, 0))

        # Protection Status Card
        protection_card = ctk.CTkFrame(
            self.browser_stats_frame, fg_color=COLORS["card"]
        )
        protection_card.grid(row=0, column=2, sticky="nsew", padx=3, pady=2)
        ctk.CTkLabel(
            protection_card,
            text="Protection (det/byp)",
            font=("Roboto", 10),
            text_color=COLORS["text_dim"],
        ).pack(pady=(8, 2))
        self.lbl_protection_stats = ctk.CTkLabel(
            protection_card,
            text="0 / 0",
            font=("Roboto", 16, "bold"),
            text_color=COLORS["warning"],
        )
        self.lbl_protection_stats.pack(pady=(0, 2))
        self.lbl_protection_event = ctk.CTkLabel(
            protection_card,
            text="No events",
            font=("Roboto", 10),
            text_color=COLORS["text_dim"],
        )
        self.lbl_protection_event.pack(pady=(0, 8))

    def _setup_activity_log(self, parent: ctk.CTkFrame) -> None:
        """Set up the activity log panel."""
        log_frame = ctk.CTkFrame(parent, fg_color="transparent")
        log_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 0))
        log_frame.grid_rowconfigure(1, weight=1, minsize=self._log_min)
        log_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            log_frame,
            text="Activity Log",
            font=("Roboto", scaled(11)),
            text_color=COLORS["text_dim"],
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.log_box = ctk.CTkTextbox(
            log_frame, fg_color=COLORS["card"], height=scaled(100)
        )
        self.log_box.grid(row=1, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

    # Event handlers

    def update_thread_lbl(self, value) -> None:
        """Update the threads label."""
        self.lbl_threads.configure(text=f"Threads: {int(value)}")

    def update_view_lbl(self, value) -> None:
        """Update the view duration label."""
        mn = int(self.slider_view_min.get())
        mx = int(self.slider_view_max.get())
        self.lbl_viewtime.configure(text=f"Duration: {mn}s - {mx}s")

    def update_burst_lbl(self, value=None) -> None:
        """Update burst mode label with current settings."""
        burst_size = int(self.slider_burst_size.get())
        sleep_max = int(self.slider_burst_sleep.get())
        sleep_min = max(1, sleep_max // 2)
        self.lbl_burst.configure(
            text=f"Burst: {burst_size} req, {sleep_min}-{sleep_max}s sleep"
        )

    def on_burst_toggle(self) -> None:
        """Handle burst mode toggle."""
        enabled = self.chk_burst_mode.get()
        self.settings["burst_mode"] = enabled
        state = "enabled" if enabled else "disabled"
        self.app.log(f"Burst mode {state}")

    def on_mode_change(self, value) -> None:
        """Handle engine mode change."""
        is_browser = "Browser" in value
        self.settings["engine_mode"] = "browser" if is_browser else "curl"

        # Adjust thread slider limits based on mode
        if is_browser:
            self.slider_threads.configure(from_=1, to=10, number_of_steps=9)
            current = int(self.slider_threads.get())
            if current > 10:
                self.slider_threads.set(5)
                self.lbl_threads.configure(text="Threads: 5")
        else:
            self.slider_threads.configure(from_=1, to=100, number_of_steps=99)

        self._update_browser_stats_visibility()
        self.app.log(
            f"Engine mode: {'Browser (stealth)' if is_browser else 'Fast (curl)'}"
        )

    def _update_browser_stats_visibility(self) -> None:
        """Show/hide browser stats row based on engine mode."""
        is_browser = self.settings.get("engine_mode", "curl") == "browser"
        if is_browser:
            self.browser_stats_frame.pack(fill="x", pady=(0, 8))
        else:
            self.browser_stats_frame.pack_forget()

    def log(self, message: str) -> None:
        """Log a message to the activity log."""
        import time

        timestamp = time.strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
