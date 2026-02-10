# Phase 04：AI 协作工作流

## 目标
编写完整的 AI 协作工作流文档，作为项目级 CLAUDE.md 的核心内容，包含全流程指南和可直接使用的 prompt 模板。

## 任务清单

- [ ] 阅读 `juben_gen/prompts.py` 提取现有 prompt 模板
- [ ] 分析 prompt_story_bible / prompt_plan_first10 / prompt_write_episode 三个核心 prompt
- [ ] 结合 Phase 01-03 产出的文档，设计全流程工作流
- [ ] 编写项目级 `CLAUDE.md`，包含：
  - 项目概述（一句话定位）
  - 目录结构说明
  - AI 协作工作流（全流程）
    - 选题阶段：小说筛选标准
    - 分析阶段：章节拆分 + Story Bible 提取
    - 规划阶段：分集节拍表设计
    - 生成阶段：逐集剧本创作
    - 审稿阶段：质量评估
    - 修订阶段：问题修复
  - Prompt 模板库
    - Story Bible 提取 prompt
    - 分集规划 prompt
    - 剧本生成 prompt
    - 审稿评分 prompt
    - 返修 prompt
  - 风格约束速查（引用 Phase 02 文档）
  - 格式规范速查（引用 Phase 03 文档）

## 输入
- `juben_gen/prompts.py`
- Phase 01-03 产出的文档
- `juben_gen/STYLE_GUIDE.fused.md`

## 产出
- `CLAUDE.md`（项目级，放在项目根目录）

## 验收
- Claude Code 打开项目时自动加载工作流
- prompt 模板可直接复制使用
- 全流程覆盖（选题→修订）
