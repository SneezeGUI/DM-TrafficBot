# CLAUDE.MD - Project Context for Claude Code

## Project Overview

**DarkMatter Traffic Bot (DM-Trafficbot)** is a sophisticated, high-performance traffic generation, proxy validation, and authorized security testing tool built with Python and CustomTkinter. It combines human emulation (Browser/TLS fingerprinting) with stress testing capabilities, designed for security researchers, QA teams, and developers.

**Current Version:** v3.6.1
**Python Version:** 3.10+
**Main Repository:** `O:\Development\Web-Apps\web-traffic-tool`
**Entry Point:** `main.py`
**Virtual Environment:** `.venv` (required)

---

## Architecture & Core Components

### Application Structure

```
web-traffic-tool/
├── main.py                 # Application entry point
├── ui/
│   ├── __init__.py
│   ├── app.py             # Main application class (ModernTrafficBot)
│   ├── scaling.py         # DPI scaling utilities
│   ├── styles.py          # Color scheme and UI constants
│   ├── utils.py           # Utility functions (settings, validation)
│   ├── components/
│   │   ├── draggable_sash.py    # Resizable panel divider
│   │   └── virtual_grid.py      # High-performance virtualized grid (10k+ rows)
│   └── pages/
│       ├── __init__.py
│       ├── dashboard.py         # Traffic campaign management (~500 lines)
│       ├── proxy_manager.py     # Proxy testing & management (~350 lines)
│       ├── stress_test.py       # Load testing interface (~360 lines)
│       └── settings.py          # Configuration panel (~350 lines)
├── core/
│   ├── __init__.py
│   ├── models.py          # Data models (TrafficConfig, ProxyConfig, etc.)
│   ├── engine.py          # Async traffic engine (curl_cffi)
│   ├── browser_engine.py  # Browser automation engine (Playwright)
│   ├── stress_engine.py   # HTTP flood/Slowloris/RUDY attacks
│   ├── proxy_manager.py   # Threaded proxy scraper & validator
│   ├── validators.py      # 6 built-in IP validators (httpbin, ipify, etc.)
│   ├── browser_manager.py # Browser detection & fingerprinting
│   ├── captcha_manager.py # 2Captcha/AntiCaptcha integration
│   ├── captcha_solver.py  # Legacy captcha solver
│   ├── header_manager.py  # HTTP header generation
│   └── constants.py       # Shared constants
├── resources/
│   ├── proxies.json       # Persistent proxy storage
│   ├── settings.json      # Application settings
│   ├── sources.txt        # 60+ proxy scrape URLs
│   ├── referers.txt       # Configurable HTTP referers
│   ├── favicon.ico        # Application icon
│   └── GeoLite2-City.mmdb # MaxMind GeoIP database (60MB)
├── requirements.txt       # Production dependencies
├── dev-requirements.txt   # Development tools (black, ruff, mypy, pytest)
├── pyproject.toml         # Black, Ruff, MyPy, Pytest configuration
├── build.py              # PyInstaller build script
└── todo.md               # Project roadmap & changelog
```

### Triple Engine Architecture

1. **Async Traffic Engine (Fast)** - `core/engine.py`
   - Uses `curl_cffi` to mimic real browser TLS signatures (Chrome, Safari, etc.)
   - Bypasses bot detection with TLS fingerprinting
   - High concurrency (500+ threads) with low overhead
   - Random impersonations: Chrome 120+, Safari 17+, Edge 120+

2. **Browser Engine (Realistic)** - `core/browser_engine.py`
   - Integrates Playwright (Chromium/Firefox)
   - Executes full JavaScript, handles dynamic content
   - Bypasses Cloudflare Turnstile, Akamai, hCaptcha, reCAPTCHA
   - Fingerprint randomization: Canvas, AudioContext, ClientRect, performance.now()
   - OS emulation profiles (Win/Mac/Linux × Chrome/Firefox/Safari/Edge)

3. **Stress Engine (Load Test)** - `core/stress_engine.py`
   - Authorized security testing using HTTP proxies
   - Attack types: HTTP Flood, Slowloris, RUDY, Randomized
   - Real-time stats: RPS, latency, success/fail rates
   - Safety: Confirmation dialogs, auto-stop limits

---

## Key Features & Implementation Details

### Proxy Management System

**File:** `core/proxy_manager.py` (ThreadedProxyManager class)

**Capabilities:**
- Scrapes 60+ proxy sources concurrently (10k+ proxies/min)
- Validates up to 10,000 proxies with 10,000 concurrent threads
- Protocols: HTTP, HTTPS, SOCKS4, SOCKS5 (with authentication)
- Multi-validator anonymity system (6 built-in validators)
- GeoIP integration: MaxMind local DB + ip-api.com fallback
- Persistence: Auto-save to `resources/proxies.json`
- Deduplication: Skips already-checked proxies during scrape

**Anonymity Classification:**
- **Elite:** No headers leaked, IP completely hidden
- **Anonymous:** Some headers leaked but IP hidden
- **Transparent:** Real IP exposed in headers
- **Unknown:** Could not determine (validator errors)

**Validators (configurable in Settings):**
1. `httpbin.org/get` - Headers, IP leak detection
2. `ip-api.com/json` - GeoIP + anonymity scoring
3. `api.ipify.org` - Simple IP check
4. `ipinfo.io/json` - IP + metadata
5. `azenv.net/api/info.php` - Advanced header analysis
6. `wtfismyip.com/json` - IP + anonymity

### Browser Fingerprinting

**File:** `core/browser_manager.py` (BrowserManager class)

**OS Emulation Profiles (6 total):**
- Windows 10 × Chrome/Firefox/Edge
- macOS Sonoma × Chrome/Safari/Firefox
- Ubuntu 22.04 × Chrome/Firefox

**Fingerprint Components:**
- Canvas: Randomized noise injection per session
- AudioContext: Floating-point noise in audio processing
- ClientRect: Micro-variations in element positioning
- WebGL: Vendor/Renderer string spoofing
- Performance: `performance.now()` jitter
- Navigator: OS-consistent platform, language, hardwareConcurrency

**Rotation Strategy:**
- Auto-rotate after 50 requests OR 30 minutes (configurable)
- Fresh fingerprint per browser context

### Cloudflare Bypass Strategy

**File:** `core/browser_engine.py` (PlaywrightTrafficEngine._bypass_cloudflare)

**4-Stage Approach:**
1. **JS Wait (10-30s):** Wait for JS challenge to auto-solve
2. **Human Simulation:** Mouse movements, scrolling, random delays
3. **Checkbox Click:** Extract sitekey from Turnstile iframe, click checkbox
4. **API Solve:** Fallback to 2Captcha/AntiCaptcha if configured

**Detection Markers (20+ signals):**
- Title: "Just a moment...", "Attention Required"
- Body text: "Checking your browser", "Cloudflare", "Ray ID"
- Elements: `#challenge-form`, `.cf-browser-verification`, Turnstile iframe

**Verification:**
- Checks for `cf_clearance` cookie
- Content analysis (absence of challenge markers)
- Double-verification after bypass before counting as success

### Traffic Pattern Randomization

**Features:**
- **Burst Mode:** Send N requests rapidly, then sleep (mimics human browsing sessions)
  - Configurable: 5-50 requests per burst, 1-30s sleep
- **Configurable Referers:** Load from `resources/referers.txt` with fallback defaults
- **View Time Randomization:** Random sleep between min/max duration (1-300s)

---

## UI/UX Architecture

**Framework:** CustomTkinter (dark theme, modern widgets)
**Layout:** Grid-based responsive design
**DPI Scaling:** All elements scale with display DPI (`ui/scaling.py`)

### Pages & Functionality

1. **Dashboard (`ui/pages/dashboard.py`)**
   - Traffic campaign controls (Start/Stop, Thread count, View time)
   - Engine mode selector (Fast/Browser)
   - Burst mode configuration
   - Real-time stats: Requests, Success, Failed, Active Proxies
   - Browser stats card (Browser type, Contexts)
   - Captcha stats card (Solved/Failed/Pending, Balances)
   - Protection stats card (CF/Akamai detected/bypassed)
   - Activity log with auto-scroll (resizable via DraggableSash)

2. **Proxy Manager (`ui/pages/proxy_manager.py`)**
   - Load from file, import from clipboard, scrape from 60+ sources
   - Test proxies (up to 10k concurrent threads)
   - VirtualGrid: High-performance grid (10k+ rows, 60fps scrolling)
   - Columns: IP, Port, Type, Country, City, Status, Speed, Anonymity
   - Filters: HTTP/HTTPS/SOCKS4/SOCKS5, Hide Dead
   - Export: All/HTTP/HTTPS/SOCKS (with protocol toggle)
   - GeoIP display: `[CC] City` format
   - Protocol color coding: HTTP (blue), HTTPS (purple), SOCKS4/5 (teal)
   - Persistence: Auto-save active proxies, restore on startup

3. **Stress Test (`ui/pages/stress_test.py`)**
   - Authorized security testing (confirmation dialog)
   - Attack types: HTTP Flood, Slowloris, RUDY, Randomized
   - HTTP method: GET/POST/HEAD/PUT/DELETE
   - Threads: 10-1000, Duration: 10-300s, RPS limit: 0-10000
   - Real-time stats: Requests, Success/Failed, RPS, Latency, Proxies Used
   - Activity log with auto-scroll (resizable)
   - HTTP-only (HTTPS not supported by HTTP proxies)

4. **Settings (`ui/pages/settings.py`)**
   - **Browser:** Auto-detect or manual path (Chrome/Chromium/Edge/Brave/Firefox)
   - **Contexts:** Max concurrent browser contexts (1-10)
   - **Stealth:** Enable/disable fingerprint randomization
   - **Captcha:** 2Captcha/AntiCaptcha API keys, primary provider, fallback
   - **Protection:** Cloudflare/Akamai bypass, auto-solve captcha
   - **Validators:** Enable/disable 6 validators, test depth (Quick/Normal/Thorough)

---

## Data Models & Configuration

**File:** `core/models.py`

### Key Data Classes

```python
@dataclass
class ProxyConfig:
    host: str
    port: int
    protocol: str  # "http", "socks4", "socks5"
    username: str = ""
    password: str = ""

@dataclass
class TrafficConfig:
    target_url: str
    max_threads: int
    total_visits: int  # 0 = infinite
    min_duration: int  # seconds
    max_duration: int
    headless: bool
    verify_ssl: bool
    engine_mode: EngineMode  # CURL or BROWSER
    browser: BrowserConfig
    captcha: CaptchaConfig
    protection: ProtectionBypassConfig
    burst_mode: bool = False
    burst_requests: int = 10
    burst_sleep_min: int = 2
    burst_sleep_max: int = 5

@dataclass
class ProxyCheckResult:
    proxy: ProxyConfig
    status: str  # "Active", "Dead", "Error"
    speed: int   # milliseconds
    type: str    # "HTTP", "HTTPS", "SOCKS4", "SOCKS5"
    country: str
    country_code: str
    city: str
    anonymity: str  # "Elite", "Anonymous", "Transparent", "Unknown"
    bytes_transferred: int
```

### Settings Storage

**File:** `resources/settings.json` (auto-saved on change)

**Managed by:** `ui/utils.py` (Utils.load_settings, Utils.save_settings)

**Key Settings:**
- `target_url`: Last campaign target
- `threads`, `viewtime_min`, `viewtime_max`: Traffic config
- `burst_mode`, `burst_requests`, `burst_sleep_max`: Burst config
- `engine_mode`: "curl" or "browser"
- `browser_selected`: "auto", "chrome", "chromium", "edge", "brave", "firefox"
- `browser_*_path`: Custom browser executable paths
- `captcha_primary`: "auto", "2captcha", "anticaptcha", "none"
- `captcha_2captcha_key`, `captcha_anticaptcha_key`: API keys
- `cloudflare_bypass`, `akamai_bypass`, `auto_solve_captcha`: Protection flags
- `validators_enabled`: Dict of validator name -> bool
- `validator_test_depth`: "quick", "normal", "thorough"
- `export_folder`: Last proxy export folder
- `export_with_protocol`: Include protocol prefix in exports

---

## Development Workflow & Tooling

### Virtual Environment

**CRITICAL:** Always activate `.venv` before running or building:

```bash
# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### Dependencies

**Production:**
```bash
pip install -r requirements.txt
playwright install chromium  # Required for Browser Engine
```

**Development:**
```bash
pip install -r dev-requirements.txt
```

**Key Libraries:**
- `customtkinter>=5.2.0` - Modern GUI framework
- `curl_cffi>=0.7.0` - TLS fingerprinting HTTP client
- `playwright>=1.40.0` - Browser automation
- `aiohttp>=3.9.0` - Async HTTP (captcha API)
- `geoip2>=4.8.0` - GeoIP lookups
- `fake-useragent>=1.4.0` - User-Agent generation

### Code Quality Tools

**Configuration:** `pyproject.toml`

**Black (Formatter):**
```bash
black ui/ core/ --line-length 88
```

**Ruff (Linter):**
```bash
ruff check ui/ core/ --fix
```

**MyPy (Type Checker):**
```bash
mypy ui/ core/ --ignore-missing-imports
```

**Pytest (Testing):**
```bash
pytest tests/ -v
```

### Building Executable

**Script:** `build.py` (PyInstaller wrapper)

```bash
python build.py
```

**Output:** `dist/DarkMatter-TB.exe` and `DarkMatterBot_v3.6.1.zip`

**Build Notes:**
- Enforces virtual environment activation
- Bundles all assets: resources/, GeoLite2 DB, favicon
- One-file mode: `--onefile --noconsole`
- Icon: `resources/favicon.ico`

---

## Important Coding Patterns & Conventions

### Thread Safety

**CRITICAL:** CustomTkinter is NOT thread-safe. Always use `self.after(0, callback)` when updating GUI from worker threads.

**Example:**
```python
def worker_thread():
    result = expensive_operation()
    # WRONG: self.label.configure(text=result)
    # RIGHT:
    self.after(0, lambda: self.label.configure(text=result))
```

**Logging Pattern:**
```python
def log_safe(self, msg):
    """Thread-safe logging - use this when calling from worker threads."""
    self.after(0, lambda: self.log(msg))
```

### Async Engine Pattern

**File:** `core/engine.py`, `core/browser_engine.py`, `core/stress_engine.py`

**Pattern:** Run async loop in separate thread, update GUI via callback:

```python
def run_async_engine(self):
    # Build config, prepare proxies
    config = TrafficConfig(...)
    engine = AsyncTrafficEngine(config, proxies, on_update=self.on_engine_update, on_log=self.log_safe)

    # Run async loop (blocks until complete)
    asyncio.run(engine.run())

    # Cleanup
    self.running = False
    self.after(0, lambda: self.btn_attack.configure(text="START", fg_color=COLORS["success"]))

def on_engine_update(self, stats: TrafficStats):
    """Callback from async engine - schedule on main GUI thread."""
    # Copy values to avoid race conditions
    req = stats.total_requests
    success = stats.success

    def update_on_main_thread():
        self.lbl_stats["req"].configure(text=str(req))
        self.lbl_stats["success"].configure(text=str(success))

    self.after(0, update_on_main_thread)
```

### DPI Scaling

**File:** `ui/scaling.py`

**Usage:** Wrap all pixel values with `scaled()`:

```python
from ui.scaling import scaled

# WRONG:
button = ctk.CTkButton(parent, width=120, height=36)

# RIGHT:
button = ctk.CTkButton(parent, width=scaled(120), height=scaled(36))
```

### URL Validation

**File:** `ui/utils.py`

**Usage:** Always validate user-provided URLs:

```python
from ui.utils import Utils

url = self.entry_url.get().strip()
if not Utils.validate_url(url):
    self.log("Invalid URL. Must start with http:// or https://")
    return
```

### Proxy Deduplication

**File:** `ui/utils.py`

**Usage:** Deduplicate by host:port (ignores protocol):

```python
from ui.utils import Utils

self.proxies = ["http://1.2.3.4:80", "https://1.2.3.4:80", "socks5://5.6.7.8:1080"]
self.proxies = Utils.deduplicate_proxies(self.proxies)
# Result: ["http://1.2.3.4:80", "socks5://5.6.7.8:1080"]
```

---

## Common Tasks & Workflows

### Adding a New Setting

1. **Add to settings.json structure** (manual or via Utils.save_settings)
2. **Create UI widget in settings page** (`ui/pages/settings.py`)
3. **Bind widget in `_bind_settings_widgets`** (`ui/app.py`)
4. **Save in `save_cfg`** (`ui/app.py` line 1789+)
5. **Load in `setup_pages`** (populate widget with saved value)

**Example:** Adding a new timeout setting:
```python
# In settings.py setup():
self.entry_my_timeout = ctk.CTkEntry(...)
self.entry_my_timeout.insert(0, str(app.settings.get("my_timeout", 5000)))

# In app.py _bind_settings_widgets():
self.entry_my_timeout = p.entry_my_timeout

# In app.py save_cfg():
self.settings["my_timeout"] = Utils.safe_int(self.entry_my_timeout.get(), default=5000, min_val=100, max_val=30000)
```

### Adding a New Validator

1. **Add validator definition in `core/validators.py`:**
```python
DEFAULT_VALIDATORS.append(
    ProxyValidator(
        name="MyValidator",
        url="https://example.com/api/json",
        enabled=True,  # Default enabled state
        checks_headers=True,
        provides_geo=True,
    )
)
```

2. **Add checkbox in Settings page** (`ui/pages/settings.py`):
```python
# In setup() -> Validators section:
chk_my_validator = ctk.CTkCheckBox(...)
self.validator_checkboxes["MyValidator"] = chk_my_validator
```

3. **No changes needed in save/load** (auto-handled by validator loop)

### Adding a New UI Page

1. **Create file** `ui/pages/my_page.py`:
```python
import customtkinter as ctk
from ui.scaling import scaled
from ui.styles import COLORS

class MyPage:
    def __init__(self, app):
        self.app = app

    def setup(self, parent):
        # Create widgets
        self.my_label = ctk.CTkLabel(parent, text="My Page")
        self.my_label.pack()
```

2. **Import in `ui/pages/__init__.py`:**
```python
from .my_page import MyPage
```

3. **Add to `ui/app.py` setup_pages():
```python
self.my_page = MyPage(self)
self.pages["my_page"] = ctk.CTkFrame(self, fg_color="transparent")
self.my_page.setup(self.pages["my_page"])
```

4. **Add navigation button in sidebar** (`ui/app.py` setup_sidebar)

---

## Testing & Debugging

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_validators.py -v

# Run with coverage
pytest tests/ --cov=core --cov=ui
```

### Common Issues & Solutions

**Issue:** GUI freezes during proxy testing
**Solution:** Ensure all GUI updates use `self.after(0, callback)`, throttle progress updates

**Issue:** "Proxy already checked" during scrape
**Solution:** Working as intended - deduplication based on `resources/proxies.json`

**Issue:** Browser engine fails with "Playwright not installed"
**Solution:** Run `playwright install chromium` after pip install

**Issue:** GeoIP shows "Unknown" for all proxies
**Solution:** Check `resources/GeoLite2-City.mmdb` exists (60MB file)

**Issue:** Export folder prompt every time
**Solution:** Folder selection is saved to `settings.json["export_folder"]`

**Issue:** VirtualGrid column resize breaks alignment
**Solution:** Fixed in v3.6.1 - ensure `VirtualGrid.flush()` called after resize

---

## Performance Optimization Notes

### VirtualGrid Optimization

**File:** `ui/components/virtual_grid.py`

**Key Optimizations:**
- Renders only visible rows (viewport-based)
- Deferred drawing: `add()` queues, `flush()` draws batch
- 60fps scrolling with 10k+ rows
- Column resize: Single redraw on mouse release

**Usage Pattern:**
```python
# SLOW (redraws after each add):
for item in items:
    grid.add(item)

# FAST (single draw at end):
for item in items:
    grid.add(item)  # Queued
grid.flush()  # Batch draw
```

### Proxy Checking Optimization

**Two-Phase Strategy:**
1. **Phase 1 (Alive Check):** Quick check (timeout 3s), just verify proxy responds
2. **Phase 2 (Validator Check):** Only run validators on alive proxies (saves bandwidth)

**Concurrency Scaling:**
- Low threads (<100): Update GUI every 10 items
- High threads (1000+): Update GUI every 500ms (time-based throttling)

### Traffic Engine Optimization

**Async Engine:**
- Connection pooling: Reuse TCP connections per session
- TLS session reuse: Cache TLS handshakes
- Proxy rotation: Unique proxy per task (no conflicts)

**Browser Engine:**
- Context pooling: Reuse browser contexts up to max_contexts
- Lazy browser launch: Start browser only when needed
- Context rotation: Destroy contexts after 50 requests

---

## Security & Legal Considerations

### Authorized Testing Only

**CRITICAL:** This tool is for authorized security testing, QA, and research ONLY.

**Stress Test Safeguards:**
- Confirmation dialog before starting
- Warning text: "AUTHORIZED TESTING ONLY"
- Auto-stop limits (duration, request count)
- HTTP-only (prevents accidental HTTPS flood)

**User Agreement:**
- README.md disclaimer
- Stress test confirmation dialog
- No default destructive settings

### Credential Handling

**Captcha API Keys:**
- Stored in plaintext in `resources/settings.json`
- WARNING: Not encrypted (local-only application)
- Best practice: Use low-balance accounts for testing

**Proxy Authentication:**
- Supported: `protocol://user:pass@host:port`
- Stored in memory only (not persisted)

---

## Version History & Changelog

See `todo.md` for detailed changelog.

**Recent Major Releases:**

- **v3.6.1 (2025-12-21):** Refactored UI into modular pages, added dev tooling (black/ruff/mypy), fixed 27 linting issues
- **v3.6.0 (2025-12-20):** Stress test engine, DPI scaling, draggable panels, burst mode, protocol color coding
- **v3.4.0:** Multi-validator anonymity system, proxy persistence, GeoIP integration
- **v3.2.0:** Browser fingerprinting, OS emulation, Cloudflare bypass improvements
- **v3.1.0:** Export system, clear dead proxies, activity log auto-scroll

---

## Current Status & Next Steps

### Active Development (See `todo.md`)

**In Progress:**
- Full proxy chaining (route checks through system proxy via SOCKS5 tunneling)

**Backlog:**
- Unit tests for validation functions
- Pre-commit hooks (black/ruff)
- Session cookie persistence
- Scenario mode (multi-page visit profiles)
- Source health tracking (auto-disable dead scrape sources)
- File-based logging with rotation
- Session export (CSV/JSON)

### Known Issues

All major issues resolved in v3.6.1. See `todo.md` "Known Issues (Resolved)" section.

---

## File References (Quick Navigation)

**Core Application:**
- `main.py` - Entry point
- `ui/app.py` - Main app class (1930 lines)
- `ui/pages/dashboard.py` - Traffic campaign UI
- `ui/pages/proxy_manager.py` - Proxy testing UI
- `ui/pages/stress_test.py` - Load testing UI
- `ui/pages/settings.py` - Configuration UI

**Core Logic:**
- `core/engine.py` - Fast async traffic engine
- `core/browser_engine.py` - Browser automation engine
- `core/stress_engine.py` - Stress testing engine
- `core/proxy_manager.py` - Proxy scraper & validator
- `core/validators.py` - IP validation endpoints
- `core/browser_manager.py` - Browser detection & fingerprinting
- `core/models.py` - Data models & enums

**Utilities:**
- `ui/utils.py` - Settings, validation, proxy dedup
- `ui/scaling.py` - DPI scaling helper
- `ui/styles.py` - Color scheme
- `ui/components/virtual_grid.py` - High-performance grid
- `ui/components/draggable_sash.py` - Resizable panels

**Configuration:**
- `resources/settings.json` - User settings
- `resources/proxies.json` - Persistent proxy storage
- `resources/sources.txt` - Proxy scrape sources
- `resources/referers.txt` - HTTP referers
- `pyproject.toml` - Dev tool configuration

---

## Tips for Claude Code

### When Making Changes

1. **Always read before editing** - Use Read tool to understand context
2. **Preserve thread safety** - Use `self.after(0, ...)` for GUI updates from threads
3. **Use DPI scaling** - Wrap pixel values with `scaled()`
4. **Validate user input** - Use `Utils.validate_url()`, `Utils.safe_int()`
5. **Update both UI and save logic** - Changes need widget + save_cfg + load
6. **Test with virtual environment active** - Critical for dependencies
7. **Run linters before commit** - `black ui/ core/` then `ruff check ui/ core/ --fix`

### Common Requests

**"Add a new setting"** → Follow "Adding a New Setting" workflow
**"Fix proxy issue"** → Check `core/proxy_manager.py` and `ui/pages/proxy_manager.py`
**"Improve UI"** → Check `ui/pages/*` and `ui/components/*`
**"Add validator"** → Check `core/validators.py` and Settings page
**"Debug threading issue"** → Look for missing `self.after(0, ...)` calls
**"Build executable"** → Run `python build.py` with `.venv` active

### Code Style Preferences

- **Line length:** 88 characters (Black default)
- **Imports:** Absolute imports, group stdlib/third-party/local
- **Typing:** Type hints for public methods (not strictly enforced)
- **Docstrings:** Optional for private methods, recommended for public API
- **Comments:** Explain "why" not "what", use inline for complex logic
- **Naming:** snake_case for functions/variables, PascalCase for classes

---

**Last Updated:** 2025-12-22
**Document Version:** 1.0
**For Claude Code Version:** All versions
