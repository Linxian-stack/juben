"""Claude LLM 客户端 — 基于 anthropic SDK，支持 extended thinking 和自动重试。"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import anthropic

# 配置相关定义集中在 config.py；这里保留同名导出，避免外部调用断裂
from .config import RoleConfig, load_role_configs

logger = logging.getLogger(__name__)

# ---------- 公共类型 ----------

Message = Dict[str, str]  # {"role": "user" | "assistant", "content": "..."}


@dataclass(frozen=True)
class LLMResponse:
    """统一的 LLM 响应。"""
    text: str
    thinking: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

# ---------- Claude 客户端 ----------

# 可重试的异常类型
_RETRYABLE = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
)


class ClaudeClient:
    """基于 anthropic SDK 的 Claude 客户端。

    特性：
    - 通过 anthropic.Anthropic 调用 Messages API
    - 支持 extended thinking（budget_tokens）
    - 自动重试：max_attempts 次 + 指数退避（base_delay * 2^n）
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
        max_attempts: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts 必须 >= 1")
        if base_delay < 0:
            raise ValueError("base_delay 必须 >= 0")

        self._max_attempts = int(max_attempts)
        self._base_delay = float(base_delay)

        # 给出更可操作的错误信息（避免 anthropic SDK 抛出不直观的异常）
        if not api_key and not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "缺少 ANTHROPIC_API_KEY：请先在环境变量中设置 Claude API Key，或在代码中显式传入 api_key。"
            )

        base_url = base_url or os.getenv("ANTHROPIC_BASE_URL")

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
        for attempt in range(self._max_attempts):
            try:
                response = self._client.messages.create(**params)
                return self._parse_response(response)
            except _RETRYABLE as e:
                last_error = e
                if attempt >= self._max_attempts - 1:
                    break
                delay = self._base_delay * (2**attempt)
                logger.warning("API 调用失败（第 %d 次），%s 秒后重试：%s", attempt + 1, delay, e)
                time.sleep(delay)
        raise RuntimeError(f"API 调用失败，已尝试 {self._max_attempts} 次：{last_error}") from last_error

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
