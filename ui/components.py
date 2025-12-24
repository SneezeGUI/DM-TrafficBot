from tkinter import Canvas

import customtkinter as ctk

from .styles import COLORS


def get_scaling_factor():
    """Get the current widget scaling factor from customtkinter."""
    try:
        return ctk.ScalingTracker.get_widget_scaling(None)
    except Exception:
        return 1.0


class DraggableSash(ctk.CTkFrame):
    """
    A horizontal sash/splitter that can be dragged to resize panels above/below.
    Used between config area and activity log to allow user-adjustable heights.
    """

    def __init__(self, master, on_drag=None, min_above=100, min_below=80, **kwargs):
        """
        Args:
            master: Parent widget
            on_drag: Callback function(delta_y) called during drag with pixel change
            min_above: Minimum height for panel above sash
            min_below: Minimum height for panel below sash
        """
        # Default styling for sash
        kwargs.setdefault("height", int(6 * get_scaling_factor()))
        kwargs.setdefault("fg_color", COLORS.get("nav", "#2a2a3d"))
        kwargs.setdefault("corner_radius", 0)

        super().__init__(master, **kwargs)

        self.on_drag = on_drag
        self.min_above = min_above
        self.min_below = min_below
        self._drag_start_y = None
        self._is_dragging = False

        # Visual handle indicator (centered grip lines)
        self._grip = ctk.CTkFrame(
            self,
            fg_color=COLORS.get("text_dim", "#888"),
            width=int(40 * get_scaling_factor()),
            height=int(2 * get_scaling_factor()),
            corner_radius=1,
        )
        self._grip.place(relx=0.5, rely=0.5, anchor="center")

        # Bind mouse events
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)

        # Also bind to grip
        self._grip.bind("<Enter>", self._on_enter)
        self._grip.bind("<Leave>", self._on_leave)
        self._grip.bind("<Button-1>", self._on_press)
        self._grip.bind("<B1-Motion>", self._on_motion)
        self._grip.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self, event):
        """Change cursor to resize indicator on hover."""
        self.configure(cursor="sb_v_double_arrow")
        self._grip.configure(fg_color=COLORS.get("accent", "#00d4aa"))

    def _on_leave(self, event):
        """Reset cursor when leaving."""
        if not self._is_dragging:
            self.configure(cursor="")
            self._grip.configure(fg_color=COLORS.get("text_dim", "#888"))

    def _on_press(self, event):
        """Start drag operation."""
        self._drag_start_y = event.y_root
        self._is_dragging = True

    def _on_motion(self, event):
        """Handle drag movement."""
        if self._drag_start_y is not None and self.on_drag:
            delta = event.y_root - self._drag_start_y
            self._drag_start_y = event.y_root
            self.on_drag(delta)

    def _on_release(self, event):
        """End drag operation."""
        self._drag_start_y = None
        self._is_dragging = False
        # Check if mouse is still over sash
        try:
            widget_under = self.winfo_containing(event.x_root, event.y_root)
            if widget_under != self and widget_under != self._grip:
                self.configure(cursor="")
                self._grip.configure(fg_color=COLORS.get("text_dim", "#888"))
        except Exception:
            pass


class VirtualGrid(ctk.CTkFrame):
    def __init__(self, master, columns, **kwargs):
        super().__init__(master, **kwargs)
        self.data = []

        # Scale-aware row height
        self._base_row_h = 30
        self.row_h = int(self._base_row_h * get_scaling_factor())

        self.sort_key = None  # Track current sort column
        self.sort_reverse = False
        self._needs_draw = False  # Deferred drawing flag
        self._needs_sort = False  # Deferred sort flag
        self._last_draw_len = 0  # Track data length at last draw

        # Column width management - proportional weights (will be converted to pixels)
        self.col_map = columns
        self.num_cols = len(columns)
        # Default weights: Address wider, others smaller
        self.col_weights = [
            2.0,
            0.8,
            1.2,
            0.8,
            0.8,
            0.8,
        ]  # Address, Proto, Country, Status, Ping, Anon

        # Resize tracking
        self._resize_col = None
        self._resize_start_x = 0
        self._resize_start_weights = None
        self._min_col_weight = 0.4  # Minimum column weight

        # Scale-aware header height
        self._header_h = int(35 * get_scaling_factor())
        self._header_font_size = max(9, int(11 * get_scaling_factor()))

        # Create main container frame for header + canvas (excludes scrollbar)
        self._content_frame = ctk.CTkFrame(
            self, fg_color="transparent", corner_radius=0
        )
        self._content_frame.pack(side="left", fill="both", expand=True)

        # Header frame - use place geometry for precise positioning
        self.headers = ctk.CTkFrame(
            self._content_frame,
            height=self._header_h,
            fg_color=COLORS["nav"],
            corner_radius=0,
        )
        self.headers.pack(fill="x")
        self.headers.pack_propagate(False)  # Keep fixed height

        # Create header buttons (will be positioned by _update_header_positions)
        self.header_btns = []
        for i, col in enumerate(columns):
            btn = ctk.CTkButton(
                self.headers,
                text=col,
                font=("Roboto", self._header_font_size, "bold"),
                fg_color="transparent",
                hover_color=COLORS["card"],
                text_color=COLORS["accent"],
                corner_radius=0,
                height=self._header_h,
                command=lambda c=col, idx=i: self._on_header_command(c, idx),
            )
            self.header_btns.append(btn)
            # Bind motion for cursor change
            btn.bind("<Motion>", lambda e, idx=i: self._on_header_motion(e, idx))
            btn.bind("<Button-1>", lambda e, idx=i: self._on_btn_press(e, idx))
            btn.bind("<B1-Motion>", self._on_header_drag_global)
            btn.bind("<ButtonRelease-1>", self._on_header_release)

        # Bind drag events to header frame background
        self.headers.bind("<Button-1>", self._on_header_press)
        self.headers.bind("<B1-Motion>", self._on_header_drag_global)
        self.headers.bind("<ButtonRelease-1>", self._on_header_release)

        # Canvas for data rows
        self.canvas = Canvas(self._content_frame, bg=COLORS["bg"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Scrollbar (outside content frame, aligned with canvas)
        self.scr = ctk.CTkScrollbar(
            self, command=self.canvas.yview, width=14, fg_color=COLORS["bg"]
        )
        self.scr.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=self.scr.set)

        # Bind events
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind(
            "<MouseWheel>",
            lambda e: (
                self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
                self.draw(),
            ),
        )
        self.headers.bind("<Configure>", lambda e: self._update_header_positions())

    def _on_canvas_configure(self, event=None):
        """Handle canvas resize - update headers and redraw."""
        self._update_header_positions()
        self.draw()

    def _update_header_positions(self):
        """Position header buttons to exactly match canvas column positions."""
        w = self.canvas.winfo_width()
        if w < 10:  # Not yet sized
            return

        positions = self._get_col_positions(w)

        for i, btn in enumerate(self.header_btns):
            x = positions[i]
            width = positions[i + 1] - positions[i]
            # CTk widgets require width via configure(), not place()
            btn.configure(width=width)
            btn.place(x=x, y=0)

    def _on_header_motion(self, event, col_idx):
        """Change cursor when near column edge for resize."""
        btn = self.header_btns[col_idx]
        btn_width = btn.winfo_width()
        # If within 10 pixels of right edge and not the last column
        if btn_width - event.x < 10 and col_idx < self.num_cols - 1:
            btn.configure(cursor="sb_h_double_arrow")
        else:
            btn.configure(cursor="")

    def _on_header_command(self, col_name, col_idx):
        """Handle header button click - sort unless we're resizing."""
        # Don't sort if we just finished a resize operation
        if self._resize_col is not None:
            return
        self.sort_by(col_name)

    def _on_btn_press(self, event, col_idx):
        """Handle button press - check if starting resize."""
        btn = self.header_btns[col_idx]
        btn_width = btn.winfo_width()
        # If clicking near right edge, start resize
        if btn_width - event.x < 10 and col_idx < self.num_cols - 1:
            self._resize_col = col_idx
            self._resize_start_x = event.x_root
            self._resize_start_weights = self.col_weights.copy()
            # Prevent the button command from firing
            return "break"

    def _on_header_press(self, event):
        """Handle press on header frame (between buttons)."""
        # Find which column edge we're near based on x position
        x = event.x
        w = self.canvas.winfo_width()
        if w < 10:
            return
        col_positions = self._get_col_positions(w)
        for i in range(
            len(col_positions) - 2
        ):  # -2 because last column can't be resized
            edge_x = col_positions[i + 1]
            if abs(x - edge_x) < 10:
                self._resize_col = i
                self._resize_start_x = event.x_root
                self._resize_start_weights = self.col_weights.copy()
                return

    def _on_header_drag_global(self, event):
        """Handle column resize drag - works across entire header."""
        if self._resize_col is not None:
            delta = event.x_root - self._resize_start_x
            # Convert delta pixels to weight change
            total_width = max(self.canvas.winfo_width(), 1)
            total_weight = sum(self._resize_start_weights)
            weight_per_pixel = total_weight / total_width
            weight_delta = delta * weight_per_pixel

            # Adjust the resized column and the next column
            new_weight = self._resize_start_weights[self._resize_col] + weight_delta
            next_weight = (
                self._resize_start_weights[self._resize_col + 1] - weight_delta
            )

            # Enforce minimum weights
            if (
                new_weight >= self._min_col_weight
                and next_weight >= self._min_col_weight
            ):
                self.col_weights[self._resize_col] = new_weight
                self.col_weights[self._resize_col + 1] = next_weight
                self._update_header_weights()
                self.draw()

    def _on_header_release(self, event):
        """End resize operation."""
        # Small delay before clearing resize_col to prevent sort from firing
        if self._resize_col is not None:
            self.after(50, self._clear_resize)

    def _clear_resize(self):
        """Clear resize state after delay."""
        self._resize_col = None
        # Reset all cursors
        for btn in self.header_btns:
            btn.configure(cursor="")

    def _update_header_weights(self):
        """Update header button positions after weight change."""
        self._update_header_positions()

    def _get_col_positions(self, total_width):
        """Calculate column positions based on weights."""
        total_weight = sum(self.col_weights)
        positions = [0]
        cumulative = 0
        for w in self.col_weights:
            cumulative += (w / total_weight) * total_width
            positions.append(int(cumulative))
        return positions

    def sort_by(self, col_name):
        key_map = {
            "Address": "ip",
            "Proto": "type",
            "Country": "country_code",
            "Status": "status",
            "Ping": "speed",
            "Anon": "anonymity",
        }
        key = key_map.get(col_name, "speed")
        # Toggle direction only if clicking same column, otherwise keep direction
        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        self.sort_key = key
        self._apply_sort()

    def _apply_sort(self, force_draw=True):
        """Apply current sort to data."""
        if not self.sort_key or not self.data:
            return
        try:
            self.data.sort(key=lambda x: x[self.sort_key], reverse=self.sort_reverse)
        except (KeyError, TypeError):
            self.data.sort(
                key=lambda x: str(x.get(self.sort_key, "")), reverse=self.sort_reverse
            )
        if force_draw:
            self.draw()
        else:
            self._needs_draw = True

    def add(self, item):
        """Add item without immediate draw - call flush() to render."""
        self.data.append(item)
        # Mark for deferred sort every 100 items (not 10 - reduces CPU)
        if self.sort_key and len(self.data) % 100 == 0:
            self._needs_sort = True
        self._needs_draw = True

    def flush(self):
        """
        Flush pending changes - apply deferred sort and draw.
        Call this periodically from GUI loop instead of drawing on every add.
        """
        if self._needs_sort and self.sort_key:
            self._apply_sort(force_draw=False)
            self._needs_sort = False

        if self._needs_draw:
            self.draw()
            self._needs_draw = False
            self._last_draw_len = len(self.data)

    def clear(self):
        self.data = []
        self._needs_draw = False
        self._needs_sort = False
        self._last_draw_len = 0
        self.canvas.delete("all")
        self.draw()

    def get_active_objects(self):
        return [d for d in self.data if d["status"] == "Active"]

    def get_active(self):
        return [
            f"{d['type'].lower()}://{d['ip']}:{d['port']}"
            for d in self.data
            if d["status"] == "Active"
        ]

    def get_counts(self):
        counts = {"HTTP": 0, "HTTPS": 0, "SOCKS4": 0, "SOCKS5": 0}
        for d in self.data:
            t = d.get("type", "HTTP").upper()
            if t == "HTTPS":
                counts["HTTPS"] += 1
            elif "HTTP" in t:
                counts["HTTP"] += 1
            elif "SOCKS4" in t:
                counts["SOCKS4"] += 1
            elif "SOCKS5" in t:
                counts["SOCKS5"] += 1
        return counts

    def get_anonymity_counts(self):
        """Get counts for each anonymity level."""
        counts = {"Elite": 0, "Anonymous": 0, "Transparent": 0, "Unknown": 0}
        for d in self.data:
            if d.get("status") != "Active":
                continue
            anon = d.get("anonymity", "Unknown")
            if anon in counts:
                counts[anon] += 1
            else:
                counts["Unknown"] += 1
        return counts

    def get_all_stats(self):
        """
        Get all stats in a single pass - more efficient than calling
        get_counts() and get_anonymity_counts() separately.
        Returns (proto_counts, anon_counts)
        """
        proto = {"HTTP": 0, "HTTPS": 0, "SOCKS4": 0, "SOCKS5": 0}
        anon = {"Elite": 0, "Anonymous": 0, "Transparent": 0, "Unknown": 0}

        for d in self.data:
            # Protocol counts
            t = d.get("type", "HTTP").upper()
            if t == "HTTPS":
                proto["HTTPS"] += 1
            elif "HTTP" in t:
                proto["HTTP"] += 1
            elif "SOCKS4" in t:
                proto["SOCKS4"] += 1
            elif "SOCKS5" in t:
                proto["SOCKS5"] += 1

            # Anonymity counts (only for active proxies)
            if d.get("status") == "Active":
                a = d.get("anonymity", "Unknown")
                if a in anon:
                    anon[a] += 1
                else:
                    anon["Unknown"] += 1

        return proto, anon

    def draw(self, _=None):
        # Update row height for current scaling
        self.row_h = int(self._base_row_h * get_scaling_factor())

        self.canvas.delete("all")
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        total_h = len(self.data) * self.row_h
        self.canvas.configure(scrollregion=(0, 0, w, total_h))

        y_off = self.canvas.yview()[0] * total_h
        start = int(y_off // self.row_h)
        end = start + int(h // self.row_h) + 2

        # Get column positions based on weights
        col_positions = self._get_col_positions(w)

        # Scale-aware font size
        font_size = max(8, int(10 * get_scaling_factor()))

        for i in range(start, min(end, len(self.data))):
            item = self.data[i]
            y = i * self.row_h
            bg_col = COLORS["card"] if i % 2 == 0 else COLORS["bg"]
            self.canvas.create_rectangle(0, y, w, y + self.row_h, fill=bg_col, width=0)

            # Build country display: [CC] City, Country or [CC] Country
            country_code = item.get("country_code", "??")
            country_name = item.get("country", "")
            city = item.get("city", "")

            # Use text-based display (Tkinter Canvas doesn't render emoji flags well)
            if city and country_code and country_code != "??":
                location_str = f"[{country_code}] {city}"
            elif country_name and country_name != "Unknown":
                location_str = f"[{country_code}] {country_name}"
            elif country_code and country_code != "??":
                location_str = f"[{country_code}]"
            else:
                location_str = "[??]"

            vals = [
                f"{item['ip']}:{item['port']}",
                item["type"],
                location_str,
                item["status"],
                f"{item['speed']} ms",
                item["anonymity"],
            ]
            for c, val in enumerate(vals):
                # Color-code columns
                if c == 1:  # Protocol column - color by type
                    proto = str(val).upper()
                    if proto == "HTTP":
                        color = "#3498DB"  # Blue
                    elif proto == "HTTPS":
                        color = "#9B59B6"  # Purple
                    elif "SOCKS5" in proto:
                        color = "#1ABC9C"  # Teal
                    elif "SOCKS4" in proto:
                        color = "#16A085"  # Dark teal
                    else:
                        color = COLORS["text"]
                elif c == 3:  # Status column
                    color = COLORS["success"] if val == "Active" else COLORS["danger"]
                elif c == 4:  # Ping column - color by speed
                    speed = item.get("speed", 9999)
                    if speed <= 2500:
                        color = COLORS["success"]  # Green
                    elif speed <= 5000:
                        color = "#F1C40F"  # Yellow
                    elif speed <= 7500:
                        color = COLORS["warning"]  # Orange
                    else:
                        color = COLORS["danger"]  # Red
                elif c == 5:  # Anonymity column - color by level
                    anon = item.get("anonymity", "Unknown")
                    if anon == "Elite":
                        color = COLORS["success"]  # Green - best
                    elif anon == "Anonymous":
                        color = "#F1C40F"  # Yellow - ok
                    elif anon == "Transparent":
                        color = COLORS["danger"]  # Red - bad
                    else:
                        color = COLORS["text_dim"]  # Gray - unknown
                else:
                    color = COLORS["text"]
                # Use column positions for text placement (scale-aware)
                text_y = y + (self.row_h // 2)  # Center vertically in row
                text_x = col_positions[c] + int(10 * get_scaling_factor())
                self.canvas.create_text(
                    text_x,
                    text_y,
                    text=str(val),
                    fill=color,
                    anchor="w",
                    font=("Roboto", font_size),
                )


class ActivityLog(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLORS["card"])
        super().__init__(master, **kwargs)

        self._log_lock = False  # Simple lock to prevent concurrent updates

        # Scale-aware height
        min_h = int(100 * get_scaling_factor())

        self.txt = ctk.CTkTextbox(
            self, fg_color=COLORS["bg"], wrap="word", height=min_h
        )
        self.txt.pack(fill="both", expand=True, padx=5, pady=5)

        # Configure text color
        self.txt._textbox.configure(foreground=COLORS.get("text", "#ffffff"))

    def log(self, message: str):
        """Thread-safe logging with auto-scroll."""
        if self._log_lock:
            return
        try:
            self._log_lock = True
            self.txt.insert("end", f"{message}\n")
            # Keep only last 1000 lines
            lines = int(self.txt.index("end-1c").split(".")[0])
            if lines > 1000:
                self.txt.delete("1.0", f"{lines - 1000}.0")
            # Auto-scroll to bottom
            self.txt.see("end")
        finally:
            self._log_lock = False

    def clear(self):
        self.txt.delete("1.0", "end")
