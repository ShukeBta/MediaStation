# MediaStation — 轻量级家庭媒体服务器 架构设计方案

> **项目定位**：一款专为轻量 NAS 打造的家庭媒体服务器，融合 Emby/Jellyfin 的媒体播放能力 + MoviePilot/NAStool 的自动化订阅下载能力，Docker 一键启动，零配置使用。

---

## 一、技术选型决策

### 1.1 架构决策矩阵

| 决策项 | 选型 | 理由 |
|--------|------|------|
| **项目结构** | Feature-first（按功能模块组织） | 媒体/下载/播放/订阅各模块独立，便于扩展 |
| **后端框架** | Python 3.11+ FastAPI | 异步高性能、自动 API 文档、Pydantic 类型安全、生态丰富 |
| **前端框架** | Vue 3 + TypeScript + Vite | Composition API、响应式系统、HMR 毫秒级热更新 |
| **数据库** | SQLite（默认）/ PostgreSQL（可选） | 轻量 NAS 友好 SQLite，大规模部署可切换 PG |
| **缓存** | 纯内存缓存（cachetools）/ Redis（可选） | 默认零依赖，可选 Redis 提升多实例缓存性能 |
| **API 风格** | RESTful + SSE（实时通知） | REST 覆盖 CRUD，SSE 推送下载/转码/刮削进度 |
| **认证** | JWT（短期 Access + 长期 Refresh） | 无状态、适合前后端分离，支持多端 |
| **任务调度** | APScheduler（进程内）/ Celery（可选） | 默认内置调度器零依赖，可选 Celery 分布式 |
| **视频转码** | FFmpeg subprocess + 硬件加速 | QSV/VAAPI/NVENC 自动检测，软编兜底 |
| **播放协议** | HLS（hls.js）+ 直接播放（MP4/WebM） | 浏览器兼容性最佳，自适应码率 |
| **容器化** | Docker + Docker Compose | 一键部署，NAS 友好 |

### 1.2 为什么选 Python FastAPI 而非 Go

| 因素 | Python FastAPI | Go (Gin) | 决策 |
|------|---------------|----------|------|
| 开发效率 | ⭐⭐⭐⭐⭐ 原型快、生态丰富 | ⭐⭐⭐ 样板代码多 | Python 胜 |
| NAS 适配 | ⭐⭐⭐⭐ 依赖管理成熟 | ⭐⭐⭐⭐⭐ 单二进制 | Go 微胜 |
| 社区生态 | ⭐⭐⭐⭐⭐ PT/BT/刮削库丰富 | ⭐⭐⭐ 生态较小 | Python 胜 |
| MoviePilot 兼容 | ⭐⭐⭐⭐⭐ 可复用插件经验 | ⭐⭐ 需重写 | Python 胜 |
| 性能 | ⭐⭐⭐⭐ 异步足够 | ⭐⭐⭐⭐⭐ 原生高并发 | Go 胜 |
| 部署体积 | ⭐⭐⭐ Docker ~300MB | ⭐⭐⭐⭐⭐ 单二进制 ~20MB | Go 胜 |

**结论**：作为 MoviePilot 插件开发者，Python 生态和经验积累是核心优势。FastAPI 异步性能足以覆盖 NAS 场景（并发 < 50），Docker 部署体积可控。

---

## 二、系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端层                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Web 前端  │  │ 移动端 PWA│  │ Emby客户端│  │ 第三方 API    │  │
│  │ Vue3+TS  │  │  浏览器   │  │Infuse/Kodi│  │ (Emby API)   │  │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └───────┬───────┘  │
└────────┼─────────────┼─────────────┼───────────────┼───────────┘
        │ HTTP/SSE    │ HTTP/SSE    │ HTTP(SSE)      │ REST
        ▼             ▼             ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Nginx (反向代理 + 静态文件)                   │
│                  :80/:443 → :3001(API)                          │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI 应用层 (:3001)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │ 媒体库模块│ │ 播放模块  │ │ 下载模块  │ │ 订阅/站点模块     │  │
│  │ Media    │ │ Playback │ │ Download │ │ Subscribe/Site    │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬──────────┘  │
│       │            │            │                 │              │
│  ┌────┴────────────┴────────────┴─────────────────┴──────────┐  │
│  │                    Service 层（业务逻辑）                    │  │
│  │  ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ │  │
│  │  │ 元数据刮削   │ │ 文件整理  │ │ 转码服务  │ │ 通知服务   │ │  │
│  │  │ (TMDb/豆瓣) │ │ (重命名)  │ │(FFmpeg)  │ │(微信/TG)  │ │  │
│  │  └─────────────┘ └──────────┘ └──────────┘ └───────────┘ │  │
│  └──────────────────────────┬────────────────────────────────┘  │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Repository 层（数据访问）                      │   │
│  │         SQLAlchemy ORM + Alembic 迁移                     │   │
│  └──────────────────────────┬────────────────────────────────┘  │
│                             ▼                                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              基础设施层                                    │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │ SQLite/PG│ │ APScheduler│ │ FFmpeg  │ │ 配置中心   │  │   │
│  │  │ 数据库    │ │ 任务调度   │ │ 转码引擎 │ │(Pydantic) │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ 媒体文件  │  │qBittorrent│  │ 外部 API  │  │ 通知服务  │
  │ /media   │  │/Transmission│ │TMDb/豆瓣  │  │微信/Telegram│
  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

---

## 三、目录结构（Feature-First）

```
mediastation/
├── docker/
│   ├── Dockerfile                    # 多阶段构建
│   ├── docker-compose.yml            # 一键部署
│   └── nginx.conf                    # 反向代理配置
│
├── backend/
│   ├── alembic/                      # 数据库迁移
│   │   ├── versions/
│   │   └── env.py
│   ├── alembic.ini
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI 入口，生命周期管理
│   │   ├── config.py                 # Pydantic Settings 配置中心
│   │   ├── deps.py                   # 依赖注入（DB session, current_user）
│   │   ├── exceptions.py             # 统一错误层级
│   │   │
│   │   ├── media/                    # 🎬 媒体库模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/media/* 路由
│   │   │   ├── schemas.py            # Pydantic 请求/响应模型
│   │   │   ├── service.py            # 媒体库业务逻辑
│   │   │   ├── repository.py         # 媒体数据访问
│   │   │   ├── models.py             # SQLAlchemy 模型
│   │   │   ├── scraper.py            # TMDb/豆瓣/Bangumi 刮削链
│   │   │   ├── scanner.py            # 文件扫描 + fsnotify
│   │   │   └── organizer.py          # 文件重命名整理
│   │   │
│   │   ├── playback/                 # ▶️ 播放模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/playback/* 路由
│   │   │   ├── schemas.py
│   │   │   ├── service.py            # 播放业务逻辑
│   │   │   ├── transcoder.py         # FFmpeg 转码引擎
│   │   │   ├── stream.py             # HLS 分片生成
│   │   │   └── subtitle.py           # 字幕处理（内嵌提取/外挂加载）
│   │   │
│   │   ├── download/                 # ⬇️ 下载模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/download/* 路由
│   │   │   ├── schemas.py
│   │   │   ├── service.py            # 下载管理业务逻辑
│   │   │   ├── clients/              # 下载客户端适配器
│   │   │   │   ├── base.py           # 抽象基类
│   │   │   │   ├── qbittorrent.py    # qBittorrent 适配
│   │   │   │   ├── transmission.py   # Transmission 适配
│   │   │   │   └── aria2.py          # Aria2 适配（可选）
│   │   │   └── models.py
│   │   │
│   │   ├── subscribe/                # 📡 订阅模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/subscribe/* 路由
│   │   │   ├── schemas.py
│   │   │   ├── service.py            # 订阅管理业务逻辑
│   │   │   ├── searcher.py           # 资源搜索（站点搜索整合）
│   │   │   ├── notifier.py           # 通知推送服务
│   │   │   ├── sites/                # 站点适配器
│   │   │   │   ├── base.py           # 站点抽象基类
│   │   │   │   ├── nexus_php.py      # NexusPHP 系列站点
│   │   │   │   ├── gazelle.py        # Gazelle 系列站点
│   │   │   │   └── custom.py         # 自定义 RSS 站点
│   │   │   └── models.py
│   │   │
│   │   ├── user/                     # 👤 用户模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/user/* 路由
│   │   │   ├── schemas.py
│   │   │   ├── service.py
│   │   │   ├── repository.py
│   │   │   ├── models.py
│   │   │   └── auth.py               # JWT 认证逻辑
│   │   │
│   │   ├── system/                   # ⚙️ 系统模块
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # /api/system/* 路由
│   │   │   ├── scheduler.py          # APScheduler 调度配置
│   │   │   ├── events.py             # SSE 事件总线
│   │   │   └── monitor.py            # 系统监控（CPU/内存/磁盘）
│   │   │
│   │   └── emby/                     # 🔄 Emby 兼容层（可选模块）
│   │       ├── __init__.py
│   │       ├── router.py             # /emby/* 路由前缀
│   │       ├── mapper.py             # UUID ↔ 数字 ID 映射
│   │       └── api.py                # Emby API 实现（140+ 接口）
│   │
│   ├── requirements.txt
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── api/                      # API 客户端封装
│   │   │   ├── client.ts             # Axios 实例 + 拦截器
│   │   │   ├── media.ts              # 媒体库 API
│   │   │   ├── playback.ts           # 播放 API
│   │   │   ├── download.ts           # 下载 API
│   │   │   ├── subscribe.ts          # 订阅 API
│   │   │   └── system.ts             # 系统 API
│   │   │
│   │   ├── components/               # 通用组件
│   │   │   ├── layout/               # 布局（侧边栏、头部、导航）
│   │   │   ├── media/                # 媒体组件（海报卡片、详情页）
│   │   │   ├── player/               # 播放器组件
│   │   │   ├── download/             # 下载组件（任务列表、进度条）
│   │   │   ├── subscribe/            # 订阅组件（订阅表单、站点管理）
│   │   │   └── common/               # 通用（骨架屏、Toast、Modal）
│   │   │
│   │   ├── views/                    # 页面视图
│   │   │   ├── Dashboard.vue         # 仪表盘
│   │   │   ├── MediaLibrary.vue      # 媒体库（电影/剧集/动漫）
│   │   │   ├── MediaDetail.vue       # 媒体详情
│   │   │   ├── Player.vue            # 播放页面
│   │   │   ├── Subscribe.vue         # 订阅管理
│   │   │   ├── Download.vue          # 下载管理
│   │   │   ├── Sites.vue             # 站点管理
│   │   │   ├── Search.vue            # 搜索
│   │   │   ├── Settings.vue          # 系统设置
│   │   │   └── Login.vue             # 登录
│   │   │
│   │   ├── stores/                   # Pinia 状态管理
│   │   │   ├── auth.ts               # 认证状态
│   │   │   ├── media.ts              # 媒体库状态
│   │   │   ├── player.ts             # 播放器状态
│   │   │   ├── download.ts           # 下载状态
│   │   │   └── settings.ts           # 设置状态
│   │   │
│   │   ├── composables/              # 组合式函数
│   │   │   ├── useSSE.ts             # SSE 实时事件
│   │   │   ├── usePlayer.ts          # 播放器控制
│   │   │   └── useNotification.ts    # 通知
│   │   │
│   │   ├── router/
│   │   ├── i18n/                     # 国际化
│   │   ├── styles/
│   │   ├── App.vue
│   │   └── main.ts
│   │
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── .env.example
├── .gitignore
└── README.md
```

---

## 四、核心模块详细设计

### 4.1 媒体库模块 (`media/`)

#### 数据模型

```python
# media/models.py
class MediaLibrary(Base):          # 媒体库（根目录）
    id: int
    name: str                      # "电影"、"电视剧"、"动漫"
    path: str                      # "/media/movies"
    media_type: MediaType          # MOVIE / TV / ANIME
    scan_interval: int             # 扫描间隔（分钟）
    enabled: bool

class MediaItem(Base):             # 媒体条目
    id: int
    library_id: int                # 所属媒体库
    tmdb_id: int | None            # TMDb ID
    douban_id: str | None          # 豆瓣 ID
    title: str                     # 标题
    original_title: str            # 原始标题
    year: int                      # 年份
    overview: str                  # 简介
    poster_url: str                # 海报
    backdrop_url: str              # 背景图
    media_type: MediaType
    rating: float                  # 评分
    genres: str                    # 类型（JSON 数组）
    file_path: str                 # 文件路径
    file_size: int                 # 文件大小（字节）
    duration: int                  # 时长（秒）
    video_codec: str               # 视频编码
    audio_codec: str               # 音频编码
    resolution: str                # 分辨率
    date_added: datetime
    last_scanned: datetime

class MediaSeason(Base):           # 季
    id: int
    media_item_id: int             # 关联剧集
    season_number: int
    name: str

class MediaEpisode(Base):          # 集
    id: int
    season_id: int
    episode_number: int
    title: str
    file_path: str
    file_size: int
    duration: int
    air_date: date | None

class Subtitle(Base):              # 字幕
    id: int
    media_item_id: int             # 或 episode_id
    language: str                  # "zh", "en", "zh-CN"
    path: str                      # 字幕文件路径
    source: str                    # "embedded", "external", "ai_asr"
```

#### 刮削链设计

```python
# media/scraper.py — Provider Chain 模式
class ScraperProvider(ABC):
    priority: int = 50             # 数字越小优先级越高
    async def search(self, title: str, year: int) -> list[MediaMetadata]: ...
    async def get_detail(self, media_id: str) -> MediaMetadata: ...

# 优先级链：TMDb(10) → 豆瓣(20) → Bangumi(25) → Fanart.tv(40)
SCRAPER_CHAIN = [
    TMDbProvider(priority=10),     # 主数据源
    DoubanProvider(priority=20),   # 中文元数据补充
    BangumiProvider(priority=25),  # 动漫专项
    FanartProvider(priority=40),   # 高清图片
]

async def scrape_media(title: str, year: int) -> MediaMetadata:
    for provider in sorted(SCRAPER_CHAIN, key=lambda p: p.priority):
        try:
            results = await provider.search(title, year)
            if results:
                return await provider.get_detail(results[0].id)
        except Exception as e:
            logger.warning(f"Scraper {provider.__class__} failed: {e}")
    raise MediaNotFoundError(f"No metadata found for: {title} ({year})")
```

### 4.2 播放模块 (`playback/`)

#### 转码引擎设计

```python
# playback/transcoder.py
class TranscodeProfile(BaseModel):
    name: str                      # "720p", "1080p", "4k", "original"
    width: int
    height: int
    bitrate: str                   # "2000k"
    codec: str = "h264"
    audio_codec: str = "aac"

class Transcoder:
    def __init__(self, config: AppConfig):
        self.hw_accel = self._detect_hw_accel()  # auto/qsv/vaapi/nvenc/none
        self.max_jobs = config.max_transcode_jobs
        self.cache_dir = Path(config.cache_dir) / "transcode"

    def _detect_hw_accel(self) -> str:
        """自动检测硬件加速能力"""
        if shutil.which("nvidia-smi"):  return "nvenc"
        if Path("/dev/dri/renderD128").exists(): return "vaapi"
        # macOS
        if sys.platform == "darwin": return "videotoolbox"
        return "none"  # 软件编码兜底

    async def transcode_to_hls(self, file_path: str, profile: TranscodeProfile) -> Path:
        """FFmpeg 转码为 HLS 分片"""
        cmd = self._build_ffmpeg_cmd(file_path, profile)
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        # 流式读取 stderr 进度
        ...

    def _build_ffmpeg_cmd(self, input_file: str, profile: TranscodeProfile) -> list[str]:
        cmd = ["ffmpeg", "-i", input_file]
        # 硬件加速参数
        if self.hw_accel == "nvenc":
            cmd += ["-hwaccel", "cuda", "-c:v", "h264_nvenc", "-preset", "p4"]
        elif self.hw_accel == "vaapi":
            cmd += ["-hwaccel", "vaapi", "-vaapi_device", "/dev/dri/renderD128",
                     "-c:v", "h264_vaapi"]
        elif self.hw_accel == "videotoolbox":
            cmd += ["-hwaccel", "videotoolbox", "-c:v", "h264_videotoolbox"]
        else:
            cmd += ["-c:v", "libx264", "-preset", "fast"]
        # HLS 输出
        cmd += ["-f", "hls", "-hls_time", "4", "-hls_list_size", "0",
                "-hls_segment_filename", str(self.cache_dir / "seg_%03d.ts"),
                str(self.cache_dir / "playlist.m3u8")]
        return cmd
```

#### 播放 API 路由

```python
# playback/router.py
@router.get("/{media_id}/play")
async def get_play_info(media_id: int, quality: str = "auto"):
    """获取播放信息（直接播放 or HLS 流地址）"""
    media = await media_service.get_by_id(media_id)
    # 检测是否可直接播放
    if media.video_codec in ("h264", "hevc") and media.container in ("mp4", "webm"):
        return PlayInfo(mode="direct", url=f"/api/playback/{media_id}/stream")
    # 需要转码
    profile = TranscodeProfile.get_by_quality(quality)
    playlist_url = await transcoder.get_or_create_hls(media.file_path, profile)
    return PlayInfo(mode="hls", url=playlist_url, subtitles=media.subtitles)

@router.get("/{media_id}/stream")
async def stream_video(media_id: int, range: str | None = Header(None)):
    """直接视频流（支持 Range 断点续传）"""
    media = await media_service.get_by_id(media_id)
    file_path = Path(media.file_path)
    file_size = file_path.stat().st_size
    # Range 请求处理
    if range:
        start, end = parse_range(range, file_size)
        return StreamingResponse(
            file_range_sender(file_path, start, end),
            status_code=206,
            headers={"Content-Range": f"bytes {start}-{end}/{file_size}"}
        )
    return FileResponse(file_path)

@router.get("/{media_id}/hls/{quality}/playlist.m3u8")
async def get_hls_playlist(media_id: int, quality: str):
    """HLS 播放列表"""
    ...

@router.get("/{media_id}/hls/{quality}/{segment}")
async def get_hls_segment(media_id: int, quality: str, segment: str):
    """HLS 分片"""
    ...
```

### 4.3 下载模块 (`download/`)

#### 下载客户端适配器

```python
# download/clients/base.py
class DownloadClient(ABC):
    @abstractmethod
    async def connect(self) -> bool: ...
    @abstractmethod
    async def add_torrent(self, url: str | Path, save_path: str,
                          category: str | None = None) -> str: ...  # torrent_id
    @abstractmethod
    async def get_torrents(self, status: str | None = None) -> list[TorrentInfo]: ...
    @abstractmethod
    async def pause(self, torrent_id: str) -> bool: ...
    @abstractmethod
    async def resume(self, torrent_id: str) -> bool: ...
    @abstractmethod
    async def delete(self, torrent_id: str, delete_files: bool = False) -> bool: ...

# download/clients/qbittorrent.py
class QBittorrentClient(DownloadClient):
    """qBittorrent WebUI API 适配器"""
    BASE_API = "/api/v2"

    async def add_torrent(self, url: str | Path, save_path: str, category: str = None):
        data = {"savepath": save_path, "category": category or "MediaStation"}
        if isinstance(url, Path):
            # 磁力链接直接传字符串，种子文件传 multipart
            async with self.session.post(f"{self.base_url}{self.BASE_API}/torrents/add",
                                          data=data, files={"torrents": url.read_bytes()}) as resp:
                resp.raise_for_status()
        else:
            data["urls"] = url
            async with self.session.post(f"{self.base_url}{self.BASE_API}/torrents/add",
                                          data=data) as resp:
                resp.raise_for_status()
```

### 4.4 订阅模块 (`subscribe/`)

#### 订阅工作流

```
用户添加订阅 → 定时触发搜索 → 站点搜索 → 资源匹配 → 自动下载 → 下载完成回调
     ↓              ↓              ↓            ↓            ↓              ↓
  电影/剧集      APScheduler    站点API       正则/大小    qBittorrent    文件整理
  画质要求       (每小时)       RSS/搜索      过滤规则      添加种子      刮削入库
```

#### 站点适配器

```python
# subscribe/sites/base.py
class SiteAdapter(ABC):
    """站点适配器基类"""
    name: str
    base_url: str

    @abstractmethod
    async def login(self, username: str, password: str, **kwargs) -> bool: ...

    @abstractmethod
    async def search(self, keyword: str, filters: SearchFilter = None) -> list[SiteResource]: ...

    @abstractmethod
    async def get_rss(self, rss_url: str) -> list[SiteResource]: ...

    @abstractmethod
    async def download(self, resource: SiteResource) -> str | None: ...  # torrent URL

# subscribe/sites/nexus_php.py
class NexusPhpSite(SiteAdapter):
    """NexusPHP 系列站点（大部分 PT 站使用此系统）"""
    async def search(self, keyword: str, filters: SearchFilter = None) -> list[SiteResource]:
        params = {"search": keyword, "cat": filters.category_id if filters else 0}
        async with self.session.get(f"{self.base_url}/torrents.php", params=params) as resp:
            html = await resp.text()
            return self._parse_torrent_list(html)

    def _parse_torrent_list(self, html: str) -> list[SiteResource]:
        """解析 NexusPHP 种子列表页"""
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table.torrents tr")
        results = []
        for row in rows:
            title_elem = row.select_one("a[href*='details']")
            size_elem = row.select_one("td:nth-child(5)")
            if title_elem and size_elem:
                results.append(SiteResource(
                    title=title_elem.text.strip(),
                    url=f"{self.base_url}/{title_elem['href']}",
                    size=parse_size(size_elem.text),
                    seeders=int(row.select_one("td:nth-child(7)")?.text or 0),
                ))
        return results
```

### 4.5 通知模块

```python
# subscribe/notifier.py
class NotifierService:
    """多渠道通知推送"""
    def __init__(self):
        self.channels: list[NotifyChannel] = []

    def add_channel(self, channel: NotifyChannel):
        self.channels.append(channel)

    async def notify(self, title: str, content: str, notify_type: NotifyType):
        for channel in self.channels:
            try:
                await channel.send(title, content, notify_type)
            except Exception as e:
                logger.error(f"Notify channel {channel.name} failed: {e}")

# 支持的通知渠道
class WechatNotifier(NotifyChannel):     # 微信（Server酱/企业微信）
class TelegramNotifier(NotifyChannel):   # Telegram Bot
class BarkNotifier(NotifyChannel):       # iOS Bark
class WebhookNotifier(NotifyChannel):    # 自定义 Webhook
class EmailNotifier(NotifyChannel):      # 邮件（SMTP）
```

---

## 五、API 设计总览

### 5.1 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录获取 JWT |
| POST | `/api/auth/refresh` | 刷新 Token |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/me` | 当前用户信息 |

### 5.2 媒体库
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/media/libraries` | 媒体库列表 |
| POST | `/api/media/libraries` | 创建媒体库 |
| PUT | `/api/media/libraries/{id}` | 更新媒体库 |
| DELETE | `/api/media/libraries/{id}` | 删除媒体库 |
| POST | `/api/media/libraries/{id}/scan` | 触发扫描 |
| GET | `/api/media/items` | 媒体列表（分页/筛选） |
| GET | `/api/media/items/{id}` | 媒体详情 |
| POST | `/api/media/items/{id}/scrape` | 手动刮削 |
| GET | `/api/media/items/{id}/episodes` | 剧集列表 |

### 5.3 播放
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/playback/{id}/info` | 获取播放信息 |
| GET | `/api/playback/{id}/stream` | 直接视频流 |
| GET | `/api/playback/{id}/hls/{quality}/playlist.m3u8` | HLS 播放列表 |
| GET | `/api/playback/{id}/hls/{quality}/{segment}` | HLS 分片 |
| POST | `/api/playback/{id}/progress` | 上报播放进度 |
| GET | `/api/playback/{id}/subtitles` | 字幕列表 |
| PUT | `/api/playback/{id}/watched` | 标记已观看 |

### 5.4 下载
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/download/tasks` | 下载任务列表 |
| POST | `/api/download/add` | 添加下载 |
| POST | `/api/download/{id}/pause` | 暂停 |
| POST | `/api/download/{id}/resume` | 恢复 |
| DELETE | `/api/download/{id}` | 删除任务 |
| GET | `/api/download/clients` | 下载客户端列表 |
| POST | `/api/download/clients` | 添加客户端 |
| PUT | `/api/download/clients/{id}` | 更新客户端 |

### 5.5 订阅
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/subscribe/list` | 订阅列表 |
| POST | `/api/subscribe/add` | 添加订阅 |
| PUT | `/api/subscribe/{id}` | 更新订阅 |
| DELETE | `/api/subscribe/{id}` | 删除订阅 |
| POST | `/api/subscribe/{id}/search` | 手动触发搜索 |
| GET | `/api/subscribe/history` | 订阅历史 |

### 5.6 站点
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sites` | 站点列表 |
| POST | `/api/sites` | 添加站点 |
| PUT | `/api/sites/{id}` | 更新站点 |
| DELETE | `/api/sites/{id}` | 删除站点 |
| POST | `/api/sites/{id}/test` | 测试连接 |
| GET | `/api/sites/{id}/categories` | 站点分类 |

### 5.7 搜索
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search` | 全局搜索（关键词） |
| GET | `/api/search/tmdb` | TMDb 搜索 |
| GET | `/api/search/douban` | 豆瓣搜索 |
| GET | `/api/search/sites` | 站点资源搜索 |

### 5.8 系统
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/system/health` | 健康检查 |
| GET | `/api/system/info` | 系统信息 |
| GET | `/api/system/status` | 运行状态 |
| GET | `/api/system/events` | SSE 实时事件 |
| GET | `/api/system/logs` | 日志查询 |
| GET | `/api/system/tasks` | 调度任务列表 |
| GET | `/api/system/settings` | 系统设置 |
| PUT | `/api/system/settings` | 更新设置 |

---

## 六、前端关键组件设计

### 6.1 内置播放器（基于 hls.js + video.js）

```typescript
// composables/usePlayer.ts
export function usePlayer(mediaId: Ref<number>) {
  const playerRef = ref<HTMLVideoElement | null>(null)
  const hls = ref<Hls | null>(null)
  const quality = ref('auto')
  const currentTime = ref(0)
  const duration = ref(0)

  async function initPlayer() {
    const { mode, url, subtitles } = await api.playback.getPlayInfo(mediaId.value)

    if (mode === 'hls') {
      hls.value = new Hls({
        maxBufferLength: 30,
        maxMaxBufferLength: 60,
        startLevel: -1,  // 自动码率
      })
      hls.value.loadSource(url)
      hls.value.attachMedia(playerRef.value!)
      // 加载字幕
      subtitles.forEach(sub => addSubtitleTrack(sub))
    } else {
      // 直接播放
      playerRef.value!.src = url
    }

    // 自动保存进度（每 10 秒）
    setInterval(() => saveProgress(), 10000)
  }

  async function saveProgress() {
    await api.playback.reportProgress(mediaId.value, currentTime.value, duration.value)
  }

  return { playerRef, hls, quality, currentTime, duration, initPlayer, saveProgress }
}
```

### 6.2 SSE 实时事件

```typescript
// composables/useSSE.ts
export function useSSE() {
  const events = ref<ServerEvent[]>([])
  let source: EventSource | null = null

  function connect(token: string) {
    source = new EventSource(`/api/system/events?token=${token}`)
    source.addEventListener('download_progress', (e) => {
      events.value.push(JSON.parse(e.data))
    })
    source.addEventListener('transcode_progress', (e) => {
      events.value.push(JSON.parse(e.data))
    })
    source.addEventListener('scan_progress', (e) => {
      events.value.push(JSON.parse(e.data))
    })
    source.addEventListener('notify', (e) => {
      showNotification(JSON.parse(e.data))
    })
    source.onerror = () => {
      setTimeout(() => connect(token), 3000)  // 自动重连
    }
  }

  onUnmounted(() => source?.close())
  return { events, connect }
}
```

---

## 七、数据库 Schema（SQLite 零配置）

### 核心表

```sql
-- 媒体库
CREATE TABLE media_libraries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
    media_type TEXT NOT NULL DEFAULT 'movie',
    scan_interval INTEGER DEFAULT 60, enabled INTEGER DEFAULT 1
);

-- 媒体条目
CREATE TABLE media_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_id INTEGER REFERENCES media_libraries(id),
    tmdb_id INTEGER, douban_id TEXT, bangumi_id INTEGER,
    title TEXT NOT NULL, original_title TEXT,
    year INTEGER, overview TEXT,
    poster_url TEXT, backdrop_url TEXT,
    media_type TEXT NOT NULL, rating REAL DEFAULT 0,
    genres TEXT, file_path TEXT NOT NULL,
    file_size INTEGER DEFAULT 0, duration INTEGER DEFAULT 0,
    video_codec TEXT, audio_codec TEXT, resolution TEXT,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_scanned TIMESTAMP
);
CREATE INDEX idx_media_library ON media_items(library_id);
CREATE INDEX idx_media_type ON media_items(media_type);
CREATE INDEX idx_media_title ON media_items(title);

-- 剧集与集
CREATE TABLE media_seasons (...);
CREATE TABLE media_episodes (...);

-- 订阅
CREATE TABLE subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tmdb_id INTEGER, douban_id TEXT,
    media_type TEXT NOT NULL,
    quality_filter TEXT DEFAULT '',  -- JSON: 优先画质列表
    min_size INTEGER DEFAULT 0,     -- 最小体积 MB
    max_size INTEGER DEFAULT 0,     -- 最大体积 MB (0=不限)
    status TEXT DEFAULT 'active',   -- active/paused/completed
    last_search TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 站点
CREATE TABLE sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    site_type TEXT DEFAULT 'nexus_php',  -- nexus_php/gazelle/custom
    cookie TEXT,                        -- 加密存储
    rss_url TEXT,
    enabled INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 50,
    login_status TEXT DEFAULT 'unknown'
);

-- 下载任务
CREATE TABLE download_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id INTEGER REFERENCES media_items(id),
    subscription_id INTEGER REFERENCES subscriptions(id),
    client_id INTEGER REFERENCES download_clients(id),
    torrent_name TEXT,
    torrent_url TEXT,
    save_path TEXT,
    status TEXT DEFAULT 'downloading',  -- downloading/seeding/completed/failed
    progress REAL DEFAULT 0,
    size INTEGER DEFAULT 0,
    downloaded INTEGER DEFAULT 0,
    speed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- 下载客户端
CREATE TABLE download_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    client_type TEXT NOT NULL,    -- qbittorrent/transmission/aria2
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    username TEXT, password TEXT,  -- 加密存储
    enabled INTEGER DEFAULT 1
);

-- 通知渠道
CREATE TABLE notify_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    channel_type TEXT NOT NULL,   -- wechat/telegram/bark/webhook/email
    config TEXT NOT NULL,          -- JSON 配置
    enabled INTEGER DEFAULT 1,
    events TEXT DEFAULT '[]'       # 订阅的事件类型
);

-- 用户
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',     -- admin/user
    avatar TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 观看历史
CREATE TABLE watch_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    media_item_id INTEGER REFERENCES media_items(id),
    episode_id INTEGER REFERENCES media_episodes(id),
    progress REAL DEFAULT 0,      -- 播放进度 (秒)
    duration INTEGER DEFAULT 0,   -- 总时长 (秒)
    completed INTEGER DEFAULT 0,  -- 是否看完
    last_watched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 字幕
CREATE TABLE subtitles (...);

-- 系统设置 (KV 存储)
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 八、Docker 部署方案

### 8.1 Dockerfile（多阶段构建）

```dockerfile
# ============ 前端构建 ============
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ============ 后端运行 ============
FROM python:3.11-slim
WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY backend/ .

# 复制前端构建产物
COPY --from=frontend-builder /app/frontend/dist ./static

# 数据目录
RUN mkdir -p /data /data/media /data/config /data/cache /data/transcode

ENV PYTHONUNBUFFERED=1
ENV PORT=3001
ENV DATA_DIR=/data

EXPOSE 3001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001"]
```

### 8.2 docker-compose.yml（一键部署）

```yaml
version: "3.8"

services:
  mediastation:
    image: mediastation:latest
    container_name: mediastation
    restart: unless-stopped
    ports:
      - "3001:3001"
    environment:
      # 基础配置
      - TZ=Asia/Shanghai
      - PORT=3001
      - DATA_DIR=/data
      - SECRET_KEY=your-secret-key-change-me
      # 数据库（默认 SQLite，可选 PostgreSQL）
      # - DATABASE_URL=postgresql://user:pass@postgres:5432/mediastation
      # TMDb API（获取媒体元数据）
      - TMDB_API_KEY=your-tmdb-api-key
      # 豆瓣（可选）
      # - DOUBAN_COOKIE=your-douban-cookie
      # Bangumi（可选）
      # - BANGUMI_TOKEN=your-bangumi-token
      # 下载客户端
      - QB_HOST=http://qbittorrent:8080
      - QB_USERNAME=admin
      - QB_PASSWORD=adminadmin
    volumes:
      # 持久化数据
      - ./data:/data
      # 媒体文件目录（根据实际路径修改）
      - /path/to/movies:/data/media/movies
      - /path/to/tv:/data/media/tv
      - /path/to/anime:/data/media/anime
      # 下载目录（与 qBittorrent 共享）
      - /path/to/downloads:/data/downloads
      # 硬件加速（可选）
      # devices:
      #   - /dev/dri:/dev/dri
    networks:
      - mediastation-net

  # 可选：PostgreSQL（大规模媒体库使用）
  # postgres:
  #   image: postgres:16-alpine
  #   environment:
  #     POSTGRES_DB: mediastation
  #     POSTGRES_USER: mediastation
  #     POSTGRES_PASSWORD: mediastation123
  #   volumes:
  #     - ./postgres-data:/var/lib/postgresql/data
  #   networks:
  #     - mediastation-net

  # 可选：qBittorrent（如果未在 NAS 上单独部署）
  # qbittorrent:
  #   image: linuxserver/qbittorrent:latest
  #   ports:
  #     - "8080:8080"
  #   environment:
  #     - PUID=1000
  #     - PGID=1000
  #     - WEBUI_PORT=8080
  #   volumes:
  #     - ./qb-config:/config
  #     - /path/to/downloads:/downloads
  #   networks:
  #     - mediastation-net

networks:
  mediastation-net:
    driver: bridge
```

---

## 九、后台任务调度（APScheduler）

```python
# system/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

def setup_scheduler(app: FastAPI):
    scheduler = AsyncIOScheduler()

    # 媒体库自动扫描（每 60 分钟）
    scheduler.add_job(
        scan_all_libraries,
        trigger=IntervalTrigger(minutes=60),
        id="media_scan",
        name="媒体库扫描",
    )

    # 订阅自动搜索（每小时）
    scheduler.add_job(
        process_all_subscriptions,
        trigger=IntervalTrigger(hours=1),
        id="subscription_search",
        name="订阅搜索",
    )

    # 下载状态同步（每 30 秒）
    scheduler.add_job(
        sync_download_status,
        trigger=IntervalTrigger(seconds=30),
        id="download_sync",
        name="下载状态同步",
    )

    # 下载完成处理（文件整理 + 刮削入库）
    scheduler.add_job(
        process_completed_downloads,
        trigger=IntervalTrigger(minutes=5),
        id="download_complete",
        name="下载完成处理",
    )

    # 转码缓存清理（每天凌晨 3 点）
    scheduler.add_job(
        cleanup_transcode_cache,
        trigger=CronTrigger(hour=3, minute=0),
        id="cache_cleanup",
        name="转码缓存清理",
    )

    # RSS 订阅拉取（每 30 分钟）
    scheduler.add_job(
        pull_rss_feeds,
        trigger=IntervalTrigger(minutes=30),
        id="rss_pull",
        name="RSS 拉取",
    )

    @app.on_event("startup")
    async def start_scheduler():
        scheduler.start()

    @app.on_event("shutdown")
    async def shutdown_scheduler():
        scheduler.shutdown()
```

---

## 十、Emby 兼容层设计（可选模块）

实现 Emby Server API 子集，使 Infuse/Kodi/Emby 客户端可直接连接 MediaStation：

```python
# emby/router.py
emby_router = APIRouter(prefix="/emby", tags=["emby-compat"])

@emby_router.post("/Users/AuthenticateByName")
async def emby_auth(username: str, password: str):
    """Emby 兼容认证"""
    user = await user_service.authenticate(username, password)
    return {
        "User": {"Id": str(user.id), "Name": user.username},
        "AccessToken": create_emby_token(user.id),
        "ServerId": "mediastation"
    }

@emby_router.get("/Users/{user_id}/Items")
async def emby_browse_items(user_id: int, parent_id: str = None):
    """Emby 媒体浏览"""
    items = await media_service.get_items(library_id=parent_id)
    return {
        "Items": [to_emby_item(item) for item in items],
        "TotalRecordCount": len(items)
    }

@emby_router.get("/Videos/{item_id}/stream")
async def emby_stream(item_id: str):
    """Emby 视频流"""
    ...

@emby_router.get("/Videos/{item_id}/stream.{format}")
async def emby_hls_stream(item_id: str, format: str):
    """Emby HLS 流"""
    ...
```

---

## 十一、开发路线图

### Phase 1: MVP 核心播放（2 周）
- [ ] FastAPI 项目脚手架 + 配置中心
- [ ] SQLite 数据库 + Alembic 迁移
- [ ] JWT 认证（登录/刷新/登出）
- [ ] 媒体库管理（CRUD + 文件扫描）
- [ ] TMDb 元数据刮削
- [ ] 视频直接播放（MP4/WebM + Range 请求）
- [ ] HLS 转码播放（FFmpeg）
- [ ] Vue3 前端框架 + 媒体库页面 + 内置播放器
- [ ] Docker 一键部署

### Phase 2: 自动化订阅下载（2 周）
- [ ] qBittorrent / Transmission 客户端集成
- [ ] 站点管理（添加/测试/分类）
- [ ] NexusPHP 站点适配器
- [ ] RSS 订阅拉取 + 资源搜索
- [ ] 订阅管理（添加/暂停/删除）
- [ ] 下载完成自动整理 + 入库
- [ ] 通知推送（Telegram / 微信 / Bark）
- [ ] APScheduler 定时任务

### Phase 3: 增强体验（2 周）
- [ ] 豆瓣/Bangumi 刮削源
- [ ] 字幕管理（外挂/内嵌提取）
- [ ] 多用户权限 + 观看历史
- [ ] Emby API 兼容层（Infuse/Kodi 支持）
- [ ] PWA 移动端适配
- [ ] 硬件加速转码（QSV/VAAPI/NVENC）
- [ ] 系统监控仪表盘

### Phase 4: 高级功能（持续迭代）
- [ ] 自定义 RSS 站点
- [ ] Aria2 下载支持
- [ ] AI 辅助刮削（元数据补全）
- [ ] 海报墙 / 剧集季视图
- [ ] 播放列表 / 收藏夹
- [ ] DLNA 投屏
- [ ] PostgreSQL 可选切换
- [ ] 插件系统（预留接口）

---

## 十二、技术依赖清单

### 后端 (Python)
```
# backend/requirements.txt
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
sqlalchemy>=2.0
alembic>=1.14
aiosqlite>=0.20
pydantic>=2.10
pydantic-settings>=2.6
python-jose[cryptography]>=3.3
passlib[bcrypt]>=1.7
python-multipart>=0.0.18
httpx>=0.28
apscheduler>=3.10
cachetools>=5.5
aiofiles>=24.1
beautifulsoup4>=4.12
lxml>=5.3
Pillow>=11.0
sse-starlette>=2.1
structlog>=24.4
```

### 前端 (Node.js)
```json
{
  "dependencies": {
    "vue": "^3.5",
    "vue-router": "^4.5",
    "pinia": "^3.0",
    "axios": "^1.7",
    "hls.js": "^1.5",
    "video.js": "^8.22",
    "tailwindcss": "^3.4",
    "@vueuse/core": "^12.4"
  },
  "devDependencies": {
    "typescript": "^5.7",
    "vite": "^6.0",
    "@vitejs/plugin-vue": "^5.2",
    "vue-tsc": "^2.2",
    "autoprefixer": "^10.4",
    "postcss": "^8.4"
  }
}
```

---

## 十三、项目亮点总结

| 特性 | 说明 |
|------|------|
| 🪶 **极致轻量** | SQLite 零配置，单 Docker 容器，NAS N100 即可流畅运行 |
| ▶️ **内置播放** | HLS.js + FFmpeg，无需 Emby/Jellyfin 即可直接播放 |
| 📡 **自动化订阅** | 站点管理 + RSS + 智能搜索 + 自动下载 + 文件整理 |
| 🔄 **Emby 兼容** | 可选 Emby API 层，支持 Infuse/Kodi 等第三方客户端 |
| 🎨 **现代前端** | Vue3 + Tailwind + PWA，响应式设计，支持手机/平板 |
| ⚡ **硬件加速** | 自动检测 QSV/VAAPI/NVENC，低 CPU 消耗 |
| 🔌 **可扩展** | 站点适配器 + 下载客户端 + 通知渠道均插件化设计 |
| 🐳 **一键部署** | docker-compose up -d，零配置开箱即用 |
