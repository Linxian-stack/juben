"""剧本生成模块 — 从节拍表逐集生成完整短剧剧本。

流程：
1. 加载节拍表 JSON
2. 逐集调用 Claude API（write 角色）
3. 第2集起注入前一集摘要保持连贯性
4. 双格式输出：TXT + DOCX
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .config import AppConfig, RoleConfig, maybe_load_config
from .docx_io import write_docx_lines
from .llm_clients import ClaudeClient, LLMResponse
from .prompts import build_system_prompt, load_fused_constraints, prompt_write_episode
from .rules import AdaptRules

logger = logging.getLogger(__name__)


def load_plan(plan_path: str | Path) -> List[Dict]:
    """读取节拍表 JSON 文件。"""
    p = Path(plan_path)
    if not p.exists():
        raise FileNotFoundError(f"节拍表 JSON 不存在：{p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"节拍表应为 JSON 数组，实际类型为 {type(data).__name__}")
    return data


def generate_episode(
    *,
    episode_plan: Dict,
    rules: AdaptRules,
    style_target: Dict,
    system_prompt: str,
    client: ClaudeClient,
    role_cfg: RoleConfig,
    prev_summary: str = "",
    sample_script: str = "",
) -> str:
    """生成单集剧本。

    Returns
    -------
    剧本纯文本。
    """
    ep_num = episode_plan.get("ep", "?")
    episode_plan_json = json.dumps(episode_plan, ensure_ascii=False, indent=2)

    user_msg = prompt_write_episode(
        rules=rules,
        style_target=style_target,
        episode_plan_json=episode_plan_json,
        prev_summary=prev_summary,
        sample_script=sample_script,
    )

    logger.info("生成第 %s 集剧本（模型=%s）", ep_num, role_cfg.model)
    response: LLMResponse = client.chat(
        model=role_cfg.model,
        system=system_prompt,
        messages=[{"role": "user", "content": user_msg}],
        thinking=role_cfg.thinking,
        budget_tokens=role_cfg.budget_tokens,
        max_tokens=8192,
    )

    script = response.text.strip()
    logger.info("第 %s 集剧本生成完成（%d 字符）", ep_num, len(script))
    return script


def generate_summary(
    *,
    episode_script: str,
    client: ClaudeClient,
    role_cfg: RoleConfig,
) -> str:
    """从剧本中提取关键摘要（角色状态、剧情进展、未解钩子），用于下一集连贯性注入。

    控制摘要长度不超过 500 字。
    """
    user_msg = (
        "【任务】从以下短剧剧本中提取关键摘要，用于下一集创作时保持连贯性。\n"
        "【要求】\n"
        "- 控制在500字以内\n"
        "- 必须包含：角色当前状态、剧情进展到哪一步、未解决的钩子/悬念\n"
        "- 简洁直接，不需要修辞\n"
        "【输出】直接输出摘要文本，不要加标题或解释。\n\n"
        f"【剧本】\n{episode_script}"
    )

    response: LLMResponse = client.chat(
        model=role_cfg.model,
        system="你是短剧创作助手，擅长提取剧情要点。",
        messages=[{"role": "user", "content": user_msg}],
        thinking=False,
        max_tokens=1024,
    )
    return response.text.strip()


def save_episode(
    script: str,
    ep_num: int,
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """保存单集剧本为 TXT 和 DOCX。

    Returns
    -------
    (txt_path, docx_path)
    """
    d = Path(output_dir) / "episodes"
    d.mkdir(parents=True, exist_ok=True)

    txt_path = d / f"ep{ep_num}.txt"
    txt_path.write_text(script, encoding="utf-8")

    docx_path = d / f"ep{ep_num}.docx"
    lines = script.split("\n")
    write_docx_lines(docx_path, lines, title=f"第{ep_num}集")

    logger.info("第 %d 集已保存：%s, %s", ep_num, txt_path, docx_path)
    return txt_path, docx_path


def save_full_script(
    episodes: List[str],
    output_dir: str | Path,
) -> tuple[Path, Path]:
    """保存合并版本（所有集拼接）为 TXT 和 DOCX。

    Returns
    -------
    (txt_path, docx_path)
    """
    d = Path(output_dir)
    d.mkdir(parents=True, exist_ok=True)

    full_text = "\n\n".join(episodes)

    txt_path = d / "script_full.txt"
    txt_path.write_text(full_text, encoding="utf-8")

    docx_path = d / "script_full.docx"
    lines = full_text.split("\n")
    write_docx_lines(docx_path, lines, title="完整剧本")

    logger.info("合并剧本已保存：%s, %s", txt_path, docx_path)
    return txt_path, docx_path


def generate_all_episodes(
    *,
    plan_path: str | Path,
    rules: AdaptRules,
    config: Optional[AppConfig] = None,
    constraints_path: str = "juben_gen/constraints.fused.json",
    output_dir: str | Path,
    sample_script: str = "",
) -> List[str]:
    """执行完整的逐集剧本生成流程。

    Parameters
    ----------
    plan_path : 节拍表 JSON 路径
    rules : 改编规则
    config : 应用配置，为 None 时使用默认配置
    constraints_path : 融合约束 JSON 路径
    output_dir : 输出目录
    sample_script : 样例剧本片段（few-shot），为空则跳过

    Returns
    -------
    所有集的剧本文本列表。
    """
    cfg = config or maybe_load_config()
    write_cfg: RoleConfig = cfg.roles["write"]

    # 1. 加载节拍表
    plan = load_plan(plan_path)
    logger.info("已加载节拍表：共 %d 集", len(plan))

    # 2. 加载融合约束
    constraints = None
    style_target: Dict = {}
    if Path(constraints_path).exists():
        constraints = load_fused_constraints(constraints_path)
        style_target = constraints.get("style_target", {})

    # 3. 构建 system prompt
    system = build_system_prompt(constraints=constraints)

    # 4. 创建客户端
    client = ClaudeClient(
        max_attempts=cfg.retry.max_attempts,
        base_delay=cfg.retry.base_delay,
    )

    # 5. 逐集生成
    episodes: List[str] = []
    prev_summary = ""

    for episode_plan in plan:
        ep_num = episode_plan.get("ep", len(episodes) + 1)

        # 生成剧本
        script = generate_episode(
            episode_plan=episode_plan,
            rules=rules,
            style_target=style_target,
            system_prompt=system,
            client=client,
            role_cfg=write_cfg,
            prev_summary=prev_summary,
            sample_script=sample_script,
        )
        episodes.append(script)

        # 保存分集文件
        save_episode(script, ep_num, output_dir)

        # 为下一集生成摘要
        if episode_plan != plan[-1]:
            prev_summary = generate_summary(
                episode_script=script,
                client=client,
                role_cfg=write_cfg,
            )
            logger.info("第 %s 集摘要已生成（%d 字符）", ep_num, len(prev_summary))

    # 6. 保存合并版本
    save_full_script(episodes, output_dir)

    logger.info("全部 %d 集剧本生成完成", len(episodes))
    return episodes
