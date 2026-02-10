from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .style_profile import build_combined_profile, save_json
from .constraints import save_constraints


def cmd_profile(args: argparse.Namespace) -> int:
    profile = build_combined_profile(args.scripts)
    save_json(profile, args.out)
    print(f"OK: {args.out}")
    return 0


def cmd_constraints(args: argparse.Namespace) -> int:
    save_constraints(
        scripts=args.scripts,
        rhythm_docx=args.rhythm,
        end_hook_docx=args.end_hook,
        template_docx=args.template,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    print(f"OK: {args.out_json}")
    print(f"OK: {args.out_md}")
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    from .planner import generate_plan, save_plan
    from .config import maybe_load_config
    from .rules import load_rules_from_docx

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config = maybe_load_config(args.config)
    rules = load_rules_from_docx(
        rhythm_docx=args.rhythm,
        end_hook_docx=args.end_hook,
        template_docx=args.template,
    )

    plan = generate_plan(
        bible_path=args.bible,
        rules=rules,
        config=config,
        constraints_path=args.constraints,
    )
    out = save_plan(plan, args.out)
    print(f"OK: {out}")
    return 0


def cmd_bible(args: argparse.Namespace) -> int:
    from .bible import generate_bible, save_bible
    from .config import maybe_load_config
    from .rules import load_rules_from_docx

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config = maybe_load_config(args.config)
    rules = load_rules_from_docx(
        rhythm_docx=args.rhythm,
        end_hook_docx=args.end_hook,
        template_docx=args.template,
    )

    bible = generate_bible(
        novel_path=args.novel,
        chapter_start=args.chapter_start,
        chapter_end=args.chapter_end,
        rules=rules,
        config=config,
        constraints_path=args.constraints,
    )
    out = save_bible(bible, args.out)
    print(f"OK: {out}")
    return 0


def _parse_chapter_range(value: str) -> tuple[int, int]:
    """解析章节范围字符串，如 '1-30'。"""
    parts = value.split("-")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"章节范围格式应为 'start-end'，如 '1-30'，实际输入：{value}")
    try:
        start, end = int(parts[0]), int(parts[1])
    except ValueError:
        raise argparse.ArgumentTypeError(f"章节范围必须是整数，实际输入：{value}")
    if start > end:
        raise argparse.ArgumentTypeError(f"起始章节不能大于结束章节：{start} > {end}")
    return start, end


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="juben_gen")
    sub = p.add_subparsers(dest="cmd", required=True)

    # profile
    p_profile = sub.add_parser("profile", help="从样例剧本docx提取风格画像（JSON）")
    p_profile.add_argument("--scripts", nargs="+", required=True, help="样例剧本docx路径（可多个）")
    p_profile.add_argument("--out", required=True, help="输出JSON路径")
    p_profile.set_defaults(func=cmd_profile)

    # constraints
    p_constraints = sub.add_parser("constraints", help="融合样例剧本+注意事项，生成可执行约束（JSON+MD）")
    p_constraints.add_argument("--scripts", nargs="+", required=True, help="样例剧本docx路径（可多个）")
    p_constraints.add_argument("--rhythm", required=True, help="节奏适配注意事项 docx")
    p_constraints.add_argument("--end_hook", required=True, help="每集结尾钩子核心 docx")
    p_constraints.add_argument("--template", required=True, help="短剧一卡通用模板 docx")
    p_constraints.add_argument("--out_json", required=True, help="输出约束 JSON 路径")
    p_constraints.add_argument("--out_md", required=True, help="输出约束说明 MD 路径")
    p_constraints.set_defaults(func=cmd_constraints)

    # bible
    p_bible = sub.add_parser("bible", help="从小说片段生成 Story Bible（JSON）")
    p_bible.add_argument("--novel", required=True, help="小说文件路径（TXT/DOCX）")
    p_bible.add_argument("--chapters", required=True, help="章节范围，如 '1-30'")
    p_bible.add_argument("--rhythm", required=True, help="节奏适配注意事项 docx")
    p_bible.add_argument("--end_hook", required=True, help="每集结尾钩子核心 docx")
    p_bible.add_argument("--template", required=True, help="短剧一卡通用模板 docx")
    p_bible.add_argument("--constraints", default="juben_gen/constraints.fused.json", help="融合约束 JSON 路径")
    p_bible.add_argument("--config", default=None, help="配置文件路径")
    p_bible.add_argument("--out", required=True, help="输出 Bible JSON 路径")
    p_bible.set_defaults(func=lambda args: _cmd_bible_wrapper(args))

    # plan
    p_plan = sub.add_parser("plan", help="从 Story Bible 生成前10集节拍表（JSON）")
    p_plan.add_argument("--bible", required=True, help="Bible JSON 路径")
    p_plan.add_argument("--rhythm", required=True, help="节奏适配注意事项 docx")
    p_plan.add_argument("--end_hook", required=True, help="每集结尾钩子核心 docx")
    p_plan.add_argument("--template", required=True, help="短剧一卡通用模板 docx")
    p_plan.add_argument("--constraints", default="juben_gen/constraints.fused.json", help="融合约束 JSON 路径")
    p_plan.add_argument("--config", default=None, help="配置文件路径")
    p_plan.add_argument("--out", required=True, help="输出节拍表 JSON 路径")
    p_plan.set_defaults(func=cmd_plan)

    return p


def _cmd_bible_wrapper(args: argparse.Namespace) -> int:
    """解析 chapters 参数并调用 cmd_bible。"""
    start, end = _parse_chapter_range(args.chapters)
    args.chapter_start = start
    args.chapter_end = end
    return cmd_bible(args)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
