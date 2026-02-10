from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from .rules import AdaptRules, redfruit_safety_notes


@dataclass(frozen=True)
class EpisodeSpec:
    seconds_min: int = 60
    seconds_max: int = 120
    scenes_range: tuple = (1, 3)
    total_lines_range: tuple = (22, 38)


def build_system_prompt() -> str:
    return "\n".join(
        [
            "你是资深短剧编剧与改编策划，擅长把小说改写成1-2分钟/集的短剧剧本。",
            "输出必须信息密度高、冲突强、节奏快、结尾有钩子；不要写散文化小说。",
            "严格遵守用户提供的《节奏适配注意事项》《一卡通用模板》《结尾钩子核心》。",
            redfruit_safety_notes(),
        ]
    )


def prompt_story_bible(*, rules: AdaptRules, novel_excerpt: str) -> str:
    return "\n\n".join(
        [
            "【任务】阅读小说片段，抽取“改编用剧情圣经 story bible”（JSON）。",
            "【输出格式】只输出JSON，不要解释。字段：",
            "{"
            '"logline":"一句话主线",'
            '"protagonist":{"name":"","goal":"","golden_finger":"","bottom_line":"","tone_tags":[]},'
            '"antagonists":[{"name":"","role":"","threat":"","tone_tags":[]}],'
            '"supporting":[{"name":"","function":"","tone_tags":[]}],'
            '"world_rules":["..."],'
            '"core_conflicts":["..."],'
            '"must_keep_setpieces":["名场面1","名场面2"],'
            '"adaptation_notes":["改编注意"]'
            "}",
            "【参考规则：节奏适配关键注意事项】\n" + rules.rhythm_notes,
            "【小说片段】\n" + novel_excerpt,
        ]
    )


def prompt_plan_first10(
    *,
    rules: AdaptRules,
    style_target: Dict[str, object],
    bible_json: str,
    episode_spec: EpisodeSpec,
) -> str:
    return "\n\n".join(
        [
            "【任务】为红果短剧规划前10集“分集节拍表”（JSON数组）。每集1-2分钟。",
            "【硬约束】",
            f"- 单集时长：{episode_spec.seconds_min}-{episode_spec.seconds_max}秒",
            f"- 单集场数：{episode_spec.scenes_range[0]}-{episode_spec.scenes_range[1]}场",
            f"- 单集总行数（含动作/台词/提示）：{episode_spec.total_lines_range[0]}-{episode_spec.total_lines_range[1]}行",
            "- 开头30秒抛冲突；每10秒至少一个记忆点（冲突/信息/情绪/动作）。",
            "- 每集结尾必须强钩子（四类之一），且在后续1-2集内回收并再埋新钩子。",
            "【输出格式】只输出JSON数组，不要解释。每集对象字段：",
            "{"
            '"ep":1,'
            '"core_goal":"本集一句话目标（推进主线）",'
            '"core_conflict":"本集核心冲突",'
            '"turn":"本集小反转/新信息",'
            '"highlight":"本集爽点/共情点",'
            '"scenes":[{"id":"1-1","place":"","time":"日/夜","inout":"内/外","characters":[""],"beats":["按顺序列出镜头/动作/台词节点(5-10条)"]}],'
            '"end_hook":{"type":"冲突卡点/信息反转/危机升级/情感抉择","last_image":"最后一镜","last_line":"最后一句台词(如有)"}'
            "}",
            "【起承转合参考（前10集付费卡点）】\n" + rules.card_template_notes,
            "【结尾钩子方法】\n" + rules.end_hook_notes,
            "【样例风格目标（统计画像）】\n" + json.dumps(style_target, ensure_ascii=False, indent=2),
            "【story bible】\n" + bible_json,
        ]
    )


def prompt_write_episode(
    *,
    rules: AdaptRules,
    style_target: Dict[str, object],
    episode_plan_json: str,
) -> str:
    return "\n\n".join(
        [
            "【任务】根据“分集节拍表”，写出该集完整短剧剧本（纯文本），用于导出docx。",
            "【格式要求】必须严格按以下结构输出（每行一个段落）：",
            "1) 第X集",
            "2) 场次行：1-1场  场景名\t日/夜\t内/外",
            "3) 人物：A、B、C",
            "4) 以“▲”开头的动作/镜头/字幕提示（尽量视觉化）",
            "5) 台词行：角色名：台词；可用 OS/VO，但不要堆叠长内心。",
            "【节奏要求】开头30秒抛冲突；每10秒有记忆点；结尾按计划给强钩子。",
            "【参考规则：节奏适配关键注意事项】\n" + rules.rhythm_notes,
            "【样例风格目标（统计画像）】\n" + json.dumps(style_target, ensure_ascii=False, indent=2),
            "【分集节拍表JSON】\n" + episode_plan_json,
        ]
    )


def prompt_judge_episode(*, rules: AdaptRules, episode_script: str) -> str:
    return "\n\n".join(
        [
            "【任务】你是短剧审稿编辑，对该集剧本做量化打分与可执行修改清单（JSON）。",
            "【评分维度】每项0-5：开头钩子/核心冲突/反转有效/爽点共情/节奏密度/人物一致/可拍性/结尾钩子强度/合规风险。",
            "【输出格式】只输出JSON：",
            "{"
            '"scores":{"open_hook":0,"core_conflict":0,"turn":0,"highlight":0,"rhythm":0,"character":0,"shootable":0,"end_hook":0,"safety":0},'
            '"fatal_issues":["必须改的问题(<=5条)"],'
            '"fix_list":[{"scene":"1-1","line_hint":"引用原句片段","problem":"","fix":"给出可直接替换/新增的台词或动作(尽量短)"}],'
            '"hook_type":"冲突卡点/信息反转/危机升级/情感抉择/无",'
            '"summary":"一句话评价"'
            "}",
            "【参考规则：节奏适配关键注意事项】\n" + rules.rhythm_notes,
            "【结尾钩子方法】\n" + rules.end_hook_notes,
            "【剧本】\n" + episode_script,
        ]
    )


def prompt_rewrite_episode(*, fix_list_json: str, episode_script: str) -> str:
    return "\n\n".join(
        [
            "【任务】按“修改清单”对剧本做最小改动返修：只改列出的问题，不要重写整集。",
            "【输出】只输出返修后的完整剧本纯文本（同原格式）。",
            "【修改清单JSON】\n" + fix_list_json,
            "【原剧本】\n" + episode_script,
        ]
    )

