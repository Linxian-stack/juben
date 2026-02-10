"""通用层 — 红果风格短剧的核心规则、格式规范与评分标准。

所有题材共享这些规则，题材层只做增量覆盖（style_overrides）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ── 结构指标（来自样例融合，各题材通用）─────────────────────────


@dataclass(frozen=True)
class StyleTarget:
    """单集结构指标约束。"""
    scenes_per_ep: Tuple[float, Tuple[int, int]] = (1.7, (1, 3))
    total_lines_per_ep: Tuple[float, Tuple[int, int]] = (28.1, (22, 38))
    dialogue_lines_per_ep: Tuple[float, Tuple[int, int]] = (10.28, (10, 20))
    stage_lines_per_ep: Tuple[float, Tuple[int, int]] = (14.23, (8, 20))
    vo_os_lines_per_ep: Tuple[float, Tuple[int, int]] = (4.34, (0, 6))

    def to_dict(self) -> Dict[str, Dict]:
        """转为与 style_profile.json target 兼容的 dict 格式。"""
        result = {}
        for key in (
            "scenes_per_ep", "total_lines_per_ep",
            "dialogue_lines_per_ep", "stage_lines_per_ep",
            "vo_os_lines_per_ep",
        ):
            suggest, rng = getattr(self, key)
            result[key] = {"suggest": suggest, "range": list(rng)}
        return result


DEFAULT_STYLE_TARGET = StyleTarget()


# ── 格式规范 ──────────────────────────────────────────────────


FORMAT_SPEC = {
    "episode_header": "第{ep}集",
    "scene_header_pattern": "{ep}-{scene}场  {place}\t{日/夜}\t{内/外}",
    "cast_line_prefix": "人物：",
    "stage_direction_prefix": "▲",
    "dialogue_pattern": "{角色名}：{台词}",
    "allowed_markers": ["【切】", "【转】", "【闪回】", "【闪出】"],
}


# ── 节奏硬规则 ────────────────────────────────────────────────


RHYTHM_RULES: List[str] = [
    "开头30秒抛冲突，禁止铺垫式开场",
    "每10秒至少1个记忆点（冲突推进/新信息/情绪爆发/视觉冲击）",
    "每集六要素：30秒勾住→核心冲突→小反转/新信息→爽点/共情点→结尾强钩子",
    "结尾钩子四选一：冲突卡点/信息反转/危机升级/情感抉择（落在最后一镜/最后一句）",
    "钩子在后续1-2集内回收，同时再埋新钩子",
]


# ── 钩子机制 ──────────────────────────────────────────────────


HOOK_TYPES: List[str] = ["冲突卡点", "信息反转", "危机升级", "情感抉择"]


# ── 禁止事项 ──────────────────────────────────────────────────


PROHIBITIONS: List[str] = [
    "禁止大段环境描写（超过2句纯环境即违规）",
    "禁止连续OS/VO超过2行（用动作和台词替代内心独白）",
    "禁止书面语/文绉绉表达（台词必须口语化短句）",
    "禁止与核心目标无关的支线",
    "禁止寒暄废话/重复信息",
    "禁止使用非标准转场标记",
]


# ── 评分维度（通用，各题材共享）───────────────────────────────


SCORING_DIMENSIONS: List[str] = [
    "open_hook",       # 开头钩子
    "core_conflict",   # 核心冲突
    "turn",            # 反转有效
    "highlight",       # 爽点共情
    "rhythm",          # 节奏密度
    "character",       # 人物一致
    "shootable",       # 可拍性
    "end_hook",        # 结尾钩子强度
    "safety",          # 合规风险
]


# ── 合规约束 ──────────────────────────────────────────────────


SAFETY_NOTES: List[str] = [
    "避免涉政、涉黄、涉赌、涉毒、极端暴力血腥、未成年人不当内容",
    "镜头处理：能用'反应镜头/声音/切黑/道具特写'表达的，不直接描写血腥细节",
    "价值导向：反派恶行要有后果，主角行动有正当动机，避免宣扬违法犯罪技巧",
]
