from __future__ import annotations

import argparse
import json
import logging
import traceback
from pathlib import Path

from .style_profile import build_combined_profile, save_json
from .constraints import save_constraints


def cmd_profile(args: argparse.Namespace) -> int:
    genre = getattr(args, "genre", None)
    profile = build_combined_profile(args.scripts, genre=genre)
    save_json(profile, args.out)
    print(f"OK: {args.out}")
    return 0


def cmd_constraints(args: argparse.Namespace) -> int:
    genre = getattr(args, "genre", None)
    save_constraints(
        scripts=args.scripts,
        rhythm_docx=args.rhythm,
        end_hook_docx=args.end_hook,
        template_docx=args.template,
        out_json=args.out_json,
        out_md=args.out_md,
        genre=genre,
    )
    print(f"OK: {args.out_json}")
    print(f"OK: {args.out_md}")
    return 0


def cmd_write(args: argparse.Namespace) -> int:
    from .writer import generate_all_episodes
    from .config import maybe_load_config
    from .rules import load_rules_from_docx

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config = maybe_load_config(args.config)
    rules = load_rules_from_docx(
        rhythm_docx=args.rhythm,
        end_hook_docx=args.end_hook,
        template_docx=args.template,
    )

    episodes = generate_all_episodes(
        plan_path=args.plan,
        rules=rules,
        config=config,
        constraints_path=args.constraints,
        output_dir=args.out,
    )
    print(f"OK: {len(episodes)} 集剧本已生成 -> {args.out}")

    # 可选：自动审稿循环
    if getattr(args, "review", False):
        from .review_loop import review_all_episodes

        ep_dir = str(Path(args.out) / "episodes")
        results = review_all_episodes(
            episodes_dir=ep_dir,
            plan_path=args.plan,
            rules=rules,
            config=config,
            constraints_path=args.constraints,
            output_dir=args.out,
            pass_threshold=args.threshold,
            max_rounds=args.max_rounds,
        )
        passed = sum(1 for r in results if r.get("pass", False))
        print(f"OK: 审稿完成 {passed}/{len(results)} 集通过")

    return 0


def cmd_review(args: argparse.Namespace) -> int:
    from .review_loop import review_all_episodes
    from .config import maybe_load_config
    from .rules import load_rules_from_docx

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    config = maybe_load_config(args.config)
    rules = load_rules_from_docx(
        rhythm_docx=args.rhythm,
        end_hook_docx=args.end_hook,
        template_docx=args.template,
    )

    results = review_all_episodes(
        episodes_dir=args.episodes,
        plan_path=args.plan,
        rules=rules,
        config=config,
        constraints_path=args.constraints,
        output_dir=args.out,
        pass_threshold=args.threshold,
        max_rounds=args.max_rounds,
    )

    passed = sum(1 for r in results if r.get("pass", False))
    total = len(results)
    print(f"OK: 审稿完成 {passed}/{total} 集通过（最多 {args.max_rounds} 轮）")
    return 0 if passed == total else 1


def cmd_generate(args: argparse.Namespace) -> int:
    """一键执行全流程：bible → plan → write → review。"""
    from .bible import generate_bible, save_bible
    from .planner import generate_plan, save_plan
    from .writer import generate_all_episodes
    from .review_loop import review_all_episodes
    from .config import maybe_load_config
    from .rules import load_rules_from_docx

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger = logging.getLogger(__name__)

    config = maybe_load_config(args.config)
    rules = load_rules_from_docx(
        rhythm_docx=args.rhythm,
        end_hook_docx=args.end_hook,
        template_docx=args.template,
    )

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    chapter_start, chapter_end = _parse_chapter_range(args.chapters)
    failed_steps: list[str] = []

    # ── 步骤 1/5：Story Bible ──
    bible_path = out_dir / "bible.json"
    print(f"\n{'='*50}")
    print(f"[1/5] 生成 Story Bible（第{chapter_start}-{chapter_end}章）")
    print(f"{'='*50}")

    try:
        bible = generate_bible(
            novel_path=args.novel,
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            rules=rules,
            config=config,
            constraints_path=args.constraints,
        )
        save_bible(bible, bible_path)
        print(f"  ✓ Bible 已保存: {bible_path}")
        print(f"  logline: {bible.get('logline', '(无)')[:80]}")
    except Exception as e:
        logger.error("Story Bible 生成失败: %s", e)
        traceback.print_exc()
        print(f"\n✗ 全流程中断：Story Bible 生成失败，后续步骤依赖此输出")
        return 1

    # ── 步骤 2/5：节拍表 ──
    plan_path = out_dir / "plan.json"
    print(f"\n{'='*50}")
    print(f"[2/5] 生成节拍表")
    print(f"{'='*50}")

    try:
        plan = generate_plan(
            bible_path=bible_path,
            rules=rules,
            config=config,
            constraints_path=args.constraints,
        )
        save_plan(plan, plan_path)
        print(f"  ✓ 节拍表已保存: {plan_path}（{len(plan)} 集）")
    except Exception as e:
        logger.error("节拍表生成失败: %s", e)
        traceback.print_exc()
        print(f"\n✗ 全流程中断：节拍表生成失败，后续步骤依赖此输出")
        return 1

    # ── 步骤 3/5：逐集剧本生成 ──
    print(f"\n{'='*50}")
    print(f"[3/5] 逐集生成剧本（共 {len(plan)} 集）")
    print(f"{'='*50}")

    try:
        episodes = generate_all_episodes(
            plan_path=plan_path,
            rules=rules,
            config=config,
            constraints_path=args.constraints,
            output_dir=str(out_dir),
        )
        print(f"  ✓ {len(episodes)} 集剧本已生成 -> {out_dir}/episodes/")
    except Exception as e:
        logger.error("剧本生成失败: %s", e)
        traceback.print_exc()
        print(f"\n✗ 剧本生成失败")
        failed_steps.append("剧本生成")
        episodes = []

    # ── 步骤 4/5：审稿循环（可选跳过） ──
    if args.skip_review:
        print(f"\n{'='*50}")
        print(f"[4/5] 审稿循环（已跳过 --skip-review）")
        print(f"{'='*50}")
    elif not episodes:
        print(f"\n{'='*50}")
        print(f"[4/5] 审稿循环（跳过：无剧本可审）")
        print(f"{'='*50}")
    else:
        print(f"\n{'='*50}")
        print(f"[4/5] 审稿循环（{len(episodes)} 集，最多 {args.max_rounds} 轮）")
        print(f"{'='*50}")

        try:
            ep_dir = str(out_dir / "episodes")
            results = review_all_episodes(
                episodes_dir=ep_dir,
                plan_path=str(plan_path),
                rules=rules,
                config=config,
                constraints_path=args.constraints,
                output_dir=str(out_dir),
                pass_threshold=args.threshold,
                max_rounds=args.max_rounds,
            )
            passed = sum(1 for r in results if r.get("pass", False))
            total = len(results)
            print(f"  ✓ 审稿完成: {passed}/{total} 集通过")

            # 保存审稿汇总
            summary_path = out_dir / "review_summary.json"
            summary_path.write_text(
                json.dumps(results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"  ✓ 审稿汇总: {summary_path}")
        except Exception as e:
            logger.error("审稿循环失败: %s", e)
            traceback.print_exc()
            failed_steps.append("审稿循环")

    # ── 步骤 5/5：样例对比评估 ──
    eval_report_path = None
    if episodes:
        print(f"\n{'='*50}")
        print(f"[5/5] 样例对比评估")
        print(f"{'='*50}")

        try:
            from .evaluator import evaluate_script, load_target as eval_load_target
            from .evaluator import format_report_md, save_report

            # 读取合并版剧本
            full_txt = out_dir / "script_full.txt"
            if full_txt.exists():
                script_text = full_txt.read_text(encoding="utf-8")
            else:
                # 回退：拼接各集 txt
                ep_dir = out_dir / "episodes"
                ep_files = sorted(ep_dir.glob("ep*.txt"))
                script_text = "\n".join(f.read_text(encoding="utf-8") for f in ep_files)

            eval_target = eval_load_target(args.constraints.replace(
                "constraints.fused.json", "style_profile.json"
            ) if hasattr(args, "constraints") else "juben_gen/style_profile.json")
            report = evaluate_script(script_text, eval_target)
            eval_report_path = save_report(report, str(out_dir))
            print(format_report_md(report))
            print(f"  ✓ 评估报告已保存: {eval_report_path}")
        except Exception as e:
            logger.error("样例对比评估失败: %s", e)
            traceback.print_exc()
            failed_steps.append("样例对比评估")
    else:
        print(f"\n{'='*50}")
        print(f"[5/5] 样例对比评估（跳过：无剧本可评估）")
        print(f"{'='*50}")

    # ── 汇总 ──
    print(f"\n{'='*50}")
    if failed_steps:
        print(f"⚠ 全流程完成（部分失败）: {', '.join(failed_steps)}")
    else:
        print(f"✓ 全流程完成")
    print(f"  输出目录: {out_dir}")
    print(f"  中间产物: bible.json, plan.json")
    print(f"  剧本文件: episodes/ep*.txt + episodes/ep*.docx")
    print(f"  合并版本: script_full.txt + script_full.docx")
    if not args.skip_review and episodes:
        print(f"  审稿日志: reviews/")
    if eval_report_path:
        print(f"  评估报告: {eval_report_path}")
    print(f"{'='*50}")

    return 1 if failed_steps else 0


def cmd_validate(args: argparse.Namespace) -> int:
    import json as json_mod
    from .validator import validate_script, load_target, format_report

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"文件不存在：{script_path}")
        return 1

    text = script_path.read_text(encoding="utf-8")
    target = load_target(args.profile)
    results = validate_script(text, target)

    if args.json:
        print(json_mod.dumps(
            [r.to_dict() for r in results],
            ensure_ascii=False,
            indent=2,
        ))
    else:
        print(format_report(results))

    return 0 if all(r.passed for r in results) else 1


def cmd_evaluate(args: argparse.Namespace) -> int:
    """对生成剧本做样例对比评估。"""
    from .evaluator import evaluate_script, load_target as eval_load_target
    from .evaluator import format_report_md, save_report

    script_path = Path(args.script)
    if not script_path.exists():
        print(f"文件不存在：{script_path}")
        return 1

    text = script_path.read_text(encoding="utf-8")
    target = eval_load_target(args.profile)
    report = evaluate_script(text, target)

    print(format_report_md(report))

    if args.out:
        rp = save_report(report, args.out)
        print(f"报告已保存: {rp}")

    return 0 if report.all_in_range else 1


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

    # generate（全流程）
    p_gen = sub.add_parser("generate", help="一键执行全流程：小说→Bible→节拍表→剧本→审稿")
    p_gen.add_argument("--novel", required=True, help="小说文件路径（TXT/DOCX）")
    p_gen.add_argument("--chapters", required=True, help="章节范围，如 '1-30'")
    p_gen.add_argument("--rhythm", required=True, help="节奏适配注意事项 docx")
    p_gen.add_argument("--end_hook", required=True, help="每集结尾钩子核心 docx")
    p_gen.add_argument("--template", required=True, help="短剧一卡通用模板 docx")
    p_gen.add_argument("--constraints", default="juben_gen/constraints.fused.json", help="融合约束 JSON 路径")
    p_gen.add_argument("--config", default=None, help="配置文件路径")
    p_gen.add_argument("--output", required=True, help="输出目录路径")
    p_gen.add_argument("--max-rounds", type=int, default=3, help="审稿最大轮数（默认3）")
    p_gen.add_argument("--threshold", type=float, default=75.0, help="审稿通过阈值（默认75）")
    p_gen.add_argument("--skip-review", action="store_true", help="跳过审稿循环")
    p_gen.set_defaults(func=cmd_generate)

    # profile
    p_profile = sub.add_parser("profile", help="从样例剧本docx提取风格画像（JSON）")
    p_profile.add_argument("--scripts", nargs="+", required=True, help="样例剧本docx路径（可多个）")
    p_profile.add_argument("--genre", default=None, help="题材标识（如 apocalypse/末世），附加题材层信息")
    p_profile.add_argument("--out", required=True, help="输出JSON路径")
    p_profile.set_defaults(func=cmd_profile)

    # constraints
    p_constraints = sub.add_parser("constraints", help="融合样例剧本+注意事项，生成可执行约束（JSON+MD）")
    p_constraints.add_argument("--scripts", nargs="+", required=True, help="样例剧本docx路径（可多个）")
    p_constraints.add_argument("--rhythm", required=True, help="节奏适配注意事项 docx")
    p_constraints.add_argument("--end_hook", required=True, help="每集结尾钩子核心 docx")
    p_constraints.add_argument("--template", required=True, help="短剧一卡通用模板 docx")
    p_constraints.add_argument("--genre", default=None, help="题材标识（如 apocalypse/末世），融合题材约束")
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

    # write
    p_write = sub.add_parser("write", help="从节拍表逐集生成剧本（TXT+DOCX）")
    p_write.add_argument("--plan", required=True, help="节拍表 JSON 路径")
    p_write.add_argument("--rhythm", required=True, help="节奏适配注意事项 docx")
    p_write.add_argument("--end_hook", required=True, help="每集结尾钩子核心 docx")
    p_write.add_argument("--template", required=True, help="短剧一卡通用模板 docx")
    p_write.add_argument("--constraints", default="juben_gen/constraints.fused.json", help="融合约束 JSON 路径")
    p_write.add_argument("--config", default=None, help="配置文件路径")
    p_write.add_argument("--out", required=True, help="输出目录路径")
    p_write.add_argument("--review", action="store_true", help="生成后自动执行审稿循环")
    p_write.add_argument("--max-rounds", type=int, default=3, help="审稿最大轮数（默认3）")
    p_write.add_argument("--threshold", type=float, default=75.0, help="审稿通过阈值（默认75）")
    p_write.set_defaults(func=cmd_write)

    # validate
    p_validate = sub.add_parser("validate", help="校验剧本格式/行数/比例")
    p_validate.add_argument("script", help="剧本 TXT 文件路径")
    p_validate.add_argument("--profile", default="juben_gen/style_profile.json", help="风格画像 JSON 路径")
    p_validate.add_argument("--json", action="store_true", help="输出 JSON 格式")
    p_validate.set_defaults(func=cmd_validate)

    # evaluate
    p_eval = sub.add_parser("evaluate", help="样例对比评估：生成剧本 vs 样例均值")
    p_eval.add_argument("script", help="剧本 TXT 文件路径")
    p_eval.add_argument("--profile", default="juben_gen/style_profile.json", help="风格画像 JSON 路径")
    p_eval.add_argument("--out", default=None, help="报告输出目录（可选）")
    p_eval.set_defaults(func=cmd_evaluate)

    # review
    p_review = sub.add_parser("review", help="对已生成的剧本执行审稿循环（校验+评分+返修）")
    p_review.add_argument("--episodes", required=True, help="剧本目录（含 ep1.txt, ep2.txt, ...）")
    p_review.add_argument("--plan", default=None, help="节拍表 JSON 路径（可选，提供时加入评审上下文）")
    p_review.add_argument("--rhythm", required=True, help="节奏适配注意事项 docx")
    p_review.add_argument("--end_hook", required=True, help="每集结尾钩子核心 docx")
    p_review.add_argument("--template", required=True, help="短剧一卡通用模板 docx")
    p_review.add_argument("--constraints", default="juben_gen/constraints.fused.json", help="融合约束 JSON 路径")
    p_review.add_argument("--config", default=None, help="配置文件路径")
    p_review.add_argument("--out", required=True, help="输出目录路径")
    p_review.add_argument("--max-rounds", type=int, default=3, help="最大返修轮数（默认3）")
    p_review.add_argument("--threshold", type=float, default=75.0, help="通过阈值（默认75）")
    p_review.set_defaults(func=cmd_review)

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
