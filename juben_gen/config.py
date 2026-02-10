"""配置加载（Claude Only）。

目标：
- 配置文件只描述“用什么模型/是否启用 thinking、重试参数、输出开关”
- API Key 不落盘，统一通过环境变量 ANTHROPIC_API_KEY 提供
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


# ---------- 角色配置 ----------

# 5 个角色的默认模型配置（可在 config.json 覆盖）
ROLE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "bible": {"model": "claude-sonnet-4-20250514", "thinking": False},
    "plan": {"model": "claude-sonnet-4-20250514", "thinking": True, "budget_tokens": 10000},
    "write": {"model": "claude-sonnet-4-20250514", "thinking": False},
    "judge": {"model": "claude-haiku-4-20250414", "thinking": True, "budget_tokens": 10000},
    "rewrite": {"model": "claude-sonnet-4-20250514", "thinking": False},
}


@dataclass(frozen=True)
class RoleConfig:
    """单个角色的模型配置。"""

    model: str
    thinking: bool = False
    budget_tokens: int = 10000


# ---------- 通用配置 ----------


@dataclass(frozen=True)
class RetryConfig:
    """Claude API 调用重试参数（指数退避）。"""

    max_attempts: int = 3
    base_delay: float = 1.0


@dataclass(frozen=True)
class OutputConfig:
    """输出相关开关。"""

    save_intermediates: bool = True


@dataclass(frozen=True)
class AppConfig:
    roles: Dict[str, RoleConfig]
    retry: RetryConfig = field(default_factory=RetryConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def load_config(config_path: str) -> AppConfig:
    """读取配置文件（JSON）。缺失字段使用默认值。"""

    data = json.loads(Path(config_path).read_text(encoding="utf-8"))

    # roles
    roles_raw = data.get("roles", {}) or {}
    roles: Dict[str, RoleConfig] = {}
    for role, defaults in ROLE_DEFAULTS.items():
        raw = roles_raw.get(role, {}) or {}
        roles[role] = RoleConfig(
            model=str(raw.get("model", defaults["model"])),
            thinking=bool(raw.get("thinking", defaults.get("thinking", False))),
            budget_tokens=int(raw.get("budget_tokens", defaults.get("budget_tokens", 10000))),
        )

    # retry
    retry_raw = data.get("retry", {}) or {}
    retry = RetryConfig(
        max_attempts=int(retry_raw.get("max_attempts", RetryConfig.max_attempts)),
        base_delay=float(retry_raw.get("base_delay", RetryConfig.base_delay)),
    )
    if retry.max_attempts < 1:
        raise ValueError("config.retry.max_attempts 必须 >= 1")
    if retry.base_delay < 0:
        raise ValueError("config.retry.base_delay 必须 >= 0")

    # output
    output_raw = data.get("output", {}) or {}
    output = OutputConfig(save_intermediates=bool(output_raw.get("save_intermediates", True)))

    return AppConfig(roles=roles, retry=retry, output=output)


def load_role_configs(config_path: str) -> Dict[str, RoleConfig]:
    """兼容旧调用：只返回 roles。"""

    return load_config(config_path).roles


def default_config_path() -> str:
    """默认配置文件路径（juben_gen/config.json）。"""

    return str(Path(__file__).with_name("config.json"))


def maybe_load_config(config_path: Optional[str] = None) -> AppConfig:
    """尽量加载配置：优先用户传入，其次默认路径；都不存在则返回默认值。"""

    path = config_path or default_config_path()
    if Path(path).exists():
        return load_config(path)

    # 无配置文件时也可运行（使用默认配置）
    roles = {k: RoleConfig(**v) for k, v in ROLE_DEFAULTS.items()}
    return AppConfig(roles=roles)

