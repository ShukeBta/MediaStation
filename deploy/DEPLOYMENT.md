# MediaStation 部署指南

本文档详细介绍 MediaStation 的各种部署方式，支持多种操作系统和平台。

## 目录

- [快速部署](#快速部署)
- [Docker Compose 部署](#docker-compose-部署)
- [Kubernetes Helm 部署](#kubernetes-helm-部署)
- [Linux 一键部署](#linux-一键部署)
- [Windows 部署](#windows-部署)
- [群晖 (Synology) 部署](#群晖-synology-部署)
- [威联通 (QNAP) 部署](#威联通-qnap-部署)
- [Unraid 部署](#unraid-部署)
- [TrueNAS Scale 部署](#truenas-scale-部署)
- [macOS 部署](#macos-部署)
- [裸机部署](#裸机部署)

---

## 快速部署

### Docker Compose（一行命令）

```bash
# Linux/macOS
curl -fsSL https://raw.githubusercontent.com/your-repo/mediastation/main/deploy/scripts/install-linux.sh | bash

# Windows (PowerShell 以管理员身份运行)
irm https://raw.githubusercontent.com/your-repo/mediastation/main/deploy/scripts/install-windows.ps1 | iex
```

---

## Docker Compose 部署

### 前置要求

- Docker 20.10+
- Docker Compose v2+

### 部署步骤

```bash
# 1. 克隆项目
git clone https://github.com/your-repo/mediastation.git
cd mediastation

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，修改 TMDB_API_KEY（必填）

# 3. 启动服务
docker compose up -d

# 4. 查看状态
docker compose ps

# 5. 查看日志
docker compose logs -f
```

访问 `http://localhost:3001`，默认账号 `admin` / `admin123`。

### 完整版配置

包含 PostgreSQL、Redis、qBittorrent 等可选服务：

```bash
# 使用完整配置
docker compose -f docker-compose.full.yml up -d
```

---

## Kubernetes Helm 部署

### 前置要求

- Kubernetes 1.24+
- Helm 3.8+
- PV 供应器（用于持久化存储）

### 部署步骤

```bash
# 1. 添加 Helm 仓库
helm repo add mediastation https://your-repo.github.io/charts
helm repo update

# 2. 创建命名空间
kubectl create namespace mediastation

# 3. 安装 Chart
helm install mediastation mediastation/mediastation \
  --namespace mediastation \
  --set secret.TMDB_API_KEY=your-api-key \
  --set persistence.mediaDirs.movies.hostPath=/mnt/media/movies \
  --set persistence.mediaDirs.tv.hostPath=/mnt/media/tv \
  --set persistence.mediaDirs.downloads.hostPath=/mnt/downloads

# 4. 查看部署状态
kubectl -n mediastation get pods
kubectl -n mediastation get svc
```

### 使用自定义 values 文件

```bash
# 创建 values 文件
cat > my-values.yaml << 'EOF'
replicaCount: 2

image:
  repository: mediastation/mediastation
  tag: latest

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: mediastation.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: mediastation-tls
      hosts:
        - mediastation.example.com

secret:
  TMDB_API_KEY: your-api-key

persistence:
  mediaDirs:
    movies:
      enabled: true
      hostPath: /data/media/movies
    tv:
      enabled: true
      hostPath: /data/media/tv
    downloads:
      enabled: true
      hostPath: /data/downloads

resources:
  limits:
    cpu: 2000m
    memory: 2Gi
  requests:
    cpu: 100m
    memory: 256Mi

gpu:
  enabled: false
EOF

# 安装
helm install mediastation mediastation/mediastation \
  --namespace mediastation \
  --values my-values.yaml
```

---

## Linux 一键部署

### 支持的系统

- Ubuntu 18.04+ / Debian 10+
- CentOS 7+ / RHEL 7+
- Fedora 34+
- Arch Linux

### 部署步骤

```bash
# 方式一：直接运行（推荐）
curl -fsSL https://raw.githubusercontent.com/your-repo/mediastation/main/deploy/scripts/install-linux.sh | bash

# 方式二：下载脚本后运行
wget https://raw.githubusercontent.com/your-repo/mediastation/main/deploy/scripts/install-linux.sh
chmod +x install-linux.sh
./install-linux.sh
```

### 脚本功能

1. 自动检测操作系统
2. 安装 Docker 和 Docker Compose（如未安装）
3. 创建必要的目录结构
4. 下载配置文件
5. 交互式配置（API Key 等）
6. 启动服务
7. 可选：创建 systemd 服务（开机自启）

### 常用命令

```bash
# 查看状态
systemctl status mediastation

# 查看日志
journalctl -u mediastation -f

# 停止服务
systemctl stop mediastation

# 重启服务
systemctl restart mediastation
```

---

## Windows 部署

### 支持的版本

- Windows 10/11
- Windows Server 2019+

### 前置要求

- Docker Desktop for Windows
- WSL 2（推荐）

### 部署步骤

1. **安装 Docker Desktop**
   - 下载地址：https://www.docker.com/products/docker-desktop
   - 启用 WSL 2 后端

2. **下载安装脚本**
   ```powershell
   # 以管理员身份打开 PowerShell
   irm https://raw.githubusercontent.com/your-repo/mediastation/main/deploy/scripts/install-windows.ps1 -OutFile install-mediasation.ps1
   .\install-mediasation.ps1
   ```

3. **配置并启动**
   - 脚本会自动下载配置
   - 输入 TMDb API Key
   - 等待服务启动

### 手动部署

```powershell
# 1. 克隆项目
git clone https://github.com/your-repo/mediastation.git
cd mediastation

# 2. 复制并编辑配置
copy .env.example .env
notepad .env  # 修改 TMDB_API_KEY

# 3. 启动
docker compose up -d

# 4. 打开浏览器
start http://localhost:3001
```

---

## 群晖 (Synology) 部署

### 方式一：Docker 图形界面

1. 打开「Docker」套件
2. 选择「注册表」，搜索 `mediastation`
3. 下载 `mediastation/mediastation:latest`
4. 创建容器：
   - 选择「高级设置」
   - 配置端口映射：`3001:3001`
   - 配置卷挂载：
     - `./data:/data`
     - `/volume1/media/movies:/data/media/movies`
     - `/volume1/media/tv:/data/media/tv`
     - `/volume1/downloads:/data/downloads`
   - 配置环境变量：`TMDB_API_KEY`
5. 完成并启动

### 方式二：SSH 命令行

```bash
# SSH 登录群晖
ssh admin@your-nas-ip

# 创建目录
sudo mkdir -p /volume1/docker/mediastation/{data,media/{movies,tv,anime},downloads}
sudo chown -R admin:users /volume1/docker/mediastation

# 下载配置
cd /volume1/docker/mediastation
sudo curl -fsSL https://raw.githubusercontent.com/your-repo/mediastation/main/docker-compose.example.yml -o docker-compose.yml
sudo curl -fsSL https://raw.githubusercontent.com/your-repo/mediastation/main/.env.example -o .env

# 编辑配置
sudo nano .env  # 修改 TMDB_API_KEY

# 启动
sudo docker compose up -d
```

### 方式三：SPK 套件包

```bash
# 下载最新 SPK
wget https://github.com/your-repo/mediastation/releases/latest/download/MediaStation.spk

# 在群晖「套件中心」>「手动安装」中上传安装
```

---

## 威联通 (QNAP) 部署

### 方式一：Container Station

1. 打开「Container Station」
2. 创建应用：
   - 上传 `docker-compose.yml`
   - 配置环境变量
3. 启动容器

### 方式二：命令行

```bash
# SSH 登录 QNAP
ssh admin@your-nas-ip

# 创建目录
mkdir -p /share/Container/mediastation/{data,media/{movies,tv,anime},downloads}

# 下载配置
cd /share/Container/mediastation
curl -fsSL https://raw.githubusercontent.com/your-repo/mediastation/main/docker-compose.example.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/your-repo/mediastation/main/.env.example -o .env

# 编辑配置
vi .env

# 启动
docker compose up -d
```

---

## Unraid 部署

### 方式一：Docker Hub 模板

1. 打开 Unraid WebUI
2. 进入「Docker」页面
3. 选择「Add Container」
4. 配置：
   - Repository: `mediastation/mediastation`
   - WebUI: `http://[IP]:[PORT:3001]/`
5. 配置端口、环境变量、卷挂载
6. 应用

### 方式二：自定义模板

1. 下载模板文件：
   ```
   https://raw.githubusercontent.com/your-repo/mediastation/main/deploy/templates/unraid/mediastation.xml
   ```
2. 将模板放入 `/boot/config/docker/custom_templates/`
3. 在 Unraid 界面选择该模板创建容器

---

## TrueNAS Scale 部署

### 方式一：Custom App

1. 登录 TrueNAS Scale WebUI
2. 进入「Apps」>「Custom App」
3. 粘贴 `deploy/charts/truenas/media-station.yaml` 内容
4. 配置：
   - 镜像：`mediastation/mediastation:latest`
   - 端口：`3001`
   - 环境变量：`TMDB_API_KEY`
5. 配置存储卷
6. 部署

### 方式二：Ix-Checkpoint

1. 进入「Apps」>「Available Applications」
2. 搜索 `mediastation`
3. 点击安装并配置

---

## macOS 部署

### 方式一：Docker Desktop

```bash
# 1. 安装 Docker Desktop
brew install --cask docker

# 2. 克隆项目
git clone https://github.com/your-repo/mediastation.git
cd mediastation

# 3. 配置
cp .env.example .env
# 编辑 .env

# 4. 启动
docker compose up -d

# 5. 访问
open http://localhost:3001
```

### 方式二：本地开发

```bash
# 1. 安装依赖
brew install python@3.11 node ffmpeg

# 2. 克隆项目
git clone https://github.com/your-repo/mediastation.git
cd mediastation

# 3. 安装后端
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. 安装前端
cd ../frontend
npm install

# 5. 启动
# 终端 1: 后端
cd backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 3001 --reload

# 终端 2: 前端
cd frontend && npm run dev
```

---

## 裸机部署

适用于 VPS、实体服务器等无容器环境。

### Ubuntu/Debian

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip ffmpeg curl git nginx certbot

# 2. 创建用户
sudo useradd -m -s /bin/bash mediastation
sudo su - mediastation

# 3. 克隆项目
git clone https://github.com/your-repo/mediastation.git
cd mediastation

# 4. 安装
mkdir -p data media/{movies,tv,anime} downloads logs
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 5. 配置
cp .env.example .env
nano .env  # 修改配置

# 6. 启动
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 3001 > logs/mediastation.log 2>&1 &

# 7. Nginx 反向代理（可选）
sudo cp nginx.example.conf /etc/nginx/sites-available/mediastation
sudo ln -s /etc/nginx/sites-available/mediastation /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### systemd 服务

```bash
# 创建服务文件
sudo cat > /etc/systemd/system/mediastation.service << 'EOF'
[Unit]
Description=MediaStation Media Server
After=network.target

[Service]
Type=simple
User=mediastation
WorkingDirectory=/home/mediastation/mediastation
ExecStart=/home/mediastation/mediastation/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 3001
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable mediastation
sudo systemctl start mediastation
```

---

## 硬件加速配置

### Intel GPU (QSV)

```yaml
# Docker Compose
services:
  mediastation:
    devices:
      - /dev/dri:/dev/dri
    environment:
      - HW_ACCEL=qsv
```

```bash
# Kubernetes
helm install mediastation ... \
  --set env.HW_ACCEL=qsv
```

### NVIDIA GPU (NVENC)

1. 安装 [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

```yaml
services:
  mediastation:
    runtime: nvidia
    devices:
      - /dev/nvidia0:/dev/nvidia0
      - /dev/nvidiactl:/dev/nvidiactl
      - /dev/nvidia-uvm:/dev/nvidia-uvm
    environment:
      - HW_ACCEL=nvenc
      - NVIDIA_VISIBLE_DEVICES=all
```

### AMD GPU (VAAPI)

```yaml
services:
  mediastation:
    devices:
      - /dev/dri:/dev/dri
    environment:
      - HW_ACCEL=vaapi
```

---

## 故障排查

### 容器无法启动

```bash
# 查看详细日志
docker compose logs mediastation

# 检查端口占用
netstat -tlnp | grep 3001
```

### 媒体文件无法播放

1. 检查文件权限
2. 检查 FFmpeg 是否正常工作
3. 查看转码日志

### 下载功能不工作

1. 检查下载客户端配置
2. 验证 qBittorrent/Transmission 连接
3. 检查端口映射

### 数据库问题

```bash
# 重置 SQLite 数据库
rm backend/data/mediastation.db
docker compose restart mediastation
```

---

## 常见问题

### Q: 如何修改默认密码？

登录后进入「设置」>「用户管理」修改。

### Q: 如何启用 HTTPS？

使用 Nginx/Caddy 反向代理，配合 Let's Encrypt 证书。

### Q: 如何备份数据？

```bash
# 备份
tar -czf mediastation-backup.tar.gz data/ media/ downloads/

# 恢复
tar -xzf mediastation-backup.tar.gz
```

### Q: 如何更新到最新版本？

```bash
docker compose pull
docker compose up -d
```

---

## 获取帮助

- GitHub Issues: https://github.com/your-repo/mediastation/issues
- 文档: https://github.com/your-repo/mediastation/wiki
- Discord: https://discord.gg/mediastation
