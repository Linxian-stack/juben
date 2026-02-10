# Phase 01：LLM 客户端重构

## 目标
用 anthropic SDK 重写 LLM 客户端，移除 OpenAI 相关代码，保留多角色模型分配，支持简单重试。

## 任务清单

- [ ] 阅读现有 `juben_gen/llm_clients.py`（OpenAICompatClient + AnthropicClient）
- [ ] 移除 `OpenAICompatClient` 类及所有 OpenAI 相关代码
- [ ] 重写 `AnthropicClient`，使用 anthropic SDK：
  - 支持 messages API
  - 支持 extended thinking（budget_tokens 参数）
  - 统一返回 `LLMResponse` dataclass
- [ ] 实现角色→模型映射：
  - bible: Claude Sonnet（长上下文理解）
  - plan: Claude Sonnet + extended thinking（逻辑推导）
  - write: Claude Sonnet（格式精度）
  - judge: Claude Haiku（成本优化）
  - rewrite: Claude Sonnet（质量保证）
- [ ] 实现简单重试机制：
  - 最多3次重试
  - 指数退避（1s, 2s, 4s）
  - 捕获速率限制和网络错误
- [ ] 移除 requests 依赖（如果仅用于 OpenAI 调用）

## 输入
- `juben_gen/llm_clients.py`（现有代码）

## 产出
- `juben_gen/llm_clients.py`（重写）

## 验收
- 无 OpenAI 相关代码
- anthropic SDK 调用正常
- 5 个角色可分别配置不同 Claude 模型
- 重试机制正常工作
