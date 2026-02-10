# Ask02：架构升级 - Claude Only

## 基本信息
- **对应任务**：task02
- **依赖阶段**：Phase 1（经验沉淀）
- **被依赖于**：Phase 3（Pipeline补齐）

## 阶段目标
重构 juben_gen 架构，移除 OpenAI 依赖，全面切换到 Claude API，简化代码和配置。

## 包含步骤
> 状态标记：( ) 待细化 | (x) 已确认

- (x) **B1 LLM 客户端重构** — 产出：纯 Claude API 客户端
- (x) **B2 Prompt 模板优化** — 产出：针对 Claude 调优的 prompt 模板
- (x) **B3 配置系统简化** — 产出：简化后的配置文件和加载逻辑

## 已确认事项
- 完全移除 OpenAI 依赖
- 全部使用 Claude API（anthropic SDK）
- 保留多角色模型分配（bible/plan/write/judge/rewrite → 不同 Claude 模型）
- 利用 Claude extended thinking 能力

---

## (x) 步骤 B1：LLM 客户端重构

### Q1：Claude API 的调用方式？
**选择**：A. 直接用 anthropic SDK

### Q2：是否保留多角色模型分配？
**选择**：A. 保留角色概念，全部指向 Claude 不同模型（如 Opus/Sonnet）

### Q3：错误处理和重试策略？
**选择**：A. 简单重试（固定次数 + 退避）

---

## (x) 步骤 B2：Prompt 模板优化

### Q1：Prompt 优化的主要方向？
**选择**：A. 利用 Claude 的长上下文优势，增加样例注入

### Q2：是否引入 Claude 的特有能力？
**选择**：A. 使用 extended thinking（深度推理）用于规划和审稿

---

## (x) 步骤 B3：配置系统简化

### Q1：配置文件格式？
**选择**：A. 保持 JSON，简化字段

### Q2：API Key 管理方式？
**选择**：A. 环境变量（ANTHROPIC_API_KEY）

---

## 输出映射
完成细化 → `TASK docs/task02/`（plan.md + 3 个 phase 文件）✅ 已生成
