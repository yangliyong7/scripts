---
name: friends-learning-notes
description: >-
  Generates Friends episode learning notes in a fixed 6-section Chinese format.
  Use when the user asks for Friends learning notes, 口语笔记, notes/ generation,
  or wants to create or rewrite notes/Friends_*_Learning_Notes.md from a transcript.
---

# Friends 口语笔记生成

## 何时使用

用户要生成或改写 `notes/Friends_*_Learning_Notes.md` 时，**必须先读本 skill**，再读对应剧本。

## 工作流程

1. 找到对应 `docs/Friends_S{season}E{ep}_*.md` 剧本，通读台词。
2. 提取本集值得学的口语表达、俚语、固定搭配。
3. 按下方 **6 个分类** 归类（禁止按剧情线分节）。
4. 写入 `notes/Friends_S{season}E{ep}_{Title_Slug}_Learning_Notes.md`。

`Title_Slug` 与 `docs/` 中同名文件一致（如 `The_One_With_Ross_Sandwich`）。

## 文件标题

```markdown
# Friends S05E12 口语表达笔记
```

季集号与剧本一致。

## 章节结构（固定顺序，不得增删改）

只能使用以下 6 个小节标题，**禁止**用剧情主题作标题（如「Ross 三明治线」「皮裤灾难」）：

```markdown
## 1. 情绪与反应
## 2. 决策与行动
## 3. 社交与关系
## 4. 描述事物
## 5. 实用短句
## 6. 剧情词汇
```

### 分类指南

| 小节 | 放什么 |
|------|--------|
| 1. 情绪与反应 | 惊讶、愤怒、无奈、开心等情绪表达 |
| 2. 决策与行动 | 决定、计划、去做某事、拒绝、动手 |
| 3. 社交与关系 | 约会、吵架、暧昧、朋友互动、称呼、关系用语 |
| 4. 描述事物 | 形容人/物/状态/场景（含比喻、夸张） |
| 5. 实用短句 | 通用、可复用的整句或固定说法 |
| 6. 剧情词汇 | **专有名词**：人名、地名、道具、梗名、本集关键事物（不是短语） |

## 条目格式

每条一行起，格式如下（参考 `notes/Friends_S05E12_Learning_Notes.md`）：

```markdown
- **phrase**: 中文解释（简短，可加语境）。
  - *Example*: 台词例句，**关键短语**加粗。
```

规则：

- 解释用 **中文**，简练，风格对齐 E12。
- 有台词就写 `*Example*`；第 6 节通常 **不写** Example。
- 第 6 节格式：`- **名词**: 简短中文说明（本集语境）`
- 同一表达只出现一次，放在最合适的分类。

## 禁止事项

- ❌ 按剧情/角色/场景分节（如 `## 3. Phoebe 募捐`）
- ❌ 增加第 7 节或合并章节
- ❌ 在「剧情词汇」里写动词短语（应放 1–5 节）
- ❌ 不写剧本就编造例句

## 质量检查

生成后自检：

- [ ] 恰好 6 个小节，标题与顺序完全一致
- [ ] 每节至少 1 条（第 6 节 3–10 个剧情词为宜）
- [ ] 无剧情主题小节名
- [ ] 文件名与 `docs/` 季集号一致

## 参考样例

完整范例：`notes/Friends_S05E12_Learning_Notes.md`

## 用户偏好

- 解释简短，避免长篇大论。
- 用户问台词含义时，同样保持简短回答。
