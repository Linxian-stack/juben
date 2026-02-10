"""样例对比评估 — 将生成剧本的统计指标与样例均值做对比，输出表格式报告。"""

from __future__ import annotations

import json
import statistics as st
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .style_profile import (
    _parse_episodes,
    _episode_stats,
    EpisodeStats,
)


@dataclass
class MetricComparison:
    """单项指标对比结果。"""
    name: str           # 中文指标名
    generated: float    # 生成值（各集均值）
    suggest: float      # 样例建议值
    range_lo: float     # 允许范围下限
    range_hi: float     # 允许范围上限
    in_range: bool      # 是否在范围内


@dataclass
class EvaluationReport:
    """评估报告。"""
    episode_count: int
    per_episode: List[EpisodeStats]
    comparisons: List[MetricComparison]

    @property
    def all_in_range(self) -> bool:
        return all(c.in_range for c in self.comparisons)


# ── 指标名称映射 ────────────────────────────────────────────────


METRIC_MAP = {
    "scenes_per_ep": ("场景数/集", "scenes"),
    "total_lines_per_ep": ("总行数/集", "total_lines"),
    "dialogue_lines_per_ep": ("台词行/集", "dialogue_lines"),
    "stage_lines_per_ep": ("舞台指示行/集", "stage_lines"),
    "vo_os_lines_per_ep": ("旁白行/集", "vo_os_lines"),
}


# ── 核心逻辑 ────────────────────────────────────────────────────


def evaluate_script(
    script_text: str,
    target: Dict[str, Dict],
) -> EvaluationReport:
    """对比生成剧本与样例目标。

    Parameters
    ----------
    script_text : 生成剧本纯文本（可含多集）
    target : style_profile.json 的 target 部分

    Returns
    -------
    EvaluationReport
    """
    lines = script_text.split("\n")
    eps = _parse_episodes(lines)

    if not eps:
        return EvaluationReport(
            episode_count=0,
            per_episode=[],
            comparisons=[],
        )

    per_ep = [_episode_stats(ep, eps[ep]) for ep in sorted(eps)]

    # 计算各集均值
    avg = {
        "scenes": float(st.mean(e.scenes for e in per_ep)),
        "total_lines": float(st.mean(e.total_lines for e in per_ep)),
        "dialogue_lines": float(st.mean(e.dialogue_lines for e in per_ep)),
        "stage_lines": float(st.mean(e.stage_lines for e in per_ep)),
        "vo_os_lines": float(st.mean(e.vo_os_lines for e in per_ep)),
    }

    comparisons: List[MetricComparison] = []
    for key, (cn_name, attr_name) in METRIC_MAP.items():
        spec = target.get(key)
        if spec is None:
            continue
        gen_val = round(avg[attr_name], 2)
        lo, hi = spec["range"]
        comparisons.append(MetricComparison(
            name=cn_name,
            generated=gen_val,
            suggest=spec["suggest"],
            range_lo=lo,
            range_hi=hi,
            in_range=(lo <= gen_val <= hi),
        ))

    return EvaluationReport(
        episode_count=len(per_ep),
        per_episode=per_ep,
        comparisons=comparisons,
    )


def load_target(profile_path: str | Path = "juben_gen/style_profile.json") -> Dict[str, Dict]:
    """从 style_profile.json 加载 target 区间。"""
    p = Path(profile_path)
    if not p.exists():
        from .validator import DEFAULT_TARGET
        return DEFAULT_TARGET
    data = json.loads(p.read_text(encoding="utf-8"))
    return data.get("target", {})


def format_report_md(report: EvaluationReport) -> str:
    """将评估报告格式化为 Markdown 表格。"""
    lines: List[str] = []
    lines.append("# 样例对比评估报告")
    lines.append("")
    lines.append(f"评估集数：{report.episode_count}")
    lines.append("")
    lines.append("| 指标 | 生成值 | 样例均值 | 范围 | 状态 |")
    lines.append("|------|--------|----------|------|------|")

    for c in report.comparisons:
        status = "✅" if c.in_range else "⚠️"
        lines.append(
            f"| {c.name} | {c.generated} | {c.suggest} "
            f"| [{c.range_lo}, {c.range_hi}] | {status} |"
        )

    lines.append("")

    # 超出范围的指标汇总
    warnings = [c for c in report.comparisons if not c.in_range]
    if warnings:
        lines.append("## 超出范围的指标")
        lines.append("")
        for c in warnings:
            direction = "偏低" if c.generated < c.range_lo else "偏高"
            lines.append(f"- **{c.name}**：生成值 {c.generated}，{direction}（范围 [{c.range_lo}, {c.range_hi}]）")
        lines.append("")
    else:
        lines.append("所有指标均在合理范围内。")
        lines.append("")

    return "\n".join(lines)


def save_report(report: EvaluationReport, output_dir: str | Path) -> Path:
    """将评估报告保存到输出目录。"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / "evaluation_report.md"
    report_path.write_text(format_report_md(report), encoding="utf-8")
    return report_path
