# Phase 01：题材模板体系

## 目标
建立通用层 + 题材层的分层模板体系，初期覆盖末世/宫斗/甜宠/悬疑/穿越 5 种题材。

## 任务清单

- [ ] 创建 `juben_gen/genres/` 目录结构：
  ```
  juben_gen/genres/
  ├── __init__.py
  ├── base.py              # 通用层（红果风格规则）
  ├── apocalypse.json      # 末世
  ├── palace_drama.json    # 宫斗
  ├── romance.json         # 甜宠
  ├── suspense.json        # 悬疑
  └── time_travel.json     # 穿越
  ```
- [ ] 定义通用层（`base.py`）：
  - 红果风格核心规则（冲突密度、钩子机制、节奏标准）
  - 通用格式规范
  - 通用评分标准
- [ ] 定义题材模板 JSON 结构：
  ```json
  {
    "genre": "末世",
    "traits": ["生存压力", "资源争夺", "人性考验"],
    "character_types": [
      { "role": "主角", "typical_traits": ["坚韧", "智慧", "有金手指"] },
      { "role": "反派", "typical_traits": ["贪婪", "强权", "阴险"] }
    ],
    "conflict_patterns": ["生存威胁", "资源争夺", "背叛", "救赎"],
    "iconic_scenes": ["末世降临", "首次危机", "基地建设", "反派对峙"],
    "style_overrides": {}
  }
  ```
- [ ] 编写 5 种题材的模板文件
- [ ] 实现题材加载逻辑：`load_genre(name) -> GenreTemplate`

## 输入
- 现有样例分析经验
- 红果风格创作规则文档

## 产出
- `juben_gen/genres/` 目录及全部文件

## 验收
- 5 种题材模板完整
- 通用层和题材层分离清晰
- 加载逻辑正常
