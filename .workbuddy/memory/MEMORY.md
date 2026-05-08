# MediaStation 项目长期记忆

## ⚠️ 开源版代码清理（2026-05-08）
为开源版发布清理了以下模块：
- **删除**: `backend/app/license/` 整个目录（授权服务端已独立部署）
- **删除**: `backend/app/assistant/` 整个目录（AI助手依赖授权服务）
- **删除**: `backend/app/profiles/` 整个目录（用户配置模块）
- **删除**: `backend/app/media/ai_scraper.py`（AI刮削器）
- **删除**: `backend/app/media/providers/ai_provider.py`（AI Provider）
- **清理**: `backend/app/main.py` - 移除 license_router 导入和注册
- **清理**: `backend/app/system/scheduler.py` - 移除 license 定时任务
- **清理**: 删除旧数据库备份文件
- **更新**: `.dockerignore`、`docker/Dockerfile`

### 清理验证
- ✅ 主应用导入成功（372个路由，无 license 路由）
- ✅ 所有关键模块导入正常
- ✅ 无遗留的 deleted 模块引用

## ⚠️ License Server 状态（2026-05-08）
- **已移除**于 2026-05-08，开源版不再包含授权服务
- 备份位置: `c:\Users\Administrator\WorkBuddy\license_server_backup\license_server_2026-05-08`

## 项目概述
- **名称**: MediaStation — 轻量级家庭媒体服务器
- **定位**: 融合媒体播放 + 自动化订阅下载，Docker 一键部署，零配置使用
- **差异化**: 播放+下载一体化闭环 / Emby兼容(164端点) / 多源刮削链
- **仓库路径**: `c:\Users\Administrator\WorkBuddy\20260428130330`
- **技术栈**: Python FastAPI + Vue 3 + TypeScript + Tailwind CSS + HLS.js + SQLite
- **参考项目**: MoviePilot V2, NAStool, nowen-video

## 架构关键点
- 后端: FastAPI async + SQLAlchemy 2.0 (aiosqlite) + APScheduler + SSE
- 前端: Vue 3 + Pinia + Vue Router + Vite + Tailwind CSS + HLS.js
- 三层架构: Controller(router) → Service → Repository
- 数据库默认 SQLite（零配置），可选 PostgreSQL（连接池+性能索引）
- Base 模型统一在 `app/base_models.py`，所有模块共用
- JWT 认证（access + refresh token），默认 admin/admin123
- 总端点数: **269 个**（Emby 164 + DLNA/AI 刮削/插件管理等 105）
- Emby 兼容层: **164 个端点**（2026-05-07 完成）

## 模块清单
- **user**: 认证、用户管理、观看历史 API
- **media**: 媒体库、扫描、多源刮削链(TMDb→豆瓣→Bangumi→AI)、文件整理、字幕管理、AI 辅助刮削、手动元数据编辑
- **playback**: Direct Play + HLS 转码、进度上报、外部播放器直链
- **download**: qBittorrent/Transmission/Aria2 客户端适配、下载完成自动整理入库
- **subscribe**: 站点管理、订阅自动化、RSS、通知
- **system**: SSE 事件、调度器(6个任务)、系统信息、配置管理、API Key 配置
- **emby_api**: Emby API 兼容层（164 个端点，Infuse/Kodi 支持）
- **dlna**: DLNA 投屏（SSDP 发现 + AVTransport 控制）
- **plugins**: 插件系统（生命周期/Hook/API 扩展/前端面板）
- **前端视图**: Dashboard / MediaLibrary / PosterWall / TvSeasonView / Player / Download / Subscribe / Sites / Settings / Login

## 开发阶段完成度
- **Phase 1–4**: ✅ 全部完成
- **Phase 5 生产化完善**: ✅ 完成（下载管理 / 订阅状态联动 / 剧集识别增强 / 电影合集支持）

## 踩坑记录（关键）
- `passlib` + `bcrypt>=5.0` 不兼容，必须锁定 `bcrypt>=4.0,<5.0`
- SQLAlchemy mapped model 必须有 primary key
- `tsconfig.node.json` 被 references 时必须设 `composite: true`
- npm install 国内用 `--registry=https://registry.npmmirror.com`
- Windows 重启后端：PowerShell `Get-NetTCPConnection -LocalPort 3001` 找 PID，`Stop-Process -Id xxx -Force`
- Git Bash 里 `taskkill /PID xxx /F` 路径转译失败，改用 PowerShell
- Edit 工具可能报 EBUSY，改用 Write 工具整体覆盖
- **httpx 对 HTTP header value 严格校验**：所有 `headers()` 方法中对 UA 等调用 `.strip()`

## 下载模块关键修复（2026-05-04 session）

### 问题与修复

| 问题 | 根因 | 修复文件 |
|------|------|----------|
| 已完成任务显示在"下载中" | `_map_state()` 将做种状态映射为 `seeding` | `clients.py` |
| 进度条不更新 | 前端字段 `downloaded_size`/`download_speed` 与后端 `downloaded`/`speed` 不匹配 | `DownloadView.vue` |
| 订阅完成状态不更新 | `sync_task_status()` 未联动更新 Subscription | `service.py` |
| 自动整理失效 | 依赖 completed 状态但 QB 实际为 seeding | 修复 `_map_state` 后自动解决 |

### `clients.py` - `_map_state()` 修复
qBittorrent 做种阶段（`uploading`/`stalledUP`/`forcedUP`/`checkingUP`/`queuedUP`/`moving`/`pausedUP`）全部映射为 `"completed"`。
`pausedDL` 映射为 `"paused"`（下载还未完成）。

### `service.py` - 订阅联动
- `sync_task_status()` 中追踪 `newly_completed_sub_ids`
- 状态从非 completed → completed 且有 `subscription_id` 时，收集订阅 ID
- 新增 `_mark_subscriptions_completed()` 方法，将 `active` 订阅标记为 `completed`

### `DownloadView.vue` - 前端修复
- 字段对齐：`task.downloaded`（不是 `downloaded_size`），`task.speed`（不是 `download_speed`）
- `getProgressPct(task)` 函数：优先用 `task.progress`（0-100），回退用 `downloaded/total_size` 计算
- 定时器改用计数器方案：每 3 秒应用 SSE 进度，每 9 秒完整刷新
- 移除 `startAutoSync()`（会造成无限循环）

## M-Team API 要点
- **正确端点**: `https://test2.m-team.cc/api`（v3 API，camelCase 参数）
- **认证**: `x-api-key` 请求头
- **下载流程**: `POST /torrent/genDlToken?id={tid}` → 返回下载 URL → GET 该 URL 获取 .torrent
- 旧 `https://api.m-team.cc/api` 已废弃

## qBittorrent API 要点
- Web API: `/api/v2/torrents/add`，Cookie-based SID 认证，必须带 `Referer` 头
- 成功响应: `"Ok."` 或空字符串；其他响应（包括中文错误消息）都是失败
- `.torrent` 文件以 `b"d"` 开头（Bencode dict）
- 添加任务后用 `_get_latest_torrent_hash()` 获取真实 hash（重试10次，间隔300ms）

## 媒体库扫描关键修复（2026-05-02）
- Season 文件夹识别：`SEASON_FOLDER_PATTERNS` + `is_season_folder()` + `parse_season_folder()`
- NFO 元数据优先：`find_nfo_file()` / `parse_nfo_file()`，优先用 NFO 中的 `tmdb_id`
- 剧集去重：`normalize_title()` 标准化，同一剧多季只创建一个 MediaItem

## 订阅搜索修复（2026-05-01）
- UA header 前导空格 → `.strip()` 修复
- 英文子串误匹配（如 Hoppers→Grasshoppers）→ `_is_title_relevant()` 词边界正则

## API 配置系统（2026-05-03）
8 个数据源（TMDb/豆瓣/Bangumi/TheTVDB/Fanart.tv/OpenAI/硅基流动/DeepSeek）在线配置。
文件：`api_config_models.py` / `api_config_service.py` / `api_config_router.py`
端点前缀：`/api/api-config/`

## MoviePilot API 参考（2026-04-30）
新增端点：`GET /api/sites/{id}/resource`（浏览站点资源）、`GET /api/sites/{id}/userdata`、
`POST /api/subscriptions/{id}/share`、`POST /api/subscriptions/{id}/fork`
新增 `SiteResourceBrowser` 类（支持 NexusPHP/M-Team/UNIT3D）

## 剧集识别增强（2026-05-04）
文件：`backend/app/media/scanner.py`

### 新增模式
- `ANIME_EPISODE_PATTERNS`: 动漫剧集模式（第01话、[01]、()格式等）
- `MULTI_SEASON_INDICATORS`: 多季合集标识（Complete Season、全季、全集等）
- `SEASON_ALIAS_MAP`: Season 别名映射

### 新增函数
- `parse_multi_episodes()`: 解析多集连播文件（返回所有集号列表）
- `is_multi_season_folder()`: 判断文件夹是否是多季合集
- 增强 `parse_season_episode()`: 支持多集返回
- 增强 `parse_season_folder()`: 支持季号范围解析

### 支持格式
- S01E01E02E03.mp4 → [1, 2, 3]
- S01E01-E02-E03.mp4 → [1, 2, 3]
- 01x02x03.mp4 → [1, 2, 3]
- Season 1-5 → (1, 5)
- 第01话.mp4 → anime模式，默认第1季

## 电影合集支持（2026-05-04）
文件：`backend/app/media/providers/base.py` / `tmdb.py`

### MediaMetadata 新增字段
- `collection_id`: TMDb 合集 ID
- `collection_name`: 合集名称
- `collection_poster_url`: 合集海报 URL
- `collection_backdrop_url`: 合集背景图 URL

### TMDbProvider 新增方法
- `get_collection(collection_id)`: 获取电影合集详情（包含所有电影列表）

## 9KG 番号支持（2026-05-04）
文件：`backend/app/media/parse_code.py`

### 新增识别
- `9KG` 番号前缀（如 9KG-001、9KGirl-123）
- 新增 9KG 关键词到 `ADULT_KEYWORDS`
- 新增 9KG 番号前缀到 `KNOWN_PREFIXES`（SNIS、NHDTA、HEYZO 等常见番号）

## License Server（2026-05-07 迭代演进）

### 最终架构
- **路径**: `license_server/`
- **架构**: 纯 Node.js 单进程（http + better-sqlite3），无 Python 依赖
- **端口**: 8001（API + 管理面板同源）
- **入口**: `license_server/server.js`（单文件，含所有路由）
- **管理面板**: `license_server/admin-panel/index.html`（内嵌于 server.js 同源提供）
- **数据库**: `license_server/data/license.db`（SQLite，WAL 模式）
- **启动**: `powershell -NoProfile -Command "Start-Process -FilePath 'node' -ArgumentList 'server.js' -WorkingDirectory '...license_server' -WindowStyle Hidden"`
- **测试 Admin Key**: `admin-test-key-2026`

### API 端点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/` `/admin` | 管理面板 HTML |
| POST | `/api/v1/activate` | 激活授权码（公开） |
| POST | `/api/v1/heartbeat` | 心跳续期（公开） |
| POST | `/api/v1/deactivate` | 注销设备（公开） |
| GET | `/api/v1/status/:fingerprint` | 查询设备状态（公开） |
| GET | `/api/v1/admin/keys` | 列出所有授权码（管理） |
| POST | `/api/v1/admin/keys` | 生成授权码（管理） |
| GET | `/api/v1/admin/keys/:id` | 授权码详情+激活设备（管理） |
| POST | `/api/v1/admin/keys/:id/revoke` | 吊销授权码（管理） |
| POST | `/api/v1/admin/activations/:id/unbind` | 解绑设备（管理） |

### HMAC 签名协议
- `HMAC_SECRET`: `ms-shared-hmac-secret-key-for-testing`
- activate/heartbeat 响应带 `signature` 字段（HMAC-SHA256）
- 客户端验证签名确保响应未被篡改
- 心跳间隔约 7 天（±2 小时随机抖动）

### 授权码格式
- 新格式: `MS-XXXX-XXXX-XXXX-XXXX`（MS- 前缀，4 段）
- 旧格式: `MSXX-XXXX-XXXX-XXXX-XX`（5 段，无标准前缀）— 数据库中兼容保留

### 关键踩坑（Node.js / SQLite / 编码）
1. **中文乱码**: Node.js `req.on('data', chunk => body += chunk)` 中 chunk 是 Buffer，`+=` 拼接按 Latin-1 编码导致中文乱码。**修复**: 先收集 `chunks[]` 数组，最后 `Buffer.concat(chunks).toString('utf-8')`
2. **SQLite NOT NULL 约束**: 旧 Python SQLAlchemy 创建的 `license_keys` 表 `is_revoked` 列无 DEFAULT 值，INSERT 未提供该列会失败。**修复**: INSERT 语句显式包含 `is_revoked` 列并设值 `0`
3. **SQLite ALTER TABLE 限制**: SQLite 不支持 `ALTER TABLE ADD COLUMN ... NOT NULL DEFAULT`。**方案**: 不修改旧表结构，只在新建表时包含完整列定义
4. **进程稳定性**: bash 后台进程随会话退出而终止。**修复**: 用 `powershell Start-Process -WindowStyle Hidden` 启动独立 Windows 进程
5. **端口占用**: server.js 内置 EADDRINUSE 处理，自动 `netstat` 查找并 `taskkill` 占用进程后重试

### 架构演进历史
1. **v1**: Python FastAPI (port 8001) + Node.js 管理面板 (port 8002) → Python 环境丢失，进程不稳定
2. **v2**: 纯 Node.js 单进程 → 管理面板内嵌，同源提供，单端口 8001

### 废弃文件（保留未删除）
- `license_server/app/` — 旧 Python FastAPI 代码
- `license_server/admin-panel/server.js` — 旧独立 Node.js 静态服务器（不再需要）
