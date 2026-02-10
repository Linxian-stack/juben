from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .text_io import read_text_auto


@dataclass(frozen=True)
class Chapter:
    index: int  # 第N章
    title: str  # 原始章节标题行
    text: str   # 章节正文（不含标题行）


_CHAPTER_RE = re.compile(r"^第(\d+)章[\\s\\u3000]*(.*)$")


def split_chapters(novel_text: str) -> List[Chapter]:
    """
    按 “第N章” 拆分章节。
    """
    lines = novel_text.splitlines()

    starts: List[Tuple[int, int, str]] = []
    for i, line in enumerate(lines):
        m = _CHAPTER_RE.match(line.strip())
        if not m:
            continue
        idx = int(m.group(1))
        starts.append((i, idx, line.strip()))

    if not starts:
        return []

    chapters: List[Chapter] = []
    for k, (start_i, idx, title_line) in enumerate(starts):
        end_i = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start_i + 1 : end_i]).strip()
        chapters.append(Chapter(index=idx, title=title_line, text=body))
    return chapters


def load_chapters(path: str | Path) -> List[Chapter]:
    return split_chapters(read_text_auto(path))


def select_chapter_range(chapters: List[Chapter], start: int, end: int) -> List[Chapter]:
    """
    选择闭区间 [start, end] 章节。
    """
    chosen = [c for c in chapters if start <= c.index <= end]
    return sorted(chosen, key=lambda c: c.index)

