"""剧本格式校验器 — 检查格式合规 + 行数范围 + 台词/舞台指示比例。

校验对象：单集剧本纯文本。
校验依据：CLAUDE.md 格式规范 + style_profile.json 的 target 区间。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from .style_profile import (
    FULL_COLON,
    TRI,
    LBR,
    EP_PREFIX,
    EP_SUFFIX,
    RENWU_PREFIX,
)


# ── 数据结构 ──────────────────────────────────────────────────────


class IssueLevel(str, Enum):
    """问题严重程度。"""
    ERROR = "error"      # 格式不合规，必须修改
    WARNING = "warning"  # 超出建议范围，建议调整


class IssueType(str, Enum):
    """问题类别。"""
    FORMAT = "format"        # 格式不合规
    LINE_COUNT = "line_count"  # 行数超出范围
    RATIO = "ratio"          # 比例异常


@dataclass
class ValidationIssue:
    """单条校验问题。"""
    type: IssueType
    level: IssueLevel
    line_num: Optional[int]  # None 表示整集级别问题
    description: str


@dataclass
class EpisodeValidation:
    """单集统计信息，用于比例/行数校验。"""
    episode: int = 0
    scene_count: int = 0
    total_lines: int = 0
    dialogue_lines: int = 0
    stage_lines: int = 0
    vo_os_lines: int = 0


@dataclass
class ValidationResult:
    """校验结果。"""
    passed: bool
    episode: int
    stats: EpisodeValidation
    issues: List[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "episode": self.episode,
            "stats": asdict(self.stats),
            "issues": [
                {
                    "type": iss.type.value,
                    "level": iss.level.value,
                    "line_num": iss.line_num,
                    "description": iss.description,
                }
                for iss in self.issues
            ],
        }


# ── 默认风格目标（与 style_profile.json 的 target 一致）─────────

DEFAULT_TARGET: Dict[str, Dict] = {
    "scenes_per_ep": {"suggest": 1.7, "range": [1, 3]},
    "total_lines_per_ep": {"suggest": 28.1, "range": [22, 38]},
    "dialogue_lines_per_ep": {"suggest": 10.28, "range": [10, 20]},
    "stage_lines_per_ep": {"suggest": 14.23, "range": [8, 20]},
    "vo_os_lines_per_ep": {"suggest": 4.34, "range": [0, 6]},
}

# ── 允许的转场标记 ────────────────────────────────────────────────

ALLOWED_TRANSITIONS = {"【切】", "【转】", "【闪回】", "【闪出】"}

# ── 正则 ──────────────────────────────────────────────────────────

# 集标题：第N集
RE_EP_TITLE = re.compile(r"^" + EP_PREFIX + r"(\d+)" + EP_SUFFIX + r"$")

# 场次行：{ep}-{scene}场  {place}\t{time}\t{in_out}
# 宽松匹配：允许空格/制表符混用
RE_SCENE = re.compile(
    r"^(\d+)-(\d+)场\s+(.+?)[\s\t]+(日|夜)[\s\t]+(内|外)\s*$"
)

# 人物行：人物：A、B、C
RE_RENWU = re.compile(r"^" + RENWU_PREFIX)

# 动作/镜头行：▲开头
RE_STAGE = re.compile(r"^" + TRI)

# 台词行：角色名：台词（全角冒号）
RE_DIALOGUE = re.compile(r"^[^▲\s【].+?" + FULL_COLON + r".+")

# 转场行：【切】【转】【闪回】【闪出】
RE_TRANSITION = re.compile(r"^【.+?】$")

# VO/OS 标记
RE_VO_OS = re.compile(r"\b(VO|OS)\b|" + r"(VO|OS)" + FULL_COLON)


# ── 行分类 ────────────────────────────────────────────────────────


class LineKind(str, Enum):
    EP_TITLE = "ep_title"
    SCENE = "scene"
    RENWU = "renwu"
    STAGE = "stage"
    DIALOGUE = "dialogue"
    TRANSITION = "transition"
    BLANK = "blank"
    UNKNOWN = "unknown"


def classify_line(line: str) -> LineKind:
    """将单行剧本文本归类。"""
    s = line.strip()
    if not s:
        return LineKind.BLANK
    if RE_EP_TITLE.match(s):
        return LineKind.EP_TITLE
    if RE_SCENE.match(s):
        return LineKind.SCENE
    if RE_RENWU.match(s):
        return LineKind.RENWU
    if RE_STAGE.match(s):
        return LineKind.STAGE
    if RE_TRANSITION.match(s):
        return LineKind.TRANSITION
    # VO/OS 行也按 stage+vo_os 统计
    if s.startswith("VO") or s.startswith("OS") or RE_VO_OS.search(s):
        return LineKind.DIALOGUE  # VO/OS 本质是台词的一种变体
    if FULL_COLON in s:
        return LineKind.DIALOGUE
    # 半角冒号的台词行（格式错误但仍归为台词）
    if re.match(r"^[^\s▲【].+:.+", s):
        return LineKind.DIALOGUE
    return LineKind.UNKNOWN


def _is_vo_os_line(line: str) -> bool:
    """判断是否是 VO/OS 台词行。"""
    s = line.strip()
    return bool(RE_VO_OS.search(s))


# ── 格式校验 ──────────────────────────────────────────────────────


def _check_format(lines: List[str]) -> tuple[List[ValidationIssue], EpisodeValidation]:
    """逐行检查格式，同时统计行数。"""
    issues: List[ValidationIssue] = []
    stats = EpisodeValidation()

    has_ep_title = False
    has_scene = False
    expect_renwu_after_scene = False  # 场次行后应跟人物行

    for i, raw_line in enumerate(lines, start=1):
        s = raw_line.strip()
        if not s:
            expect_renwu_after_scene = False
            continue

        kind = classify_line(raw_line)
        stats.total_lines += 1

        if kind == LineKind.EP_TITLE:
            has_ep_title = True
            m = RE_EP_TITLE.match(s)
            if m:
                stats.episode = int(m.group(1))
            expect_renwu_after_scene = False
            continue

        if kind == LineKind.SCENE:
            has_scene = True
            stats.scene_count += 1
            expect_renwu_after_scene = True
            continue

        if kind == LineKind.RENWU:
            # 人物行格式检查：顿号分隔
            content = s[len(RENWU_PREFIX):]
            if content and "," in content and "、" not in content:
                issues.append(ValidationIssue(
                    type=IssueType.FORMAT,
                    level=IssueLevel.WARNING,
                    line_num=i,
                    description=f"人物行建议用顿号「、」分隔，而非逗号：{s}",
                ))
            expect_renwu_after_scene = False
            continue

        if kind == LineKind.STAGE:
            stats.stage_lines += 1
            expect_renwu_after_scene = False
            continue

        if kind == LineKind.TRANSITION:
            if s not in ALLOWED_TRANSITIONS:
                issues.append(ValidationIssue(
                    type=IssueType.FORMAT,
                    level=IssueLevel.WARNING,
                    line_num=i,
                    description=f"非标准转场标记：{s}，允许的有：{', '.join(ALLOWED_TRANSITIONS)}",
                ))
            expect_renwu_after_scene = False
            continue

        if kind == LineKind.DIALOGUE:
            stats.dialogue_lines += 1
            if _is_vo_os_line(raw_line):
                stats.vo_os_lines += 1
            # 检查是否用了半角冒号
            if ":" in s and FULL_COLON not in s:
                issues.append(ValidationIssue(
                    type=IssueType.FORMAT,
                    level=IssueLevel.ERROR,
                    line_num=i,
                    description=f"台词行应使用全角冒号「：」，检测到半角冒号：{s[:40]}...",
                ))
            expect_renwu_after_scene = False
            continue

        # UNKNOWN — 无法归类的行
        if expect_renwu_after_scene:
            # 场次行后第一个非空行不是人物行
            issues.append(ValidationIssue(
                type=IssueType.FORMAT,
                level=IssueLevel.WARNING,
                line_num=i,
                description=f"场次行后建议紧跟人物行，实际为：{s[:50]}",
            ))
            expect_renwu_after_scene = False
        else:
            issues.append(ValidationIssue(
                type=IssueType.FORMAT,
                level=IssueLevel.WARNING,
                line_num=i,
                description=f"无法识别的行格式：{s[:50]}",
            ))

    # 整集级别格式检查
    if not has_ep_title:
        issues.append(ValidationIssue(
            type=IssueType.FORMAT,
            level=IssueLevel.ERROR,
            line_num=None,
            description="缺少集标题行（格式：第N集）",
        ))
    if not has_scene:
        issues.append(ValidationIssue(
            type=IssueType.FORMAT,
            level=IssueLevel.WARNING,
            line_num=None,
            description="未检测到场次行（格式：N-N场  场景名 日/夜 内/外）",
        ))

    return issues, stats


# ── 行数范围校验 ──────────────────────────────────────────────────


def _check_line_counts(stats: EpisodeValidation, target: Dict[str, Dict]) -> List[ValidationIssue]:
    """检查行数/场景数是否在允许范围内。"""
    issues: List[ValidationIssue] = []

    checks = [
        ("scenes_per_ep", stats.scene_count, "场景数"),
        ("total_lines_per_ep", stats.total_lines, "总行数"),
        ("dialogue_lines_per_ep", stats.dialogue_lines, "台词行数"),
        ("stage_lines_per_ep", stats.stage_lines, "舞台指示行数"),
        ("vo_os_lines_per_ep", stats.vo_os_lines, "VO/OS行数"),
    ]

    for key, actual, label in checks:
        spec = target.get(key)
        if spec is None:
            continue
        lo, hi = spec["range"]
        suggest = spec["suggest"]
        if actual < lo or actual > hi:
            issues.append(ValidationIssue(
                type=IssueType.LINE_COUNT,
                level=IssueLevel.ERROR,
                line_num=None,
                description=f"{label}={actual}，超出允许范围 [{lo}, {hi}]（建议值 {suggest}）",
            ))
        elif abs(actual - suggest) > (hi - lo) * 0.4:
            # 在范围内但偏离建议值较多
            issues.append(ValidationIssue(
                type=IssueType.LINE_COUNT,
                level=IssueLevel.WARNING,
                line_num=None,
                description=f"{label}={actual}，偏离建议值 {suggest}（范围 [{lo}, {hi}]）",
            ))

    return issues


# ── 比例校验 ──────────────────────────────────────────────────────


def _check_ratios(stats: EpisodeValidation) -> List[ValidationIssue]:
    """检查台词/舞台指示与总行数的比例。"""
    issues: List[ValidationIssue] = []
    total = stats.total_lines
    if total == 0:
        return issues

    dialogue_ratio = stats.dialogue_lines / total
    stage_ratio = stats.stage_lines / total

    # 根据样例统计：台词约占 36%（10.28/28.1），舞台约占 50%（14.23/28.1）
    # 给 ±15% 的浮动空间
    if dialogue_ratio < 0.15:
        issues.append(ValidationIssue(
            type=IssueType.RATIO,
            level=IssueLevel.WARNING,
            line_num=None,
            description=f"台词占比过低：{dialogue_ratio:.0%}（建议 25%-55%），可能对话不足",
        ))
    elif dialogue_ratio > 0.70:
        issues.append(ValidationIssue(
            type=IssueType.RATIO,
            level=IssueLevel.WARNING,
            line_num=None,
            description=f"台词占比过高：{dialogue_ratio:.0%}（建议 25%-55%），缺少舞台/镜头指示",
        ))

    if stage_ratio < 0.15:
        issues.append(ValidationIssue(
            type=IssueType.RATIO,
            level=IssueLevel.WARNING,
            line_num=None,
            description=f"舞台指示占比过低：{stage_ratio:.0%}（建议 30%-60%），可能画面感不足",
        ))
    elif stage_ratio > 0.75:
        issues.append(ValidationIssue(
            type=IssueType.RATIO,
            level=IssueLevel.WARNING,
            line_num=None,
            description=f"舞台指示占比过高：{stage_ratio:.0%}（建议 30%-60%），可能缺乏对话推动",
        ))

    return issues


# ── 主入口 ────────────────────────────────────────────────────────


def load_target(profile_path: str | Path = "juben_gen/style_profile.json") -> Dict[str, Dict]:
    """从 style_profile.json 加载 target 区间。找不到则返回默认值。"""
    p = Path(profile_path)
    if not p.exists():
        return DEFAULT_TARGET
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("target", DEFAULT_TARGET)


def validate_episode(
    text: str,
    target: Optional[Dict[str, Dict]] = None,
) -> ValidationResult:
    """校验单集剧本文本。

    Parameters
    ----------
    text : 单集剧本纯文本
    target : 风格目标区间（同 style_profile.json 的 target），为 None 时使用默认值

    Returns
    -------
    ValidationResult
    """
    if target is None:
        target = DEFAULT_TARGET

    lines = text.split("\n")

    # 1. 格式校验 + 统计
    format_issues, stats = _check_format(lines)

    # 2. 行数范围校验
    count_issues = _check_line_counts(stats, target)

    # 3. 比例校验
    ratio_issues = _check_ratios(stats)

    all_issues = format_issues + count_issues + ratio_issues
    has_error = any(iss.level == IssueLevel.ERROR for iss in all_issues)

    return ValidationResult(
        passed=not has_error,
        episode=stats.episode,
        stats=stats,
        issues=all_issues,
    )


def validate_script(
    text: str,
    target: Optional[Dict[str, Dict]] = None,
) -> List[ValidationResult]:
    """校验多集剧本文本（自动按「第N集」分割）。

    Parameters
    ----------
    text : 可能包含多集的剧本纯文本
    target : 风格目标区间

    Returns
    -------
    每集的 ValidationResult 列表
    """
    if target is None:
        target = DEFAULT_TARGET

    # 按「第N集」分割
    ep_pattern = re.compile(r"^(" + EP_PREFIX + r"\d+" + EP_SUFFIX + r")$", re.MULTILINE)
    splits = ep_pattern.split(text)

    # splits 形如 [前文, "第1集", 内容, "第2集", 内容, ...]
    results: List[ValidationResult] = []
    i = 1
    while i < len(splits):
        ep_title = splits[i]
        ep_body = splits[i + 1] if i + 1 < len(splits) else ""
        ep_text = ep_title + "\n" + ep_body
        results.append(validate_episode(ep_text, target))
        i += 2

    # 如果没有检测到集标题，整体当作一集校验
    if not results:
        results.append(validate_episode(text, target))

    return results


def format_report(results: List[ValidationResult]) -> str:
    """将校验结果格式化为可读文本报告。"""
    lines: List[str] = []
    total_errors = 0
    total_warnings = 0

    for r in results:
        ep_label = f"第{r.episode}集" if r.episode else "未知集"
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"== {ep_label} {status} ==")
        lines.append(
            f"  统计：场景={r.stats.scene_count}  总行={r.stats.total_lines}  "
            f"台词={r.stats.dialogue_lines}  舞台={r.stats.stage_lines}  "
            f"VO/OS={r.stats.vo_os_lines}"
        )

        errors = [iss for iss in r.issues if iss.level == IssueLevel.ERROR]
        warnings = [iss for iss in r.issues if iss.level == IssueLevel.WARNING]
        total_errors += len(errors)
        total_warnings += len(warnings)

        if errors:
            lines.append(f"  错误（{len(errors)}）：")
            for iss in errors:
                loc = f"L{iss.line_num}" if iss.line_num else "整集"
                lines.append(f"    [{loc}] {iss.description}")
        if warnings:
            lines.append(f"  警告（{len(warnings)}）：")
            for iss in warnings:
                loc = f"L{iss.line_num}" if iss.line_num else "整集"
                lines.append(f"    [{loc}] {iss.description}")
        if not errors and not warnings:
            lines.append("  无问题")
        lines.append("")

    # 汇总
    all_passed = all(r.passed for r in results)
    summary = "全部通过" if all_passed else "存在未通过的集"
    lines.append(f"汇总：{len(results)} 集，{summary}（{total_errors} 错误 / {total_warnings} 警告）")

    return "\n".join(lines)
