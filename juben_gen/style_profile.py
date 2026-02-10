from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .docx_io import read_docx_lines


FULL_COLON = "\uFF1A"  # ：
TRI = "\u25B2"  # ▲
LBR = "\u3010"  # 【
EP_PREFIX = "\u7B2C"  # 第
EP_SUFFIX = "\u96C6"  # 集
RENWU_PREFIX = "\u4EBA\u7269" + FULL_COLON  # 人物：


@dataclass(frozen=True)
class EpisodeStats:
    episode: int
    scenes: int
    total_lines: int
    dialogue_lines: int
    stage_lines: int
    vo_os_lines: int


@dataclass(frozen=True)
class ScriptStyleProfile:
    file: str
    episodes: int
    episode_range: Tuple[int, int]
    avg_scenes_per_ep: float
    avg_total_lines_per_ep: float
    avg_dialogue_lines_per_ep: float
    avg_stage_lines_per_ep: float
    avg_vo_os_lines_per_ep: float
    per_episode: List[EpisodeStats]


def _parse_episodes(lines: List[str]) -> Dict[int, List[str]]:
    ep_re = re.compile(r"^" + EP_PREFIX + r"(\d+)" + EP_SUFFIX)
    eps: Dict[int, List[str]] = {}
    current: Optional[int] = None

    for line in lines:
        m = ep_re.match(line.strip())
        if m:
            current = int(m.group(1))
            eps.setdefault(current, [])
            continue
        if current is None:
            continue
        eps[current].append(line)

    return eps


def _episode_stats(ep: int, ep_lines: List[str]) -> EpisodeStats:
    scene_re = re.compile(r"^(\d+)-(\d+)")

    scenes = 0
    dialogue = 0
    stage = 0
    vo_os = 0

    for line in ep_lines:
        s = line.strip()
        if not s:
            continue

        if scene_re.match(s):
            scenes += 1
            continue

        if s.startswith(RENWU_PREFIX):
            continue

        if s.startswith(TRI) or s.startswith(LBR):
            stage += 1
            continue

        # OS/VO 归到“舞台/镜头提示”类
        if s.startswith("VO") or ("VO" + FULL_COLON in s) or ("OS" in s):
            stage += 1
            vo_os += 1
            continue

        if FULL_COLON in s:
            dialogue += 1

    total = sum(1 for x in ep_lines if (x or "").strip())
    return EpisodeStats(
        episode=ep,
        scenes=scenes,
        total_lines=total,
        dialogue_lines=dialogue,
        stage_lines=stage,
        vo_os_lines=vo_os,
    )


def build_style_profile(docx_path: str | Path) -> ScriptStyleProfile:
    p = Path(docx_path)
    lines = read_docx_lines(p)
    eps = _parse_episodes(lines)
    if not eps:
        raise ValueError(f"未识别到“第N集”标记：{p}")

    per_ep = [_episode_stats(ep, eps[ep]) for ep in sorted(eps)]

    import statistics as st

    avg_scenes = float(st.mean(s.scenes for s in per_ep))
    avg_total = float(st.mean(s.total_lines for s in per_ep))
    avg_dialogue = float(st.mean(s.dialogue_lines for s in per_ep))
    avg_stage = float(st.mean(s.stage_lines for s in per_ep))
    avg_vo_os = float(st.mean(s.vo_os_lines for s in per_ep))

    return ScriptStyleProfile(
        file=p.name,
        episodes=len(per_ep),
        episode_range=(min(eps), max(eps)),
        avg_scenes_per_ep=avg_scenes,
        avg_total_lines_per_ep=avg_total,
        avg_dialogue_lines_per_ep=avg_dialogue,
        avg_stage_lines_per_ep=avg_stage,
        avg_vo_os_lines_per_ep=avg_vo_os,
        per_episode=per_ep,
    )


def build_combined_profile(
    docx_paths: List[Union[str, Path]],
    genre: Optional[str] = None,
) -> Dict[str, object]:
    """多个样例脚本合并成一个"目标区间"画像，方便给生成模型做硬约束。

    Parameters
    ----------
    docx_paths : 样例剧本路径列表
    genre : 题材标识（如 "apocalypse" 或 "末世"），提供时会附加题材层信息。
    """
    profiles = [build_style_profile(p) for p in docx_paths]

    def mean(xs: List[float]) -> float:
        return float(sum(xs) / max(1, len(xs)))

    universal = {
        "scenes_per_ep": {
            "suggest": round(mean([p.avg_scenes_per_ep for p in profiles]), 2),
            "range": [1, 3],
        },
        "total_lines_per_ep": {
            "suggest": round(mean([p.avg_total_lines_per_ep for p in profiles]), 2),
            "range": [22, 38],
        },
        "dialogue_lines_per_ep": {
            "suggest": round(mean([p.avg_dialogue_lines_per_ep for p in profiles]), 2),
            "range": [10, 20],
        },
        "stage_lines_per_ep": {
            "suggest": round(mean([p.avg_stage_lines_per_ep for p in profiles]), 2),
            "range": [8, 20],
        },
        "vo_os_lines_per_ep": {
            "suggest": round(mean([p.avg_vo_os_lines_per_ep for p in profiles]), 2),
            "range": [0, 6],
        },
    }

    result: Dict[str, object] = {
        "sources": [asdict(p) for p in profiles],
        "universal": universal,
        "target": universal,  # 向后兼容
    }

    # 附加题材层信息
    if genre:
        from .genres import load_genre
        genre_template = load_genre(genre)
        result["genre_specific"] = genre_template.to_dict()

    return result


def save_json(obj: object, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

