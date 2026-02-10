from __future__ import annotations

from pathlib import Path

from charset_normalizer import from_path


def read_text_auto(path: str | Path) -> str:
    """
    自动识别编码读取 txt。

    说明：
    - 你提供的《地狱游戏》为 gb18030
    - 《末世天灾》为 utf-8
    """
    p = Path(path)
    best = from_path(str(p)).best()
    if best is None:
        # 极端情况下兜底：当作 utf-8 读
        return p.read_text(encoding="utf-8", errors="ignore")
    # CharsetMatch.__str__ 会返回解码后的字符串（内部用 best.encoding）
    return str(best)

