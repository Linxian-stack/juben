# Phase 02：多轮审稿机制

## 目标
将校验器集成到 pipeline 中，校验不通过自动触发返修，默认最多3轮，记录每轮日志。

## 任务清单

- [ ] 创建 `juben_gen/review_loop.py` 模块
- [ ] 实现审稿循环逻辑：
  ```
  for round in range(max_rounds):
      validation = validator.validate_episode(script)
      if validation.passed:
          break
      review = judge.review_episode(script)
      script = rewriter.rewrite_episode(script, review)
  ```
- [ ] 集成 validator（Phase 01）+ judge（task03）+ rewriter（task03）
- [ ] 配置参数：
  - `max_rounds`: 默认3，可通过 config.json 配置
  - `pass_threshold`: 默认 overall >= 75
- [ ] 审稿日志记录：
  - 每轮记录：轮次、校验结果、评分、修改内容摘要
  - 保存到 `{output_dir}/reviews/ep{N}_log.json`
- [ ] 更新 `cli.py` 的 generate 命令，接入审稿循环

## 输入
- 剧本文本
- validator + judge + rewriter 模块

## 产出
- `juben_gen/review_loop.py`
- CLI 集成更新

## 验收
- 校验不通过自动触发返修
- 最多3轮限制有效
- 每轮日志完整记录
