# Phase 02：风格画像参数化

## 目标
重构风格画像系统，通用指标统一，题材相关指标可配置，每个题材独立 JSON 配置。

## 任务清单

- [ ] 重构 `juben_gen/style_profile.py`：
  - 分离通用指标和题材指标
  - 通用指标：行数范围、台词比例、场景数（跨题材统一）
  - 题材指标：冲突类型权重、情绪曲线模式、特有元素频率
- [ ] 扩展 style_profile.json 结构：
  ```json
  {
    "universal": {
      "total_lines_per_ep": { "suggest": 28.1, "range": [22, 38] },
      "dialogue_lines_per_ep": { "suggest": 10.28, "range": [10, 20] },
      ...
    },
    "genre_specific": {
      "apocalypse": {
        "action_intensity": "high",
        "emotional_tone": "tense",
        ...
      }
    }
  }
  ```
- [ ] 更新 `build_combined_profile()` 支持题材参数
- [ ] 更新 constraints.py 的融合逻辑，注入题材参数
- [ ] 更新 prompts.py，在 prompt 中注入题材特定约束

## 输入
- `juben_gen/style_profile.py`
- `juben_gen/constraints.py`
- Phase 01 题材模板

## 产出
- `juben_gen/style_profile.py`（重构）
- 更新后的约束和 prompt 模块

## 验收
- 通用指标跨题材统一
- 题材指标可通过 JSON 配置
- 不同题材生成时应用不同参数
