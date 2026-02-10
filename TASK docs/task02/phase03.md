# Phase 03：配置系统简化

## 目标
简化配置系统，移除 OpenAI 相关字段，API Key 通过环境变量管理。

## 任务清单

- [ ] 阅读现有 `juben_gen/config.example.json`
- [ ] 简化配置结构：
  ```json
  {
    "roles": {
      "bible":   { "model": "claude-sonnet-4-20250514" },
      "plan":    { "model": "claude-sonnet-4-20250514", "thinking": true },
      "write":   { "model": "claude-sonnet-4-20250514" },
      "judge":   { "model": "claude-haiku-4-20250414", "thinking": true },
      "rewrite": { "model": "claude-sonnet-4-20250514" }
    },
    "retry": { "max_attempts": 3, "base_delay": 1.0 },
    "output": { "save_intermediates": true }
  }
  ```
- [ ] 移除 provider 字段（全部是 anthropic）
- [ ] API Key 通过 `ANTHROPIC_API_KEY` 环境变量读取
- [ ] 更新配置加载逻辑，适配新结构
- [ ] 更新 `juben_gen/README.md` 中的配置说明

## 输入
- `juben_gen/config.example.json`
- `juben_gen/cli.py`

## 产出
- `juben_gen/config.example.json`（简化）
- 配置加载逻辑更新

## 验收
- 无 OpenAI/provider 相关字段
- 环境变量读取 API Key
- README 配置说明同步更新
