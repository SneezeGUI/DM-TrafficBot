
import pytest
import json
from dataclasses import asdict
from core.models import (
    TrafficConfig, 
    ProxyConfig, 
    BrowserConfig, 
    CaptchaConfig, 
    ProtectionBypassConfig, 
    EngineMode,
    CaptchaProvider
)

def test_proxy_config_serialization():
    """Test that ProxyConfig can be serialized/deserialized correctly."""
    proxy = ProxyConfig(
        host="127.0.0.1",
        port=8080,
        protocol="socks5",
        username="user",
        password="pass"
    )
    
    # Simulate network transmission (JSON)
    data = asdict(proxy)
    json_str = json.dumps(data)
    loaded_data = json.loads(json_str)
    
    reconstructed = ProxyConfig(**loaded_data)
    
    assert reconstructed.host == "127.0.0.1"
    assert reconstructed.port == 8080
    assert reconstructed.protocol == "socks5"
    assert reconstructed.username == "user"
    assert reconstructed.password == "pass"

def test_proxy_config_curl_format():
    """Test the to_curl_cffi_format method."""
    # Auth
    p1 = ProxyConfig(host="1.1.1.1", port=80, protocol="http", username="user", password="pass")
    assert p1.to_curl_cffi_format() == "http://user:pass@1.1.1.1:80"
    
    # No Auth
    p2 = ProxyConfig(host="1.1.1.1", port=80, protocol="socks5")
    assert p2.to_curl_cffi_format() == "socks5://1.1.1.1:80"

def test_traffic_config_defaults():
    """Test TrafficConfig initialization with minimal args."""
    # Setup nested configs
    browser_cfg = BrowserConfig(fingerprint_rotation_enabled=True)
    captcha_cfg = CaptchaConfig(primary_provider=CaptchaProvider.NONE)
    protection_cfg = ProtectionBypassConfig(cloudflare_enabled=False)
    
    config = TrafficConfig(
        target_url="https://example.com",
        max_threads=50,
        total_visits=0,
        min_duration=10,
        max_duration=30,
        headless=True,
        verify_ssl=False,
        engine_mode=EngineMode.CURL,
        browser=browser_cfg,
        captcha=captcha_cfg,
        protection=protection_cfg
    )
    
    assert config.target_url == "https://example.com"
    assert config.max_threads == 50
    assert config.engine_mode == EngineMode.CURL
    assert config.browser.fingerprint_rotation_enabled is True
