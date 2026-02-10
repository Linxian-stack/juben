# Phase 01：输出校验器

## 目标
实现纯 Python 规则校验器，检查格式合规 + 行数范围 + 台词/舞台指示比例，输出通过/不通过 + 问题列表。

## 任务清单

- [ ] 创建 `juben_gen/validator.py` 模块
- [ ] 实现格式合规检查：
  - 集标题格式：`第{N}集`
  - 场次行格式：`{ep}-{scene}场  {place}\t{time}\t{in_out}`
  - 人物行格式：`人物：`开头
  - 动作行格式：`▲` 开头
  - 台词行格式：`{角色名}：{台词}`
  - 转场标记：在允许集合内
- [ ] 实现行数范围检查（基于 style_profile.json 的 target）：
  - 总行数：[22, 38]
  - 台词行：[10, 20]
  - 舞台指示行：[8, 20]
  - 旁白行：[0, 6]
  - 场景数：[1, 3]
- [ ] 实现比例检查：
  - 台词/总行数比例
  - 舞台指示/总行数比例
- [ ] 输出结果格式：
  ```python
  @dataclass
  class ValidationResult:
      passed: bool
      issues: list[ValidationIssue]  # type, line_num, description

  def validate_episode(text: str, profile: dict) -> ValidationResult
  ```

## 输入
- 剧本文本
- `juben_gen/style_profile.json`

## 产出
- `juben_gen/validator.py`

## 验收
- 格式/行数/比例三类检查均实现
- 输出清晰的问题列表（含行号和描述）
