import re
import time
import logging
import os
import requests as std_requests
from typing import List, Callable, Optional, Set, Dict
from concurrent.futures import ThreadPoolExecutor
from curl_cffi import requests
from .header_manager import HeaderManager
from .models import ProxyConfig, ProxyCheckResult
from .constants import (
    SCRAPE_TIMEOUT_SECONDS,
    PROXY_CHECK_BATCH_SIZE,
    DEAD_PROXY_SPEED_MS,
)
from .validators import (
    DEFAULT_VALIDATORS,
    Validator,
    ValidatorResult,
    aggregate_results,
    AggregatedResult,
)

# GeoIP cache to avoid repeated lookups
_geoip_cache: Dict[str, dict] = {}

# MaxMind GeoLite2 database reader (lazy loaded)
_geoip_reader = None
_geoip_reader_initialized = False


def _init_geoip_reader():
    """
    Initialize the MaxMind GeoLite2-City database reader.
    Returns the reader or None if unavailable.
    """
    global _geoip_reader, _geoip_reader_initialized

    if _geoip_reader_initialized:
        return _geoip_reader

    _geoip_reader_initialized = True

    # Try to find the database file
    db_paths = [
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "resources",
            "GeoLite2-City.mmdb",
        ),
        os.path.join(
            os.path.dirname(__file__), "..", "resources", "GeoLite2-City.mmdb"
        ),
        "resources/GeoLite2-City.mmdb",
        "GeoLite2-City.mmdb",
    ]

    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break

    if not db_path:
        logging.info("GeoLite2-City.mmdb not found, will use API fallback for GeoIP")
        return None

    try:
        import geoip2.database

        _geoip_reader = geoip2.database.Reader(db_path)
        logging.info(f"GeoLite2-City database loaded from {db_path}")
        return _geoip_reader
    except ImportError:
        logging.warning(
            "geoip2 package not installed, will use API fallback. Run: pip install geoip2"
        )
        return None
    except Exception as e:
        logging.warning(f"Failed to load GeoLite2 database: {e}")
        return None


def _lookup_geoip_local(ip: str) -> Optional[dict]:
    """
    Look up geographic information using local MaxMind database.
    Returns dict or None if lookup fails.
    """
    reader = _init_geoip_reader()
    if not reader:
        return None

    try:
        response = reader.city(ip)
        return {
            "country": response.country.name or "Unknown",
            "countryCode": response.country.iso_code or "??",
            "city": response.city.name or "",
        }
    except Exception as e:
        # IP not found in database or other error (e.g., private IP ranges)
        logging.debug(f"GeoIP local lookup failed for {ip}: {type(e).__name__}")
        return None


def _lookup_geoip_api(ip: str) -> dict:
    """
    Look up geographic information using multiple API fallbacks.
    Tries multiple providers in sequence until one succeeds.
    Returns dict with country, countryCode, city.
    """
    default = {"country": "Unknown", "countryCode": "??", "city": ""}

    # Validate IP format (basic check)
    if not ip or ip in ("0.0.0.0", "127.0.0.1", "localhost"):
        return default

    # API 1: ip-api.com (free, 45 req/min) - HTTP only, fast
    try:
        resp = std_requests.get(
            f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,city",
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                logging.debug(
                    f"GeoIP ip-api.com success for {ip}: {data.get('country')}"
                )
                return {
                    "country": data.get("country", "Unknown"),
                    "countryCode": data.get("countryCode", "??"),
                    "city": data.get("city", ""),
                }
            else:
                logging.debug(
                    f"GeoIP ip-api.com returned status: {data.get('status')} for {ip}"
                )
        else:
            logging.debug(f"GeoIP ip-api.com HTTP {resp.status_code} for {ip}")
    except Exception as e:
        logging.debug(f"GeoIP ip-api.com failed for {ip}: {type(e).__name__}: {e}")

    # API 2: ipapi.co (free, 1000 req/day)
    try:
        resp = std_requests.get(
            f"https://ipapi.co/{ip}/json/",
            timeout=5,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            if not data.get("error"):
                logging.debug(
                    f"GeoIP ipapi.co success for {ip}: {data.get('country_name')}"
                )
                return {
                    "country": data.get("country_name", "Unknown"),
                    "countryCode": data.get("country_code", "??"),
                    "city": data.get("city", ""),
                }
            else:
                logging.debug(f"GeoIP ipapi.co error: {data.get('reason')} for {ip}")
        else:
            logging.debug(f"GeoIP ipapi.co HTTP {resp.status_code} for {ip}")
    except Exception as e:
        logging.debug(f"GeoIP ipapi.co failed for {ip}: {type(e).__name__}: {e}")

    # API 3: ipwhois.app (free, 10000 req/month)
    try:
        resp = std_requests.get(f"https://ipwhois.app/json/{ip}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("success", True):  # ipwhois returns success=false on error
                logging.debug(
                    f"GeoIP ipwhois.app success for {ip}: {data.get('country')}"
                )
                return {
                    "country": data.get("country", "Unknown"),
                    "countryCode": data.get("country_code", "??"),
                    "city": data.get("city", ""),
                }
            else:
                logging.debug(f"GeoIP ipwhois.app returned success=false for {ip}")
        else:
            logging.debug(f"GeoIP ipwhois.app HTTP {resp.status_code} for {ip}")
    except Exception as e:
        logging.debug(f"GeoIP ipwhois.app failed for {ip}: {type(e).__name__}: {e}")

    logging.warning(f"All GeoIP APIs failed for {ip}")
    return default


def lookup_geoip(ip: str) -> dict:
    """
    Look up geographic information for an IP address.

    Uses local MaxMind GeoLite2-City database for speed and no rate limits.
    Falls back to ip-api.com if database is unavailable.

    Results are cached to avoid repeated lookups.

    Returns dict with: country, countryCode, city
    """
    global _geoip_cache

    if ip in _geoip_cache:
        return _geoip_cache[ip]

    # Try local database first (fast, no rate limit)
    result = _lookup_geoip_local(ip)

    if result:
        logging.debug(f"GeoIP local DB success for {ip}: {result.get('country')}")
    else:
        # Fall back to API if local lookup failed
        logging.debug(f"GeoIP local DB miss for {ip}, trying API fallback")
        result = _lookup_geoip_api(ip)

    _geoip_cache[ip] = result
    return result


def detect_anonymity(response_data: dict, real_ip: str, proxy_ip: str) -> str:
    """
    Detect proxy anonymity level based on response headers and origin.

    Levels:
    - Elite (L1): No proxy detection, real IP completely hidden
    - Anonymous (L2): Proxy detected but real IP hidden
    - Transparent (L3): Real IP is exposed
    - Unknown: Cannot determine (response missing required fields)

    Args:
        response_data: JSON response from httpbin-like service (e.g., /get, /ip)
        real_ip: The user's real IP address
        proxy_ip: The proxy's IP address

    Returns:
        Anonymity level string

    Note:
        For accurate detection, use test URLs that return origin/headers like:
        - https://httpbin.org/get
        - https://httpbin.org/ip
        NOT https://httpbin.org/json (doesn't return needed fields)
    """
    # Check if response has the fields we need for detection
    origin = response_data.get("origin", "")
    headers = response_data.get("headers", {})

    # If response doesn't have origin OR headers, we can't reliably detect
    # This happens with endpoints like /json that don't return this data
    has_detection_data = bool(origin) or bool(headers)

    if not has_detection_data:
        return "Unknown"

    # If real IP appears in origin, it's transparent
    if real_ip and origin and real_ip in origin:
        return "Transparent"

    # Headers that expose real IP (Transparent)
    ip_exposing_headers = [
        "X-Forwarded-For",
        "X-Real-Ip",
        "X-Client-Ip",
        "Client-Ip",
        "Forwarded",
        "Cf-Connecting-Ip",
        "True-Client-Ip",
    ]

    for header in ip_exposing_headers:
        value = headers.get(header, "")
        if value:
            # Check if real IP is exposed
            if real_ip and real_ip in value:
                return "Transparent"
            # Header exists with some value but not our IP - Anonymous
            # (proxy is adding forwarding headers but hiding real IP)

    # Headers that indicate proxy usage (Anonymous)
    proxy_revealing_headers = [
        "Via",
        "X-Forwarded-For",
        "X-Proxy-Id",
        "Proxy-Connection",
        "X-Bluecoat-Via",
        "Proxy-Authenticate",
        "Proxy-Authorization",
    ]

    for header in proxy_revealing_headers:
        if headers.get(header):
            return "Anonymous"

    # Has detection data but no proxy indicators found - Elite
    if has_detection_data:
        return "Elite"

    return "Unknown"


class ThreadedProxyManager:
    def __init__(self):
        self.regex_pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b")

    def scrape(
        self,
        sources: List[str],
        protocols: List[str],
        max_threads: int = 20,
        scraper_proxy: str = None,
        on_progress: Callable[[int], None] = None,
    ) -> List[ProxyConfig]:
        """Scrapes proxies from provided source URLs using threads."""
        found_proxies: Set[tuple] = set()

        def fetch_source(url: str):
            try:
                # Use standard requests for speed (scraping text/html usually doesn't need TLS fingerprinting)
                # But we use rotating headers to avoid 403s
                h = HeaderManager.get_random_headers()
                proxies = (
                    {"http": scraper_proxy, "https": scraper_proxy}
                    if scraper_proxy
                    else None
                )

                response = std_requests.get(
                    url, timeout=SCRAPE_TIMEOUT_SECONDS, headers=h, proxies=proxies
                )
                if response.status_code == 200:
                    if on_progress:
                        on_progress(len(response.content))
                    matches = self.regex_pattern.findall(response.text)

                    # Smart Protocol Detection
                    u_lower = url.lower()
                    source_protos = []

                    # Heuristics based on URL hints
                    if "socks5" in u_lower:
                        source_protos.append("socks5")
                    if "socks4" in u_lower:
                        source_protos.append("socks4")
                    if "http" in u_lower and "socks" not in u_lower:
                        source_protos.append("http")

                    # Intersect with user requests
                    valid_protos = [p for p in source_protos if p in protocols]

                    # Fallback: If no specific protocol detected, try all requested
                    if not valid_protos:
                        valid_protos = protocols

                    for m in matches:
                        ip, port = m.split(":")
                        for proto in valid_protos:
                            found_proxies.add((ip, int(port), proto))
            except Exception as e:
                logging.debug(f"Error scraping {url}: {e}")

        with ThreadPoolExecutor(max_workers=max_threads) as ex:
            ex.map(
                fetch_source,
                [url for url in sources if url.strip() and not url.startswith("#")],
            )

        results = []
        for ip, port, proto in found_proxies:
            results.append(ProxyConfig(host=ip, port=port, protocol=proto))

        return results

    def check_proxies(
        self,
        proxies: List[ProxyConfig],
        target_url: str,
        timeout_ms: int,
        real_ip: str,
        on_progress: Callable[[ProxyCheckResult, int, int], None],
        concurrency: int = 100,
        pause_checker: Optional[Callable[[], bool]] = None,
        validators: Optional[List[Validator]] = None,
        test_depth: str = "quick",
    ) -> List[ProxyCheckResult]:
        """
        Checks a list of proxies concurrently using threads.
        """
        total = len(proxies)
        completed = 0
        valid_results = []
        lock = logging.threading.Lock()  # Simple lock for counter

        # Determine which validators to use based on test_depth
        active_validators = []
        if validators:
            enabled = [v for v in validators if v.enabled]
            if test_depth == "quick":
                active_validators = enabled[:1] if enabled else []
            elif test_depth == "normal":
                active_validators = enabled[:3] if enabled else []
            else:  # thorough
                active_validators = enabled

        def check_single(proxy: ProxyConfig):
            nonlocal completed

            # Pause logic
            if pause_checker:
                while pause_checker():
                    time.sleep(0.5)

            result = self._test_proxy(
                proxy, target_url, timeout_ms, real_ip, active_validators
            )

            with lock:
                completed += 1
                current_completed = completed

            if on_progress:
                on_progress(result, current_completed, total)

            if result.status == "Active":
                return result
            return None

        valid_results_list = []
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = []

            # Scale batch size with concurrency (min 50, max 500, ~10% of threads)
            batch_size = max(PROXY_CHECK_BATCH_SIZE, min(500, concurrency // 10))
            # Reduce sleep for high concurrency
            batch_sleep = (
                0.05 if concurrency <= 500 else 0.02 if concurrency <= 2000 else 0.01
            )

            # Staggered Launch to prevent UI freeze
            for i in range(0, len(proxies), batch_size):
                batch = proxies[i : i + batch_size]
                for p in batch:
                    futures.append(ex.submit(check_single, p))

                # Check pause during submission
                if pause_checker:
                    while pause_checker():
                        time.sleep(0.5)

                # Small sleep to yield CPU
                time.sleep(batch_sleep)

            for f in futures:
                res = f.result()
                if res:
                    valid_results_list.append(res)

        return valid_results_list

    def _test_proxy_alive(
        self, proxy: ProxyConfig, target_url: str, timeout_ms: int
    ) -> ProxyCheckResult:
        """
        Phase 1: Quick alive check - tests connectivity, speed, type, and GeoIP.
        Does NOT run validator API checks (saves bandwidth for dead proxies).
        """
        result = ProxyCheckResult(
            proxy=proxy,
            status="Dead",
            speed=DEAD_PROXY_SPEED_MS,
            type=proxy.protocol.upper(),
            country="Unknown",
            country_code="??",
            city="",
            anonymity="Unknown",  # Will be set in phase 2
        )

        proxy_url = proxy.to_curl_cffi_format()
        proxies_dict = {"http": proxy_url, "https": proxy_url}
        timeout_sec = max(timeout_ms / 1000, 1.0)

        bytes_transferred = 0
        is_https = target_url.lower().startswith("https://")

        start_time = time.time()
        try:
            with requests.Session(impersonate="chrome120") as session:
                resp = session.get(
                    target_url, timeout=timeout_sec, proxies=proxies_dict, verify=False
                )

                latency = int((time.time() - start_time) * 1000)
                result.speed = latency
                result.status = "Active"

                # Calculate bytes transferred
                request_overhead = 500
                response_headers = 300
                response_body = len(resp.content) if resp.content else 0
                tls_overhead = 5000 if is_https else 0
                proxy_connect = 200 if is_https else 0
                bytes_transferred = (
                    request_overhead
                    + response_headers
                    + response_body
                    + tls_overhead
                    + proxy_connect
                )

                # Type detection
                if is_https and result.type == "HTTP":
                    result.type = "HTTPS"

                # HTTPS tunneling test for HTTP proxies
                if not is_https and result.type == "HTTP":
                    https_capable = self._test_https_tunnel(
                        session, proxies_dict, timeout_sec
                    )
                    if https_capable:
                        result.type = "HTTPS"
                        bytes_transferred += 2000
                        logging.debug(
                            f"Proxy {proxy.host}:{proxy.port} upgraded to HTTPS (tunnel test passed)"
                        )

                # Extract exit IP for GeoIP
                proxy_exit_ip = None
                try:
                    response_data = resp.json()
                    origin = response_data.get("origin", "")
                    if origin:
                        proxy_exit_ip = origin.split(",")[0].strip()
                        logging.debug(
                            f"Proxy {proxy.host}:{proxy.port} exit IP: {proxy_exit_ip}"
                        )
                except (ValueError, KeyError, AttributeError) as e:
                    logging.debug(f"Failed to extract exit IP from response: {e}")

                # GeoIP lookup - try exit IP first, fallback to proxy host IP
                lookup_ip = proxy_exit_ip or proxy.host
                if lookup_ip:
                    geo = lookup_geoip(lookup_ip)
                    result.country = geo.get("country", "Unknown")
                    result.country_code = geo.get("countryCode", "??")
                    result.city = geo.get("city", "")
                    if result.country == "Unknown":
                        logging.debug(f"GeoIP lookup failed for {lookup_ip}")

                # Store exit IP for phase 2 validator checks
                result._exit_ip = proxy_exit_ip

                result.bytes_transferred = bytes_transferred

                # Base score (will be adjusted in phase 2 with anonymity factor)
                result.score = round(1000.0 / max(latency, 1), 2)
                proxy.score = result.score

        except Exception as e:
            logging.debug(
                f"Proxy {proxy.host}:{proxy.port} failed: {type(e).__name__}: {e}"
            )
            result.bytes_transferred = 1500 if is_https else 500

        return result

    def _test_proxy_anonymity(
        self,
        result: ProxyCheckResult,
        real_ip: str,
        timeout_ms: int,
        validators: List[Validator],
    ) -> ProxyCheckResult:
        """
        Phase 2: Anonymity check - runs validator API checks on confirmed-alive proxies.
        Only called for proxies that passed the alive check.
        """
        if result.status != "Active":
            return result

        proxy = result.proxy
        proxy_url = proxy.to_curl_cffi_format()
        proxies_dict = {"http": proxy_url, "https": proxy_url}
        timeout_sec = max(timeout_ms / 1000, 1.0)

        proxy_exit_ip = getattr(result, "_exit_ip", None)
        bytes_transferred = result.bytes_transferred

        try:
            with requests.Session(impersonate="chrome120") as session:
                if validators and len(validators) > 0:
                    # Run multi-validator test
                    validator_results, validator_bytes = self._run_validators(
                        session, proxy, proxies_dict, validators, timeout_sec, real_ip
                    )
                    bytes_transferred += validator_bytes

                    aggregated = aggregate_results(
                        validator_results,
                        real_ip,
                        proxy_exit_ip=proxy_exit_ip or "",
                        proxy_worked=True,
                    )
                    result.anonymity = aggregated.anonymity_level
                    anon_score_factor = max(0.5, aggregated.anonymity_score / 100.0)
                else:
                    # Fallback to simple detection using IP comparison
                    if proxy_exit_ip and real_ip:
                        if proxy_exit_ip == real_ip:
                            result.anonymity = "Transparent"
                            anon_score_factor = 0.5
                        else:
                            result.anonymity = "Anonymous"
                            anon_score_factor = 1.0
                    else:
                        result.anonymity = "Anonymous"
                        anon_score_factor = 0.8

                # Update bytes and score with anonymity factor
                result.bytes_transferred = bytes_transferred
                base_score = 1000.0 / max(result.speed, 1)
                result.score = round(base_score * anon_score_factor, 2)
                proxy.score = result.score

        except Exception as e:
            logging.debug(
                f"Anonymity check failed for {proxy.host}:{proxy.port}: {type(e).__name__}: {e}"
            )
            # Keep the proxy as Active but with Unknown anonymity
            result.anonymity = "Unknown"

        return result

    def _test_proxy(
        self,
        proxy: ProxyConfig,
        target_url: str,
        timeout_ms: int,
        real_ip: str,
        validators: Optional[List[Validator]] = None,
    ) -> ProxyCheckResult:
        """
        Full proxy test: Phase 1 (alive) + Phase 2 (anonymity) combined.
        Validators only run if proxy passes alive check.
        """
        # Phase 1: Quick alive check
        result = self._test_proxy_alive(proxy, target_url, timeout_ms)

        # Phase 2: Only check anonymity if proxy is alive
        if result.status == "Active" and validators:
            result = self._test_proxy_anonymity(result, real_ip, timeout_ms, validators)
        elif result.status == "Active":
            # No validators - use simple anonymity detection
            proxy_exit_ip = getattr(result, "_exit_ip", None)
            if proxy_exit_ip and real_ip:
                if proxy_exit_ip == real_ip:
                    result.anonymity = "Transparent"
                    anon_score_factor = 0.5
                else:
                    result.anonymity = "Anonymous"
                    anon_score_factor = 1.0
            else:
                result.anonymity = "Anonymous"
                anon_score_factor = 0.8

            # Adjust score with anonymity factor
            base_score = 1000.0 / max(result.speed, 1)
            result.score = round(base_score * anon_score_factor, 2)
            proxy.score = result.score

        return result

    def _run_validators(
        self,
        session,
        proxy: ProxyConfig,
        proxies_dict: dict,
        validators: List[Validator],
        timeout_sec: float,
        real_ip: str,
    ) -> tuple:
        """
        Run multiple validators against a proxy and collect results.
        Returns (List[ValidatorResult], total_bytes_transferred)
        """
        results = []
        total_bytes = 0

        for validator in validators:
            is_https = validator.url.lower().startswith("https://")
            try:
                start = time.time()
                resp = session.get(
                    validator.url,
                    timeout=min(timeout_sec, validator.timeout),
                    proxies=proxies_dict,
                    verify=False,
                )
                elapsed_ms = int((time.time() - start) * 1000)

                # Calculate bytes for this validator request
                request_overhead = 500
                response_headers = 300
                response_body = len(resp.content) if resp.content else 0
                # TLS overhead only for first HTTPS request in session (session reuse)
                # Subsequent HTTPS requests reuse connection, so minimal TLS overhead
                tls_overhead = (
                    500 if is_https else 0
                )  # Session reuse = smaller overhead
                total_bytes += (
                    request_overhead + response_headers + response_body + tls_overhead
                )

                vr = validator.parse_response(resp.text, resp.status_code, real_ip)
                vr.response_time_ms = elapsed_ms
                results.append(vr)

            except Exception as e:
                # Validator failed - record failure
                results.append(
                    ValidatorResult(
                        validator_name=validator.name, success=False, error=str(e)
                    )
                )
                # Failed request still used some bandwidth
                total_bytes += 800 if is_https else 300

        return results, total_bytes

    def _test_https_tunnel(
        self, session, proxies_dict: dict, timeout_sec: float
    ) -> bool:
        """
        Test if an HTTP proxy can tunnel HTTPS traffic (CONNECT method).

        This is critical for browser mode which requires HTTPS tunneling.
        HTTP proxies that can't tunnel HTTPS will fail on HTTPS sites.

        Uses a fast, reliable HTTPS endpoint for the test.

        Returns:
            True if proxy supports HTTPS tunneling, False otherwise
        """
        # Use a simple, fast HTTPS endpoint for the test
        # ipify is lightweight and reliable
        https_test_urls = [
            "https://api.ipify.org?format=json",
            "https://httpbin.org/ip",
        ]

        for test_url in https_test_urls:
            try:
                resp = session.get(
                    test_url,
                    timeout=min(timeout_sec, 5.0),  # Max 5s for quick test
                    proxies=proxies_dict,
                    verify=False,
                )
                if resp.status_code == 200:
                    return True
            except Exception:
                # Try next URL
                continue

        return False
