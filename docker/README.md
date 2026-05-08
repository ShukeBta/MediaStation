# MediaStation Docker 部署指南

## 快速开始

### 1. 配置文件

```bash
# 进入 docker 目录
cd docker

# 复制环境变量模板
cp .env.template .env

# 编辑 .env 配置必填项
nano .env
```

### 2. 必填配置项

```env
# 应用密钥 (32位随机字符串)
APP_SECRET_KEY=change-me-to-a-random-secret-key-min-32-chars

# TMDb API (申请地址: https://www.themoviedb.org/settings/api)
TMDB_API_KEY=your-tmdb-api-key

# License 服务器密钥
LICENSE_ADMIN_API_KEY=change-me
LICENSE_HMAC_SECRET=change-me
```

### 3. 一键部署

**Linux/macOS:**
```bash
chmod +x deploy-docker.sh
./deploy-docker.sh
```

**Windows (PowerShell):**
```powershell
.\deploy-docker.ps1
```

### 4. 访问服务

部署完成后访问：
- **主界面**: http://localhost:3002
- **qBittorrent**: http://localhost:8080
- **授权管理**: http://localhost:3001

---

## Docker Compose 命令

```bash
# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f

# 停止服务
docker compose down

# 重启服务
docker compose restart

# 重新构建镜像
docker compose build --no-cache
docker compose up -d

# 更新服务
docker compose pull
docker compose up -d
```

---

## 目录结构

```
mediastation/
├── docker/
│   ├── docker-compose.yml      # 主配置
│   ├── docker-compose.license.yml  # 独立授权服务
│   ├── .env.template           # 环境变量模板
│   ├── .env                   # 你的配置 (不提交)
│   ├── Dockerfile             # 后端镜像
│   ├── Dockerfile.license     # 授权服务镜像
│   ├── deploy-docker.sh       # Linux/macOS 部署脚本
│   ├── deploy-docker.ps1      # Windows 部署脚本
│   ├── license_data/          # 授权数据库
│   └── config/                # 配置文件
│
├── data/                      # 应用数据
├── media/                     # 媒体文件 (挂载)
└── downloads/                 # 下载目录
```

---

## 数据持久化

所有数据存储在宿主机目录：

| 容器 | 宿主机目录 | 说明 |
|------|-----------|------|
| backend | `./data` | SQLite 数据库 |
| qbittorrent | `./downloads` | 下载文件 |
| qbittorrent | `./config/qbittorrent` | qBittorrent 配置 |
| license-server | `./license_data` | 授权数据库 |

---

## 自定义配置

### 修改端口

编辑 `.env` 文件：

```env
BACKEND_PORT=3002      # 后端 API
LICENSE_PORT=3001      # 授权服务
```

### 添加更多 Tracker

在 `.env` 中配置对应的 API 密钥。

### HTTPS 配置

使用 Nginx 反向代理，参考 `nginx.example.conf`。

---

## 常见问题

### Q: 容器启动失败？
```bash
# 查看详细日志
docker compose logs -f backend
docker compose logs -f license-server
```

### Q: 如何更新？
```bash
docker compose pull
docker compose up -d
```

### Q: 如何备份数据？
```bash
# 备份整个 data 目录
tar -czf mediastation-backup.tar.gz data/

# 备份授权数据库
cp license_data/license.db license.db.backup
```

### Q: 完全重置？
```bash
docker compose down -v  # -v 会删除数据卷
docker compose up -d
```

---

## 安全建议

1. **修改默认密码** - qBittorrent 默认账号 `admin/adminadmin`
2. **设置强密钥** - 不要使用默认的 `change-me` 密钥
3. **限制端口访问** - 使用防火墙限制外部访问
4. **定期备份** - 定期备份 `data/` 和 `license_data/` 目录
