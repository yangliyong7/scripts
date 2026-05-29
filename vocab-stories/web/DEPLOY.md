# 部署说明（静态站点）

## 目录

将本目录 `web/` **原样上传** 到 Linux 服务器或对象存储即可，无需 Node 构建。

```
web/
  index.html
  unit.html
  assets/
  data/
  audio/          # 有美音 MP3 的单元
  start-server.sh # 仅本地预览，生产用 Nginx
```

## 生产部署（Linux + Nginx）

```bash
# 示例：上传到服务器
rsync -avz ./web/ user@your-server:/var/www/vocab-stories/web/

# 权限（按你站点用户调整，常见为 www-data）
sudo chown -R www-data:www-data /var/www/vocab-stories/web
```

### Nginx 配置示例

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

    location ~* \.(mp3|png|webp|svg)$ {
        add_header Cache-Control "public, max-age=86400";
    }
}
```

启用 HTTPS（推荐，iOS 朗读更稳定）：

```bash
sudo certbot --nginx -d vocab.example.com
```

> 生产环境 **不要用** `python -m http.server` 对外提供服务；用 Nginx / Caddy 等。

## 本地预览（Linux / macOS）

```bash
cd vocab-stories/web
chmod +x start-server.sh sync-data.sh
./start-server.sh
# 或指定端口：PORT=9000 ./start-server.sh
```

访问：`http://127.0.0.1:8080`（局域网用手机访问服务器 IP:8080）。

必须用 **HTTP 服务** 打开，不能直接双击 HTML（`fetch` 会失败）。

### Windows 本地预览（可选）

```powershell
cd vocab-stories\web
py -3 -m http.server 8080
```

## 美音 MP3（生成后上传）

```bash
pip install edge-tts
python3 scripts/generate_audio.py --unit 1
# 男声：python3 scripts/generate_audio.py --unit 1 --voice en-US-GuyNeural
```

输出：`audio/unit-001/part-A.mp3` … `part-J.mp3`。部署时务必上传整个 `audio/` 目录。

## 插图

Unit 001：`assets/img/unit-001/part-A.png` … `part-J.png`（电影写实风，体积较大，可按需转 WebP）。

故事 JSON 字段：

```json
"image": "assets/img/unit-001/part-A.png",
"image_caption_zh": "中文图注"
```

## 同步词表

```bash
./sync-data.sh
```

## 更新 manifest

新增故事后，编辑 `data/manifest.json`，将对应单元的 `ready` 设为 `true`。
