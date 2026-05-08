# MediaStation - 开源媒体资源管理系统

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Vue.js-3.x-green.svg" alt="Vue">
  <img src="https://img.shields.io/badge/License-GPL%20v3-blue.svg" alt="License">
</p>

## 项目简介

MediaStation 是一个现代化的媒体资源管理系统，支持多平台资源聚合、订阅管理和自动化下载。

### 主要功能

- 🌐 **多平台支持** - 支持 MTeam、BTN 等私有 Tracker
- 📊 **资源聚合** - 统一管理和搜索分散的媒体资源
- 🔄 **自动订阅** - RSS 订阅和自动下载
- 📱 **现代化界面** - 响应式设计，支持深色模式
- 🔐 **安全认证** - HMAC 签名验证，双因素支持
- 📈 **实时统计** - Dashboard 展示系统状态
- 🤖 **AI 能力** - 智能刮削、场景识别、AI 助手

---

## ✨ 完全开源

MediaStation 采用 **完全开源** 策略，无用户数量限制，可自由使用于个人或商业场景。

如需更多高级功能，请联系获取 **MediaStation Plus** 版本：
- 🔒 高级订阅管理
- 📞 优先技术支持
- 🚀 企业级功能

---

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 后端 | Python 3.9+ / FastAPI | 高性能异步 API |
| 前端 | Vue 3 / TypeScript / Vite | 现代化响应式界面 |
| 数据库 | SQLite | 轻量级嵌入式数据库 |
| 授权 | JWT + HMAC | 安全令牌验证 |
| 部署 | Docker / PM2 | 容器化部署支持 |

---

## 快速开始

### 前置要求

- Python 3.9+
- Node.js 18+
- npm 或 yarn
- SQLite3

### 1. 克隆项目

```bash
git clone https://github.com/ShukeBta/MediaStation.git
cd MediaStation
```

### 2. 后端设置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 复制环境变量
cp .env.example .env
# 编辑 .env 配置你的设置

# 启动服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 3002
```

### 3. 前端设置

```bash
cd frontend

# 安装依赖
npm install

# 复制环境变量
cp .env.example .env
# 编辑 .env 配置 API 地址

# 开发模式
npm run dev

# 生产构建
npm run build
```

### 4. 使用 Docker 部署

```bash
# 快速启动
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 项目结构

```
MediaStation/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/            # 核心模块
│   │   ├── models/          # 数据模型
│   │   ├── services/        # 业务逻辑
│   │   └── main.py          # 应用入口
│   ├── data/                # 数据目录
│   └── requirements.txt
│
├── frontend/                # 前端应用
│   ├── src/
│   │   ├── components/     # Vue 组件
│   │   ├── views/           # 页面视图
│   │   ├── stores/          # 状态管理
│   │   └── api/             # API 调用
│   └── package.json
│
├── deploy/                  # 部署配置
│   ├── scripts/            # 部署脚本
│   ├── templates/          # 配置模板
│   └── charts/             # Helm Charts
│
└── docker/                 # Docker 配置
```

---

## 配置说明

### 后端环境变量 (.env)

```env
# API 配置
API_HOST=0.0.0.0
API_PORT=3002

# 数据库
DB_PATH=./data/mediastation.db

# JWT 密钥 (必须修改)
JWT_SECRET=your-super-secret-key-change-this

# MTeam API (可选)
MTEAM_API_KEY=your-mteam-api-key
MTEAM_API_SECRET=your-mteam-api-secret
```

### 前端环境变量 (.env)

```env
VITE_API_BASE_URL=http://localhost:3002
```

---

## 文档

- [部署指南](./deploy/DEPLOYMENT.md) - 详细部署说明
- [架构文档](./docs/architecture.md) - 系统架构详解
- [优化路线图](./docs/OPTIMIZATION_ROADMAP.md) - 后续规划

---

## 常见问题

### Q: 开源版有人数限制吗？
A: 是的，开源版限制最多 15 名注册用户。

### Q: 支持哪些平台？
A: 目前支持 MTeam 和 BTN 私有 Tracker。

### Q: 如何申请 Plus 版本？
A: 请通过项目主页的联系信息获取报价和演示。

---

## 许可证

本项目采用 **Business Source License 1.1 (BSL)** 协议。

要点：
- 🎯 **免费使用**：最多 15 名用户
- 🚫 **禁止商业**：超过 15 名用户需购买商业许可
- 🔄 **可修改**：允许 fork 和修改代码
- 📢 **需开源**：修改后的版本也需要开源

详细条款请查看 [LICENSE](LICENSE) 文件。

---

## 贡献

欢迎提交 Issue 和 Pull Request！

---

<p align="center">
  Made with ❤️ by ShukeBta
</p>
