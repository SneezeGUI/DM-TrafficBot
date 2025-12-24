
import pytest
from ui.utils import Utils

class TestUtils:
    
    @pytest.mark.parametrize("url,expected", [
        ("https://google.com", True),
        ("http://test.local", True),
        ("google.com", False),
        ("ftp://server", False),
        ("", False),
        ("   https://trimmed.com   ", True),
    ])
    def test_validate_url(self, url, expected):
        assert Utils.validate_url(url) == expected

    @pytest.mark.parametrize("value,default,min_v,max_v,expected", [
        ("100", 0, 0, 1000, 100),   # Valid
        ("abc", 50, 0, 1000, 50),   # Invalid string -> default
        ("-10", 0, 0, 100, 0),      # Below min -> min
        ("2000", 0, 0, 100, 100),   # Above max -> max
        (None, 10, 0, 100, 10),     # None -> default
        (50, 0, 0, 100, 50),        # Int input -> int
    ])
    def test_safe_int(self, value, default, min_v, max_v, expected):
        assert Utils.safe_int(value, default, min_v, max_v) == expected

    def test_deduplicate_proxies(self):
        proxies = [
            "http://1.1.1.1:80",
            "socks5://1.1.1.1:80", # Different protocol, should be kept
            "http://2.2.2.2:80",
            "  http://2.2.2.2:80  ", # Duplicate with whitespace
            "https://3.3.3.3:443"
        ]
        
        result = Utils.deduplicate_proxies(proxies)
        
        # Should keep 1.1.1.1 (http), 1.1.1.1 (socks5), 2.2.2.2, 3.3.3.3
        assert len(result) == 4
        assert "http://1.1.1.1:80" in result
        assert "socks5://1.1.1.1:80" in result
        assert "http://2.2.2.2:80" in result
        assert "https://3.3.3.3:443" in result
