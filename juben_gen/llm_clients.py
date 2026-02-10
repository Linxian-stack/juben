"""Claude LLM 客户端 — 基于 anthropic SDK，支持 extended thinking 和自动重试。"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic

logger = logging.getLogger(__name__)

# ---------- 公共类型 ----------

Message = Dict[str, str]  # {"role": "user" | "assistant", "content": "..."}


@dataclass(frozen=True)
class LLMResponse:
    """统一的 LLM 响应。"""
    text: str
    thinking: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


# ---------- 角色配置 ----------

# 5 个角色的默认模型配置
ROLE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "bible":   {"model": "claude-sonnet-4-20250514",  "thinking": False},
    "plan":    {"model": "claude-sonnet-4-20250514",  "thinking": True, "budget_tokens": 10000},
    "write":   {"model": "claude-sonnet-4-20250514",  "thinking": False},
    "judge":   {"model": "claude-haiku-4-20250414",   "thinking": False},
    "rewrite": {"model": "claude-sonnet-4-20250514",  "thinking": False},
}


@dataclass(frozen=True)
class RoleConfig:
    """单个角色的模型配置。"""
    model: str
    thinking: bool = False
    budget_tokens: int = 10000


def load_role_configs(config_path: str) -> Dict[str, RoleConfig]:
    """从 config.json 读取角色配置，缺失的角色使用默认值。"""
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    roles_raw = data.get("roles", {})
    configs: Dict[str, RoleConfig] = {}
    for role, defaults in ROLE_DEFAULTS.items():
        raw = roles_raw.get(role, {})
        configs[role] = RoleConfig(
            model=raw.get("model", defaults["model"]),
            thinking=raw.get("thinking", defaults.get("thinking", False)),
            budget_tokens=raw.get("budget_tokens", defaults.get("budget_tokens", 10000)),
        )
    return configs


# ---------- Claude 客户端 ----------

# 可重试的异常类型
_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # 秒


class ClaudeClient:
    """基于 anthropic SDK 的 Claude 客户端。

    特性：
    - 通过 anthropic.Anthropic 调用 Messages API
    - 支持 extended thinking（budget_tokens）
    - 自动重试：3 次 + 指数退避（1s, 2s, 4s）
    - 仅捕获速率限制、网络错误和服务端错误

    环境变量：
    - ANTHROPIC_API_KEY（必须）
    - ANTHROPIC_BASE_URL（可选）
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 120.0,
    ) -> None:
        kwargs: Dict[str, Any] = {"timeout": timeout}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.Anthropic(**kwargs)

    def chat(
        self,
        *,
        model: str,
        system: str = "",
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        thinking: bool = False,
        budget_tokens: int = 10000,
    ) -> LLMResponse:
        """发送消息并返回响应，自动重试可恢复的错误。"""
        params: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
            "max_tokens": max_tokens,
        }
        if system:
            params["system"] = system

        if thinking:
            params["thinking"] = {"type": "enabled", "budget_tokens": budget_tokens}
            # extended thinking 模式下不支持 temperature
        else:
            params["temperature"] = temperature

        return self._call_with_retry(params)

    def _call_with_retry(self, params: Dict[str, Any]) -> LLMResponse:
        """带指数退避的重试逻辑。"""
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._client.messages.create(**params)
                return self._parse_response(response)
            except _RETRYABLE as e:
                last_error = e
                delay = _BASE_DELAY * (2 ** attempt)
                logger.warning("API 调用失败（第 %d 次），%s 秒后重试：%s", attempt + 1, delay, e)
                time.sleep(delay)
        raise RuntimeError(f"API 调用失败，已重试 {_MAX_RETRIES} 次：{last_error}") from last_error

    @staticmethod
    def _parse_response(response: anthropic.types.Message) -> LLMResponse:
        """从 API 响应中提取文本和思维链。"""
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "thinking":
                thinking_parts.append(block.thinking)
        return LLMResponse(
            text="".join(text_parts),
            thinking="".join(thinking_parts),
            raw=response.model_dump(),
        )
