# 部署说明（静态站点）

## 目录

将本目录 `web/` **原样上传** 到服务器或对象存储即可，无需 Node 构建。

```
web/
  index.html          # 单元目录
  unit.html           # 学习页（?u=1 … ?u=20）
  assets/css/app.css
  assets/js/app.js
  data/manifest.json
  data/units.json
  data/stories/unit-001.json
  manifest.webmanifest
```

## 本地预览

```powershell
cd vocab-stories\web
py -3 -m http.server 8080
```

手机与电脑同一 WiFi 下访问：`http://<电脑IP>:8080`

> 必须用 **http(s) 服务** 打开，不能直接双击 HTML（`fetch` 会失败）。

## 生产部署

### Nginx 示例

```nginx
server {
    listen 80;
    server_name vocab.example.com;
    root /var/www/vocab-stories/web;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }

    location ~* \.(json|css|js)$ {
        add_header Cache-Control "public, max-age=3600";
    }
}
```

### HTTPS

语音朗读在 iOS Safari 上建议启用 **HTTPS**，否则 `speechSynthesis` 可能受限。

## 美音朗读（推荐）

使用 **Microsoft 神经语音** 预生成 MP3（比浏览器自带 TTS 自然得多）：

```powershell
py -3 -m pip install edge-tts
py -3 scripts/generate_audio.py --unit 1
# 男声可选：py -3 scripts/generate_audio.py --unit 1 --voice en-US-GuyNeural
```

生成文件位于 `audio/unit-001/part-A.mp3` … `part-J.mp3`。部署时 **务必一并上传 `audio/` 目录**。

## 插图

每 Part 可在故事 JSON 中配置：

```json
"image": "assets/img/unit-001/part-A.svg",
"image_caption_zh": "中文图注，帮助理解本段场景"
```

Unit 001 已含 **电影写实风** PNG：`assets/img/unit-001/part-A.png` … `part-J.png`（每图约 1.6–2.5 MB）。部署时请上传 **`assets/img/`** 整目录。

生成新单元插图：使用写实电影剧照风格 prompt，保存为 `part-{id}.png` 并在故事 JSON 中设置 `image` 字段。

## 功能

| 功能 | 说明 |
|------|------|
| 移动端布局 | 大按钮、安全区、可调字号 |
| 点击生词 | 高亮词查看中文释义 |
| 朗读 | **优先 MP3 美音**；无 MP3 时回退浏览器 TTS |
| PWA | `manifest.webmanifest` 可「添加到主屏幕」 |

## 更新词表与故事

1. 在仓库根目录重跑聚类（每单元 200 词）  
2. 复制 `data/units.json` → `web/data/units.json`  
3. 更新 `web/data/manifest.json` 的 `ready` 字段  
4. 新增 `web/data/stories/unit-NNN.json`  

同步脚本（可选）：

```powershell
Copy-Item ..\data\units.json .\data\units.json -Force
```

## 后续单元

`unit-002` … `unit-020` 故事文件放入 `data/stories/` 后，将 `manifest.json` 中对应单元的 `ready` 设为 `true`。
