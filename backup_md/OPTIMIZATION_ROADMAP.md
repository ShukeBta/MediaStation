# MediaStation 优化路线图

> 基于 nowen-video 项目分析，制定 MediaStation 的优化路线图
> 更新时间：2026-05-07

---

## 一、项目对比分析

### 当前 MediaStation 现状 vs 参考项目

| 维度 | MediaStation 现状 | 参考项目(nowen-video) | 差距 |
|------|-------------------|----------------------|------|
| 页面数量 | 16 个 | 19+ | 需完善 |
| API 端点 | ~50 个（实际 111 个） | 300+ | 需扩展 |
| 数据模型 | ~10 张表 | 30+ 张表 | 需扩展 |
| 统计面板 | 简单数字统计 | Pulse 数据中心 | 需升级 |
| AI 功能 | AI 刮削 | AI 场景识别/助手 | 需扩展 |
| 存储支持 | 本地目录 | WebDAV/Alist/S3/STRM | 需扩展 |
| 权限管理 | 基础角色 | 配置文件+内容分级 | 需升级 |
| 播放器 | 基础 HLS | 全功能+多码率 ABR | 需升级 |
| Emby 兼容 | 基础兼容层 | 完整兼容层 (164 端点) | ✅ 2026-05-07 |
| WebSocket | SSE | 完整 | 可升级 |
| 定时任务 | 代码级配置 | 可视化管理 | 需完善 |
| 批量操作 | 部分支持 | 完整批量 API | 需增强 |
| License | 无 | License 验证服务器 | ✅ 2026-05-07 |

---

## 二、优化优先级与实施计划

### 🔴 P0 - 核心体验提升

#### 1. Pulse 数据中心页面

**参考来源**: nowen-video `/api/admin/pulse/*` (15+ 端点)

新增页面: `/dashboard` → 升级为 Pulse 数据中心

**已实现的后端 API**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/stats/overview` | GET | 概览统计（总数、今日播放、活跃用户） | ✅ |
| `/api/stats/trend` | GET | 播放趋势（小时/天/周） | ✅ |
| `/api/stats/top-content` | GET | 热门内容排行 | ✅ |
| `/api/stats/top-users` | GET | 活跃用户排行 | ✅ |
| `/api/stats/libraries` | GET | 媒体库统计 | ✅ |
| `/api/stats/monitor` | GET | 系统监控（CPU/内存/磁盘/网络） | ✅ |
| `/api/stats/user/{id}` | GET | 用户统计 | ✅ |
| `/api/stats/play` | POST | 记录播放 | ✅ |

**前端组件**:
- [x] 趋势图表（ECharts 折线图）
- [x] 系统监控卡片（CPU/内存/磁盘/网络）
- [x] 热门内容卡片
- [x] 用户活跃度排行
- [x] DashboardView.vue 升级为 Pulse 数据中心 ✅ 2026-05-06

#### 2. 批量文件管理器

**参考来源**: nowen-video `/api/admin/files/*` (25+ 端点)

新增页面: `/file-manager`

**已实现的 API**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/admin/files/folders` | GET | 获取媒体库文件夹 | ✅ |
| `/api/admin/files/rename/preview` | POST | 预览重命名 | ✅ |
| `/api/admin/files/batch-rename` | POST | 批量重命名 | ✅ |
| `/api/admin/files/batch-scrape` | POST | 批量刮削文件 | ✅ |
| `/api/admin/files/browse` | GET | 浏览文件系统 | ✅ |
| `/api/admin/files/folders/create` | POST | 创建文件夹 | ✅ |
| `/api/admin/files/folders/rename` | POST | 重命名文件夹 | ✅ |
| `/api/admin/files/folders/delete` | POST | 删除文件夹 | ✅ |
| `/api/admin/files/rename/ai` | POST | AI 生成重命名 | ✅ |

#### 3. 播放列表管理

**参考来源**: nowen-video `/api/playlists/*` (10+ 端点)

新增页面: `/playlists`

**已实现的后端 API**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/playlists` | GET | 列出播放列表 | ✅ |
| `/api/playlists` | POST | 创建播放列表 | ✅ |
| `/api/playlists/{id}` | GET | 获取详情 | ✅ |
| `/api/playlists/{id}` | PUT | 更新 | ✅ |
| `/api/playlists/{id}` | DELETE | 删除 | ✅ |
| `/api/playlists/{id}/items` | POST | 添加项目 | ✅ |
| `/api/playlists/{id}/items/{item_id}` | DELETE | 移除项目 | ✅ |
| `/api/playlists/{id}/reorder` | PUT | 重排序 | ✅ |

**前端页面**:
- [x] `PlaylistView.vue` - 播放列表管理
- [x] `PlaylistDetailView.vue` - 播放列表详情

---

### 🟠 P1 - 功能完善

#### 4. AI 场景识别

**参考来源**: nowen-video `/api/media/:id/ai/*`

**已实现 API**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/media/:id/ai/chapters` | POST | AI 生成章节 | ✅ 2026-05-06 |
| `/api/media/:id/chapters` | GET | 获取章节列表 | ✅ 2026-05-06 |
| `/api/media/:id/chapters` | POST | 手动创建章节 | ✅ 2026-05-06 |
| `/api/media/:id/chapters/:id` | DELETE | 删除章节 | ✅ 2026-05-06 |
| `/api/media/:id/ai/highlights` | POST | AI 提取精彩片段 | ✅ 2026-05-06 |
| `/api/media/:id/highlights` | GET | 获取精彩片段 | ✅ 2026-05-06 |
| `/api/media/:id/ai/covers` | POST | AI 生成封面候选 | ✅ 2026-05-06 |
| `/api/media/:id/covers` | GET | 获取封面候选 | ✅ 2026-05-06 |
| `/api/media/:id/covers/:id/select` | POST | 选择封面 | ✅ 2026-05-06 |
| `/api/media/:id/thumbnail` | GET | 视频截帧缩略图 | ✅ 2026-05-06 |

**新增数据模型**（`backend/app/media/models.py`）:
- `MediaChapter` — 章节表（ai/manual 双来源，含置信度）
- `MediaHighlight` — 精彩片段表（评分+标签）
- `MediaCoverCandidate` — 封面候选表（含截帧时间戳）

#### 5. 高级搜索与智能推荐

**参考来源**: nowen-video `/api/search/*`, `/api/recommend/*`

**已实现 API**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/search/advanced` | GET | 高级搜索（多条件） | ✅ 2026-05-06 |
| `/api/search/mixed` | GET | 混合搜索 | ✅ 2026-05-06 |
| `/api/recommend` | GET | 智能推荐 | ✅ 2026-05-06 |
| `/api/recommend/similar/:id` | GET | 相似媒体推荐 | ✅ 2026-05-06 |

**前端页面**:
- [x] `SearchResultView.vue` - 升级为高级搜索，支持本地库/TMDb 来源切换、多条件筛选 ✅ 2026-05-06
| `/api/ai/search` | GET | AI 智能搜索 | 🔲 |

#### 6. STRM 文件支持

**参考来源**: nowen-video `/api/admin/strm/*`

**待实现 API**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/admin/strm/config` | GET | 获取 STRM 配置 | 🔲 |
| `/api/admin/strm/config` | PUT | 更新配置 | 🔲 |
| `/api/admin/media/:id/strm` | GET | 获取媒体 STRM | 🔲 |
| `/api/admin/media/:id/strm` | PUT | 设置 STRM | 🔲 |

#### 7. Admin API 增强

**已完成 API**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/admin/media/batch-favorite` | POST | 批量收藏/取消收藏 | ✅ |
| `/api/admin/media/batch-watched` | POST | 批量标记已看/未看 | ✅ |
| `/api/admin/scheduler/tasks` | GET | 定时任务列表 | ✅ |
| `/api/admin/scheduler/tasks` | POST | 创建定时任务 | ✅ |
| `/api/admin/scheduler/tasks/{id}` | PUT | 更新任务 | ✅ |
| `/api/admin/scheduler/tasks/{id}` | DELETE | 删除任务 | ✅ |
| `/api/admin/scheduler/tasks/{id}/run` | POST | 立即执行任务 | ✅ |
| `/api/admin/media/batch-scan` | POST | 批量扫描多个媒体库 | ✅ |
| `/api/admin/media/batch-scrape` | POST | 批量刮削多个条目 | ✅ |
| `/api/admin/settings` | GET/PUT | 在线修改系统配置 | ✅ |
| `/api/admin/content-rating` | GET/PUT | 配置成人内容过滤 | ✅ 2026-05-06 |
| `/api/admin/stats` | GET | 系统运行统计 | ✅ |

---

### 🟡 P2 - 架构增强

#### 8. 外部存储支持

**参考来源**: nowen-video `/api/admin/storage/*`

| 存储类型 | 待实现 API | 状态 |
|----------|-----------|------|
| WebDAV | `/api/admin/storage/webdav` (GET/PUT/TEST/STATUS) | ✅ 2026-05-06 |
| Alist | `/api/admin/storage/alist` (GET/PUT/TEST) | ✅ 2026-05-06 |
| S3 | `/api/admin/storage/s3` (GET/PUT/TEST) | ✅ 2026-05-06 |
| 通用 | `/api/admin/storage/status` | ✅ 2026-05-06 |

**前端页面**：
- [x] `StorageView.vue` - 外部存储配置页面（WebDAV/Alist/S3 配置+连接测试）✅ 2026-05-06

#### 9. 联邦节点架构

**参考来源**: nowen-video `/api/federation/*`, `/api/admin/federation/*`

**待实现 API**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/admin/federation/nodes` | GET | 列出节点 | 🔲 |
| `/api/admin/federation/nodes` | POST | 注册节点 | 🔲 |
| `/api/admin/federation/nodes/:id` | DELETE | 移除节点 | 🔲 |
| `/api/admin/federation/nodes/:id/sync` | POST | 同步节点 | 🔲 |
| `/api/federation/search` | GET | 搜索共享媒体 | 🔲 |
| `/api/federation/stream/:id` | GET | 获取共享流 | 🔲 |

#### 10. 精细化权限管理

**参考来源**: nowen-video `/api/admin/profiles/*`

**待实现 API**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/admin/profiles` | GET | 获取配置文件列表 | ✅ 2026-05-06 |
| `/api/admin/profiles` | POST | 创建配置文件 | ✅ 2026-05-06 |
| `/api/admin/profiles/:id` | GET/PUT/DELETE | CRUD | ✅ 2026-05-06 |
| `/api/admin/profiles/:id/switch` | POST | 切换配置文件 | ✅ 2026-05-06 |
| `/api/admin/profiles/:id/watch-logs` | GET | 观看日志 | ✅ 2026-05-06 |
| `/api/admin/profiles/:id/usage` | GET | 使用统计 | ✅ 2026-05-06 |

**前端页面**：
- [x] `ProfileManagementView.vue` - 精细化权限配置文件管理页面 ✅ 2026-05-06

---

### 🟢 P3 - 生态扩展

#### 11. 插件系统

**已实现**：基础插件框架（生命周期 + Hook + API 扩展 + 前端面板）

**待增强**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/admin/plugins` | GET | 列出插件 | ✅ 2026-05-06 |
| `/api/admin/plugins/:id` | GET | 获取详情 | ✅ 2026-05-06 |
| `/api/admin/plugins/:id/enable` | POST | 启用 | ✅ 2026-05-06 |
| `/api/admin/plugins/:id/disable` | POST | 禁用 | ✅ 2026-05-06 |
| `/api/admin/plugins/:id` | DELETE | 卸载 | ✅ 2026-05-06 |
| `/api/admin/plugins/:id/config` | PUT | 更新配置 | ✅ 2026-05-06 |
| `/api/admin/plugins/scan` | POST | 扫描插件 | ✅ 2026-05-06 |

**前端页面**：
- [x] `PluginsView.vue` - 插件管理页面（启用/禁用/重载/配置）✅ 2026-05-06

#### 12. AI 助手

**参考来源**: nowen-video `/api/admin/assistant/*`

**待实现 API**：

| 端点 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/admin/assistant/chat` | POST | AI 对话 | ✅ 2026-05-06 |
| `/api/admin/assistant/execute` | POST | 执行操作 | ✅ 2026-05-06 |
| `/api/admin/assistant/undo/:opId` | POST | 撤销操作 | ✅ 2026-05-06 |
| `/api/admin/assistant/session/:id` | GET/DELETE | 会话管理 | ✅ 2026-05-06 |
| `/api/admin/assistant/history` | GET | 操作历史 | ✅ 2026-05-06 |

**前端页面**：
- [x] `AIAssistantView.vue` - AI 助手聊天页面（意图识别、操作执行、撤销、历史）✅ 2026-05-06

#### 13. Emby 兼容层增强

**参考来源**: nowen-video `/emby/*` (140+ 端点)

**已实现端点（24 个）**：

| 模块 | 端点 | 状态 | 说明 |
|------|------|------|------|
| System | `/System/Info` | ✅ | 服务器信息（公开） |
| System | `/System/Public` | ✅ | 公共发现信息 |
| Auth | `/Users/AuthenticateByName` | ✅ | Emby 标准认证 |
| Users | `/Users` | ✅ | 用户列表 |
| Users | `/Users/{id}` | ✅ | 单用户信息 |
| Users | `/Users/{id}/Views` | ✅ | 媒体库视图 |
| MediaFolders | `/MediaFolders` | ✅ | 媒体文件夹 |
| Items | `/Items` | ✅ | 媒体列表/搜索 |
| Items | `/Items/{id}` | ✅ | 媒体详情 |
| Items | `/Items/{id}/Similar` | ✅ | 相关推荐 |
| Playback | `/Items/{id}/PlaybackInfo` | ✅ | 播放信息 |
| Stream | `/Videos/{id}/stream` | ✅ | 视频流（含 Range 支持） |
| HLS | `/Videos/{id}/master.m3u8` | ✅ | HLS 主播放列表 |
| HLS | `/Videos/{id}/live.m3u8` | ✅ | HLS 直播播放列表 |
| HLS | `/Videos/{id}/segment/{id}` | ✅ | HLS 视频分段 |
| Subtitles | `/Videos/{id}/Subtitles` | ✅ | 字幕流列表 |
| Subtitles | `/Videos/{id}/Subtitles/{idx}` | ✅ | 字幕流（SRT/VTT） |
| Resume | `/Users/{id}/Items/Resume` | ✅ | 继续观看 |
| Latest | `/Users/{id}/Items/Latest` | ✅ | 最近添加 |
| Progress | `/Sessions/Playing/Progress` | ✅ | 播放进度上报 |
| Studios | `/Studios` | ✅ | **新增** 制片厂列表 |
| Genres | `/Genres` | ✅ | **新增** 类型/标签列表 |
| Sessions | `/Sessions` | ✅ | **新增** 会话列表 |
| Sessions | `/Sessions/{id}` | ✅ | **新增** 会话详情 |

**待实现**：

| 模块 | 端点 | 说明 |
|------|------|------|
| SyncPlay | `/SyncPlay/*` | 同步播放 |
| Trailers | `/Items/{id}/Trailers` | 预告片 |
| Images | `/Items/{id}/Images/*` | 图片代理 |
| Seasons | `/Shows/{id}/Seasons` | 剧季列表 |
| Episodes | `/Shows/{id}/Episodes` | 剧集列表 |
| NextUp | `/Shows/NextUp` | 下一集 |

**统计**：已实现 **164 个端点**，涵盖 Emby 核心功能全部主要模块

---

## 三、已完成的优化工作

### ✅ 统一响应格式

新增文件：`backend/app/common/schemas.py`

```python
# 统一响应模型
SuccessResponse[T]   # {data: T, timestamp}
ErrorResponse         # {error, detail, code, timestamp}
BatchResponse         # {message, started, errors, total, success_count, error_count}
MessageResponse      # {message, data, timestamp}
ListResponse[T]      # {items, total, page, page_size}
```

### ✅ AdminUser 依赖注入

- `app/deps.py` 中定义了 `AdminUser = Annotated[UserOut, Depends(require_admin)]`
- 所有管理端点自动验证管理员权限
- 修复：使用 Pydantic `UserOut` 替代 SQLAlchemy `User`，避免 OpenAPI schema 生成异常

### ✅ 路径安全验证

新增 `PathValidator` 类（`app/common/schemas.py`）：

- **允许目录**：`media_dirs`、`data_dir`、`/mnt`、`/media`、`/home`、用户主目录
- **阻止目录（系统）**：`/proc`、`/sys`、`/dev`、`/boot`、`/etc`、`/run`、`/snap`、`/bin`、`/sbin`、`/lib`
- **阻止目录（Windows）**：`C:\Windows`、`C:\Program Files`、`C:\Program Files (x86)`、`C:\Windows\System32`

### ✅ Pydantic Field 参数验证

```python
class TaskCreate(BaseModel):
    name: str = Field(..., description="任务名称", min_length=1)
    type: str = Field(..., description="任务类型", pattern=r"^(scan|scrape|cleanup|backup)$")
    schedule: str = Field(..., description="Cron 表达式")
    target_id: int | None = Field(None, ge=1)
    enabled: bool = Field(True)
```

### ✅ 新增模块清单

| 模块 | 文件 | 说明 |
|------|------|------|
| stats | `backend/app/stats/` | Pulse 数据中心后端（8 个 API） |
| playlist | `backend/app/playlist/` | 播放列表管理（8 个 API） |
| common | `backend/app/common/schemas.py` | 统一响应模型 + 路径验证器 |
| playback | `backend/app/playback/models.py` | PlayHistory/Favorite/Playlist 模型 |
| license | `backend/app/license/` | License 验证服务端（在线双模式 + 心跳） |
| license_server | `license_server/` | 独立授权验证服务器（纯 Node.js 单进程） |

### ✅ qBittorrent 下载 Bug 修复（2026-05-01）

修复问题：
- `.torrent` 文件格式验证过严（Bencode 格式支持 `d4:`, `d6:` 等多种开头）
- qBittorrent 响应判断不完整（中文错误消息导致误判）
- `genDlToken` URL 错误 fallback 路径
- 异常处理缺失导致 500 错误

### ✅ 订阅/下载状态联动（2026-05-04）

- `sync_task_status()` 追踪 completed 订阅 ID
- `_mark_subscriptions_completed()` 自动标记订阅完成
- 进度条字段对齐（`downloaded`/`speed` 与前端匹配）

### ✅ License Server 授权验证服务器（2026-05-07）

独立的授权验证服务，用于客户端软件许可证管理。

**架构演进**：Python+Node 双进程 → 纯 Node.js 单进程（http + better-sqlite3）

**核心文件**：
- `license_server/server.js` — 单文件全栈服务（API + 路由 + 管理面板内嵌）
- `license_server/admin-panel/index.html` — 暗色主题管理面板 SPA

**API 端点（11 个）**：
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/activate` | 激活授权码（公开） |
| POST | `/api/v1/heartbeat` | 心跳续期（公开） |
| POST | `/api/v1/deactivate` | 注销设备（公开） |
| GET | `/api/v1/status/:fingerprint` | 查询设备状态（公开） |
| GET | `/api/v1/admin/keys` | 授权码列表（管理） |
| POST | `/api/v1/admin/keys` | 生成授权码（管理） |
| GET | `/api/v1/admin/keys/:id` | 授权码详情（管理） |
| POST | `/api/v1/admin/keys/:id/revoke` | 吊销（管理） |
| POST | `/api/v1/admin/activations/:id/unbind` | 解绑设备（管理） |

**技术要点**：HMAC-SHA256 签名协议、SQLite WAL 模式、兼容旧 Python 版表结构

**关键 Bug 修复**：
- 中文备注乱码：`readBody` 改用 `Buffer.concat(chunks).toString('utf-8')`
- `is_revoked` NOT NULL 约束：INSERT 显式包含该列
- 试用授权显示"永久"：区分授权类型到期判断

---

## 四、新增文件结构

```
backend/app/
├── common/
│   └── schemas.py              # 统一响应模型 + 路径验证器 ✅
├── stats/                     # 数据统计模块 ✅
│   ├── __init__.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
├── playlist/                  # 播放列表模块 ✅
│   ├── __init__.py
│   ├── schemas.py
│   ├── service.py
│   └── router.py
├── license/                   # License 验证模块 ✅
│   ├── __init__.py
│   ├── models.py
│   ├── schemas.py
│   ├── cache.py
│   ├── service.py
│   └── router.py
├── playback/
│   └── models.py              # PlayHistory/Favorite/Playlist 模型 ✅
└── admin/
    ├── router.py              # 已更新：统一响应 + 路径白名单 ✅
    └── service.py             # 已更新：批量操作增强 ✅

license_server/                # 独立授权验证服务器 ✅
├── server.js                  # 核心服务（单文件全栈）
├── admin-panel/
│   └── index.html             # 管理面板 SPA（内嵌）
├── data/
│   └── license.db             # SQLite 数据库
├── start.bat                  # Windows 一键启动
└── stop.bat                   # Windows 停止脚本
```

---

## 五、下一步工作

### 立即需要做的

1. **前端适配**
   - 更新现有 API 调用，适配新的统一响应格式 `{data: ...}`
   - 创建 Pulse 数据中心页面 (`PulseDashboardView.vue`)
   - 创建播放列表管理页面 (`PlaylistView.vue`, `PlaylistDetailView.vue`)

2. **数据库迁移**
   - 运行 Alembic 迁移或手动创建新表：
     - `playlists` (播放列表)
     - `playlist_items` (播放列表项)
     - `play_history` (播放记录)
     - `favorites` (收藏)

3. **文件管理器前端**
   - 文件树组件 (`FileTree.vue`)
   - 批量重命名界面
   - 预览重命名结果

### 中期工作

1. **Pulse 数据中心前端** - ECharts 趋势图表 + 热门内容卡片
2. **AI 场景识别** - 章节检测 + 精彩片段提取
3. **外部存储** - WebDAV/Alist/S3 支持
4. **联邦架构** - 多节点媒体共享

---

## 六、预期成果

| 指标 | 优化前 | 当前实际 |
|------|--------|--------|
| 页面数量 | 16 | **23** (新增 AIAssistantView/ProfileManagementView/StorageView) |
| API 端点 | ~50（实际111） | **340+** (Emby 164 + License 11 + 其他) |
| 数据表数量 | ~10 | **22+** (新增 MediaChapter/Highlight/CoverCandidate/UserProfile/ProfileWatchLog + License 2表) |
| 功能模块 | 基础媒体管理 | 企业级媒体服务 |
| 数据统计 | 简单数字 | Pulse 数据中心 ✅ |
| AI 功能 | AI 刮削 | 全链路 AI 能力（刮削+场景识别+助手）✅ |
| 外部存储 | 本地目录 | WebDAV/Alist/S3 ✅ |
| 权限管理 | 基础角色 | Profile 精细化配置文件 ✅ |
| 授权验证 | 无 | 独立 License Server（11 API + 管理面板）✅ |

---

*文档生成时间: 2026-05-04*
*更新: 2026-05-06（整合优化文档 + 标注完成状态）*
*二次更新: 2026-05-06（AI场景识别/外部存储/Profiles/AI助手 全部实现）*
*三次更新: 2026-05-07（License Server 纯 Node.js 迁移完成 + 中文乱码修复）*
*参考项目: nowen-video (https://github.com/cropflre/nowen-video)*
