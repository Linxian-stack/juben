# Phase 05：返修循环

## 目标
实现评分不达标时的自动返修模块，整集重写，最多N轮。

## 任务清单

- [ ] 创建 `juben_gen/rewriter.py` 模块
- [ ] 实现返修逻辑：
  - 输入：原剧本 + 评分 JSON（含问题列表和修改建议）
  - 调用 Claude API（rewrite 角色）
  - 输出：重写后的剧本文本
- [ ] 实现循环控制：
  - 重写后再次调用 judge 评分
  - 达标（overall >= 阈值）则停止
  - 未达标继续重写，最多 N 轮（默认3轮，可配置）
  - 达到最大轮数仍未通过，保留最高分版本并警告
- [ ] 保存每轮中间结果：
  - `{output_dir}/reviews/ep{N}_round{M}.txt`
  - `{output_dir}/reviews/ep{N}_round{M}_review.json`

## 输入
- 剧本文本 + 评分 JSON

## 产出
- `juben_gen/rewriter.py`
- 中间结果文件

## 验收
- 评分不达标时自动触发重写
- 达标后立即停止
- 最大轮数限制有效
- 中间结果完整保存
