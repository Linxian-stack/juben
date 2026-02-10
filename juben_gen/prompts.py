"""Prompt 模板库 — 针对 Claude 长上下文 + extended thinking 优化。

每个 prompt 函数返回 user message 文本，system prompt 通过 build_system_prompt() 生成。
plan / judge 角色建议搭配 extended thinking 使用（由 llm_clients.RoleConfig 控制）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union

from .rules import AdaptRules, redfruit_safety_notes

# ---------- 公共数据类 ----------


@dataclass(frozen=True)
class EpisodeSpec:
    """单集结构约束参数。"""
    seconds_min: int = 60
    seconds_max: int = 120
    scenes_range: tuple = (1, 3)
    total_lines_range: tuple = (22, 38)


# ---------- 融合约束加载 ----------


def load_fused_constraints(path: Union[str, Path] = "juben_gen/constraints.fused.json") -> Dict:
    """读取融合约束 JSON（style_target + format_spec + rules_text）。"""
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------- System Prompt ----------


def build_system_prompt(
    *,
    constraints: Optional[Dict] = None,
    sample_snippet: str = "",
) -> str:
    """构建 system prompt，注入完整的风格约束和格式规范。

    Parameters
    ----------
    constraints : 融合约束 dict（来自 constraints.fused.json），为 None 时使用精简版。
                  若含 "genre" 键，会自动注入题材特定约束。
    sample_snippet : 样例剧本片段（few-shot），为空则跳过。
    """
    sections: List[str] = [
        "你是资深短剧编剧与改编策划，擅长把小说改写成1-2分钟/集的红果风格短剧剧本。",
        "输出必须信息密度高、冲突强、节奏快、结尾有钩子；不要写散文化小说。",
    ]

    # 注入格式规范
    fmt_rules = _FORMAT_RULES
    if constraints:
        fmt = constraints.get("format_spec", {})
        fmt_rules = _build_format_rules(fmt)
    sections.append("【格式硬约束】\n" + fmt_rules)

    # 注入结构指标
    if constraints:
        target = constraints.get("style_target", {})
        sections.append("【结构指标约束】\n" + _build_target_summary(target))

    # 注入题材特定约束
    if constraints:
        genre_section = _build_genre_section(constraints.get("genre"))
        if genre_section:
            sections.append(genre_section)

    # 注入节奏硬规则
    sections.append(_RHYTHM_RULES)

    # 注入禁止事项
    sections.append(_PROHIBITION_LIST)

    # 合规约束
    sections.append(redfruit_safety_notes())

    # 样例片段（few-shot）
    if sample_snippet:
        sections.append("【样例剧本片段（格式参考）】\n" + sample_snippet)

    return "\n\n".join(sections)


# ---------- User Prompts ----------


def prompt_story_bible(
    *,
    rules: AdaptRules,
    novel_excerpt: str,
    sample_bible_json: str = "",
) -> str:
    """Story Bible 提取 prompt。

    Parameters
    ----------
    sample_bible_json : 样例 Bible JSON 字符串（few-shot 参考），为空则跳过。
    """
    sections: List[str] = [
        '【任务】阅读小说片段，抽取"改编用剧情圣经 story bible"（JSON）。',
        "【输出格式】只输出JSON，不要解释。字段：\n" + _BIBLE_SCHEMA,
        "【参考规则：节奏适配关键注意事项】\n" + rules.rhythm_notes,
    ]

    if sample_bible_json:
        sections.append("【样例 Bible JSON（仅供参考格式和粒度）】\n" + sample_bible_json)

    sections.append("【小说片段】\n" + novel_excerpt)

    return "\n\n".join(sections)


def prompt_plan_first10(
    *,
    rules: AdaptRules,
    style_target: Dict[str, object],
    bible_json: str,
    episode_spec: EpisodeSpec,
    sample_plan_json: str = "",
) -> str:
    """前10集分集节拍表规划 prompt。建议搭配 extended thinking 使用。

    Parameters
    ----------
    sample_plan_json : 样例节拍表 JSON 字符串（few-shot），为空则跳过。
    """
    sections: List[str] = [
        '【任务】为红果短剧规划前10集"分集节拍表"（JSON数组）。每集1-2分钟。',
        _build_hard_constraints(episode_spec),
        "【输出格式】只输出JSON数组，不要解释。每集对象字段：\n" + _PLAN_SCHEMA,
        "【起承转合参考（前10集付费卡点）】\n" + rules.card_template_notes,
        "【结尾钩子方法】\n" + rules.end_hook_notes,
        "【样例风格目标（统计画像）】\n" + json.dumps(style_target, ensure_ascii=False, indent=2),
    ]

    if sample_plan_json:
        sections.append("【样例节拍表JSON（格式参考）】\n" + sample_plan_json)

    sections.append("【story bible】\n" + bible_json)

    return "\n\n".join(sections)


def prompt_write_episode(
    *,
    rules: AdaptRules,
    style_target: Dict[str, object],
    episode_plan_json: str,
    prev_summary: str = "",
    sample_script: str = "",
) -> str:
    """单集剧本生成 prompt。

    Parameters
    ----------
    prev_summary : 前一集摘要（保持连贯性），为空则跳过。
    sample_script : 样例剧本片段（格式参考），为空则跳过。
    """
    sections: List[str] = [
        '【任务】根据"分集节拍表"，写出该集完整短剧剧本（纯文本），用于导出docx。',
        _WRITE_FORMAT_RULES,
        "【节奏要求】\n" + _WRITE_RHYTHM_RULES,
        "【禁止事项】\n" + _WRITE_PROHIBITIONS,
        "【参考规则：节奏适配关键注意事项】\n" + rules.rhythm_notes,
        "【样例风格目标（统计画像）】\n" + json.dumps(style_target, ensure_ascii=False, indent=2),
    ]

    if sample_script:
        sections.append("【样例剧本片段（格式参考）】\n" + sample_script)

    if prev_summary:
        sections.append("【前一集摘要（保持连贯性）】\n" + prev_summary)

    sections.append("【分集节拍表JSON】\n" + episode_plan_json)

    return "\n\n".join(sections)


def prompt_judge_episode(
    *,
    rules: AdaptRules,
    episode_script: str,
    style_target: Optional[Dict[str, object]] = None,
) -> str:
    """审稿评分 prompt。建议搭配 extended thinking 做深度评估。

    Parameters
    ----------
    style_target : 结构指标约束，提供后会加入校验参考。
    """
    sections: List[str] = [
        "【任务】你是短剧审稿编辑，对该集剧本做量化打分与可执行修改清单（JSON）。",
        "【评分维度】每项0-5分：\n" + _JUDGE_DIMENSIONS,
        "【输出格式】只输出JSON：\n" + _JUDGE_SCHEMA,
        "【评审重点】\n" + _JUDGE_FOCUS,
        "【参考规则：节奏适配关键注意事项】\n" + rules.rhythm_notes,
        "【结尾钩子方法】\n" + rules.end_hook_notes,
    ]

    if style_target:
        sections.append(
            "【结构指标约束（用于校验行数/比例）】\n"
            + json.dumps(style_target, ensure_ascii=False, indent=2)
        )

    sections.append("【剧本】\n" + episode_script)

    return "\n\n".join(sections)


def prompt_rewrite_episode(
    *,
    fix_list_json: str,
    episode_script: str,
    scores_json: str = "",
) -> str:
    """最小改动返修 prompt。

    Parameters
    ----------
    scores_json : 审稿评分 JSON（提供上下文），为空则跳过。
    """
    sections: List[str] = [
        '【任务】按"修改清单"对剧本做最小改动返修：只改列出的问题，不要重写整集。',
        "【输出】只输出返修后的完整剧本纯文本（同原格式）。",
        "【返修原则】\n" + _REWRITE_PRINCIPLES,
    ]

    if scores_json:
        sections.append("【审稿评分JSON（上下文参考）】\n" + scores_json)

    sections.append("【修改清单JSON】\n" + fix_list_json)
    sections.append("【原剧本】\n" + episode_script)

    return "\n\n".join(sections)


# ============================================================
# 内部常量 — 格式/节奏/禁止事项/Schema
# ============================================================

_FORMAT_RULES = """\
- 集标题：`第{ep}集`（独占一行）
- 场次行：`{ep}-{scene}场  {place}\t{日/夜}\t{内/外}`
- 人物行：`人物：A、B、C`（顿号分隔，紧跟场次行）
- 动作/镜头行：以`▲`开头（短句、强视觉、动词优先）
- 台词行：`角色名：台词`（全角冒号"："）；可带括号表演提示（2-4字）
- VO/OS行：`VO：角色名（内容）` 或 `角色名OS：内容`
- 转场标记：仅允许 `【切】` `【转】` `【闪回】` `【闪出】`
- 【闪回】和【闪出】必须成对出现，闪回内容不超过5行"""

_RHYTHM_RULES = """\
【节奏硬规则】
- 开头30秒抛冲突，禁止铺垫式开场
- 每10秒至少1个记忆点（冲突推进/新信息/情绪爆发/视觉冲击）
- 每集六要素：30秒勾住→核心冲突→小反转/新信息→爽点/共情点→结尾强钩子
- 结尾钩子四选一：冲突卡点/信息反转/危机升级/情感抉择（落在最后一镜/最后一句）
- 钩子在后续1-2集内回收，同时再埋新钩子"""

_PROHIBITION_LIST = """\
【禁止事项】
- 禁止大段环境描写（超过2句纯环境即违规）
- 禁止连续OS/VO超过2行（用动作和台词替代内心独白）
- 禁止书面语/文绉绉表达（台词必须口语化短句）
- 禁止与核心目标无关的支线
- 禁止寒暄废话/重复信息
- 禁止使用非标准转场标记"""

# ---------- Schema 常量 ----------

_BIBLE_SCHEMA = """\
{
  "logline": "一句话主线",
  "protagonist": {
    "name": "", "goal": "", "golden_finger": "",
    "bottom_line": "", "tone_tags": []
  },
  "antagonists": [
    {"name": "", "role": "", "threat": "", "tone_tags": []}
  ],
  "supporting": [
    {"name": "", "function": "", "tone_tags": []}
  ],
  "world_rules": ["..."],
  "core_conflicts": ["..."],
  "must_keep_setpieces": ["名场面1", "名场面2"],
  "adaptation_notes": ["改编注意"]
}"""

_PLAN_SCHEMA = """\
{
  "ep": 1,
  "core_goal": "本集一句话目标（推进主线）",
  "core_conflict": "本集核心冲突",
  "turn": "本集小反转/新信息",
  "highlight": "本集爽点/共情点",
  "scenes": [{
    "id": "1-1", "place": "", "time": "日/夜", "inout": "内/外",
    "characters": [""],
    "beats": ["按顺序列出镜头/动作/台词节点(5-10条)"]
  }],
  "end_hook": {
    "type": "冲突卡点/信息反转/危机升级/情感抉择",
    "last_image": "最后一镜",
    "last_line": "最后一句台词(如有)"
  }
}"""

_JUDGE_SCHEMA = """\
{
  "scores": {
    "open_hook": 0, "core_conflict": 0, "turn": 0,
    "highlight": 0, "rhythm": 0, "character": 0,
    "shootable": 0, "end_hook": 0, "safety": 0
  },
  "fatal_issues": ["必须改的问题(<=5条)"],
  "fix_list": [{
    "scene": "1-1",
    "line_hint": "引用原句片段",
    "problem": "",
    "fix": "给出可直接替换/新增的台词或动作(尽量短)"
  }],
  "hook_type": "冲突卡点/信息反转/危机升级/情感抉择/无",
  "summary": "一句话评价"
}"""

_JUDGE_DIMENSIONS = """\
- open_hook (开头钩子): 前30秒是否抛出冲突，是否勾住观众
- core_conflict (核心冲突): 是否有且仅有1个核心冲突，是否与主线相关
- turn (反转有效): 是否有小反转/新信息，是否出人意料又合理
- highlight (爽点共情): 是否有可视化的爽点或具体困境的共情点
- rhythm (节奏密度): 是否每10秒有记忆点，有无拖沓段落
- character (人物一致): 台词是否有辨识度，人设是否一致
- shootable (可拍性): 场景数/行数是否在范围内，动作是否可执行
- end_hook (结尾钩子强度): 是否有明确钩子类型，是否落在最后一镜/最后一句
- safety (合规风险): 是否有涉政/涉黄/涉赌/涉毒/极端血腥内容"""

_JUDGE_FOCUS = """\
- 致命问题不超过5条，聚焦最影响质量的问题
- fix_list 中的 fix 字段必须是可直接复制粘贴的替换内容
- 检查行数是否在合理范围内（总行数22-38，台词10-20，舞台指示8-20）
- 检查结尾是否有明确的钩子类型和视觉化呈现
- 检查是否有连续超过2行的OS/VO"""

# ---------- Write 阶段专用 ----------

_WRITE_FORMAT_RULES = """\
【格式要求】必须严格按以下结构输出（每行一个段落）：
1) 第X集（独占一行）
2) 场次行：X-N场  场景名\t日/夜\t内/外
3) 人物：A、B、C（紧跟场次行，顿号分隔）
4) 以"▲"开头的动作/镜头/字幕提示（短句、动词优先、强视觉）
5) 台词行：角色名：台词（全角冒号"："）；可带括号表演提示（2-4字）
6) VO/OS行标注清楚
7) 转场仅用：【切】【转】【闪回】【闪出】"""

_WRITE_RHYTHM_RULES = """\
- 开头30秒抛冲突，直接进入核心事件
- 每10秒有记忆点（冲突/信息/情绪/动作）
- 结尾按计划给强钩子（四选一），落在最后一镜或最后一句
- 心理描写必须视觉化：用动作（攥拳/咬唇）、表情特写、镜头语言替代内心独白"""

_WRITE_PROHIBITIONS = """\
- 禁止超过2句的纯环境描写
- 禁止连续OS/VO超过2行
- 禁止大段内心独白（OS仅用于简短点题，1-2句）
- 禁止书面语和文绉绉表达
- 禁止寒暄废话、重复已知信息
- 禁止所有角色说话语气相同（必须有辨识度）
- 禁止使用非标准转场标记"""

# ---------- Rewrite 阶段专用 ----------

_REWRITE_PRINCIPLES = """\
- 只改修改清单列出的问题，不要动其他部分
- 保持原有格式不变（集标题/场次行/人物行/▲前缀/全角冒号）
- 替换台词时保持角色语言风格一致
- 如果修改涉及删减行数，确保总行数仍在合理范围内
- 如果修改涉及新增台词/动作，确保不破坏节奏密度"""


# ---------- 辅助函数 ----------


def _build_format_rules(fmt: Dict) -> str:
    """从 format_spec dict 构建格式约束文本。"""
    markers = fmt.get("allowed_markers", ["【切】", "【转】", "【闪回】", "【闪出】"])
    ep_header = fmt.get("episode_header", "第{ep}集")
    scene_pattern = fmt.get("scene_header_pattern", "{ep}-{scene}场  {place}\t{日/夜}\t{内/外}")
    cast_prefix = fmt.get("cast_line_prefix", "人物：")
    stage_prefix = fmt.get("stage_direction_prefix", "▲")
    dialogue_pattern = fmt.get("dialogue_pattern", "{角色名}：{台词}")
    markers_str = " ".join(markers)
    return "\n".join([
        f"- 集标题：`{ep_header}`（独占一行）",
        f"- 场次行：`{scene_pattern}`",
        f"- 人物行：以`{cast_prefix}`开头（角色名用顿号分隔）",
        f"- 动作/镜头行：以`{stage_prefix}`开头（短句、强视觉、动词优先）",
        f"- 台词行：`{dialogue_pattern}`（全角冒号\u201c：\u201d）",
        "- VO/OS行：`VO：角色名（内容）` 或 `角色名OS：内容`",
        f"- 转场标记：仅允许 {markers_str}",
        "- 【闪回】和【闪出】必须成对出现，闪回内容不超过5行",
    ])


def _build_target_summary(target: Dict) -> str:
    """从 style_target dict 构建结构指标摘要。"""
    lines = []
    field_names = {
        "scenes_per_ep": "场景数/集",
        "total_lines_per_ep": "总行数/集",
        "dialogue_lines_per_ep": "台词行/集",
        "stage_lines_per_ep": "舞台指示行/集",
        "vo_os_lines_per_ep": "VO/OS行/集",
    }
    for key, label in field_names.items():
        v = target.get(key, {})
        if isinstance(v, dict):
            lines.append(f"- {label}：建议 {v.get('suggest')}，范围 {v.get('range')}")
    return "\n".join(lines)


def _build_genre_section(genre_data: Optional[Dict]) -> str:
    """从题材 dict 构建题材特定约束文本块。无题材时返回空字符串。"""
    if not genre_data or not isinstance(genre_data, dict):
        return ""

    genre_name = genre_data.get("genre", "未知题材")
    lines = [f"【题材特定约束（{genre_name}）】"]

    traits = genre_data.get("traits", [])
    if traits:
        lines.append(f"- 核心特征：{', '.join(traits)}")

    conflict_patterns = genre_data.get("conflict_patterns", [])
    if conflict_patterns:
        lines.append("- 冲突模式（优先使用）：")
        for cp in conflict_patterns:
            lines.append(f"  · {cp}")

    char_types = genre_data.get("character_types", [])
    if char_types:
        lines.append("- 角色类型参考：")
        for ct in char_types:
            role = ct.get("role", "")
            style = ct.get("speech_style", "")
            lines.append(f"  · {role}：{style}")

    iconic = genre_data.get("iconic_scenes", [])
    if iconic:
        lines.append(f"- 标志性场景（名场面参考）：{'; '.join(iconic)}")

    hooks = genre_data.get("hook_preferences", {})
    if hooks:
        lines.append(f"- 钩子偏好：主力={hooks.get('primary', '')}，辅助={hooks.get('secondary', '')}")
        notes = hooks.get("notes", "")
        if notes:
            lines.append(f"  说明：{notes}")

    overrides = genre_data.get("style_overrides", {})
    if overrides:
        for key, val in overrides.items():
            lines.append(f"- {key}：{val}")

    return "\n".join(lines)


def _build_hard_constraints(spec: EpisodeSpec) -> str:
    """从 EpisodeSpec 构建硬约束文本块。"""
    return "\n".join([
        "【硬约束】",
        f"- 单集时长：{spec.seconds_min}-{spec.seconds_max}秒",
        f"- 单集场数：{spec.scenes_range[0]}-{spec.scenes_range[1]}场",
        f"- 单集总行数（含动作/台词/提示）：{spec.total_lines_range[0]}-{spec.total_lines_range[1]}行",
        "- 开头30秒抛冲突；每10秒至少一个记忆点（冲突/信息/情绪/动作）",
        "- 每集结尾必须强钩子（四类之一），且在后续1-2集内回收并再埋新钩子",
    ])
