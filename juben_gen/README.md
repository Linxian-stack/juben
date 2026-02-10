# juben_gen（MVP）

把小说改编成 **红果风格** 的 **1-2分钟/集** 短剧剧本，并输出 **docx**。

## 你当前这套样例的“目标画像”

已从两份样例剧本统计得到：`juben_gen/style_profile.json`  
建议先按该画像做硬约束（单集场数、行数、台词/动作比例等）。

## 命令

### 1) 从样例剧本提取风格画像

```powershell
python -m juben_gen.cli profile `
  --scripts "末世天灾，我靠吞金超市躺赢.docx" "地狱游戏：开局获得预知羊皮纸1216(1).docx" `
  --out "juben_gen/style_profile.json"
```

## 配置（Claude）

### 1) 设置 API Key（环境变量）

> 配置文件 **不存** API Key，请用环境变量 `ANTHROPIC_API_KEY`。

```powershell
$env:ANTHROPIC_API_KEY = "YOUR_KEY"
# 可选：自定义 API Base URL（如代理/私有网关）
$env:ANTHROPIC_BASE_URL = "https://api.anthropic.com"
```

### 2) 准备 config.json（可选）

将 `juben_gen/config.example.json` 复制为 `juben_gen/config.json`，按需调整模型分配与重试参数：

```json
{
  "roles": {
    "bible":   { "model": "claude-sonnet-4-20250514" },
    "plan":    { "model": "claude-sonnet-4-20250514", "thinking": true },
    "write":   { "model": "claude-sonnet-4-20250514" },
    "judge":   { "model": "claude-haiku-4-20250414",  "thinking": true },
    "rewrite": { "model": "claude-sonnet-4-20250514" }
  },
  "retry": { "max_attempts": 3, "base_delay": 1.0 },
  "output": { "save_intermediates": true }
}
```

## 多模型流水线建议（落盘 JSON，便于复盘）

1. **结构化（模型A，长文理解）**：小说片段 -> story bible（JSON）
2. **前10集节拍表（模型A）**：按“一卡模板+结尾钩子”规划 1-10 集（JSON）
3. **写剧本（模型B，格式化输出）**：节拍表 -> 剧本纯文本 -> 导出 docx
4. **审稿打分（模型C，独立评审）**：量化评分 + 可执行修改清单（JSON）
5. **最小返修（模型B/A）**：只按修改清单返修，避免跑题

> 代码里已准备：规则读取（3份注意事项docx）、风格画像、prompt 组装与 Claude（anthropic SDK）客户端。
