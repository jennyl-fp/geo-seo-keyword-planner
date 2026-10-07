"""環境配置讀取（T1.2）。

來源：GEO關鍵字研究工具-簡易版規格 v2 §2 Adapter 表 —
  Ahrefs: AHREFS_API_TOKEN（ADR-002 唯一付費源）
  GSC:    GOOGLE_APPLICATION_CREDENTIALS + GSC_SITE_URL（ADR-007）
          或 FIRSTPAGE_MCP_TOKEN 經 agency MCP（ADR-010，優先）
  GKP:    KEYWORD_PLANNER_MCP_COMMAND（ADR-006）

缺任何 env 不 raise：對應值為 None、has_* 為 False，
下游 client 據此降級並在報告聲明（ADR-004 offline-first）。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

AHREFS_TOKEN_ENV = "AHREFS_API_TOKEN"
GSC_CREDENTIALS_ENV = "GOOGLE_APPLICATION_CREDENTIALS"
GSC_SITE_ENV = "GSC_SITE_URL"
GKP_COMMAND_ENV = "KEYWORD_PLANNER_MCP_COMMAND"
FIRSTPAGE_TOKEN_ENV = "FIRSTPAGE_MCP_TOKEN"
FIRSTPAGE_URL_ENV = "FIRSTPAGE_MCP_URL"

FIRSTPAGE_DEFAULT_URL = "https://mcp.firstpage.com.hk/mcp/"


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


@dataclass(frozen=True)
class Config:
    ahrefs_api_token: str | None = None
    gsc_credentials_path: str | None = None
    gsc_site_url: str | None = None
    gkp_mcp_command: str | None = None
    firstpage_token: str | None = None
    firstpage_url: str | None = None

    @property
    def has_ahrefs(self) -> bool:
        return self.ahrefs_api_token is not None

    @property
    def has_gsc(self) -> bool:
        return self.gsc_credentials_path is not None and self.gsc_site_url is not None

    @property
    def has_gkp(self) -> bool:
        return self.gkp_mcp_command is not None

    @property
    def has_firstpage(self) -> bool:
        return self.firstpage_token is not None

    @property
    def resolved_firstpage_url(self) -> str:
        return self.firstpage_url or FIRSTPAGE_DEFAULT_URL


def load_dotenv(path: str | Path = ".env") -> None:
    """啟動時載入 .env（KEY=VALUE 行；# 註解略過；已存在的 env 不覆蓋；
    無檔案靜默）。零依賴（不引 python-dotenv），供 server.main 使用。"""
    env_file = Path(path)
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """由 env mapping（預設 os.environ）建構 Config；缺項永不 raise。"""
    source = os.environ if env is None else env
    return Config(
        ahrefs_api_token=_clean(source.get(AHREFS_TOKEN_ENV)),
        gsc_credentials_path=_clean(source.get(GSC_CREDENTIALS_ENV)),
        gsc_site_url=_clean(source.get(GSC_SITE_ENV)),
        gkp_mcp_command=_clean(source.get(GKP_COMMAND_ENV)),
        firstpage_token=_clean(source.get(FIRSTPAGE_TOKEN_ENV)),
        firstpage_url=_clean(source.get(FIRSTPAGE_URL_ENV)),
    )
