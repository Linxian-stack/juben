# juben_gen：小说 → 红果风格短剧剧本（1-2分钟/集）

一句话定位：**用“样例驱动的量化约束 + 红果节奏规则 + 可复制的 Prompt 模板”把小说稳定改编成可导出 DOCX 的短剧剧本。**

---

## 目录结构（你需要关注的部分）

- `novels/`：原始小说（txt/docx 等）
- `scripts/`：优秀样例剧本（docx）+ 3 份注意事项 docx（节奏/结尾钩子/一卡模板）
- `docs/`：方法论文档（样例分析、红果规则、格式规范）
- `juben_gen/`：Python 工具与 Prompt 组装
  - `prompts.py`：本项目核心 Prompt 模板库（bible / plan / write / judge / rewrite）
  - `style_profile.py`：从样例剧本统计“目标画像”
  - `constraints.py`：融合样例 + 注意事项，生成可执行约束（JSON+MD）
  - `docx_io.py`：读写 docx（逐行）
- `TASK docs/`：任务分解与执行计划

---

## AI 协作工作流（选题 → 修订）

> 建议原则：**先约束后创作**。先把“结构指标/格式/节奏钩子”固定，再写内容，最后用审稿 JSON 做闭环返修。

### 0) 准备约束（一次性）

你至少需要两类输入：

1) **风格画像（结构指标）**：每集场数/总行数/台词与动作比例  
2) **规则文本**：节奏注意事项 + 结尾钩子方法 + 一卡通用模板

仓库已提供融合产物：
- `juben_gen/style_profile.json`（样例画像）
- `juben_gen/STYLE_GUIDE.fused.md`（速查版）
- `juben_gen/constraints.fused.json`（画像 + 格式 spec + 规则全文）

如需重新生成（可选）：
```powershell
# 1) 样例画像（JSON）
python -m juben_gen.cli profile `
  --scripts "scripts/样例1.docx" "scripts/样例2.docx" `
  --out "juben_gen/style_profile.json"

# 2) 可执行约束（JSON + MD）
python -m juben_gen.cli constraints `
  --scripts "scripts/样例1.docx" "scripts/样例2.docx" `
  --rhythm "scripts/节奏适配关键注意事项.docx" `
  --end_hook "scripts/每集结尾钩子核心.docx" `
  --template "scripts/短剧一卡通用模板.docx" `
  --out_json "juben_gen/constraints.fused.json" `
  --out_md "juben_gen/STYLE_GUIDE.fused.md"
```

### 1) 选题阶段：小说筛选标准（先判断“能不能拍/好不好追”）

优先选择满足以下条件的小说（越多越好）：

- **主线单一**：一句话说清主角核心目标（复仇/求生/夺回/翻身/救人）
- **冲突密集**：能拆成 10-20 个“小冲突”，每集解决 1 个
- **金手指明确**：系统/重生记忆/身份/资源/强关系（甜宠=男主）
- **名场面充足**：打脸、当众揭穿、身份暴露、反杀、救人等可视化高光
- **可控世界观**：不要一上来就是复杂群像/宏大设定/长时间铺垫
- **合规可拍**：避开涉政/涉黄/涉赌/涉毒/极端血腥等（见下方合规速查）

输出（给后续阶段用）：  
`一句话 logline + 主角目标 + 反派威胁 + 3个可拍名场面 + 10集内可达成的阶段性成果`

### 2) 分析阶段：章节拆分 + Story Bible（JSON）

目标：把原著“能写成短剧”的信息抽成结构化圣经，后续规划/写作都以它为准。

输入建议：
- 给 **章节范围**（例如第 1-10 章），再给一个 **足够长的片段**（建议 3k-10k 字）
- 避免整本喂给模型：宁可分段、多轮提取

输出：只要一份 `story bible JSON`（见下方模板）

### 3) 规划阶段：前10集分集节拍表（JSON 数组）

目标：把“大冲突”拆成可拍的 10 集节拍表，并且每集都满足红果硬规则。

硬约束（默认值，来自样例融合）：
- 单集时长：60-120 秒
- 单集场数：1-3 场（建议 1.7）
- 单集总行数：22-38 行（建议 28.1）
- 开头 30 秒抛冲突；每 10 秒至少 1 个记忆点
- 结尾必须强钩子（四选一），并在后续 1-2 集内回收

输出：`[{ep, core_goal, core_conflict, turn, highlight, scenes, end_hook}, ...]`

### 4) 生成阶段：逐集剧本创作（纯文本）

目标：按节拍表逐集写剧本，**严格遵守格式**（便于导出 docx & 后续校验器）。

建议做法：
1. 一次只写一集（更稳、更易审稿）
2. 每集写完立刻跑“自查清单”（见下方格式/风格速查）

### 5) 审稿阶段：质量评估（JSON）

目标：用“量化评分 + 可执行修改清单”驱动返修闭环，避免只给泛泛意见。

输出：只要审稿 JSON（见下方模板），特别关注：
- 致命问题（`fatal_issues` <= 5 条）
- 可直接替换/新增的台词或动作（`fix_list[].fix` 要可复制）

### 6) 修订阶段：最小改动返修（纯文本）

目标：**只改审稿清单列出的问题**，避免跑题和重写整集。

返修后建议复审一轮；若评分仍低于阈值，再考虑“整集重写”（但先确保节拍表没问题）。

---

## Prompt 模板库（可直接复制）

> 这些模板与 `juben_gen/prompts.py` 保持一致（少量占位符改成可手填）。

### 1) Story Bible 提取（只输出 JSON）

```text
【任务】阅读小说片段，抽取“改编用剧情圣经 story bible”（JSON）。
【输出格式】只输出JSON，不要解释。字段：
{"logline":"一句话主线","protagonist":{"name":"","goal":"","golden_finger":"","bottom_line":"","tone_tags":[]},"antagonists":[{"name":"","role":"","threat":"","tone_tags":[]}],"supporting":[{"name":"","function":"","tone_tags":[]}],"world_rules":["..."],"core_conflicts":["..."],"must_keep_setpieces":["名场面1","名场面2"],"adaptation_notes":["改编注意"]}

【参考规则：节奏适配关键注意事项】
（粘贴 constraints.fused.json → rules_text.rhythm_notes，或引用 docs/红果风格创作规则.md 的节奏部分）

【小说片段】
（粘贴章节文本）
```

### 2) 前10集分集节拍表（只输出 JSON 数组）

```text
【任务】为红果短剧规划前10集“分集节拍表”（JSON数组）。每集1-2分钟。
【硬约束】
- 单集时长：60-120秒
- 单集场数：1-3场
- 单集总行数（含动作/台词/提示）：22-38行
- 开头30秒抛冲突；每10秒至少一个记忆点（冲突/信息/情绪/动作）。
- 每集结尾必须强钩子（四类之一），且在后续1-2集内回收并再埋新钩子。

【输出格式】只输出JSON数组，不要解释。每集对象字段：
{"ep":1,"core_goal":"本集一句话目标（推进主线）","core_conflict":"本集核心冲突","turn":"本集小反转/新信息","highlight":"本集爽点/共情点","scenes":[{"id":"1-1","place":"","time":"日/夜","inout":"内/外","characters":[""],"beats":["按顺序列出镜头/动作/台词节点(5-10条)"]}],"end_hook":{"type":"冲突卡点/信息反转/危机升级/情感抉择","last_image":"最后一镜","last_line":"最后一句台词(如有)"}}

【起承转合参考（前10集付费卡点）】
（粘贴 constraints.fused.json → rules_text.card_template_notes）

【结尾钩子方法】
（粘贴 constraints.fused.json → rules_text.end_hook_notes）

【样例风格目标（统计画像）】
（粘贴 constraints.fused.json → style_target；或粘贴 juben_gen/style_profile.json → target）

【story bible】
（粘贴上一步输出的 bible JSON）
```

### 3) 单集剧本生成（输出纯文本剧本）

```text
【任务】根据“分集节拍表”，写出该集完整短剧剧本（纯文本），用于导出docx。
【格式要求】必须严格按以下结构输出（每行一个段落）：
1) 第X集
2) 场次行：1-1场  场景名\t日/夜\t内/外
3) 人物：A、B、C
4) 以“▲”开头的动作/镜头/字幕提示（尽量视觉化）
5) 台词行：角色名：台词；可用 OS/VO，但不要堆叠长内心。

【节奏要求】开头30秒抛冲突；每10秒有记忆点；结尾按计划给强钩子。

【参考规则：节奏适配关键注意事项】
（粘贴 constraints.fused.json → rules_text.rhythm_notes）

【样例风格目标（统计画像）】
（粘贴 constraints.fused.json → style_target）

【分集节拍表JSON】
（粘贴该集 plan JSON）
```

### 4) 审稿评分（只输出 JSON）

```text
【任务】你是短剧审稿编辑，对该集剧本做量化打分与可执行修改清单（JSON）。
【评分维度】每项0-5：开头钩子/核心冲突/反转有效/爽点共情/节奏密度/人物一致/可拍性/结尾钩子强度/合规风险。
【输出格式】只输出JSON：
{"scores":{"open_hook":0,"core_conflict":0,"turn":0,"highlight":0,"rhythm":0,"character":0,"shootable":0,"end_hook":0,"safety":0},"fatal_issues":["必须改的问题(<=5条)"],"fix_list":[{"scene":"1-1","line_hint":"引用原句片段","problem":"","fix":"给出可直接替换/新增的台词或动作(尽量短)"}],"hook_type":"冲突卡点/信息反转/危机升级/情感抉择/无","summary":"一句话评价"}

【参考规则：节奏适配关键注意事项】
（粘贴 constraints.fused.json → rules_text.rhythm_notes）

【结尾钩子方法】
（粘贴 constraints.fused.json → rules_text.end_hook_notes）

【剧本】
（粘贴该集剧本文本）
```

### 5) 最小返修（输出返修后的完整剧本）

```text
【任务】按“修改清单”对剧本做最小改动返修：只改列出的问题，不要重写整集。
【输出】只输出返修后的完整剧本纯文本（同原格式）。

【修改清单JSON】
（粘贴审稿输出 fix_list）

【原剧本】
（粘贴原剧本）
```

---

## 风格约束速查（更详细见 `docs/红果风格创作规则.md`）

- **开篇即冲突**：前 30 秒抛核心冲突，禁止慢热铺垫
- **10 秒记忆点**：冲突/信息/情绪/动作至少其一
- **每集六要素**：钩住 → 核心冲突 → 小反转/新信息 → 爽点/共情点 → 结尾强钩子
- **钩子四选一**：冲突卡点 / 信息反转 / 危机升级 / 情感抉择（落在最后一镜/最后一句）
- **信息差驱动**：冲突来自“知道 vs 不知道”，避免巧合与降智
- **合规底线**：避开涉政/涉黄/涉赌/涉毒/极端血腥；能切黑不直描（参考 `juben_gen/rules.py:redfruit_safety_notes`）

---

## 格式规范速查（更详细见 `docs/剧本格式规范.md`）

> 目标：可导出 docx + 便于脚本校验（后续会有 validator）。

必须满足：
- 集标题：`第{ep}集`（独占一行）
- 场次行：`{ep}-{scene}场  {place}\t{日/夜}\t{内/外}`
- 人物行：`人物：A、B、C`（顿号分隔）
- 动作/镜头：`▲...`（短句、强视觉）
- 台词：`角色名：台词`（**全角冒号**“：”）
- 允许转场：`【切】` `【转】` `【闪回】` `【闪出】`

结构指标（建议值/范围，来自样例融合）：
- 场景数/集：建议 1.7，范围 [1, 3]
- 总行数/集：建议 28.1，范围 [22, 38]
- 台词行/集：建议 10.28，范围 [10, 20]
- 动作行/集：建议 14.23，范围 [8, 20]
- VO/OS 行/集：建议 4.34，范围 [0, 6]

