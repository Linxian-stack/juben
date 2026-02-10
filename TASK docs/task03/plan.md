# Task03：Pipeline 补齐 - 端到端流水线

## 概要
实现完整的「小说→剧本」自动化流水线：bible → plan → write → judge → rewrite，支持 CLI 一键执行。

## 依赖
- 前置：task02（Claude Only 架构）
- 后续：task04（质量控制基于 pipeline 输出）

## Phase 列表

| Phase | 文件 | 内容 | 产出物 |
|-------|------|------|--------|
| 01 | phase01.md | C1 Story Bible 生成 | `juben_gen/bible.py` |
| 02 | phase02.md | C2 节拍表规划 | `juben_gen/planner.py` |
| 03 | phase03.md | C3 剧本生成 | `juben_gen/writer.py` |
| 04 | phase04.md | C4 审稿评分 | `juben_gen/judge.py` |
| 05 | phase05.md | C5 返修循环 | `juben_gen/rewriter.py` |
| 06 | phase06.md | C6 CLI 集成 | `juben_gen/cli.py`（扩展） |

## 执行顺序
Phase 01 → 02 → 03 → 04 → 05 → 06（流水线各环节按顺序实现，最后 CLI 串联）

## 验收标准
- 单一 `generate` 命令可执行全流程
- 输入：小说 TXT/DOCX + 章节范围
- 输出：剧本 TXT + DOCX + 全部中间 JSON
- 每集注入前一集摘要保持连贯性
- 评分低于阈值自动触发整集重写
