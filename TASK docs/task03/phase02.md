# Phase 02：节拍表规划

## 目标
实现 Story Bible → 前10集节拍表的规划模块。

## 任务清单

- [ ] 创建 `juben_gen/planner.py` 模块
- [ ] 加载 Bible JSON 作为输入
- [ ] 加载风格约束（constraints.fused.json）
- [ ] 调用 Claude API（plan 角色，启用 extended thinking）
- [ ] 输出节拍表 JSON 数组：
  ```json
  [
    {
      "episode": 1,
      "core_conflict": "主要冲突描述",
      "reversal": "反转点",
      "highlight": "亮点/爽点",
      "scenes": [
        { "scene_num": 1, "location": "", "time": "", "description": "" }
      ],
      "end_hook": { "type": "冲突卡点钩|信息反转钩|危机升级钩|情感抉择钩", "content": "" }
    }
  ]
  ```
- [ ] 保存节拍表 JSON 到输出目录

## 输入
- `{output_dir}/bible.json`
- `juben_gen/constraints.fused.json`

## 产出
- `juben_gen/planner.py`
- 输出 `{output_dir}/plan.json`

## 验收
- 生成10集节拍表
- 每集包含冲突/反转/亮点/场景/钩子
- extended thinking 正常工作
