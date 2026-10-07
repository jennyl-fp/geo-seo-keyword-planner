"""T1.2 驗收測試：has_* 布林；缺 env 不 raise（規格 §2 Adapter 表）。
債務#5：load_dotenv。"""

import os

from config import Config, load_config, load_dotenv


class TestMissingEnv:
    def test_empty_env_no_raise_all_off(self):
        cfg = load_config({})
        assert cfg.ahrefs_api_token is None
        assert cfg.gsc_credentials_path is None
        assert cfg.gsc_site_url is None
        assert cfg.gkp_mcp_command is None
        assert not cfg.has_ahrefs
        assert not cfg.has_gsc
        assert not cfg.has_gkp

    def test_blank_values_treated_as_missing(self):
        cfg = load_config(
            {
                "AHREFS_API_TOKEN": "   ",
                "GOOGLE_APPLICATION_CREDENTIALS": "\t",
                "GSC_SITE_URL": " ",
                "KEYWORD_PLANNER_MCP_COMMAND": "",
            }
        )
        assert not cfg.has_ahrefs
        assert not cfg.has_gsc
        assert not cfg.has_gkp

    def test_unknown_env_ignored(self):
        cfg = load_config({"TOTALLY_UNRELATED": "x"})
        assert cfg == Config()


class TestAhrefs:
    def test_token_present(self):
        cfg = load_config({"AHREFS_API_TOKEN": "tok-123"})
        assert cfg.has_ahrefs
        assert cfg.ahrefs_api_token == "tok-123"


class TestGsc:
    def test_credentials_only_not_enough(self):
        assert not load_config({"GOOGLE_APPLICATION_CREDENTIALS": "/sa.json"}).has_gsc

    def test_site_url_only_not_enough(self):
        assert not load_config({"GSC_SITE_URL": "https://example.com/"}).has_gsc

    def test_both_present(self):
        cfg = load_config(
            {
                "GOOGLE_APPLICATION_CREDENTIALS": "/sa.json",
                "GSC_SITE_URL": "https://example.com/",
            }
        )
        assert cfg.has_gsc


class TestGkp:
    def test_command_present(self):
        cfg = load_config({"KEYWORD_PLANNER_MCP_COMMAND": "uv run keyword-planner"})
        assert cfg.has_gkp
        assert cfg.gkp_mcp_command == "uv run keyword-planner"


class TestOsEnvironDefault:
    def test_reads_environ(self, monkeypatch):
        monkeypatch.setenv("AHREFS_API_TOKEN", "tok-live")
        assert load_config().has_ahrefs

    def test_environ_missing(self, monkeypatch):
        monkeypatch.delenv("AHREFS_API_TOKEN", raising=False)
        assert not load_config().has_ahrefs


class TestFirstpage:
    def test_token_present(self):
        cfg = load_config({"FIRSTPAGE_MCP_TOKEN": "bearer-xyz"})
        assert cfg.has_firstpage
        assert cfg.firstpage_token == "bearer-xyz"
        assert cfg.resolved_firstpage_url == "https://mcp.firstpage.com.hk/mcp/"

    def test_custom_url(self):
        cfg = load_config(
            {
                "FIRSTPAGE_MCP_TOKEN": "t",
                "FIRSTPAGE_MCP_URL": "http://localhost:9999/mcp",
            }
        )
        assert cfg.resolved_firstpage_url == "http://localhost:9999/mcp"

    def test_no_token_defaults(self):
        cfg = load_config({})
        assert not cfg.has_firstpage


class TestDeterminism:
    def test_same_env_same_config(self):
        env = {"AHREFS_API_TOKEN": "t", "GSC_SITE_URL": "https://a.hk/"}
        assert load_config(env) == load_config(env)


class TestLoadDotenv:
    def test_loads_and_respects_existing(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text(
            "# comment\n\nAHREFS_API_TOKEN=from-file\n"
            "GSC_SITE_URL=\"https://quoted.hk/\"\nINVALID_LINE\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("AHREFS_API_TOKEN", raising=False)
        monkeypatch.delenv("GSC_SITE_URL", raising=False)
        monkeypatch.setenv("KEYWORD_PLANNER_MCP_COMMAND", "keep-me")
        env_file.write_text(
            env_file.read_text(encoding="utf-8")
            + "\nKEYWORD_PLANNER_MCP_COMMAND=should-not-override\n",
            encoding="utf-8",
        )
        load_dotenv(env_file)
        assert os.environ["AHREFS_API_TOKEN"] == "from-file"
        assert os.environ["GSC_SITE_URL"] == "https://quoted.hk/"
        assert os.environ["KEYWORD_PLANNER_MCP_COMMAND"] == "keep-me"

    def test_missing_file_silent(self, tmp_path):
        load_dotenv(tmp_path / "nope.env")

    def test_ignores_lines_without_equals(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("just words\n# note\n", encoding="utf-8")
        before = dict(os.environ)
        load_dotenv(env_file)
        assert dict(os.environ) == before
