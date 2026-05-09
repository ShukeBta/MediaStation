# MediaStation 项目长期记忆

## 项目概述
- **名称**: MediaStation — 轻量级家庭媒体服务器
- **定位**: 播放+下载一体化 / Emby兼容(164端点) / Docker一键部署
- **仓库路径**: `c:\Users\Administrator\WorkBuddy\20260428130330`
- **技术栈**: Python FastAPI + Vue 3 + TypeScript + Tailwind CSS + HLS.js + SQLite
- **后端端口**: 3001 | **前端端口**: 5173

## 架构关键点
- 后端: FastAPI async + SQLAlchemy 2.0 (aiosqlite) + APScheduler + SSE
- 前端: Vue 3 + Pinia + Vue Router + Vite + Tailwind CSS
- 三层架构: Controller(router) → Service → Repository
- Base 模型: `app/base_models.py`，JWT 认证，默认 admin/admin123
- 总端点: 269+（Emby 164 + 其他 105+）

## 模块清单
- **user**: 认证、用户管理、观看历史
- **media**: 媒体库、扫描、多源刮削链(TMDb→豆瓣→Bangumi)、字幕管理
- **playback**: Direct Play + HLS 转码、进度上报
- **download**: qBittorrent/Transmission/Aria2 适配、下载完成自动整理
- **subscribe**: 站点管理、订阅自动化、RSS、通知
- **system**: SSE事件、调度器、系统信息、配置管理
- **admin**: 批量操作、文件管理、AI助手(规则引擎)、存储配置
- **emby_api**: Emby API 兼容层（164端点）
- **license**: 基于 user.tier 字段判断 Plus 状态（简化版，无外部授权服务）
- **前端视图**: Dashboard / MediaLibrary / PosterWall / Player / Download / Subscribe / Settings / AIAssistant

## 开发完成度
- Phase 1–5: ✅ 全部完成

## 踩坑记录（关键）
- `passlib` + `bcrypt>=5.0` 不兼容，必须锁定 `bcrypt>=4.0,<5.0`
- SQLAlchemy mapped model 必须有 primary key
- `tsconfig.node.json` 被 references 时必须设 `composite: true`
- npm install 国内用 `--registry=https://registry.npmmirror.com`
- Windows 重启后端: PowerShell `Get-NetTCPConnection -LocalPort 3001` 找 PID，`Stop-Process -Id xxx -Force`
- Git Bash 里 `taskkill /PID` 路径转译失败，改用 PowerShell
- **httpx 对 HTTP header value 严格校验**：所有 `.headers()` 中对 UA 等调用 `.strip()`

## 前端修复汇总（2026-05-09）

### auth store 简化
- 移除 `licenseApi` import、`licenseStatus` 状态、`fetchLicenseStatus()` 函数
- `isPlus` 直接用 `user.tier === 'plus'`
- `router/index.ts` 导航守卫中移除 `auth.fetchLicenseStatus()` 调用

### AI 助手端点（backend/app/admin/router.py 末尾）
7个端点全部在 admin router 中以规则引擎实现（内存存储，无外部 AI）:
- `GET/DELETE /admin/assistant/session(s)` — 会话管理
- `GET /admin/assistant/history` — 操作历史
- `POST /admin/assistant/chat` — 消息/回复（意图识别规则引擎）
- `POST /admin/assistant/execute` — 执行建议操作
- `POST /admin/assistant/undo/{op_id}` — 撤销

### License API
- `backend/app/license/` 模块存在，提供 `/api/license/status` 端点
- 基于 `user.tier` 字段判断 Plus 状态（无外部授权服务依赖）

## 下载模块关键修复（2026-05-04）
- `clients.py`: qBittorrent 做种阶段全部映射为 `"completed"`（`uploading/stalledUP/forcedUP` 等）
- `service.py`: `sync_task_status()` 联动更新订阅状态
- `DownloadView.vue`: 字段对齐 `task.downloaded`/`task.speed`，进度计数器方案

## M-Team API
- 正确端点: `https://test2.m-team.cc/api`（v3，camelCase 参数，`x-api-key` 认证）
- 下载: `POST /torrent/genDlToken?id={tid}` → 获取 URL → GET 下载 .torrent

## qBittorrent API
- Web API: `/api/v2/torrents/add`，Cookie-based SID，必须带 `Referer` 头
- 成功响应: `"Ok."` 或空字符串

## 媒体库扫描要点（2026-05-02）
- Season 文件夹识别: `SEASON_FOLDER_PATTERNS` + `is_season_folder()`
- NFO 元数据优先: `find_nfo_file()` / `parse_nfo_file()`
- 剧集去重: `normalize_title()` 标准化

## API 配置系统
8个数据源（TMDb/豆瓣/Bangumi/TheTVDB/Fanart.tv/OpenAI/硅基流动/DeepSeek）在线配置
文件: `api_config_models.py` / `api_config_service.py` / `api_config_router.py`

## 个人偏好
- 使用中文沟通
- UI: 现代深色主题，卡片式布局，渐变色，平滑动画
- 工作模式: 直接创建/修改文件，一步到位交付，修复后直接推送
- 调试: 从控制台输出中发现错误，直接粘贴终端报错定位问题
