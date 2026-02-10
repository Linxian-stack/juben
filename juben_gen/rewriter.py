"""返修循环模块 — 评分不达标时自动重写，最多N轮。

流程：
1. 根据评分 JSON 中的修改清单，调用 Claude API 返修剧本
2. 返修后重新评分
3. 达标则停止，否则继续重写（最多 max_rounds 轮）
4. 达到上限仍未通过，保留最高分版本并警告
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .config import AppConfig, RoleConfig, maybe_load_config
from .judge import judge_episode, save_review, DEFAULT_PASS_THRESHOLD
from .llm_clients import ClaudeClient, LLMResponse
from .prompts import build_system_prompt, load_fused_constraints, prompt_rewrite_episode
from .rules import AdaptRules

logger = logging.getLogger(__name__)

# 默认最大返修轮数
DEFAULT_MAX_ROUNDS = 3


def rewrite_episode(
    *,
    episode_script: str,
    review: Dict,
    config: Optional[AppConfig] = None,
    constraints_path: str = "juben_gen/constraints.fused.json",
) -> str:
    """对单集剧本做一次返修。

    Parameters
    ----------
    episode_script : 原剧本纯文本
    review : 评分 JSON（含 fix_list、scores 等）
    config : 应用配置，为 None 时使用默认配置
    constraints_path : 融合约束 JSON 路径

    Returns
    -------
    返修后的剧本纯文本。
    """
    cfg = config or maybe_load_config()
    role_cfg: RoleConfig = cfg.roles["rewrite"]

    # 加载融合约束
    constraints = None
    if Path(constraints_path).exists():
        constraints = load_fused_constraints(constraints_path)

    # 组装 prompt
    system = build_system_prompt(constraints=constraints)

    fix_list = review.get("fix_list", [])
    scores = review.get("scores", {})

    user_msg = prompt_rewrite_episode(
        fix_list_json=json.dumps(fix_list, ensure_ascii=False, indent=2),
        episode_script=episode_script,
        scores_json=json.dumps(scores, ensure_ascii=False, indent=2),
    )

    # 调用 Claude API
    client = ClaudeClient(
        max_attempts=cfg.retry.max_attempts,
        base_delay=cfg.retry.base_delay,
    )
    logger.info(
        "调用 Claude API（rewrite 角色，模型=%s）",
        role_cfg.model,
    )
    response: LLMResponse = client.chat(
        model=role_cfg.model,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
        thinking=role_cfg.thinking,
        budget_tokens=role_cfg.budget_tokens,
        max_tokens=8192,
    )

    script = response.text.strip()
    logger.info("返修完成（%d 字符）", len(script))
    return script


def _save_round_result(
    script: str,
    review: Dict,
    output_dir: str | Path,
    ep_num: int,
    round_num: int,
) -> tuple[Path, Path]:
    """保存某轮的剧本和评分。

    Returns
    -------
    (script_path, review_path)
    """
    d = Path(output_dir) / "reviews"
    d.mkdir(parents=True, exist_ok=True)

    script_path = d / f"ep{ep_num}_round{round_num}.txt"
    script_path.write_text(script, encoding="utf-8")

    review_path = d / f"ep{ep_num}_round{round_num}_review.json"
    review_path.write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    logger.info("第 %d 集第 %d 轮结果已保存：%s, %s", ep_num, round_num, script_path, review_path)
    return script_path, review_path


def rewrite_loop(
    *,
    episode_script: str,
    review: Dict,
    ep_num: int,
    rules: AdaptRules,
    config: Optional[AppConfig] = None,
    constraints_path: str = "juben_gen/constraints.fused.json",
    output_dir: str | Path,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    episode_plan: Optional[Dict] = None,
) -> tuple[str, Dict, int]:
    """返修循环：重写 → 评分 → 判断，最多 max_rounds 轮。

    Parameters
    ----------
    episode_script : 初始剧本纯文本（已评分不通过的版本）
    review : 初始评分 JSON
    ep_num : 集号
    rules : 改编规则
    config : 应用配置
    constraints_path : 融合约束 JSON 路径
    output_dir : 输出目录
    pass_threshold : 通过阈值
    max_rounds : 最大返修轮数
    episode_plan : 节拍表中该集规划（可选，传给 judge）

    Returns
    -------
    (best_script, best_review, total_rounds)
    - best_script: 最高分版本的剧本文本
    - best_review: 最高分版本的评分 JSON
    - total_rounds: 实际执行的返修轮数
    """
    cfg = config or maybe_load_config()

    current_script = episode_script
    current_review = review
    best_script = episode_script
    best_review = review
    best_score = current_review.get("scores", {}).get("overall", 0)

    # 保存初始版本（round 0）
    _save_round_result(current_script, current_review, output_dir, ep_num, 0)

    for round_num in range(1, max_rounds + 1):
        logger.info(
            "第 %d 集：开始第 %d/%d 轮返修（当前 overall=%.1f，阈值=%.1f）",
            ep_num, round_num, max_rounds, best_score, pass_threshold,
        )

        # 1. 返修
        new_script = rewrite_episode(
            episode_script=current_script,
            review=current_review,
            config=cfg,
            constraints_path=constraints_path,
        )

        # 2. 重新评分
        new_review = judge_episode(
            episode_script=new_script,
            episode_plan=episode_plan,
            rules=rules,
            config=cfg,
            constraints_path=constraints_path,
            pass_threshold=pass_threshold,
        )
        new_review["episode"] = ep_num

        # 3. 保存本轮结果
        _save_round_result(new_script, new_review, output_dir, ep_num, round_num)

        new_score = new_review.get("scores", {}).get("overall", 0)
        logger.info(
            "第 %d 集第 %d 轮返修结果：overall=%.1f（%s）",
            ep_num, round_num, new_score,
            "通过" if new_review.get("pass", False) else "未通过",
        )

        # 更新最高分版本
        if new_score > best_score:
            best_script = new_script
            best_review = new_review
            best_score = new_score

        # 4. 达标则停止
        if new_review.get("pass", False):
            logger.info("第 %d 集在第 %d 轮达标（overall=%.1f）", ep_num, round_num, new_score)
            return best_script, best_review, round_num

        # 未达标，用新版本继续下一轮
        current_script = new_script
        current_review = new_review

    # 达到最大轮数仍未通过
    logger.warning(
        "第 %d 集经过 %d 轮返修仍未达标（最高分=%.1f，阈值=%.1f），保留最高分版本",
        ep_num, max_rounds, best_score, pass_threshold,
    )
    return best_script, best_review, max_rounds


def rewrite_all_episodes(
    *,
    episodes_dir: str | Path,
    reviews_dir: str | Path,
    plan_path: Optional[str | Path] = None,
    rules: AdaptRules,
    config: Optional[AppConfig] = None,
    constraints_path: str = "juben_gen/constraints.fused.json",
    output_dir: str | Path,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> List[Dict]:
    """对所有未通过的剧本执行返修循环。

    Parameters
    ----------
    episodes_dir : 剧本目录（含 ep1.txt, ep2.txt, ...）
    reviews_dir : 评分目录（含 ep1_review.json, ep2_review.json, ...）
    plan_path : 节拍表 JSON 路径（可选）
    rules : 改编规则
    config : 应用配置
    constraints_path : 融合约束 JSON 路径
    output_dir : 输出目录
    pass_threshold : 通过阈值
    max_rounds : 最大返修轮数

    Returns
    -------
    所有集的最终评分结果列表。
    """
    import re

    ep_dir = Path(episodes_dir)
    rev_dir = Path(reviews_dir)

    if not ep_dir.exists():
        raise FileNotFoundError(f"剧本目录不存在：{ep_dir}")
    if not rev_dir.exists():
        raise FileNotFoundError(f"评分目录不存在：{rev_dir}")

    # 收集所有 epN_review.json
    review_files = sorted(
        rev_dir.glob("ep*_review.json"),
        key=lambda f: int(re.search(r"ep(\d+)", f.name).group(1)),
    )
    if not review_files:
        raise FileNotFoundError(f"评分目录中未找到 ep*_review.json 文件：{rev_dir}")

    # 可选加载节拍表
    plan: List[Dict] = []
    if plan_path and Path(plan_path).exists():
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))

    results: List[Dict] = []
    rewritten_count = 0

    for review_file in review_files:
        ep_num = int(re.search(r"ep(\d+)", review_file.name).group(1))
        review = json.loads(review_file.read_text(encoding="utf-8"))

        # 已通过的集直接跳过
        if review.get("pass", False):
            logger.info("第 %d 集已通过（overall=%.1f），跳过返修", ep_num, review.get("scores", {}).get("overall", 0))
            results.append(review)
            continue

        # 读取对应剧本
        script_path = ep_dir / f"ep{ep_num}.txt"
        if not script_path.exists():
            logger.warning("第 %d 集剧本文件不存在：%s，跳过", ep_num, script_path)
            results.append(review)
            continue

        script = script_path.read_text(encoding="utf-8")
        episode_plan = _find_episode_plan(plan, ep_num)

        # 执行返修循环
        best_script, best_review, rounds = rewrite_loop(
            episode_script=script,
            review=review,
            ep_num=ep_num,
            rules=rules,
            config=config,
            constraints_path=constraints_path,
            output_dir=output_dir,
            pass_threshold=pass_threshold,
            max_rounds=max_rounds,
            episode_plan=episode_plan,
        )

        # 覆盖原剧本为最佳版本
        script_path.write_text(best_script, encoding="utf-8")

        # 更新评分文件
        save_review(best_review, output_dir, ep_num)

        results.append(best_review)
        rewritten_count += 1
        logger.info(
            "第 %d 集返修完成：%d 轮，最终 overall=%.1f（%s）",
            ep_num, rounds,
            best_review.get("scores", {}).get("overall", 0),
            "通过" if best_review.get("pass", False) else "未通过",
        )

    # 汇总
    passed = sum(1 for r in results if r.get("pass", False))
    logger.info(
        "返修完成：共 %d 集，返修 %d 集，最终 %d 通过 / %d 未通过",
        len(results), rewritten_count, passed, len(results) - passed,
    )
    return results


def _find_episode_plan(plan: List[Dict], ep_num: int) -> Optional[Dict]:
    """在节拍表中查找对应集号的规划。"""
    for item in plan:
        if item.get("ep") == ep_num:
            return item
    return None
