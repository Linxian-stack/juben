# Phase 03：新样例接入

## 目标
扩展 profile 命令，支持新题材样例一键接入：提供样例 DOCX → 自动统计 → 生成题材配置。

## 任务清单

- [ ] 扩展 `juben_gen/cli.py` 的 `profile` 子命令：
  ```
  juben profile \
    --scripts "scripts/新题材样例.docx" \
    --genre suspense \
    --output juben_gen/genres/suspense.json
  ```
- [ ] 实现自动统计 + 题材配置生成：
  1. 解析样例 DOCX，提取统计指标（复用 style_profile.py）
  2. 如果已有该题材配置，合并新样例数据（加权平均）
  3. 如果没有，生成新的题材配置模板
- [ ] 最低1个样例即可生成画像，2-3个效果更好
- [ ] 生成后提示用户手动补充题材特有字段（角色类型、冲突模式等）
- [ ] 更新 `juben_gen/README.md` 新增题材接入说明

## 输入
- 新题材样例 DOCX
- 题材名称

## 产出
- `juben_gen/cli.py`（扩展 profile 命令）
- 生成的题材配置 JSON

## 验收
- 1个样例即可生成画像
- 多样例合并正常
- 已有题材追加样例正常
- README 说明同步更新
