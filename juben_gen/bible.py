"""Story Bible 生成模块 — 从小说片段提取结构化剧情圣经（JSON）。

流程：
1. 加载小说文件（TXT/DOCX）
2. 按章节拆分并选择指定范围
3. 调用 Claude API（bible 角色）生成 Story Bible
4. 解析并保存 Bible JSON
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from .config import AppConfig, RoleConfig, maybe_load_config
from .docx_io import read_docx_lines
from .llm_clients import ClaudeClient, LLMResponse
from .novel import Chapter, load_chapters, select_chapter_range, split_chapters
from .prompts import build_system_prompt, load_fused_constraints, prompt_story_bible
from .rules import AdaptRules
from .text_io import read_text_auto

logger = logging.getLogger(__name__)


def load_novel_text(path: str | Path) -> str:
    """根据后缀加载小说全文（TXT 或 DOCX）。"""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".docx":
        return "\n".join(read_docx_lines(p))
    # 默认按纯文本处理（.txt 及其他）
    return read_text_auto(p)


def extract_chapter_text(
    novel_path: str | Path,
    chapter_start: int,
    chapter_end: int,
) -> str:
    """加载小说并提取指定章节范围的文本。

    Returns
    -------
    拼接后的章节文本（含章节标题）。
    """
    full_text = load_novel_text(novel_path)
    chapters = split_chapters(full_text)
    if not chapters:
        logger.warning("未检测到章节标记（第N章），将使用全文")
        return full_text

    selected = select_chapter_range(chapters, chapter_start, chapter_end)
    if not selected:
        raise ValueError(
            f"章节范围 [{chapter_start}, {chapter_end}] 未匹配到任何章节。"
            f"可用范围：[{chapters[0].index}, {chapters[-1].index}]"
        )

    logger.info("已选择 %d 个章节（第%d章 ~ 第%d章）", len(selected), selected[0].index, selected[-1].index)
    return "\n\n".join(f"{ch.title}\n{ch.text}" for ch in selected)


def generate_bible(
    *,
    novel_path: str | Path,
    chapter_start: int,
    chapter_end: int,
    rules: AdaptRules,
    config: Optional[AppConfig] = None,
    constraints_path: str = "juben_gen/constraints.fused.json",
    sample_bible_json: str = "",
) -> Dict:
    """执行完整的 Story Bible 生成流程。

    Parameters
    ----------
    novel_path : 小说文件路径（TXT/DOCX）
    chapter_start, chapter_end : 章节范围（闭区间）
    rules : 改编规则（节奏/钩子/模板）
    config : 应用配置，为 None 时使用默认配置
    constraints_path : 融合约束 JSON 路径
    sample_bible_json : 样例 Bible JSON 字符串（few-shot），为空则跳过

    Returns
    -------
    解析后的 Bible dict。
    """
    cfg = config or maybe_load_config()
    role_cfg: RoleConfig = cfg.roles["bible"]

    # 1. 提取章节文本
    novel_excerpt = extract_chapter_text(novel_path, chapter_start, chapter_end)

    # 2. 加载融合约束（用于 system prompt）
    constraints = None
    if Path(constraints_path).exists():
        constraints = load_fused_constraints(constraints_path)

    # 3. 组装 prompt
    system = build_system_prompt(constraints=constraints)
    user_msg = prompt_story_bible(
        rules=rules,
        novel_excerpt=novel_excerpt,
        sample_bible_json=sample_bible_json,
    )

    # 4. 调用 Claude API
    client = ClaudeClient(
        max_attempts=cfg.retry.max_attempts,
        base_delay=cfg.retry.base_delay,
    )
    logger.info("调用 Claude API（bible 角色，模型=%s）", role_cfg.model)
    response: LLMResponse = client.chat(
        model=role_cfg.model,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
        thinking=role_cfg.thinking,
        budget_tokens=role_cfg.budget_tokens,
        max_tokens=8192,
    )

    # 5. 解析 JSON
    bible = _parse_bible_json(response.text)
    logger.info("Story Bible 生成完成：logline=%s", bible.get("logline", "")[:50])
    return bible


def save_bible(bible: Dict, output_path: str | Path) -> Path:
    """保存 Bible JSON 到文件。"""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(bible, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Bible JSON 已保存：%s", p)
    return p


def _parse_bible_json(text: str) -> Dict:
    """从 LLM 响应文本中提取 JSON。

    处理常见情况：
    - 纯 JSON 响应
    - 被 ```json ... ``` 包裹的响应
    """
    cleaned = text.strip()

    # 去除 markdown 代码块标记
    if cleaned.startswith("```"):
        # 找到第一个换行后的内容
        first_newline = cleaned.index("\n")
        last_fence = cleaned.rfind("```")
        if last_fence > first_newline:
            cleaned = cleaned[first_newline + 1:last_fence].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error("Bible JSON 解析失败：%s\n原始响应（前500字符）：%s", e, text[:500])
        raise ValueError(f"LLM 返回的内容无法解析为 JSON：{e}") from e
