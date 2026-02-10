from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .rules import load_rules_from_docx
from .style_profile import build_combined_profile, save_json


def build_constraints(
    *,
    scripts: List[Union[str, Path]],
    rhythm_docx: Union[str, Path],
    end_hook_docx: Union[str, Path],
    template_docx: Union[str, Path],
    genre: Optional[str] = None,
) -> Dict[str, object]:
    """融合样例剧本 + 规则文本，生成可执行约束。

    Parameters
    ----------
    genre : 题材标识（如 "apocalypse" 或 "末世"），提供时融合题材特定约束。
    """
    style_profile = build_combined_profile([str(p) for p in scripts], genre=genre)
    rules = load_rules_from_docx(
        rhythm_docx=rhythm_docx,
        end_hook_docx=end_hook_docx,
        template_docx=template_docx,
    )

    format_spec = {
        "episode_header": "第{ep}集",
        "scene_header_pattern": "{ep}-{scene}场  {place}\\t{day_or_night}\\t{in_or_out}",
        "cast_line_prefix": "人物：",
        "stage_direction_prefix": "▲",
        "dialogue_pattern": "{角色名}：{台词}",
        "allowed_markers": ["【切】", "【转】", "【闪回】", "【闪出】"],
    }

    result: Dict[str, object] = {
        "style_target": style_profile["target"],
        "format_spec": format_spec,
        "rules_text": {
            "rhythm_notes": rules.rhythm_notes,
            "end_hook_notes": rules.end_hook_notes,
            "card_template_notes": rules.card_template_notes,
        },
        "fusion_policy": {
            "numeric": "两套样例取均值做suggest；range取适配1-2分钟/集的可控区间（可拍+高密度）。",
            "rhythm": "以《节奏适配关键注意事项》为硬规则；冲突密度与结尾钩子必须满足。",
            "format": "以两份样例共有格式为准：第N集/场次/人物/▲/角色：台词。",
        },
    }

    # 注入题材层约束
    genre_data = style_profile.get("genre_specific")
    if genre_data:
        result["genre"] = genre_data

    return result


def write_style_guide_md(constraints: Dict[str, object], path: Union[str, Path]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    target = constraints.get("style_target", {})
    fmt = constraints.get("format_spec", {})
    genre_data = constraints.get("genre")

    def _r(name: str, obj: Dict[str, object]) -> str:
        v = obj.get(name, {})
        if not isinstance(v, dict):
            return ""
        return f"- **{name}**：建议 {v.get('suggest')}，范围 {v.get('range')}"

    lines = [
        "# 融合风格约束（基于两套优秀样例）",
        "",
        "## 结构指标（1-2分钟/集，通用层）",
        _r("scenes_per_ep", target),  # type: ignore[arg-type]
        _r("total_lines_per_ep", target),  # type: ignore[arg-type]
        _r("dialogue_lines_per_ep", target),  # type: ignore[arg-type]
        _r("stage_lines_per_ep", target),  # type: ignore[arg-type]
        _r("vo_os_lines_per_ep", target),  # type: ignore[arg-type]
        "",
        "## 格式规范（必须可导出docx且可被脚本校验）",
        f"- 集标题：`{fmt.get('episode_header')}`",
        f"- 场次行：`{fmt.get('scene_header_pattern')}`（用 Tab 或空格分隔也可，但字段顺序别乱）",
        f"- 人物行前缀：`{fmt.get('cast_line_prefix')}`（用顿号\u201c、\u201d分隔）",
        f"- 动作/镜头行前缀：`{fmt.get('stage_direction_prefix')}`（短句、强视觉）",
        f"- 台词行：`{fmt.get('dialogue_pattern')}`（中文全角冒号\u201c：\u201d）",
        f"- 允许的转场标记：{fmt.get('allowed_markers')}",
        "",
        "## 节奏硬规则（来自注意事项）",
        "- 开头30秒抛冲突；每10秒至少一个记忆点（冲突/信息/情绪/动作）。",
        "- 每集：1个核心冲突 + 1个小反转/新信息 + 1个爽点/共情点 + 结尾强钩子。",
        "- 钩子在后续1-2集内回收，同时再埋新钩子，避免挖坑不填。",
        "",
        "## 结尾钩子四选一（必须明确到\u201c最后一镜/最后一句\u201d）",
        "- 冲突卡点钩 / 信息反转钩 / 危机升级钩 / 情感抉择钩",
        "",
    ]

    # 题材层信息
    if genre_data and isinstance(genre_data, dict):
        lines.extend([
            f"## 题材层约束（{genre_data.get('genre', '')}）",
            "",
            f"- **核心特征**：{', '.join(genre_data.get('traits', []))}",
            f"- **冲突模式**：{'; '.join(genre_data.get('conflict_patterns', []))}",
            f"- **标志性场景**：{'; '.join(genre_data.get('iconic_scenes', []))}",
        ])
        hooks = genre_data.get("hook_preferences", {})
        if hooks:
            lines.append(f"- **主力钩子**：{hooks.get('primary', '')}（辅助：{hooks.get('secondary', '')}）")
            lines.append(f"- **钩子说明**：{hooks.get('notes', '')}")
        overrides = genre_data.get("style_overrides", {})
        for key, val in overrides.items():
            lines.append(f"- **{key}**：{val}")
        lines.append("")

    p.write_text("\n".join([x for x in lines if x is not None]), encoding="utf-8")


def save_constraints(
    *,
    scripts: List[Union[str, Path]],
    rhythm_docx: Union[str, Path],
    end_hook_docx: Union[str, Path],
    template_docx: Union[str, Path],
    out_json: Union[str, Path],
    out_md: Union[str, Path],
    genre: Optional[str] = None,
) -> None:
    c = build_constraints(
        scripts=scripts,
        rhythm_docx=rhythm_docx,
        end_hook_docx=end_hook_docx,
        template_docx=template_docx,
        genre=genre,
    )
    save_json(c, out_json)
    write_style_guide_md(c, out_md)

