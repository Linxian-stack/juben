# Phase 02：Prompt 模板优化

## 目标
针对 Claude 特点重新调优所有 prompt 模板，利用长上下文注入更多样例，规划和审稿角色启用 extended thinking。

## 任务清单

- [ ] 阅读现有 `juben_gen/prompts.py` 所有模板
- [ ] 优化 `build_system_prompt()`：
  - 注入更详细的风格约束（利用 Claude 长上下文）
  - 注入样例剧本片段作为 few-shot 示例
- [ ] 优化 `prompt_story_bible()`：
  - 增加样例 Bible JSON 作为参考
  - 利用长上下文注入更多小说章节
- [ ] 优化 `prompt_plan_first10()`：
  - 标记为 extended thinking 角色
  - 注入样例节拍表作为参考
- [ ] 优化 `prompt_write_episode()`：
  - 注入样例剧本片段（格式参考）
  - 强化格式约束指令
- [ ] 新增 `prompt_judge_episode()` 和 `prompt_rewrite_episode()`
  - judge 使用 extended thinking 深度评估
  - rewrite 接收评分和修改建议

## 输入
- `juben_gen/prompts.py`（现有代码）
- task01 Phase 02 产出的创作规则
- task01 Phase 03 产出的格式规范

## 产出
- `juben_gen/prompts.py`（重写）

## 验收
- 所有 prompt 模板针对 Claude 优化
- 长上下文样例注入机制就绪
- extended thinking 标记正确
