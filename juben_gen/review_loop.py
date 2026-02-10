"""多轮审稿循环 — validator（格式校验） + judge（LLM 审稿） + rewriter（返修）。

校验不通过自动触发返修，默认最多3轮，每轮记录日志。
整合 validator（纯 Python 格式校验）与 judge + rewriter（LLM 审稿返修）。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .config import AppConfig, maybe_load_config
from .judge import judge_episode, DEFAULT_PASS_THRESHOLD
from .rewriter import rewrite_episode
from .rules import AdaptRules
from .validator import ValidationResult, validate_episode, load_target

logger = logging.getLogger(__name__)

# 默认最大返修轮数
DEFAULT_MAX_ROUNDS = 3


def _save_round_log(
    log_entry: Dict,
    output_dir: str | Path,
    ep_num: int,
) -> Path:
    """追加一条日志到 {output_dir}/reviews/ep{N}_log.json。"""
    d = Path(output_dir) / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    log_path = d / f"ep{ep_num}_log.json"

    # 读取已有日志或初始化
    if log_path.exists():
        logs = json.loads(log_path.read_text(encoding="utf-8"))
    else:
        logs = []

    logs.append(log_entry)
    log_path.write_text(
        json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return log_path


def _save_round_script(
    script: str,
    output_dir: str | Path,
    ep_num: int,
    round_num: int,
) -> Path:
    """保存某轮的剧本到 {output_dir}/reviews/ep{N}_round{M}.txt。"""
    d = Path(output_dir) / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"ep{ep_num}_round{round_num}.txt"
    p.write_text(script, encoding="utf-8")
    return p


def _save_round_review(
    review: Dict,
    output_dir: str | Path,
    ep_num: int,
    round_num: int,
) -> Path:
    """保存某轮的评分到 {output_dir}/reviews/ep{N}_round{M}_review.json。"""
    d = Path(output_dir) / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"ep{ep_num}_round{round_num}_review.json"
    p.write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return p


def _build_log_entry(
    round_num: int,
    validation: ValidationResult,
    review: Optional[Dict],
    action: str,
) -> Dict:
    """构建单轮日志条目。"""
    entry: Dict = {
        "round": round_num,
        "validation": {
            "passed": validation.passed,
            "error_count": sum(
                1 for iss in validation.issues if iss.level.value == "error"
            ),
            "warning_count": sum(
                1 for iss in validation.issues if iss.level.value == "warning"
            ),
            "stats": {
                "scene_count": validation.stats.scene_count,
                "total_lines": validation.stats.total_lines,
                "dialogue_lines": validation.stats.dialogue_lines,
                "stage_lines": validation.stats.stage_lines,
                "vo_os_lines": validation.stats.vo_os_lines,
            },
        },
        "action": action,
    }
    if review:
        entry["review"] = {
            "overall": review.get("scores", {}).get("overall", 0),
            "passed": review.get("pass", False),
            "fatal_issues_count": len(review.get("fatal_issues", [])),
            "fix_count": len(review.get("fix_list", [])),
        }
    return entry


def review_episode(
    *,
    episode_script: str,
    ep_num: int,
    rules: AdaptRules,
    config: Optional[AppConfig] = None,
    constraints_path: str = "juben_gen/constraints.fused.json",
    output_dir: str | Path,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    episode_plan: Optional[Dict] = None,
    style_target: Optional[Dict] = None,
) -> tuple[str, Dict, int]:
    """对单集剧本执行完整审稿循环。

    流程：
    1. validator 格式校验
    2. judge LLM 审稿
    3. 两者都通过 → 结束
    4. 未通过 → rewriter 返修 → 重复步骤 1-3
    5. 达到 max_rounds 仍未通过 → 保留最高分版本并警告

    Parameters
    ----------
    episode_script : 单集剧本纯文本
    ep_num : 集号
    rules : 改编规则
    config : 应用配置
    constraints_path : 融合约束 JSON 路径
    output_dir : 输出目录
    pass_threshold : 通过阈值（overall >= 此值）
    max_rounds : 最大返修轮数
    episode_plan : 节拍表中该集规划（可选）
    style_target : 风格目标区间（可选，为 None 时从 style_profile.json 加载）

    Returns
    -------
    (best_script, best_review, total_rounds)
    """
    cfg = config or maybe_load_config()
    target = style_target or load_target()

    current_script = episode_script
    best_script = episode_script
    best_review: Dict = {}
    best_score: float = 0.0

    for round_num in range(max_rounds + 1):
        is_initial = round_num == 0

        # ── 步骤 1：validator 格式校验 ──
        validation = validate_episode(current_script, target)
        logger.info(
            "第 %d 集第 %d 轮校验：%s（error=%d, warning=%d）",
            ep_num,
            round_num,
            "PASS" if validation.passed else "FAIL",
            sum(1 for iss in validation.issues if iss.level.value == "error"),
            sum(1 for iss in validation.issues if iss.level.value == "warning"),
        )

        # ── 步骤 2：judge LLM 审稿 ──
        review = judge_episode(
            episode_script=current_script,
            episode_plan=episode_plan,
            rules=rules,
            config=cfg,
            constraints_path=constraints_path,
            pass_threshold=pass_threshold,
        )
        review["episode"] = ep_num

        overall = review.get("scores", {}).get("overall", 0)
        judge_passed = review.get("pass", False)

        logger.info(
            "第 %d 集第 %d 轮审稿：overall=%.1f（%s）",
            ep_num, round_num, overall,
            "通过" if judge_passed else "未通过",
        )

        # 保存本轮结果
        _save_round_script(current_script, output_dir, ep_num, round_num)
        _save_round_review(review, output_dir, ep_num, round_num)

        # 更新最佳版本
        if overall > best_score:
            best_script = current_script
            best_review = review
            best_score = overall

        # ── 步骤 3：判断是否通过 ──
        both_passed = validation.passed and judge_passed

        if both_passed:
            action = "通过"
        elif round_num >= max_rounds:
            action = "达到最大轮数"
        else:
            action = "触发返修"

        # 记录日志
        log_entry = _build_log_entry(round_num, validation, review, action)
        _save_round_log(log_entry, output_dir, ep_num)

        if both_passed:
            logger.info(
                "第 %d 集在第 %d 轮通过（校验+审稿均通过，overall=%.1f）",
                ep_num, round_num, overall,
            )
            return best_script, best_review, round_num

        if round_num >= max_rounds:
            break

        # ── 步骤 4：返修 ──
        # 将 validator 的问题注入到 review 的 fix_list 中
        review_with_validation = _inject_validation_issues(review, validation)

        logger.info(
            "第 %d 集第 %d 轮返修开始（校验 %s，审稿 %s）",
            ep_num, round_num + 1,
            "PASS" if validation.passed else "FAIL",
            "PASS" if judge_passed else "FAIL",
        )

        current_script = rewrite_episode(
            episode_script=current_script,
            review=review_with_validation,
            config=cfg,
            constraints_path=constraints_path,
        )

    # 达到最大轮数仍未通过
    logger.warning(
        "第 %d 集经过 %d 轮审稿仍未完全通过（最高分=%.1f，阈值=%.1f），保留最高分版本",
        ep_num, max_rounds, best_score, pass_threshold,
    )
    return best_script, best_review, max_rounds


def _inject_validation_issues(review: Dict, validation: ValidationResult) -> Dict:
    """将 validator 发现的格式问题注入到 review 的 fix_list 和 fatal_issues 中。

    这样 rewriter 能同时修复格式问题和内容问题。
    """
    if validation.passed:
        return review

    review = {**review}  # 浅拷贝

    # 注入到 fatal_issues
    fatal_issues = list(review.get("fatal_issues", []))
    fix_list = list(review.get("fix_list", []))

    for iss in validation.issues:
        if iss.level.value == "error":
            fatal_issues.append(f"[格式校验] {iss.description}")
            fix_list.append({
                "scene": f"L{iss.line_num}" if iss.line_num else "整集",
                "line_hint": "",
                "problem": f"[格式校验] {iss.description}",
                "fix": f"请修复：{iss.description}",
            })

    review["fatal_issues"] = fatal_issues
    review["fix_list"] = fix_list
    return review


def review_all_episodes(
    *,
    episodes_dir: str | Path,
    plan_path: Optional[str | Path] = None,
    rules: AdaptRules,
    config: Optional[AppConfig] = None,
    constraints_path: str = "juben_gen/constraints.fused.json",
    output_dir: str | Path,
    pass_threshold: float = DEFAULT_PASS_THRESHOLD,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
) -> List[Dict]:
    """对目录中所有剧本执行审稿循环。

    Parameters
    ----------
    episodes_dir : 剧本目录（含 ep1.txt, ep2.txt, ...）
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
    if not ep_dir.exists():
        raise FileNotFoundError(f"剧本目录不存在：{ep_dir}")

    ep_files = sorted(
        ep_dir.glob("ep*.txt"),
        key=lambda f: int(re.search(r"ep(\d+)", f.name).group(1)),
    )
    if not ep_files:
        raise FileNotFoundError(f"剧本目录中未找到 ep*.txt 文件：{ep_dir}")

    # 可选加载节拍表
    plan: List[Dict] = []
    if plan_path and Path(plan_path).exists():
        plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))

    # 加载风格目标
    from .prompts import load_fused_constraints
    style_target: Dict = {}
    if Path(constraints_path).exists():
        constraints = load_fused_constraints(constraints_path)
        style_target = constraints.get("style_target", {})

    results: List[Dict] = []

    for ep_file in ep_files:
        ep_num = int(re.search(r"ep(\d+)", ep_file.name).group(1))
        script = ep_file.read_text(encoding="utf-8")

        # 匹配节拍表中对应集
        episode_plan = None
        for item in plan:
            if item.get("ep") == ep_num:
                episode_plan = item
                break

        best_script, best_review, rounds = review_episode(
            episode_script=script,
            ep_num=ep_num,
            rules=rules,
            config=config,
            constraints_path=constraints_path,
            output_dir=output_dir,
            pass_threshold=pass_threshold,
            max_rounds=max_rounds,
            episode_plan=episode_plan,
            style_target=style_target or None,
        )

        # 覆盖原剧本为最佳版本
        ep_file.write_text(best_script, encoding="utf-8")

        results.append(best_review)
        logger.info(
            "第 %d 集审稿完成：%d 轮，最终 overall=%.1f（%s）",
            ep_num, rounds,
            best_review.get("scores", {}).get("overall", 0),
            "通过" if best_review.get("pass", False) else "未通过",
        )

    # 汇总
    passed = sum(1 for r in results if r.get("pass", False))
    logger.info(
        "全部审稿完成：共 %d 集，%d 通过 / %d 未通过",
        len(results), passed, len(results) - passed,
    )
    return results
