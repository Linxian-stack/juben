"""题材模板体系 — 通用层 + 题材层分层架构。

通用层（base.py）：红果风格核心规则、格式规范、评分标准。
题材层（*.json）：各题材独有的特征、角色类型、冲突模式、标志性场景。

用法::

    from juben_gen.genres import load_genre, list_genres, GenreTemplate

    # 列出所有可用题材
    genres = list_genres()  # ["apocalypse", "palace_drama", ...]

    # 加载指定题材
    genre = load_genre("apocalypse")
    print(genre.genre)          # "末世"
    print(genre.traits)         # ["生存压力", ...]
    print(genre.hook_primary)   # "危机升级"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# 题材 JSON 文件所在目录
_GENRE_DIR = Path(__file__).parent

# 内置题材名 -> 文件名映射
_BUILTIN_GENRES: Dict[str, str] = {
    "apocalypse": "apocalypse.json",
    "palace_drama": "palace_drama.json",
    "romance": "romance.json",
    "suspense": "suspense.json",
    "time_travel": "time_travel.json",
}

# 中文名 -> 英文名映射（方便用中文查找）
_CN_TO_EN: Dict[str, str] = {
    "末世": "apocalypse",
    "宫斗": "palace_drama",
    "甜宠": "romance",
    "悬疑": "suspense",
    "穿越": "time_travel",
}


# ── 数据结构 ──────────────────────────────────────────────────


@dataclass(frozen=True)
class CharacterType:
    """题材典型角色类型。"""
    role: str
    typical_traits: List[str]
    speech_style: str


@dataclass(frozen=True)
class HookPreferences:
    """题材钩子偏好。"""
    primary: str
    secondary: str
    notes: str


@dataclass(frozen=True)
class GenreTemplate:
    """题材模板，包含通用层不覆盖的题材专属信息。"""
    genre: str                          # 中文名
    genre_en: str                       # 英文标识
    traits: List[str]                   # 题材核心特征
    character_types: List[CharacterType]  # 典型角色类型
    conflict_patterns: List[str]        # 冲突模式
    iconic_scenes: List[str]            # 标志性场景
    hook_primary: str                   # 主力钩子类型
    hook_secondary: str                 # 辅助钩子类型
    hook_notes: str                     # 钩子使用说明
    style_overrides: Dict[str, str] = field(default_factory=dict)  # 风格覆盖

    def to_dict(self) -> Dict:
        """转为可序列化的 dict。"""
        return {
            "genre": self.genre,
            "genre_en": self.genre_en,
            "traits": self.traits,
            "character_types": [
                {
                    "role": ct.role,
                    "typical_traits": ct.typical_traits,
                    "speech_style": ct.speech_style,
                }
                for ct in self.character_types
            ],
            "conflict_patterns": self.conflict_patterns,
            "iconic_scenes": self.iconic_scenes,
            "hook_preferences": {
                "primary": self.hook_primary,
                "secondary": self.hook_secondary,
                "notes": self.hook_notes,
            },
            "style_overrides": self.style_overrides,
        }


# ── 加载逻辑 ──────────────────────────────────────────────────


def _parse_genre(data: Dict) -> GenreTemplate:
    """将 JSON dict 解析为 GenreTemplate。"""
    hooks = data.get("hook_preferences", {})
    return GenreTemplate(
        genre=data["genre"],
        genre_en=data["genre_en"],
        traits=data.get("traits", []),
        character_types=[
            CharacterType(
                role=ct["role"],
                typical_traits=ct.get("typical_traits", []),
                speech_style=ct.get("speech_style", ""),
            )
            for ct in data.get("character_types", [])
        ],
        conflict_patterns=data.get("conflict_patterns", []),
        iconic_scenes=data.get("iconic_scenes", []),
        hook_primary=hooks.get("primary", ""),
        hook_secondary=hooks.get("secondary", ""),
        hook_notes=hooks.get("notes", ""),
        style_overrides=data.get("style_overrides", {}),
    )


def load_genre(name: str) -> GenreTemplate:
    """加载题材模板。

    Parameters
    ----------
    name : 题材标识，支持英文名（apocalypse）或中文名（末世）。
           也可传入 JSON 文件路径（加载自定义题材）。

    Returns
    -------
    GenreTemplate

    Raises
    ------
    FileNotFoundError : 题材不存在
    """
    # 中文名转英文名
    en_name = _CN_TO_EN.get(name, name)

    # 内置题材
    if en_name in _BUILTIN_GENRES:
        json_path = _GENRE_DIR / _BUILTIN_GENRES[en_name]
    else:
        # 尝试作为文件路径
        json_path = Path(name)
        if not json_path.exists():
            # 尝试在 genres 目录下查找
            json_path = _GENRE_DIR / f"{en_name}.json"

    if not json_path.exists():
        available = ", ".join(sorted(_BUILTIN_GENRES.keys()))
        raise FileNotFoundError(
            f"题材 '{name}' 不存在。可用题材：{available}"
        )

    data = json.loads(json_path.read_text(encoding="utf-8"))
    return _parse_genre(data)


def list_genres() -> List[str]:
    """列出所有内置题材的英文标识。"""
    return sorted(_BUILTIN_GENRES.keys())


def list_genres_cn() -> Dict[str, str]:
    """返回 {中文名: 英文名} 的映射。"""
    return dict(_CN_TO_EN)
