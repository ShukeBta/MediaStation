# MediaStation 设置页面完善 — 本次变更概览

## 完成的工作

### 1. 后端接口增强（`backend/app/system/router.py`）

| 接口 | 变更 |
|------|------|
| `GET /api/system/info` | 新增 `ffmpeg_ok`, `ffprobe_ok`, `uptime`, `db_type`, `tmdb_language`, `start_time`, `max_transcode_jobs` 等字段 |
| `GET /api/system/scheduler` | 修正字段名，同时输出 `next_run_time`（前端用）和 `next_run`，增加 `trigger` 字段 |
| `POST /api/system/scheduler/{job_id}/trigger` | **新增** — 手动立即触发任意定时任务 |
| `GET /api/system/config` | **新增** — 获取可编辑系统配置（API Key 屏蔽明文） |
| `PATCH /api/system/config` | **新增** — 更新配置并持久化写入 `.env` 文件 |

---

### 2. 前端 API 层（`frontend/src/api/system.ts`）

新增 `triggerJob(jobId)`, `getConfig()`, `updateConfig(data)` 三个方法。

---

### 3. 设置页面 Tab 组件

#### SchedulerTab.vue（重写）
- 修复 `next_run_time` 字段对齐 Bug
- 新增「立即运行」按钮，触发后自动刷新列表
- Trigger 字符串人性化解析（`interval[0:30:00]` → `每 30 分钟`）
- 新增刷新按钮

#### SystemTab.vue（重写）
- 分三个卡片：应用信息、外部工具状态、资源监控
- TMDb 配置状态徽章（已配置/未配置 API Key）
- FFmpeg / FFprobe 可用性检测徽章
- 硬件加速标识（Intel QSV / NVIDIA NVENC 等）
- 内存/磁盘自动单位格式化（GB/TB）

#### GeneralTab.vue（全新）
- TMDb API Key 输入（支持显示/隐藏）
- 元数据语言选择（zh-CN/zh-TW/en-US/ja-JP/ko-KR）
- FFmpeg/FFprobe 路径配置
- 硬件加速模式选择
- 最大并发转码任务数
- 保存结果内联提示（成功/失败）

#### LibrariesTab.vue（增强）
- 每个媒体库显示**条目数量**（来自 `item_count` 字段）
- 扫描时显示进度 banner（带动画）
- 扫描完成显示结果：新增/更新/移除数量
- 删除提示文案更清晰（说明不删除实际文件）
- slide-down 动画过渡

---

### 4. SettingsView.vue
- 新增「全局配置」Tab，共 6 个 Tab：
  **媒体库 | 下载客户端 | 通知渠道 | 定时任务 | 全局配置 | 系统信息**

---

## 构建状态

```
✓ vue-tsc 类型检查：0 错误
✓ Vite 构建：140 模块，3.09s
✓ 产物已同步至 backend/static/
```

## 下一步建议

1. **用户管理**：添加修改密码、创建多用户功能
2. **站点搜索页**：专门的搜索页面，手动搜索资源并一键下载
3. **下载后自动入库**：下载完成后触发媒体扫描 + 刮削
4. **转码状态查看**：在系统信息页展示当前进行中的转码任务列表
