# Phase 03：剧本生成

## 目标
实现节拍表 → 完整剧本的逐集生成模块，每集注入前一集摘要保持连贯性，双格式输出。

## 任务清单

- [ ] 创建 `juben_gen/writer.py` 模块
- [ ] 实现逐集生成逻辑：
  - 加载节拍表 JSON
  - 逐集调用 Claude API（write 角色）
  - 第1集：注入节拍表 + 风格约束
  - 第2集起：注入节拍表 + 前一集摘要 + 风格约束
- [ ] 实现前集摘要生成：
  - 从上一集剧本中提取关键信息（角色状态、剧情进展、未解钩子）
  - 控制摘要长度（不超过 500 字）
- [ ] 双格式输出：
  - 纯文本：`{output_dir}/episodes/ep{N}.txt`
  - DOCX：`{output_dir}/episodes/ep{N}.docx`（复用 docx_io.py）
- [ ] 保存所有集的合并版本：
  - `{output_dir}/script_full.txt`
  - `{output_dir}/script_full.docx`

## 输入
- `{output_dir}/plan.json`
- `juben_gen/constraints.fused.json`

## 产出
- `juben_gen/writer.py`
- 输出分集 + 合并文件

## 验收
- 10集逐集生成正常
- 前集摘要注入保持剧情连贯
- TXT 和 DOCX 双输出
