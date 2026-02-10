"""审稿评分模块 — 对单集剧本做量化打分与可执行修改清单。

流程：
1. 加载单集剧本文本 + 节拍表对应集
2. 调用 Claude API（judge 角色，启用 extended thinking）
3. 解析并保存评分 JSON
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .config import AppConfig, RoleConfig, maybe_load_config
from .llm_clients import ClaudeClient, LLMResponse
from .prompts import build_system_prompt, load_fused_constraints, prompt_judge_episode
from .rules import AdaptRules

logger = logging.getLogger(__name__)

# 默认通过阈值：overall >= 75
DEFAULT_PASS_THRESHOLD = 75.0


def judge_episode(
    *,
    episode_script: str,
    episode_plan: Optional[Dict] = None,
    rules: AdaptRules,
    config: Optional[AppConfig] = None,
    constraints_path: str = "juben_gen/constraints.fused.json",
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
) -> Dict:
    """对单集剧本做审稿评分。

    Parameters
    ----------
    episode_script : 单集剧本纯文本
    episode_plan : 节拍表中该集的规划 dict（可选，提供时加入评审上下文）
    rules : 改编规则（节奏/钩子/模板）
    config : 应用配置，为 None 时使用默认配置
    constraints_path : 融合约束 JSON 路径
    pass_threshold : 通过阈值（overall >= 此值为通过）

    Returns
    -------
    评分结果 dict，包含 scores / issues / pass 等字段。
    """
    cfg = config or maybe_load_config()
    role_cfg: RoleConfig = cfg.roles["judge"]

    # 1. 加载融合约束
    constraints = None
    style_target: Dict = {}
    if Path(constraints_path).exists():
        constraints = load_fused_constraints(constraints_path)
        style_target = constraints.get("style_target", {})

    # 2. 组装 prompt
    system = build_system_prompt(constraints=constraints)

    # 如果有节拍表规划，追加到剧本文本前面作为上下文
    script_with_context = episode_script
    if episode_plan:
        plan_text = json.dumps(episode_plan, ensure_ascii=False, indent=2)
        script_with_context = (
            f"【本集节拍表规划（评审参考）】\n{plan_text}\n\n"
            f"【剧本正文】\n{episode_script}"
        )

    user_msg = prompt_judge_episode(
        rules=rules,
        episode_script=script_with_context,
        style_target=style_target or None,
    )

    # 3. 调用 Claude API（extended thinking）
    client = ClaudeClient(
        max_attempts=cfg.retry.max_attempts,
        base_delay=cfg.retry.base_delay,
    )
    logger.info(
        "调用 Claude API（judge 角色，模型=%s，thinking=%s）",
        role_cfg.model,
        role_cfg.thinking,
    )
    response: LLMResponse = client.chat(
        model=role_cfg.model,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
        thinking=role_cfg.thinking,
        budget_tokens=role_cfg.budget_tokens,
        max_tokens=8192,
    )

    if response.thinking:
        logger.info("Extended thinking 输出（前200字）：%s", response.thinking[:200])

    # 4. 解析评分 JSON
    review = _parse_review_json(response.text)

    # 5. 计算 overall 分数和通过判定
    review = _enrich_review(review, pass_threshold)

    ep = review.get("episode", "?")
    overall = review.get("scores", {}).get("overall", 0)
    passed = review.get("pass", False)
    logger.info("第 %s 集审稿完成：overall=%.1f, pass=%s", ep, overall, passed)

    return review


def save_review(review: Dict, output_dir: str | Path, ep_num: int) -> Path:
    """保存评分 JSON 到 {output_dir}/reviews/ep{N}_review.json。"""
    d = Path(output_dir) / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"ep{ep_num}_review.json"
    p.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("评分 JSON 已保存：%s", p)
    return p


def judge_all_episodes(
    *,
    episodes_dir: str | Path,
    plan_path: Optional[str | Path] = None,
    rules: AdaptRules,
    config: Optional[AppConfig] = None,
    constraints_path: str = "juben_gen/constraints.fused.json",
    output_dir: str | Path,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
) -> List[Dict]:
    """对所有已生成的剧本逐集评分。

    Parameters
    ----------
    episodes_dir : 剧本目录（含 ep1.txt, ep2.txt, ...）
    plan_path : 节拍表 JSON 路径（可选，提供时加入评审上下文）
    rules : 改编规则
    config : 应用配置
    constraints_path : 融合约束 JSON 路径
    output_dir : 输出目录（评分文件保存到 {output_dir}/reviews/）
    pass_threshold : 通过阈值

    Returns
    -------
    所有集的评分结果列表。
    """
    ep_dir = Path(episodes_dir)
    if not ep_dir.exists():
        raise FileNotFoundError(f"剧本目录不存在：{ep_dir}")

    # 收集所有 epN.txt 文件，按集号排序
    ep_files = sorted(ep_dir.glob("ep*.txt"), key=lambda f: _extract_ep_num(f.name))
    if not ep_files:
        raise FileNotFoundError(f"剧本目录中未找到 ep*.txt 文件：{ep_dir}")

    # 可选加载节拍表
    plan: List[Dict] = []
    if plan_path and Path(plan_path).exists():
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))

    reviews: List[Dict] = []
    for ep_file in ep_files:
        ep_num = _extract_ep_num(ep_file.name)
        script = ep_file.read_text(encoding="utf-8")

        # 匹配节拍表中对应集
        episode_plan = _find_episode_plan(plan, ep_num)

        review = judge_episode(
            episode_script=script,
            episode_plan=episode_plan,
            rules=rules,
            config=config,
            constraints_path=constraints_path,
            pass_threshold=pass_threshold,
        )
        review["episode"] = ep_num

        save_review(review, output_dir, ep_num)
        reviews.append(review)

    # 汇总统计
    passed_count = sum(1 for r in reviews if r.get("pass", False))
    logger.info(
        "全部 %d 集评分完成：%d 通过 / %d 未通过",
        len(reviews),
        passed_count,
        len(reviews) - passed_count,
    )

    return reviews


def _parse_review_json(text: str) -> Dict:
    """从 LLM 响应文本中提取评分 JSON。"""
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
            "评分 JSON 解析失败：%s\n原始响应（前500字符）：%s", e, text[:500]
        )
        raise ValueError(f"LLM 返回的内容无法解析为 JSON：{e}") from e

    if not isinstance(result, dict):
        raise ValueError(f"期望 JSON 对象，实际类型为 {type(result).__name__}")

    return result


def _enrich_review(review: Dict, pass_threshold: float) -> Dict:
    """计算 overall 分数和通过判定。

    overall = 9个维度分数的均值，映射到 0-100 分制（原始 0-5 × 20）。
    """
    scores = review.get("scores", {})

    # 9个维度
    dimensions = [
        "open_hook", "core_conflict", "turn", "highlight",
        "rhythm", "character", "shootable", "end_hook", "safety",
    ]
    raw_scores = [scores.get(d, 0) for d in dimensions]
    valid_scores = [s for s in raw_scores if isinstance(s, (int, float))]

    if valid_scores:
        avg_raw = sum(valid_scores) / len(valid_scores)
        overall = round(avg_raw * 20, 1)  # 0-5 映射到 0-100
    else:
        overall = 0.0

    scores["overall"] = overall
    review["scores"] = scores
    review["pass"] = overall >= pass_threshold

    return review


def _extract_ep_num(filename: str) -> int:
    """从文件名（如 ep1.txt）中提取集号。"""
    import re
    match = re.search(r"ep(\d+)", filename)
    if not match:
        raise ValueError(f"无法从文件名提取集号：{filename}")
    return int(match.group(1))


def _find_episode_plan(plan: List[Dict], ep_num: int) -> Optional[Dict]:
    """在节拍表中查找对应集号的规划。"""
    for item in plan:
        if item.get("ep") == ep_num:
            return item
    return None
