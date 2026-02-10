"""节拍表规划模块 — 从 Story Bible 生成前10集分集节拍表（JSON 数组）。

流程：
1. 加载 Bible JSON
2. 加载融合约束（style_target + rules_text）
3. 调用 Claude API（plan 角色，启用 extended thinking）
4. 解析并保存节拍表 JSON 数组
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .config import AppConfig, RoleConfig, maybe_load_config
from .llm_clients import ClaudeClient, LLMResponse
from .prompts import (
    EpisodeSpec,
    build_system_prompt,
    load_fused_constraints,
    prompt_plan_first10,
)
from .rules import AdaptRules

logger = logging.getLogger(__name__)


def load_bible(bible_path: str | Path) -> Dict:
    """读取 Bible JSON 文件。"""
    p = Path(bible_path)
    if not p.exists():
        raise FileNotFoundError(f"Bible JSON 不存在：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def generate_plan(
    *,
    bible_path: str | Path,
    rules: AdaptRules,
    config: Optional[AppConfig] = None,
    constraints_path: str = "juben_gen/constraints.fused.json",
    episode_count: int = 10,
    sample_plan_json: str = "",
) -> List[Dict]:
    """执行完整的节拍表规划流程。

    Parameters
    ----------
    bible_path : Story Bible JSON 路径
    rules : 改编规则（节奏/钩子/模板）
    config : 应用配置，为 None 时使用默认配置
    constraints_path : 融合约束 JSON 路径
    episode_count : 规划集数（默认10集）
    sample_plan_json : 样例节拍表 JSON 字符串（few-shot），为空则跳过

    Returns
    -------
    节拍表列表（每集一个 dict）。
    """
    cfg = config or maybe_load_config()
    role_cfg: RoleConfig = cfg.roles["plan"]

    # 1. 加载 Bible
    bible = load_bible(bible_path)
    bible_json_str = json.dumps(bible, ensure_ascii=False, indent=2)
    logger.info("已加载 Bible：logline=%s", bible.get("logline", "")[:50])

    # 2. 加载融合约束
    constraints = None
    style_target: Dict = {}
    if Path(constraints_path).exists():
        constraints = load_fused_constraints(constraints_path)
        style_target = constraints.get("style_target", {})

    # 3. 组装 prompt
    system = build_system_prompt(constraints=constraints)
    user_msg = prompt_plan_first10(
        rules=rules,
        style_target=style_target,
        bible_json=bible_json_str,
        episode_spec=EpisodeSpec(),
        sample_plan_json=sample_plan_json,
    )

    # 4. 调用 Claude API（extended thinking）
    client = ClaudeClient(
        max_attempts=cfg.retry.max_attempts,
        base_delay=cfg.retry.base_delay,
    )
    logger.info(
        "调用 Claude API（plan 角色，模型=%s，thinking=%s）",
        role_cfg.model,
        role_cfg.thinking,
    )
    response: LLMResponse = client.chat(
        model=role_cfg.model,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
        thinking=role_cfg.thinking,
        budget_tokens=role_cfg.budget_tokens,
        max_tokens=16384,
    )

    if response.thinking:
        logger.info("Extended thinking 输出（前200字）：%s", response.thinking[:200])

    # 5. 解析 JSON 数组
    plan = _parse_plan_json(response.text)
    logger.info("节拍表生成完成：共 %d 集", len(plan))
    return plan


def save_plan(plan: List[Dict], output_path: str | Path) -> Path:
    """保存节拍表 JSON 到文件。"""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("节拍表 JSON 已保存：%s", p)
    return p


def _parse_plan_json(text: str) -> List[Dict]:
    """从 LLM 响应文本中提取 JSON 数组。

    处理常见情况：
    - 纯 JSON 数组响应
    - 被 ```json ... ``` 包裹的响应
    """
    cleaned = text.strip()

    # 去除 markdown 代码块标记
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        last_fence = cleaned.rfind("```")
        if last_fence > first_newline:
            cleaned = cleaned[first_newline + 1 : last_fence].strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(
            "节拍表 JSON 解析失败：%s\n原始响应（前500字符）：%s", e, text[:500]
        )
        raise ValueError(f"LLM 返回的内容无法解析为 JSON 数组：{e}") from e

    if not isinstance(result, list):
        raise ValueError(f"期望 JSON 数组，实际类型为 {type(result).__name__}")

    return result
