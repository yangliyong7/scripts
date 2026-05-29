# Vocab Stories · 通用词库故事学习

基于 `study.txt` 全库聚类编故事，服务 **可理解输入（i+1）** 与 **精听精读**。

## 规模

| 项目 | 数量 |
|------|------|
| 词条总数 | **3920** |
| 每单元词数 | **200**（最后一单元 **120**） |
| 故事篇数 | **20** |

计算：\(3920 \div 200 = 19\) 篇满编 + 1 篇收尾（120 词）。

## 原则

- 先按 **主题 / 近义 / 同类** 聚类，再按顺序每 **200** 词切成一个单元；**每个词只出现一次**。
- 单元内可含多个主题（见 `index.md` 标注「××等（N类）」）；词形提示见 `data/units.json` 中的 `morph` 字段。
- 原创人物与情节，与仓库其他材料无关。

## 目录

| 路径 | 说明 |
|------|------|
| `data/vocab.json` | 全库解析 |
| `data/clusters.json` | 单元元数据 |
| `data/units.json` | 每单元 200 词表 |
| `data/word_to_unit.json` | 词号 → 单元 |
| `index.md` | 20 篇索引 |
| `units/unit-NNN.md` | 学习正文（Markdown，可选） |
| **`web/`** | **手机端网页版（可部署）** |

## 重新生成索引（每单元 200 词）

```powershell
py -3 "$env:TEMP\vc_200fix.py"
```

（脚本由聚类逻辑生成；亦可从本仓库维护的 builder 运行。）

## 网页版（推荐手机使用）

**Linux 本地预览：**

```bash
cd vocab-stories/web
chmod +x start-server.sh
./start-server.sh
```

**生产部署：** 将 `web/` 用 Nginx 托管，见 `web/DEPLOY.md`（不要用 `.ps1`，那是 Windows 专用）。

- **unit-001** 已含完整故事（10 Part）+ TTS 朗读 + 词表抽屉  
- unit-002～020：词表可用，故事待补充（`manifest.json` 中 `ready: false`）

## 学习步骤（每单元）

1. 读中文梗概 → 2. 分章读/听 Story（建议按 Part 拆分精听）→ 3. 做题 → 4. 精读句 → 5. 复述  

**说明：** 200 词/篇建议拆成 **8～12 个小 Part**，每 Part 精听一遍，避免信息过载。
