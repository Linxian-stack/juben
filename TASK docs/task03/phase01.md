# Phase 01：Story Bible 生成

## 目标
实现小说→结构化 Story Bible 的生成模块，支持 TXT/DOCX 输入，用户指定章节范围。

## 任务清单

- [ ] 创建 `juben_gen/bible.py` 模块
- [ ] 实现小说加载逻辑：
  - TXT：复用 `text_io.py`（自动编码检测）
  - DOCX：复用 `docx_io.py`
- [ ] 实现章节选择：
  - 复用 `novel.py` 的 `split_chapters()` 和 `select_chapter_range()`
  - CLI 参数指定起止章节（如 `--chapters 1-30`）
- [ ] 调用 Claude API（bible 角色）生成 Story Bible
- [ ] 输出 JSON 结构：
  ```json
  {
    "logline": "一句话故事线",
    "protagonist": { "name": "", "traits": [], "arc": "" },
    "antagonist": { "name": "", "traits": [], "motivation": "" },
    "core_conflict": "",
    "key_scenes": [{ "chapter": 0, "description": "" }]
  }
  ```
- [ ] 保存 Bible JSON 到输出目录

## 输入
- 小说文件（TXT/DOCX）
- 章节范围参数

## 产出
- `juben_gen/bible.py`
- 输出 `{output_dir}/bible.json`

## 验收
- TXT 和 DOCX 均能正确加载
- 章节范围选择正常
- Bible JSON 结构完整
