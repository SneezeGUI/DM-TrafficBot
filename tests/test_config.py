
import pytest
import os
import json
from ui.utils import Utils

class TestConfigLoading:
    
    @pytest.fixture
    def settings_file(self, tmp_path):
        """Create a temporary settings file."""
        file = tmp_path / "test_settings.json"
        data = {
            "target_url": "https://file-config.com",
            "threads": 10,
            "master_port": 8000
        }
        file.write_text(json.dumps(data))
        return str(file)

    def test_load_defaults(self, tmp_path):
        """Test loading defaults when file doesn't exist."""
        # Ensure no file exists
        file = str(tmp_path / "nonexistent.json")
        settings = Utils.load_settings(file)
        
        assert settings["target_url"] == "https://example.com"
        assert settings["threads"] == 5
        assert settings["mode"] == "standalone"

    def test_load_from_file(self, settings_file):
        """Test loading from a file."""
        settings = Utils.load_settings(settings_file)
        
        assert settings["target_url"] == "https://file-config.com"
        assert settings["threads"] == 10
        assert settings["master_port"] == 8000
        # Default should persist if not in file
        assert settings["mode"] == "standalone"

    def test_env_var_override(self, settings_file):
        """Test that environment variables override file settings."""
        # Set env vars
        os.environ["DM_MASTER_HOST"] = "10.0.0.5"
        os.environ["DM_MASTER_PORT"] = "9000" # Int override
        os.environ["DM_SLAVE_SECRET"] = "secret123"
        os.environ["DM_HEADLESS"] = "false" # Bool override (default is True)
        
        try:
            settings = Utils.load_settings(settings_file)
            
            # Env var overrides
            assert settings["master_host"] == "10.0.0.5"
            assert settings["master_port"] == 9000
            assert settings["slave_secret_key"] == "secret123"
            assert settings["headless"] is False
            
            # File settings persist if not overridden
            assert settings["target_url"] == "https://file-config.com"
            
        finally:
            # Cleanup env vars
            del os.environ["DM_MASTER_HOST"]
            del os.environ["DM_MASTER_PORT"]
            del os.environ["DM_SLAVE_SECRET"]
            del os.environ["DM_HEADLESS"]
