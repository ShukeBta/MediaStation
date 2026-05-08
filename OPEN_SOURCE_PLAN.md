# MediaStation 开源仓库规划

## 📦 仓库策略

| 仓库 | 可见性 | 内容 | 说明 |
|------|--------|------|------|
| **MediaStation** | 🌐 Public | 主开源仓库 | 包含 backend + frontend + deploy |
| **mediastation-license-server** | 🔒 Private | 授权服务 | 原 server 仓库重命名 |

---

## 🏗️ 开源仓库结构 (MediaStation)

```
MediaStation/
├── backend/                    # 后端服务 (Python/FastAPI)
│   ├── app/                   # 应用代码
│   ├── data/                  # SQLite 数据目录
│   ├── static/                # 静态文件
│   ├── .env.example           # 环境变量示例（无敏感信息）
│   ├── requirements.txt       # Python 依赖
│   └── README.md              # 后端单独说明
│
├── frontend/                  # 前端 (Vue3 + Vite + TypeScript)
│   ├── src/                   # 源码
│   ├── dist/                  # 构建产物
│   ├── public/                # 静态资源
│   ├── .env.example           # 环境变量示例
│   ├── package.json
│   └── README.md              # 前端单独说明
│
├── deploy/                    # 部署脚本和配置
│   ├── scripts/               # 部署脚本
│   ├── templates/             # Nginx/Kubernetes 模板
│   ├── charts/                # Helm charts
│   ├── packages/              # 配置文件
│   └── DEPLOYMENT.md          # 详细部署文档
│
├── docker/                    # Dockerfile
├── docker-compose.yml         # Docker Compose 配置
├── docker-compose.example.yml # 示例配置
├── nginx.example.conf         # Nginx 配置示例
│
├── docs/                      # 技术文档
│   ├── architecture.md        # 架构文档
│   └── OPTIMIZATION_ROADMAP.md # 优化路线图
│
├── README.md                  # 项目主 README
├── LICENSE                    # BSL 1.1 协议
├── .gitignore                 # Git 忽略文件
└── CONTRIBUTING.md            # 贡献指南
```

---

## 🔒 闭源仓库 (mediastation-license-server)

```
mediastation-license-server/
├── server.js                  # 授权服务主文件
├── app/                       # 管理面板前端
├── templates/                 # HTML 模板
├── admin-panel/               # 管理面板静态文件
├── data/                      # 授权数据库
├── package.json
├── Dockerfile
├── docker-compose.yml
├── deploy.sh                  # 部署脚本
├── README.md                  # 授权服务文档
├── SECURITY_GUIDE.md          # 安全指南
└── .env.example               # 环境变量示例
```

---

## 🚫 需要排除的敏感文件

### backend/
```
backend/.env                   # ❌ 数据库密码、API密钥
backend/*.log                  # ❌ 日志文件
backend/app.db                 # ❌ 生产数据库
backend/mediastation.db        # ❌ 生产数据库
backend/backend*.log           # ❌ 日志文件
backend/venv/                  # ❌ Python 虚拟环境
backend/node_modules/          # ❌ (如有)
backend/__pycache__/           # ❌ Python 缓存
backend/*.pyc                 # ❌ Python 编译文件
```

### frontend/
```
frontend/.env                  # ❌ API 地址
frontend/dist/                # ❌ 构建产物 (可选，源码已足够)
frontend/node_modules/         # ❌ npm 依赖
frontend/*.log                 # ❌ 日志文件
frontend/logs/                 # ❌ 日志目录
```

### license_server/
```
license_server/.env            # ❌ 密钥
license_server/data/           # ❌ 授权数据库
license_server/node_modules/   # ❌ npm 依赖
license_server/*.log           # ❌ 日志文件
```

---

## 📝 .gitignore 模板

```gitignore
# Environment
.env
.env.local
.env.*.local
*.env

# Logs
*.log
logs/
*.log.*

# Database
*.db
*.db-journal
*.db-wal
*.db-shm
data/*.db

# Dependencies
node_modules/
venv/
__pycache__/
*.pyc
*.pyo

# Build
dist/
build/
*.egg-info/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Secrets
*.pem
*.key
credentials.json
```

---

## 🔄 开源步骤

### 1. 创建新仓库
```bash
# 在 GitHub 创建 MediaStation 仓库 (Public)
gh repo create MediaStation --public --source=. --push

# 将 server 仓库重命名为 mediastation-license-server
# 在 https://github.com/ShukeBta/server/settings 手动重命名
```

### 2. 准备开源分支
```bash
# 清理敏感文件
./deploy/scripts/clean-for-opensource.sh

# 添加开源 .gitignore
cp deploy/templates/.gitignore.example .gitignore

# 提交开源版本
git add .
git commit -m "chore: prepare for open source"
git push origin main
```

### 3. 许可证选择
- **BSL 1.1**: 禁止商业使用超过 101 台服务器
- **AGPL**: 要求开源修改版本
- **推荐**: BSL 1.1（更灵活，法律成本低）

---

## 📊 开源后用户限制说明

在 README 中明确说明：

```
## ⚠️ 开源版限制

本开源版允许 **最多 15 名用户** 免费使用。

如需更多用户或高级功能，请联系获取 MediaStation Plus 版本：
- 无限用户数量
- 高级订阅管理
- 优先技术支持
```

---

## 🎯 后续计划 (闭源扩展)

| 版本 | 用户数 | 闭源程度 | 计划时间 |
|------|--------|----------|----------|
| 开源版 | ≤15 | 完全开源 | 现在 |
| Plus | 不限 | 前端+后端闭源 | 后期 |
| Enterprise | 不限 | 全部闭源+定制 | 商业化后 |
