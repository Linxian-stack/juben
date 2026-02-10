from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from .docx_io import read_docx_lines


@dataclass(frozen=True)
class AdaptRules:
    rhythm_notes: str
    end_hook_notes: str
    card_template_notes: str


def load_rules_from_docx(
    *,
    rhythm_docx: str | Path,
    end_hook_docx: str | Path,
    template_docx: str | Path,
) -> AdaptRules:
    # 这些 docx 很短，直接拼成文本即可
    rhythm = "\n".join(read_docx_lines(rhythm_docx))
    end_hook = "\n".join(read_docx_lines(end_hook_docx))
    template = "\n".join(read_docx_lines(template_docx))

    return AdaptRules(
        rhythm_notes=rhythm,
        end_hook_notes=end_hook,
        card_template_notes=template,
    )


def redfruit_safety_notes() -> str:
    """
    红果向的一般化合规提醒（非平台官方条款复述，仅作写作约束）。
    """
    return "\n".join(
        [
            "合规约束（通用）：避免涉政、涉黄、涉赌、涉毒、极端暴力血腥、未成年人不当内容。",
            "镜头处理：能用“反应镜头/声音/切黑/道具特写”表达的，不直接描写血腥细节。",
            "价值导向：反派恶行要有后果，主角行动有正当动机，避免宣扬违法犯罪技巧。",
        ]
    )

