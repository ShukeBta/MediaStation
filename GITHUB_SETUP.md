# GitHub 开源操作指南

## 🚀 步骤概览

```
步骤 1: GitHub 网页创建仓库 (5分钟)
步骤 2: 添加远程仓库并推送 (2分钟)  
步骤 3: 重命名 server 仓库 (2分钟)
```

---

## 步骤 1: 创建 MediaStation 仓库

### 1.1 登录 GitHub

访问 https://github.com 并登录你的账号

### 1.2 创建新仓库

1. 点击右上角 **"+"** 按钮 → **"New repository"**
2. 填写信息：

```
Repository name: MediaStation
Description: 开源媒体资源管理系统
Visibility: Public ☑️
☑️ Add a README file (不要勾选，我们会用自己的)
☑️ Add .gitignore (选择 Python)
```

3. 点击 **"Create repository"**

### 1.3 复制仓库地址

创建成功后会显示仓库地址，例如：
```
https://github.com/ShukeBta/MediaStation.git
```

---

## 步骤 2: 推送代码

### 2.1 添加远程仓库

```bash
cd /c/Users/Administrator/WorkBuddy/20260428130330

# 添加远程仓库 (把 YOUR_USERNAME 换成你的 GitHub 用户名)
git remote add origin https://github.com/YOUR_USERNAME/MediaStation.git
```

### 2.2 配置 Git 用户信息 (如果还没配置)

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### 2.3 暂存文件

```bash
# 查看状态
git status

# 添加所有文件 (不包括 .gitignore 里的)
git add .

# 或者只添加特定目录
git add README.md LICENSE .gitignore CONTRIBUTING.md
git add backend/ frontend/ deploy/ docs/ docker/
git add docker-compose.yml docker-compose.example.yml nginx.example.conf
```

### 2.4 提交

```bash
git commit -m "feat: initial open source release

- MediaStation v1.0 正式开源
- 后端: FastAPI + SQLite
- 前端: Vue 3 + TypeScript
- 部署: Docker 支持
- 开源协议: BSL 1.1
- 用户限制: 最多 15 名用户
"
```

### 2.5 推送

```bash
# 首次推送，设置默认分支
git branch -M main
git push -u origin main
```

---

## 步骤 3: 重命名 server 仓库为 mediastation-license-server

### 3.1 访问 server 仓库设置

1. 访问 https://github.com/ShukeBta/server/settings
2. 滚动到 **"Repository name"** 部分

### 3.2 重命名

1. 将 `server` 改为 `mediastation-license-server`
2. 点击 **"Rename"**
3. 将仓库可见性改为 **Private** (闭源)

### 3.3 验证

- 新仓库地址: https://github.com/ShukeBta/mediastation-license-server

---

## ✅ 完成后检查

### MediaStation 仓库 (开源)
- [ ] 仓库可见性: Public
- [ ] README.md 正确显示
- [ ] LICENSE 文件存在
- [ ] 代码已推送

### mediastation-license-server 仓库 (闭源)
- [ ] 仓库可见性: Private
- [ ] 重命名成功
- [ ] 包含 server.js, admin-panel 等文件

---

## 📝 常用 Git 命令

```bash
# 查看状态
git status

# 查看远程仓库
git remote -v

# 拉取更新
git pull origin main

# 推送更新
git push origin main

# 查看提交历史
git log --oneline

# 创建并切换分支
git checkout -b feature/new-feature

# 合并分支
git checkout main
git merge feature/new-feature
```

---

## ⚠️ 重要提醒

### 敏感信息检查

推送到开源仓库前，确认以下文件已排除：

```bash
# 应该被 .gitignore 排除的文件
backend/.env              # ❌ 敏感
backend/*.db              # ❌ 数据库
backend/venv/             # ❌ 虚拟环境
backend/__pycache__/      # ❌ 缓存
frontend/node_modules/     # ❌ npm 包
frontend/.env             # ❌ 敏感
license_server/           # ❌ 不在开源仓库里
```

### 本地验证

```bash
# 在推送到 GitHub 前，先检查
git status

# 确保没有意外的敏感文件
git ls-files | grep -E "\.env$|\.db$|node_modules"
```

---

## 🎉 恭喜！

完成以上步骤后，你的开源项目就上线了！

- **开源仓库**: https://github.com/ShukeBta/MediaStation
- **闭源仓库**: https://github.com/ShukeBta/mediastation-license-server
