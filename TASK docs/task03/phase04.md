# Phase 04：审稿评分

## 目标
实现自动审稿评分模块，从格式合规、节奏、冲突密度、钩子质量四个维度评分。

## 任务清单

- [ ] 创建 `juben_gen/judge.py` 模块
- [ ] 实现评分调用：
  - 调用 Claude API（judge 角色，启用 extended thinking）
  - 输入：单集剧本文本 + 节拍表中对应集的规划
- [ ] 输出评分 JSON：
  ```json
  {
    "episode": 1,
    "scores": {
      "format_compliance": 85,
      "rhythm": 70,
      "conflict_density": 80,
      "hook_quality": 75,
      "overall": 77.5
    },
    "issues": [
      { "type": "rhythm", "description": "第3场节奏过缓", "suggestion": "压缩对话，增加动作" }
    ],
    "pass": false
  }
  ```
- [ ] 评分阈值配置（默认 overall >= 75 通过）
- [ ] 保存评分 JSON：`{output_dir}/reviews/ep{N}_review.json`

## 输入
- 单集剧本文本
- 节拍表对应集

## 产出
- `juben_gen/judge.py`
- 输出评分 JSON

## 验收
- 4维度评分输出正常
- 问题列表有具体描述和修改建议
- 通过/不通过判定正确
