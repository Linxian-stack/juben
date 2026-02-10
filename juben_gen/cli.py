from __future__ import annotations

import argparse
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="juben_gen")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_profile = sub.add_parser("profile", help="从样例剧本docx提取风格画像（JSON）")
    p_profile.add_argument("--scripts", nargs="+", required=True, help="样例剧本docx路径（可多个）")
    p_profile.add_argument("--out", required=True, help="输出JSON路径")
    p_profile.set_defaults(func=cmd_profile)

    p_constraints = sub.add_parser("constraints", help="融合样例剧本+注意事项，生成可执行约束（JSON+MD）")
    p_constraints.add_argument("--scripts", nargs="+", required=True, help="样例剧本docx路径（可多个）")
    p_constraints.add_argument("--rhythm", required=True, help="节奏适配注意事项 docx")
    p_constraints.add_argument("--end_hook", required=True, help="每集结尾钩子核心 docx")
    p_constraints.add_argument("--template", required=True, help="短剧一卡通用模板 docx")
    p_constraints.add_argument("--out_json", required=True, help="输出约束 JSON 路径")
    p_constraints.add_argument("--out_md", required=True, help="输出约束说明 MD 路径")
    p_constraints.set_defaults(func=cmd_constraints)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
