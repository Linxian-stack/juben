# Phase 06：CLI 集成

## 目标
扩展 CLI，增加统一的 `generate` 命令，串联全流程，自动保存所有中间 JSON。

## 任务清单

- [ ] 扩展 `juben_gen/cli.py`，新增 `generate` 子命令
- [ ] 命令参数设计：
  ```
  juben generate \
    --novel "novels/我宫斗冠军.txt" \
    --chapters 1-30 \
    --config config.json \
    --output output/宫斗冠军/
  ```
- [ ] 实现全流程编排：
  1. 加载小说 + 拆分章节
  2. 生成 Story Bible → 保存 `bible.json`
  3. 生成节拍表 → 保存 `plan.json`
  4. 逐集生成剧本 → 保存分集文件
  5. 逐集审稿评分 → 保存评分 JSON
  6. 不达标自动返修 → 保存返修结果
  7. 合并最终版本 → 保存 `script_full.txt/docx`
- [ ] 进度输出（当前处理到第几集、第几轮返修）
- [ ] 错误处理（API 调用失败不中断全流程，跳过失败集并报告）
- [ ] 保留现有 `profile` 和 `constraints` 子命令

## 输入
- CLI 参数

## 产出
- `juben_gen/cli.py`（扩展）

## 验收
- `generate` 命令一键执行全流程
- 所有中间 JSON 自动保存到输出目录
- 进度输出清晰
- 兼容现有子命令
