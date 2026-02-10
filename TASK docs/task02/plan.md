# Task02：架构升级 - Claude Only

## 概要
重构 juben_gen，移除 OpenAI 依赖，全面切换到 Claude API（anthropic SDK），简化代码和配置。

## 依赖
- 前置：task01（方法论文档指导设计决策）
- 后续：task03（Pipeline 基于新架构构建）

## Phase 列表

| Phase | 文件 | 内容 | 产出物 |
|-------|------|------|--------|
| 01 | phase01.md | B1 LLM 客户端重构 | `juben_gen/llm_clients.py`（重写） |
| 02 | phase02.md | B2 Prompt 模板优化 | `juben_gen/prompts.py`（重写） |
| 03 | phase03.md | B3 配置系统简化 | `juben_gen/config.example.json`（简化） |

## 执行顺序
Phase 01 → 02 → 03（客户端先行，prompt 依赖客户端接口，配置最后调整）

## 进度追踪

- [x] phase01: B1 LLM 客户端重构
- [x] phase02: B2 Prompt 模板优化
- [x] phase03: B3 配置系统简化

## 验收标准
- OpenAI 相关代码和依赖完全移除
- anthropic SDK 客户端正常工作
- 5 个角色均可配置不同 Claude 模型
- extended thinking 可用于规划和审稿角色
- 简单重试机制（3次 + 指数退避）正常工作
